"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
from collections import defaultdict
from typing import Any

from bkm_space.api import SpaceApi

from bkmonitor.iam.definitions.actions import Actions
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
    get_bk_tenant_id,
    require_bk_tenant_id,
)

logger = logging.getLogger("kernel_api")

FUNC_ACTION_CATEGORIES = "admin.permission.action_categories"
FUNC_QUERY_USER_PERMISSIONS = "admin.permission.query_user_permissions"

OPERATION_ACTION_CATEGORIES = "permission.action_categories"
OPERATION_QUERY_USER_PERMISSIONS = "permission.query_user_permissions"

# ---------------------------------------------------------------------------
# action_id 返回形式开关
#
# True  → actions[].action_id 返回 V3 方言 ID（如 view_business_v2，IAM 平台注册的 ID），
#         与旧版接口 / 前端历史契约一致（参考 permission_result.json）
# False → 返回业务 ID（如 view_business，schema ActionDef.id）
#
# 切换只改这一行即可，无需改动其他逻辑。
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


def _get_v3_type(action: ActionDef) -> str:
    """从 ActionDef.extensions 获取 v3 type（view / manage）。"""
    return action.extensions.get("v3", {}).get("type", "")


def _to_dialect_action_id(fw, biz_action_id: str) -> str:
    """业务 action_id → V3 方言 ID（IAM 平台注册的 ID）。

    通过 v3 provider 的 codec 编码；codec 不可用时回退业务 ID（恒等）。
    """
    v3_provider = getattr(fw, "providers", {}).get("v3")
    codec = getattr(v3_provider, "codec", None)
    if codec is not None:
        return codec.encode_action(biz_action_id)
    return biz_action_id


def _parse_iam_path(path_value: str) -> list[dict[str, str]]:
    """Parse _bk_iam_path_ value into path chain. Fully generic, not coupled to resource type or depth.

    "/space,2/"            → [{"type": "space", "id": "2"}]
    "/space,2/apm_app,3/"  → [{"type": "space", "id": "2"}, {"type": "apm_app", "id": "3"}]
    """
    segments = [s for s in path_value.strip("/").split("/") if s]
    result: list[dict[str, str]] = []
    for seg in segments:
        typ, _, idx = seg.partition(",")
        if idx:
            result.append({"type": typ, "id": idx})
    return result


def _field_to_resource_type(field: str) -> str:
    """Extract resource type from IAM field name.

    "space.id" → "space", "apm_application._bk_iam_path_" → "apm_application"
    """
    return field.split(".")[0] if field else ""


# ============================================================================
# PolicyExpression → permission entries 解析
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
# 父资源 / 展示名 解析（替代已删除的 batch_get_parent / batch_get_display_names）
# ============================================================================


def _batch_get_parent(rt: str, instance_ids: set[str]) -> dict[str, str]:
    """Resolve parent resource IDs for given resource type instances.
    Returns {instance_id: parent_id}.
    """
    if not instance_ids:
        return {}
    fn = _PARENT_RESOLVERS.get(rt)
    return fn(instance_ids) if fn else {}


def _resolve_apm_app_parent(instance_ids: set[str]) -> dict[str, str]:
    """ApmApplication → space 父资源解析。"""
    try:
        from apm_web.models import Application

        qs = Application.objects.filter(application_id__in=instance_ids).values("application_id", "bk_biz_id")
        return {str(row["application_id"]): str(row["bk_biz_id"]) for row in qs if row["bk_biz_id"] is not None}
    except ImportError:
        return {}


def _resolve_grafana_dashboard_parent(instance_ids: set[str]) -> dict[str, str]:
    """GrafanaDashboard → space 父资源解析。
    dashboard id 格式: "{org_id}|{uid}" → 通过 org_id 找对应 space。
    暂返回空（Grafana dashboard 的 space 归属需要额外查询）。
    """
    return {}


def _resolve_rum_app_parent(instance_ids: set[str]) -> dict[str, str]:
    """RumApplication → space 父资源解析。"""
    try:
        from apm_web.models import Application

        qs = Application.objects.filter(application_id__in=instance_ids).values("application_id", "bk_biz_id")
        return {str(row["application_id"]): str(row["bk_biz_id"]) for row in qs if row["bk_biz_id"] is not None}
    except ImportError:
        return {}


_PARENT_RESOLVERS: dict[str, Any] = {
    "apm_application": _resolve_apm_app_parent,
    "grafana_dashboard": _resolve_grafana_dashboard_parent,
    "rum_application": _resolve_rum_app_parent,
}


def _resolve_parent_paths(permissions: list[dict], schema: SchemaRegistry) -> None:
    """沿资源拓扑向上递归补齐 path 首节点的父资源，直到顶级（ancestor 为空）。"""
    while True:
        groups_by_type: dict[str, list[tuple[dict, str]]] = defaultdict(list)
        for entry in permissions:
            path = entry["path"]
            if not path:
                continue
            head_type = path[0]["type"]
            try:
                rt_def = schema.get_resource_type(head_type)
            except Exception:
                continue
            if not rt_def.ancestor:
                continue
            groups_by_type[head_type].append((entry, path[0]["id"]))

        if not groups_by_type:
            break

        made_progress = False
        for rt, items in groups_by_type.items():
            instance_ids = {iid for _, iid in items}
            parent_map = _batch_get_parent(rt, instance_ids)
            if not parent_map:
                continue
            rt_def = schema.get_resource_type(rt)
            parent_rt_id = rt_def.ancestor
            for entry, iid in items:
                parent_id = parent_map.get(iid)
                if parent_id:
                    entry["path"].insert(0, {"type": parent_rt_id, "id": parent_id})
                    made_progress = True

        if not made_progress:
            break


# ---- 展示名解析 ----

_EMPTY_DISPLAY: dict[str, str] = {}


def _get_space_display_names(ids: set[str]) -> dict[str, str]:
    """通过 SpaceApi 获取空间展示名。"""
    try:
        spaces = SpaceApi.list_spaces_dict()
        return {str(s["bk_biz_id"]): s.get("display_name", "") for s in spaces if str(s["bk_biz_id"]) in ids}
    except Exception as e:
        logger.warning("Failed to resolve space display names: %s", e)
        return {}


def _get_apm_app_display_names(ids: set[str]) -> dict[str, str]:
    """APM 应用展示名。"""
    try:
        from apm_web.models import Application

        qs = Application.objects.filter(application_id__in=ids).values("application_id", "app_name")
        return {str(row["application_id"]): row["app_name"] for row in qs}
    except ImportError:
        return {}


def _get_grafana_dashboard_display_names(ids: set[str]) -> dict[str, str]:
    """Grafana dashboard 展示名。"""
    return {}


def _get_rum_app_display_names(ids: set[str]) -> dict[str, str]:
    """RUM 应用展示名。"""
    try:
        from apm_web.models import Application

        qs = Application.objects.filter(application_id__in=ids).values("application_id", "app_name")
        return {str(row["application_id"]): row["app_name"] for row in qs}
    except ImportError:
        return {}


_DISPLAY_NAME_RESOLVERS: dict[str, Any] = {
    "space": _get_space_display_names,
    "apm_application": _get_apm_app_display_names,
    "grafana_dashboard": _get_grafana_dashboard_display_names,
    "rum_application": _get_rum_app_display_names,
}


def _resolve_display_names(permissions: list[dict]) -> None:
    """Fill display_name for all path nodes in-place, via polymorphic batch query."""
    ids_by_type: dict[str, set[str]] = defaultdict(set)
    for entry in permissions:
        for node in entry["path"]:
            ids_by_type[node["type"]].add(node["id"])

    display_names: dict[str, dict[str, str]] = {}
    for rt, ids in ids_by_type.items():
        fn = _DISPLAY_NAME_RESOLVERS.get(rt)
        display_names[rt] = fn(ids) if fn else _EMPTY_DISPLAY

    for entry in permissions:
        for node in entry["path"]:
            node["display_name"] = display_names.get(node["type"], _EMPTY_DISPLAY).get(node["id"], "")


# ============================================================================
# 操作业务分组定义：分类名 → action 枚举集合（Business ID）
#
# 使用 Actions 枚举（而非硬编码字符串），typo / 改名在 import 时即暴露。
# 新增 action 未在此登记时，自动归入"其他"组（见 _get_action_category）。
# ============================================================================

_ACTION_CATEGORY_MAP: dict[str, frozenset[str]] = {
    "业务": frozenset({Actions.VIEW_BUSINESS.id}),
    "数据集成": frozenset(
        {
            Actions.VIEW_PLUGIN.id,
            Actions.MANAGE_PLUGIN.id,
            Actions.VIEW_COLLECTION.id,
            Actions.MANAGE_COLLECTION.id,
            Actions.VIEW_CUSTOM_METRIC.id,
            Actions.MANAGE_CUSTOM_METRIC.id,
            Actions.VIEW_CUSTOM_EVENT.id,
            Actions.MANAGE_CUSTOM_EVENT.id,
        }
    ),
    "监控场景": frozenset(
        {
            Actions.VIEW_HOST.id,
            Actions.MANAGE_HOST.id,
            Actions.VIEW_SYNTHETIC.id,
            Actions.MANAGE_SYNTHETIC.id,
            Actions.USE_PUBLIC_SYNTHETIC_LOCATION.id,
        }
    ),
    "监控管理": frozenset(
        {
            Actions.VIEW_RULE.id,
            Actions.MANAGE_RULE.id,
            Actions.VIEW_NOTIFY_TEAM.id,
            Actions.MANAGE_NOTIFY_TEAM.id,
            Actions.VIEW_DOWNTIME.id,
            Actions.MANAGE_DOWNTIME.id,
            Actions.EXPORT_CONFIG.id,
            Actions.IMPORT_CONFIG.id,
        }
    ),
    "分析定位": frozenset(
        {
            Actions.EXPLORE_METRIC.id,
            Actions.VIEW_EVENT.id,
            Actions.MANAGE_EVENT.id,
            Actions.VIEW_SINGLE_DASHBOARD.id,
            Actions.EDIT_SINGLE_DASHBOARD.id,
            Actions.MANAGE_DATASOURCE.id,
            Actions.NEW_DASHBOARD.id,
            Actions.MANAGE_REPORT.id,
            Actions.VIEW_DASHBOARD.id,
            Actions.MANAGE_DASHBOARD.id,
            Actions.VIEW_INCIDENT.id,
            Actions.MANAGE_INCIDENT.id,
        }
    ),
    "应用监控": frozenset(
        {
            Actions.VIEW_APM_APPLICATION.id,
            Actions.MANAGE_APM_APPLICATION.id,
        }
    ),
    "用户体验监控": frozenset(
        {
            Actions.VIEW_RUM_APPLICATION.id,
            Actions.MANAGE_RUM_APPLICATION.id,
        }
    ),
    "全局配置": frozenset(
        {
            Actions.MANAGE_PUBLIC_SYNTHETIC_LOCATION.id,
            Actions.MANAGE_PUBLIC_PLUGIN.id,
            Actions.VIEW_GLOBAL_SETTING.id,
            Actions.MANAGE_GLOBAL_SETTING.id,
            Actions.VIEW_SELF_STATE.id,
            Actions.MANAGE_PUBLIC_ACTION_CONFIG.id,
            Actions.MANAGE_CALENDAR.id,
        }
    ),
    "监控平台MCP": frozenset(
        {
            Actions.USING_DASHBOARD_MCP.id,
            Actions.USING_METRICS_MCP.id,
            Actions.USING_LOG_MCP.id,
            Actions.USING_ALARM_MCP.id,
            Actions.USING_ALARM_HANDLING_MCP.id,
            Actions.USING_METADATA_MCP.id,
            Actions.USING_APM_MCP.id,
            Actions.USING_OPERATION_MCP.id,
        }
    ),
}

# 构建期生成反查表（action_id → 分类），一次构建多次使用
_ACTION_ID_TO_CATEGORY: dict[str, str] = {
    aid: category for category, aids in _ACTION_CATEGORY_MAP.items() for aid in aids
}

_ACTION_CATEGORY_ORDER: list[str] = [
    "业务",
    "数据集成",
    "监控场景",
    "监控管理",
    "分析定位",
    "应用监控",
    "用户体验监控",
    "全局配置",
    "监控平台MCP",
]


def _get_action_category(action_id: str) -> str:
    """查询 action 的业务分组；未登记的 action 归入"其他"。"""
    return _ACTION_ID_TO_CATEGORY.get(action_id, "其他")


# ============================================================================
# action_categories 构建
# ============================================================================


def _build_action_info(action: ActionDef) -> dict[str, Any]:
    """Build the standard action info dict."""
    return {
        "id": action.id,
        "name": action.name,
        "type": _get_v3_type(action),
        "resource_type": action.resource_type or None,
        "description": action.description,
    }


def _build_business_groups(schema: SchemaRegistry) -> list[dict[str, Any]]:
    """将 schema 中的操作按业务场景扁平分组。"""
    groups_data: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for action in sorted(schema.all_actions(), key=lambda a: a.id):
        info = _build_action_info(action)
        category = _get_action_category(action.id)
        groups_data[category].append(info)

    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for name in _ACTION_CATEGORY_ORDER:
        if name in groups_data:
            result.append(
                {
                    "name": name,
                    "action_count": len(groups_data[name]),
                    "actions": groups_data[name],
                }
            )
            seen.add(name)

    for name in sorted(groups_data.keys()):
        if name not in seen:
            result.append(
                {
                    "name": name,
                    "action_count": len(groups_data[name]),
                    "actions": groups_data[name],
                }
            )

    return result


def _build_action_groups(schema: SchemaRegistry) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Group actions by resource_type, returning (groups, action_index)."""
    groups_data: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for action in sorted(schema.all_actions(), key=lambda a: a.id):
        key = action.resource_type or "global"
        groups_data[key].append(_build_action_info(action))

    # 排序：顶级资源 → 全局 → 其它非顶级资源
    top_level_keys = sorted(
        k
        for k in groups_data
        if k != "global" and schema.has_resource_type(k) and not schema.get_resource_type(k).ancestor
    )
    other_keys = sorted(k for k in groups_data if k != "global" and k not in top_level_keys)
    key_order = top_level_keys + (["global"] if "global" in groups_data else []) + other_keys

    groups: list[dict[str, Any]] = []
    for key in key_order:
        actions = groups_data[key]
        if key != "global" and schema.has_resource_type(key):
            rt_def = schema.get_resource_type(key)
            groups.append(
                {
                    "resource_type": key,
                    "name": rt_def.name,
                    "is_top_level": not rt_def.ancestor,
                    "parent_resource_type": rt_def.ancestor or None,
                    "action_count": len(actions),
                    "actions": actions,
                }
            )
        else:
            groups.append(
                {
                    "resource_type": key if key != "global" else None,
                    "name": "全局操作",
                    "is_top_level": True,
                    "parent_resource_type": None,
                    "action_count": len(actions),
                    "actions": actions,
                }
            )

    action_index = {
        a.id: {
            "name": a.name,
            "type": _get_v3_type(a),
            "resource_type": a.resource_type or None,
        }
        for a in schema.all_actions()
    }

    return groups, action_index


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
# RPC Functions
# ============================================================================


@KernelRPCRegistry.register(
    FUNC_ACTION_CATEGORIES,
    summary="获取 IAM 操作元数据",
    description=(
        "返回所有 IAM 操作按资源类型分组的元数据，含操作 ID、名称、类型、资源类型，"
        "以及分组信息、业务场景分组和资源类型定义，供前端展示列头、筛选和分组信息。"
        "business_groups 按业务场景分组，未匹配到业务分组的操作自动归入'其他'组。"
    ),
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
    },
    example_params={"bk_tenant_id": "system"},
)
def action_categories(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)

    fw = get_framework()
    schema = fw.schema

    groups, action_index = _build_action_groups(schema)
    business_groups = _build_business_groups(schema)

    # 构建资源类型元数据列表
    resource_types = [
        {
            "id": rt.id,
            "name": str(rt.name),
            "is_top_level": not rt.ancestor,
            "parent_resource_type": rt.ancestor or None,
        }
        for rt in schema.all_resource_types()
    ]

    return build_response(
        operation=OPERATION_ACTION_CATEGORIES,
        func_name=FUNC_ACTION_CATEGORIES,
        bk_tenant_id=bk_tenant_id,
        data={
            "groups": groups,
            "business_groups": business_groups,
            "action_index": action_index,
            "resource_types": resource_types,
        },
        safety_level=SAFETY_LEVEL_READ,
    )


@KernelRPCRegistry.register(
    FUNC_QUERY_USER_PERMISSIONS,
    summary="查询指定用户的全部 IAM 权限",
    description=(
        "查询指定用户的所有 IAM 操作权限（操作→空间映射）。"
        "通过框架 query_policies_by_actions 批量获取策略表达式，本地递归解析。"
    ),
    params_schema={
        "username": "必填，要查询的用户名",
        "bk_tenant_id": "必填，租户 ID",
    },
    example_params={"username": "admin", "bk_tenant_id": "system"},
)
def _query_policies_with_fallback(
    fw,
    subject: FwSubject,
    action_ids: list[str],
    warnings: list[dict],
) -> dict[str, list]:
    """批量优先 + 逐条降级查询策略表达式。

    批量查询（query_policies_by_actions）失败时降级为逐个 action 查询：
      * 单条查询失败 → policies[aid] = [None]（上层标记 error），并在 warnings 中记录
        失败的 action_id 与错误详情
      * 单条查询成功 → policies[aid] = 表达式列表（可能为空，表示无权限策略）
    """
    try:
        return fw.query_policies_by_actions(subject, action_ids)
    except Exception as e:
        logger.warning("Batch IAM policy query failed, falling back to individual queries: %s", e)
        warnings.append(
            {
                "code": "IAM_BATCH_FAILED",
                "message": "批量 IAM 策略查询失败，已降级为逐操作查询",
                "details": {"error": str(e)},
            }
        )

    policies: dict[str, list] = {}
    for aid in action_ids:
        try:
            policies[aid] = fw.query_policies(subject, aid)
        except Exception as e:
            logger.warning("IAM query failed for action %s: %s", aid, e)
            policies[aid] = [None]
            warnings.append(
                {
                    "code": "IAM_QUERY_FAILED",
                    "message": f"操作 {aid} 的 IAM 策略查询失败，已跳过",
                    "details": {"action_id": aid, "error": str(e)},
                }
            )
    return policies


def query_user_permissions(params: dict[str, Any]) -> dict[str, Any]:
    username = _normalize_username(params.get("username"))
    bk_tenant_id = require_bk_tenant_id(params)

    fw = get_framework()
    schema = fw.schema
    subject = FwSubject(id=username, type=SubjectType.USER, tenant_id=bk_tenant_id)

    all_actions_list = schema.all_actions()
    action_ids = [a.id for a in all_actions_list]

    # TODO 删除
    # action_ids.remove("view_incident")
    # action_ids.remove("manage_incident")

    # 通过框架查询策略表达式：批量优先，失败时降级为逐个 action 查询
    warnings: list[dict] = []
    policies = _query_policies_with_fallback(fw, subject, action_ids, warnings)

    # 一次遍历同时构造 actions_result 与累计 summary
    actions_result: list[dict[str, Any]] = []
    granted_actions = 0
    resolve_failed = 0

    for action in all_actions_list:
        # fw.query_policies_by_actions 返回 dict[action_id → list[PolicyExpression]]
        # V3Provider 的表达式在 list[0]
        expr_list = policies.get(action.id, [None])
        expr = expr_list[0] if expr_list else None

        grant_type, permissions, note = _parse_action_permissions(action, expr)

        if grant_type != "error":
            try:
                _resolve_parent_paths(permissions, schema)
                _resolve_display_names(permissions)
            except Exception as e:
                # DB 不可用等场景：权限数据本身可用，仅缺失父路径/展示名，降级跳过
                logger.warning("Resolve parent/display names failed for action %s: %s", action.id, e)
                resolve_failed += 1

        item = _build_action_result_item(action, grant_type, permissions, note)
        if USE_DIALECT_ACTION_ID:
            # 对外返回 V3 方言 ID（IAM 平台注册的 ID）；切换开关见 USE_DIALECT_ACTION_ID
            item["action_id"] = _to_dialect_action_id(fw, action.id)
        actions_result.append(item)

        if grant_type in ("partial", "all"):
            granted_actions += 1

    if resolve_failed:
        warnings.append(
            {
                "code": "IAM_RESOLVE_FAILED",
                "message": f"{resolve_failed} 个 action 的父路径/展示名解析失败（权限数据不受影响）",
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
