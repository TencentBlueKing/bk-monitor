"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.utils.translation import gettext as _

from bkmonitor.commons.tools import is_ipv6_biz
from bkmonitor.models import MetricListCache
from bkmonitor.utils.request import get_request_tenant_id
from constants.cmdb import TargetNodeType, TargetObjectType
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import api
from monitor_web.models import (
    CollectConfigMeta,
    CollectorPluginMeta,
    PluginVersionHistory,
)
from monitor_web.models.scene_view import SceneViewModel
from monitor_web.plugin.constant import PluginType
from monitor_web.plugin.manager import PluginManagerFactory
from monitor_web.scene_view.builtin import BuiltinProcessor
from monitor_web.scene_view.builtin.utils import get_variable_filter_dict, sort_panels


def get_order_config(view: SceneViewModel) -> list:
    """
    获取排序配置
    """
    if view and view.order:
        return view.order

    if view.scene_id.startswith("collect_"):
        collect_config_id = int(view.scene_id.lstrip("collect_"))
        collect_config = CollectConfigMeta.objects.get(bk_biz_id=view.bk_biz_id, id=collect_config_id)
        plugin = collect_config.plugin
    else:
        plugin_id = view.scene_id.split("plugin_", 1)[-1]
        plugin = CollectorPluginMeta.objects.get(
            bk_tenant_id=get_request_tenant_id(), plugin_id=plugin_id, bk_biz_id__in=[0, view.bk_biz_id]
        )

    if plugin.plugin_type in [PluginType.LOG, PluginType.SNMP_TRAP]:
        return []

    order = []
    metric_json = plugin.current_version.info.metric_json
    group_list = api.metadata.query_time_series_group(time_series_group_name=f"{plugin.plugin_type}_{plugin.plugin_id}")
    for table in metric_json:
        table_name = table["table_name"] if not group_list else "__default__"
        table_id = plugin.current_version.get_result_table_id(plugin, table_name).lower()
        row = {
            "id": table["table_name"],
            "title": table["table_desc"],
            "panels": [],
            "hidden": False,
        }
        for field in table["fields"]:
            row["panels"].append(
                {
                    "id": f"{table_id}.{field['name']}",
                    "title": field["description"] or field["name"],
                    "hidden": False,
                }
            )
        if row["panels"]:
            order.append(row)
    return order


def get_panels(view: SceneViewModel) -> list[dict]:
    """
    获取指标信息，包含指标信息及该指标需要使用的聚合方法、聚合维度、聚合周期等
    """
    bk_tenant_id = get_request_tenant_id()
    if view.scene_id.startswith("collect_"):
        collect_config_id = int(view.scene_id.lstrip("collect_"))
        collect_config = CollectConfigMeta.objects.get(bk_biz_id=view.bk_biz_id, id=collect_config_id)
        plugin = collect_config.plugin
    else:
        plugin_id = view.scene_id.split("plugin_", 1)[-1]
        plugin = CollectorPluginMeta.objects.get(
            bk_tenant_id=bk_tenant_id, plugin_id=plugin_id, bk_biz_id__in=[0, view.bk_biz_id]
        )
        collect_config = CollectConfigMeta.objects.filter(plugin_id=plugin_id, bk_biz_id=view.bk_biz_id).first()

    if not collect_config:
        return []

    variable_filters = get_variable_filter_dict(view.variables)

    panels = []
    if plugin.plugin_type == CollectorPluginMeta.PluginType.PROCESS:
        metric_json = PluginManagerFactory.get_manager(
            bk_tenant_id=bk_tenant_id, plugin=plugin.plugin_id, plugin_type=plugin.plugin_type
        ).gen_metric_info()
    else:
        metric_json = collect_config.deployment_config.metrics
    # 如果插件id在time_series_group能查到，则可以认为是分表的，否则走原有逻辑
    group_list = api.metadata.query_time_series_group(time_series_group_name=f"{plugin.plugin_type}_{plugin.plugin_id}")

    for table in metric_json:
        # 分表模式下，这里table_id都为__default__
        table_name = table["table_name"] if not group_list else "__default__"
        table_id = PluginVersionHistory.get_result_table_id(plugin, table_name).lower()

        # 查询所有维度字段
        metric_cache: MetricListCache | None = MetricListCache.objects.filter(
            bk_tenant_id=bk_tenant_id,
            data_source_label=DataSourceLabel.BK_MONITOR_COLLECTOR,
            data_type_label=DataTypeLabel.TIME_SERIES,
            result_table_id=table_id,
        ).first()
        if metric_cache:
            dimensions = [dimension["id"] for dimension in metric_cache.dimensions]
            data_label = metric_cache.data_label
        else:
            dimensions = []
            data_label = table_id.split(".")[0]
            for metric in table["fields"]:
                if metric["monitor_type"] == "dimension":
                    dimensions.append(metric["name"])
                    continue

        for field in table["fields"]:
            if not field["is_active"]:
                continue
            if field["monitor_type"] != "metric":
                continue

            if plugin.plugin_type == PluginType.LOG or plugin.plugin_type == PluginType.SNMP_TRAP:
                panels.append(
                    {
                        "id": data_label or table_id,
                        "type": "event-log",
                        "title": field["description"] or field["name"],
                        "gridPos": {"x": 0, "y": 0, "w": 24, "h": 20},
                        "targets": [
                            {
                                "data": {
                                    "bk_biz_id": view.bk_biz_id,
                                    "expression": "A",
                                    "query_configs": [
                                        {
                                            "metrics": [{"field": "_index", "method": "COUNT", "alias": "A"}],
                                            "table": table_id,
                                            "data_label": data_label,
                                            "data_source_label": DataSourceLabel.BK_MONITOR_COLLECTOR,
                                            "data_type_label": DataTypeLabel.LOG,
                                            "interval": "$interval",
                                            "group_by": ["$group_by"],
                                            "where": [],
                                            "functions": [
                                                {"id": "time_shift", "params": [{"id": "n", "value": "$time_shift"}]}
                                            ],
                                            "filter_dict": {
                                                "targets": ["$current_target", "$compare_targets"],
                                                "variables": variable_filters,
                                            },
                                        }
                                    ],
                                },
                                "alias": "",
                                "datasource": "time_series",
                                "data_type": "time_series",
                                "api": "grafana.graphUnifyQuery",
                            },
                            {
                                "data": {
                                    "bk_biz_id": view.bk_biz_id,
                                    "result_table_id": table_id,
                                    "data_source_label": DataSourceLabel.BK_MONITOR_COLLECTOR,
                                    "data_type_label": DataTypeLabel.LOG,
                                    "filter_dict": {
                                        "targets": ["$current_target", "$compare_targets"],
                                        "variables": get_variable_filter_dict(view.variables),
                                        "dimensions": "$dimensions",
                                    },
                                },
                                "alias": "",
                                "datasource": "log",
                                "data_type": "table",
                                "api": "grafana.logQuery",
                            },
                        ],
                    }
                )
            else:
                panels.append(
                    {
                        "id": f"{data_label or table_id}.{field['name']}",
                        "type": "graph",
                        "title": field["description"] or field["name"],
                        "subTitle": f"{data_label or table_id}.{field['name']}",
                        "dimensions": dimensions,
                        "targets": [
                            {
                                "data": {
                                    "bk_biz_id": view.bk_biz_id,
                                    "expression": "A",
                                    "query_configs": [
                                        {
                                            "metrics": [{"field": field["name"], "method": "$method", "alias": "A"}],
                                            "interval": "$interval",
                                            "table": table_id,
                                            "data_label": data_label,
                                            "data_source_label": DataSourceLabel.BK_MONITOR_COLLECTOR,
                                            "data_type_label": DataTypeLabel.TIME_SERIES,
                                            "group_by": ["$group_by"],
                                            "where": [],
                                            "functions": [
                                                {"id": "time_shift", "params": [{"id": "n", "value": "$time_shift"}]}
                                            ],
                                            "filter_dict": {
                                                "targets": ["$current_target", "$compare_targets"],
                                                "bk_collect_config_id": [
                                                    str(collect_config.id)
                                                    if view.scene_id.startswith("collect_")
                                                    else "$bk_collect_config_id"
                                                ],
                                                "variables": variable_filters,
                                            },
                                        }
                                    ],
                                },
                                "alias": "",
                                "datasource": "time_series",
                                "data_type": "time_series",
                                "api": "grafana.graphUnifyQuery",
                            }
                        ],
                    }
                )
    return panels


class CollectBuiltinProcessor(BuiltinProcessor):
    OptionFields = ["show_panel_count"]

    @classmethod
    def get_auto_view_panels(cls, view: SceneViewModel) -> tuple[list[dict], list[dict]]:
        """
        获取平铺视图配置
        """
        panels = get_panels(view)
        if view.mode == "auto":
            panels, order = sort_panels(panels, get_order_config(view), hide_metric=False)
        else:
            return panels, []
        return panels, order

    @classmethod
    def get_default_view_config(cls, bk_biz_id: int, scene_id: str):
        # 根据IPv6开关决定聚合字段
        if is_ipv6_biz(bk_biz_id):
            host_fields = {"bk_host_id": "bk_host_id"}
        else:
            host_fields = {"ip": "bk_target_ip", "bk_cloud_id": "bk_target_cloud_id"}

        if scene_id.startswith("collect_"):
            # 采集配置场景视图
            collect_config_id = int(scene_id.lstrip("collect_"))
            collect_config = CollectConfigMeta.objects.get(bk_biz_id=bk_biz_id, id=collect_config_id)
            plugin = collect_config.plugin

            target_node_type = collect_config.deployment_config.target_node_type
            target_object_type = collect_config.target_object_type

            # 按下发类型生成选择器配置
            if target_node_type == TargetNodeType.INSTANCE:
                selector_data_source_params = {"dataType": "list", "fields": host_fields}
                selector_type = "target_list"
                options = {
                    "show_status_bar": True,
                    "show_overview": True,
                }
            else:
                selector_data_source_params = {
                    "dataType": "topo_tree",
                    "fields": host_fields
                    if target_object_type == TargetObjectType.HOST
                    else {"service_instance_id": "bk_target_service_instance_id"},
                }
                selector_type = "topo_tree"
                options = {
                    "can_check_node": True,
                    "show_status_bar": True,
                    "show_overview": True,
                    "status_mapping": [
                        {"id": "SUCCESS", "name": _("正常"), "color": "success"},
                        {"id": "FAILED", "name": _("失败"), "color": "warning"},
                        {"id": "NODATA", "name": _("无数据"), "color": "nodata"},
                    ],
                }
            selector_panel = {
                "title": _("对象列表"),
                "type": selector_type,
                "targets": [
                    {
                        "datasource": "topo_tree",
                        "api": "collecting.frontendTargetStatusTopo",
                        "data": {"id": collect_config.id, "bk_biz_id": bk_biz_id},
                        **selector_data_source_params,
                    }
                ],
                "options": {selector_type: options},
            }
        else:
            # 自定义场景视图
            plugin_id = scene_id.split("plugin_", 1)[-1]
            plugin = CollectorPluginMeta.objects.get(
                bk_tenant_id=get_request_tenant_id(), plugin_id=plugin_id, bk_biz_id__in=[0, bk_biz_id]
            )
            collect_config = CollectConfigMeta.objects.filter(plugin_id=plugin_id, bk_biz_id=bk_biz_id).first()

            selector_panel = {
                "title": _("对象列表"),
                "type": "topo_tree",
                "targets": [
                    {
                        "datasource": "topo_tree",
                        "api": "scene_view.getPluginTargetTopo",
                        "data": {"plugin_id": plugin_id},
                        "dataType": "topo_tree",
                        "fields": host_fields
                        if collect_config and collect_config.target_object_type == TargetObjectType.HOST
                        else {"service_instance_id": "bk_target_service_instance_id"},
                    }
                ],
                "options": {
                    "topo_tree": {
                        "can_check_node": False,
                        "show_status_bar": False,
                        "show_overview": True,
                    }
                },
            }

        # 按插件类型下发
        if plugin.plugin_type == PluginType.LOG or plugin.plugin_type == PluginType.SNMP_TRAP:
            mode = "custom"
            panel_tool = {
                "compare_select": False,
                "columns_toggle": False,
                "interval_select": True,
                "split_switcher": False,
            }
            enable_index_list = False
        else:
            mode = "auto"
            panel_tool = {
                "compare_select": True,
                "columns_toggle": True,
                "interval_select": True,
                "split_switcher": False,
                "method_select": True,
            }
            enable_index_list = True

        return {
            "id": "default",
            "type": "detail",
            "mode": mode,
            "name": _("默认"),
            "variables": [],
            "panels": [],
            "list": [],
            "order": [],
            "options": {
                "enable_index_list": enable_index_list,
                "panel_tool": panel_tool,
                "view_editable": True,
                "enable_group": True,
                "variable_editable": True,
                "alert_filterable": True,
                "selector_panel": selector_panel,
            },
        }

    @classmethod
    def create_default_views(cls, bk_biz_id: int, scene_id: str, view_type: str, existed_views):
        if existed_views:
            return

        view_config = cls.get_default_view_config(bk_biz_id, scene_id)
        SceneViewModel.objects.create(
            bk_biz_id=bk_biz_id,
            scene_id=scene_id,
            type=view_type,
            id=view_config["id"],
            name=view_config["name"],
            mode="auto",
            variables=view_config.get("variables", []),
            panels=[],
            list=[],
            order=[],
            options=view_config.get("options", {}),
        )

    @classmethod
    def create_or_update_view(
        cls, bk_biz_id: int, scene_id: str, view_type: str, view_id: str, view_config: dict
    ) -> SceneViewModel | None:
        if view_type == "overview":
            return

        view: SceneViewModel | None = SceneViewModel.objects.filter(
            bk_biz_id=bk_biz_id, scene_id=scene_id, type=view_type, id=view_id
        ).first()
        if view:
            view.name = view_config["name"]
            if "variables" in view_config:
                view.variables = view_config["variables"]
            if "options" in view_config:
                view.options = view_config["options"]
            if "order" in view_config:
                view.order = view_config["order"]
            view.save()
        else:
            view = SceneViewModel.objects.create(
                bk_biz_id=bk_biz_id,
                scene_id=scene_id,
                type=view_type,
                id=view_id,
                name=view_config["name"],
                mode="auto",
                order=view_config.get("order", []),
                panels=[],
                options=view_config.get("options", {}),
                list=[],
                variables=view_config.get("variables", []),
            )
        return view

    @classmethod
    def get_view_config(cls, view: SceneViewModel, *args, **kwargs) -> dict:
        default_config = cls.get_default_view_config(view.bk_biz_id, view.scene_id)
        panels, order = cls.get_auto_view_panels(view)

        # 如果插件视角的视图，则需要添加采集配置变量
        if view.scene_id.startswith("plugin_"):
            view.variables.insert(
                0,
                {
                    "id": 0,
                    "title": _("采集配置"),
                    "type": "list",
                    "targets": [
                        {
                            "datasource": "scene_view",
                            "dataType": "list",
                            "api": "scene_view.getPluginCollectConfigIdList",
                            "data": {"plugin_id": view.scene_id.split("plugin_", 1)[-1]},
                            "fields": {"id": "bk_collect_config_id"},
                        }
                    ],
                    "options": {"variables": {"multiple": True, "required": False, "internal": True}},
                },
            )

        options = default_config["options"]
        options.update({key: value for key, value in view.options.items() if key in cls.OptionFields})

        return {
            "id": view.id,
            "name": view.name,
            "mode": default_config["mode"],
            "variables": view.variables,
            "order": order,
            "panels": panels,
            "list": [],
            "options": options,
        }

    @classmethod
    def is_builtin_scene(cls, scene_id: str) -> bool:
        return scene_id.startswith("collect_") or scene_id.startswith("plugin_")
