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


def test_process_port_status_queries_latest_five_minutes_at_drawer_end(monkeypatch):
    query_calls = []

    class FakeDataSource:
        def __init__(self, **kwargs):
            self.config = kwargs

    class FakeUnifyQuery:
        def __init__(self, **kwargs):
            self.config = kwargs

        def query_data(self, **kwargs):
            query_calls.append(kwargs)
            return [
                {
                    "_time_": 1_700_003_599_000,
                    "listen": '["8080"]',
                    "nonlisten": "[]",
                    "not_accurate_listen": "[]",
                }
            ]

    monkeypatch.setattr(host_resources, "load_data_source", lambda *_args: FakeDataSource)
    monkeypatch.setattr(host_resources, "UnifyQuery", FakeUnifyQuery)
    monkeypatch.setattr(
        host_resources.api.cmdb,
        "get_host_by_id",
        lambda **_kwargs: [SimpleNamespace(bk_host_innerip="127.0.0.1", bk_cloud_id=0)],
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

    assert query_calls == [{"start_time": 1_700_003_300_000, "end_time": 1_700_003_600_000}]
    assert result[0]["value"] == "8080"


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
