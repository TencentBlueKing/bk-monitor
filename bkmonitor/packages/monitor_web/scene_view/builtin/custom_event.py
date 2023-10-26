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
from typing import List, Dict, Tuple
from django.utils.translation import gettext as _
from django.db import models

from constants.data_source import DataSourceLabel, DataTypeLabel
from monitor_web.models import CustomEventGroup
from monitor_web.models.scene_view import SceneViewModel
from monitor_web.scene_view.builtin.collect import CollectBuiltinProcessor
from monitor_web.scene_view.builtin.utils import get_variable_filter_dict


def get_panels(view: SceneViewModel) -> List[Dict]:
    """
    获取指标信息，包含指标信息及该指标需要使用的聚合方法、聚合维度、聚合周期等
    """
    custom_event_id = int(view.scene_id.lstrip("custom_event_"))
    config = CustomEventGroup.objects.get(
        models.Q(bk_biz_id=view.bk_biz_id) | models.Q(is_platform=True), pk=custom_event_id
    )
    return [
        {
            "id": config.table_id,
            "type": "event-log",
            "title": config.name,
            "gridPos": {"x": 0, "y": 0, "w": 24, "h": 20},
            "targets": [
                {
                    "data": {
                        "expression": "A",
                        "query_configs": [
                            {
                                "metrics": [{"field": "_index", "method": "$method", "alias": "A"}],
                                "table": config.table_id,
                                "data_source_label": DataSourceLabel.CUSTOM,
                                "data_type_label": DataTypeLabel.EVENT,
                                "group_by": ["$group_by"],
                                "interval": "$interval",
                                "where": [],
                                "functions": [{"id": "time_shift", "params": [{"id": "n", "value": "$time_shift"}]}],
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
                },
                {
                    "data": {
                        "result_table_id": config.table_id,
                        "data_source_label": DataSourceLabel.CUSTOM,
                        "data_type_label": DataTypeLabel.EVENT,
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
    ]


class CustomEventBuiltinProcessor(CollectBuiltinProcessor):
    @classmethod
    def get_auto_view_panels(cls, view: SceneViewModel) -> Tuple[List[Dict], List[Dict]]:
        """
        获取平铺视图配置
        """
        return get_panels(view), []

    @classmethod
    def get_default_view_config(cls, bk_biz_id: int, scene_id: str):
        custom_event_id = int(scene_id.lstrip("custom_event_"))
        return {
            "id": "default",
            "type": "detail",
            "mode": "custom",
            "name": _("默认"),
            "variables": [],
            "panels": [],
            "list": [],
            "order": [],
            "options": {
                "enable_index_list": False,
                "panel_tool": {
                    "compare_select": False,
                    "columns_toggle": False,
                    "interval_select": True,
                    "split_switcher": False,
                    "method_select": True,
                },
                "view_editable": True,
                "enable_group": True,
                "variable_editable": True,
                "selector_panel": {
                    "title": _("事件列表"),
                    "type": "list",
                    "targets": [
                        {
                            "datasource": "custom_metric_target",
                            "dataType": "list",
                            "api": "scene_view.getCustomEventTargetList",
                            "data": {"id": custom_event_id},
                            "fields": {"id": "target"},
                        }
                    ],
                },
            },
        }

    @classmethod
    def is_builtin_scene(cls, scene_id: str) -> bool:
        return scene_id.startswith("custom_event_")
