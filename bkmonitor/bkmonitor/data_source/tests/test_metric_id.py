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
from bkmonitor.data_source.metric_id import SystemMetricIdParser, CustomMetricIdParser, PluginMetricIdParser
from monitor_web.plugin.constant import PluginType


class TestDataSource:
    system_metric_testcases = {
        ("system:disk:usage", "bk_monitor.system.disk.usage"): {
            "data_source_label": "bk_monitor",
            "data_type_label": "time_series",
            "result_table_id": "system.disk",
            "metric_field": "usage",
        },
        ("pingserver:base:loss_percent", "bk_monitor.pingserver.base.loss_percent"): {
            "data_source_label": "bk_monitor",
            "data_type_label": "time_series",
            "result_table_id": "pingserver.base",
            "metric_field": "loss_percent",
        },
        ("uptimecheck:http:available", "bk_monitor.uptimecheck.http.available"): {
            "data_source_label": "bk_monitor",
            "data_type_label": "time_series",
            "result_table_id": "uptimecheck.http",
            "metric_field": "available",
        },
        ("process:port:alive", "bk_monitor.process.port.alive"): {
            "data_source_label": "bk_monitor",
            "data_type_label": "time_series",
            "result_table_id": "process.port",
            "metric_field": "alive",
        },
    }

    custom_metric_testcases = {
        ("custom_report_aggate:http_requests_total", "custom.custom_report_aggate.base.http_requests_total"): {
            "data_source_label": "custom",
            "data_type_label": "time_series",
            "result_table_id": "custom_report_aggate.base",
            "metric_field": "http_requests_total",
        },
        (
            "operation_data_custom_series:user_recent_login_total",
            "custom.operation_data_custom_series.base.user_recent_login_total",
        ): {
            "data_source_label": "custom",
            "data_type_label": "time_series",
            "result_table_id": "operation_data_custom_series.base",
            "metric_field": "user_recent_login_total",
        },
        ("bkunifylogbeat_common:system_load_5", "custom.bkunifylogbeat_common.base.system_load_5"): {
            "data_source_label": "custom",
            "data_type_label": "time_series",
            "result_table_id": "bkunifylogbeat_common.base",
            "metric_field": "system_load_5",
        },
        ("bkunifylogbeat_task:sender_state", "custom.bkunifylogbeat_task.base.sender_state"): {
            "data_source_label": "custom",
            "data_type_label": "time_series",
            "result_table_id": "bkunifylogbeat_task.base",
            "metric_field": "sender_state",
        },
        ("custom:100010:usage", "custom.2_bkmonitor_time_series_100010.base.usage"): {
            "data_source_label": "custom",
            "data_type_label": "time_series",
            "result_table_id": "2_bkmonitor_time_series_100010.base",
            "metric_field": "usage",
        },
        ("custom:custom_table:custom_field", "custom.custom_table.base.custom_field"): {
            "data_source_label": "custom",
            "data_type_label": "time_series",
            "result_table_id": "custom_table.base",
            "metric_field": "custom_field",
        },
    }

    plugin_metric_testcases = [
        {
            "metric_id": "testplugin:metric1",
            "old_metric_id": "bk_monitor.script_testplugin.base.metric1",
            "plugin_config": {
                "plugin_id": "testplugin",
                "plugin_type": "Script",
                "metric_json": [
                    {"table_name": "base1", "fields": [{"name": "metric2"}]},
                    {"table_name": "base", "fields": [{"name": "metric1"}]},
                ],
            },
            "config": {
                "data_source_label": "bk_monitor",
                "data_type_label": "time_series",
                "result_table_id": "script_testplugin.base",
                "metric_field": "metric1",
            },
        }
    ]

    def test_system_metric(self):
        for (metric_id, old_metric_id), config in self.system_metric_testcases.items():
            assert SystemMetricIdParser.match(metric_id)
            assert SystemMetricIdParser.match(old_metric_id)
            assert SystemMetricIdParser.parse_to_config(2, metric_id) == config
            assert SystemMetricIdParser.parse_to_config(2, old_metric_id) == config
            assert SystemMetricIdParser.generate_metric_id(**config) == metric_id

    def test_custom_metric(self):
        for (metric_id, old_metric_id), config in self.custom_metric_testcases.items():
            assert CustomMetricIdParser.match(metric_id)
            assert CustomMetricIdParser.match(old_metric_id)
            assert CustomMetricIdParser.parse_to_config(2, metric_id) == config
            assert CustomMetricIdParser.parse_to_config(2, old_metric_id) == config
            assert CustomMetricIdParser.generate_metric_id(**config) == metric_id

    def test_plugin_metric(self, mock):
        class CollectorPluginMeta:
            PLUGIN_TYPE_CHOICES = (
                (PluginType.EXPORTER, PluginType.EXPORTER),
                (PluginType.SCRIPT, PluginType.SCRIPT),
                (PluginType.JMX, PluginType.JMX),
                (PluginType.DATADOG, PluginType.DATADOG),
                (PluginType.PUSHGATEWAY, "BK-Pull"),
                (PluginType.BUILT_IN, "BK-Monitor"),
                (PluginType.LOG, PluginType.LOG),
                (PluginType.PROCESS, "Process"),
                (PluginType.SNMP_TRAP, PluginType.SNMP_TRAP),
                (PluginType.SNMP, PluginType.SNMP),
            )

            @classmethod
            def get_result_table_id(cls, plugin, table_name):
                db_name = ("{}_{}".format(plugin.plugin_type, plugin.plugin_id)).lower()
                if plugin.plugin_type == PluginType.PROCESS:
                    db_name = "process"
                return "{}.{}".format(db_name, table_name)

            @property
            def current_version(self):
                return self

            @property
            def info(self):
                return self

            def __init__(self, plugin_id, plugin_type, metric_json):
                self.plugin_id = plugin_id
                self.plugin_type = plugin_type
                self.metric_json = metric_json

        for testcase in self.plugin_metric_testcases:
            mock.patch(
                "bkmonitor.data_source.metric_id.PluginMetricIdParser._get_plugin",
                return_value=CollectorPluginMeta(**testcase["plugin_config"]),
            )
            assert PluginMetricIdParser.match(testcase["metric_id"])
            assert PluginMetricIdParser.match(testcase["old_metric_id"])
            assert PluginMetricIdParser.parse_to_config(2, testcase["metric_id"]) == testcase["config"]
            assert PluginMetricIdParser.parse_to_config(2, testcase["old_metric_id"]) == testcase["config"]
            assert PluginMetricIdParser.generate_metric_id(**testcase["config"]) == testcase["metric_id"]
