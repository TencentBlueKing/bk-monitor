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
import copy
import json
from typing import Dict, List, Optional, Set

from django.core.exceptions import EmptyResultSet
from django.utils.translation import gettext as _

from bkmonitor.models import BCSNode, BCSPodMonitor, BCSServiceMonitor
from core.drf_resource import resource
from monitor_web.models.scene_view import SceneViewModel, SceneViewOrderModel
from monitor_web.scene_view.builtin import BuiltinProcessor
from monitor_web.scene_view.builtin.constants import (
    DEFAULT_CONTAINER_DETAIL,
    DEFAULT_GRAPH_PROMQL_QUERY_CONFIG,
    DEFAULT_GRAPH_UNIFY_QUERY_QUERY_CONFIG,
    DEFAULT_NODE_PANELS,
    DEFAULT_PANEL_GROUP_ID_PREFIX,
    DEFAULT_POD_DETAIL,
    DEFAULT_SERVICE_DETAIL,
    DEFAULT_WORKLOAD_DETAIL,
    GROUP_TITLE_MAP_KEY,
    VIEW_FILENAMES,
)


class KubernetesBuiltinProcessor(BuiltinProcessor):
    builtin_views = None

    @classmethod
    def load_builtin_views(cls):
        if cls.builtin_views is None:
            cls.builtin_views = {}
            view_filenames = VIEW_FILENAMES
            for filename in view_filenames:
                cls.builtin_views[filename] = cls._read_builtin_view_config(filename)

    @classmethod
    def create_default_kubernetes_order(cls, bk_biz_id: int, scene_id: str, view_type: str):
        SceneViewOrderModel.objects.update_or_create(
            bk_biz_id=bk_biz_id,
            scene_id=scene_id,
            type=view_type,
            defaults={
                "config": [
                    "cluster",
                    "event",
                    "workload",
                    "service",
                    "pod",
                    "container",
                    "node",
                    "service_monitor",
                    "pod_monitor",
                ]
            },
        )

    @classmethod
    def create_default_views(cls, bk_biz_id: int, scene_id: str, view_type: str, existed_view):
        cls.load_builtin_views()

        builtin_view_ids = {v.split("-")[-1] for v in cls.builtin_views if v.startswith("kubernetes-")}
        existed_view_ids: Set[str] = {v.id for v in existed_view}
        create_view_ids = builtin_view_ids - existed_view_ids

        new_views = []
        for view_id in create_view_ids:
            view_config = cls.builtin_views[f"kubernetes-{view_id}"]
            new_views.append(
                SceneViewModel(
                    bk_biz_id=bk_biz_id,
                    scene_id=scene_id,
                    type=view_type,
                    id=view_id,
                    name=view_config["name"],
                    mode=view_config["mode"],
                    variables=view_config.get("variables", []),
                    panels=view_config.get("panels", []),
                    list=view_config.get("list", []),
                    order=view_config.get("order", []),
                    options=view_config.get("options", {}),
                )
            )
        if new_views:
            SceneViewModel.objects.bulk_create(new_views)

        # 删除多余的视图
        delete_view_ids = existed_view_ids - builtin_view_ids
        if delete_view_ids:
            SceneViewModel.objects.filter(
                bk_biz_id=bk_biz_id, scene_id=scene_id, type=view_type, id__in=delete_view_ids
            ).delete()

        cls.create_default_kubernetes_order(bk_biz_id, scene_id, view_type)

    @classmethod
    def get_metric_prefixes(cls, view: SceneViewModel) -> List:
        """获得在指标缓存中需要检索的指标前缀 ."""
        metric_prefixes = []
        if view.id in ["container", "pod", "workload"]:
            metric_prefixes = ["container_", "kube_pod_"]
        elif view.id == "service":
            metric_prefixes = ["container_"]
        elif view.id == "node":
            metric_prefixes = ["node_"]
        return metric_prefixes

    @classmethod
    def get_available_metric_list(cls, view: SceneViewModel, metric_prefixes: str, default_detail_config: List) -> List:
        """获得可用的所有指标列表 ."""
        # 根据指标前缀在指标缓存表中查询匹配的指标
        metric_list = cls.get_metrics_list(view, metric_prefixes)
        metric_set = set(metric_list)
        # 获得需要默认展示的指标
        for group in default_detail_config:
            for panel in group["panels"]:
                metric_field = panel["id"].split(".").pop()
                if metric_field not in metric_set:
                    metric_list.append(metric_field)

        return metric_list

    @classmethod
    def get_order(cls, view: SceneViewModel, default_detail_config: List):
        view_id = cls.get_view_id(view)
        if view_id in ["kubernetes-service_monitor", "kubernetes-pod_monitor", "kubernetes-event"]:
            return []

        # 获得在指标缓存中需要检索的指标前缀
        metric_prefixes = cls.get_metric_prefixes(view)
        if not metric_prefixes:
            return []
        # 获得可用的所有指标列表
        metric_list = cls.get_available_metric_list(view, metric_prefixes, default_detail_config)

        # 从数据库获得保存的面板分组配置
        id_prefix = f"bk_monitor.time_series.k8s.{view.id}."
        order_groups = cls.get_order_groups(view, id_prefix)
        order_groups_map = {order_group["id"]: order_group for order_group in order_groups}

        # 获得所有的面板配置
        metric_field_existed = {panel["title"] for order_group in order_groups for panel in order_group["panels"]}

        # 补齐指标缓存中新增的指标面板
        for metric_field in sorted(list(set(metric_list) - set(metric_field_existed))):
            group_key = ""
            for metric_prefix in metric_prefixes:
                if metric_field.startswith(metric_prefix):
                    group_key = metric_field.replace(metric_prefix, "", 1).split("_")[0]
            if group_key not in GROUP_TITLE_MAP_KEY.values():
                group_key = "else"
            group_id = f"{id_prefix}{group_key}"
            order_group = order_groups_map.get(group_id)
            panel_id = f"{id_prefix}{metric_field}"
            # 在所有分组中查询指标是否存在
            if not cls.is_panel_in_order_groups(panel_id, group_id, order_groups_map):
                # 判断指标面板ID是否是默认的，如果是默认的面板则显示
                hidden = cls.get_order_item_hidden_by_default(order_group["id"], panel_id, default_detail_config)
                order_group["panels"].append(
                    {
                        "id": panel_id,
                        "title": metric_field,
                        "hidden": hidden,
                    }
                )

        return order_groups

    @classmethod
    def get_metrics_list(cls, view, metric_prefixes):
        """根据指标前缀从指标缓存中查询指标 ."""
        if not metric_prefixes:
            return []
        params = {
            "bk_biz_id": view.bk_biz_id,
            "data_source_label": ["bk_monitor"],
            "data_type_label": "time_series",
            "result_table_label": ["kubernetes"],
            "conditions": [{"key": "query", "value": metric_prefixes}],
            "tag": "",
        }
        metric_list_response = resource.strategies.get_metric_list_v2(params)
        metric_list = [
            item["metric_field"]
            for item in metric_list_response["metric_list"]
            if any([item["metric_field"].startswith(prefix) for prefix in metric_prefixes])
        ]
        return metric_list

    @classmethod
    def is_panel_in_order_groups(cls, panel_id, group_id, order_groups_map):
        """在所有分组中查询面板ID是否存在 ."""
        order_group = order_groups_map.get(group_id)
        if not order_group:
            return False
        for panel in order_group["panels"]:
            if panel["id"] == panel_id:
                return True
        return False

    @classmethod
    def get_order_groups(cls, view: SceneViewModel, id_prefix: str) -> List:
        """获得面板分组配置 ."""
        # 获得面板分组ID
        order_groups_map = {}
        default_group_id_list = []
        for group_title, group_key in GROUP_TITLE_MAP_KEY.items():
            group_id = f"{id_prefix}{group_key}"
            default_group_id_list.append(group_id)
            order_groups_map[group_id] = {
                "id": group_id,
                "title": group_title,
                "panels": [],
                "hidden": False,
            }

        # 如果数据库中保存过面板分组配置，则以数据库的顺序为准
        order_groups = []
        group_id_list = []
        for order_group in view.order:
            group_id = order_group['id']
            if not group_id.startswith(id_prefix):
                group_id = f"{id_prefix}{group_id}"
                order_group["id"] = group_id
            group_id_list.append(group_id)
            order_groups_map[group_id] = order_group
            order_groups.append(order_group)

        # 用户自定义的顺序优先级高，再加上默认分组
        for group_id in set(default_group_id_list) - set(group_id_list):
            order_groups.append(order_groups_map[group_id])

        return order_groups

    @classmethod
    def get_order_item_hidden_by_default(cls, group_key, panel_id, default_detail_config):
        """判断指标面板ID是否是默认的 ."""
        for group in default_detail_config:
            if group["id"] != group_key:
                continue
            for panel in group["panels"]:
                if panel["id"] == panel_id:
                    return False
        return True

    @classmethod
    def get_view_id(cls, view: SceneViewModel):
        view_id = f"kubernetes-{view.id}"
        return view_id

    @classmethod
    def add_event_panel(cls, view, view_config):
        view_id = view.id
        if view_id in [
            "pod",
            "workload",
            "service",
            "node",
        ]:
            data = {
                "result_table_id": "events",
                "data_source_label": "custom",
                "data_type_label": "event",
                "bcs_cluster_id": "$bcs_cluster_id",
            }
            if view_id == "pod":
                data["kind"] = "Pod"
                data["name"] = "$pod_name"
                data["namespace"] = "$namespace"
            elif view_id == "workload":
                data["kind"] = "$workload_type"
                data["name"] = "$workload_name"
                data["namespace"] = "$namespace"
            elif view_id == "service":
                data["kind"] = "Service"
                data["name"] = "$service_name"
                data["namespace"] = "$namespace"
            elif view_id == "node":
                data["kind"] = "Node"
                data["name"] = "$node_name"
            view_config["panels"].append(
                {
                    "id": "bk_monitor.time_series.k8s.events",
                    "title": _("事件"),
                    "type": "row",
                    "panels": [
                        {
                            "id": "events",
                            "title": "Events",
                            "type": "event-log",
                            "options": {
                                "dashboard_common": {
                                    "static_width": True,
                                }
                            },
                            "targets": [
                                {
                                    "datasource": "time_series",
                                    "data_type": "time_series",
                                    "api": "scene_view.getKubernetesEvents",
                                    "data": {"data_type": "chart", **data},
                                },
                                {
                                    "datasource": "event_list",
                                    "dataType": "table",
                                    "api": "scene_view.getKubernetesEvents",
                                    "data": data,
                                },
                            ],
                        }
                    ],
                    "hidden": False,
                }
            )

    @classmethod
    def get_view_config(cls, view: SceneViewModel, params: Dict = None, *args, **kwargs) -> Dict:
        cls.load_builtin_views()
        view_id = cls.get_view_id(view)
        view_config = json.loads(json.dumps(cls.builtin_views[view_id]))

        if view.id == "cluster":
            view_config = cls.get_cluster_view_config(view, view_config)
        elif view.id == "event":
            view_config = cls.get_event_view_config(view, view_config)
        elif view.id == "workload":
            view_config = cls.get_workload_view_config(view, view_config)
        if view.id == "pod":
            view_config = cls.get_pod_view_config(view, view_config)
        elif view.id == "container":
            view_config = cls.get_container_view_config(view, view_config)
        elif view.id == "service":
            view_config = cls.get_service_view_config(view, view_config)
        elif view.id == "node":
            view_config = cls.get_node_view_config(view, view_config)
        elif view.id == "service_monitor":
            view_config = cls.get_service_monitor_view_config(view, view_config)
        elif view.id == "pod_monitor":
            view_config = cls.get_pod_monitor_view_config(view, view_config)

        if view_config.get("panels"):
            view_config["panels"] = list(
                filter(
                    lambda panel_group: panel_group["type"] != "row" or len(panel_group.get("panels", [])) > 0,
                    view_config["panels"],
                )
            )
        if view_config.get("overview_panels"):
            view_config["overview_panels"] = list(
                filter(
                    lambda panel_group: panel_group["type"] != "row" or len(panel_group.get("panels", [])) > 0,
                    view_config["overview_panels"],
                )
            )
        return view_config

    @classmethod
    def get_cluster_view_config(cls, view: SceneViewModel, view_config: Dict):
        return view_config

    @classmethod
    def get_event_view_config(cls, view: SceneViewModel, view_config: Dict):
        return view_config

    @classmethod
    def get_pod_view_config(cls, view: SceneViewModel, view_config: Dict):
        view_config["panels"] = []
        default_detail_config = DEFAULT_POD_DETAIL
        default_where = [
            {
                "key": "bcs_cluster_id",
                "method": "eq",
                "value": ["$bcs_cluster_id"],
            },
            {
                "key": "namespace",
                "method": "eq",
                "value": ["$namespace"],
            },
            {
                "key": "pod_name",
                "method": "eq",
                "value": ["$pod_name"],
            },
        ]
        # 设置视图面板的显示位置
        view_config["order"] = cls.get_order(view, default_detail_config)
        # 根据面板位置配置，添加前端显示的面板配置
        cls.patch_group_panels(default_detail_config, default_where, view_config)
        # 设置概览视图的面板
        overview_where = []
        overview_panels = cls.copy_replace_panels_with_where(view_config["panels"], overview_where)
        view_config["overview_panels"] = overview_panels
        # 添加事件视图面板
        cls.add_event_panel(view, view_config)

        return view_config

    @classmethod
    def get_container_view_config(cls, view: SceneViewModel, view_config: Dict):
        view_config["panels"] = []
        default_detail_config = DEFAULT_CONTAINER_DETAIL
        default_where = [
            {
                "key": "bcs_cluster_id",
                "method": "eq",
                "value": ["$bcs_cluster_id"],
            },
            {
                "key": "container_name",
                "method": "eq",
                "value": ["$container_name"],
            },
            {
                "key": "namespace",
                "method": "eq",
                "value": ["$namespace"],
            },
            {
                "key": "pod_name",
                "method": "eq",
                "value": ["$pod_name"],
            },
        ]

        # 设置视图面板的显示位置
        view_config["order"] = cls.get_order(view, default_detail_config)
        # 设置视图分组的面板
        cls.patch_group_panels(default_detail_config, default_where, view_config)
        # 设置概览视图的面板
        overview_where = []
        overview_panels = cls.copy_replace_panels_with_where(view_config["panels"], overview_where)
        view_config["overview_panels"] = overview_panels
        # 添加事件视图面板
        cls.add_event_panel(view, view_config)

        return view_config

    @classmethod
    def get_workload_view_config(cls, view: SceneViewModel, view_config: Dict):
        view_config["panels"] = []
        default_detail_config = DEFAULT_WORKLOAD_DETAIL
        default_where = [
            {"key": "bcs_cluster_id", "method": "eq", "value": ["$bcs_cluster_id"]},
            {"key": "namespace", "method": "eq", "value": ["$namespace"]},
            {"key": "workload_kind", "method": "eq", "value": ["$workload_type"]},
            {"key": "workload_name", "method": "eq", "value": ["$workload_name"]},
        ]
        # 设置视图面板的显示位置
        view_config["order"] = cls.get_order(view, default_detail_config)
        # 设置视图分组的面板
        cls.patch_group_panels(default_detail_config, default_where, view_config)
        # 设置概览视图的面板
        overview_where = []
        overview_panels = cls.copy_replace_panels_with_where(view_config["panels"], overview_where)
        view_config["overview_panels"] = overview_panels
        # 视图面板添加事件panels
        cls.add_event_panel(view, view_config)

        return view_config

    @classmethod
    def copy_replace_panels_with_where(cls, panels, where):
        """复制面板并用部分属性值替换 ."""
        overview_panels = copy.deepcopy(panels)
        # 获得所有的子面板
        all_panels = []
        for panel in overview_panels:
            if panel["type"] == "row":
                sub_panels = panel["panels"]
            else:
                sub_panels = [panel]
            all_panels.extend(sub_panels)

        for sub_panel in all_panels:
            targets = sub_panel["targets"]
            for target in targets:
                query_configs = target["data"]["query_configs"]
                for query_config in query_configs:
                    query_config["where"] = where

        return overview_panels

    @classmethod
    def get_service_view_config(cls, view: SceneViewModel, view_config: Dict):
        view_config["panels"] = []
        default_detail_config = DEFAULT_SERVICE_DETAIL
        default_where = [
            {"key": "bcs_cluster_id", "method": "eq", "value": ["$bcs_cluster_id"]},
            {"key": "namespace", "method": "eq", "value": ["$namespace"]},
            {"key": "pod_name", "method": "eq", "value": "$pod_name_list"},
        ]

        # 设置视图面板的显示位置
        view_config["order"] = cls.get_order(view, default_detail_config)
        # 设置视图分组的面板
        cls.patch_group_panels(default_detail_config, default_where, view_config)
        # 设置概览视图的面板
        overview_where = []
        overview_panels = cls.copy_replace_panels_with_where(view_config["panels"], overview_where)
        view_config["overview_panels"] = overview_panels
        # 添加事件视图面板
        cls.add_event_panel(view, view_config)

        return view_config

    @classmethod
    def build_panel_group(cls, view: SceneViewModel, default_detail_config: List) -> Dict:
        """构造视图中的面板顺序配置 ."""
        # 获得数据库中的面板顺序
        id_prefix = DEFAULT_PANEL_GROUP_ID_PREFIX.format(view_id=view.id)
        order_groups_map = {}
        for group in view.order:
            group_id = group['id']
            if not group_id.startswith(id_prefix):
                # 自定义分组加上前缀
                group_id = f"{id_prefix}{group_id}"
                group["id"] = group_id
            order_groups_map[group_id] = {
                "id": group_id,
                "title": group["title"],
                "panels": group["panels"],
            }

        # 获得默认分组中的面板顺序
        panel_ids_set = set()
        for group in default_detail_config:
            group_id = group["id"]
            if group_id not in order_groups_map:
                # 添加新的分组
                panel_ids_set |= {panel["id"] for panel in group["panels"]}
                order_groups_map[group_id] = {
                    "id": group_id,
                    "title": group["title"],
                    "panels": group["panels"],
                }
            else:
                # 添加新的面板，追加到之前的面板后面
                panels = order_groups_map[group_id]["panels"]
                old_panel_id_set = {panel["id"] for panel in panels}
                new_panels = copy.deepcopy(panels)
                for panel in group["panels"]:
                    if panel["id"] not in old_panel_id_set:
                        new_panels.append(panel)
                        panel_ids_set.add(panel["id"])
                order_groups_map[group_id]["panels"] = new_panels

        # 根据指标前缀在指标缓存表中查询匹配的指标
        metric_prefixes = cls.get_metric_prefixes(view)
        metric_list = cls.get_metrics_list(view, metric_prefixes)
        # 补齐指标缓存中新增的指标面板
        for metric_field in metric_list:
            group_suffix = None
            for prefix in metric_prefixes:
                if metric_field.startswith(prefix):
                    group_suffix = metric_field.replace(prefix, "", 1).split("_")[0]
            if not group_suffix:
                continue
            # 添加其他组
            group_id = f"{id_prefix}{group_suffix}"
            if group_id not in order_groups_map:
                group_id = f"{id_prefix}else"
                order_groups_map[group_id] = {
                    "id": group_id,
                    "title": "else",
                    "panels": [],
                }
            # 添加新增的panel到指定组
            panels = order_groups_map[group_id]["panels"]
            panel_id = f"{id_prefix}{metric_field}"
            if panel_id not in panel_ids_set:
                panels.append(
                    {
                        "id": panel_id,
                        "title": metric_field,
                        "hidden": True,
                        "target": {
                            "query_configs": [
                                {
                                    "metrics": [
                                        {
                                            "field": metric_field,
                                        }
                                    ]
                                }
                            ]
                        },
                    }
                )
                panel_ids_set.add(panel_id)

        # 去掉无效的配置
        new_order_groups_map = {}
        for group_id, group in order_groups_map.items():
            # 去掉数据库中无效的panel
            panels = group["panels"]
            new_panels = [panel for panel in panels if panel["id"] in panel_ids_set]
            # 去掉不包含panel的组
            if not new_panels:
                continue
            new_order_groups_map[group_id] = {
                "id": group_id,
                "title": group["title"],
                "panels": new_panels,
            }

        return new_order_groups_map

    @classmethod
    def build_order(cls, view: SceneViewModel, default_detail_config: List, order_groups_map: Dict) -> List:
        order_groups_map = copy.deepcopy(order_groups_map)
        id_prefix = DEFAULT_PANEL_GROUP_ID_PREFIX.format(view_id=view.id)
        order = []
        group_id_set = set()
        # 先按数据库记录中的顺序排序
        for group in view.order:
            group_id = group["id"]
            order_group = order_groups_map.get(group_id)
            if not order_group:
                continue
            order.append(order_group)
            group_id_set.add(group_id)

        # 再按默认配置排序
        for group in default_detail_config:
            group_id = group["id"]
            if group_id in group_id_set:
                # 已经在数据库配置中存在则忽略
                continue
            order_group = order_groups_map.get(group_id)
            if not order_group:
                continue
            order.append(order_group)

        # else组放在最后
        group_id = f"{id_prefix}else"
        else_group = order_groups_map.get(group_id)
        if else_group:
            order.append(else_group)

        # 只返回panel的部分数据
        for group in order:
            group["panels"] = [
                {
                    "id": panel["id"],
                    "hidden": panel["hidden"],
                    "title": panel["title"],
                }
                for panel in group["panels"]
            ]

        return order

    @classmethod
    def build_panels(cls, order: List, panel_group_map: Dict, default_where: List) -> List:
        """给面板配置添加unify query参数 ."""
        group_list = []
        for group in order:
            group_id = group["id"]
            order_group = panel_group_map.get(group_id)
            if not order_group:
                continue
            panels = order_group["panels"]
            if not panels:
                continue
            panels_panels = []

            for panel in panels:
                # 忽略隐藏的面板
                if panel.get("hidden"):
                    continue
                panel_id = panel["id"]
                # 获得面板的默认参数
                title = panel["title"]
                # 获得子标题
                sub_title = panel.get("sub_title")
                if not sub_title:
                    sub_title = panel_id.rsplit(".")[-1]
                # 位置信息
                grid_pos = {"x": 0, "y": 0, "w": 24, "h": 8}
                # 图表的类型
                graph_type = panel.get("type", "graph")
                # 图表显示配置
                options = {
                    "legend": {
                        "displayMode": "list",
                        "placement": "right",
                    },
                    "unit": panel.get("unit", ""),
                }
                # 图表接口配置
                targets = []
                for target in panel.get("targets", []):
                    target_data = target.get("data", {})
                    if not target_data:
                        continue
                    query_configs_in_config = target_data.get("query_configs")
                    if not query_configs_in_config:
                        continue
                    expression = target_data.get("expression", "A")
                    query_configs = []
                    for query_config in query_configs_in_config:
                        promql = query_config.get("promql")
                        if not promql:
                            group_by = query_config.get("group_by", [])
                            if not group_by:
                                new_group_by = ["$group_by"]
                            else:
                                new_group_by = group_by + ["$group_by"]
                            functions = query_config.get("functions", [])
                            metrics = query_config.get("metrics", [])
                            new_metrics = []
                            for index, metric in enumerate(metrics):
                                field = metric["field"]
                                if not functions:
                                    if index == 0:
                                        functions = [
                                            {"id": "time_shift", "params": [{"id": "n", "value": "$time_shift"}]}
                                        ]
                                    if field.endswith("_total"):
                                        functions.append({"id": "irate", "params": [{"id": "window", "value": "2m"}]})
                                alias = metric.get("alias", "A")
                                table = metric.get("table", "")
                                new_metrics.append(
                                    {
                                        "alias": alias,
                                        "table": table,
                                        "field": field,
                                        "method": "$method",
                                    }
                                )
                            where = query_config.get("where", [])
                            new_where = where + default_where
                            new_query_config = copy.deepcopy(DEFAULT_GRAPH_UNIFY_QUERY_QUERY_CONFIG)
                            new_query_config.update(
                                {
                                    "metrics": new_metrics,
                                    "group_by": new_group_by,
                                    "where": new_where,
                                    "functions": functions,
                                }
                            )
                        else:
                            new_query_config = copy.deepcopy(DEFAULT_GRAPH_PROMQL_QUERY_CONFIG)
                            new_query_config.update(
                                {
                                    "alias": alias,
                                    "promql": promql,
                                }
                            )
                            expression = promql

                        query_configs.append(new_query_config)

                    targets.append(
                        {
                            "data": {
                                "expression": expression,
                                "query_configs": query_configs,
                            },
                            "datasource": "time_series",
                            "data_type": "time_series",
                            "api": "grafana.graphUnifyQuery",
                        }
                    )

                panels_panels.append(
                    {
                        "id": panel_id,
                        "type": graph_type,
                        "title": title,
                        "subTitle": sub_title,
                        "gridPos": grid_pos,
                        "options": options,
                        "targets": targets,
                    }
                )

            if not panels_panels:
                continue
            group_list.append(
                {
                    "id": group_id,
                    "title": group["title"],
                    "type": "row",
                    "panels": panels_panels,
                }
            )

        return group_list

    @classmethod
    def get_node_view_config(cls, view: SceneViewModel, view_config: Dict):
        # 获得所有的面板
        default_detail_config = DEFAULT_NODE_PANELS
        panel_group_map = cls.build_panel_group(view, default_detail_config)

        # 设置视图面板的显示位置
        order = cls.build_order(view, default_detail_config, panel_group_map)
        view_config["order"] = order

        # 设置视图分组的面板
        where = [
            {
                "key": "bcs_cluster_id",
                "method": "eq",
                "value": ["$bcs_cluster_id"],
            },
            {
                "key": "instance",
                "method": "reg",
                "value": ["^$node_ip:"],
            },
        ]
        panels = cls.build_panels(order, panel_group_map, where)
        view_config["panels"] = panels

        # 设置概览视图的面板
        try:
            bcs_cluster_ids = list(
                BCSNode.objects.filter_by_biz_id(view.bk_biz_id).values_list("bcs_cluster_id", flat=True)
            )
            bcs_cluster_ids = sorted(list(set(bcs_cluster_ids)))
            overview_where = [
                {
                    "key": "bcs_cluster_id",
                    "method": "contains",
                    "value": bcs_cluster_ids,
                },
            ]
        except EmptyResultSet:
            overview_where = []
        overview_panels = cls.build_overview_panels(view, view_config["panels"], overview_where, panel_group_map)
        view_config["overview_panels"] = overview_panels

        return view_config

    @classmethod
    def build_overview_panels(
        cls, view: SceneViewModel, panels: List, where: List, panel_group_map: Dict = None
    ) -> List:
        """复制面板并用部分属性值替换 ."""
        bk_biz_id = view.bk_biz_id
        try:
            bcs_cluster_ids = list(BCSNode.objects.filter_by_biz_id(bk_biz_id).values_list("bcs_cluster_id", flat=True))
            bcs_cluster_ids = sorted(list(set(bcs_cluster_ids)))
        except EmptyResultSet:
            bcs_cluster_ids = []

        overview_panels = copy.deepcopy(panels)
        # 获得配置中的所有概览的where配置
        overview_where_map = {}
        overview_promql_map = {}
        if panel_group_map:
            for group in panel_group_map.values():
                for panel in group.get("panels", []):
                    panel_id = panel["id"]
                    targets = panel.get("targets", [])
                    for target in targets:
                        query_configs = target.get("data", {}).get("query_configs", [])
                        for index, query_config in enumerate(query_configs):
                            overview_promql = query_config.get("overview_promql")
                            overview_where = query_config.get("overview_where", [])
                            if overview_where:
                                overview_where_map.setdefault(panel_id, {})[index] = overview_where
                            if overview_promql:
                                overview_promql_map.setdefault(panel_id, {})[index] = overview_promql

        # 获得所有的子面板
        all_panels = []
        for panel in overview_panels:
            if panel["type"] == "row":
                sub_panels = panel["panels"]
            else:
                sub_panels = [panel]
            all_panels.extend(sub_panels)

        # 使用概览的配置替换
        for sub_panel in all_panels:
            panel_id = sub_panel["id"]
            targets = sub_panel["targets"]
            for target in targets:
                query_configs = target["data"]["query_configs"]
                for index, query_config in enumerate(query_configs):
                    overview_where = overview_where_map.get(panel_id, {}).get(index)
                    overview_promql = overview_promql_map.get(panel_id, {}).get(index)
                    if overview_promql and bcs_cluster_ids:
                        overview_promql = overview_promql % {"bcs_cluster_ids": "|".join(bcs_cluster_ids)}
                        query_config["promql"] = overview_promql
                        target["data"]["expression"] = overview_promql
                    else:
                        if not overview_where:
                            new_overview_where = where
                        else:
                            new_overview_where = overview_where + where
                        query_config["where"] = new_overview_where

        return overview_panels

    @classmethod
    def get_service_monitor_view_config(cls, view: SceneViewModel, view_config: Dict):
        default_detail_config = []
        view_config["order"] = cls.get_order(view, default_detail_config)
        view_config["panels"] = []
        # 如果无数据添加提示
        bk_biz_id = view.bk_biz_id
        try:
            cluster_list = BCSServiceMonitor.objects.filter_by_biz_id(bk_biz_id)
            if cluster_list:
                return view_config
        except EmptyResultSet:
            pass

        view_config["options"] = {}
        view_config["overview_panels"] = [
            {
                "id": 1,
                "gridPos": {"x": 0, "y": 0, "w": 24, "h": 24},
                "targets": [
                    {
                        "data": {
                            "type": "building",
                            "title": _("暂未发现任何ServiceMonitor"),
                            "subTitle": _("1. 确认集群中是否已经安装bkmonitor-operator\n" "2. 确认ServiceMonitor Yaml配置文件已经正确应用"),
                        }
                    }
                ],
                "title": "",
                "type": "exception-guide",
            }
        ]
        return view_config

    @classmethod
    def get_pod_monitor_view_config(cls, view: SceneViewModel, view_config: Dict):
        default_detail_config = []
        view_config["order"] = cls.get_order(view, default_detail_config)
        view_config["panels"] = []
        # 如果无数据添加提示
        bk_biz_id = view.bk_biz_id
        try:
            cluster_list = BCSPodMonitor.objects.filter_by_biz_id(bk_biz_id)
            if cluster_list:
                return view_config
        except EmptyResultSet:
            pass

        view_config["options"] = {}
        view_config["overview_panels"] = [
            {
                "id": 1,
                "gridPos": {"x": 0, "y": 0, "w": 24, "h": 24},
                "targets": [
                    {
                        "data": {
                            "type": "building",
                            "title": _("暂未发现任何PodMonitor"),
                            "subTitle": _("1. 确认集群中是否已经安装bkmonitor-operator\n" "2. 确认PodMonitor Yaml配置文件已经正确应用"),
                        }
                    }
                ],
                "title": "",
                "type": "exception-guide",
            }
        ]
        return view_config

    @classmethod
    def get_panel_default_param(
        cls, view_config: Dict, default_detail_config_map: Dict, group_id: str, panel_id: str
    ) -> Dict:
        """获得面板的默认参数配置 ."""
        # 获得默认面板参数配置
        default_panel = default_detail_config_map.get(group_id, {}).get(panel_id)
        if default_panel:
            return default_panel

        if view_config["id"] == "node":
            id_prefix = "bk_monitor.time_series.k8s.node."
            id_segments = panel_id.replace(id_prefix, "", 1).split(".")
            metric_field = id_segments.pop()
            table = ".".join(id_segments)
        else:
            table = ""
            metric_field = panel_id.split(".").pop()
        return {
            "id": panel_id,
            "title": metric_field,
            "target": {"query_configs": [{"table": table, "field": metric_field}]},
        }

    @classmethod
    def patch_group_panels(cls, default_detail_config, default_where, view_config):
        """给面板配置添加unify query参数 ."""
        # 格式化默认配置
        default_detail_config_map = {}
        for group in default_detail_config:
            for panel in group["panels"]:
                default_detail_config_map.setdefault(group["id"], {})[panel["id"]] = panel

        for group in view_config["order"]:
            group_id = group["id"]
            group_panels = group["panels"]
            panels_to_show = []
            for panel in group_panels:
                # 忽略隐藏的面板
                if panel["hidden"]:
                    continue
                panel_id = panel["id"]
                # 获得面板的默认参数
                panel_param = cls.get_panel_default_param(view_config, default_detail_config_map, group_id, panel_id)
                panel = {
                    "id": panel_id,
                    "type": "graph",
                    "title": panel_param["title"],
                    "subTitle": panel_id.split(".").pop(),
                    "gridPos": {"x": 0, "y": 0, "w": 24, "h": 8},
                    "options": {"legend": {"displayMode": "list", "placement": "right"}},
                    "targets": [],
                }
                target = panel_param["target"]
                if target:
                    query_configs = []
                    expression = target.get("expression", "A")
                    for index, qc in enumerate(target["query_configs"]):
                        field = qc["field"]
                        functions = []
                        if index == 0:
                            functions = [{"id": "time_shift", "params": [{"id": "n", "value": "$time_shift"}]}]
                        if field.endswith("_total"):
                            functions.append({"id": "rate", "params": [{"id": "window", "value": "2m"}]})
                        group_by = list(qc.get("group", []))
                        if not group_by:
                            group_by = ["$group_by"]
                        else:
                            group_by.append("$group_by")
                        query_configs.append(
                            {
                                "metrics": [
                                    {
                                        "alias": qc.get("alias", "A"),
                                        "table": qc.get("table", ""),
                                        "field": field,
                                        "method": "$method",
                                    }
                                ],
                                "interval": "$interval",  # 汇聚周期
                                "table": qc.get("table", ""),
                                "data_source_label": "bk_monitor",
                                "data_type_label": "time_series",
                                "group_by": group_by,
                                "where": default_where,
                                "functions": functions,
                            }
                        )
                    target = {
                        "data": {"expression": expression, "query_configs": query_configs},
                        "datasource": "time_series",
                        "data_type": "time_series",
                        "api": "grafana.graphUnifyQuery",
                    }
                    panel["targets"].append(target)

                panels_to_show.append(panel)

            view_config["panels"].append(
                {"id": group["id"], "title": group["title"], "type": "row", "panels": panels_to_show}
            )

    @classmethod
    def is_builtin_scene(cls, scene_id: str) -> bool:
        return scene_id == "kubernetes"

    @classmethod
    def create_or_update_view(
        cls, bk_biz_id: int, scene_id: str, view_type: str, view_id: str, view_config: Dict
    ) -> Optional[SceneViewModel]:
        view = SceneViewModel.objects.get(bk_biz_id=bk_biz_id, scene_id=scene_id, type=view_type, id=view_id)
        if "order" in view_config:
            order = view_config["order"]
            # 去掉重复的前缀
            id_prefix = f"bk_monitor.time_series.k8s.{view.id}."
            for group in order:
                group_id = group["id"]
                if not group_id:
                    continue
                if group_id.startswith(id_prefix):
                    # 处理多个重复的前缀
                    new_group_id = "{}{}".format(id_prefix, "".join(item for item in group_id.split(id_prefix) if item))
                    group["id"] = new_group_id
            view.order = order
        view.save()
        return None
