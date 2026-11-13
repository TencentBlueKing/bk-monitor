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

from apm_web.handlers import metric_group
from apm_web.metric import resources as metric_resources
from apm_web.metric.resources import ServiceListAsyncResource
from apm_web.metric_handler import AvgDurationInstance
from apm_web.models import Application
from apm_web.utils import fill_series
from bkmonitor.data_source import filter_dict_to_conditions
from bkmonitor.utils.time_tools import time_interval_align
from monitor_web.grafana.resources.unify_query import GraphUnifyQueryResource

BK_BIZ_ID = 2
APP_NAME = "demo"
START_TIME = 1_700_000_013
END_TIME = START_TIME + 3600
FIRST_POINT = (START_TIME + 60) * 1000


@pytest.fixture
def application_lookup(mocker: MockerFixture) -> Mock:
    application = Application(bk_biz_id=BK_BIZ_ID, app_name=APP_NAME, metric_result_table_id="demo.__default__")
    return mocker.patch.object(Application.objects, "get", return_value=application)


@pytest.fixture(autouse=True)
def metric_table_lookup(mocker: MockerFixture) -> Mock:
    return mocker.patch.object(Application, "get_metric_table_id", return_value="demo.__default__")


@pytest.fixture(autouse=True)
def metric_info_lookup(mocker: MockerFixture) -> Mock:
    return mocker.patch.object(GraphUnifyQueryResource, "get_metric_info", return_value=[])


def request_column(column: str, service_names: list[str] | None = None) -> dict[str, Any]:
    params = {"bk_biz_id": BK_BIZ_ID, "app_name": APP_NAME, "start_time": START_TIME, "end_time": END_TIME}
    if service_names is not None:
        params["service_names"] = service_names
    return ServiceListAsyncResource().request({**params, "column": column})


@pytest.mark.parametrize(
    ("column", "targets"), [("request_count", None), ("request_count", []), ("unknown", ["collector"])]
)
def test_empty_metric_request_skips_queries(
    application_lookup: Mock, metric_info_lookup: Mock, column: str, targets: list[str] | None
) -> None:
    assert request_column(column, targets) == {"data": []}
    application_lookup.assert_not_called()
    metric_info_lookup.assert_not_called()


def test_error_rate_uses_expression_and_preserves_ratio(mocker: MockerFixture, application_lookup: Mock) -> None:
    first_point = (time_interval_align(START_TIME, 120) + 120) * 1000
    error_point = first_point + 120_000
    query = mocker.patch(
        "bkmonitor.data_source.unify_query.query.api.unify_query.query_data",
        return_value={
            "series": [
                {
                    "columns": ["_time", "_value"],
                    "types": ["time", "double"],
                    "group_keys": ["service_name"],
                    "group_values": ["collector"],
                    "values": [[first_point // 1000, 0], [error_point // 1000, 0.25]],
                }
            ]
        },
    )
    mocker.patch("monitor_web.grafana.resources.unify_query.safe_push_to_gateway")
    mocker.patch("bkmonitor.data_source.unify_query.query.metrics.report_all")

    [row] = request_column("error_rate", ["collector"])["data"]

    assert row["error_rate"]["unit"] == "percentunit"
    assert [point for point in row["error_rate"]["datapoints"] if point[0] is not None] == [
        [0, first_point],
        [0.25, error_point],
    ]
    query.assert_called_once()
    params = query.call_args.kwargs
    assert params["metric_merge"] == "(a or b < bool 0) / b"
    error, total = params["query_list"]
    for item in (error, total):
        assert item["dimensions"] == ["service_name"]
        assert item["field_name"] == "bk_apm_count"
        assert {"field_name": "service_name", "op": "contains", "value": ["collector"]} in item["conditions"][
            "field_list"
        ]
    assert {"field_name": "status_code", "op": "contains", "value": ["2"]} in error["conditions"]["field_list"]
    assert {"field_name": "status_code", "op": "ncontains", "value": [""]} in total["conditions"]["field_list"]


def test_request_count_filters_targets_and_keeps_merge_order(mocker: MockerFixture, application_lookup: Mock) -> None:
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
            rows = [({"service_name": "collector-mysql"}, 100), ({"service_name": "http:query-v2"}, 100)]
        elif group == ("service_name", "db_system"):
            rows = [({"service_name": "collector", "db_system": "mysql"}, 7)]
        elif group == ("service_name", "messaging_system"):
            # 故意与 DB 分支同名，验证消息指标按原顺序覆盖 DB 指标。
            rows = [({"service_name": "collector", "messaging_system": "mysql"}, 9)]
        else:
            rows = [({"peer_service": "query-v2"}, 5)]
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
    targets = ["__BKMONITOR_ALL__", "collector-mysql", "http:query-v2", "collector-mysql"]

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
    assert requests == {
        ("service_name",): {("service_name", "contains", tuple(dict.fromkeys(targets)))},
        ("service_name", "db_system"): {
            ("service_name", "contains", ("collector", "http:query")),
            ("db_system", "ncontains", ("",)),
        },
        ("service_name", "messaging_system"): {
            ("service_name", "contains", ("collector", "http:query")),
            ("messaging_system", "ncontains", ("",)),
        },
        ("peer_service",): {("peer_service", "contains", ("query-v2",))},
    }


def test_metric_column_propagates_query_failure(mocker: MockerFixture, application_lookup: Mock) -> None:
    def graph_response(params: dict[str, Any]) -> dict[str, Any]:
        if params["query_configs"][0]["group_by"] == ["service_name", "db_system"]:
            raise RuntimeError("db metric query failed")
        return {"series": []}

    mocker.patch(
        "apm_web.handlers.service_handler.resource.grafana.graph_unify_query",
        side_effect=graph_response,
    )

    with pytest.raises(RuntimeError, match="db metric query failed"):
        request_column("request_count", ["collector-mysql"])


@pytest.mark.parametrize(
    ("service_name", "predicate", "component_field"),
    [
        ("collector", "api-mysql", "db_system"),
        ("collector-api", "mysql", "db_system"),
        ("-collector", "client-kafka", "messaging_system"),
        ("collector-", "mysql", "db_system"),
        ("collector", "-kafka", "messaging_system"),
    ],
)
def test_component_target_preserves_all_hyphen_pairings(
    mocker: MockerFixture,
    application_lookup: Mock,
    service_name: str,
    predicate: str,
    component_field: str,
) -> None:
    def graph_response(params: dict[str, Any]) -> dict[str, Any]:
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
        "apm_web.handlers.service_handler.resource.grafana.graph_unify_query",
        side_effect=graph_response,
    )
    target = f"{service_name}-{predicate}"

    [row] = request_column("request_count", [target])["data"]

    assert row["service_name"] == target
    assert [point for point in row["request_count"]["datapoints"] if point[0] is not None] == [[7, FIRST_POINT]]


@pytest.mark.parametrize("column", ["request_count", "error_rate"])
def test_count_columns_share_metric_helper(
    mocker: MockerFixture, application_lookup: Mock, metric_table_lookup: Mock, column: str
) -> None:
    groups = mocker.spy(metric_group, "SpanMetricGroup")
    mocker.patch("bkmonitor.data_source.unify_query.query.api.unify_query.query_data", return_value={"series": []})
    mocker.patch("monitor_web.grafana.resources.unify_query.safe_push_to_gateway")
    mocker.patch("bkmonitor.data_source.unify_query.query.metrics.report_all")

    request_column(column, ["collector-mysql"])

    metric_table_lookup.assert_called_once_with(BK_BIZ_ID, APP_NAME)
    helpers = [call.kwargs["metric_helper"] for call in groups.call_args_list]
    assert len(helpers) > 1
    assert all(helper is helpers[0] for helper in helpers)


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
                "group_values": ["collector"],
                "values": [[aligned_start + 60, 1.123456789], [aligned_start + 240, 2.987654321], [aligned_end, 999]],
            }
        ]
    }
    query = mocker.patch("bkmonitor.data_source.unify_query.query.api.unify_query.query_data", return_value=uq_response)
    mocker.patch("bkmonitor.data_source.unify_query.query.metrics.report_all")
    mocker.patch("bkmonitor.data_source.data_source.api.unify_query.query_data_by_promql", return_value=uq_response)
    legacy_points = AvgDurationInstance(
        application_lookup.return_value, START_TIME, END_TIME, group_by=["service_name"]
    ).get_range_calculate_values_mapping()[("collector",)]

    [row] = request_column("avg_duration", ["collector"])["data"]

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
    assert params["metric_merge"] == "(a or vector(0)) / (b != 0)"
    assert [item["field_name"] for item in params["query_list"]] == ["bk_apm_duration_sum", "bk_apm_total"]
    for item in params["query_list"]:
        assert item["time_aggregation"]["function"] == "increase"
        assert item["time_aggregation"]["window"] == "60s"
        assert item["dimensions"] == ["service_name"]
        assert item["conditions"]["field_list"] == [
            {"field_name": "service_name", "value": ["collector"], "op": "contains"}
        ]


def test_error_rate_preserves_sparse_trend_timestamps(mocker: MockerFixture, application_lookup: Mock) -> None:
    timestamp = (time_interval_align(START_TIME, 120) + 600) * 1000
    mocker.patch(
        "bkmonitor.data_source.unify_query.query.api.unify_query.query_data",
        return_value={
            "series": [
                {
                    "columns": ["_time", "_value"],
                    "types": ["time", "double"],
                    "group_keys": ["service_name"],
                    "group_values": ["collector"],
                    "values": [[timestamp // 1000, 1 / 3], [time_interval_align(END_TIME, 120), 999]],
                }
            ]
        },
    )
    mocker.patch("monitor_web.grafana.resources.unify_query.safe_push_to_gateway")
    mocker.patch("bkmonitor.data_source.unify_query.query.metrics.report_all")

    [row] = request_column("error_rate", ["collector"])["data"]

    assert row["error_rate"] == {
        "unit": "percentunit",
        "datapoints": fill_series([{"datapoints": [[0.333333, timestamp]]}], START_TIME, END_TIME, interval=120)[0][
            "datapoints"
        ],
    }


@pytest.mark.parametrize("values", [None, [], [0], [1]])
def test_error_rate_distinguishes_no_data_from_zero(
    mocker: MockerFixture, application_lookup: Mock, values: list[int] | None
) -> None:
    timestamp = time_interval_align(START_TIME, 120) + 120
    # UQ 对缺失分母返回空 series，对零分母的 NaN 返回空 values；有效零值不能丢弃。
    series = (
        []
        if values is None
        else [
            {
                "columns": ["_time", "_value"],
                "types": ["time", "double"],
                "group_keys": ["service_name"],
                "group_values": ["collector"],
                "values": [[timestamp, value] for value in values],
            }
        ]
    )
    query = mocker.patch(
        "bkmonitor.data_source.unify_query.query.api.unify_query.query_data", return_value={"series": series}
    )
    mocker.patch("monitor_web.grafana.resources.unify_query.safe_push_to_gateway")
    mocker.patch("bkmonitor.data_source.unify_query.query.metrics.report_all")

    [row] = request_column("error_rate", ["collector"])["data"]

    assert row["error_rate"]["unit"] == "percentunit"
    if values:
        assert [point for point in row["error_rate"]["datapoints"] if point[0] is not None] == [
            [values[0], timestamp * 1000]
        ]
    else:
        assert row["error_rate"]["datapoints"] is None
    query.assert_called_once()


@pytest.mark.parametrize(("component_values", "expected_value"), [([0], 0), ([], 0.5)])
def test_error_rate_merges_available_series_when_names_collide(
    mocker: MockerFixture, application_lookup: Mock, component_values: list[float], expected_value: float
) -> None:
    timestamp = time_interval_align(START_TIME, 120) + 120

    def response(**params: Any) -> dict[str, Any]:
        group = params["query_list"][0]["dimensions"]
        if group == ["service_name"]:
            dimensions, values = {"service_name": "collector-mysql"}, [0.5]
        elif group == ["service_name", "db_system"]:
            dimensions, values = {"service_name": "collector", "db_system": "mysql"}, component_values
        else:
            return {"series": []}
        return {
            "series": [
                {
                    "columns": ["_time", "_value"],
                    "types": ["time", "double"],
                    "group_keys": list(dimensions),
                    "group_values": list(dimensions.values()),
                    "values": [[timestamp, value] for value in values],
                }
            ]
        }

    mocker.patch("bkmonitor.data_source.unify_query.query.api.unify_query.query_data", side_effect=response)
    mocker.patch("monitor_web.grafana.resources.unify_query.safe_push_to_gateway")
    mocker.patch("bkmonitor.data_source.unify_query.query.metrics.report_all")

    [row] = request_column("error_rate", ["collector-mysql"])["data"]

    assert [point for point in row["error_rate"]["datapoints"] if point[0] is not None] == [
        [expected_value, timestamp * 1000]
    ]


@pytest.mark.parametrize("column", ["request_count", "error_rate"])
def test_graph_preserves_service_named_all_marker(mocker: MockerFixture, application_lookup: Mock, column: str) -> None:
    timestamp = time_interval_align(START_TIME, 120) + 120
    target = "__BKMONITOR_ALL__"

    def response(**params: Any) -> dict[str, Any]:
        for query in params["query_list"]:
            assert {"field_name": "service_name", "op": "contains", "value": [target]} in query["conditions"][
                "field_list"
            ]
        return {
            "series": [
                {
                    "columns": ["_time", "_value"],
                    "types": ["time", "double"],
                    "group_keys": ["service_name"],
                    "group_values": [target],
                    "values": [[timestamp, 0]],
                }
            ]
        }

    query = mocker.patch("bkmonitor.data_source.unify_query.query.api.unify_query.query_data", side_effect=response)
    mocker.patch("monitor_web.grafana.resources.unify_query.safe_push_to_gateway")
    mocker.patch("bkmonitor.data_source.unify_query.query.metrics.report_all")

    [row] = request_column(column, [target])["data"]

    assert [point for point in row[column]["datapoints"] if point[0] is not None] == [[0, timestamp * 1000]]
    query.assert_called_once()
