import copy
from collections.abc import Iterator
from typing import Any
from unittest.mock import Mock

import pytest

from apm_web.trace import resources
from apm_web.trace.resources import ListTraceResource
from bkmonitor.data_source.utils.apm import LogicSupportOperator
from constants.apm import TraceListQueryMode


def build_query_data(filters: list[dict[str, Any]], query: str = "") -> dict[str, Any]:
    return {
        "bk_biz_id": 2,
        "app_name": "demo",
        "start_time": 1_787_821_414,
        "end_time": 1_787_825_014,
        "offset": 0,
        "limit": 10,
        "query": query,
        "filters": filters,
        "sort": [],
    }


def mock_trace_list_api(monkeypatch: pytest.MonkeyPatch, responses: Iterator[dict[str, Any]]) -> list[dict[str, Any]]:
    requests: list[dict[str, Any]] = []

    def query_trace_list(params: dict[str, Any]) -> dict[str, Any]:
        requests.append(copy.deepcopy(params))
        return next(responses)

    monkeypatch.setattr(resources.api.apm_api, "query_trace_list", query_trace_list)
    monkeypatch.setattr(ListTraceResource, "burial_point", Mock())
    return requests


@pytest.mark.parametrize(
    "precalculation_data",
    [
        pytest.param([], id="empty-list"),
        pytest.param(None, id="fake-query-none"),
    ],
)
def test_error_logic_filter_falls_back_to_origin_when_precalculation_is_empty(
    monkeypatch: pytest.MonkeyPatch, precalculation_data: list[dict[str, Any]] | None
) -> None:
    responses: Iterator[dict[str, Any]] = iter(
        [
            {"data": precalculation_data, "total": 0},
            {"data": [{"trace_id": "error-trace", "error": True}], "total": 0},
        ]
    )
    requests = mock_trace_list_api(monkeypatch, responses)

    response = ListTraceResource().get_trace_list_api_data(
        build_query_data([{"key": "error", "operator": LogicSupportOperator.LOGIC, "value": []}])
    )

    assert response["type"] == TraceListQueryMode.ORIGIN
    assert response["data"] == [{"trace_id": "error-trace", "error": True}]
    assert [request["query_mode"] for request in requests] == [
        TraceListQueryMode.PRE_CALCULATION,
        TraceListQueryMode.ORIGIN,
    ]
    assert requests[1]["filters"] == [{"key": "error", "operator": LogicSupportOperator.LOGIC, "value": []}]


def test_error_logic_filter_keeps_non_empty_precalculation_result(monkeypatch: pytest.MonkeyPatch) -> None:
    responses: Iterator[dict[str, Any]] = iter([{"data": [{"trace_id": "error-trace", "error": True}], "total": 0}])
    requests = mock_trace_list_api(monkeypatch, responses)

    response = ListTraceResource().get_trace_list_api_data(
        build_query_data([{"key": "error", "operator": LogicSupportOperator.LOGIC, "value": []}])
    )

    assert response["type"] == TraceListQueryMode.PRE_CALCULATION
    assert [request["query_mode"] for request in requests] == [TraceListQueryMode.PRE_CALCULATION]


@pytest.mark.parametrize(
    "filters",
    [
        [{"key": "error", "operator": "equal", "value": ["true"]}],
        [
            {"key": "error", "operator": LogicSupportOperator.LOGIC, "value": []},
            {"key": "error_count", "operator": "equal", "value": ["1"]},
        ],
    ],
)
def test_origin_incompatible_filter_does_not_fall_back(
    monkeypatch: pytest.MonkeyPatch, filters: list[dict[str, Any]]
) -> None:
    responses: Iterator[dict[str, Any]] = iter([{"data": [], "total": 0}])
    requests = mock_trace_list_api(monkeypatch, responses)

    response = ListTraceResource().get_trace_list_api_data(build_query_data(filters))

    assert response["type"] == TraceListQueryMode.PRE_CALCULATION
    assert [request["query_mode"] for request in requests] == [TraceListQueryMode.PRE_CALCULATION]


def test_error_query_does_not_fall_back_without_origin_equivalent_mapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses: Iterator[dict[str, Any]] = iter([{"data": [], "total": 0}])
    requests = mock_trace_list_api(monkeypatch, responses)

    response = ListTraceResource().get_trace_list_api_data(
        build_query_data(
            [{"key": "error", "operator": LogicSupportOperator.LOGIC, "value": []}],
            query="error: true",
        )
    )

    assert response["type"] == TraceListQueryMode.PRE_CALCULATION
    assert [request["query_mode"] for request in requests] == [TraceListQueryMode.PRE_CALCULATION]
