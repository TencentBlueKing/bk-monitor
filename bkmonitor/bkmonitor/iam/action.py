# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Dict, List, Union

from django.conf import settings
from django.utils.translation import gettext as _
from iam import Action

from core.errors.iam import ActionNotExistError


class ActionMeta(Action):
    """
    动作定义
    """

    def __init__(
        self,
        id: str,
        name: str,
        name_en: str,
        type: str,
        version: int,
        related_resource_types: list = None,
        related_actions: list = None,
        description: str = "",
        description_en: str = "",
    ):
        super(ActionMeta, self).__init__(id)
        self.name = name
        self.name_en = name_en
        self.type = type
        self.version = version
        self.related_resource_types = related_resource_types or []
        self.related_actions = related_actions or []
        self.description = description
        self.description_en = description_en

    def to_json(self):
        return {
            "id": self.id,
            "name": self.name,
            "name_en": self.name_en,
            "type": self.type,
            "version": self.version,
            "related_resource_types": self.related_resource_types,
            "related_actions": self.related_actions,
            "description": self.description,
            "description_en": self.description_en,
        }

    def is_read_action(self):
        """
        是否为读权限
        """
        return self.type == "view"


# CMDB 业务资源类型
SPACE_RESOURCE = {
    "id": "space",
    "system_id": settings.BK_IAM_SYSTEM_ID,
    "selection_mode": "instance",
    "related_instance_selections": [{"system_id": "bk_monitorv3", "id": "space_list"}],
}

APM_APPLICATION_RESOURCE = {
    "id": "apm_application",
    "system_id": settings.BK_IAM_SYSTEM_ID,
    "selection_mode": "instance",
    "related_instance_selections": [{"system_id": settings.BK_IAM_SYSTEM_ID, "id": "apm_application_list_v2"}],
}

GRAFANA_DASHBOARD_RESOURCE = {
    "id": "grafana_dashboard",
    "system_id": settings.BK_IAM_SYSTEM_ID,
    "selection_mode": "instance",
    "related_instance_selections": [{"system_id": settings.BK_IAM_SYSTEM_ID, "id": "grafana_dashboard_list"}],
}


class ActionEnum:
    VIEW_BUSINESS = ActionMeta(
        id="view_business_v2",
        name=_("业务访问"),
        name_en="View Business",
        type="view",
        related_resource_types=[SPACE_RESOURCE],
        related_actions=[],
        version=1,
    )

    EXPLORE_METRIC = ActionMeta(
        id="explore_metric_v2",
        name=_("指标检索"),
        name_en="Explore Metric",
        type="view",
        related_resource_types=[SPACE_RESOURCE],
        related_actions=[VIEW_BUSINESS.id],
        version=1,
    )

    VIEW_SYNTHETIC = ActionMeta(
        id="view_synthetic_v2",
        name=_("拨测查看"),
        name_en="View Synthetic",
        type="view",
        related_resource_types=[SPACE_RESOURCE],
        related_actions=[VIEW_BUSINESS.id],
        version=1,
    )

    MANAGE_SYNTHETIC = ActionMeta(
        id="manage_synthetic_v2",
        name=_("拨测管理"),
        name_en="Manage Synthetic",
        type="manage",
        related_resource_types=[SPACE_RESOURCE],
        related_actions=[VIEW_SYNTHETIC.id],
        version=1,
    )

    MANAGE_PUBLIC_SYNTHETIC_LOCATION = ActionMeta(
        id="manage_public_synthetic_location",
        name=_("拨测公共节点管理"),
        name_en="Manage Public Synthetic Location",
        type="manage",
        related_resource_types=[],
        related_actions=[VIEW_SYNTHETIC.id],
        version=1,
    )

    VIEW_HOST = ActionMeta(
        id="view_host_v2",
        name=_("主机详情查看"),
        name_en="View Host",
        type="view",
        related_resource_types=[SPACE_RESOURCE],
        related_actions=[VIEW_BUSINESS.id],
        version=1,
    )

    MANAGE_HOST = ActionMeta(
        id="manage_host_v2",
        name=_("主机详情管理"),
        name_en="Manage Host",
        type="manage",
        related_resource_types=[SPACE_RESOURCE],
        related_actions=[VIEW_BUSINESS.id, VIEW_HOST.id],
        version=1,
    )

    VIEW_EVENT = ActionMeta(
        id="view_event_v2",
        name=_("事件中心查看"),
        name_en="View Event",
        type="view",
        related_resource_types=[SPACE_RESOURCE],
        related_actions=[VIEW_BUSINESS.id],
        version=1,
    )

    MANAGE_EVENT = ActionMeta(
        id="manage_event_v2",
        name=_("事件中心管理"),
        name_en="Manage Event",
        type="manage",
        related_resource_types=[SPACE_RESOURCE],
        related_actions=[VIEW_EVENT.id],
        version=1,
    )

    VIEW_PLUGIN = ActionMeta(
        id="view_plugin_v2",
        name=_("指标插件查看"),
        name_en="View Metric Plugin",
        type="view",
        related_resource_types=[SPACE_RESOURCE],
        related_actions=[VIEW_BUSINESS.id],
        version=1,
    )

    MANAGE_PLUGIN = ActionMeta(
        id="manage_plugin_v2",
        name=_("指标插件管理"),
        name_en="Manage Metric Plugin",
        type="manage",
        related_resource_types=[SPACE_RESOURCE],
        related_actions=[VIEW_PLUGIN.id],
        version=1,
    )

    MANAGE_PUBLIC_PLUGIN = ActionMeta(
        id="manage_public_plugin",
        name=_("公共插件管理"),
        name_en="Manage Public Plugin",
        type="manage",
        related_resource_types=[],
        related_actions=[],
        version=1,
    )

    VIEW_COLLECTION = ActionMeta(
        id="view_collection_v2",
        name=_("采集查看"),
        name_en="View Collection",
        type="view",
        related_resource_types=[SPACE_RESOURCE],
        related_actions=[VIEW_BUSINESS.id],
        version=1,
    )

    MANAGE_COLLECTION = ActionMeta(
        id="manage_collection_v2",
        name=_("采集管理"),
        name_en="Manage Collection",
        type="manage",
        related_resource_types=[SPACE_RESOURCE],
        related_actions=[VIEW_COLLECTION.id],
        version=1,
    )

    VIEW_NOTIFY_TEAM = ActionMeta(
        id="view_notify_team_v2",
        name=_("告警组查看"),
        name_en="View Notify Team",
        type="view",
        related_resource_types=[SPACE_RESOURCE],
        related_actions=[VIEW_BUSINESS.id],
        version=1,
    )

    MANAGE_NOTIFY_TEAM = ActionMeta(
        id="manage_notify_team_v2",
        name=_("告警组管理"),
        name_en="Manage Notify Team",
        type="manage",
        related_resource_types=[SPACE_RESOURCE],
        related_actions=[VIEW_BUSINESS.id, VIEW_NOTIFY_TEAM.id],
        version=1,
    )

    VIEW_RULE = ActionMeta(
        id="view_rule_v2",
        name=_("策略查看"),
        name_en="View Rule",
        type="view",
        related_resource_types=[SPACE_RESOURCE],
        related_actions=[VIEW_BUSINESS.id, VIEW_NOTIFY_TEAM.id, VIEW_NOTIFY_TEAM.id],
        version=1,
    )

    MANAGE_RULE = ActionMeta(
        id="manage_rule_v2",
        name=_("策略管理"),
        name_en="Manage Rule",
        type="manage",
        related_resource_types=[SPACE_RESOURCE],
        related_actions=[VIEW_BUSINESS.id, VIEW_RULE.id, VIEW_NOTIFY_TEAM.id],
        version=1,
    )

    VIEW_DOWNTIME = ActionMeta(
        id="view_downtime_v2",
        name=_("屏蔽查看"),
        name_en="View Downtime",
        type="view",
        related_resource_types=[SPACE_RESOURCE],
        related_actions=[VIEW_BUSINESS.id],
        version=1,
    )

    MANAGE_DOWNTIME = ActionMeta(
        id="manage_downtime_v2",
        name=_("屏蔽管理"),
        name_en="Manage Downtime",
        type="manage",
        related_resource_types=[SPACE_RESOURCE],
        related_actions=[VIEW_BUSINESS.id, VIEW_NOTIFY_TEAM.id, VIEW_RULE.id],
        version=1,
    )

    VIEW_CUSTOM_METRIC = ActionMeta(
        id="view_custom_metric_v2",
        name=_("自定义指标上报查看"),
        name_en="View Custom Metric",
        type="view",
        related_resource_types=[SPACE_RESOURCE],
        related_actions=[VIEW_BUSINESS.id],
        version=1,
    )

    MANAGE_CUSTOM_METRIC = ActionMeta(
        id="manage_custom_metric_v2",
        name=_("自定义指标上报管理"),
        name_en="Manage Custom Metric",
        type="manage",
        related_resource_types=[SPACE_RESOURCE],
        related_actions=[VIEW_BUSINESS.id, VIEW_CUSTOM_METRIC.id],
        version=1,
    )

    VIEW_CUSTOM_EVENT = ActionMeta(
        id="view_custom_event_v2",
        name=_("自定义事件上报查看"),
        name_en="View Custom Event",
        type="view",
        related_resource_types=[SPACE_RESOURCE],
        related_actions=[VIEW_BUSINESS.id],
        version=1,
    )

    MANAGE_CUSTOM_EVENT = ActionMeta(
        id="manage_custom_event_v2",
        name=_("自定义事件上报管理"),
        name_en="Manage Custom Event",
        type="manage",
        related_resource_types=[SPACE_RESOURCE],
        related_actions=[VIEW_BUSINESS.id, VIEW_CUSTOM_EVENT.id],
        version=1,
    )

    VIEW_DASHBOARD = ActionMeta(
        id="view_dashboard_v2",
        name=_("仪表盘查看"),
        name_en="View Dashboard",
        type="view",
        related_resource_types=[SPACE_RESOURCE],
        related_actions=[VIEW_BUSINESS.id],
        version=1,
    )

    MANAGE_DASHBOARD = ActionMeta(
        id="manage_dashboard_v2",
        name=_("仪表盘管理"),
        name_en="Manage Dashboard",
        type="manage",
        related_resource_types=[SPACE_RESOURCE],
        related_actions=[VIEW_BUSINESS.id, VIEW_DASHBOARD.id],
        version=1,
    )

    VIEW_SINGLE_DASHBOARD = ActionMeta(
        id="view_single_dashboard",
        name=_("仪表盘实例查看"),
        name_en="View Single Dashboard",
        type="view",
        related_resource_types=[GRAFANA_DASHBOARD_RESOURCE],
        related_actions=[VIEW_BUSINESS.id],
        version=1,
    )

    EDIT_SINGLE_DASHBOARD = ActionMeta(
        id="edit_single_dashboard",
        name=_("仪表盘实例编辑"),
        name_en="Edit Single Dashboard",
        type="manage",
        related_resource_types=[GRAFANA_DASHBOARD_RESOURCE],
        related_actions=[VIEW_BUSINESS.id, VIEW_SINGLE_DASHBOARD.id],
        version=1,
    )

    NEW_DASHBOARD = ActionMeta(
        id="new_dashboard",
        name=_("新建仪表盘"),
        name_en="New Dashboard",
        type="manage",
        related_resource_types=[SPACE_RESOURCE],
        related_actions=[VIEW_BUSINESS.id, VIEW_SINGLE_DASHBOARD.id, EDIT_SINGLE_DASHBOARD.id],
        version=1,
    )

    MANAGE_DATASOURCE = ActionMeta(
        id="manage_datasource_v2",
        name=_("仪表盘配置管理"),
        name_en="Manage DataSource",
        type="manage",
        related_resource_types=[SPACE_RESOURCE],
        related_actions=[VIEW_BUSINESS.id, VIEW_SINGLE_DASHBOARD.id, EDIT_SINGLE_DASHBOARD.id],
        version=1,
    )

    EXPORT_CONFIG = ActionMeta(
        id="export_config_v2",
        name=_("导出"),
        name_en="Export Config",
        type="view",
        related_resource_types=[SPACE_RESOURCE],
        related_actions=[VIEW_BUSINESS.id],
        version=1,
    )

    IMPORT_CONFIG = ActionMeta(
        id="import_config_v2",
        name=_("导入"),
        name_en="Import Config",
        type="manage",
        related_resource_types=[SPACE_RESOURCE],
        related_actions=[VIEW_BUSINESS.id],
        version=1,
    )

    VIEW_GLOBAL_SETTING = ActionMeta(
        id="view_global_setting",
        name=_("全局配置查看"),
        name_en="View Global Setting",
        type="view",
        related_resource_types=[],
        version=1,
    )

    MANAGE_GLOBAL_SETTING = ActionMeta(
        id="manage_global_setting",
        name=_("全局配置编辑"),
        name_en="Manage Global Setting",
        type="manage",
        related_resource_types=[],
        version=1,
    )

    VIEW_SELF_STATE = ActionMeta(
        id="view_self_state",
        name=_("自监控查看"),
        name_en="View Self-state",
        type="view",
        related_resource_types=[],
        version=1,
    )

    MANAGE_PUBLIC_ACTION_CONFIG = ActionMeta(
        id="manage_public_action_config",
        name=_("公共套餐管理"),
        name_en="Manage Public Action Config",
        type="manage",
        related_resource_types=[],
        version=1,
    )

    VIEW_APM_APPLICATION = ActionMeta(
        id="view_apm_application_v2",
        name=_("APM应用查看"),
        name_en="APM Application View",
        type="view",
        related_resource_types=[APM_APPLICATION_RESOURCE],
        related_actions=[VIEW_BUSINESS.id],
        version=1,
    )

    MANAGE_APM_APPLICATION = ActionMeta(
        id="manage_apm_application_v2",
        name=_("APM应用管理"),
        name_en="APM Application Manage",
        type="manage",
        related_resource_types=[APM_APPLICATION_RESOURCE],
        related_actions=[],
        version=1,
    )

    MANAGE_CALENDAR = ActionMeta(
        id="manage_calendar",
        name=_("日历服务管理"),
        name_en="Calendar Manage",
        type="manage",
        related_resource_types=[],
        related_actions=[],
        version=1,
    )
    MANAGE_REPORT = ActionMeta(
        id="manage_report",
        name=_("订阅管理"),
        name_en="Report Manage",
        type="manage",
        related_resource_types=[SPACE_RESOURCE],
        related_actions=[VIEW_BUSINESS.id],
        version=1,
    )

    VIEW_INCIDENT = ActionMeta(
        id="view_incident",
        name=_("故障查看"),
        name_en="View Incident",
        type="view",
        related_resource_types=[SPACE_RESOURCE],
        related_actions=[VIEW_BUSINESS.id],
        version=1,
    )

    MANAGE_INCIDENT = ActionMeta(
        id="manage_incident",
        name=_("故障管理"),
        name_en="Manage Incident",
        type="manage",
        related_resource_types=[SPACE_RESOURCE],
        related_actions=[VIEW_INCIDENT.id],
        version=1,
    )


_all_actions = {action.id: action for action in ActionEnum.__dict__.values() if isinstance(action, ActionMeta)}


def get_action_by_id(action_id: Union[str, ActionMeta]) -> ActionMeta:
    """
    根据动作ID获取动作实例
    """
    if isinstance(action_id, ActionMeta):
        # 如果已经是实例，则直接返回
        return action_id

    if action_id not in _all_actions:
        raise ActionNotExistError({"action_id": action_id})

    return _all_actions[action_id]


def fetch_related_actions(actions: List[Union[ActionMeta, str]]) -> Dict[str, ActionMeta]:
    """
    递归获取 action 动作依赖列表
    """
    actions = [get_action_by_id(action) for action in actions]

    def fetch_related_actions_recursive(_action: ActionMeta):
        _related_actions = {}
        for related_action_id in _action.related_actions:
            try:
                related_action = get_action_by_id(related_action_id)
            except ActionNotExistError:
                continue
            _related_actions[related_action_id] = related_action
            _related_actions.update(fetch_related_actions_recursive(related_action))
        return _related_actions

    related_actions = {}
    for action in actions:
        related_actions.update(fetch_related_actions_recursive(action))

    # 剔除根节点本身
    for action in actions:
        related_actions.pop(action.id, None)

    return related_actions


def generate_all_actions_json() -> List:
    """
    生成migrations的json配置
    """
    results = []
    for value in _all_actions.values():
        results.append({"operation": "upsert_action", "data": value.to_json()})
    return results


# 权限全集
ALL_ACTION_IDS = set(_all_actions.keys())
# 默认最小监控功能使用权限
MINI_ACTION_IDS = [
    ActionEnum.VIEW_BUSINESS.id,
    ActionEnum.EXPLORE_METRIC.id,
    ActionEnum.VIEW_EVENT.id,
    ActionEnum.MANAGE_EVENT.id,
    ActionEnum.VIEW_NOTIFY_TEAM.id,
    ActionEnum.MANAGE_NOTIFY_TEAM.id,
    ActionEnum.VIEW_RULE.id,
    ActionEnum.MANAGE_RULE.id,
    ActionEnum.VIEW_DOWNTIME.id,
    ActionEnum.MANAGE_DOWNTIME.id,
    ActionEnum.VIEW_CUSTOM_METRIC.id,
    ActionEnum.MANAGE_CUSTOM_METRIC.id,
    ActionEnum.VIEW_CUSTOM_EVENT.id,
    ActionEnum.MANAGE_CUSTOM_EVENT.id,
    ActionEnum.VIEW_SINGLE_DASHBOARD.id,
    ActionEnum.EDIT_SINGLE_DASHBOARD.id,
    ActionEnum.MANAGE_DATASOURCE.id,
    ActionEnum.EXPORT_CONFIG.id,
    ActionEnum.IMPORT_CONFIG.id,
    ActionEnum.VIEW_APM_APPLICATION.id,
    ActionEnum.MANAGE_APM_APPLICATION.id,
    ActionEnum.VIEW_INCIDENT.id,
    ActionEnum.MANAGE_INCIDENT.id,
]
# CMDB（主机依赖）权限
CMDB_REQUIRE_ACTION_IDS = [
    ActionEnum.MANAGE_COLLECTION.id,
    ActionEnum.VIEW_COLLECTION.id,
    ActionEnum.MANAGE_HOST.id,
    ActionEnum.VIEW_HOST.id,
    ActionEnum.MANAGE_PLUGIN.id,
    ActionEnum.VIEW_PLUGIN.id,
    ActionEnum.MANAGE_SYNTHETIC.id,
    ActionEnum.VIEW_SYNTHETIC.id,
]
# 管理权限
ADMIN_ACTION_IDS = [
    ActionEnum.MANAGE_CALENDAR.id,
    ActionEnum.MANAGE_REPORT.id,
    ActionEnum.MANAGE_GLOBAL_SETTING.id,
    ActionEnum.VIEW_GLOBAL_SETTING.id,
    ActionEnum.MANAGE_PUBLIC_PLUGIN.id,
    ActionEnum.MANAGE_PUBLIC_ACTION_CONFIG.id,
    ActionEnum.MANAGE_PUBLIC_SYNTHETIC_LOCATION.id,
    ActionEnum.VIEW_SELF_STATE.id,
]
