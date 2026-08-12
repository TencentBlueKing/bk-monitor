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
from monitor_web.scene_view.resources import host as host_resources


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


@pytest.mark.parametrize(
    "serializer_class",
    [
        host_resources.GetHostProcessPortStatusResource.RequestSerializer,
        host_resources.GetHostProcessUptimeResource.RequestSerializer,
    ],
)
def test_process_external_panel_preserves_drawer_time_range(monkeypatch, serializer_class):
    monkeypatch.setattr(host_resources, "validate_bk_biz_id", lambda value: value)
    serializer = serializer_class(
        data={
            "bk_biz_id": 2,
            "bk_host_id": 101,
            "display_name": "nginx",
            "start_time": 1_700_000_000,
            "end_time": 1_700_003_600,
        }
    )

    serializer.is_valid(raise_exception=True)

    assert serializer.validated_data["start_time"] == 1_700_000_000
    assert serializer.validated_data["end_time"] == 1_700_003_600


@pytest.mark.parametrize(
    "health, expected_name, expected_color",
    [(0, "正常", "#3FC06D"), (1, "异常", "#EA3636")],
)
def test_process_port_status_preserves_multiple_ports_with_process_health_at_drawer_end(
    monkeypatch, health, expected_name, expected_color
):
    metric_calls = []
    process_calls = []

    def fake_get_process_port_health(**kwargs):
        metric_calls.append(kwargs)
        return {101: {"nginx": health}}

    def fake_get_process_info(**kwargs):
        process_calls.append(kwargs)
        return {
            101: [
                {"name": "nginx", "ports": [8080, 8081]},
                {"name": "other", "ports": [9090]},
            ]
        }

    monkeypatch.setattr(host_resources.resource.cc, "get_process_port_health", fake_get_process_port_health)
    monkeypatch.setattr(host_resources.resource.cc, "get_process_info", fake_get_process_info)
    monkeypatch.setattr(
        host_resources.api.cmdb,
        "get_host_by_id",
        lambda **_kwargs: [SimpleNamespace(bk_host_innerip="127.0.0.1", bk_cloud_id=0, bk_host_id=101)],
    )

    result = host_resources.GetHostProcessPortStatusResource().perform_request(
        {
            "bk_biz_id": 2,
            "bk_host_id": 101,
            "display_name": "nginx",
            "start_time": 1_700_000_000,
            "end_time": 1_700_003_600,
        }
    )

    expected_query = {
        "bk_biz_id": 2,
        "hosts": [SimpleNamespace(bk_host_innerip="127.0.0.1", bk_cloud_id=0, bk_host_id=101)],
        "start_time": 1_700_003_300,
        "end_time": 1_700_003_600,
    }
    assert metric_calls == [expected_query]
    assert process_calls == [{**expected_query, "limit_port_num": 0}]
    assert result == [
        {
            "value": "8080",
            "statusBgColor": "#e7f9f2" if health == 0 else "#ffe8c3",
            "statusColor": expected_color,
            "name": expected_name,
        },
        {
            "value": "8081",
            "statusBgColor": "#e7f9f2" if health == 0 else "#ffe8c3",
            "statusColor": expected_color,
            "name": expected_name,
        },
    ]


def test_get_host_process_list_id_is_process_name_for_scene_variable(monkeypatch):
    """旧版主机监控进程变量 fields:id→display_name，列表 id 必须是进程名而非 CMDB 进程 ID。"""
    host = SimpleNamespace(bk_host_id=101, ip="127.0.0.1", bk_cloud_id=0)

    monkeypatch.setattr(host_resources.api.cmdb, "get_host_by_id", lambda **_kwargs: [host])
    monkeypatch.setattr(
        host_resources.resource.cc,
        "get_process_info",
        lambda *_args, **_kwargs: {
            101: [
                {
                    "id": 15139,
                    "name": "kafka_broker",
                    "status": 0,
                    "protocol": "1",
                    "bindIp": "127.0.0.1",
                    "port": 9092,
                    "startCommand": "/usr/bin/kafka",
                    "user": "kafka",
                }
            ]
        },
    )

    class FakeAsyncResult:
        def __init__(self, value):
            self._value = value

        def get(self):
            return self._value

    class FakeThreadPool:
        def apply_async(self, func, kwds=None):
            return FakeAsyncResult(func(**(kwds or {})))

        def close(self):
            return None

        def join(self):
            return None

    monkeypatch.setattr(host_resources, "ThreadPool", FakeThreadPool)
    monkeypatch.setattr(host_resources.resource.cc, "get_process_port_health", lambda **_kwargs: {101: {}})
    monkeypatch.setattr(host_resources.resource.cc, "get_process_runtime_metrics", lambda **_kwargs: {101: {}})
    monkeypatch.setattr(host_resources.resource.cc, "get_process_uptime", lambda **_kwargs: {101: {}})
    monkeypatch.setattr(host_resources.resource.cc, "get_process_instance_count", lambda **_kwargs: {101: {}})

    result = host_resources.GetHostProcessListResource().perform_request(
        {"bk_biz_id": 10, "bk_host_id": 101, "start_time": 1_700_000_000, "end_time": 1_700_003_600}
    )

    assert result[0]["id"] == "kafka_broker"
    assert result[0]["name"] == "kafka_broker"
    assert result[0]["id"] != 15139


def test_process_uptime_queries_snapshot_at_drawer_end_in_milliseconds(monkeypatch):
    query_calls = []
    data_source_configs = []

    class FakeDataSource:
        def __init__(self, **kwargs):
            data_source_configs.append(kwargs)

    class FakeUnifyQuery:
        def __init__(self, **kwargs):
            self.config = kwargs

        def query_data(self, **kwargs):
            query_calls.append(kwargs)
            return [{"_result_": 7200}]

    monkeypatch.setattr(host_resources, "load_data_source", lambda *_args: FakeDataSource)
    monkeypatch.setattr(host_resources, "UnifyQuery", FakeUnifyQuery)
    monkeypatch.setattr(
        host_resources.api.cmdb,
        "get_host_by_id",
        lambda **_kwargs: [SimpleNamespace(bk_host_innerip="127.0.0.1", bk_cloud_id=0)],
    )

    result = host_resources.GetHostProcessUptimeResource().perform_request(
        {
            "bk_biz_id": 2,
            "bk_host_id": 101,
            "display_name": "nginx",
            "start_time": 1_700_003_540,
            "end_time": 1_700_003_600,
        }
    )

    assert data_source_configs[0]["metrics"] == [{"field": "uptime", "method": "MAX", "alias": "A"}]
    assert query_calls == [{"start_time": 1_700_003_540_000, "end_time": 1_700_003_600_000, "instant": True}]
    assert result == {"value": 7200, "unit": "s"}
