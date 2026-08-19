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
# 权限 RPC —— 共享构建逻辑（provider 无关）
#
# 分类表、action 元数据构建与 action_categories RPC，均由 schema（SSOT）驱动，
# v3 / v4 查询接口共用。action 元数据中的 "type" 字段为 v3 平台语义（view / manage），
# 通过 _build_action_info(include_v3_type=...) 参数化，v3 接口与 action_categories
# 兼容历史契约传 True，v4 接口不消费该字段。
# ---------------------------------------------------------------------------

import logging
from collections import defaultdict
from typing import Any

from bkmonitor.iam.definitions.actions import Actions
from bkmonitor.iam.iam_engine.django.facade import get_framework
from bkmonitor.iam.iam_engine.schema.definitions import ActionDef
from bkmonitor.iam.iam_engine.schema.registry import SchemaRegistry
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.common import (
    SAFETY_LEVEL_READ,
    build_response,
    get_bk_tenant_id,
)

logger = logging.getLogger("kernel_api")

FUNC_ACTION_CATEGORIES = "admin.permission.action_categories"
OPERATION_ACTION_CATEGORIES = "permission.action_categories"


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


def _get_v3_type(action: ActionDef) -> str:
    """从 ActionDef.extensions 获取 v3 type（view / manage）。"""
    return action.extensions.get("v3", {}).get("type", "")


# ============================================================================
# action_categories 构建
# ============================================================================


def _build_action_info(action: ActionDef, include_v3_type: bool = True) -> dict[str, Any]:
    """Build the standard action info dict（v3 type 字段按需包含）。"""
    info = {
        "id": action.id,
        "name": action.name,
        "resource_type": action.resource_type or None,
        "description": action.description,
    }
    if include_v3_type:
        info["type"] = _get_v3_type(action)
    return info


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


# ============================================================================
# RPC Functions
# ============================================================================


@KernelRPCRegistry.register(
    FUNC_ACTION_CATEGORIES,
    summary="获取 IAM 操作元数据",
    description=(
        "返回所有 IAM 操作按资源类型分组的元数据，含操作 ID、名称、类型、资源类型，"
        "以及分组信息、业务场景分组和资源类型定义，"
        "供前端展示列头、筛选和分组信息。"
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
