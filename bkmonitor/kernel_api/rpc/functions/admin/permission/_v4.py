"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

# ---------------------------------------------------------------------------
# 权限 RPC —— v4 语义（query_user_permissions_v4 / query_user_sub_resources_v4）
#
# v4 平台限制：authorized-resources 仅支持顶层资源（一级）反向查询，二级资源
# （apm_application / grafana_dashboard / rum_application）只能"遍历资源数据库表
# 枚举候选 + 正向批量鉴权"。因此拆为两个端点，支持前端分阶段加载：
#   - query_user_permissions_v4（总览）：全局 action + space 级授权 + 二级 action
#     的 deferred 标记（零平台调用）；前端首次加载一次拿全；
#   - query_user_sub_resources_v4（展开）：指定空间下指定 action 集合的二级资源
#     授权明细；浏览器可对（空间 × 资源类型）并发多个请求，不重复查询总览数据。
#
# codec 边界：本模块禁止直连 V4Client、禁止假设 v4 恒等映射，只消费 provider
# 方法（get_authorized_resources / batch_by_*，其内部已按 MonitorV4Codec 完成
# 编解码）；出参 action_id 恒为 schema 业务 ID。未来 v4 codec 变化时本模块与
# 前端契约零改动。
# ---------------------------------------------------------------------------

import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from bkmonitor.iam.adapters import catalog
from bkmonitor.iam.iam_engine.core.exceptions import ProviderNotFound
from bkmonitor.iam.iam_engine.core.types import (
    BatchByActionRequest,
    BatchByResourceRequest,
    ResourceInstance,
    Subject as FwSubject,
    SubjectType,
)
from bkmonitor.iam.iam_engine.django.facade import get_framework
from bkmonitor.iam.iam_engine.schema.definitions import ActionDef
from bkmonitor.iam.iam_engine.schema.registry import SchemaRegistry
from bkmonitor.iam.iam_engine.schema.visibility import is_visible_to
from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.common import (
    SAFETY_LEVEL_READ,
    build_response,
    require_bk_tenant_id,
)

from ._v3 import _normalize_username

logger = logging.getLogger("kernel_api")

FUNC_QUERY_USER_PERMISSIONS_V4 = "admin.permission.query_user_permissions_v4"
OPERATION_QUERY_USER_PERMISSIONS_V4 = "permission.query_user_permissions_v4"

FUNC_QUERY_USER_SUB_RESOURCES_V4 = "admin.permission.query_user_sub_resources_v4"
OPERATION_QUERY_USER_SUB_RESOURCES_V4 = "permission.query_user_sub_resources_v4"

# 总览中 space 级授权的并发查询 worker 数（get_authorized_resources 每 action 1 次）
_SPACE_QUERY_WORKERS = 8

# 二级资源枚举的分页大小（catalog.list_instances 单页上限）
_LIST_PAGE_SIZE = 1000


# ============================================================================
# 通用辅助
# ============================================================================


def _normalize_bk_biz_id(value: Any) -> int:
    """Validate and normalize a bk_biz_id parameter（可负整数）。"""
    raw = str(value).strip()
    try:
        return int(raw)
    except (TypeError, ValueError):
        raise CustomException(message="bk_biz_id 必填且必须为整数") from None


def _normalize_action_ids(params: dict[str, Any], schema: SchemaRegistry) -> tuple[list[ActionDef], list[dict]]:
    """解析可选 action_ids 参数（逗号分隔字符串或列表），未知 / 对 v4 不可见 ID 记 warning 跳过。

    缺省返回 schema 中对 v4 平台可见的全部 action：exclude_providers=("v4",) 的
    过时 action（如 view_dashboard / manage_dashboard）不进入 v4 查询，
    与 V4Migrator 的平台注册口径保持一致。返回 (actions, warnings)。
    """
    raw = params.get("action_ids")
    warnings: list[dict] = []
    if raw in (None, ""):
        return [a for a in schema.all_actions() if is_visible_to(a, "v4")], warnings

    if isinstance(raw, str):
        raw_ids = [s.strip() for s in raw.split(",") if s.strip()]
    elif isinstance(raw, list | tuple | set):
        raw_ids = [str(s).strip() for s in raw if str(s).strip()]
    else:
        raise CustomException(message="action_ids 必须是字符串或列表")

    actions: list[ActionDef] = []
    for aid in raw_ids:
        try:
            action = schema.get_action(aid)
        except Exception:
            warnings.append(
                {
                    "code": "IAM_UNKNOWN_ACTION",
                    "message": f"未知操作 {aid}，已忽略",
                    "details": {"action_id": aid},
                }
            )
            continue
        if not is_visible_to(action, "v4"):
            warnings.append(
                {
                    "code": "IAM_UNSUPPORTED_ACTION",
                    "message": f"操作 {aid} 不适用于 v4 后端（exclude_providers），已忽略",
                    "details": {"action_id": aid},
                }
            )
            continue
        actions.append(action)
    return actions, warnings


def _action_kind(action: ActionDef, schema: SchemaRegistry) -> str:
    """按 action 关联资源类型划分：global / top / sub。"""
    rt_id = action.resource_type or ""
    if not rt_id:
        return "global"
    try:
        rt_def = schema.get_resource_type(rt_id)
    except Exception:
        # 未知类型保守按顶级处理（不查平台），仅兜底
        return "top"
    return "top" if not rt_def.ancestor else "sub"


def _build_v4_action_item(
    action: ActionDef,
    grant_type: str,
    permissions: list[dict] | None = None,
    sub_resources: list[dict] | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    return {
        "action_id": action.id,
        "action_name": action.name,
        "resource_type": action.resource_type or None,
        "grant_type": grant_type,
        "permissions": permissions or [],
        "sub_resources": sub_resources,
        "note": note,
    }


def _parse_authorized(authorized: list[dict], rt_biz: str) -> tuple[bool, set[str]]:
    """解析 get_authorized_resources 返回（provider 已 decode 为业务命名）。

    Returns (all_granted, ids)：
      * ids 含 "*" → all_granted=True（该资源类型下任意资源均有权限）
      * 其余 id 收集到集合（跳过 "*"）
    """
    all_granted = False
    ids: set[str] = set()
    for item in authorized or []:
        if item.get("type") != rt_biz:
            continue
        item_ids = item.get("ids") or []
        if "*" in item_ids:
            all_granted = True
        ids.update(str(i) for i in item_ids if i != "*")
    return all_granted, ids


def _query_space_grant(v4_provider, subject: FwSubject, action: ActionDef) -> tuple[str, list[dict], str | None]:
    """查询单个 space 级 action 的授权条目。

    Returns (grant_type, permissions, error)；error 非 None 表示平台调用失败。
    """
    authorized = v4_provider.get_authorized_resources(subject, action.id)
    all_granted, ids = _parse_authorized(authorized, action.resource_type)
    if all_granted:
        return "all", [{"resource_type": action.resource_type, "resource_id": "*", "display_name": ""}], None
    if not ids:
        return "none", [], None
    permissions = [{"resource_type": action.resource_type, "resource_id": i, "display_name": ""} for i in sorted(ids)]
    return "partial", permissions, None


def _fill_space_display_names(items: list[dict], bk_tenant_id: str) -> None:
    """为总览 space 授权条目批量补全展示名（一次 catalog 查询）。"""
    space_ids = {p["resource_id"] for item in items for p in item["permissions"] if p["resource_id"] != "*"}
    if not space_ids:
        return
    try:
        fetched = catalog.fetch_instance_info(
            "space", list(space_ids), requires=["display_name"], bk_tenant_id=bk_tenant_id
        )
    except Exception as e:
        logger.warning("Resolve space display names failed: %s", e)
        return
    names = {item["id"]: item.get("display_name", "") for item in fetched}
    for item in items:
        for p in item["permissions"]:
            if p["resource_id"] != "*":
                p["display_name"] = names.get(p["resource_id"], "")


def _list_all_instances(rt_id: str, bk_biz_id: str, bk_tenant_id: str) -> list[dict]:
    """翻页收集资源目录枚举的全部候选实例（每页 ≤1000）。"""
    parent = {"type": "space", "id": bk_biz_id}
    collected: list[dict] = []
    page = 1
    while True:
        result = catalog.list_instances(
            rt_id, {"parent": parent}, {"page": page, "page_size": _LIST_PAGE_SIZE}, bk_tenant_id=bk_tenant_id
        )
        items = result.get("results") or []
        collected.extend(items)
        if not items or len(collected) >= (result.get("count") or 0):
            break
        page += 1
    return collected


def _require_v4_provider(fw):
    """显式获取 v4 provider；未配置时明确报错（不静默降级）。"""
    try:
        return fw.get_provider("v4")
    except ProviderNotFound:
        raise CustomException(
            message="当前 IAM 后端未配置 v4 provider，v4 权限查询接口不可用；"
            "请使用 admin.permission.query_user_permissions"
        ) from None


# ============================================================================
# RPC Functions
# ============================================================================


@KernelRPCRegistry.register(
    FUNC_QUERY_USER_PERMISSIONS_V4,
    summary="查询指定用户的全部 IAM 权限（v4 总览）",
    description=(
        "v4 权限总览：返回全局操作、space 级授权，以及二级资源操作的 deferred 标记"
        "（二级资源授权需调用 query_user_sub_resources_v4 按空间展开）。"
    ),
    params_schema={
        "username": "必填，要查询的用户名",
        "bk_tenant_id": "必填，租户 ID",
        "action_ids": "可选，只查询指定操作（业务 ID，逗号分隔或列表）",
    },
    example_params={"username": "admin", "bk_tenant_id": "system"},
)
def query_user_permissions_v4(params: dict[str, Any]) -> dict[str, Any]:
    username = _normalize_username(params.get("username"))
    bk_tenant_id = require_bk_tenant_id(params)

    fw = get_framework()
    v4_provider = _require_v4_provider(fw)
    schema = fw.schema
    subject = FwSubject(id=username, type=SubjectType.USER, tenant_id=bk_tenant_id)

    warnings: list[dict] = []
    actions, filter_warnings = _normalize_action_ids(params, schema)
    warnings.extend(filter_warnings)
    action_by_id = {a.id: a for a in actions}

    global_actions = [a for a in actions if _action_kind(a, schema) == "global"]
    space_actions = [a for a in actions if _action_kind(a, schema) == "top"]
    sub_actions = [a for a in actions if _action_kind(a, schema) == "sub"]

    result_by_id: dict[str, dict] = {}

    # ---- 全局 action：一次批量（无关资源类型） ----
    if global_actions:
        try:
            batch = v4_provider.batch_by_action(
                BatchByActionRequest(subject=subject, action_ids=tuple(a.id for a in global_actions), resource=None)
            )
            allowed_map = {item.action_id: item.allowed for item in batch.items}
        except Exception as e:
            logger.warning("Batch auth for global actions failed: %s", e)
            allowed_map = {}
            for action in global_actions:
                warnings.append(
                    {
                        "code": "IAM_QUERY_FAILED",
                        "message": f"操作 {action.id} 的 IAM 鉴权查询失败",
                        "details": {"action_id": action.id, "error": str(e)},
                    }
                )
        for action in global_actions:
            if action.id in allowed_map:
                result_by_id[action.id] = _build_v4_action_item(action, "all" if allowed_map[action.id] else "none")
            else:
                result_by_id[action.id] = _build_v4_action_item(action, "error", note="IAM 查询失败")

    # ---- space 级授权：每 action 1 次 get_authorized_resources，并发 ----
    if space_actions:
        workers = min(_SPACE_QUERY_WORKERS, len(space_actions))
        futures = {}
        with ThreadPoolExecutor(max_workers=workers) as executor:
            for action in space_actions:
                futures[executor.submit(_query_space_grant, v4_provider, subject, action)] = action.id
            for future in as_completed(futures):
                aid = futures[future]
                action = action_by_id[aid]
                try:
                    grant_type, permissions, err = future.result()
                except Exception as e:
                    grant_type, permissions, err = "error", [], e
                if err is not None:
                    warnings.append(
                        {
                            "code": "IAM_QUERY_FAILED",
                            "message": f"操作 {aid} 的 IAM 授权查询失败",
                            "details": {"action_id": aid, "error": str(err)},
                        }
                    )
                    grant_type = "error"
                result_by_id[aid] = _build_v4_action_item(
                    action, grant_type, permissions, note="IAM 查询失败" if err else None
                )

    # ---- 二级资源 action：deferred（平台不支持二级反向查询，不查平台） ----
    for action in sub_actions:
        result_by_id[action.id] = _build_v4_action_item(
            action,
            "deferred",
            note="二级资源授权需调用 query_user_sub_resources_v4 按空间展开",
        )

    # ---- space 授权条目展示名批量补全 ----
    _fill_space_display_names(list(result_by_id.values()), bk_tenant_id)

    actions_result = [result_by_id[a.id] for a in actions]
    summary = {
        "total_actions": len(actions_result),
        "granted_actions": sum(1 for a in actions_result if a["grant_type"] in ("all", "partial")),
        "deferred_actions": sum(1 for a in actions_result if a["grant_type"] == "deferred"),
        "error_actions": sum(1 for a in actions_result if a["grant_type"] == "error"),
    }

    return build_response(
        operation=OPERATION_QUERY_USER_PERMISSIONS_V4,
        func_name=FUNC_QUERY_USER_PERMISSIONS_V4,
        bk_tenant_id=bk_tenant_id,
        data={
            "username": username,
            "bk_tenant_id": bk_tenant_id,
            "backend": "v4",
            "actions": actions_result,
            "summary": summary,
        },
        warnings=warnings,
        safety_level=SAFETY_LEVEL_READ,
    )


@KernelRPCRegistry.register(
    FUNC_QUERY_USER_SUB_RESOURCES_V4,
    summary="查询指定空间下二级资源操作的全部授权（v4 展开）",
    description=(
        "v4 二级资源授权明细：按 bk_biz_id 枚举该空间下的二级资源实例"
        "（遍历资源数据库表），再按 action 正向批量鉴权；"
        "只返回二级资源操作的授权明细，不包含全局 / 顶层数据。"
    ),
    params_schema={
        "username": "必填，要查询的用户名",
        "bk_tenant_id": "必填，租户 ID",
        "bk_biz_id": "必填，指定空间 ID（可负）",
        "action_ids": ("可选，只查询指定操作（业务 ID，逗号分隔或列表；缺省 = 全部二级资源操作）"),
    },
    example_params={"username": "admin", "bk_tenant_id": "system", "bk_biz_id": 2},
)
def query_user_sub_resources_v4(params: dict[str, Any]) -> dict[str, Any]:
    username = _normalize_username(params.get("username"))
    bk_tenant_id = require_bk_tenant_id(params)
    bk_biz_id = _normalize_bk_biz_id(params.get("bk_biz_id"))

    fw = get_framework()
    v4_provider = _require_v4_provider(fw)
    schema = fw.schema
    subject = FwSubject(id=username, type=SubjectType.USER, tenant_id=bk_tenant_id)

    warnings: list[dict] = []
    actions, filter_warnings = _normalize_action_ids(params, schema)
    warnings.extend(filter_warnings)

    # 只接受二级资源操作，其余记 warning 忽略
    eligible: list[ActionDef] = []
    for action in actions:
        if _action_kind(action, schema) == "sub":
            eligible.append(action)
        else:
            warnings.append(
                {
                    "code": "IAM_UNSUPPORTED_ACTION",
                    "message": f"操作 {action.id} 不关联二级资源，已忽略",
                    "details": {"action_id": action.id},
                }
            )

    actions_by_rt: dict[str, list[ActionDef]] = defaultdict(list)
    for action in eligible:
        actions_by_rt[action.resource_type].append(action)

    items: list[dict] = []
    for rt, rt_actions in actions_by_rt.items():
        # 1) 遍历资源数据库表枚举候选（含 display_name）
        try:
            candidates = _list_all_instances(rt, str(bk_biz_id), bk_tenant_id)
        except Exception as e:
            logger.warning("Enumerate sub resources failed for rt=%s: %s", rt, e)
            warnings.append(
                {
                    "code": "IAM_SUB_RESOURCE_ENUM_FAILED",
                    "message": f"资源类型 {rt} 的实例枚举失败",
                    "details": {"resource_type": rt, "error": str(e)},
                }
            )
            for action in rt_actions:
                items.append(_build_v4_action_item(action, "error", note="二级资源枚举失败"))
            continue

        if not candidates:
            for action in rt_actions:
                items.append(_build_v4_action_item(action, "none", note="该空间下无此资源类型的实例"))
            continue

        # 2) 按 action 正向批量鉴权（provider 内部 20/批分片 + 并发）
        candidate_by_id = {c["id"]: c for c in candidates}
        resources = tuple(ResourceInstance(type=rt, id=c["id"]) for c in candidates)
        for action in rt_actions:
            try:
                auth_result = v4_provider.batch_by_resource(
                    BatchByResourceRequest(subject=subject, action_id=action.id, resources=resources)
                )
            except Exception as e:
                logger.warning("Batch auth failed for action %s: %s", action.id, e)
                warnings.append(
                    {
                        "code": "IAM_BATCH_AUTH_FAILED",
                        "message": f"操作 {action.id} 的实例鉴权失败",
                        "details": {"action_id": action.id, "error": str(e)},
                    }
                )
                items.append(_build_v4_action_item(action, "error", note="IAM 查询失败"))
                continue

            allowed_ids = [item.resource_id for item in auth_result.items if item.allowed]
            if len(allowed_ids) == len(candidates):
                grant_type = "all"
            elif allowed_ids:
                grant_type = "partial"
            else:
                grant_type = "none"

            sub_resources = [
                {
                    "resource_id": rid,
                    "display_name": candidate_by_id.get(rid, {}).get("display_name", ""),
                    "parent": {"type": "space", "id": str(bk_biz_id)},
                }
                for rid in allowed_ids
            ]
            items.append(_build_v4_action_item(action, grant_type, sub_resources=sub_resources))

    summary = {
        "total_actions": len(eligible),
        "granted_actions": sum(1 for a in items if a["grant_type"] in ("all", "partial")),
        "error_actions": sum(1 for a in items if a["grant_type"] == "error"),
    }

    return build_response(
        operation=OPERATION_QUERY_USER_SUB_RESOURCES_V4,
        func_name=FUNC_QUERY_USER_SUB_RESOURCES_V4,
        bk_tenant_id=bk_tenant_id,
        data={
            "username": username,
            "bk_tenant_id": bk_tenant_id,
            "backend": "v4",
            "bk_biz_id": bk_biz_id,
            "actions": items,
            "summary": summary,
        },
        warnings=warnings,
        safety_level=SAFETY_LEVEL_READ,
    )
