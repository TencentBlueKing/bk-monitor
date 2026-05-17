"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import dataclasses
import os
from typing import Any

from bk_monitor_base.domains.metric_plugin.constants import PluginType
from django.utils.translation import gettext as _

from bkmonitor.commons.tools import is_ipv6_biz
from bkmonitor.models import MetricListCache
from bkmonitor.utils.request import get_request_tenant_id
from constants.cmdb import TargetNodeType, TargetObjectType
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import api
from monitor_web.models import CollectConfigMeta
from monitor_web.models.scene_view import SceneViewModel
from monitor_web.plugin.compat import convert_plugin_type_to_legacy
from monitor_web.scene_view.builtin import BuiltinProcessor
from monitor_web.scene_view.builtin.utils import get_variable_filter_dict, sort_panels

_USE_BASE_PLUGIN = os.getenv("ENABLE_BK_MONITOR_BASE_PLUGIN", "false").lower() == "true"


# ---------------------------------------------------------------------------
# 适配层：统一新旧模式的插件查询与 result_table_id 生成
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class _PluginInfo:
    """下游函数所需的最小插件信息集合，屏蔽新旧模型差异。"""

    plugin_id: str
    plugin_type: str
    bk_biz_id: int
    metric_json: list[dict[str, Any]] = dataclasses.field(default_factory=list)


def _get_result_table_id(plugin_type: str, plugin_id: str, table_name: str, bk_biz_id: int = 0) -> str:
    """根据插件信息生成结果表 ID。

    从 ``PluginVersionHistory.get_result_table_id`` 提取的纯命名规则逻辑，
    不依赖 ORM 模型实例，新旧模式共用。

    Args:
        plugin_type: 插件类型，新旧模式大小写可能不同，内部统一用 ``.lower()`` 比较，
            但 LOG / SNMP_TRAP 查询事件分组时需转换为统一兼容前缀。
        plugin_id: 插件 ID。
        table_name: 指标组表名。
        bk_biz_id: 业务 ID，仅 LOG / SNMP_TRAP 类型需要。

    Returns:
        结果表 ID 字符串。
    """
    pt = plugin_type.lower()
    if pt in (PluginType.LOG, PluginType.SNMP_TRAP):
        name = f"{convert_plugin_type_to_legacy(pt)}_{plugin_id}"
        event_groups = api.metadata.query_event_group.request.refresh(
            bk_biz_id=bk_biz_id,
            event_group_name=name,
        )
        if not event_groups:
            raise ValueError(f"event group not found: {name}")
        return event_groups[0]["table_id"]
    db_name = f"{pt}_{plugin_id}"
    if pt == PluginType.PROCESS:
        db_name = "process"
    return f"{db_name}.{table_name}"


def _get_plugin_info_old(bk_tenant_id: str, plugin_id: str, bk_biz_id: int) -> _PluginInfo:
    """旧模式：从 ``CollectorPluginMeta`` 查询插件信息。

    PROCESS 类型的 metric_json 通过 ``PluginManagerFactory.gen_metric_info()`` 生成，
    其余类型从 ``plugin.current_version.info.metric_json`` 获取。

    Args:
        bk_tenant_id: 租户 ID。
        plugin_id: 插件 ID。
        bk_biz_id: 业务 ID，用于限定查询范围。

    Returns:
        填充完毕的 ``_PluginInfo`` 实例。
    """
    from monitor_web.models import CollectorPluginMeta
    from monitor_web.plugin.manager import PluginManagerFactory

    plugin = CollectorPluginMeta.objects.get(
        bk_tenant_id=bk_tenant_id, plugin_id=plugin_id, bk_biz_id__in=[0, bk_biz_id]
    )
    if plugin.plugin_type.lower() == PluginType.PROCESS:
        metric_json = PluginManagerFactory.get_manager(
            bk_tenant_id=bk_tenant_id, plugin=plugin.plugin_id, plugin_type=plugin.plugin_type
        ).gen_metric_info()
    else:
        metric_json = plugin.current_version.info.metric_json
    return _PluginInfo(
        plugin_id=plugin.plugin_id,
        plugin_type=plugin.plugin_type,
        bk_biz_id=plugin.bk_biz_id,
        metric_json=metric_json,
    )


def _get_plugin_info_new(bk_tenant_id: str, plugin_id: str, bk_biz_id: int) -> _PluginInfo:
    """新模式：从 bk-monitor-base 领域 API 查询插件信息。

    PROCESS 类型的 metric_json 通过 ``ProcessPluginManager.get_metric_info()`` 生成，
    其余类型从 ``MetricPlugin.metrics`` 获取。两者都经过
    ``convert_metric_json_to_legacy`` 转换为旧格式，保证下游消费逻辑不变。

    Args:
        bk_tenant_id: 租户 ID。
        plugin_id: 插件 ID。
        bk_biz_id: 业务 ID（新模式下仅用于填充返回值）。

    Returns:
        填充完毕的 ``_PluginInfo`` 实例。
    """
    from bk_monitor_base.domains.metric_plugin.manager.node_man.process import ProcessPluginManager
    from bk_monitor_base.metric_plugin import get_metric_plugin

    from monitor_web.plugin.compat import convert_metric_json_to_legacy

    plugin = get_metric_plugin(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id)
    if plugin.type == PluginType.PROCESS:
        metric_json = convert_metric_json_to_legacy(ProcessPluginManager.get_metric_info())
    else:
        metric_json = convert_metric_json_to_legacy(plugin.metrics)
    return _PluginInfo(
        plugin_id=plugin.id,
        plugin_type=plugin.type,
        bk_biz_id=plugin.bk_biz_id,
        metric_json=metric_json,
    )


def _get_plugin_info(bk_tenant_id: str, plugin_id: str, bk_biz_id: int) -> _PluginInfo:
    """按 ``ENABLE_BK_MONITOR_BASE_PLUGIN`` 开关分派到新旧模式查询插件信息。

    Args:
        bk_tenant_id: 租户 ID。
        plugin_id: 插件 ID。
        bk_biz_id: 业务 ID。

    Returns:
        ``_PluginInfo`` 实例，包含 plugin_id、plugin_type、bk_biz_id、metric_json。
    """
    if _USE_BASE_PLUGIN:
        return _get_plugin_info_new(bk_tenant_id, plugin_id, bk_biz_id)
    return _get_plugin_info_old(bk_tenant_id, plugin_id, bk_biz_id)


# ---------------------------------------------------------------------------
# 业务函数
# ---------------------------------------------------------------------------


def _resolve_scene_context(scene_id: str, bk_biz_id: int) -> tuple[_PluginInfo, CollectConfigMeta | None]:
    """根据 scene_id 前缀解析出插件信息和可选的采集配置。

    ``collect_`` 前缀：通过采集配置 ID 查 ``CollectConfigMeta``，再用其 ``plugin_id``
    查插件信息。

    ``plugin_`` 前缀：直接用 plugin_id 查插件信息，同时尝试查找关联的采集配置。

    Args:
        scene_id: 场景视图 ID，格式为 ``collect_<id>`` 或 ``plugin_<plugin_id>``。
        bk_biz_id: 业务 ID。

    Returns:
        ``(_PluginInfo, CollectConfigMeta | None)`` 二元组。``collect_`` 场景下
        ``CollectConfigMeta`` 一定存在；``plugin_`` 场景下可能为 ``None``。
    """
    bk_tenant_id = get_request_tenant_id()
    if scene_id.startswith("collect_"):
        collect_config_id = int(scene_id.removeprefix("collect_"))
        collect_config = CollectConfigMeta.objects.get(bk_biz_id=bk_biz_id, id=collect_config_id)
        plugin_info = _get_plugin_info(bk_tenant_id, collect_config.plugin_id, bk_biz_id)
        return plugin_info, collect_config
    else:
        plugin_id = scene_id.split("plugin_", 1)[-1]
        plugin_info = _get_plugin_info(bk_tenant_id, plugin_id, bk_biz_id)
        collect_config = CollectConfigMeta.objects.filter(plugin_id=plugin_id, bk_biz_id=bk_biz_id).first()
        return plugin_info, collect_config


def get_order_config(view: SceneViewModel) -> list:
    """获取排序配置。"""
    if view and view.order:
        return view.order

    plugin_info, _ = _resolve_scene_context(view.scene_id, view.bk_biz_id)

    if plugin_info.plugin_type.lower() in (PluginType.LOG, PluginType.SNMP_TRAP):
        return []

    order = []
    group_list = api.metadata.query_time_series_group(
        time_series_group_name=f"{plugin_info.plugin_type}_{plugin_info.plugin_id}"
    )
    for table in plugin_info.metric_json:
        table_name = table["table_name"] if not group_list else "__default__"
        table_id = _get_result_table_id(
            plugin_info.plugin_type, plugin_info.plugin_id, table_name, plugin_info.bk_biz_id
        ).lower()
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
    """获取指标信息，包含指标信息及该指标需要使用的聚合方法、聚合维度、聚合周期等。"""
    bk_tenant_id = get_request_tenant_id()
    plugin_info, collect_config = _resolve_scene_context(view.scene_id, view.bk_biz_id)

    if not collect_config:
        return []

    variable_filters = get_variable_filter_dict(view.variables)

    panels = []
    if plugin_info.plugin_type.lower() == PluginType.PROCESS:
        metric_json = plugin_info.metric_json
    else:
        metric_json = collect_config.deployment_config.metrics
    group_list = api.metadata.query_time_series_group(
        time_series_group_name=f"{plugin_info.plugin_type}_{plugin_info.plugin_id}"
    )

    for table in metric_json:
        table_name = table["table_name"] if not group_list else "__default__"
        table_id = _get_result_table_id(
            plugin_info.plugin_type, plugin_info.plugin_id, table_name, plugin_info.bk_biz_id
        ).lower()

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

            if plugin_info.plugin_type.lower() in (PluginType.LOG, PluginType.SNMP_TRAP):
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


def get_simple_panel_count(view: SceneViewModel) -> int:
    """
    获取简化场景下的图表数量。

    用于 SceneViewList 仅请求基础信息时，避免为计算 panel_count
    触发完整面板渲染和 MetricListCache 查询。

    仅支持 collect_* 和 plugin_* 场景的精确计数；其他场景类型（如
    custom_event_*、custom_metric_* 等）不展示 panel_count，直接返回 0。
    """
    from monitor_web.models import CollectorPluginMeta
    from monitor_web.plugin.manager import PluginManagerFactory

    bk_tenant_id = get_request_tenant_id()
    if view.scene_id.startswith("collect_"):
        collect_config_id = int(view.scene_id.lstrip("collect_"))
        collect_config = CollectConfigMeta.objects.get(bk_biz_id=view.bk_biz_id, id=collect_config_id)
        plugin = collect_config.plugin
    elif view.scene_id.startswith("plugin_"):
        plugin_id = view.scene_id.split("plugin_", 1)[-1]
        plugin = CollectorPluginMeta.objects.get(
            bk_tenant_id=bk_tenant_id, plugin_id=plugin_id, bk_biz_id__in=[0, view.bk_biz_id]
        )
        collect_config = CollectConfigMeta.objects.filter(plugin_id=plugin_id, bk_biz_id=view.bk_biz_id).first()
    else:
        return 0

    if not collect_config:
        return 0

    if plugin.plugin_type == CollectorPluginMeta.PluginType.PROCESS:
        metric_json = PluginManagerFactory.get_manager(
            bk_tenant_id=bk_tenant_id, plugin=plugin.plugin_id, plugin_type=plugin.plugin_type
        ).gen_metric_info()
    else:
        metric_json = collect_config.deployment_config.metrics

    return sum(
        1
        for table in metric_json
        for field in table["fields"]
        if field["is_active"] and field["monitor_type"] == "metric"
    )


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

        plugin_info, collect_config = _resolve_scene_context(scene_id, bk_biz_id)

        if scene_id.startswith("collect_"):
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
            plugin_id = plugin_info.plugin_id

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
        if plugin_info.plugin_type.lower() in (PluginType.LOG, PluginType.SNMP_TRAP):
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
    def get_view_config(cls, view: SceneViewModel, params: dict = None, *args, **kwargs) -> dict:
        params = params or {}
        default_config = cls.get_default_view_config(view.bk_biz_id, view.scene_id)

        if params.get("only_simple_info"):
            options = default_config["options"]
            options.update({key: value for key, value in view.options.items() if key in cls.OptionFields})
            return {
                "id": view.id,
                "name": view.name,
                "mode": default_config["mode"],
                "variables": view.variables,
                "order": [],
                "panels": [{"type": "graph"} for _ in range(get_simple_panel_count(view))],
                "list": [],
                "options": options,
            }

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
