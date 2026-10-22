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
#
# 后端口径（backend 参数）不在此处硬编码任何版本分支：
#   - 操作集合：V3 保留历史 Dashboard 操作，V4 使用产品确认的实例级模型；
#   - id 口径：actions[].id 经 provider.codec.encode_action 编码（v3 输出方言 ID、
#     v4 输出业务 ID 都是各自 codec 的职责，本模块不关心）。
# ---------------------------------------------------------------------------

import logging
from collections import defaultdict
from typing import Any

from bkmonitor.iam.definitions import actions as product_actions
from bkmonitor.iam.backends.v3.codec import MonitorV3Codec
from iam_engine.exceptions import ProviderNotFound
from iam_engine.core.config import AuthMode, DEFAULT_DUAL_STACK
from iam_engine.core.exceptions import InvalidAuthModeError
from bkmonitor.iam.permission import Permission
from iam_engine.schema.definitions import ActionDef
from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.common import (
    SAFETY_LEVEL_READ,
    build_response,
    get_bk_tenant_id,
)

logger = logging.getLogger("kernel_api")

FUNC_ACTION_CATEGORIES = "admin.permission.action_categories"
OPERATION_ACTION_CATEGORIES = "permission.action_categories"


def _get_enabled_provider(fw, protocol):
    """Read one current mode snapshot before any protocol-specific IAM query."""
    try:
        mode = AuthMode(fw.mode_provider.get_mode())
    except (ValueError, InvalidAuthModeError) as error:
        raise CustomException(message="Invalid IAM mode; permission query is unavailable") from error
    if AuthMode(protocol) not in DEFAULT_DUAL_STACK.modes_for(mode):
        raise CustomException(message=f"IAM {protocol} is disabled in mode {mode.value}")
    return fw.get_provider(protocol)


# ============================================================================
# 操作业务分组定义：分类名 → action 枚举集合（Business ID）
#
# 使用 Actions 枚举（而非硬编码字符串），typo / 改名在 import 时即暴露。
# 新增 action 未在此登记时，自动归入"其他"组（见 _get_action_category）。
# ============================================================================

_ACTION_CATEGORY_MAP: dict[str, frozenset[str]] = {
    "业务": frozenset({product_actions["view_business"].id}),
    "数据集成": frozenset(
        {
            product_actions["view_plugin"].id,
            product_actions["manage_plugin"].id,
            product_actions["view_collection"].id,
            product_actions["manage_collection"].id,
            product_actions["view_custom_metric"].id,
            product_actions["manage_custom_metric"].id,
            product_actions["view_custom_event"].id,
            product_actions["manage_custom_event"].id,
        }
    ),
    "监控场景": frozenset(
        {
            product_actions["view_host"].id,
            product_actions["manage_host"].id,
            product_actions["view_synthetic"].id,
            product_actions["manage_synthetic"].id,
            product_actions["use_public_synthetic_location"].id,
        }
    ),
    "监控管理": frozenset(
        {
            product_actions["view_rule"].id,
            product_actions["manage_rule"].id,
            product_actions["view_notify_team"].id,
            product_actions["manage_notify_team"].id,
            product_actions["view_downtime"].id,
            product_actions["manage_downtime"].id,
            product_actions["export_config"].id,
            product_actions["import_config"].id,
        }
    ),
    "分析定位": frozenset(
        {
            product_actions["explore_metric"].id,
            product_actions["view_event"].id,
            product_actions["manage_event"].id,
            product_actions["view_single_dashboard"].id,
            product_actions["edit_single_dashboard"].id,
            product_actions["manage_datasource"].id,
            product_actions["new_dashboard"].id,
            product_actions["manage_report"].id,
            product_actions["view_dashboard"].id,
            product_actions["manage_dashboard"].id,
            product_actions["view_incident"].id,
            product_actions["manage_incident"].id,
        }
    ),
    "应用监控": frozenset(
        {
            product_actions["view_apm_application"].id,
            product_actions["manage_apm_application"].id,
        }
    ),
    "用户体验监控": frozenset(
        {
            product_actions["view_rum_application"].id,
            product_actions["manage_rum_application"].id,
        }
    ),
    "全局配置": frozenset(
        {
            product_actions["manage_public_synthetic_location"].id,
            product_actions["manage_public_plugin"].id,
            product_actions["view_global_setting"].id,
            product_actions["manage_global_setting"].id,
            product_actions["view_self_state"].id,
            product_actions["manage_public_action_config"].id,
            product_actions["manage_calendar"].id,
        }
    ),
    "监控平台MCP": frozenset(
        {
            product_actions["using_dashboard_mcp"].id,
            product_actions["using_metrics_mcp"].id,
            product_actions["using_log_mcp"].id,
            product_actions["using_alarm_mcp"].id,
            product_actions["using_alarm_handling_mcp"].id,
            product_actions["using_metadata_mcp"].id,
            product_actions["using_apm_mcp"].id,
            product_actions["using_operation_mcp"].id,
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


def _build_action_info(
    action: ActionDef,
    include_v3_type: bool = True,
    codec=None,
) -> dict[str, Any]:
    """Build the standard action info dict（v3 type 字段按需包含）。

    指定 codec 时 actions[].id 按该 provider 的方言编码（v3 → 方言 ID，
    v4 → 业务 ID），保证与对应后端的权限查询接口 action_id 口径一致。
    """
    info = {
        "id": codec.encode_action(action.id) if codec is not None else action.id,
        "name": action.name,
        "resource_type": action.resource_type or None,
        "description": action.description,
    }
    if include_v3_type:
        info["type"] = _get_v3_type(action)
    return info


def _visible_actions(schema, provider=None) -> list[ActionDef]:
    """返回当前协议的产品操作集合，保留 V3 历史 Dashboard 操作。"""
    return list((schema.v4_actions if provider is not None and provider.name == "v4" else schema.actions).values())


def _build_business_groups(schema, provider=None) -> list[dict[str, Any]]:
    """将 schema 中的操作按业务场景扁平分组（可选按 provider 可见性 + id 口径）。"""
    codec = provider.codec if provider is not None else MonitorV3Codec()
    groups_data: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for action in sorted(_visible_actions(schema, provider), key=lambda a: a.id):
        info = _build_action_info(action, codec=codec)
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


def _build_action_groups(
    schema, provider=None
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Group actions by resource_type, returning (groups, action_index).

    指定 provider 时按 provider 可见性过滤 action 并按 codec 编码 id（action_index 同源）。
    """
    codec = provider.codec if provider is not None else MonitorV3Codec()
    groups_data: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for action in sorted(_visible_actions(schema, provider), key=lambda a: a.id):
        key = action.resource_type or "global"
        groups_data[key].append(_build_action_info(action, codec=codec))

    # 排序：顶级资源 → 全局 → 其它非顶级资源
    top_level_keys = sorted(
        k
        for k in groups_data
        if k != "global" and (k in schema.resource_types) and not schema.resource_types[k].ancestor
    )
    other_keys = sorted(k for k in groups_data if k != "global" and k not in top_level_keys)
    key_order = top_level_keys + (["global"] if "global" in groups_data else []) + other_keys

    groups: list[dict[str, Any]] = []
    for key in key_order:
        actions = groups_data[key]
        if key != "global" and (key in schema.resource_types):
            rt_def = schema.resource_types[key]
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
        (codec.encode_action(a.id) if codec is not None else a.id): {
            "name": a.name,
            "type": _get_v3_type(a),
            "resource_type": a.resource_type or None,
        }
        for a in _visible_actions(schema, provider)
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
        "backend": (
            "可选，后端 provider 名（如 v3 / v4）：按该 provider 可见性过滤，"
            "action id 按其 codec 编码；缺省保留 V3 ID"
        ),
    },
    example_params={"bk_tenant_id": "system"},
)
def action_categories(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)

    fw = Permission(username="iam_metadata", bk_tenant_id=bk_tenant_id)
    schema = fw.schema

    # backend → 对应 provider：可见性过滤与 id 口径全部由 provider 提供
    # （codec 编码方言 ID），本模块不硬编码任何版本分支。
    backend = params.get("backend") or ""
    provider = None
    if backend:
        try:
            provider = fw.get_provider(backend)
        except ProviderNotFound:
            raise CustomException(
                message=f"backend 指定的 provider '{backend}' 未装配，无法生成该后端口径的元数据"
            ) from None

    groups, action_index = _build_action_groups(schema, provider)
    business_groups = _build_business_groups(schema, provider)

    # 构建资源类型元数据列表（可选按 provider 可见性过滤）
    resource_types = [
        {
            "id": rt.id,
            "name": str(rt.name),
            "is_top_level": not rt.ancestor,
            "parent_resource_type": rt.ancestor or None,
        }
        for rt in schema.resource_types.values()
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
