"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from types import SimpleNamespace

import pytest

from monitor_web.scene_view.builtin import host


def build_metric(metric_field):
    return SimpleNamespace(
        data_source_label="bk_monitor",
        data_type_label="time_series",
        result_table_id="system.proc",
        metric_field=metric_field,
        metric_field_name=metric_field,
        default_dimensions=["bk_target_ip", "bk_target_cloud_id", "display_name"],
    )


@pytest.mark.parametrize(
    "metric_field, expected_method",
    [
        ("cpu_usage_pct", "sum_without_time"),
        ("mem_usage_pct", "sum_without_time"),
        ("mem_res", "sum_without_time"),
        ("mem_virt", "sum_without_time"),
        ("fd_num", "sum_without_time"),
        ("uptime", "MAX"),
    ],
)
def test_process_panel_uses_process_group_aggregation(monkeypatch, metric_field, expected_method):
    monkeypatch.setattr(host, "is_ipv6_biz", lambda _bk_biz_id: False)

    panel = host.get_metric_panel(bk_biz_id=2, metric=build_metric(metric_field), view_id="process")
    query_config = panel["targets"][0]["data"]["query_configs"][0]

    assert query_config["metrics"][0]["method"] == expected_method
    assert query_config["filter_dict"]["display_name"] == "$display_name"
    assert query_config["group_by"] == ["$group_by", "display_name"]
