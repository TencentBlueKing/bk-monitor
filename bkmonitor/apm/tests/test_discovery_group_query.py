from types import SimpleNamespace
from typing import Any
from unittest import mock

import pytest

from apm.core.discover.base import TopoHandler
from apm.core.discover.exceptions import IncompleteDiscoveryError
from apm.core.discover.log.service import ServiceDiscover as LogDiscover
from apm.core.discover.node import NodeDiscover
from apm.core.discover.relation import RelationDiscover
from apm.core.handlers.query.span_query import SpanQuery
from apm.models import ApmApplication, ApmTopoDiscoverRule, TopoNode
from apm.resources import QueryTopoNodeResource
from bkmonitor.data_source.exceptions import IncompleteQueryResultError
from bkmonitor.data_source.data_source import (
    BkApmTraceDataSource,
    LogSearchLogDataSource,
    LogSearchTimeSeriesDataSource,
)
from apm.tests.test_service_heartbeat import datasource, make_node
from apm.tests.test_toponode_discover import build_other_span_without_platform, build_rules
from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder, UnifyQuerySet
from bkmonitor.data_source.unify_query.query import UnifyQuery
from bkmonitor.data_source.utils.query import BaseQuery
from constants.data_source import DataSourceLabel, DataTypeLabel


pytestmark = pytest.mark.django_db(databases="__all__")


def test_log_query_uses_index_set_collapse_and_descending_time() -> None:
    with mock.patch("bkmonitor.data_source.unify_query.builder.QueryHelper.query", return_value=[]) as query:
        LogDiscover(datasource()).discover(100, 200)
    assert query.call_count == 2
    for call, field in zip(query.call_args_list, ["resource.service.name", "resource.server"]):
        body = call.kwargs["query_body"]
        assert (body["bk_biz_id"], body["start_time"], body["end_time"]) == (2, 100000, 200000)
        config = body["query_configs"][0]
        assert config["table"] == "123"
        assert config["index_set_id"] == 123
        assert config["distinct"] == field
        assert config["time_field"] == "time"
        assert body["order_by"] == ["-time"]
        assert body["limit"] == BaseQuery.QUERY_MAX_LIMIT


@pytest.mark.parametrize("rows", [[], [{"resource.service.name": "demo", "time": 150000}]])
def test_collapsed_raw_query_rejects_partial_routes(rows: list[dict[str, Any]]) -> None:
    query = UnifyQuery(2, [], "a", bk_tenant_id="system")
    with (
        mock.patch.object(
            query, "get_unify_query_params", return_value={"query_list": [{"collapse": {"field": "service"}}]}
        ),
        mock.patch(
            "bkmonitor.data_source.unify_query.query.api.unify_query.query_raw",
            return_value={"list": rows, "status": {"code": "QUERY_RAW_PARTIAL", "message": "one route failed"}},
        ),
        pytest.raises(IncompleteQueryResultError),
    ):
        query._query_log_using_unify_query(100000, 200000, limit=10000)


@pytest.mark.parametrize("status", [None, {"code": "SPACE_TABLE_ID_FIELD_MISSING_FALLBACK", "message": "fallback"}])
def test_collapsed_raw_query_accepts_empty_results_and_non_failure_status(status: Any) -> None:
    query = UnifyQuery(2, [], "a", bk_tenant_id="system")
    with (
        mock.patch.object(
            query, "get_unify_query_params", return_value={"query_list": [{"collapse": {"field": "service"}}]}
        ),
        mock.patch.object(query, "process_log_by_datasource", side_effect=lambda rows: rows),
        mock.patch(
            "bkmonitor.data_source.unify_query.query.api.unify_query.query_raw",
            return_value={"list": [], "status": status},
        ),
    ):
        assert query._query_log_using_unify_query(100000, 200000, limit=10000) == []


def test_noncollapsed_raw_query_keeps_partial_result_behavior() -> None:
    query = UnifyQuery(2, [], "a", bk_tenant_id="system")
    with (
        mock.patch.object(query, "get_unify_query_params", return_value={"query_list": [{}]}),
        mock.patch.object(query, "process_log_by_datasource", side_effect=lambda rows: rows),
        mock.patch(
            "bkmonitor.data_source.unify_query.query.api.unify_query.query_raw",
            return_value={"list": [{"service": "demo"}], "status": {"code": "QUERY_RAW_PARTIAL"}},
        ),
    ):
        assert query._query_log_using_unify_query(100000, 200000)[0]["service"] == "demo"


def test_span_group_query_preserves_complete_records_and_existing_guards() -> None:
    span = {"span_id": "last", "end_time": 190000000, "attributes": {"db.system": "mysql"}}
    query = SpanQuery([])
    guarded = (
        QueryConfigBuilder((DataTypeLabel.LOG, DataSourceLabel.BK_APM)).table("2_trace.app").filter(app_name__eq="app")
    )
    with (
        mock.patch.object(query, "build_queries", return_value=[guarded]),
        mock.patch.object(query, "get_qs", return_value=UnifyQuerySet().scope(2).start_time(100000).end_time(200000)),
        mock.patch("bkmonitor.data_source.unify_query.builder.QueryHelper.query", return_value=[span]) as request,
    ):
        assert query.query_group_list(100, 200, "resource.service.name") == [span]
    body = request.call_args.kwargs["query_body"]
    config = body["query_configs"][0]
    assert config["distinct"] == "resource.service.name"
    assert body["order_by"] == ["-end_time"]
    assert config["select"] == []
    assert "app_name" in str(config["filter_dict"])


@pytest.mark.parametrize("failure", [None, "query", "discovery"])
def test_trace_fallback_discovers_sparse_service_before_heartbeat(failure: str | None) -> None:
    handler = object.__new__(TopoHandler)
    handler.bk_biz_id = 2
    handler.app_name = "app"
    last_span = {"resource": {"service.name": "sparse"}, "end_time": 190000000, "kind": 2, "attributes": {"a": "b"}}
    old = make_node("old", heartbeat={"trace": {"last_data_at": 80, "checked_at": 90}})

    def discover(spans: list[dict[str, Any]], template: list[Any]) -> bool:
        assert spans == [last_span]
        if failure == "discovery":
            return False
        make_node("sparse", source=["trace"])
        return True

    with (
        mock.patch.object(handler, "_get_trace_task_splits", return_value=(100, 1, "table")),
        mock.patch.object(handler, "list_trace_ids", return_value=[]),
        mock.patch("apm.core.discover.base.DiscoverContainer.list_discovers", return_value=[]),
        mock.patch.object(TopoHandler, "_trace_target", new_callable=mock.PropertyMock, return_value=SimpleNamespace()),
        mock.patch("apm.core.discover.base.SpanQuery") as query,
        mock.patch.object(handler, "_discover_spans", side_effect=discover),
    ):
        query.return_value.query_group_list.side_effect = RuntimeError("query failed") if failure == "query" else None
        query.return_value.query_group_list.return_value = [last_span]
        if failure:
            with pytest.raises((RuntimeError, IncompleteDiscoveryError)):
                handler.discover()
            assert not TopoNode.objects.filter(topo_key="sparse").exists()
        else:
            handler.discover()
            assert TopoNode.objects.get(topo_key="sparse").heartbeat["trace"]["last_data_at"] == 190
        call = query.return_value.query_group_list.call_args
        assert call.args[1] - call.args[0] == 600
    old.refresh_from_db()
    assert old.heartbeat == {"trace": {"last_data_at": 80, "checked_at": 90}}


def test_log_discovery_consumes_flat_uq_records_and_sends_collapse() -> None:
    with (
        mock.patch.object(UnifyQuery, "use_unify_query", return_value=True),
        mock.patch(
            "bkmonitor.data_source.unify_query.query.api.unify_query.query_raw",
            side_effect=[
                {"list": [{"resource.service.name": "demo", "time": 150000}]},
                {"list": [{"resource.server": "demo", "time": 180000}]},
            ],
        ) as request,
        mock.patch.object(TopoNode, "get_empty_extra_data", return_value={"kind": "service"}),
    ):
        LogDiscover(datasource()).discover(100, 200)
    assert TopoNode.objects.get(topo_key="demo").heartbeat["log"]["last_data_at"] == 180
    for call, field in zip(request.call_args_list, ["resource.service.name", "resource.server"]):
        params = call.kwargs
        assert params["limit"] == 10000
        assert params["order_by"] == ["-time"]
        assert params["query_list"][0]["collapse"] == {"field": field}
        assert params["query_list"][0]["table_id"] == "bklog_index_set_123"


@pytest.mark.parametrize(
    "failure", [RuntimeError("query failed"), {"list": [], "status": {"code": "QUERY_RAW_PARTIAL"}}]
)
def test_log_second_uq_failure_does_not_publish_first_field(failure: Any) -> None:
    old = make_node(heartbeat={"log": {"last_data_at": 80, "checked_at": 90}})
    with (
        mock.patch.object(UnifyQuery, "use_unify_query", return_value=True),
        mock.patch(
            "bkmonitor.data_source.unify_query.query.api.unify_query.query_raw",
            side_effect=[
                {"list": [{"resource.service.name": "new", "time": 150000}]},
                failure,
            ],
        ),
        pytest.raises((ValueError, RuntimeError)),
    ):
        LogDiscover(datasource()).discover(100, 200)
    old.refresh_from_db()
    assert old.heartbeat == {"log": {"last_data_at": 80, "checked_at": 90}}
    assert TopoNode.objects.count() == 1


@pytest.mark.parametrize(
    "results,expected", [([True, False], True), ([False, True], False), ([RuntimeError(), True], False)]
)
def test_fallback_dispatch_requires_only_node_discovery(results: list[Any], expected: bool) -> None:
    handler = object.__new__(TopoHandler)
    all_spans = SimpleNamespace(DISCOVERY_ALL_SPANS=True, model=TopoNode)
    filtered_spans = SimpleNamespace(DISCOVERY_ALL_SPANS=False, model=None)
    spans = [{"kind": 1}, {"kind": 2}]
    template = [(all_spans, None, "topo", {}), (filtered_spans, None, "topo", {})]
    with mock.patch("apm.core.discover.base.ThreadPool") as pool:
        executor = pool.return_value.__enter__.return_value
        executor.map_ignore_exception.return_value = results
        assert handler._discover_spans(spans, template) is expected
        params = executor.map_ignore_exception.call_args.args[1]
        assert params[0][1] == spans
        assert params[1][1] == [{"kind": 2}]
        assert executor.map_ignore_exception.call_args.kwargs["return_exception"] is True
        pool.return_value.__exit__.assert_called_once()


def test_disabled_profiling_only_hides_profile_only_nodes(settings) -> None:
    settings.USE_TZ = False
    app = ApmApplication.objects.create(bk_biz_id=2, app_name="app", is_enabled_profiling=True)
    for name, source in [("profile", ["profiling"]), ("log", ["log"]), ("mixed", ["profiling", "log"]), ("old", [])]:
        make_node(name, source=source)
    resource = QueryTopoNodeResource()
    params = {"bk_biz_id": 2, "app_name": "app"}
    assert {node["topo_key"] for node in resource.perform_request(params)} == {"profile", "log", "mixed", "old"}
    app.is_enabled_profiling = False
    app.save(update_fields=["is_enabled_profiling"])
    assert {node["topo_key"] for node in resource.perform_request(params)} == {"log", "mixed", "old"}
    assert resource.perform_request({**params, "topo_key": "profile"}) == []
    assert TopoNode.objects.filter(topo_key="profile").exists()


def test_blacklisted_collapse_fails_without_bypassing_routing(settings) -> None:
    settings.LOG_UNIFY_QUERY_BLACK_BIZ_LIST_ENV = [2]
    node = make_node(heartbeat={"log": {"last_data_at": 80, "checked_at": 90}})
    with (
        mock.patch.object(LogSearchTimeSeriesDataSource, "LOG_UNIFY_QUERY_BLACK_BIZ_LIST", None),
        mock.patch("bkmonitor.data_source.unify_query.query.api.unify_query.query_raw") as raw,
        mock.patch("bkmonitor.data_source.data_source.api.log_search.es_query_search") as legacy,
    ):
        ordinary = LogSearchLogDataSource(bk_biz_id=2, table="123", index_set_id=123)
        assert ordinary.switch_unify_query(2) is False
        with pytest.raises(IncompleteQueryResultError, match="excluded"):
            LogDiscover(datasource()).discover(100, 200)
        raw.assert_not_called()
        legacy.assert_not_called()
    node.refresh_from_db()
    assert node.heartbeat == {"log": {"last_data_at": 80, "checked_at": 90}}


@pytest.mark.parametrize("raw_time", [150000, "150000", "1970-01-01T00:02:30Z", "1970-01-01T08:02:30+08:00"])
def test_log_supported_date_representations(raw_time: Any) -> None:
    with (
        mock.patch(
            "bkmonitor.data_source.unify_query.builder.QueryHelper.query",
            side_effect=[[{"resource": {"service.name": "demo"}, "time": raw_time}], []],
        ),
        mock.patch.object(TopoNode, "get_empty_extra_data", return_value={"kind": "service"}),
    ):
        LogDiscover(datasource()).discover(100, 200)
    assert TopoNode.objects.get(topo_key="demo").heartbeat["log"]["last_data_at"] == 150


@pytest.mark.parametrize("raw_time", [None, "bad-time", 150, 999999, float("nan"), float("inf")])
def test_invalid_log_time_keeps_previous_heartbeat(raw_time: Any) -> None:
    node = make_node(heartbeat={"log": {"last_data_at": 80, "checked_at": 90}})
    with (
        mock.patch(
            "bkmonitor.data_source.unify_query.builder.QueryHelper.query",
            return_value=[{"resource": {"service": {"name": "demo"}}, "time": raw_time}],
        ),
        pytest.raises(IncompleteQueryResultError),
    ):
        LogDiscover(datasource()).discover(100, 200)
    node.refresh_from_db()
    assert node.heartbeat == {"log": {"last_data_at": 80, "checked_at": 90}}


def test_trace_windows_use_same_duration() -> None:
    handler = object.__new__(TopoHandler)
    with mock.patch("apm.core.discover.base.constants.DISCOVER_TIME_RANGE", "5m"):
        assert handler._get_after_key_body()["query"]["bool"]["must"]["range"]["time"]["gte"] == "now-5m"


def test_fallback_real_node_creation_survives_relation_failure() -> None:
    handler = object.__new__(TopoHandler)
    handler.bk_biz_id = 2
    handler.app_name = "app"
    raw = build_other_span_without_platform()
    raw.update({f"resource.{key}": value for key, value in raw.pop("resource").items()})
    span = BkApmTraceDataSource(bk_biz_id=2, table="2_trace.app").process_unify_query_log([raw])[0]
    name = span["resource"]["service.name"]

    def execute(func: Any, params: list[Any], **kwargs: Any) -> list[Any]:
        return [func(*args) for args in params]

    with (
        mock.patch.object(handler, "_get_trace_task_splits", return_value=(100, 1, "table")),
        mock.patch.object(handler, "list_trace_ids", return_value=[]),
        mock.patch(
            "apm.core.discover.base.DiscoverContainer.list_discovers", return_value=[NodeDiscover, RelationDiscover]
        ),
        mock.patch.object(TopoHandler, "_trace_target", new_callable=mock.PropertyMock, return_value=SimpleNamespace()),
        mock.patch("apm.core.discover.base.SpanQuery") as query,
        mock.patch("apm.core.discover.base.ThreadPool") as pool,
        mock.patch("apm.core.discover.node.ThreadPool") as node_pool,
        mock.patch.object(ApmTopoDiscoverRule, "get_application_rule", return_value=build_rules()),
        mock.patch.object(NodeDiscover, "clear_expired"),
        mock.patch.object(RelationDiscover, "get_remain_data", return_value={}),
        mock.patch.object(RelationDiscover, "discover", side_effect=RuntimeError("relation unavailable")),
    ):
        query.return_value.query_group_list.return_value = [span]
        pool.return_value.__enter__.return_value.map_ignore_exception.side_effect = execute
        node_pool.return_value.map_ignore_exception.side_effect = execute
        assert handler.discover() is True
    node = TopoNode.objects.get(bk_biz_id=2, app_name="app", topo_key=name)
    assert node.source == ["trace"]
    assert node.heartbeat["trace"]["last_data_at"] == span["end_time"] // 1000000
