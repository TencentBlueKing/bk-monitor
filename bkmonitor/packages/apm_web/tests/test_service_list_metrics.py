"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2026 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from threading import Event, get_ident
from typing import Any
from unittest.mock import Mock

import pytest
from pytest_mock import MockerFixture

from apm_web.metric import resources as metric_resources
from apm_web.metric.resources import ServiceListAsyncResource
from apm_web.metric_handler import AvgDurationInstance
from apm_web.models import Application
from apm_web.utils import fill_series
from bkmonitor.data_source import filter_dict_to_conditions
from bkmonitor.utils.time_tools import time_interval_align
from monitor_web.grafana.resources.unify_query import GraphUnifyQueryResource

BK_BIZ_ID = 2
APP_NAME = "orders"
START_TIME = 1_700_000_013
END_TIME = START_TIME + 3600
FIRST_POINT = (START_TIME + 60) * 1000


@pytest.fixture
def application_lookup(mocker: MockerFixture) -> Mock:
    application = Application(bk_biz_id=BK_BIZ_ID, app_name=APP_NAME, metric_result_table_id="demo.bk_apm_count")
    return mocker.patch.object(Application.objects, "get", return_value=application)


@pytest.fixture(autouse=True)
def metric_info_lookup(mocker: MockerFixture) -> Mock:
    return mocker.patch.object(GraphUnifyQueryResource, "get_metric_info", return_value=[])


def request_column(column: str, service_names: list[str] | None = None) -> dict[str, Any]:
    params = {"bk_biz_id": BK_BIZ_ID, "app_name": APP_NAME, "start_time": START_TIME, "end_time": END_TIME}
    if service_names is not None:
        params["service_names"] = service_names
    return ServiceListAsyncResource().request({**params, "column": column})


@pytest.mark.parametrize(
    ("column", "targets"), [("request_count", None), ("request_count", []), ("unknown", ["orders"])]
)
def test_empty_metric_request_skips_queries(
    application_lookup: Mock, metric_info_lookup: Mock, column: str, targets: list[str] | None
) -> None:
    assert request_column(column, targets) == {"data": []}
    application_lookup.assert_not_called()
    metric_info_lookup.assert_not_called()


def test_error_rate_preserves_status_calculation(mocker: MockerFixture, application_lookup: Mock) -> None:
    error_point = (START_TIME + 180) * 1000
    zero_total_point = (START_TIME + 300) * 1000
    graph = mocker.patch(
        "apm_web.handlers.metric_group.groups.span.resource.grafana.graph_unify_query.query_with_metric_info",
        return_value={
            "series": [
                {
                    "dimensions": {"service_name": "orders", "status_code": "1"},
                    "datapoints": [[10, FIRST_POINT], [3, error_point], [0, zero_total_point]],
                },
                {"dimensions": {"service_name": "orders", "status_code": "2"}, "datapoints": [[1, error_point]]},
                {"dimensions": {"service_name": "orders"}, "datapoints": [[20, error_point], [20, zero_total_point]]},
            ]
        },
    )

    [row] = request_column("error_rate", ["orders"])["data"]

    assert row["error_rate"]["unit"] == "percentunit"
    assert [point for point in row["error_rate"]["datapoints"] if point[0] is not None] == [
        [0, FIRST_POINT],
        [0.25, error_point],
    ]
    graph.assert_called_once()
    params = graph.call_args.args[0]
    assert (int(params["bk_biz_id"]), params["start_time"], params["end_time"]) == (BK_BIZ_ID, START_TIME, END_TIME)
    [query] = params["query_configs"]
    assert query["group_by"] == ["service_name", "status_code"]
    assert query["interval"] == 120
    assert [(item["field"], item["method"]) for item in query["metrics"]] == [("bk_apm_count", "SUM")]
    conditions = filter_dict_to_conditions(query["filter_dict"], query["where"])
    assert [(item["key"], item["method"], item["value"]) for item in conditions] == [("service_name", "eq", ["orders"])]


def test_request_count_filters_targets_and_keeps_merge_order(
    mocker: MockerFixture, application_lookup: Mock, metric_info_lookup: Mock
) -> None:
    remote_started = Event()
    workers: set[int] = set()
    requests = {}
    timestamp = time_interval_align(START_TIME, 120) + 120

    def uq_response(**params: Any) -> dict[str, Any]:
        [query] = params["query_list"]
        group = tuple(query["dimensions"])
        requests[group] = {
            (item["field_name"], item["op"], tuple(item["value"])) for item in query["conditions"]["field_list"]
        }
        workers.add(get_ident())
        if group == ("service_name",):
            assert remote_started.wait(timeout=5)
            rows = [({"service_name": "orders-mysql"}, 100), ({"service_name": "http:billing-v2"}, 100)]
        elif group == ("service_name", "db_system"):
            rows = [({"service_name": "orders", "db_system": "mysql"}, 7)]
        elif group == ("service_name", "messaging_system"):
            rows = [({"service_name": "orders", "messaging_system": "mysql"}, 9)]
        else:
            rows = [({"peer_service": "billing-v2"}, 5)]
            remote_started.set()
        rows.append((dict.fromkeys(group, "offpage"), 999))
        return {
            "series": [
                {
                    "columns": ["_time", "_value"],
                    "types": ["time", "double"],
                    "group_keys": list(dims),
                    "group_values": list(dims.values()),
                    "values": [[timestamp, value]],
                }
                for dims, value in rows
            ]
        }

    mocker.patch("monitor_web.grafana.resources.unify_query.safe_push_to_gateway")
    mocker.patch("bkmonitor.data_source.unify_query.query.metrics.report_all")
    mocker.patch("bkmonitor.data_source.unify_query.query.api.unify_query.query_data", side_effect=uq_response)
    fill = mocker.spy(metric_resources, "fill_series")
    targets = ["__BKMONITOR_ALL__", "orders-mysql", "http:billing-v2", "orders-mysql"]

    result = request_column("request_count", targets)

    assert [row["service_name"] for row in result["data"]] == targets
    cells = [row["request_count"] for row in result["data"]]
    assert cells[0] == {"datapoints": None, "unit": None}
    assert cells[1] == cells[3]
    assert [[point for point in cell["datapoints"] if point[0] is not None] for cell in cells[1:]] == [
        [[value, timestamp * 1000]] for value in (9, 5, 9)
    ]
    assert len(workers) == 2
    assert fill.call_count == 2
    metric_info_lookup.assert_called_once()
    assert requests == {
        ("service_name",): {("service_name", "contains", tuple(dict.fromkeys(targets)))},
        ("service_name", "db_system"): {
            ("service_name", "contains", ("http:billing", "orders")),
            ("db_system", "ncontains", ("",)),
        },
        ("service_name", "messaging_system"): {
            ("service_name", "contains", ("http:billing", "orders")),
            ("messaging_system", "ncontains", ("",)),
        },
        ("peer_service",): {("peer_service", "contains", ("billing-v2",))},
    }


def test_metric_column_propagates_query_failure(mocker: MockerFixture, application_lookup: Mock) -> None:
    def graph_response(params: dict[str, Any], *, metric_infos: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        if params["query_configs"][0]["group_by"] == ["service_name", "db_system"]:
            raise RuntimeError("db metric query failed")
        return {"series": []}

    mocker.patch(
        "apm_web.handlers.metric_group.groups.span.resource.grafana.graph_unify_query.query_with_metric_info",
        side_effect=graph_response,
    )

    with pytest.raises(RuntimeError, match="db metric query failed"):
        request_column("request_count", ["orders-mysql"])


@pytest.mark.parametrize(
    ("service_name", "predicate", "component_field"),
    [
        ("orders", "api-mysql", "db_system"),
        ("orders-api", "mysql", "db_system"),
        ("-orders", "api-mysql", "messaging_system"),
        ("orders-", "mysql", "db_system"),
        ("orders", "-mysql", "messaging_system"),
    ],
)
def test_component_target_preserves_all_hyphen_pairings(
    mocker: MockerFixture,
    application_lookup: Mock,
    service_name: str,
    predicate: str,
    component_field: str,
) -> None:
    def graph_response(params: dict[str, Any], *, metric_infos: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        [query] = params["query_configs"]
        if query["group_by"] != ["service_name", component_field]:
            return {"series": []}
        conditions = filter_dict_to_conditions(query["filter_dict"], query["where"])
        candidates = next(item["value"] for item in conditions if item["key"] == "service_name")
        if service_name not in candidates:
            return {"series": []}
        return {
            "series": [
                {
                    "dimensions": {"service_name": service_name, component_field: predicate},
                    "datapoints": [[7, FIRST_POINT]],
                }
            ]
        }

    mocker.patch(
        "apm_web.handlers.metric_group.groups.span.resource.grafana.graph_unify_query.query_with_metric_info",
        side_effect=graph_response,
    )
    target = f"{service_name}-{predicate}"

    [row] = request_column("request_count", [target])["data"]

    assert row["service_name"] == target
    assert [point for point in row["request_count"]["datapoints"] if point[0] is not None] == [[7, FIRST_POINT]]


@pytest.mark.parametrize("column", ["request_count", "error_rate"])
def test_count_columns_preload_metric_info_in_request_thread(
    mocker: MockerFixture, application_lookup: Mock, metric_info_lookup: Mock, column: str
) -> None:
    parent_thread = get_ident()
    prefetched = [{"metric_field": "bk_apm_count"}]

    def lookup(params: dict[str, Any]) -> list[dict[str, Any]]:
        assert get_ident() == parent_thread
        assert params["bk_biz_id"] == BK_BIZ_ID
        assert params["query_configs"][0]["metrics"][0]["field"] == "bk_apm_count"
        return prefetched

    def query(params: dict[str, Any], *, metric_infos: list[dict[str, Any]] | None) -> dict[str, Any]:
        assert get_ident() != parent_thread
        assert metric_infos is prefetched
        return {"series": []}

    metric_info_lookup.side_effect = lookup
    graph = mocker.patch(
        "apm_web.handlers.metric_group.groups.span.resource.grafana.graph_unify_query.query_with_metric_info",
        side_effect=query,
    )

    request_column(column, ["orders-mysql"])

    metric_info_lookup.assert_called_once()
    assert graph.call_count == 3


def test_average_duration_preserves_precision_step_and_end_point(
    mocker: MockerFixture, application_lookup: Mock, metric_info_lookup: Mock
) -> None:
    aligned_start = time_interval_align(START_TIME, 60)
    aligned_end = time_interval_align(END_TIME, 60)
    uq_response = {
        "series": [
            {
                "columns": ["_time", "_value"],
                "types": ["time", "double"],
                "group_keys": ["service_name"],
                "group_values": ["orders"],
                "values": [[aligned_start + 60, 1.123456789], [aligned_start + 240, 2.987654321], [aligned_end, 999]],
            }
        ]
    }
    query = mocker.patch("bkmonitor.data_source.unify_query.query.api.unify_query.query_data", return_value=uq_response)
    mocker.patch("bkmonitor.data_source.unify_query.query.metrics.report_all")
    mocker.patch("bkmonitor.data_source.data_source.api.unify_query.query_data_by_promql", return_value=uq_response)
    legacy_points = AvgDurationInstance(
        application_lookup.return_value, START_TIME, END_TIME, group_by=["service_name"]
    ).get_range_calculate_values_mapping()[("orders",)]

    [row] = request_column("avg_duration", ["orders"])["data"]

    assert row["avg_duration"] == {
        "datapoints": fill_series([{"datapoints": legacy_points}], START_TIME, END_TIME, interval=120)[0]["datapoints"],
        "unit": "ns",
    }
    assert [point[0] for point in row["avg_duration"]["datapoints"] if point[0] is not None] == [
        1.123456789,
        2.987654321,
    ]
    query.assert_called_once()
    metric_info_lookup.assert_not_called()
    params = query.call_args.kwargs
    assert (params["space_uid"], params["start_time"], params["end_time"], params["step"]) == (
        "bkcc__2",
        str(aligned_start),
        str(aligned_end),
        "60s",
    )
    assert params["metric_merge"] == "(a or vector(0)) / b"
    assert [item["field_name"] for item in params["query_list"]] == ["bk_apm_duration_sum", "bk_apm_total"]
    for item in params["query_list"]:
        assert item["time_aggregation"]["function"] == "increase"
        assert item["time_aggregation"]["window"] == "60s"
        assert item["dimensions"] == ["service_name"]
        assert item["conditions"]["field_list"] == [
            {"field_name": "service_name", "value": ["orders"], "op": "contains"}
        ]
