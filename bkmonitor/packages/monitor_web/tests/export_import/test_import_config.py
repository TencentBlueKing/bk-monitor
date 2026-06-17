"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from monitor_web.export_import.import_config import normalize_result_table_id


class TestNormalizeResultTableId:
    def test_fix_corrupted_colon_separator(self):
        """冒号形态的结果表 ID 应被还原为点号，并清空一并串坏的 metric_id。"""
        query_config = {
            "data_source_label": "custom",
            "data_type_label": "time_series",
            "result_table_id": "2_bkapm_metric_smg:__default__",
            "metric_id": "custom:2_bkapm_metric_smg:__default__.PlayerNum",
        }
        normalize_result_table_id(query_config)
        assert query_config["result_table_id"] == "2_bkapm_metric_smg.__default__"
        assert query_config["metric_id"] == ""

    def test_skip_prometheus_promql_with_colon(self):
        """Prometheus 的 promql 允许含冒号，不能被改动。"""
        query_config = {
            "data_source_label": "prometheus",
            "data_type_label": "time_series",
            "result_table_id": "",
            "promql": "rate(a:b:c[5m])",
            "metric_id": "rate(a:b:c[5m])",
        }
        normalize_result_table_id(query_config)
        assert query_config["metric_id"] == "rate(a:b:c[5m])"

    def test_skip_bkdata(self):
        """计算平台结果表另有处理，本函数跳过。"""
        query_config = {
            "data_source_label": "bk_data",
            "data_type_label": "time_series",
            "result_table_id": "2_a:b",
            "metric_id": "bk_data.2_a:b.x",
        }
        normalize_result_table_id(query_config)
        assert query_config["result_table_id"] == "2_a:b"

    def test_noop_for_clean_dotted_table_id(self):
        """已是规范点号的结果表 ID 不应被改动。"""
        query_config = {
            "data_source_label": "bk_monitor",
            "data_type_label": "time_series",
            "result_table_id": "system.cpu_summary",
            "metric_id": "bk_monitor.system.cpu_summary.usage",
        }
        normalize_result_table_id(query_config)
        assert query_config["result_table_id"] == "system.cpu_summary"
        assert query_config["metric_id"] == "bk_monitor.system.cpu_summary.usage"
