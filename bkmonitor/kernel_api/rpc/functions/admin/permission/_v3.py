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
# 权限 RPC —— v3 语义收口（query_user_permissions）
#
# v3 权限总览接口的全部 v3 专属逻辑：
#   - 策略查询显式走 v3 provider（不消费组合聚合结果，v3+v4 共配置时语义唯一）；
#   - v3 平台 AST（PolicyExpression）→ 权限树 entries 解析；
#   - 父路径 / 展示名经资源目录 catalog 做全响应级两阶段批量补全（每 rt 一次查询）；
#   - 对外 action_id 默认返回 v3 方言 ID（USE_DIALECT_ACTION_ID，历史契约）。
# ---------------------------------------------------------------------------

import logging
from collections import defaultdict
from typing import Any

from bkmonitor.iam.adapters import catalog
from bkmonitor.iam.adapters.catalog import parse_iam_path as _parse_iam_path
from bkmonitor.iam.iam_engine.core.exceptions import ProviderNotFound
from bkmonitor.iam.iam_engine.core.types import Subject as FwSubject, SubjectType
from bkmonitor.iam.iam_engine.django.facade import get_framework
from bkmonitor.iam.iam_engine.policy.expression import Op, PolicyExpression
from bkmonitor.iam.iam_engine.schema.definitions import ActionDef
from bkmonitor.iam.iam_engine.schema.registry import SchemaRegistry
from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.common import (
    SAFETY_LEVEL_READ,
    build_response,
    require_bk_tenant_id,
)

from ._shared import _get_v3_type

logger = logging.getLogger("kernel_api")

FUNC_QUERY_USER_PERMISSIONS = "admin.permission.query_user_permissions"
OPERATION_QUERY_USER_PERMISSIONS = "permission.query_user_permissions"

# ---------------------------------------------------------------------------
# action_id 返回形式开关
#
# True  → actions[].action_id 返回 V3 方言 ID（如 view_business_v2，IAM 平台注册的 ID），
#         与旧版接口 / 前端历史契约一致（参考 permission_result.json）
# False → 返回业务 ID（如 view_business，schema ActionDef.id）
#
# 仅对 v3 接口生效；v4 接口恒返回业务 ID。切换只改这一行即可，无需改动其他逻辑。
# ---------------------------------------------------------------------------
USE_DIALECT_ACTION_ID = True


# ============================================================================
# 通用辅助
# ============================================================================


def _normalize_username(value: Any) -> str:
    """Validate and normalize a username parameter."""
    username = str(value or "").strip()
    if not username:
        raise CustomException(message="username 为必填项")
    return username


def _to_dialect_action_id(v3_provider, biz_action_id: str) -> str:
    """业务 action_id → V3 方言 ID（IAM 平台注册的 ID）。

    通过 v3 provider 的 codec 编码；v3 查询链路中 provider 已显式校验存在，
    codec 必在，不再静默回退业务 ID。
    """
    return v3_provider.codec.encode_action(biz_action_id)


def _field_to_resource_type(field: str) -> str:
    """Extract resource type from IAM field name.

    "space.id" → "space", "apm_application._bk_iam_path_" → "apm_application"
    """
    return field.split(".")[0] if field else ""


# ============================================================================
# PolicyExpression → permission entries 解析（v3 AST 语义）
# ============================================================================


def _parse_expression_entries(expr: PolicyExpression) -> tuple[bool, list[dict]]:
    """Parse PolicyExpression AST into (is_all, entries).

    Each entry: {"path": [{"type": "space", "id": "2"}, ...]}
    """
    if expr is None:
        return False, []

    if expr.op == Op.ANY:
        return True, []

    if expr.op == Op.NONE:
        return False, []

    if expr.op == Op.IN:
        values = expr.value or ()
        if not values:
            return False, []
        typ = _field_to_resource_type(expr.field)
        return False, [{"path": [{"type": typ, "id": str(v)}]} for v in values]

    if expr.op == Op.EQ:
        value = expr.value
        if not value:
            return False, []
        typ = _field_to_resource_type(expr.field)
        return False, [{"path": [{"type": typ, "id": str(value)}]}]

    if expr.op == Op.STARTS_WITH:
        value = expr.value
        if not value:
            return False, []
        path = _parse_iam_path(str(value))
        return (False, [{"path": path}]) if path else (False, [])

    if expr.op == Op.OR:
        entries: list[dict] = []
        for child in expr.children:
            sub_all, sub_entries = _parse_expression_entries(child)
            if sub_all:
                return True, []
            entries.extend(sub_entries)
        return False, entries

    if expr.op == Op.AND:
        all_entries: list[list[dict]] = []
        for child in expr.children:
            sub_all, sub_entries = _parse_expression_entries(child)
            if sub_all:
                continue
            if sub_entries:
                all_entries.append(sub_entries)

        if not all_entries:
            return False, []

        result_entries = all_entries[0]
        for next_entries in all_entries[1:]:
            new_result: list[dict] = []
            for r in result_entries:
                for n in next_entries:
                    new_result.append({"path": r["path"] + n["path"]})
            result_entries = new_result
        return False, result_entries

    return False, []


def _parse_action_permissions(action: ActionDef, expr: PolicyExpression | None) -> tuple[str, list[dict], str | None]:
    """Return (grant_type, permissions, note).

    permissions: list of {"path": [{type, id, [display_name]}, ...]}
    """
    if expr is None:
        return "error", [], "IAM 查询失败"

    is_all, entries = _parse_expression_entries(expr)

    if is_all:
        return "all", [{"path": []}], None
    if not entries:
        return "none", [], None
    return "partial", entries, None


# ============================================================================
# 全响应级两阶段补全（父路径 + 展示名），经资源目录 catalog 批量查询
# ============================================================================


def _enrich_permissions(actions_result: list[dict], schema: SchemaRegistry) -> int:
    """父路径 + 展示名两阶段补全，等价于旧版逐 action 的
    _resolve_parent_paths + _resolve_display_names 语义。

    阶段 1（父路径）：对"头节点类型有祖先"的 entry 按 rt 归组，每 rt 一次 catalog 查询
    _bk_iam_path_ 后前置补齐父链；
    阶段 2（展示名）：收集所有 path 节点按 rt 归组，每 rt 一次 catalog 查询回填 display_name
    （apm/rum 取 name=app_name 口径，与历史契约一致）。

    DB 查询次数从 O(action × rt) 降为 O(rt)。返回 resolve_failed 计数（rt 查询失败数）。
    """
    resolve_failed = 0

    # ---- 阶段 1：父路径补全 ----
    head_entries: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for action in actions_result:
        for entry in action["permissions"]:
            path = entry["path"]
            if not path:
                continue
            head = path[0]
            try:
                rt_def = schema.get_resource_type(head["type"])
            except Exception:
                continue
            if rt_def.ancestor:
                head_entries[(head["type"], head["id"])].append(entry)

    ids_by_rt: dict[str, set[str]] = defaultdict(set)
    for rt, iid in head_entries:
        ids_by_rt[rt].add(iid)

    chains: dict[tuple[str, str], list[dict]] = {}
    for rt, ids in ids_by_rt.items():
        try:
            items = catalog.fetch_instance_info(rt, list(ids), requires=["_bk_iam_path_"])
        except Exception as e:
            logger.warning("Resolve parent path via catalog failed for rt=%s: %s", rt, e)
            resolve_failed += 1
            continue
        for item in items:
            chain = catalog.parse_iam_path(item.get("_bk_iam_path_", ""))
            if chain:
                chains[(rt, item["id"])] = chain

    for (rt, iid), entries in head_entries.items():
        chain = chains.get((rt, iid))
        if not chain:
            continue
        for entry in entries:
            path = entry["path"]
            if chain[-1] == path[0]:
                # 父链末段即头节点：去头后整体前置
                prefix = chain[:-1]
            else:
                # 历史数据父链末段与头节点不一致：只前置 path 中不存在的段
                prefix = [seg for seg in chain if seg not in path]
            entry["path"] = prefix + path

    # ---- 阶段 2：展示名回填 ----
    display_ids_by_rt: dict[str, set[str]] = defaultdict(set)
    for action in actions_result:
        for entry in action["permissions"]:
            for node in entry["path"]:
                display_ids_by_rt[node["type"]].add(node["id"])

    display_names: dict[str, dict[str, str]] = {}
    for rt, ids in display_ids_by_rt.items():
        try:
            items = catalog.fetch_instance_info(rt, list(ids), requires=["display_name", "name"])
        except Exception as e:
            logger.warning("Resolve display names via catalog failed for rt=%s: %s", rt, e)
            resolve_failed += 1
            continue
        display_names[rt] = {item["id"]: item.get("name") or item.get("display_name", "") for item in items}

    for action in actions_result:
        for entry in action["permissions"]:
            for node in entry["path"]:
                rt_names = display_names.get(node["type"])
                if rt_names is None:
                    # 该 rt 查询失败 → 与旧版降级语义一致：不补 display_name 字段
                    continue
                node["display_name"] = rt_names.get(node["id"], "")

    return resolve_failed


def _build_action_result_item(
    action: ActionDef,
    grant_type: str,
    permissions: list[dict],
    note: str | None = None,
) -> dict[str, Any]:
    item = {
        "action_id": action.id,
        "action_name": action.name,
        "type": _get_v3_type(action),
        "resource_type": action.resource_type or None,
        "grant_type": grant_type,
        "permissions": permissions,
    }
    if note:
        item["note"] = note
    return item


# ============================================================================
# 策略查询（显式 v3 provider，单源）
# ============================================================================


def _query_policies_with_fallback(
    v3_provider,
    subject: FwSubject,
    action_ids: list[str],
    warnings: list[dict],
    failed_action_ids: set[str],
) -> dict[str, PolicyExpression | None]:
    """批量优先 + 逐条降级查询 v3 策略表达式。

    单 provider 语义三态（调用方据此区分"查询失败"与"无权限"）：
      * aid in failed_action_ids  → 查询失败（上层标 error），并在 warnings 记录
      * policies[aid] 为 None      → 无权限兜底（v3 无策略时正常返回 none()，None 仅兜底）
      * policies[aid] 为表达式     → 按 AST 解析（none() 表示无权限）
    """
    try:
        return v3_provider.query_policy_by_actions(subject, action_ids)
    except Exception as e:
        logger.warning("Batch IAM policy query failed, falling back to individual queries: %s", e)
        warnings.append(
            {
                "code": "IAM_BATCH_FAILED",
                "message": "批量 IAM 策略查询失败，已降级为逐操作查询",
                "details": {"error": str(e)},
            }
        )

    policies: dict[str, PolicyExpression | None] = {}
    for aid in action_ids:
        try:
            policies[aid] = v3_provider.query_policy(subject, aid)
        except Exception as e:
            logger.warning("IAM query failed for action %s: %s", aid, e)
            policies[aid] = None
            failed_action_ids.add(aid)
            warnings.append(
                {
                    "code": "IAM_QUERY_FAILED",
                    "message": f"操作 {aid} 的 IAM 策略查询失败，已跳过",
                    "details": {"action_id": aid, "error": str(e)},
                }
            )
    return policies


# ============================================================================
# RPC Functions
# ============================================================================


@KernelRPCRegistry.register(
    FUNC_QUERY_USER_PERMISSIONS,
    summary="查询指定用户的全部 IAM 权限",
    description=(
        "查询指定用户的所有 IAM 操作权限（操作→空间映射）。"
        "通过 v3 provider 批量获取策略表达式，本地递归解析，"
        "父路径 / 展示名经资源目录 catalog 做全响应级批量补全。"
    ),
    params_schema={
        "username": "必填，要查询的用户名",
        "bk_tenant_id": "必填，租户 ID",
    },
    example_params={"username": "admin", "bk_tenant_id": "system"},
)
def query_user_permissions(params: dict[str, Any]) -> dict[str, Any]:
    username = _normalize_username(params.get("username"))
    bk_tenant_id = require_bk_tenant_id(params)

    fw = get_framework()
    try:
        v3_provider = fw.get_provider("v3")
    except ProviderNotFound:
        raise CustomException(
            message="当前 IAM 后端未配置 v3 provider，v3 权限总览接口不可用；"
            "请使用 admin.permission.query_user_permissions_v4"
        ) from None
    schema = fw.schema
    subject = FwSubject(id=username, type=SubjectType.USER, tenant_id=bk_tenant_id)

    all_actions_list = schema.all_actions()
    action_ids = [a.id for a in all_actions_list]

    # 通过 v3 provider 查询策略表达式：批量优先，失败时降级为逐个 action 查询
    warnings: list[dict] = []
    failed_action_ids: set[str] = set()
    policies = _query_policies_with_fallback(v3_provider, subject, action_ids, warnings, failed_action_ids)

    # 一次遍历同时构造 actions_result 与累计 summary
    actions_result: list[dict[str, Any]] = []
    granted_actions = 0

    for action in all_actions_list:
        # 语义区分（单 provider 三态，见 _query_policies_with_fallback）：
        #   * aid in failed_action_ids           → 查询失败 (grant_type=error)
        #   * policies[aid] 为 None              → 无权限   (grant_type=none)
        #   * policies[aid] 为表达式（含 none()）→ 按 AST 解析
        if action.id in failed_action_ids:
            grant_type, permissions, note = "error", [], "IAM 查询失败"
        else:
            expr = policies.get(action.id)
            if expr is None:
                grant_type, permissions, note = "none", [], None
            else:
                grant_type, permissions, note = _parse_action_permissions(action, expr)

        item = _build_action_result_item(action, grant_type, permissions, note)
        if USE_DIALECT_ACTION_ID:
            # 对外返回 V3 方言 ID（IAM 平台注册的 ID）；切换开关见 USE_DIALECT_ACTION_ID
            item["action_id"] = _to_dialect_action_id(v3_provider, action.id)
        actions_result.append(item)

        if grant_type in ("partial", "all"):
            granted_actions += 1

    # 全响应级两阶段补全：父路径 + 展示名（每 rt 一次 catalog 批量查询）
    resolve_failed = 0
    try:
        resolve_failed = _enrich_permissions(actions_result, schema)
    except Exception as e:
        # DB 不可用等场景：权限数据本身可用，仅缺失父路径/展示名，降级跳过
        logger.warning("Enrich parent/display names failed: %s", e)
        resolve_failed = len(actions_result)

    if resolve_failed:
        warnings.append(
            {
                "code": "IAM_RESOLVE_FAILED",
                "message": (f"{resolve_failed} 类资源的父路径/展示名解析失败（权限数据不受影响）"),
            }
        )

    summary = {
        "total_actions": len(actions_result),
        "granted_actions": granted_actions,
    }

    return build_response(
        operation=OPERATION_QUERY_USER_PERMISSIONS,
        func_name=FUNC_QUERY_USER_PERMISSIONS,
        bk_tenant_id=bk_tenant_id,
        data={
            "username": username,
            "bk_tenant_id": bk_tenant_id,
            "actions": actions_result,
            "summary": summary,
        },
        warnings=warnings,
        safety_level=SAFETY_LEVEL_READ,
    )
