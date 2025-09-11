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


from django.db.models.query import QuerySet

from core.drf_resource import resource
from bkmonitor.models.metric_list_cache import MetricListCache

from .data import BASE_METRICS, UPTIMECHECK_METRICS


class TestGetMetricListResource(object):
    def test_get_label_metric_list(self, mocker):
        # 获取指定标签指标
        mocker.patch.object(QuerySet, "values", return_value=BASE_METRICS)
        mocker.patch.object(QuerySet, "count", side_effect=[1, 2, 3, 4, 0])
        assert resource.strategies.get_metric_list(data_source_label="os", bk_biz_id=2, search_value="sa;fd;ewq") == {
            "count_list": [
                {
                    "count": 1,
                    "source_type": "BKMONITOR",
                    "data_type_label": "time_series",
                    "source_name": "\u76d1\u63a7\u91c7\u96c6",
                    "data_source_label": "bk_monitor",
                },
                {
                    "count": 2,
                    "source_type": "BASEALARM",
                    "data_type_label": "event",
                    "source_name": "\u7cfb\u7edf\u4e8b\u4ef6",
                    "data_source_label": "bk_monitor",
                },
                {
                    "count": 3,
                    "source_type": "BKDATA",
                    "data_type_label": "time_series",
                    "source_name": "\u6570\u636e\u5e73\u53f0",
                    "data_source_label": "bk_data",
                },
                {
                    "count": 4,
                    "source_type": "CUSTOMEVENT",
                    "data_type_label": "event",
                    "source_name": "\u81ea\u5b9a\u4e49\u4e8b\u4ef6",
                    "data_source_label": "custom",
                },
                {
                    "count": 0,
                    "source_type": "CUSTOMTIMINGDATA",
                    "data_type_label": "time_series",
                    "source_name": "\u81ea\u5b9a\u4e49\u65f6\u5e8f\u6570\u636e",
                    "data_source_label": "custom",
                },
            ],
            "metric_list": [
                {
                    "related_name": "test_host_exporter",
                    "metric_field": "host_cpu_idle_percent",
                    "related_id": "test_host_exporter",
                    "metric_field_name": "CPU\\u7a7a\\u95f2\\u65f6\\u95f4\\u767e\\u5206\\u6bd4",
                    "id": 292,
                    "unit": "%",
                    "dimensions": [
                        {"id": "bk_biz_id", "name": "\\u4e1a\\u52a1ID"},
                        {"id": "bk_cloud_id", "name": "\\u4e91\\u533a\\u57dfID"},
                        {"id": "ip", "name": "\\u91c7\\u96c6\\u5668IP\\u5730\\u5740"},
                        {"id": "bk_target_ip", "name": "\\u76ee\\u6807IP"},
                        {"id": "bk_target_cloud_id", "name": "\\u76ee\\u6807\\u673a\\u5668\\u4e91\\u533a\\u57dfID"},
                    ],
                    "collect_config": "test_host_exporter_collect",
                    "data_target": "host_target",
                    "data_type_label": "time_series",
                    "default_trigger_config": {"count": 1, "check_window": 5},
                    "collect_config_ids": [31],
                    "description": "",
                    "unit_conversion": 1.0,
                    "bk_biz_id": 0,
                    "data_source_label": "bk_monitor",
                    "result_table_id": "exporter_test_host_exporter.cpu",
                    "default_condition": [],
                    "result_table_name": "CPU\\u6027\\u80fd",
                    "result_table_label": "os",
                    "default_dimensions": ["bk_target_ip", "bk_target_cloud_id"],
                    "plugin_type": "Exporter",
                }
            ],
        }

    def test_get_uptimecheck_metric_list(self, mocker):
        # 获取拨测指标
        mocker.patch.object(MetricListCache.objects, "filter", return_value=MetricListCache.objects)
        mocker.patch.object(MetricListCache.objects, "values", return_value=UPTIMECHECK_METRICS)
        mocker.patch.object(MetricListCache.objects, "count", side_effect=[1, 2, 3, 4, 0])
        assert resource.strategies.get_metric_list(
            data_source_label="uptimecheck", bk_biz_id=2, search_value="sa;fd;ewq"
        ) == {
            "count_list": [
                {
                    "count": 1,
                    "source_type": "BKMONITOR",
                    "data_type_label": "time_series",
                    "source_name": "\u76d1\u63a7\u91c7\u96c6",
                    "data_source_label": "bk_monitor",
                },
                {
                    "count": 2,
                    "source_type": "BASEALARM",
                    "data_type_label": "event",
                    "source_name": "\u7cfb\u7edf\u4e8b\u4ef6",
                    "data_source_label": "bk_monitor",
                },
                {
                    "count": 3,
                    "source_type": "BKDATA",
                    "data_type_label": "time_series",
                    "source_name": "\u6570\u636e\u5e73\u53f0",
                    "data_source_label": "bk_data",
                },
                {
                    "count": 4,
                    "source_type": "CUSTOMEVENT",
                    "data_type_label": "event",
                    "source_name": "\u81ea\u5b9a\u4e49\u4e8b\u4ef6",
                    "data_source_label": "custom",
                },
                {
                    "count": 0,
                    "source_type": "CUSTOMTIMINGDATA",
                    "data_type_label": "time_series",
                    "source_name": "\u81ea\u5b9a\u4e49\u65f6\u5e8f\u6570\u636e",
                    "data_source_label": "custom",
                },
            ],
            "metric_list": [
                {
                    "related_name": "ping_baidu",
                    "metric_field": "available",
                    "related_id": "1",
                    "method_list": ["AVG"],
                    "metric_field_name": "单点可用率",
                    "id": 386,
                    "unit": "%",
                    "dimensions": [{"id": "task_id", "name": "任务ID"}],
                    "collect_config": "",
                    "data_target": "none_target",
                    "data_type_label": "time_series",
                    "result_table_id": "uptimecheck.http",
                    "collect_config_ids": "",
                    "description": "",
                    "unit_conversion": 0.01,
                    "bk_biz_id": 2,
                    "data_source_label": "bk_monitor",
                    "default_trigger_config": {"count": 1, "check_window": 5},
                    "default_condition": [
                        {"key": "task_id", "value_name": "1（ping_baidu）", "method": "eq", "value": 1}
                    ],
                    "result_table_name": "uptimecheck.http",
                    "result_table_label": "uptimecheck",
                    "default_dimensions": ["task_id"],
                    "plugin_type": "",
                }
            ],
        }
