from types import SimpleNamespace
from typing import Any
from unittest import mock

import pytest
from pytest_mock import MockerFixture

from apm.core.discover.base import TopoHandler
from apm.core.discover.cached_mixin import CachedDiscoverMixin
from apm.core.discover.host import HostDiscover
from apm.core.discover.log.service import ServiceDiscover as LogDiscover
from apm.core.discover.node import NodeDiscover
from apm.core.discover.relation import RelationDiscover
from apm.core.handlers.query.span_query import SpanQuery
from apm.models import (
    ApmApplication,
    ApmTopoDiscoverRule,
    Endpoint,
    HostInstance,
    RemoteServiceRelation,
    RootEndpoint,
    TopoInstance,
    TopoNode,
    TopoRelation,
    TraceDataSource,
)
from apm.resources import QueryTopoInstanceResource, QueryTopoNodeResource
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
from constants.apm import SpanKind
from constants.data_source import DataSourceLabel, DataTypeLabel
from metadata.models import ESStorage


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


@pytest.mark.parametrize("code", ["QUERY_RAW_PARTIAL", "SPACE_TABLE_ID_FIELD_IS_NOT_EXISTS"])
def test_noncollapsed_raw_query_keeps_status_behavior(code: str) -> None:
    query = UnifyQuery(2, [], "a", bk_tenant_id="system")
    with (
        mock.patch.object(query, "get_unify_query_params", return_value={"query_list": [{}]}),
        mock.patch.object(query, "process_log_by_datasource", side_effect=lambda rows: rows),
        mock.patch(
            "bkmonitor.data_source.unify_query.query.api.unify_query.query_raw",
            return_value={"list": [{"service": "demo"}], "status": {"code": code}},
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


def test_trace_es_query_preserves_collapse_sort_and_time_filter() -> None:
    query = BkApmTraceDataSource._get_queryset(
        bk_tenant_id="system",
        table="2_trace.app",
        where={"app_name__eq": "app"},
        time_field="end_time",
        start_time=100000000,
        end_time=200000000,
        distinct="resource.service.name",
        order_by=["-end_time"],
        limit=10000,
    )
    _, params = query.query.sql_with_params()
    assert params["collapse"] == {"field": "resource.service.name"}
    assert params["sort"] == [{"end_time": "desc"}]
    assert "end_time" in str(params["query"])
    assert "app_name" in str(params["query"])


@pytest.mark.parametrize("failure", [None, "query"])
def test_trace_fallback_discovers_sparse_service_before_heartbeat(failure: str | None) -> None:
    handler = object.__new__(TopoHandler)
    handler.bk_biz_id = 2
    handler.app_name = "app"
    last_span = {"resource": {"service.name": "sparse"}, "end_time": 190000000, "kind": 2, "attributes": {"a": "b"}}
    old = make_node("old", heartbeat={"trace": {"last_data_at": 80, "checked_at": 90}})

    def discover(spans: list[dict[str, Any]], template: list[Any], is_fallback: bool = False) -> None:
        assert spans == [last_span]
        make_node("sparse", source=["trace"])

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
            with pytest.raises(RuntimeError):
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
    "failure",
    [
        RuntimeError("query failed"),
    ],
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


def test_disabled_profiling_keeps_existing_nodes(settings) -> None:
    settings.USE_TZ = False
    app = ApmApplication.objects.create(bk_biz_id=2, app_name="app", is_enabled_profiling=True)
    for name, source in [("profile", ["profiling"]), ("log", ["log"]), ("mixed", ["profiling", "log"]), ("old", [])]:
        make_node(name, source=source)
    resource = QueryTopoNodeResource()
    params = {"bk_biz_id": 2, "app_name": "app"}
    assert {node["topo_key"] for node in resource.perform_request(params)} == {"profile", "log", "mixed", "old"}
    app.is_enabled_profiling = False
    app.save(update_fields=["is_enabled_profiling"])
    assert {node["topo_key"] for node in resource.perform_request(params)} == {"profile", "log", "mixed", "old"}
    assert len(resource.perform_request({**params, "topo_key": "profile"})) == 1
    assert TopoNode.objects.filter(topo_key="profile").exists()


@pytest.mark.parametrize("raw_time", [150000, "150000"])
def test_log_numeric_milliseconds_convert_to_seconds(raw_time: Any) -> None:
    with (
        mock.patch(
            "bkmonitor.data_source.unify_query.builder.QueryHelper.query",
            side_effect=[[{"resource": {"service.name": "demo"}, "time": raw_time}], []],
        ),
        mock.patch.object(TopoNode, "get_empty_extra_data", return_value={"kind": "service"}),
    ):
        LogDiscover(datasource()).discover(100, 200)
    assert TopoNode.objects.get(topo_key="demo").heartbeat["log"]["last_data_at"] == 150


@pytest.mark.parametrize("existing_source", [None, "profiling"])
def test_fallback_real_node_creation_survives_relation_failure(existing_source: str | None, settings) -> None:
    settings.USE_TZ = False
    handler = object.__new__(TopoHandler)
    handler.bk_biz_id = 2
    handler.app_name = "app"
    raw = build_other_span_without_platform()
    raw.update({f"resource.{key}": value for key, value in raw.pop("resource").items()})
    span = BkApmTraceDataSource(bk_biz_id=2, table="2_trace.app").process_unify_query_log([raw])[0]
    name = span["resource"]["service.name"]
    if existing_source:
        make_node(name, source=[existing_source])

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
        pool.return_value.map_ignore_exception.side_effect = execute
        node_pool.return_value.map_ignore_exception.side_effect = execute
        assert handler.discover() is True
    node = TopoNode.objects.get(bk_biz_id=2, app_name="app", topo_key=name)
    assert node.source == ([existing_source, "trace"] if existing_source else ["trace"])
    assert node.heartbeat["trace"]["last_data_at"] == span["end_time"] // 1000000


@pytest.mark.parametrize("code", ["QUERY_RAW_PARTIAL", "SPACE_TABLE_ID_FIELD_IS_NOT_EXISTS"])
def test_collapsed_raw_query_preserves_returned_records(code: str) -> None:
    query = UnifyQuery(2, [], "a", bk_tenant_id="system")
    rows = [{"service": "demo"}]
    with (
        mock.patch.object(
            query, "get_unify_query_params", return_value={"query_list": [{"collapse": {"field": "service"}}]}
        ),
        mock.patch.object(query, "process_log_by_datasource", side_effect=lambda records: records),
        mock.patch(
            "bkmonitor.data_source.unify_query.query.api.unify_query.query_raw",
            return_value={"list": rows, "status": {"code": code}},
        ),
    ):
        assert query._query_log_using_unify_query(100000, 200000) == rows


def test_log_default_count_and_collapse_keep_existing_routing(settings) -> None:
    ordinary = LogSearchLogDataSource(bk_biz_id=2, table="123", index_set_id=123)
    collapsed = LogSearchLogDataSource(bk_biz_id=2, table="123", index_set_id=123, distinct="resource.service.name")
    assert ordinary.metrics == [{"field": "_index", "method": "COUNT"}]
    assert not collapsed.metrics
    settings.LOG_UNIFY_QUERY_BLACK_BIZ_LIST_ENV = [2]
    with mock.patch.object(LogSearchTimeSeriesDataSource, "LOG_UNIFY_QUERY_BLACK_BIZ_LIST", None):
        assert ordinary.switch_unify_query(2) is False
        assert collapsed.switch_unify_query(2) is False


@pytest.fixture
def trace_discovery(mocker: MockerFixture, settings: Any) -> tuple[TopoHandler, mock.MagicMock]:
    settings.USE_TZ = False
    ApmApplication.objects.create(bk_biz_id=2, app_name="app")
    TraceDataSource.objects.create(bk_biz_id=2, app_name="app", result_table_id="2_trace.app")
    ESStorage.objects.create(table_id="2_trace.app", storage_cluster_id=1, retention=7)
    handler = TopoHandler(2, "app")
    mocker.patch.object(handler, "_get_trace_task_splits", return_value=(10000, 1, "table"))
    mocker.patch("apm.core.discover.base.bk_biz_id_to_bk_tenant_id", return_value="system")
    mocker.patch.object(ApmTopoDiscoverRule, "get_application_rule", return_value=build_rules())
    mocker.patch.object(HostDiscover, "list_bk_cloud_id", return_value={})
    # 只隔离原有清理逻辑的时区差异，节点写入、快照读取和缓存刷新均走真实实现。
    mocker.patch.object(CachedDiscoverMixin, "_instance_clear_expired", side_effect=lambda instances: ([], instances))

    def execute(func: Any, params: list[tuple[Any, ...]], **kwargs: Any) -> list[Any]:
        return [func(*args) for args in params]

    mocker.patch("apm.core.discover.base.ThreadPool").return_value.map_ignore_exception.side_effect = execute
    mocker.patch("apm.core.discover.node.ThreadPool").return_value.map_ignore_exception.side_effect = execute
    query = mocker.patch("apm.core.discover.base.SpanQuery").return_value
    return handler, query


def build_trace_span(
    service_name: str,
    trace_id: str,
    span_id: str,
    parent_span_id: str,
    span_name: str,
    start_time: int,
    end_time: int,
    kind: int = SpanKind.SPAN_KIND_SERVER,
) -> dict[str, Any]:
    span = build_other_span_without_platform()
    span.update(
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=parent_span_id,
        span_name=span_name,
        start_time=start_time,
        end_time=end_time,
        elapsed_time=end_time - start_time,
        kind=kind,
    )
    span["resource"].update(
        {"service.name": service_name, "bk.instance.id": f"java:{service_name}:", "net.host.ip": "127.0.0.1"}
    )
    span["attributes"] = {"http.method": "GET"}
    return span


def test_fallback_reuses_objects_created_in_regular_round(
    trace_discovery: tuple[TopoHandler, mock.MagicMock], mocker: MockerFixture
) -> None:
    handler, query = trace_discovery
    root = build_trace_span("front", "trace", "root", "", "GET /entry", 100000000, 150000000)
    client = build_trace_span(
        "front", "trace", "client", "root", "GET /catalog", 110000000, 190000000, SpanKind.SPAN_KIND_CLIENT
    )
    client["attributes"]["peer.service"] = "catalog"
    server = build_trace_span("back", "trace", "server", "client", "GET /catalog", 120000000, 180000000)
    mocker.patch.object(handler, "list_trace_ids", return_value=[["trace"]])
    mocker.patch.object(handler, "list_span_by_trace_ids", return_value=[root, client, server])
    expected_counts = {
        TopoNode: 3,
        Endpoint: 4,
        HostInstance: 2,
        TopoInstance: 2,
        TopoRelation: 2,
        RemoteServiceRelation: 1,
        RootEndpoint: 1,
    }
    discovered_ids: dict[type, set[int]] = {}

    def last_spans(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        for model, count in expected_counts.items():
            assert model.objects.count() == count
            ids = set(model.objects.values_list("id", flat=True))
            assert ids == discovered_ids.setdefault(model, ids)
        return [client, server]

    query.query_group_list.side_effect = last_spans
    for _ in range(2):
        assert handler.discover() is True
        for model, ids in discovered_ids.items():
            assert set(model.objects.values_list("id", flat=True)) == ids
    instances = QueryTopoInstanceResource().perform_request(
        {
            "bk_biz_id": 2,
            "app_name": "app",
            "service_name": [],
            "fields": ["id", "topo_node_key", "instance_id"],
        }
    )
    assert instances["total"] == 2
    assert {item["id"] for item in instances["data"]} == discovered_ids[TopoInstance]
    assert TopoNode.objects.get(topo_key="front").heartbeat["trace"]["last_data_at"] == 190
    assert TopoNode.objects.get(topo_key="back").heartbeat["trace"]["last_data_at"] == 180


def test_fallback_does_not_promote_downstream_endpoint_to_root(
    trace_discovery: tuple[TopoHandler, mock.MagicMock], mocker: MockerFixture
) -> None:
    handler, query = trace_discovery
    root_old = build_trace_span("front", "old", "root-old", "", "GET /entry", 100000000, 150000000)
    downstream = build_trace_span("back", "old", "downstream", "root-old", "GET /downstream", 110000000, 130000000)
    root_new = build_trace_span("front", "new", "root-new", "", "GET /new-entry", 180000000, 190000000)
    mocker.patch.object(handler, "list_trace_ids", return_value=[["old", "new"]])
    mocker.patch.object(handler, "list_span_by_trace_ids", return_value=[root_old, downstream, root_new])
    query.query_group_list.return_value = [root_new, downstream]

    assert handler.discover() is True
    assert set(RootEndpoint.objects.values_list("service_name", "endpoint_name")) == {
        ("front", "GET /entry"),
        ("front", "GET /new-entry"),
    }
    assert RootEndpoint.objects.count() == 2
    assert TopoNode.objects.get(topo_key="back").heartbeat["trace"]["last_data_at"] == 130


def test_fallback_discovers_sparse_service_without_inventing_root(
    trace_discovery: tuple[TopoHandler, mock.MagicMock], mocker: MockerFixture
) -> None:
    handler, query = trace_discovery
    downstream = build_trace_span("back", "trace", "downstream", "upstream", "GET /downstream", 110000000, 130000000)
    mocker.patch.object(handler, "list_trace_ids", return_value=[])
    query.query_group_list.return_value = [downstream]

    assert handler.discover() is True
    node = TopoNode.objects.get(topo_key="back")
    assert node.source == ["trace"]
    assert node.heartbeat["trace"]["last_data_at"] == 130
    assert Endpoint.objects.filter(service_name="back", endpoint_name="GET /downstream").count() == 1
    assert TopoInstance.objects.filter(topo_node_key="back").count() == 1
    assert HostInstance.objects.filter(topo_node_key="back").count() == 1
    assert not RootEndpoint.objects.exists()
