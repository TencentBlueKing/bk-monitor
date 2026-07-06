"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from monitor_web.strategies.metric_list_cache import BkmonitorMetricCacheManager


class TestBkmonitorMetricCacheManager:
    def test_get_system_metric_uses_existing_cloud_dimension(self):
        manager = BkmonitorMetricCacheManager.__new__(BkmonitorMetricCacheManager)
        manager.dimension_map = {}
        manager.get_label_name = lambda label: label

        table = {
            "table_id": "bkmonitor_time_series_1100030.__default__",
            "table_name_zh": "系统基础指标",
            "label": "os",
            "source_label": "bk_monitor",
            "type_label": "time_series",
            "data_label": "system_base",
            "field_list": [
                {"field_name": "hostname", "tag": "dimension", "description": "hostname"},
                {"field_name": "bk_target_ip", "tag": "dimension", "description": "目标IP"},
                {"field_name": "bk_cloud_id", "tag": "dimension", "description": "bk_cloud_id"},
                {"field_name": "host_timesync_query_seconds_min", "tag": "metric", "alias_name": "", "unit": ""},
            ],
        }

        [metric] = manager.get_system_metric(table)

        dimensions = [dimension["id"] for dimension in metric["dimensions"]]
        assert "bk_target_ip" in dimensions
        assert "bk_cloud_id" in dimensions
        assert "bk_target_cloud_id" not in dimensions
        assert dimensions.count("bk_target_ip") == 1
        assert metric["default_dimensions"] == ["bk_target_ip", "bk_cloud_id"]
