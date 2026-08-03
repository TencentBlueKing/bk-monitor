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
# 角色定义（v4 RBAC；v3 Provider 忽略）
#
# 3 角色：业务查看 / 业务运维 / 业务管理
# 子资源 action 的 RoleActionBinding.resource_type 使用子资源自身类型。
# ---------------------------------------------------------------------------

from ..iam_engine.schema.definitions import RoleActionBinding, RoleDef

# ---- View actions on space ----
_view_space = [
    "view_business",
    "explore_metric",
    "view_synthetic",
    "view_host",
    "view_event",
    "view_plugin",
    "view_collection",
    "view_notify_team",
    "view_rule",
    "view_downtime",
    "view_custom_metric",
    "view_custom_event",
    "view_dashboard",
    "view_incident",
    "export_config",
    "using_dashboard_mcp",
    "using_metrics_mcp",
    "using_log_mcp",
    "using_metadata_mcp",
    "using_alarm_mcp",
    "using_apm_mcp",
    "using_operation_mcp",
]

# ---- Manage actions on space ----
_manage_space = [
    "manage_synthetic",
    "manage_host",
    "manage_event",
    "manage_plugin",
    "manage_collection",
    "manage_notify_team",
    "manage_rule",
    "manage_downtime",
    "manage_custom_metric",
    "manage_custom_event",
    "manage_dashboard",
    "manage_datasource",
    "new_dashboard",
    "import_config",
    "manage_incident",
    "manage_report",
    "using_alarm_handling_mcp",
]

# ---- Sub-resource actions (by resource type) ----
_view_sub = {
    "apm_application": ["view_apm_application"],
    "grafana_dashboard": ["view_single_dashboard"],
    "rum_application": ["view_rum_application"],
}
_manage_sub = {
    "apm_application": ["manage_apm_application"],
    "grafana_dashboard": ["edit_single_dashboard"],
    "rum_application": ["manage_rum_application"],
}

# ---- Resource-free actions ----
_resource_free = [
    "view_global_setting",
    "manage_global_setting",
    "view_self_state",
    "manage_public_plugin",
    "manage_public_action_config",
    "manage_public_synthetic_location",
    "use_public_synthetic_location",
    "manage_calendar",
]


class Roles:
    SPACE_VIEWER = RoleDef(
        id="space_viewer",
        name="业务查看",
        actions=tuple(
            [RoleActionBinding(aid, "space") for aid in _view_space]
            + [RoleActionBinding(aid, rt) for rt, aids in _view_sub.items() for aid in aids]
        ),
    )

    SPACE_OPERATOR = RoleDef(
        id="space_operator",
        name="业务运维",
        actions=tuple(
            [RoleActionBinding(aid, "space") for aid in _view_space]
            + [RoleActionBinding(aid, rt) for rt, aids in _view_sub.items() for aid in aids]
            + [RoleActionBinding(aid, "space") for aid in _manage_space]
            + [RoleActionBinding(aid, rt) for rt, aids in _manage_sub.items() for aid in aids]
        ),
    )

    SPACE_ADMIN = RoleDef(
        id="space_admin",
        name="业务管理",
        actions=tuple(
            [RoleActionBinding(aid, "space") for aid in _view_space]
            + [RoleActionBinding(aid, rt) for rt, aids in _view_sub.items() for aid in aids]
            + [RoleActionBinding(aid, "space") for aid in _manage_space]
            + [RoleActionBinding(aid, rt) for rt, aids in _manage_sub.items() for aid in aids]
            + [RoleActionBinding(aid, "") for aid in _resource_free]
        ),
    )
