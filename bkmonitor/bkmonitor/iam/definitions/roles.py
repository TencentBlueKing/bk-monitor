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

from ..iam_engine.schema.definitions import ActionDef, ResourceTypeDef, RoleActionBinding, RoleDef
from .actions import Actions
from .resource_types import ResourceTypes


def _bind(action: ActionDef, resource_type: ResourceTypeDef | None = None) -> RoleActionBinding:
    """把 ActionDef + ResourceTypeDef 归一为 RoleActionBinding。

    Args:
        action: 操作定义对象
        resource_type: 授权维度；None 表示无关资源类型的授权
    """
    rt_id = resource_type.id if resource_type is not None else ""
    return RoleActionBinding(action_id=action.id, resource_type=rt_id)


# ---- View actions on space ----
_view_space = [
    Actions.VIEW_BUSINESS,
    Actions.EXPLORE_METRIC,
    Actions.VIEW_SYNTHETIC,
    Actions.VIEW_HOST,
    Actions.VIEW_EVENT,
    Actions.VIEW_PLUGIN,
    Actions.VIEW_COLLECTION,
    Actions.VIEW_NOTIFY_TEAM,
    Actions.VIEW_RULE,
    Actions.VIEW_DOWNTIME,
    Actions.VIEW_CUSTOM_METRIC,
    Actions.VIEW_CUSTOM_EVENT,
    Actions.VIEW_INCIDENT,
    Actions.EXPORT_CONFIG,
    Actions.USING_DASHBOARD_MCP,
    Actions.USING_METRICS_MCP,
    Actions.USING_LOG_MCP,
    Actions.USING_METADATA_MCP,
    Actions.USING_ALARM_MCP,
    Actions.USING_APM_MCP,
    Actions.USING_OPERATION_MCP,
]

# ---- Manage actions on space ----
_manage_space = [
    Actions.MANAGE_SYNTHETIC,
    Actions.MANAGE_HOST,
    Actions.MANAGE_EVENT,
    Actions.MANAGE_PLUGIN,
    Actions.MANAGE_COLLECTION,
    Actions.MANAGE_NOTIFY_TEAM,
    Actions.MANAGE_RULE,
    Actions.MANAGE_DOWNTIME,
    Actions.MANAGE_CUSTOM_METRIC,
    Actions.MANAGE_CUSTOM_EVENT,
    Actions.MANAGE_DATASOURCE,
    Actions.NEW_DASHBOARD,
    Actions.IMPORT_CONFIG,
    Actions.MANAGE_INCIDENT,
    Actions.MANAGE_REPORT,
    Actions.USING_ALARM_HANDLING_MCP,
]

# ---- Sub-resource actions (by resource type) ----
_view_sub = {
    ResourceTypes.APM_APPLICATION: [Actions.VIEW_APM_APPLICATION],
    ResourceTypes.GRAFANA_DASHBOARD: [Actions.VIEW_SINGLE_DASHBOARD],
    ResourceTypes.RUM_APPLICATION: [Actions.VIEW_RUM_APPLICATION],
}
_manage_sub = {
    ResourceTypes.APM_APPLICATION: [Actions.MANAGE_APM_APPLICATION],
    ResourceTypes.GRAFANA_DASHBOARD: [Actions.EDIT_SINGLE_DASHBOARD],
    ResourceTypes.RUM_APPLICATION: [Actions.MANAGE_RUM_APPLICATION],
}

# ---- Resource-free actions ----
_resource_free = [
    Actions.VIEW_GLOBAL_SETTING,
    Actions.MANAGE_GLOBAL_SETTING,
    Actions.VIEW_SELF_STATE,
    Actions.MANAGE_PUBLIC_PLUGIN,
    Actions.MANAGE_PUBLIC_ACTION_CONFIG,
    Actions.MANAGE_PUBLIC_SYNTHETIC_LOCATION,
    Actions.USE_PUBLIC_SYNTHETIC_LOCATION,
    Actions.MANAGE_CALENDAR,
]


class Roles:
    SPACE_VIEWER = RoleDef(
        id="space_viewer",
        name="业务查看",
        actions=tuple(
            [_bind(a, ResourceTypes.SPACE) for a in _view_space]
            + [_bind(a, rt) for rt, aids in _view_sub.items() for a in aids]
        ),
    )

    SPACE_OPERATOR = RoleDef(
        id="space_operator",
        name="业务运维",
        actions=tuple(
            [_bind(a, ResourceTypes.SPACE) for a in _view_space]
            + [_bind(a, rt) for rt, aids in _view_sub.items() for a in aids]
            + [_bind(a, ResourceTypes.SPACE) for a in _manage_space]
            + [_bind(a, rt) for rt, aids in _manage_sub.items() for a in aids]
        ),
    )

    SPACE_ADMIN = RoleDef(
        id="space_admin",
        name="业务管理",
        actions=tuple(
            [_bind(a, ResourceTypes.SPACE) for a in _view_space]
            + [_bind(a, rt) for rt, aids in _view_sub.items() for a in aids]
            + [_bind(a, ResourceTypes.SPACE) for a in _manage_space]
            + [_bind(a, rt) for rt, aids in _manage_sub.items() for a in aids]
            + [_bind(a) for a in _resource_free]
        ),
    )
