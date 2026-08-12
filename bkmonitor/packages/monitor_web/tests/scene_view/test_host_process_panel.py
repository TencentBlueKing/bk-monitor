"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from copy import deepcopy
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


def test_default_process_order_is_isolated_between_requests():
    view = SimpleNamespace(id="process", order=[])

    first_order = host.get_order_config(view)
    first_order[0]["panels"].clear()

    second_order = host.get_order_config(view)

    assert second_order[0]["panels"]
    assert second_order == host.DEFAULT_PROCESS_ORDER


def test_default_host_order_does_not_mutate_global_config(monkeypatch):
    extra_metric = SimpleNamespace(result_table_id="system.load", metric_field="extra")

    class FakeMetricRows(list):
        def values(self, *_fields):
            return [{"result_table_id": metric.result_table_id, "metric_field": metric.metric_field} for metric in self]

    class FakeManager:
        def filter(self, **_kwargs):
            return FakeMetricRows([extra_metric])

    original_order = deepcopy(host.DEFAULT_HOST_ORDER)
    monkeypatch.setattr(host.MetricListCache, "objects", FakeManager())
    monkeypatch.setattr(host, "bk_biz_id_to_bk_tenant_id", lambda _bk_biz_id: "tenant")

    order = host.get_default_order(SimpleNamespace(id="host", bk_biz_id=2))

    assert {panel["id"] for panel in order[0]["panels"]} - {panel["id"] for panel in original_order[0]["panels"]} == {
        "bk_monitor.time_series.system.load.extra"
    }
    assert host.DEFAULT_HOST_ORDER == original_order


def test_process_panels_only_include_system_metrics(monkeypatch):
    system_metric = build_metric("cpu_usage_pct")
    custom_metric = SimpleNamespace(
        data_source_label="bk_monitor",
        data_type_label="time_series",
        result_table_id="custom.proc",
        metric_field="cpu_usage_pct",
        metric_field_name="cpu_usage_pct",
        default_dimensions=["display_name"],
    )

    class FakeQuerySet(list):
        def filter(self, **kwargs):
            prefix = kwargs["result_table_id__startswith"]
            return FakeQuerySet(metric for metric in self if metric.result_table_id.startswith(prefix))

    class FakeManager:
        def filter(self, **_kwargs):
            return FakeQuerySet([system_metric, custom_metric])

    monkeypatch.setattr(host.MetricListCache, "objects", FakeManager())
    monkeypatch.setattr(host, "is_ipv6_biz", lambda _bk_biz_id: False)

    panels = host.get_panels(SimpleNamespace(id="process", bk_biz_id=2))

    assert [panel["id"] for panel in panels] == ["bk_monitor.time_series.system.proc.cpu_usage_pct"]
