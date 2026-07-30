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

from django.conf import settings
from iam import MultiActionRequest, Request, Subject
from iam.exceptions import AuthAPIError

from bkmonitor.iam.action import ActionMeta, _all_actions, get_action_by_id
from bkmonitor.iam.permission import Permission
from bkmonitor.iam.resource import _all_resources
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


def _normalize_username(value: Any) -> str:
    """Validate and normalize a username parameter."""
    username = str(value or "").strip()
    if not username:
        raise CustomException(message="username 为必填项")
    return username


def _get_resource_type(action: ActionMeta) -> str | None:
    rts = action.related_resource_types
    return rts[0]["id"] if rts else None


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


def _parse_permission_entries(condition: dict | None, resource_type: str | None) -> tuple[bool, list[dict]]:
    """Parse IAM policy expression tree into (is_all, entries).

    Each entry: {"path": [{"type": "space", "id": "2"}, ...]}
    Fully generic — works for any resource type and any nesting depth.
    """
    if not condition:
        return False, []

    op = condition.get("op", "").lower()

    if op == "any":
        return True, []

    if op == "in":
        field = condition.get("field", "")
        values = condition.get("value", [])
        if not values:
            return False, []
        typ = _field_to_resource_type(field)
        return False, [{"path": [{"type": typ, "id": str(v)}]} for v in values]

    if op == "eq":
        field = condition.get("field", "")
        value = condition.get("value", "")
        if not value:
            return False, []
        typ = _field_to_resource_type(field)
        return False, [{"path": [{"type": typ, "id": str(value)}]}]

    if op == "starts_with":
        value = condition.get("value", "")
        if not value:
            return False, []
        path = _parse_iam_path(value)
        return (False, [{"path": path}]) if path else (False, [])

    if op == "or":
        entries: list[dict] = []
        for sub in condition.get("content", []):
            sub_all, sub_entries = _parse_permission_entries(sub, resource_type)
            if sub_all:
                return True, []
            entries.extend(sub_entries)
        return False, entries

    if op == "and":
        all_entries: list[list[dict]] = []
        for sub in condition.get("content", []):
            sub_all, sub_entries = _parse_permission_entries(sub, resource_type)
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


def _resolve_parent_paths(permissions: list[dict]) -> None:
    """
    沿资源拓扑向上递归补齐 path 首节点的父资源，直到顶级（parent_resource is None）。
    """
    while True:
        # 按“当前需要向上补齐父节点”的类型分组
        groups_by_type: dict[str, list[tuple[dict, str]]] = defaultdict(list)
        for entry in permissions:
            path = entry["path"]
            if not path:
                continue
            head_type = path[0]["type"]
            cls = _all_resources.get(head_type)
            if cls is None or cls.parent_resource is None:
                # 未知资源类型或已到顶级，无需再向上
                continue
            groups_by_type[head_type].append((entry, path[0]["id"]))

        if not groups_by_type:
            break

        made_progress = False
        for rt, items in groups_by_type.items():
            cls = _all_resources[rt]
            parent_cls = cls.parent_resource  # 父类型从拓扑元数据获取，不硬编码
            instance_ids = {iid for _, iid in items}
            parent_map = cls.batch_get_parent(instance_ids)
            if not parent_map:
                continue
            for entry, iid in items:
                parent_id = parent_map.get(iid)
                if parent_id:
                    entry["path"].insert(0, {"type": parent_cls.id, "id": parent_id})
                    made_progress = True

        # 如果本轮未能为任何 entry 补齐父节点，适时退出避免死循环
        if not made_progress:
            break


def _resolve_display_names(permissions: list[dict]) -> None:
    """Fill display_name for all path nodes in-place, via polymorphic batch query."""
    ids_by_type: dict[str, set[str]] = defaultdict(set)
    for entry in permissions:
        for node in entry["path"]:
            ids_by_type[node["type"]].add(node["id"])

    display_names: dict[str, dict[str, str]] = {}
    for rt, ids in ids_by_type.items():
        cls = _all_resources.get(rt)
        if cls:
            display_names[rt] = cls.batch_get_display_names(ids)
        else:
            display_names[rt] = {}

    for entry in permissions:
        for node in entry["path"]:
            node["display_name"] = display_names.get(node["type"], {}).get(node["id"], "")


def _parse_action_permissions(action: ActionMeta, condition: dict | None) -> tuple[str, list[dict], str | None]:
    """Return (grant_type, permissions, note).

    permissions: list of {"path": [{type, id, [display_name]}, ...]}
    """
    if condition is None:
        return "error", [], "IAM 查询失败"

    resource_type = _get_resource_type(action)
    is_all, entries = _parse_permission_entries(condition, resource_type)

    if is_all:
        return "all", [{"path": []}], None
    if not entries:
        return "none", [], None
    return "partial", entries, None


def _batch_query_policies(iam_client, actions: list[ActionMeta], username) -> dict[str, dict | None]:
    """Primary path: batch query all actions at once."""
    if not actions:
        return {}

    action_objs = [get_action_by_id(a.id) for a in actions]
    multi_request = MultiActionRequest(
        system=settings.BK_IAM_SYSTEM_ID,
        subject=Subject("user", username),
        actions=action_objs,
        resources=[],
        environment=None,
    )

    raw_list = iam_client._do_policy_query_by_actions(multi_request, with_resources=False)
    return {item["action"]["id"]: item.get("condition") for item in raw_list}


def _fallback_query_policies(iam_client, actions: list[ActionMeta], username, warnings) -> dict[str, dict | None]:
    """Fallback: query each action individually, skipping AuthAPIError per action."""
    result: dict[str, dict | None] = {}
    for action in actions:
        try:
            request = Request(
                system=settings.BK_IAM_SYSTEM_ID,
                subject=Subject("user", username),
                action=action,
                resources=[],
                environment=None,
            )
            policy = iam_client._do_policy_query(request)
            result[action.id] = policy
        except Exception as e:
            logger.warning("IAM query failed for action %s: %s", action.id, e)
            result[action.id] = None
            warnings.append(
                {
                    "code": "IAM_QUERY_FAILED",
                    "message": f"操作 {action.id} 的 IAM 策略查询失败，已跳过",
                    "details": {"action_id": action.id, "error": str(e)},
                }
            )
    return result


def _query_policies(iam_client, actions: list[ActionMeta], username) -> tuple[dict[str, dict | None], list[dict]]:
    """Query IAM policies for all actions, with batch-first + fallback."""
    warnings: list[dict] = []
    try:
        result = _batch_query_policies(iam_client, actions, username)
    except AuthAPIError as e:
        logger.warning("Batch IAM policy query failed, falling back to individual queries: %s", e)
        warnings.append(
            {
                "code": "IAM_BATCH_FAILED",
                "message": "批量 IAM 策略查询失败，已降级为逐操作查询",
                "details": {"error": str(e)},
            }
        )
        result = _fallback_query_policies(iam_client, actions, username, warnings)
    return result, warnings


# ---------------------------------------------------------------------------
# 操作业务分组定义（扁平结构，无子组）
# 仅作参照，_all_actions 中未匹配的操作自动归入"其他"组
# ---------------------------------------------------------------------------
_ACTION_CATEGORY_MAP: dict[str, str] = {
    # 业务
    "view_business_v2": "业务",
    # 数据集成
    "view_plugin_v2": "数据集成",
    "manage_plugin_v2": "数据集成",
    "view_collection_v2": "数据集成",
    "manage_collection_v2": "数据集成",
    "view_custom_metric_v2": "数据集成",
    "manage_custom_metric_v2": "数据集成",
    "view_custom_event_v2": "数据集成",
    "manage_custom_event_v2": "数据集成",
    # 监控场景
    "view_host_v2": "监控场景",
    "manage_host_v2": "监控场景",
    "view_synthetic_v2": "监控场景",
    "manage_synthetic_v2": "监控场景",
    "use_public_synthetic_location": "监控场景",
    # 监控管理
    "view_rule_v2": "监控管理",
    "manage_rule_v2": "监控管理",
    "view_notify_team_v2": "监控管理",
    "manage_notify_team_v2": "监控管理",
    "view_downtime_v2": "监控管理",
    "manage_downtime_v2": "监控管理",
    "export_config_v2": "监控管理",
    "import_config_v2": "监控管理",
    # 分析定位
    "explore_metric_v2": "分析定位",
    "view_event_v2": "分析定位",
    "manage_event_v2": "分析定位",
    "view_single_dashboard": "分析定位",
    "edit_single_dashboard": "分析定位",
    "manage_datasource_v2": "分析定位",
    "new_dashboard": "分析定位",
    "manage_report": "分析定位",
    "view_dashboard_v2": "分析定位",
    "manage_dashboard_v2": "分析定位",
    "view_incident": "分析定位",
    "manage_incident": "分析定位",
    # 应用监控
    "view_apm_application_v2": "应用监控",
    "manage_apm_application_v2": "应用监控",
    # 用户体验监控
    "view_rum_application_v2": "用户体验监控",
    "manage_rum_application_v2": "用户体验监控",
    # 全局配置
    "manage_public_synthetic_location": "全局配置",
    "manage_public_plugin": "全局配置",
    "view_global_setting": "全局配置",
    "manage_global_setting": "全局配置",
    "view_self_state": "全局配置",
    "manage_public_action_config": "全局配置",
    "manage_calendar": "全局配置",
    # 监控平台MCP
    "using_dashboard_mcp": "监控平台MCP",
    "using_metrics_mcp": "监控平台MCP",
    "using_log_mcp": "监控平台MCP",
    "using_alarm_mcp": "监控平台MCP",
    "using_alarm_handling_mcp": "监控平台MCP",
    "using_metadata_mcp": "监控平台MCP",
    "using_apm_mcp": "监控平台MCP",
    "using_operation_mcp": "监控平台MCP",
}

# 分组显示顺序
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


def _build_business_groups() -> list[dict[str, Any]]:
    """将 _all_actions 中的操作按业务场景扁平分组。

    - 匹配到 _ACTION_CATEGORY_MAP 的操作归入对应分组
    - 未匹配到的操作归入"其他"兜底组
    - _ACTION_CATEGORY_MAP 中存在但 _all_actions 中不存在的操作 ID 不会出现在结果中
    """
    groups_data: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for action in sorted(_all_actions.values(), key=lambda a: a.id):
        resource_type = _get_resource_type(action)
        info = {
            "id": action.id,
            "name": action.name,
            "type": action.type,
            "resource_type": resource_type,
            "description": action.description,
        }
        category = _ACTION_CATEGORY_MAP.get(action.id, "其他")
        groups_data[category].append(info)

    # 按 _ACTION_CATEGORY_ORDER 定义的顺序输出，未在排序列表中的追加到末尾
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


def _build_action_groups() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Group actions by resource_type, returning (groups, action_index)."""
    groups_data: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for action in sorted(_all_actions.values(), key=lambda a: a.id):
        resource_type = _get_resource_type(action)
        info = {
            "id": action.id,
            "name": action.name,
            "type": action.type,
            "resource_type": resource_type,
            "description": action.description,
        }
        key = resource_type or "global"
        groups_data[key].append(info)

    # 排序：顶级资源 → 全局 → 其它非顶级资源。
    top_level_keys = sorted(
        k
        for k in groups_data
        if k != "global" and (cls := _all_resources.get(k)) is not None and cls.parent_resource is None
    )
    other_keys = sorted(k for k in groups_data if k != "global" and k not in top_level_keys)
    key_order = top_level_keys + (["global"] if "global" in groups_data else []) + other_keys

    groups: list[dict[str, Any]] = []
    for key in key_order:
        actions = groups_data[key]
        resource_cls = _all_resources.get(key) if key != "global" else None
        groups.append(
            {
                "resource_type": key if key != "global" else None,
                "name": str(resource_cls.name) if resource_cls else "全局操作",
                "is_top_level": resource_cls.parent_resource is None if resource_cls else True,
                "parent_resource_type": resource_cls.parent_resource.id
                if resource_cls and resource_cls.parent_resource
                else None,
                "action_count": len(actions),
                "actions": actions,
            }
        )

    action_index = {
        action.id: {
            "name": action.name,
            "type": action.type,
            "resource_type": _get_resource_type(action),
        }
        for action in _all_actions.values()
    }

    return groups, action_index


def _build_action_result_item(
    action: ActionMeta,
    grant_type: str,
    permissions: list[dict],
    note: str | None = None,
) -> dict[str, Any]:
    item = {
        "action_id": action.id,
        "action_name": action.name,
        "type": action.type,
        "resource_type": _get_resource_type(action),
        "grant_type": grant_type,
        "permissions": permissions,
    }
    if note:
        item["note"] = note
    return item


# ---------------------------------------------------------------------------
# RPC Functions
# ---------------------------------------------------------------------------


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

    groups, action_index = _build_action_groups()
    business_groups = _build_business_groups()

    # 构建资源类型元数据列表
    resource_types = [
        {
            "id": cls.id,
            "name": str(cls.name),
            "is_top_level": cls.parent_resource is None,
            "parent_resource_type": cls.parent_resource.id if cls.parent_resource else None,
        }
        for cls in _all_resources.values()
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
        "通过 _do_policy_query_by_actions 一次批量获取策略表达式，本地递归解析提取 space.id 值列表；"
        "若批量查询因 IAM 服务端异常失败，自动降级为逐操作查询。"
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

    # Init Permission (force skip_check=False to query real IAM)
    p = Permission(username, bk_tenant_id)
    p.skip_check = False
    iam_client = p.iam_client

    all_actions_list: list[ActionMeta] = list(_all_actions.values())

    # Query IAM policies (batch primary, fallback on error)
    policies, warnings = _query_policies(iam_client, all_actions_list, username)

    # 一次遍历同时构造 actions_result 与累计 summary 所需计数
    actions_result: list[dict[str, Any]] = []
    granted_actions = 0  # 有任何授权（partial/all）的操作数

    for action in all_actions_list:
        condition = policies.get(action.id)
        grant_type, permissions, note = _parse_action_permissions(action, condition)

        if grant_type != "error":
            _resolve_parent_paths(permissions)
            _resolve_display_names(permissions)

        item = _build_action_result_item(action, grant_type, permissions, note)
        actions_result.append(item)

        if grant_type in ("partial", "all"):
            granted_actions += 1

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
