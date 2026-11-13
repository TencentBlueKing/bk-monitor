"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2026 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any
from unittest.mock import Mock

import pytest
from pytest_mock import MockerFixture

from apm_web.handlers.metric_group import MetricHelper, SpanMetricGroup
from apm_web.models import Application
from apm_web.trace.resources import TraceChartsResource
from bkmonitor.data_source import UnifyQuery, filter_dict_to_conditions, load_data_source
from bkmonitor.utils.time_tools import time_interval_align
from constants.apm import CallSide, SpanKind
from monitor_web.grafana.resources.unify_query import GraphUnifyQueryResource

START_TIME = 1_700_000_013
END_TIME = START_TIME + 3600


@pytest.fixture(autouse=True)
def metric_table_lookup(mocker: MockerFixture) -> Mock:
    return mocker.patch.object(Application, "get_metric_table_id", return_value="demo.__default__")


@pytest.fixture
def uq_query(mocker: MockerFixture) -> Mock:
    mocker.patch("bkmonitor.data_source.unify_query.query.metrics.report_all")
    return mocker.patch(
        "bkmonitor.data_source.unify_query.query.api.unify_query.query_data", return_value={"series": []}
    )


def make_group(group_by: list[str], **kwargs: Any) -> SpanMetricGroup:
    return SpanMetricGroup(2, "demo", group_by=group_by, metric_helper=MetricHelper(2, "demo"), **kwargs)


@pytest.mark.parametrize("calculation_type", ["request_total", "exception_rate", "avg_duration"])
@pytest.mark.parametrize("for_service_list", [False, True])
@pytest.mark.parametrize(
    ("group_by", "filter_value"),
    [
        (["service_name"], "collector"),
        (["service_name", "db_system"], "mysql"),
        (["service_name", "messaging_system"], "kafka"),
        (["peer_service"], "query-v2"),
    ],
)
def test_exported_config_and_handle_execute_same_query(
    uq_query: Mock, calculation_type: str, for_service_list: bool, group_by: list[str], filter_value: str
) -> None:
    group = make_group(
        group_by, filter_dict={f"{group_by[-1]}__eq": [filter_value]}, interval=120, for_service_list=for_service_list
    )
    options = {"start_time": START_TIME, "end_time": END_TIME}
    raw = group.query_config(calculation_type, raw=True, **options)
    config = group.query_config(calculation_type, **options)

    group.handle(calculation_type, start_time=START_TIME, end_time=END_TIME)
    actual = uq_query.call_args.kwargs
    # 从公开导出的配置构造查询，核对最终发给 UQ 的定义，而非测试私有工厂。
    query = UnifyQuery(
        bk_biz_id=raw["bk_biz_id"],
        data_sources=[
            load_data_source(q["data_source_label"], q["data_type_label"])(bk_biz_id=2, **q)
            for q in raw["query_configs"]
        ],
        expression=raw["expression"],
    )
    query.query_data(start_time=raw["start_time"], end_time=raw["end_time"])
    exported = uq_query.call_args.kwargs

    for field in ("query_list", "metric_merge", "start_time", "end_time", "step", "space_uid"):
        assert actual[field] == exported[field]
    if calculation_type == "exception_rate":
        assert actual["metric_merge"] == ("(a or b < bool 0) / b" if for_service_list else "a / b")
        total_conditions = actual["query_list"][1]["conditions"]["field_list"]
        assert ({"field_name": "status_code", "op": "ncontains", "value": [""]} in total_conditions) == for_service_list
    assert config["expression"] == raw["expression"]
    for panel, q in zip(config["query_configs"], raw["query_configs"]):
        assert panel["agg_dimension"] == q["group_by"] == group_by
        assert panel["agg_interval"] == q["interval"] == 120
        assert "filter_dict" not in q
        assert panel["agg_condition"] == q["where"]
        assert panel["functions"] == q["functions"]
        assert panel["metric_field"] == q["metrics"][0]["field"]
        assert panel["agg_method"] == q["metrics"][0]["method"] == "SUM"
        assert panel["alias"] == q["metrics"][0]["alias"]
    assert raw["start_time"] == START_TIME * 1000
    expected_end = time_interval_align(END_TIME, 120) if calculation_type == "avg_duration" else END_TIME
    assert raw["end_time"] == expected_end * 1000


@pytest.mark.parametrize(
    "kind,kinds", [(CallSide.CALLER.value, SpanKind.calling_kinds()), (CallSide.CALLEE.value, SpanKind.called_kinds())]
)
@pytest.mark.parametrize("calculation_type", ["request_total", "exception_rate", "avg_duration"])
def test_subqueries_preserve_service_kind_and_filters(calculation_type: str, kind: str, kinds: list[int]) -> None:
    group = make_group(
        ["service_name", "db_system"],
        service_name="collector",
        kind=kind,
        filter_dict={"db_system__neq": [""], "service_name__eq": ["collector"]},
        interval=60,
    )
    config = group.query_config(calculation_type, raw=True)
    for query in config["query_configs"]:
        conditions = filter_dict_to_conditions(query.get("filter_dict", {}), query["where"])
        assert {"key": "db_system", "method": "neq", "value": [""]} in conditions
        assert any(c["key"] == "service_name" and c["value"] == ["collector"] for c in conditions)
        assert any(c["key"] == "kind" and set(c["value"]) == {str(k) for k in kinds} for c in conditions)
        assert query["time_field"] == "time"


@pytest.mark.parametrize("offset", [0, 13, 59])
@pytest.mark.parametrize("interval", [60, 120])
def test_average_duration_preserves_precision_and_excludes_aligned_end(
    uq_query: Mock, offset: int, interval: int
) -> None:
    start = time_interval_align(START_TIME, interval) + offset
    end = start + 3600
    aligned_start = time_interval_align(start, interval)
    aligned_end = time_interval_align(end, interval)
    uq_query.return_value = {
        "series": [
            {
                "columns": ["_time", "_value"],
                "types": ["time", "double"],
                "group_keys": ["service_name"],
                "group_values": ["collector"],
                "values": [
                    [aligned_start + interval, 1.123456789],
                    [aligned_end - interval, 2.987654321],
                    [aligned_end, 999],
                ],
            },
            {
                "columns": ["_time", "_value"],
                "types": ["time", "double"],
                "group_keys": ["service_name"],
                "group_values": ["query"],
                "values": [[aligned_start + interval, 0], [aligned_end, 999]],
            },
            {
                "columns": ["_time", "_value"],
                "types": ["time", "double"],
                "group_keys": ["service_name"],
                "group_values": ["transfer"],
                "values": [],
            },
        ]
    }
    group = make_group(["service_name"], interval=interval)

    result = group.handle("avg_duration", start_time=start, end_time=end)

    assert result == [
        {"service_name": "collector", "_result_": 1.123456789, "_time_": (aligned_start + interval) * 1000},
        {"service_name": "collector", "_result_": 2.987654321, "_time_": (aligned_end - interval) * 1000},
        {"service_name": "query", "_result_": 0, "_time_": (aligned_start + interval) * 1000},
    ]
    params = uq_query.call_args.kwargs
    assert params["start_time"] == str(aligned_start)
    assert params["end_time"] == str(aligned_end)
    assert params["metric_merge"] == "(a or vector(0)) / (b != 0)"
    for query in params["query_list"]:
        assert query["time_aggregation"]["window"] == f"{interval}s"


def test_average_duration_keeps_zero_time_fallback(mocker: MockerFixture, uq_query: Mock) -> None:
    now = END_TIME + 17
    mocker.patch("bkmonitor.data_source.unify_query.query.time.time", return_value=now)
    group = make_group(["service_name"], interval=60)

    group.handle("avg_duration", start_time=0, end_time=3600)

    assert uq_query.call_args.kwargs["start_time"] == str(time_interval_align(now - 3600, 60))
    assert uq_query.call_args.kwargs["end_time"] == str(time_interval_align(now, 60))
    config = group.query_config("avg_duration", raw=True, start_time=1, end_time=50)
    assert config["start_time"] == 1000
    assert config["end_time"] == 50000


@pytest.mark.parametrize("calculation_type", ["error_count", "p50_duration", "p95_duration", "p99_duration"])
def test_existing_panel_metrics_remain_exportable(calculation_type: str) -> None:
    group = make_group(["service_name"])
    assert group.query_config(calculation_type)["query_configs"]
    assert group.query_config(calculation_type, raw=True)["query_configs"]


def test_unsupported_calculation_fails_before_query(uq_query: Mock) -> None:
    group = make_group(["service_name"])
    with pytest.raises(ValueError, match="Unsupported range calculation type"):
        group.handle("unsupported", start_time=START_TIME, end_time=END_TIME)
    with pytest.raises(ValueError, match="Unsupported calculation type"):
        group.query_config("unsupported")
    uq_query.assert_not_called()


@pytest.mark.parametrize("calculation_type", ["request_total", "exception_rate", "avg_duration"])
def test_handle_returns_query_records_without_graph_formatting(uq_query: Mock, calculation_type: str) -> None:
    timestamp = time_interval_align(START_TIME, 120) + 120
    uq_query.return_value = {
        "series": [
            {
                "columns": ["_time", "_value"],
                "types": ["time", "double"],
                "group_keys": ["service_name"],
                "group_values": ["collector"],
                "values": [[timestamp, 0.123456789]],
            }
        ]
    }

    records = make_group(["service_name"]).handle(calculation_type, start_time=START_TIME, end_time=END_TIME)

    assert records == [{"service_name": "collector", "_time_": timestamp * 1000, "_result_": 0.123456789}]


@pytest.mark.parametrize("calculation_type", ["request_total", "exception_rate", "avg_duration"])
def test_trace_chart_target_preserves_exported_filters(calculation_type: str) -> None:
    group = make_group(["service_name"], service_name="collector", kind=CallSide.CALLER.value)
    config = group.query_config(calculation_type, raw=True)

    target = TraceChartsResource.build_target(config, "demo", alias="metric")
    serializer = GraphUnifyQueryResource.RequestSerializer(
        data={
            **target["data"]["unify_query_param"],
            "bk_biz_id": 2,
            "start_time": START_TIME,
            "end_time": END_TIME,
        }
    )
    serializer.is_valid(raise_exception=True)

    assert serializer.validated_data["expression"] == config["expression"]
    for exported, actual, expected in zip(
        target["data"]["query_configs"], serializer.validated_data["query_configs"], config["query_configs"]
    ):
        assert "filter_dict" not in exported
        assert any(
            c["key"] == "service_name" and c["method"] == "eq" and c["value"] == ["collector"]
            for c in exported["where"]
        )
        assert actual["where"] == expected["where"]
        assert actual["metrics"] == [{**metric, "display": False} for metric in expected["metrics"]]


def test_trace_error_rate_keeps_all_calls_in_denominator(mocker: MockerFixture) -> None:
    app = Application(bk_biz_id=2, app_name="demo")
    mocker.patch.object(Application.objects, "get", return_value=app)

    panels = TraceChartsResource().request({"bk_biz_id": 2, "app_name": "demo", "service_name": "collector"})
    [data] = [
        target["data"] for panel in panels for target in panel["targets"] if target["data"].get("unit") == "percentunit"
    ]

    # 图表展示与实际取数使用的两份配置都保持 Trace 原有口径。
    for config in (data, data["unify_query_param"]):
        assert config["expression"] == "a / b"
        error, total = config["query_configs"]
        assert total["where"] == [{"key": "service_name", "method": "eq", "value": ["collector"]}]
        assert {"condition": "and", "key": "status_code", "method": "eq", "value": ["2"]} in error["where"]
