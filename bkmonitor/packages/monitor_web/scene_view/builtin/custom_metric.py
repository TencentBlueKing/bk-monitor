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
import re
from collections import defaultdict
from typing import Dict, List, Tuple

from django.db import models
from django.utils.translation import gettext as _
from monitor_web.models import CustomTSGroupingRule, CustomTSItem, CustomTSTable
from monitor_web.models.scene_view import SceneViewModel
from monitor_web.scene_view.builtin.collect import CollectBuiltinProcessor
from monitor_web.scene_view.builtin.utils import get_variable_filter_dict, sort_panels

from constants.data_source import DataSourceLabel, DataTypeLabel


def get_order_config(view: SceneViewModel) -> List:
    """
    获取排序配置
    """
    if view and view.order:
        return view.order

    custom_metric_id = int(view.scene_id.lstrip("custom_metric_"))
    table = CustomTSTable.objects.get(
        models.Q(bk_biz_id=view.bk_biz_id) | models.Q(is_platform=True), pk=custom_metric_id
    )
    fields = CustomTSItem.objects.filter(table=table).exclude(label=[])
    groups = CustomTSGroupingRule.objects.filter(time_series_group_id=table.time_series_group_id)
    group_map = {group.name: group for group in groups}

    label_fields = defaultdict(list)
    for field in fields:
        for label in field.label:
            match_type = set()
            match_rules = []
            group = group_map[label]
            if field.metric_name in group.manual_list:
                match_type.add("manual")
            for rule in group.auto_rules:
                if re.search(rule, field.metric_name):
                    match_type.add("auto")
                    match_rules.append(rule)
            label_fields[label].append(
                {
                    "match_type": list(match_type),
                    "metric_name": field.metric_name,
                    "hidden": field.hidden,
                    "match_rules": match_rules,
                }
            )

    return [
        {
            "id": label,
            "title": label,
            "manual_list": group_map[label].manual_list,
            "auto_rules": group_map[label].auto_rules,
            "panels": [
                {
                    "id": f"{table.table_id}.{field['metric_name']}",
                    "hidden": field["hidden"],
                    "match_type": field["match_type"],
                    "match_rules": field["match_rules"],
                }
                for field in fields
            ],
        }
        for label, fields in label_fields.items()
    ]


def get_panels(view: SceneViewModel) -> List[Dict]:
    """
    获取指标信息，包含指标信息及该指标需要使用的聚合方法、聚合维度、聚合周期等
    """
    custom_metric_id = int(view.scene_id.lstrip("custom_metric_"))
    config = CustomTSTable.objects.get(
        models.Q(bk_biz_id=view.bk_biz_id) | models.Q(is_platform=True), pk=custom_metric_id
    )
    metrics = config.get_metrics()

    panels = []
    for metric in metrics.values():
        if metric["monitor_type"] == "dimension":
            continue

        panels.append(
            {
                "id": f"{config.data_label or config.table_id}.{metric['name']}",
                "type": "graph",
                "title": metric["description"] or metric["name"],
                "subTitle": f"{config.data_label or config.table_id}.{metric['name']}",
                "dimensions": [dimension["id"] for dimension in metric["dimension_list"]],
                "targets": [
                    {
                        "data": {
                            "expression": "A",
                            "query_configs": [
                                {
                                    "metrics": [{"field": metric["name"], "method": "$method", "alias": "A"}],
                                    "interval": "$interval",
                                    "table": config.table_id,
                                    "data_label": config.data_label,
                                    "data_source_label": DataSourceLabel.CUSTOM,
                                    "data_type_label": DataTypeLabel.TIME_SERIES,
                                    "group_by": ["$group_by"],
                                    "where": [],
                                    "functions": [
                                        {"id": "time_shift", "params": [{"id": "n", "value": "$time_shift"}]}
                                    ],
                                    "filter_dict": {
                                        "targets": ["$current_target", "$compare_targets"],
                                        "variables": get_variable_filter_dict(view.variables),
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


class CustomMetricBuiltinProcessor(CollectBuiltinProcessor):
    @classmethod
    def get_auto_view_panels(cls, view: SceneViewModel) -> Tuple[List[Dict], List[Dict]]:
        """
        获取平铺视图配置
        """
        panels = get_panels(view)
        panels, order = sort_panels(panels, get_order_config(view), hide_metric=False)
        return panels, order

    @classmethod
    def get_default_view_config(cls, bk_biz_id: int, scene_id: str):
        custom_metric_id = int(scene_id.lstrip("custom_metric_"))
        return {
            "id": "default",
            "type": "detail",
            "mode": "auto",
            "name": _("默认"),
            "variables": [],
            "panels": [],
            "list": [],
            "order": [],
            "options": {
                "enable_index_list": True,
                "panel_tool": {
                    "compare_select": True,
                    "columns_toggle": True,
                    "interval_select": True,
                    "split_switcher": False,
                    "method_select": True,
                },
                "view_editable": True,
                "enable_auto_grouping": True,
                "enable_group": True,
                "variable_editable": True,
                "selector_panel": {
                    "title": _("目标列表"),
                    "type": "target_list",
                    "targets": [
                        {
                            "datasource": "custom_metric_target",
                            "dataType": "list",
                            "api": "scene_view.getCustomMetricTargetList",
                            "data": {"id": custom_metric_id},
                            "fields": {"id": "target"},
                        }
                    ],
                    "options": {"target_list": {"show_overview": True, "placeholder": _("搜索")}},
                },
            },
        }

    @classmethod
    def is_builtin_scene(cls, scene_id: str) -> bool:
        return scene_id.startswith("custom_metric_")
