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
# 操作定义（v3/v4 共用）
#
# Action ID 与现有 bkmonitor/iam/action.py 中 ActionEnum 保持一致。
#
# extensions["v3"] 字段说明：
#   action_id : V3 IAM 平台实际注册的 action_id（带 _v2 后缀表示经历过 V1→V2 迁移）
#   type      : ABAC 的 view / manage
#   version   : 固定为 1
# ---------------------------------------------------------------------------

from ..iam_engine.schema.definitions import ActionDef


class Actions:
    # ---- Space-level view actions ----
    VIEW_BUSINESS = ActionDef(
        id="view_business",
        name="业务访问",
        resource_type="space",
        extensions={"v3": {"action_id": "view_business_v2", "type": "view", "version": 1}},
    )
    EXPLORE_METRIC = ActionDef(
        id="explore_metric",
        name="指标检索",
        resource_type="space",
        extensions={"v3": {"action_id": "explore_metric_v2", "type": "view", "version": 1}},
    )
    VIEW_SYNTHETIC = ActionDef(
        id="view_synthetic",
        name="拨测查看",
        resource_type="space",
        extensions={"v3": {"action_id": "view_synthetic_v2", "type": "view", "version": 1}},
    )
    VIEW_HOST = ActionDef(
        id="view_host",
        name="主机详情查看",
        resource_type="space",
        extensions={"v3": {"action_id": "view_host_v2", "type": "view", "version": 1}},
    )
    VIEW_EVENT = ActionDef(
        id="view_event",
        name="事件中心查看",
        resource_type="space",
        extensions={"v3": {"action_id": "view_event_v2", "type": "view", "version": 1}},
    )
    VIEW_PLUGIN = ActionDef(
        id="view_plugin",
        name="指标插件查看",
        resource_type="space",
        extensions={"v3": {"action_id": "view_plugin_v2", "type": "view", "version": 1}},
    )
    VIEW_COLLECTION = ActionDef(
        id="view_collection",
        name="采集查看",
        resource_type="space",
        extensions={"v3": {"action_id": "view_collection_v2", "type": "view", "version": 1}},
    )
    VIEW_NOTIFY_TEAM = ActionDef(
        id="view_notify_team",
        name="告警组查看",
        resource_type="space",
        extensions={"v3": {"action_id": "view_notify_team_v2", "type": "view", "version": 1}},
    )
    VIEW_RULE = ActionDef(
        id="view_rule",
        name="策略查看",
        resource_type="space",
        extensions={"v3": {"action_id": "view_rule_v2", "type": "view", "version": 1}},
    )
    VIEW_DOWNTIME = ActionDef(
        id="view_downtime",
        name="屏蔽查看",
        resource_type="space",
        extensions={"v3": {"action_id": "view_downtime_v2", "type": "view", "version": 1}},
    )
    VIEW_CUSTOM_METRIC = ActionDef(
        id="view_custom_metric",
        name="自定义指标上报查看",
        resource_type="space",
        extensions={"v3": {"action_id": "view_custom_metric_v2", "type": "view", "version": 1}},
    )
    VIEW_CUSTOM_EVENT = ActionDef(
        id="view_custom_event",
        name="自定义事件上报查看",
        resource_type="space",
        extensions={"v3": {"action_id": "view_custom_event_v2", "type": "view", "version": 1}},
    )
    VIEW_DASHBOARD = ActionDef(
        id="view_dashboard",
        name="仪表盘查看",
        resource_type="space",
        extensions={"v3": {"action_id": "view_dashboard_v2", "type": "view", "version": 1}},
    )
    VIEW_INCIDENT = ActionDef(
        id="view_incident",
        name="故障查看",
        resource_type="space",
        extensions={"v3": {"action_id": "view_incident", "type": "view", "version": 1}},
    )
    EXPORT_CONFIG = ActionDef(
        id="export_config",
        name="导出",
        resource_type="space",
        extensions={"v3": {"action_id": "export_config_v2", "type": "view", "version": 1}},
    )

    # ---- MCP view actions (space-level) ----
    USING_DASHBOARD_MCP = ActionDef(
        id="using_dashboard_mcp",
        name="使用仪表盘MCP",
        resource_type="space",
        extensions={"v3": {"action_id": "using_dashboard_mcp", "type": "view", "version": 1}},
    )
    USING_METRICS_MCP = ActionDef(
        id="using_metrics_mcp",
        name="使用指标MCP",
        resource_type="space",
        extensions={"v3": {"action_id": "using_metrics_mcp", "type": "view", "version": 1}},
    )
    USING_LOG_MCP = ActionDef(
        id="using_log_mcp",
        name="使用日志MCP",
        resource_type="space",
        extensions={"v3": {"action_id": "using_log_mcp", "type": "view", "version": 1}},
    )
    USING_METADATA_MCP = ActionDef(
        id="using_metadata_mcp",
        name="使用元数据MCP",
        resource_type="space",
        extensions={"v3": {"action_id": "using_metadata_mcp", "type": "view", "version": 1}},
    )
    USING_ALARM_MCP = ActionDef(
        id="using_alarm_mcp",
        name="使用告警查询MCP",
        resource_type="space",
        extensions={"v3": {"action_id": "using_alarm_mcp", "type": "view", "version": 1}},
    )
    USING_APM_MCP = ActionDef(
        id="using_apm_mcp",
        name="使用APM MCP",
        resource_type="space",
        extensions={"v3": {"action_id": "using_apm_mcp", "type": "view", "version": 1}},
    )
    USING_OPERATION_MCP = ActionDef(
        id="using_operation_mcp",
        name="使用运营数据MCP",
        resource_type="space",
        extensions={"v3": {"action_id": "using_operation_mcp", "type": "view", "version": 1}},
    )

    # ---- Space-level manage actions ----
    MANAGE_SYNTHETIC = ActionDef(
        id="manage_synthetic",
        name="拨测管理",
        resource_type="space",
        extensions={"v3": {"action_id": "manage_synthetic_v2", "type": "manage", "version": 1}},
    )
    MANAGE_HOST = ActionDef(
        id="manage_host",
        name="主机详情管理",
        resource_type="space",
        extensions={"v3": {"action_id": "manage_host_v2", "type": "manage", "version": 1}},
    )
    MANAGE_EVENT = ActionDef(
        id="manage_event",
        name="事件中心管理",
        resource_type="space",
        extensions={"v3": {"action_id": "manage_event_v2", "type": "manage", "version": 1}},
    )
    MANAGE_PLUGIN = ActionDef(
        id="manage_plugin",
        name="指标插件管理",
        resource_type="space",
        extensions={"v3": {"action_id": "manage_plugin_v2", "type": "manage", "version": 1}},
    )
    MANAGE_COLLECTION = ActionDef(
        id="manage_collection",
        name="采集管理",
        resource_type="space",
        extensions={"v3": {"action_id": "manage_collection_v2", "type": "manage", "version": 1}},
    )
    MANAGE_NOTIFY_TEAM = ActionDef(
        id="manage_notify_team",
        name="告警组管理",
        resource_type="space",
        extensions={"v3": {"action_id": "manage_notify_team_v2", "type": "manage", "version": 1}},
    )
    MANAGE_RULE = ActionDef(
        id="manage_rule",
        name="策略管理",
        resource_type="space",
        extensions={"v3": {"action_id": "manage_rule_v2", "type": "manage", "version": 1}},
    )
    MANAGE_DOWNTIME = ActionDef(
        id="manage_downtime",
        name="屏蔽管理",
        resource_type="space",
        extensions={"v3": {"action_id": "manage_downtime_v2", "type": "manage", "version": 1}},
    )
    MANAGE_CUSTOM_METRIC = ActionDef(
        id="manage_custom_metric",
        name="自定义指标上报管理",
        resource_type="space",
        extensions={"v3": {"action_id": "manage_custom_metric_v2", "type": "manage", "version": 1}},
    )
    MANAGE_CUSTOM_EVENT = ActionDef(
        id="manage_custom_event",
        name="自定义事件上报管理",
        resource_type="space",
        extensions={"v3": {"action_id": "manage_custom_event_v2", "type": "manage", "version": 1}},
    )
    MANAGE_DASHBOARD = ActionDef(
        id="manage_dashboard",
        name="仪表盘管理",
        resource_type="space",
        extensions={"v3": {"action_id": "manage_dashboard_v2", "type": "manage", "version": 1}},
    )
    MANAGE_DATASOURCE = ActionDef(
        id="manage_datasource",
        name="仪表盘配置管理",
        resource_type="space",
        extensions={"v3": {"action_id": "manage_datasource_v2", "type": "manage", "version": 1}},
    )
    NEW_DASHBOARD = ActionDef(
        id="new_dashboard",
        name="新建仪表盘",
        resource_type="space",
        extensions={"v3": {"action_id": "new_dashboard", "type": "manage", "version": 1}},
    )
    IMPORT_CONFIG = ActionDef(
        id="import_config",
        name="导入",
        resource_type="space",
        extensions={"v3": {"action_id": "import_config_v2", "type": "manage", "version": 1}},
    )
    MANAGE_INCIDENT = ActionDef(
        id="manage_incident",
        name="故障管理",
        resource_type="space",
        extensions={"v3": {"action_id": "manage_incident", "type": "manage", "version": 1}},
    )
    MANAGE_REPORT = ActionDef(
        id="manage_report",
        name="订阅管理",
        resource_type="space",
        extensions={"v3": {"action_id": "manage_report", "type": "manage", "version": 1}},
    )
    USING_ALARM_HANDLING_MCP = ActionDef(
        id="using_alarm_handling_mcp",
        name="使用告警处置MCP",
        resource_type="space",
        extensions={"v3": {"action_id": "using_alarm_handling_mcp", "type": "manage", "version": 1}},
    )

    # ---- Sub-resource view actions ----
    VIEW_APM_APPLICATION = ActionDef(
        id="view_apm_application",
        name="APM应用查看",
        resource_type="apm_application",
        extensions={"v3": {"action_id": "view_apm_application_v2", "type": "view", "version": 1}},
    )
    VIEW_SINGLE_DASHBOARD = ActionDef(
        id="view_single_dashboard",
        name="仪表盘实例查看",
        resource_type="grafana_dashboard",
        extensions={"v3": {"action_id": "view_single_dashboard", "type": "view", "version": 1}},
    )
    VIEW_RUM_APPLICATION = ActionDef(
        id="view_rum_application",
        name="RUM应用查看",
        resource_type="rum_application",
        extensions={"v3": {"action_id": "view_rum_application_v2", "type": "view", "version": 1}},
    )

    # ---- Sub-resource manage actions ----
    MANAGE_APM_APPLICATION = ActionDef(
        id="manage_apm_application",
        name="APM应用管理",
        resource_type="apm_application",
        extensions={"v3": {"action_id": "manage_apm_application_v2", "type": "manage", "version": 1}},
    )
    EDIT_SINGLE_DASHBOARD = ActionDef(
        id="edit_single_dashboard",
        name="仪表盘实例编辑",
        resource_type="grafana_dashboard",
        extensions={"v3": {"action_id": "edit_single_dashboard", "type": "manage", "version": 1}},
    )
    MANAGE_RUM_APPLICATION = ActionDef(
        id="manage_rum_application",
        name="RUM应用管理",
        resource_type="rum_application",
        extensions={"v3": {"action_id": "manage_rum_application_v2", "type": "manage", "version": 1}},
    )

    # ---- Resource-free actions ----
    VIEW_GLOBAL_SETTING = ActionDef(
        id="view_global_setting",
        name="全局配置查看",
        resource_type="",
        extensions={"v3": {"action_id": "view_global_setting", "type": "view", "version": 1}},
    )
    MANAGE_GLOBAL_SETTING = ActionDef(
        id="manage_global_setting",
        name="全局配置编辑",
        resource_type="",
        extensions={"v3": {"action_id": "manage_global_setting", "type": "manage", "version": 1}},
    )
    VIEW_SELF_STATE = ActionDef(
        id="view_self_state",
        name="自监控查看",
        resource_type="",
        extensions={"v3": {"action_id": "view_self_state", "type": "view", "version": 1}},
    )
    MANAGE_PUBLIC_PLUGIN = ActionDef(
        id="manage_public_plugin",
        name="公共插件管理",
        resource_type="",
        extensions={"v3": {"action_id": "manage_public_plugin", "type": "manage", "version": 1}},
    )
    MANAGE_PUBLIC_ACTION_CONFIG = ActionDef(
        id="manage_public_action_config",
        name="公共套餐管理",
        resource_type="",
        extensions={"v3": {"action_id": "manage_public_action_config", "type": "manage", "version": 1}},
    )
    MANAGE_PUBLIC_SYNTHETIC_LOCATION = ActionDef(
        id="manage_public_synthetic_location",
        name="拨测公共节点管理",
        resource_type="",
        extensions={"v3": {"action_id": "manage_public_synthetic_location", "type": "manage", "version": 1}},
    )
    USE_PUBLIC_SYNTHETIC_LOCATION = ActionDef(
        id="use_public_synthetic_location",
        name="拨测公共节点使用",
        resource_type="",
        extensions={"v3": {"action_id": "use_public_synthetic_location", "type": "view", "version": 1}},
    )
    MANAGE_CALENDAR = ActionDef(
        id="manage_calendar",
        name="日历服务管理",
        resource_type="",
        extensions={"v3": {"action_id": "manage_calendar", "type": "manage", "version": 1}},
    )
