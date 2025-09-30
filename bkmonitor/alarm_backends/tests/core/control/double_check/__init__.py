# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from typing import Optional


def make_item_config(force_params: Optional[dict] = None) -> dict:
    defaults = {
        "query_configs": [
            {
                "metric_field": "idle",
                "agg_dimension": ["ip", "bk_cloud_id"],
                "id": 2,
                "agg_method": "AVG",
                "agg_condition": [],
                "agg_interval": 60,
                "result_table_id": "system.cpu_detail",
                "unit": "%",
                "data_type_label": "time_series",
                "metric_id": "bk_monitor.system.cpu_detail.idle",
                "data_source_label": "bk_monitor",
            }
        ],
        "algorithms": [
            {
                "config": [[{"threshold": 51.0, "method": "gte"}]],
                "level": 3,
                "type": "Threshold",
                "id": 2,
            },
            {
                "config": [[{"threshold": 100, "method": "lte"}]],
                "level": 3,
                "type": "Threshold",
                "id": 3,
            },
        ],
        "no_data_config": {"is_enabled": False, "continuous": 5},
        "id": 2,
        "name": "\u7a7a\u95f2\u7387",
        "target": [
            [{"field": "ip", "method": "eq", "value": [{"ip": "127.0.0.1", "bk_cloud_id": 0, "bk_supplier_id": 0}]}]
        ],
    }

    defaults.update(force_params)
    return defaults
