import copy
import gzip
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.test import RequestFactory
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response

from apm.core.handlers.query.span_query import SpanQuery
from apm_web.handlers.trace_handler.base import TraceHandler
from apm_web.trace.diagram.base import TreeBuildingConfig
from apm_web.trace.diagram.topo import TopoNode, trace_data_to_topo_data
from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder, UnifyQuerySet
from constants.data_source import DataSourceLabel, DataTypeLabel
from monitor_api.middlewares import MonitorAPIMiddleware

from .utils import read_trace_list


def test_compact_groups_send_each_member_list_once() -> None:
    spans = copy.deepcopy(read_trace_list("simple"))
    result = TraceHandler.handle_trace("app", spans, spans[0]["trace_id"], {}, compact_groups=True)
    groups = [span["group_info"] for span in result["trace_tree"]["spans"] if span.get("group_info")]
    assert len(groups) == 3
    assert sum(len(group["members"]) for group in groups) == 3
    assert len({group["id"] for group in groups}) == 1
    assert len({group["duration"] for group in groups}) == 1

    full = TraceHandler.handle_trace("app", spans, spans[0]["trace_id"], {})
    full_groups = [span["group_info"] for span in full["trace_tree"]["spans"] if span.get("group_info")]
    assert all(len(group["members"]) == 3 for group in full_groups)
    assert result["trace_info"] == full["trace_info"]
    assert len(result["original_data"]) == len(spans)


@pytest.mark.parametrize("reduce_details", [None, False, True])
def test_trace_resource_compacts_group_members_only_when_requested(reduce_details: bool | None) -> None:
    from apm_web.trace.resources import TraceDetailResource

    spans: list[dict] = copy.deepcopy(read_trace_list("simple"))
    parameters: dict = {"bk_biz_id": 2, "app_name": "app", "trace_id": spans[0]["trace_id"]}
    if reduce_details is not None:
        parameters["reduce_span_details"] = reduce_details
    with (
        patch("apm_web.trace.resources.get_llm_entity_set", return_value=None),
        patch(
            "apm_web.trace.resources.api.apm_api.query_trace_detail",
            return_value={"trace_data": spans, "relation_mapping": {}, "options": {}},
        ),
        patch("apm_web.trace.diagram.config.DiagramConfigController.read", return_value=None),
    ):
        result: dict = TraceDetailResource().request(parameters)

    groups = [span["group_info"] for span in result["trace_tree"]["spans"] if span.get("group_info")]
    members = {span["spanID"] for span in result["trace_tree"]["spans"] if span.get("group_info")}
    assert len(groups) == len(members) == 3
    assert all(not group["members"] or set(group["members"]) == members for group in groups)
    assert sum(bool(group["members"]) for group in groups) == (1 if reduce_details else 3)


def test_trace_original_timestamps_are_preserved_without_copying_attributes() -> None:
    spans = copy.deepcopy(read_trace_list("simple"))
    root = next(span for span in spans if not span["parent_span_id"])
    child = next(span for span in spans if span["parent_span_id"] == root["span_id"])
    root["kind"] = 3
    child["kind"] = 2
    child["start_time"] = root["start_time"] - 10
    child["end_time"] = root["start_time"] - 5
    original_start = child["start_time"]
    result = TraceHandler.handle_trace("app", spans, spans[0]["trace_id"], {}, enabled_time_alignment=True)
    originals = {span["span_id"]: span for span in result["original_data"]}
    displayed = {span["spanID"]: span for span in result["trace_tree"]["spans"]}
    assert originals[child["span_id"]]["start_time"] == original_start
    assert displayed[child["span_id"]]["startTime"] == root["start_time"]
    for span in spans:
        original = originals[span["span_id"]]
        assert original is not span
        assert original["attributes"] is span["attributes"]
        assert original["status"] is not span["status"]


@pytest.mark.parametrize("span_count", [500, 501])
@pytest.mark.parametrize("reduce_details", [None, False, True])
def test_trace_resource_defers_large_trace_details_only_when_requested(
    span_count: int, reduce_details: bool | None
) -> None:
    from apm_web.trace.resources import SpanDetailResource, TraceDetailResource

    template: dict = copy.deepcopy(read_trace_list("simple")[0])
    spans: list[dict] = []
    for index in range(span_count):
        span: dict = copy.deepcopy(template)
        span["span_id"] = f"{index + 1:016x}"
        span["parent_span_id"] = "0000000000000001" if index else ""
        spans.append(span)
    full: dict = TraceHandler.handle_trace(
        "app", copy.deepcopy(spans), template["trace_id"], {}, compact_groups=bool(reduce_details)
    )
    with (
        patch("apm_web.trace.resources.get_llm_entity_set", return_value=None),
        patch(
            "apm_web.trace.resources.api.apm_api.query_trace_detail",
            return_value={"trace_data": spans, "relation_mapping": {}, "options": {}},
        ),
        patch("apm_web.trace.resources.api.apm_api.query_span_detail", return_value=spans[0]),
        patch("apm_web.trace.diagram.config.DiagramConfigController.read", return_value=None),
    ):
        parameters: dict = {"bk_biz_id": 2, "app_name": "app", "trace_id": template["trace_id"]}
        if reduce_details is not None:
            parameters["reduce_span_details"] = reduce_details
        serializer = TraceDetailResource.RequestSerializer(data=parameters)
        serializer.is_valid(raise_exception=True)
        result: dict = TraceDetailResource().perform_request(serializer.validated_data)
        restored: dict = SpanDetailResource().perform_request(
            {"bk_biz_id": 2, "app_name": "app", "span_id": spans[0]["span_id"]}
        )
    assert result["trace_info"] == full["trace_info"]
    assert len(result["original_data"]) == len(result["trace_tree"]["spans"]) == span_count
    for actual, expected in zip(result["trace_tree"]["spans"], full["trace_tree"]["spans"], strict=True):
        for field in ("spanID", "operationName", "startTime", "duration", "references", "group_info"):
            assert actual.get(field) == expected.get(field)
        assert bool(actual["attributes"]) is not (bool(reduce_details) and span_count > 500)
    if reduce_details and span_count > 500:
        assert all(not span["attributes"] and not span["events"] for span in result["original_data"])
        assert all(not process["tags"] for process in result["trace_tree"]["processes"].values())
        assert result["original_data"][0]["resource"] == {"service.name": template["resource"]["service.name"]}
    else:
        assert result["original_data"] == full["original_data"]
    assert restored["origin_data"] == spans[0]
    assert restored["trace_tree"]["spans"][0]["attributes"] == full["trace_tree"]["spans"][0]["attributes"]
    assert spans[0]["attributes"] == template["attributes"]
    assert spans[0]["resource"] == template["resource"]


@pytest.mark.parametrize("reduce_details", [False, True])
def test_cross_app_and_llm_details_are_independent_of_large_trace_opt_in(reduce_details: bool) -> None:
    spans: list[dict] = copy.deepcopy(read_trace_list("simple"))
    spans[0]["app_name"] = "other-app"
    spans[1]["bk_biz_id"] = 3
    spans[2]["llm_detail"] = {"span_type": "LLM"}
    deferred: set[str] = TraceHandler.get_deferred_span_ids(spans, 2, "app", reduce_span_details=reduce_details)
    assert deferred == {span["span_id"] for span in spans[:3]}
    compact: dict = TraceHandler.handle_trace("app", spans, spans[0]["trace_id"], {}, detail_span_ids=deferred)
    TraceHandler.sanitize_span_details(compact, 2, "app", detail_span_ids=deferred)
    for span in compact["trace_tree"]["spans"]:
        assert bool(span["attributes"]) is (span["spanID"] not in deferred)
    for span in compact["original_data"]:
        assert bool(span["attributes"]) is (span["span_id"] not in deferred)


def test_large_trace_preserves_virtual_details_without_storage_lookup() -> None:
    virtual: dict = copy.deepcopy(read_trace_list("simple")[0])
    virtual["is_virtual"] = True
    spans: list[dict] = [{"span_id": str(index)} for index in range(501)] + [virtual]
    assert virtual["span_id"] not in TraceHandler.get_deferred_span_ids(spans, 2, "app", reduce_span_details=True)
    converted: dict = TraceHandler._convert_span("app", virtual, defer_details=True)
    assert converted["attributes"]


def test_large_trace_keeps_existing_llm_and_cross_app_selection_without_opt_in() -> None:
    spans = [{"span_id": str(index)} for index in range(501)]
    spans[0]["llm_detail"] = {"span_type": "LLM"}
    spans[1]["app_name"] = "other-app"
    assert TraceHandler.get_deferred_span_ids(spans, 2, "app") == {"0", "1"}


def test_trace_query_keeps_single_page_limit() -> None:
    query = SpanQuery([SimpleNamespace(app=SimpleNamespace(bk_biz_id=2, app_name="app"))])
    guarded = (
        QueryConfigBuilder((DataTypeLabel.LOG, DataSourceLabel.BK_APM)).table("2_trace.app").filter(app_name__eq="app")
    )
    records: list[dict] = [{"start_time": 100, "span_id": str(index)} for index in range(2)]
    with (
        patch.object(query, "build_queries", return_value=[guarded]),
        patch.object(query, "get_qs", return_value=UnifyQuerySet().scope(2)),
        patch("bkmonitor.data_source.unify_query.builder.QueryHelper.query", return_value=records) as request,
    ):
        assert query.query_by_trace_id("trace-id", 100, 200, limit=2) == records
    request.assert_called_once()
    assert request.call_args.kwargs["query_body"]["limit"] == 2
    assert request.call_args.kwargs["query_body"]["order_by"] == ["start_time"]


@pytest.mark.parametrize("prefix", [False, True])
def test_cross_trace_query_keeps_single_page_and_deduplication(prefix: bool) -> None:
    query = SpanQuery([SimpleNamespace(app=SimpleNamespace(bk_biz_id=2, app_name="app"))])
    table: str = "PREFIX#2_bkapm.trace_" if prefix else "2_bkapm.trace_app"
    first: dict = {"start_time": 100, "span_id": "a"}
    second: dict = {"start_time": 100, "span_id": "b"}
    with (
        patch.object(query, "get_qs", return_value=UnifyQuerySet().scope(2)),
        patch(
            "bkmonitor.data_source.unify_query.builder.QueryHelper.query",
            return_value=[first, first, second],
        ) as request,
    ):
        if prefix:
            spans = query.prefix_query_by_trace_id("trace-id", 100, 200)
        else:
            spans = query.cross_query_by_trace_id("trace-id", table, 100, 200)
    assert spans == [first, second]
    request.assert_called_once()
    assert request.call_args.kwargs["query_body"]["order_by"] == ["start_time"]
    assert table in str(request.call_args.kwargs["query_body"])


def test_topology_builds_each_grouped_subtree_once() -> None:
    spans = copy.deepcopy(read_trace_list("grouping_same_children", category="topo"))
    config = TreeBuildingConfig(min_group_members=2, with_group=True)
    with patch.object(TopoNode, "from_group", wraps=TopoNode.from_group) as build_group:
        result = trace_data_to_topo_data(spans, config)
    assert len(result["nodes"]) == 7
    assert len(result["relations"]) == 6
    assert build_group.call_count == sum(node["collapsed"] for node in result["nodes"])


def test_topology_preserves_virtual_return_branches() -> None:
    spans = copy.deepcopy(read_trace_list("virtual_return_cache_collision", category="topo"))
    config = TreeBuildingConfig(
        with_group=True, group_ignore_sequence=True, with_virtual_return=True, min_group_spans_count=0
    )
    result = trace_data_to_topo_data(spans, config)
    assert len(result["nodes"]) == 7
    assert len(result["relations"]) == 6
    assert "0000000000000015" in {node["id"] for node in result["nodes"]}


def test_trace_span_query_preserves_app_scope_without_batch_opt_in() -> None:
    source = SimpleNamespace(app=SimpleNamespace(bk_biz_id=2, app_name="app"))
    query = SpanQuery([source])
    guarded = (
        QueryConfigBuilder((DataTypeLabel.LOG, DataSourceLabel.BK_APM)).table("2_trace.app").filter(app_name__eq="app")
    )
    with (
        patch.object(query, "build_queries", return_value=[guarded]),
        patch.object(query, "get_qs", return_value=UnifyQuerySet().scope(2).start_time(100000).end_time(200000)),
        patch("bkmonitor.data_source.unify_query.builder.QueryHelper.query", return_value=[]) as request,
    ):
        assert query.query_by_trace_id("trace-id", 100, 200) == []
    body = request.call_args.kwargs["query_body"]
    assert body["is_es_batch"] is False
    assert body["bk_biz_id"] == 2
    assert "app_name" in str(body["query_configs"][0]["filter_dict"])
    assert "trace-id" in str(body["query_configs"][0]["filter_dict"])


@pytest.mark.parametrize("endpoint", ["trace_detail", "span_detail"])
@pytest.mark.parametrize("ajax", [False, True])
@pytest.mark.parametrize("accept_encoding", ["", "br", "gzip, deflate, br", "gzip;q=0", "gzip;q=0.5", "gzip;q=invalid"])
def test_detail_gzip_requires_frontend_request_and_negotiation(endpoint: str, ajax: bool, accept_encoding: str) -> None:
    from apm_web.trace.views import TraceQueryViewSet

    route = next(route for route in TraceQueryViewSet.resource_routes if route.endpoint == endpoint)
    assert not route.content_encoding
    payload = {"trace_id": "trace-id", "spans": [{"span_id": "span-id"}] * 100}
    raw = JSONRenderer().render(payload)
    response = Response(payload)
    request = RequestFactory().post(
        f"/{endpoint}/",
        HTTP_ACCEPT_ENCODING=accept_encoding,
        HTTP_X_REQUESTED_WITH="XMLHttpRequest" if ajax else "",
    )
    request.accepted_renderer = JSONRenderer()
    request.accepted_media_type = "application/json"
    view = TraceQueryViewSet()
    view.action = endpoint
    view.headers = {}
    response = view.finalize_response(request, response)
    response.render()
    compressed = MonitorAPIMiddleware(lambda request: response).process_response(request, response)
    assert {"X-Requested-With", "Accept-Encoding"} <= set(compressed["Vary"].split(", "))
    if ajax and accept_encoding in {"gzip, deflate, br", "gzip;q=0.5"}:
        assert compressed["Content-Encoding"] == "gzip"
        assert len(compressed.content) < len(raw)
        assert int(compressed["Content-Length"]) == len(compressed.content)
        assert gzip.decompress(compressed.content) == raw
    else:
        assert not compressed.has_header("Content-Encoding")
        assert compressed.content == raw
