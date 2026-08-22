"""
迁移: 0001_init
生成时间: 2026-08-21T13:52:27.413753
"""

import json

from bkmonitor.iam.iam_engine.schema.diff import Change, ChangeType, EntityKind


dependencies: list[str] = []

operations: list[Change] = [
    Change(
        kind=EntityKind.RESOURCE_TYPE,
        change_type=ChangeType.CREATE,
        entity_id="space",
        before=None,
        after={
            "id": "space",
            "name": "空间",
            "description": "",
            "extensions": {
                "v3": {
                    "system_id": "bk_monitorv3",
                    "selection_mode": "instance",
                    "name_en": "Space",
                    "related_instance_selections": [{"system_id": "bk_monitorv3", "id": "space_list"}],
                }
            },
            "ancestors": [],
        },
        reason="New resource type",
        destructive=False,
    ),
    Change(
        kind=EntityKind.RESOURCE_TYPE,
        change_type=ChangeType.CREATE,
        entity_id="apm_application",
        before=None,
        after={
            "id": "apm_application",
            "name": "APM应用",
            "description": "",
            "extensions": {
                "v3": {
                    "system_id": "bk_monitorv3",
                    "selection_mode": "instance",
                    "name_en": "APM Application",
                    "related_instance_selections": [{"system_id": "bk_monitorv3", "id": "apm_application_list_v2"}],
                }
            },
            "ancestors": ["space"],
        },
        reason="New resource type",
        destructive=False,
    ),
    Change(
        kind=EntityKind.RESOURCE_TYPE,
        change_type=ChangeType.CREATE,
        entity_id="grafana_dashboard",
        before=None,
        after={
            "id": "grafana_dashboard",
            "name": "Grafana仪表盘",
            "description": "",
            "extensions": {
                "v3": {
                    "system_id": "bk_monitorv3",
                    "selection_mode": "instance",
                    "name_en": "Grafana Dashboard",
                    "related_instance_selections": [{"system_id": "bk_monitorv3", "id": "grafana_dashboard_list"}],
                }
            },
            "ancestors": ["space"],
        },
        reason="New resource type",
        destructive=False,
    ),
    Change(
        kind=EntityKind.RESOURCE_TYPE,
        change_type=ChangeType.CREATE,
        entity_id="rum_application",
        before=None,
        after={
            "id": "rum_application",
            "name": "RUM应用",
            "description": "",
            "extensions": {
                "v3": {
                    "system_id": "bk_monitorv3",
                    "selection_mode": "instance",
                    "name_en": "RUM Application",
                    "related_instance_selections": [{"system_id": "bk_monitorv3", "id": "rum_application_list_v2"}],
                }
            },
            "ancestors": ["space"],
        },
        reason="New resource type",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="view_business",
        before=None,
        after={
            "id": "view_business",
            "name": "业务访问",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "view_business_v2",
                    "type": "view",
                    "version": 1,
                    "name_en": "View Business",
                    "related_actions": [],
                }
            },
            "resource_type_id": "space",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="explore_metric",
        before=None,
        after={
            "id": "explore_metric",
            "name": "指标检索",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "explore_metric_v2",
                    "type": "view",
                    "version": 1,
                    "name_en": "Explore Metric",
                    "related_actions": ["view_business_v2"],
                }
            },
            "resource_type_id": "space",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="view_synthetic",
        before=None,
        after={
            "id": "view_synthetic",
            "name": "拨测查看",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "view_synthetic_v2",
                    "type": "view",
                    "version": 1,
                    "name_en": "View Synthetic",
                    "related_actions": ["view_business_v2"],
                }
            },
            "resource_type_id": "space",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="view_host",
        before=None,
        after={
            "id": "view_host",
            "name": "主机详情查看",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "view_host_v2",
                    "type": "view",
                    "version": 1,
                    "name_en": "View Host",
                    "related_actions": ["view_business_v2"],
                }
            },
            "resource_type_id": "space",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="view_event",
        before=None,
        after={
            "id": "view_event",
            "name": "事件中心查看",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "view_event_v2",
                    "type": "view",
                    "version": 1,
                    "name_en": "View Event",
                    "related_actions": ["view_business_v2"],
                }
            },
            "resource_type_id": "space",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="view_plugin",
        before=None,
        after={
            "id": "view_plugin",
            "name": "指标插件查看",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "view_plugin_v2",
                    "type": "view",
                    "version": 1,
                    "name_en": "View Metric Plugin",
                    "related_actions": ["view_business_v2"],
                }
            },
            "resource_type_id": "space",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="view_collection",
        before=None,
        after={
            "id": "view_collection",
            "name": "采集查看",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "view_collection_v2",
                    "type": "view",
                    "version": 1,
                    "name_en": "View Collection",
                    "related_actions": ["view_business_v2"],
                }
            },
            "resource_type_id": "space",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="view_notify_team",
        before=None,
        after={
            "id": "view_notify_team",
            "name": "告警组查看",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "view_notify_team_v2",
                    "type": "view",
                    "version": 1,
                    "name_en": "View Notify Team",
                    "related_actions": ["view_business_v2"],
                }
            },
            "resource_type_id": "space",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="view_rule",
        before=None,
        after={
            "id": "view_rule",
            "name": "策略查看",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "view_rule_v2",
                    "type": "view",
                    "version": 1,
                    "name_en": "View Rule",
                    "related_actions": ["view_business_v2", "view_notify_team_v2", "view_notify_team_v2"],
                }
            },
            "resource_type_id": "space",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="view_downtime",
        before=None,
        after={
            "id": "view_downtime",
            "name": "屏蔽查看",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "view_downtime_v2",
                    "type": "view",
                    "version": 1,
                    "name_en": "View Downtime",
                    "related_actions": ["view_business_v2"],
                }
            },
            "resource_type_id": "space",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="view_custom_metric",
        before=None,
        after={
            "id": "view_custom_metric",
            "name": "自定义指标上报查看",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "view_custom_metric_v2",
                    "type": "view",
                    "version": 1,
                    "name_en": "View Custom Metric",
                    "related_actions": ["view_business_v2"],
                }
            },
            "resource_type_id": "space",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="view_custom_event",
        before=None,
        after={
            "id": "view_custom_event",
            "name": "自定义事件上报查看",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "view_custom_event_v2",
                    "type": "view",
                    "version": 1,
                    "name_en": "View Custom Event",
                    "related_actions": ["view_business_v2"],
                }
            },
            "resource_type_id": "space",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="view_dashboard",
        before=None,
        after={
            "id": "view_dashboard",
            "name": "仪表盘查看",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "view_dashboard_v2",
                    "type": "view",
                    "version": 1,
                    "name_en": "View Dashboard",
                    "related_actions": ["view_business_v2"],
                },
                "exclude_providers": ("v4",),
            },
            "resource_type_id": "space",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="view_incident",
        before=None,
        after={
            "id": "view_incident",
            "name": "故障查看",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "view_incident",
                    "type": "view",
                    "version": 1,
                    "name_en": "View Incident",
                    "related_actions": ["view_business_v2"],
                }
            },
            "resource_type_id": "space",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="export_config",
        before=None,
        after={
            "id": "export_config",
            "name": "导出",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "export_config_v2",
                    "type": "view",
                    "version": 1,
                    "name_en": "Export Config",
                    "related_actions": ["view_business_v2"],
                }
            },
            "resource_type_id": "space",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="using_dashboard_mcp",
        before=None,
        after={
            "id": "using_dashboard_mcp",
            "name": "使用仪表盘MCP",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "using_dashboard_mcp",
                    "type": "view",
                    "version": 1,
                    "name_en": "Using Dashboard MCP",
                    "related_actions": ["view_business_v2"],
                }
            },
            "resource_type_id": "space",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="using_metrics_mcp",
        before=None,
        after={
            "id": "using_metrics_mcp",
            "name": "使用指标MCP",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "using_metrics_mcp",
                    "type": "view",
                    "version": 1,
                    "name_en": "Using Metrics MCP",
                    "related_actions": ["view_business_v2"],
                }
            },
            "resource_type_id": "space",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="using_log_mcp",
        before=None,
        after={
            "id": "using_log_mcp",
            "name": "使用日志MCP",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "using_log_mcp",
                    "type": "view",
                    "version": 1,
                    "name_en": "Using Log MCP",
                    "related_actions": ["view_business_v2"],
                }
            },
            "resource_type_id": "space",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="using_metadata_mcp",
        before=None,
        after={
            "id": "using_metadata_mcp",
            "name": "使用元数据MCP",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "using_metadata_mcp",
                    "type": "view",
                    "version": 1,
                    "name_en": "Using Metadata MCP",
                    "related_actions": ["view_business_v2"],
                }
            },
            "resource_type_id": "space",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="using_alarm_mcp",
        before=None,
        after={
            "id": "using_alarm_mcp",
            "name": "使用告警查询MCP",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "using_alarm_mcp",
                    "type": "view",
                    "version": 1,
                    "name_en": "Using Alarm Query MCP",
                    "related_actions": ["view_business_v2"],
                }
            },
            "resource_type_id": "space",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="using_apm_mcp",
        before=None,
        after={
            "id": "using_apm_mcp",
            "name": "使用APM MCP",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "using_apm_mcp",
                    "type": "view",
                    "version": 1,
                    "name_en": "Using APM MCP",
                    "related_actions": ["view_business_v2"],
                }
            },
            "resource_type_id": "space",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="using_operation_mcp",
        before=None,
        after={
            "id": "using_operation_mcp",
            "name": "使用运营数据MCP",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "using_operation_mcp",
                    "type": "view",
                    "version": 1,
                    "name_en": "Using Operation MCP",
                    "related_actions": ["view_business_v2"],
                }
            },
            "resource_type_id": "space",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="manage_synthetic",
        before=None,
        after={
            "id": "manage_synthetic",
            "name": "拨测管理",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "manage_synthetic_v2",
                    "type": "manage",
                    "version": 1,
                    "name_en": "Manage Synthetic",
                    "related_actions": ["view_synthetic_v2"],
                }
            },
            "resource_type_id": "space",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="manage_host",
        before=None,
        after={
            "id": "manage_host",
            "name": "主机详情管理",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "manage_host_v2",
                    "type": "manage",
                    "version": 1,
                    "name_en": "Manage Host",
                    "related_actions": ["view_business_v2", "view_host_v2"],
                }
            },
            "resource_type_id": "space",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="manage_event",
        before=None,
        after={
            "id": "manage_event",
            "name": "事件中心管理",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "manage_event_v2",
                    "type": "manage",
                    "version": 1,
                    "name_en": "Manage Event",
                    "related_actions": ["view_event_v2"],
                }
            },
            "resource_type_id": "space",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="manage_plugin",
        before=None,
        after={
            "id": "manage_plugin",
            "name": "指标插件管理",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "manage_plugin_v2",
                    "type": "manage",
                    "version": 1,
                    "name_en": "Manage Metric Plugin",
                    "related_actions": ["view_plugin_v2"],
                }
            },
            "resource_type_id": "space",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="manage_collection",
        before=None,
        after={
            "id": "manage_collection",
            "name": "采集管理",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "manage_collection_v2",
                    "type": "manage",
                    "version": 1,
                    "name_en": "Manage Collection",
                    "related_actions": ["view_collection_v2"],
                }
            },
            "resource_type_id": "space",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="manage_notify_team",
        before=None,
        after={
            "id": "manage_notify_team",
            "name": "告警组管理",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "manage_notify_team_v2",
                    "type": "manage",
                    "version": 1,
                    "name_en": "Manage Notify Team",
                    "related_actions": ["view_business_v2", "view_notify_team_v2"],
                }
            },
            "resource_type_id": "space",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="manage_rule",
        before=None,
        after={
            "id": "manage_rule",
            "name": "策略管理",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "manage_rule_v2",
                    "type": "manage",
                    "version": 1,
                    "name_en": "Manage Rule",
                    "related_actions": ["view_business_v2", "view_rule_v2", "view_notify_team_v2"],
                }
            },
            "resource_type_id": "space",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="manage_downtime",
        before=None,
        after={
            "id": "manage_downtime",
            "name": "屏蔽管理",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "manage_downtime_v2",
                    "type": "manage",
                    "version": 1,
                    "name_en": "Manage Downtime",
                    "related_actions": ["view_business_v2", "view_notify_team_v2", "view_rule_v2"],
                }
            },
            "resource_type_id": "space",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="manage_custom_metric",
        before=None,
        after={
            "id": "manage_custom_metric",
            "name": "自定义指标上报管理",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "manage_custom_metric_v2",
                    "type": "manage",
                    "version": 1,
                    "name_en": "Manage Custom Metric",
                    "related_actions": ["view_business_v2", "view_custom_metric_v2"],
                }
            },
            "resource_type_id": "space",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="manage_custom_event",
        before=None,
        after={
            "id": "manage_custom_event",
            "name": "自定义事件上报管理",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "manage_custom_event_v2",
                    "type": "manage",
                    "version": 1,
                    "name_en": "Manage Custom Event",
                    "related_actions": ["view_business_v2", "view_custom_event_v2"],
                }
            },
            "resource_type_id": "space",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="manage_dashboard",
        before=None,
        after={
            "id": "manage_dashboard",
            "name": "仪表盘管理",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "manage_dashboard_v2",
                    "type": "manage",
                    "version": 1,
                    "name_en": "Manage Dashboard",
                    "related_actions": ["view_business_v2", "view_dashboard_v2"],
                },
                "exclude_providers": ("v4",),
            },
            "resource_type_id": "space",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="manage_datasource",
        before=None,
        after={
            "id": "manage_datasource",
            "name": "仪表盘配置管理",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "manage_datasource_v2",
                    "type": "manage",
                    "version": 1,
                    "name_en": "Manage DataSource",
                    "related_actions": ["view_business_v2", "view_single_dashboard", "edit_single_dashboard"],
                }
            },
            "resource_type_id": "space",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="new_dashboard",
        before=None,
        after={
            "id": "new_dashboard",
            "name": "新建仪表盘",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "new_dashboard",
                    "type": "manage",
                    "version": 1,
                    "name_en": "New Dashboard",
                    "related_actions": ["view_business_v2", "view_single_dashboard", "edit_single_dashboard"],
                }
            },
            "resource_type_id": "space",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="import_config",
        before=None,
        after={
            "id": "import_config",
            "name": "导入",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "import_config_v2",
                    "type": "manage",
                    "version": 1,
                    "name_en": "Import Config",
                    "related_actions": ["view_business_v2"],
                }
            },
            "resource_type_id": "space",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="manage_incident",
        before=None,
        after={
            "id": "manage_incident",
            "name": "故障管理",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "manage_incident",
                    "type": "manage",
                    "version": 1,
                    "name_en": "Manage Incident",
                    "related_actions": ["view_incident"],
                }
            },
            "resource_type_id": "space",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="manage_report",
        before=None,
        after={
            "id": "manage_report",
            "name": "订阅管理",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "manage_report",
                    "type": "manage",
                    "version": 1,
                    "name_en": "Report Manage",
                    "related_actions": ["view_business_v2"],
                }
            },
            "resource_type_id": "space",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="using_alarm_handling_mcp",
        before=None,
        after={
            "id": "using_alarm_handling_mcp",
            "name": "使用告警处置MCP",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "using_alarm_handling_mcp",
                    "type": "manage",
                    "version": 1,
                    "name_en": "Using Alarm Handling MCP",
                    "related_actions": ["using_alarm_mcp"],
                }
            },
            "resource_type_id": "space",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="view_apm_application",
        before=None,
        after={
            "id": "view_apm_application",
            "name": "APM应用查看",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "view_apm_application_v2",
                    "type": "view",
                    "version": 1,
                    "name_en": "APM Application View",
                    "related_actions": ["view_business_v2"],
                }
            },
            "resource_type_id": "apm_application",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="view_single_dashboard",
        before=None,
        after={
            "id": "view_single_dashboard",
            "name": "仪表盘实例查看",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "view_single_dashboard",
                    "type": "view",
                    "version": 1,
                    "name_en": "View Single Dashboard",
                    "related_actions": ["view_business_v2"],
                }
            },
            "resource_type_id": "grafana_dashboard",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="view_rum_application",
        before=None,
        after={
            "id": "view_rum_application",
            "name": "RUM应用查看",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "view_rum_application_v2",
                    "type": "view",
                    "version": 1,
                    "name_en": "RUM Application View",
                    "related_actions": ["view_business_v2"],
                }
            },
            "resource_type_id": "rum_application",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="manage_apm_application",
        before=None,
        after={
            "id": "manage_apm_application",
            "name": "APM应用管理",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "manage_apm_application_v2",
                    "type": "manage",
                    "version": 1,
                    "name_en": "APM Application Manage",
                    "related_actions": [],
                }
            },
            "resource_type_id": "apm_application",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="edit_single_dashboard",
        before=None,
        after={
            "id": "edit_single_dashboard",
            "name": "仪表盘实例编辑",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "edit_single_dashboard",
                    "type": "manage",
                    "version": 1,
                    "name_en": "Edit Single Dashboard",
                    "related_actions": ["view_business_v2", "view_single_dashboard"],
                }
            },
            "resource_type_id": "grafana_dashboard",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="manage_rum_application",
        before=None,
        after={
            "id": "manage_rum_application",
            "name": "RUM应用管理",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "manage_rum_application_v2",
                    "type": "manage",
                    "version": 1,
                    "name_en": "RUM Application Manage",
                    "related_actions": [],
                }
            },
            "resource_type_id": "rum_application",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="view_global_setting",
        before=None,
        after={
            "id": "view_global_setting",
            "name": "全局配置查看",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "view_global_setting",
                    "type": "view",
                    "version": 1,
                    "name_en": "View Global Setting",
                    "related_actions": [],
                }
            },
            "resource_type_id": "",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="manage_global_setting",
        before=None,
        after={
            "id": "manage_global_setting",
            "name": "全局配置编辑",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "manage_global_setting",
                    "type": "manage",
                    "version": 1,
                    "name_en": "Manage Global Setting",
                    "related_actions": [],
                }
            },
            "resource_type_id": "",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="view_self_state",
        before=None,
        after={
            "id": "view_self_state",
            "name": "自监控查看",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "view_self_state",
                    "type": "view",
                    "version": 1,
                    "name_en": "View Self-state",
                    "related_actions": [],
                }
            },
            "resource_type_id": "",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="manage_public_plugin",
        before=None,
        after={
            "id": "manage_public_plugin",
            "name": "公共插件管理",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "manage_public_plugin",
                    "type": "manage",
                    "version": 1,
                    "name_en": "Manage Public Plugin",
                    "related_actions": [],
                }
            },
            "resource_type_id": "",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="manage_public_action_config",
        before=None,
        after={
            "id": "manage_public_action_config",
            "name": "公共套餐管理",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "manage_public_action_config",
                    "type": "manage",
                    "version": 1,
                    "name_en": "Manage Public Action Config",
                    "related_actions": [],
                }
            },
            "resource_type_id": "",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="manage_public_synthetic_location",
        before=None,
        after={
            "id": "manage_public_synthetic_location",
            "name": "拨测公共节点管理",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "manage_public_synthetic_location",
                    "type": "manage",
                    "version": 1,
                    "name_en": "Manage Public Synthetic Location",
                    "related_actions": ["view_synthetic_v2"],
                }
            },
            "resource_type_id": "",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="use_public_synthetic_location",
        before=None,
        after={
            "id": "use_public_synthetic_location",
            "name": "拨测公共节点使用",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "use_public_synthetic_location",
                    "type": "view",
                    "version": 1,
                    "name_en": "Use Public Synthetic Location",
                    "related_actions": ["view_synthetic_v2"],
                }
            },
            "resource_type_id": "",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ACTION,
        change_type=ChangeType.CREATE,
        entity_id="manage_calendar",
        before=None,
        after={
            "id": "manage_calendar",
            "name": "日历服务管理",
            "description": "",
            "extensions": {
                "v3": {
                    "action_id": "manage_calendar",
                    "type": "manage",
                    "version": 1,
                    "name_en": "Calendar Manage",
                    "related_actions": [],
                }
            },
            "resource_type_id": "",
        },
        reason="New action",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ROLE,
        change_type=ChangeType.CREATE,
        entity_id="space_viewer",
        before=None,
        after={
            "id": "space_viewer",
            "name": "业务查看",
            "description": "",
            "extensions": {},
            "actions": [
                {"action_id": "view_business", "resource_type": "space"},
                {"action_id": "explore_metric", "resource_type": "space"},
                {"action_id": "view_synthetic", "resource_type": "space"},
                {"action_id": "view_host", "resource_type": "space"},
                {"action_id": "view_event", "resource_type": "space"},
                {"action_id": "view_plugin", "resource_type": "space"},
                {"action_id": "view_collection", "resource_type": "space"},
                {"action_id": "view_notify_team", "resource_type": "space"},
                {"action_id": "view_rule", "resource_type": "space"},
                {"action_id": "view_downtime", "resource_type": "space"},
                {"action_id": "view_custom_metric", "resource_type": "space"},
                {"action_id": "view_custom_event", "resource_type": "space"},
                {"action_id": "view_incident", "resource_type": "space"},
                {"action_id": "export_config", "resource_type": "space"},
                {"action_id": "using_dashboard_mcp", "resource_type": "space"},
                {"action_id": "using_metrics_mcp", "resource_type": "space"},
                {"action_id": "using_log_mcp", "resource_type": "space"},
                {"action_id": "using_metadata_mcp", "resource_type": "space"},
                {"action_id": "using_alarm_mcp", "resource_type": "space"},
                {"action_id": "using_apm_mcp", "resource_type": "space"},
                {"action_id": "using_operation_mcp", "resource_type": "space"},
                {"action_id": "view_apm_application", "resource_type": "apm_application"},
                {"action_id": "view_single_dashboard", "resource_type": "grafana_dashboard"},
                {"action_id": "view_rum_application", "resource_type": "rum_application"},
            ],
        },
        reason="New role",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ROLE,
        change_type=ChangeType.CREATE,
        entity_id="space_operator",
        before=None,
        after={
            "id": "space_operator",
            "name": "业务运维",
            "description": "",
            "extensions": {},
            "actions": [
                {"action_id": "view_business", "resource_type": "space"},
                {"action_id": "explore_metric", "resource_type": "space"},
                {"action_id": "view_synthetic", "resource_type": "space"},
                {"action_id": "view_host", "resource_type": "space"},
                {"action_id": "view_event", "resource_type": "space"},
                {"action_id": "view_plugin", "resource_type": "space"},
                {"action_id": "view_collection", "resource_type": "space"},
                {"action_id": "view_notify_team", "resource_type": "space"},
                {"action_id": "view_rule", "resource_type": "space"},
                {"action_id": "view_downtime", "resource_type": "space"},
                {"action_id": "view_custom_metric", "resource_type": "space"},
                {"action_id": "view_custom_event", "resource_type": "space"},
                {"action_id": "view_incident", "resource_type": "space"},
                {"action_id": "export_config", "resource_type": "space"},
                {"action_id": "using_dashboard_mcp", "resource_type": "space"},
                {"action_id": "using_metrics_mcp", "resource_type": "space"},
                {"action_id": "using_log_mcp", "resource_type": "space"},
                {"action_id": "using_metadata_mcp", "resource_type": "space"},
                {"action_id": "using_alarm_mcp", "resource_type": "space"},
                {"action_id": "using_apm_mcp", "resource_type": "space"},
                {"action_id": "using_operation_mcp", "resource_type": "space"},
                {"action_id": "view_apm_application", "resource_type": "apm_application"},
                {"action_id": "view_single_dashboard", "resource_type": "grafana_dashboard"},
                {"action_id": "view_rum_application", "resource_type": "rum_application"},
                {"action_id": "manage_synthetic", "resource_type": "space"},
                {"action_id": "manage_host", "resource_type": "space"},
                {"action_id": "manage_event", "resource_type": "space"},
                {"action_id": "manage_plugin", "resource_type": "space"},
                {"action_id": "manage_collection", "resource_type": "space"},
                {"action_id": "manage_notify_team", "resource_type": "space"},
                {"action_id": "manage_rule", "resource_type": "space"},
                {"action_id": "manage_downtime", "resource_type": "space"},
                {"action_id": "manage_custom_metric", "resource_type": "space"},
                {"action_id": "manage_custom_event", "resource_type": "space"},
                {"action_id": "manage_datasource", "resource_type": "space"},
                {"action_id": "new_dashboard", "resource_type": "space"},
                {"action_id": "import_config", "resource_type": "space"},
                {"action_id": "manage_incident", "resource_type": "space"},
                {"action_id": "manage_report", "resource_type": "space"},
                {"action_id": "using_alarm_handling_mcp", "resource_type": "space"},
                {"action_id": "manage_apm_application", "resource_type": "apm_application"},
                {"action_id": "edit_single_dashboard", "resource_type": "grafana_dashboard"},
                {"action_id": "manage_rum_application", "resource_type": "rum_application"},
            ],
        },
        reason="New role",
        destructive=False,
    ),
    Change(
        kind=EntityKind.ROLE,
        change_type=ChangeType.CREATE,
        entity_id="space_admin",
        before=None,
        after={
            "id": "space_admin",
            "name": "业务管理",
            "description": "",
            "extensions": {},
            "actions": [
                {"action_id": "view_business", "resource_type": "space"},
                {"action_id": "explore_metric", "resource_type": "space"},
                {"action_id": "view_synthetic", "resource_type": "space"},
                {"action_id": "view_host", "resource_type": "space"},
                {"action_id": "view_event", "resource_type": "space"},
                {"action_id": "view_plugin", "resource_type": "space"},
                {"action_id": "view_collection", "resource_type": "space"},
                {"action_id": "view_notify_team", "resource_type": "space"},
                {"action_id": "view_rule", "resource_type": "space"},
                {"action_id": "view_downtime", "resource_type": "space"},
                {"action_id": "view_custom_metric", "resource_type": "space"},
                {"action_id": "view_custom_event", "resource_type": "space"},
                {"action_id": "view_incident", "resource_type": "space"},
                {"action_id": "export_config", "resource_type": "space"},
                {"action_id": "using_dashboard_mcp", "resource_type": "space"},
                {"action_id": "using_metrics_mcp", "resource_type": "space"},
                {"action_id": "using_log_mcp", "resource_type": "space"},
                {"action_id": "using_metadata_mcp", "resource_type": "space"},
                {"action_id": "using_alarm_mcp", "resource_type": "space"},
                {"action_id": "using_apm_mcp", "resource_type": "space"},
                {"action_id": "using_operation_mcp", "resource_type": "space"},
                {"action_id": "view_apm_application", "resource_type": "apm_application"},
                {"action_id": "view_single_dashboard", "resource_type": "grafana_dashboard"},
                {"action_id": "view_rum_application", "resource_type": "rum_application"},
                {"action_id": "manage_synthetic", "resource_type": "space"},
                {"action_id": "manage_host", "resource_type": "space"},
                {"action_id": "manage_event", "resource_type": "space"},
                {"action_id": "manage_plugin", "resource_type": "space"},
                {"action_id": "manage_collection", "resource_type": "space"},
                {"action_id": "manage_notify_team", "resource_type": "space"},
                {"action_id": "manage_rule", "resource_type": "space"},
                {"action_id": "manage_downtime", "resource_type": "space"},
                {"action_id": "manage_custom_metric", "resource_type": "space"},
                {"action_id": "manage_custom_event", "resource_type": "space"},
                {"action_id": "manage_datasource", "resource_type": "space"},
                {"action_id": "new_dashboard", "resource_type": "space"},
                {"action_id": "import_config", "resource_type": "space"},
                {"action_id": "manage_incident", "resource_type": "space"},
                {"action_id": "manage_report", "resource_type": "space"},
                {"action_id": "using_alarm_handling_mcp", "resource_type": "space"},
                {"action_id": "manage_apm_application", "resource_type": "apm_application"},
                {"action_id": "edit_single_dashboard", "resource_type": "grafana_dashboard"},
                {"action_id": "manage_rum_application", "resource_type": "rum_application"},
                {"action_id": "view_global_setting", "resource_type": ""},
                {"action_id": "manage_global_setting", "resource_type": ""},
                {"action_id": "view_self_state", "resource_type": ""},
                {"action_id": "manage_public_plugin", "resource_type": ""},
                {"action_id": "manage_public_action_config", "resource_type": ""},
                {"action_id": "manage_public_synthetic_location", "resource_type": ""},
                {"action_id": "use_public_synthetic_location", "resource_type": ""},
                {"action_id": "manage_calendar", "resource_type": ""},
            ],
        },
        reason="New role",
        destructive=False,
    ),
]

target_snapshot: dict = json.loads(
    '{\n    "actions": {\n        "edit_single_dashboard": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "edit_single_dashboard",\n                    "name_en": "Edit Single Dashboard",\n                    "related_actions": [\n                        "view_business_v2",\n                        "view_single_dashboard"\n                    ],\n                    "type": "manage",\n                    "version": 1\n                }\n            },\n            "id": "edit_single_dashboard",\n            "name": "仪表盘实例编辑",\n            "resource_type": "grafana_dashboard"\n        },\n        "explore_metric": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "explore_metric_v2",\n                    "name_en": "Explore Metric",\n                    "related_actions": [\n                        "view_business_v2"\n                    ],\n                    "type": "view",\n                    "version": 1\n                }\n            },\n            "id": "explore_metric",\n            "name": "指标检索",\n            "resource_type": "space"\n        },\n        "export_config": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "export_config_v2",\n                    "name_en": "Export Config",\n                    "related_actions": [\n                        "view_business_v2"\n                    ],\n                    "type": "view",\n                    "version": 1\n                }\n            },\n            "id": "export_config",\n            "name": "导出",\n            "resource_type": "space"\n        },\n        "import_config": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "import_config_v2",\n                    "name_en": "Import Config",\n                    "related_actions": [\n                        "view_business_v2"\n                    ],\n                    "type": "manage",\n                    "version": 1\n                }\n            },\n            "id": "import_config",\n            "name": "导入",\n            "resource_type": "space"\n        },\n        "manage_apm_application": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "manage_apm_application_v2",\n                    "name_en": "APM Application Manage",\n                    "related_actions": [],\n                    "type": "manage",\n                    "version": 1\n                }\n            },\n            "id": "manage_apm_application",\n            "name": "APM应用管理",\n            "resource_type": "apm_application"\n        },\n        "manage_calendar": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "manage_calendar",\n                    "name_en": "Calendar Manage",\n                    "related_actions": [],\n                    "type": "manage",\n                    "version": 1\n                }\n            },\n            "id": "manage_calendar",\n            "name": "日历服务管理",\n            "resource_type": ""\n        },\n        "manage_collection": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "manage_collection_v2",\n                    "name_en": "Manage Collection",\n                    "related_actions": [\n                        "view_collection_v2"\n                    ],\n                    "type": "manage",\n                    "version": 1\n                }\n            },\n            "id": "manage_collection",\n            "name": "采集管理",\n            "resource_type": "space"\n        },\n        "manage_custom_event": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "manage_custom_event_v2",\n                    "name_en": "Manage Custom Event",\n                    "related_actions": [\n                        "view_business_v2",\n                        "view_custom_event_v2"\n                    ],\n                    "type": "manage",\n                    "version": 1\n                }\n            },\n            "id": "manage_custom_event",\n            "name": "自定义事件上报管理",\n            "resource_type": "space"\n        },\n        "manage_custom_metric": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "manage_custom_metric_v2",\n                    "name_en": "Manage Custom Metric",\n                    "related_actions": [\n                        "view_business_v2",\n                        "view_custom_metric_v2"\n                    ],\n                    "type": "manage",\n                    "version": 1\n                }\n            },\n            "id": "manage_custom_metric",\n            "name": "自定义指标上报管理",\n            "resource_type": "space"\n        },\n        "manage_dashboard": {\n            "description": "",\n            "extensions": {\n                "exclude_providers": [\n                    "v4"\n                ],\n                "v3": {\n                    "action_id": "manage_dashboard_v2",\n                    "name_en": "Manage Dashboard",\n                    "related_actions": [\n                        "view_business_v2",\n                        "view_dashboard_v2"\n                    ],\n                    "type": "manage",\n                    "version": 1\n                }\n            },\n            "id": "manage_dashboard",\n            "name": "仪表盘管理",\n            "resource_type": "space"\n        },\n        "manage_datasource": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "manage_datasource_v2",\n                    "name_en": "Manage DataSource",\n                    "related_actions": [\n                        "view_business_v2",\n                        "view_single_dashboard",\n                        "edit_single_dashboard"\n                    ],\n                    "type": "manage",\n                    "version": 1\n                }\n            },\n            "id": "manage_datasource",\n            "name": "仪表盘配置管理",\n            "resource_type": "space"\n        },\n        "manage_downtime": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "manage_downtime_v2",\n                    "name_en": "Manage Downtime",\n                    "related_actions": [\n                        "view_business_v2",\n                        "view_notify_team_v2",\n                        "view_rule_v2"\n                    ],\n                    "type": "manage",\n                    "version": 1\n                }\n            },\n            "id": "manage_downtime",\n            "name": "屏蔽管理",\n            "resource_type": "space"\n        },\n        "manage_event": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "manage_event_v2",\n                    "name_en": "Manage Event",\n                    "related_actions": [\n                        "view_event_v2"\n                    ],\n                    "type": "manage",\n                    "version": 1\n                }\n            },\n            "id": "manage_event",\n            "name": "事件中心管理",\n            "resource_type": "space"\n        },\n        "manage_global_setting": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "manage_global_setting",\n                    "name_en": "Manage Global Setting",\n                    "related_actions": [],\n                    "type": "manage",\n                    "version": 1\n                }\n            },\n            "id": "manage_global_setting",\n            "name": "全局配置编辑",\n            "resource_type": ""\n        },\n        "manage_host": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "manage_host_v2",\n                    "name_en": "Manage Host",\n                    "related_actions": [\n                        "view_business_v2",\n                        "view_host_v2"\n                    ],\n                    "type": "manage",\n                    "version": 1\n                }\n            },\n            "id": "manage_host",\n            "name": "主机详情管理",\n            "resource_type": "space"\n        },\n        "manage_incident": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "manage_incident",\n                    "name_en": "Manage Incident",\n                    "related_actions": [\n                        "view_incident"\n                    ],\n                    "type": "manage",\n                    "version": 1\n                }\n            },\n            "id": "manage_incident",\n            "name": "故障管理",\n            "resource_type": "space"\n        },\n        "manage_notify_team": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "manage_notify_team_v2",\n                    "name_en": "Manage Notify Team",\n                    "related_actions": [\n                        "view_business_v2",\n                        "view_notify_team_v2"\n                    ],\n                    "type": "manage",\n                    "version": 1\n                }\n            },\n            "id": "manage_notify_team",\n            "name": "告警组管理",\n            "resource_type": "space"\n        },\n        "manage_plugin": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "manage_plugin_v2",\n                    "name_en": "Manage Metric Plugin",\n                    "related_actions": [\n                        "view_plugin_v2"\n                    ],\n                    "type": "manage",\n                    "version": 1\n                }\n            },\n            "id": "manage_plugin",\n            "name": "指标插件管理",\n            "resource_type": "space"\n        },\n        "manage_public_action_config": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "manage_public_action_config",\n                    "name_en": "Manage Public Action Config",\n                    "related_actions": [],\n                    "type": "manage",\n                    "version": 1\n                }\n            },\n            "id": "manage_public_action_config",\n            "name": "公共套餐管理",\n            "resource_type": ""\n        },\n        "manage_public_plugin": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "manage_public_plugin",\n                    "name_en": "Manage Public Plugin",\n                    "related_actions": [],\n                    "type": "manage",\n                    "version": 1\n                }\n            },\n            "id": "manage_public_plugin",\n            "name": "公共插件管理",\n            "resource_type": ""\n        },\n        "manage_public_synthetic_location": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "manage_public_synthetic_location",\n                    "name_en": "Manage Public Synthetic Location",\n                    "related_actions": [\n                        "view_synthetic_v2"\n                    ],\n                    "type": "manage",\n                    "version": 1\n                }\n            },\n            "id": "manage_public_synthetic_location",\n            "name": "拨测公共节点管理",\n            "resource_type": ""\n        },\n        "manage_report": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "manage_report",\n                    "name_en": "Report Manage",\n                    "related_actions": [\n                        "view_business_v2"\n                    ],\n                    "type": "manage",\n                    "version": 1\n                }\n            },\n            "id": "manage_report",\n            "name": "订阅管理",\n            "resource_type": "space"\n        },\n        "manage_rule": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "manage_rule_v2",\n                    "name_en": "Manage Rule",\n                    "related_actions": [\n                        "view_business_v2",\n                        "view_rule_v2",\n                        "view_notify_team_v2"\n                    ],\n                    "type": "manage",\n                    "version": 1\n                }\n            },\n            "id": "manage_rule",\n            "name": "策略管理",\n            "resource_type": "space"\n        },\n        "manage_rum_application": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "manage_rum_application_v2",\n                    "name_en": "RUM Application Manage",\n                    "related_actions": [],\n                    "type": "manage",\n                    "version": 1\n                }\n            },\n            "id": "manage_rum_application",\n            "name": "RUM应用管理",\n            "resource_type": "rum_application"\n        },\n        "manage_synthetic": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "manage_synthetic_v2",\n                    "name_en": "Manage Synthetic",\n                    "related_actions": [\n                        "view_synthetic_v2"\n                    ],\n                    "type": "manage",\n                    "version": 1\n                }\n            },\n            "id": "manage_synthetic",\n            "name": "拨测管理",\n            "resource_type": "space"\n        },\n        "new_dashboard": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "new_dashboard",\n                    "name_en": "New Dashboard",\n                    "related_actions": [\n                        "view_business_v2",\n                        "view_single_dashboard",\n                        "edit_single_dashboard"\n                    ],\n                    "type": "manage",\n                    "version": 1\n                }\n            },\n            "id": "new_dashboard",\n            "name": "新建仪表盘",\n            "resource_type": "space"\n        },\n        "use_public_synthetic_location": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "use_public_synthetic_location",\n                    "name_en": "Use Public Synthetic Location",\n                    "related_actions": [\n                        "view_synthetic_v2"\n                    ],\n                    "type": "view",\n                    "version": 1\n                }\n            },\n            "id": "use_public_synthetic_location",\n            "name": "拨测公共节点使用",\n            "resource_type": ""\n        },\n        "using_alarm_handling_mcp": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "using_alarm_handling_mcp",\n                    "name_en": "Using Alarm Handling MCP",\n                    "related_actions": [\n                        "using_alarm_mcp"\n                    ],\n                    "type": "manage",\n                    "version": 1\n                }\n            },\n            "id": "using_alarm_handling_mcp",\n            "name": "使用告警处置MCP",\n            "resource_type": "space"\n        },\n        "using_alarm_mcp": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "using_alarm_mcp",\n                    "name_en": "Using Alarm Query MCP",\n                    "related_actions": [\n                        "view_business_v2"\n                    ],\n                    "type": "view",\n                    "version": 1\n                }\n            },\n            "id": "using_alarm_mcp",\n            "name": "使用告警查询MCP",\n            "resource_type": "space"\n        },\n        "using_apm_mcp": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "using_apm_mcp",\n                    "name_en": "Using APM MCP",\n                    "related_actions": [\n                        "view_business_v2"\n                    ],\n                    "type": "view",\n                    "version": 1\n                }\n            },\n            "id": "using_apm_mcp",\n            "name": "使用APM MCP",\n            "resource_type": "space"\n        },\n        "using_dashboard_mcp": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "using_dashboard_mcp",\n                    "name_en": "Using Dashboard MCP",\n                    "related_actions": [\n                        "view_business_v2"\n                    ],\n                    "type": "view",\n                    "version": 1\n                }\n            },\n            "id": "using_dashboard_mcp",\n            "name": "使用仪表盘MCP",\n            "resource_type": "space"\n        },\n        "using_log_mcp": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "using_log_mcp",\n                    "name_en": "Using Log MCP",\n                    "related_actions": [\n                        "view_business_v2"\n                    ],\n                    "type": "view",\n                    "version": 1\n                }\n            },\n            "id": "using_log_mcp",\n            "name": "使用日志MCP",\n            "resource_type": "space"\n        },\n        "using_metadata_mcp": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "using_metadata_mcp",\n                    "name_en": "Using Metadata MCP",\n                    "related_actions": [\n                        "view_business_v2"\n                    ],\n                    "type": "view",\n                    "version": 1\n                }\n            },\n            "id": "using_metadata_mcp",\n            "name": "使用元数据MCP",\n            "resource_type": "space"\n        },\n        "using_metrics_mcp": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "using_metrics_mcp",\n                    "name_en": "Using Metrics MCP",\n                    "related_actions": [\n                        "view_business_v2"\n                    ],\n                    "type": "view",\n                    "version": 1\n                }\n            },\n            "id": "using_metrics_mcp",\n            "name": "使用指标MCP",\n            "resource_type": "space"\n        },\n        "using_operation_mcp": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "using_operation_mcp",\n                    "name_en": "Using Operation MCP",\n                    "related_actions": [\n                        "view_business_v2"\n                    ],\n                    "type": "view",\n                    "version": 1\n                }\n            },\n            "id": "using_operation_mcp",\n            "name": "使用运营数据MCP",\n            "resource_type": "space"\n        },\n        "view_apm_application": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "view_apm_application_v2",\n                    "name_en": "APM Application View",\n                    "related_actions": [\n                        "view_business_v2"\n                    ],\n                    "type": "view",\n                    "version": 1\n                }\n            },\n            "id": "view_apm_application",\n            "name": "APM应用查看",\n            "resource_type": "apm_application"\n        },\n        "view_business": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "view_business_v2",\n                    "name_en": "View Business",\n                    "related_actions": [],\n                    "type": "view",\n                    "version": 1\n                }\n            },\n            "id": "view_business",\n            "name": "业务访问",\n            "resource_type": "space"\n        },\n        "view_collection": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "view_collection_v2",\n                    "name_en": "View Collection",\n                    "related_actions": [\n                        "view_business_v2"\n                    ],\n                    "type": "view",\n                    "version": 1\n                }\n            },\n            "id": "view_collection",\n            "name": "采集查看",\n            "resource_type": "space"\n        },\n        "view_custom_event": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "view_custom_event_v2",\n                    "name_en": "View Custom Event",\n                    "related_actions": [\n                        "view_business_v2"\n                    ],\n                    "type": "view",\n                    "version": 1\n                }\n            },\n            "id": "view_custom_event",\n            "name": "自定义事件上报查看",\n            "resource_type": "space"\n        },\n        "view_custom_metric": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "view_custom_metric_v2",\n                    "name_en": "View Custom Metric",\n                    "related_actions": [\n                        "view_business_v2"\n                    ],\n                    "type": "view",\n                    "version": 1\n                }\n            },\n            "id": "view_custom_metric",\n            "name": "自定义指标上报查看",\n            "resource_type": "space"\n        },\n        "view_dashboard": {\n            "description": "",\n            "extensions": {\n                "exclude_providers": [\n                    "v4"\n                ],\n                "v3": {\n                    "action_id": "view_dashboard_v2",\n                    "name_en": "View Dashboard",\n                    "related_actions": [\n                        "view_business_v2"\n                    ],\n                    "type": "view",\n                    "version": 1\n                }\n            },\n            "id": "view_dashboard",\n            "name": "仪表盘查看",\n            "resource_type": "space"\n        },\n        "view_downtime": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "view_downtime_v2",\n                    "name_en": "View Downtime",\n                    "related_actions": [\n                        "view_business_v2"\n                    ],\n                    "type": "view",\n                    "version": 1\n                }\n            },\n            "id": "view_downtime",\n            "name": "屏蔽查看",\n            "resource_type": "space"\n        },\n        "view_event": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "view_event_v2",\n                    "name_en": "View Event",\n                    "related_actions": [\n                        "view_business_v2"\n                    ],\n                    "type": "view",\n                    "version": 1\n                }\n            },\n            "id": "view_event",\n            "name": "事件中心查看",\n            "resource_type": "space"\n        },\n        "view_global_setting": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "view_global_setting",\n                    "name_en": "View Global Setting",\n                    "related_actions": [],\n                    "type": "view",\n                    "version": 1\n                }\n            },\n            "id": "view_global_setting",\n            "name": "全局配置查看",\n            "resource_type": ""\n        },\n        "view_host": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "view_host_v2",\n                    "name_en": "View Host",\n                    "related_actions": [\n                        "view_business_v2"\n                    ],\n                    "type": "view",\n                    "version": 1\n                }\n            },\n            "id": "view_host",\n            "name": "主机详情查看",\n            "resource_type": "space"\n        },\n        "view_incident": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "view_incident",\n                    "name_en": "View Incident",\n                    "related_actions": [\n                        "view_business_v2"\n                    ],\n                    "type": "view",\n                    "version": 1\n                }\n            },\n            "id": "view_incident",\n            "name": "故障查看",\n            "resource_type": "space"\n        },\n        "view_notify_team": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "view_notify_team_v2",\n                    "name_en": "View Notify Team",\n                    "related_actions": [\n                        "view_business_v2"\n                    ],\n                    "type": "view",\n                    "version": 1\n                }\n            },\n            "id": "view_notify_team",\n            "name": "告警组查看",\n            "resource_type": "space"\n        },\n        "view_plugin": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "view_plugin_v2",\n                    "name_en": "View Metric Plugin",\n                    "related_actions": [\n                        "view_business_v2"\n                    ],\n                    "type": "view",\n                    "version": 1\n                }\n            },\n            "id": "view_plugin",\n            "name": "指标插件查看",\n            "resource_type": "space"\n        },\n        "view_rule": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "view_rule_v2",\n                    "name_en": "View Rule",\n                    "related_actions": [\n                        "view_business_v2",\n                        "view_notify_team_v2",\n                        "view_notify_team_v2"\n                    ],\n                    "type": "view",\n                    "version": 1\n                }\n            },\n            "id": "view_rule",\n            "name": "策略查看",\n            "resource_type": "space"\n        },\n        "view_rum_application": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "view_rum_application_v2",\n                    "name_en": "RUM Application View",\n                    "related_actions": [\n                        "view_business_v2"\n                    ],\n                    "type": "view",\n                    "version": 1\n                }\n            },\n            "id": "view_rum_application",\n            "name": "RUM应用查看",\n            "resource_type": "rum_application"\n        },\n        "view_self_state": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "view_self_state",\n                    "name_en": "View Self-state",\n                    "related_actions": [],\n                    "type": "view",\n                    "version": 1\n                }\n            },\n            "id": "view_self_state",\n            "name": "自监控查看",\n            "resource_type": ""\n        },\n        "view_single_dashboard": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "view_single_dashboard",\n                    "name_en": "View Single Dashboard",\n                    "related_actions": [\n                        "view_business_v2"\n                    ],\n                    "type": "view",\n                    "version": 1\n                }\n            },\n            "id": "view_single_dashboard",\n            "name": "仪表盘实例查看",\n            "resource_type": "grafana_dashboard"\n        },\n        "view_synthetic": {\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "action_id": "view_synthetic_v2",\n                    "name_en": "View Synthetic",\n                    "related_actions": [\n                        "view_business_v2"\n                    ],\n                    "type": "view",\n                    "version": 1\n                }\n            },\n            "id": "view_synthetic",\n            "name": "拨测查看",\n            "resource_type": "space"\n        }\n    },\n    "resource_types": {\n        "apm_application": {\n            "ancestor": "space",\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "name_en": "APM Application",\n                    "related_instance_selections": [\n                        {\n                            "id": "apm_application_list_v2",\n                            "system_id": "bk_monitorv3"\n                        }\n                    ],\n                    "selection_mode": "instance",\n                    "system_id": "bk_monitorv3"\n                }\n            },\n            "id": "apm_application",\n            "name": "APM应用"\n        },\n        "grafana_dashboard": {\n            "ancestor": "space",\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "name_en": "Grafana Dashboard",\n                    "related_instance_selections": [\n                        {\n                            "id": "grafana_dashboard_list",\n                            "system_id": "bk_monitorv3"\n                        }\n                    ],\n                    "selection_mode": "instance",\n                    "system_id": "bk_monitorv3"\n                }\n            },\n            "id": "grafana_dashboard",\n            "name": "Grafana仪表盘"\n        },\n        "rum_application": {\n            "ancestor": "space",\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "name_en": "RUM Application",\n                    "related_instance_selections": [\n                        {\n                            "id": "rum_application_list_v2",\n                            "system_id": "bk_monitorv3"\n                        }\n                    ],\n                    "selection_mode": "instance",\n                    "system_id": "bk_monitorv3"\n                }\n            },\n            "id": "rum_application",\n            "name": "RUM应用"\n        },\n        "space": {\n            "ancestor": "",\n            "description": "",\n            "extensions": {\n                "v3": {\n                    "name_en": "Space",\n                    "related_instance_selections": [\n                        {\n                            "id": "space_list",\n                            "system_id": "bk_monitorv3"\n                        }\n                    ],\n                    "selection_mode": "instance",\n                    "system_id": "bk_monitorv3"\n                }\n            },\n            "id": "space",\n            "name": "空间"\n        }\n    },\n    "roles": {\n        "space_admin": {\n            "actions": [\n                {\n                    "action_id": "view_business",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "explore_metric",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "view_synthetic",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "view_host",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "view_event",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "view_plugin",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "view_collection",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "view_notify_team",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "view_rule",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "view_downtime",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "view_custom_metric",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "view_custom_event",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "view_incident",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "export_config",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "using_dashboard_mcp",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "using_metrics_mcp",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "using_log_mcp",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "using_metadata_mcp",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "using_alarm_mcp",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "using_apm_mcp",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "using_operation_mcp",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "view_apm_application",\n                    "resource_type": "apm_application"\n                },\n                {\n                    "action_id": "view_single_dashboard",\n                    "resource_type": "grafana_dashboard"\n                },\n                {\n                    "action_id": "view_rum_application",\n                    "resource_type": "rum_application"\n                },\n                {\n                    "action_id": "manage_synthetic",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "manage_host",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "manage_event",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "manage_plugin",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "manage_collection",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "manage_notify_team",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "manage_rule",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "manage_downtime",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "manage_custom_metric",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "manage_custom_event",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "manage_datasource",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "new_dashboard",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "import_config",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "manage_incident",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "manage_report",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "using_alarm_handling_mcp",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "manage_apm_application",\n                    "resource_type": "apm_application"\n                },\n                {\n                    "action_id": "edit_single_dashboard",\n                    "resource_type": "grafana_dashboard"\n                },\n                {\n                    "action_id": "manage_rum_application",\n                    "resource_type": "rum_application"\n                },\n                {\n                    "action_id": "view_global_setting",\n                    "resource_type": ""\n                },\n                {\n                    "action_id": "manage_global_setting",\n                    "resource_type": ""\n                },\n                {\n                    "action_id": "view_self_state",\n                    "resource_type": ""\n                },\n                {\n                    "action_id": "manage_public_plugin",\n                    "resource_type": ""\n                },\n                {\n                    "action_id": "manage_public_action_config",\n                    "resource_type": ""\n                },\n                {\n                    "action_id": "manage_public_synthetic_location",\n                    "resource_type": ""\n                },\n                {\n                    "action_id": "use_public_synthetic_location",\n                    "resource_type": ""\n                },\n                {\n                    "action_id": "manage_calendar",\n                    "resource_type": ""\n                }\n            ],\n            "description": "",\n            "extensions": {},\n            "id": "space_admin",\n            "name": "业务管理"\n        },\n        "space_operator": {\n            "actions": [\n                {\n                    "action_id": "view_business",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "explore_metric",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "view_synthetic",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "view_host",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "view_event",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "view_plugin",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "view_collection",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "view_notify_team",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "view_rule",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "view_downtime",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "view_custom_metric",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "view_custom_event",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "view_incident",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "export_config",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "using_dashboard_mcp",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "using_metrics_mcp",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "using_log_mcp",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "using_metadata_mcp",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "using_alarm_mcp",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "using_apm_mcp",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "using_operation_mcp",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "view_apm_application",\n                    "resource_type": "apm_application"\n                },\n                {\n                    "action_id": "view_single_dashboard",\n                    "resource_type": "grafana_dashboard"\n                },\n                {\n                    "action_id": "view_rum_application",\n                    "resource_type": "rum_application"\n                },\n                {\n                    "action_id": "manage_synthetic",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "manage_host",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "manage_event",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "manage_plugin",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "manage_collection",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "manage_notify_team",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "manage_rule",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "manage_downtime",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "manage_custom_metric",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "manage_custom_event",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "manage_datasource",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "new_dashboard",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "import_config",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "manage_incident",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "manage_report",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "using_alarm_handling_mcp",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "manage_apm_application",\n                    "resource_type": "apm_application"\n                },\n                {\n                    "action_id": "edit_single_dashboard",\n                    "resource_type": "grafana_dashboard"\n                },\n                {\n                    "action_id": "manage_rum_application",\n                    "resource_type": "rum_application"\n                }\n            ],\n            "description": "",\n            "extensions": {},\n            "id": "space_operator",\n            "name": "业务运维"\n        },\n        "space_viewer": {\n            "actions": [\n                {\n                    "action_id": "view_business",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "explore_metric",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "view_synthetic",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "view_host",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "view_event",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "view_plugin",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "view_collection",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "view_notify_team",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "view_rule",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "view_downtime",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "view_custom_metric",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "view_custom_event",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "view_incident",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "export_config",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "using_dashboard_mcp",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "using_metrics_mcp",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "using_log_mcp",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "using_metadata_mcp",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "using_alarm_mcp",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "using_apm_mcp",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "using_operation_mcp",\n                    "resource_type": "space"\n                },\n                {\n                    "action_id": "view_apm_application",\n                    "resource_type": "apm_application"\n                },\n                {\n                    "action_id": "view_single_dashboard",\n                    "resource_type": "grafana_dashboard"\n                },\n                {\n                    "action_id": "view_rum_application",\n                    "resource_type": "rum_application"\n                }\n            ],\n            "description": "",\n            "extensions": {},\n            "id": "space_viewer",\n            "name": "业务查看"\n        }\n    }\n}'
)
