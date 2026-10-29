import datetime

import pytest

from apm.core.discover.precalculation.storage import PrecalculateStorage, RendezvousHash
from apm.core.handlers.query.base import FakeQuery
from apm.core.handlers.query.define import QueryMode
from apm.core.handlers.query.proxy import QueryProxy, _get_app_meta
from apm.core.handlers.query.span_query import SpanQuery
from apm.models import TraceDataSource
from apm.tests.trace_switch_history import EXCLUSIVE_RT, SHARED_RT, T1, T2
from bkmonitor.data_source.utils.apm import TraceDatasourceTarget
from metadata.models import ESStorage

pytestmark = pytest.mark.django_db(databases="__all__")


@pytest.fixture(autouse=True)
def fixed_now(mocker):
    now = datetime.datetime.fromtimestamp(T2 + 86400)
    mocker.patch("bkmonitor.data_source.utils.query.datetime.datetime").now.return_value = now


@pytest.fixture
def history():
    return [
        {"table_id": EXCLUSIVE_RT, "switched_at": T1, "retention": 14},
        {"table_id": SHARED_RT, "switched_at": T2, "retention": 7},
    ]


@pytest.fixture
def proxy(history, mocker):
    mocker.patch(
        "apm.core.handlers.query.proxy._get_app_meta",
        return_value={
            "bk_biz_id": 2,
            "app_name": "demo",
            "table_id": EXCLUSIVE_RT,
            "retention": 7,
            "history_link_info": history,
        },
    )
    return QueryProxy(2, "demo")


@pytest.fixture
def span_query(proxy):
    return proxy.span_query


@pytest.mark.parametrize(
    ("start", "end", "tables"),
    [
        (T1 - 3600, T1 - 1801, [EXCLUSIVE_RT]),
        (T1 - 1800, T1 - 1800, [EXCLUSIVE_RT, SHARED_RT]),
        (T1, T1 + 1800, [EXCLUSIVE_RT, SHARED_RT]),
        (T1 + 1801, T2 - 1801, [SHARED_RT]),
        (T2 - 1800, T2 - 1800, [SHARED_RT, EXCLUSIVE_RT]),
        (T2 + 1800, T2 + 1800, [SHARED_RT, EXCLUSIVE_RT]),
        (T2 + 1801, T2 + 3600, [EXCLUSIVE_RT]),
        (T1 - 3600, T2 + 3600, [EXCLUSIVE_RT, SHARED_RT]),
    ],
)
def test_query_routes_by_switch_window_then_deduplicates(history, proxy, start, end, tables):
    assert TraceDataSource.get_query_table_ids(EXCLUSIVE_RT, history, start, end) == tables
    query = proxy._get_query(QueryMode.SPAN, start, end)
    assert [q.query.table_name for q in query.build_queries()] == tables


def test_historical_shared_table_keeps_application_filter(span_query):
    queries = span_query.build_queries()
    assert "bk_biz_id" not in str(queries[0].query.where)
    assert "bk_biz_id__eq" in str(queries[1].query.where)
    assert "app_name__eq" in str(queries[1].query.where)
    assert "demo" in str(queries[1].query.where)


def test_span_list_preserves_user_time_range_and_pagination(proxy, mocker):
    span_query = proxy._get_query(QueryMode.SPAN, T1 + 1801, T2 - 1801)
    query = mocker.patch("bkmonitor.data_source.unify_query.builder.QueryHelper.query", return_value=[])
    assert span_query.query_list(T1 + 1801, T2 - 1801, 10, 20) == []
    body = query.call_args.kwargs["query_body"]
    assert [q["table"] for q in body["query_configs"]] == [SHARED_RT]
    assert (body["start_time"], body["end_time"]) == ((T1 + 1801) * 1000, (T2 - 1801) * 1000)
    assert (body["offset"], body["limit"]) == (10, 20)


def test_trace_detail_reads_both_rts_and_keeps_trace_filter(span_query, mocker):
    query = mocker.patch("bkmonitor.data_source.unify_query.builder.QueryHelper.query", return_value=[])
    span_query.query_by_trace_id("trace-1", T1 - 60, T1 + 60)
    body = query.call_args.kwargs["query_body"]
    assert [q["table"] for q in body["query_configs"]] == [EXCLUSIVE_RT, SHARED_RT]
    for config in body["query_configs"]:
        assert config["time_field"] == "start_time"
        assert "trace-1" in str(config["filter_dict"])


def test_default_range_preserves_longer_historical_retention(span_query):
    assert span_query.retention == 14


def test_shared_rt_for_two_apps_is_not_deduplicated_across_apps():
    query = SpanQuery([TraceDatasourceTarget.build(2, app, SHARED_RT, retention=7) for app in ("demo", "another")])
    queries = query.build_queries()
    assert len(queries) == 2
    assert queries[0].query.where != queries[1].query.where


def test_query_proxy_loads_history_from_metadata(exclusive, history, datasource_apis):
    exclusive.history_link_info = history
    exclusive.save()
    _get_app_meta.cache_clear()
    try:
        targets = QueryProxy(2, "demo").span_query.data_sources
        assert {target.table_id for target in targets} == {EXCLUSIVE_RT, SHARED_RT}
        assert all(not hasattr(target, "history_link_info") for target in targets)
    finally:
        _get_app_meta.cache_clear()


@pytest.fixture
def uq_request(mocker):
    mocker.patch("bkmonitor.data_source.unify_query.query.bk_biz_id_to_space_uid", return_value="bkcc__2")
    mocker.patch("bkmonitor.data_source.unify_query.query.UnifyQuery.use_unify_query", return_value=True)
    return mocker.patch("bkmonitor.data_source.unify_query.query.api.unify_query.query_raw")


@pytest.mark.parametrize("sort,order_by", [("end_time desc", "-end_time"), ("attributes.score", "attributes.score")])
def test_uq_list_sends_both_rts_with_global_pagination(span_query, uq_request, sort, order_by):
    uq_request.return_value = {"list": [{"span_id": "new"}, {"span_id": "old"}]}
    records = span_query.query_list(T1 - 60, T2 + 60, 10, 2, sort=[sort])
    uq_request.assert_called_once()
    params = uq_request.call_args.kwargs
    assert [q["table_id"] for q in params["query_list"]] == [EXCLUSIVE_RT, SHARED_RT]
    assert params["order_by"] == [order_by]
    assert all("attributes" not in q["keep_columns"] for q in params["query_list"])
    assert (params["_from"], params["limit"]) == (10, 2)
    assert (params["start_time"], params["end_time"]) == (str(T1 - 60), str(T2 + 60))
    assert "demo" in str(params["query_list"][1])
    assert "bk_biz_id" in str(params["query_list"][1])
    assert [row["span_id"] for row in records] == ["new", "old"]
    assert all("attributes" not in row for row in records)


def test_uq_group_list_passes_collapse_for_both_rts(span_query, uq_request):
    uq_request.return_value = {"list": [{"trace_id": "new"}, {"trace_id": "old"}]}
    records = span_query.query_group_list(T1 - 60, T2 + 60, "trace_id", offset=1, limit=2)
    uq_request.assert_called_once()
    params = uq_request.call_args.kwargs
    assert [q["table_id"] for q in params["query_list"]] == [EXCLUSIVE_RT, SHARED_RT]
    assert all(q["collapse"] == {"field": "trace_id"} for q in params["query_list"])
    assert (params["_from"], params["limit"]) == (1, 2)
    assert params["order_by"] == ["-end_time"]
    assert [row["trace_id"] for row in records] == ["new", "old"]


def test_uq_history_failure_is_propagated(span_query, uq_request):
    uq_request.side_effect = RuntimeError("historical RT unavailable")
    with pytest.raises(RuntimeError, match="historical RT unavailable"):
        span_query.query_list(T1 - 60, T2 + 60, 0, 20)
    uq_request.assert_called_once()


@pytest.mark.parametrize(
    ("start", "end", "shared", "exclusive"),
    [
        (T1 - 3600, T1 - 1801, False, True),
        (T1 + 1801, T2 - 1801, True, False),
        (T2 + 1801, T2 + 3600, False, True),
        (T1 - 60, T2 + 60, True, True),
    ],
)
def test_trace_list_routes_precalculation_history(history, proxy, mocker, start, end, shared, exclusive):
    ring = RendezvousHash([f"1-precalculate.trace_{i}" for i in range(10)])
    old_table = ring.select_node("2:demo").split("-", 1)[-1]
    shared_table = ring.select_node(f"0:{SHARED_RT}").split("-", 1)[-1]
    assert old_table != shared_table

    storage = PrecalculateStorage.__new__(PrecalculateStorage)
    storage.bk_biz_id, storage.app_name, storage.hash_ring, storage.is_valid = 2, "demo", ring, True
    storage_factory = mocker.patch("apm.core.handlers.query.proxy.PrecalculateStorage", return_value=storage)
    trace_query = proxy._get_query(QueryMode.TRACE, start, end)
    queries = trace_query.build_queries()
    assert {q.query.table_name for q in queries} == (
        ({old_table} if exclusive else set()) | ({shared_table} if shared else set())
    )
    for query in queries:
        assert "biz_id__eq" in str(query.query.where)
        assert "app_name__eq" in str(query.query.where)
        assert "demo" in str(query.query.where)
    # 复用存储环，但不能缓存上一次时间范围的选表结果。
    middle = proxy._get_query(QueryMode.TRACE, T1 + 1801, T2 - 1801)
    assert [q.query.table_name for q in middle.build_queries()] == [shared_table]
    storage_factory.assert_called_once()
    # 查询上下文的预计算路由不回写到持久化切换记录。
    assert all("levels" not in link for link in history)


def test_explicit_precalculation_table_keeps_relation_query_scope(proxy):
    query = proxy._get_trace_query("precalculate.relation")
    assert [q.query.table_name for q in query.build_queries()] == ["precalculate.relation"]


def test_proxy_selects_sources_for_each_request(proxy):
    old = proxy._get_query(QueryMode.SPAN, T1 - 3600, T1 - 1801)
    middle = proxy._get_query(QueryMode.SPAN, T1 + 1801, T2 - 1801)
    assert [target.table_id for target in old.data_sources] == [EXCLUSIVE_RT]
    assert [target.table_id for target in middle.data_sources] == [SHARED_RT]
    assert [target.table_id for target in old.data_sources] == [EXCLUSIVE_RT]


def test_trace_id_search_expands_history_after_resetting_time(proxy, mocker):
    request = mocker.patch("bkmonitor.data_source.unify_query.builder.QueryHelper.query", return_value=[])
    proxy.query_list(
        QueryMode.SPAN,
        T1 + 1801,
        T2 - 1801,
        20,
        0,
        filters=[{"key": "trace_id", "operator": "equal", "value": ["trace-1"]}],
    )
    assert {q["table"] for q in request.call_args.kwargs["query_body"]["query_configs"]} == {EXCLUSIVE_RT, SHARED_RT}


@pytest.fixture
def exclusive_query_storage(exclusive, mocker):
    ESStorage.objects.create(table_id=EXCLUSIVE_RT, storage_cluster_id=1, retention=7)
    ESStorage.objects.create(table_id="precalculate.trace", storage_cluster_id=1, retention=7)
    mocker.patch.object(
        PrecalculateStorage,
        "fetch_cluster_simple_infos",
        return_value=[{"table_name": "precalculate.trace", "cluster_id": 1}],
    )
    _get_app_meta.cache_clear()
    yield
    _get_app_meta.cache_clear()


@pytest.mark.parametrize(
    ("mode", "cold_queries", "new_proxy_queries", "table_id"),
    [
        (QueryMode.SPAN, 2, 0, EXCLUSIVE_RT),
        (QueryMode.ORIGIN_TRACE, 2, 0, EXCLUSIVE_RT),
        (QueryMode.TRACE, 4, 2, "precalculate.trace"),
    ],
)
def test_exclusive_query_db_cost_matches_single_table_path(
    exclusive_query_storage, django_assert_num_queries, mode, cold_queries, new_proxy_queries, table_id
):
    # 仅替换集群发现；应用元数据、保留期和预计算表均执行真实 ORM 查询。
    proxy = QueryProxy(2, "demo")
    with django_assert_num_queries(cold_queries):
        first = proxy._get_query(mode, T1, T2)
        assert [q.query.table_name for q in first.build_queries()] == [table_id]
    with django_assert_num_queries(0):
        for start, end in ((T1 + 1, T2), (T1, T2 + 1)):
            query = proxy._get_query(mode, start, end)
            assert query.data_sources == first.data_sources
        cached_query = getattr(proxy, f"{mode}_query")
        assert cached_query.data_sources == first.data_sources
    with django_assert_num_queries(new_proxy_queries):
        assert QueryProxy(2, "demo")._get_query(mode).data_sources == first.data_sources


@pytest.mark.parametrize("retention", [None, 0, 7])
def test_exclusive_target_preserves_retention_without_history_selection(mocker, retention):
    mocker.patch(
        "apm.core.handlers.query.proxy._get_app_meta",
        return_value={"table_id": EXCLUSIVE_RT, "retention": retention, "history_link_info": []},
    )
    select = mocker.patch.object(TraceDataSource, "get_query_table_ids", side_effect=AssertionError("不要选历史表"))
    targets = QueryProxy(2, "demo")._build_data_sources(start_time=T1, end_time=T2)
    assert targets == [TraceDatasourceTarget.build(2, "demo", EXCLUSIVE_RT, retention=retention)]
    select.assert_not_called()


def test_invalid_precalculation_keeps_fake_query_without_loading_metadata(mocker):
    storage = mocker.patch("apm.core.handlers.query.proxy.PrecalculateStorage")
    storage.return_value.is_valid = False
    meta = mocker.patch("apm.core.handlers.query.proxy._get_app_meta", side_effect=ValueError("未配置数据源"))
    proxy = QueryProxy(2, "demo")
    assert isinstance(proxy._get_query(QueryMode.TRACE, T1, T2), FakeQuery)
    assert proxy.is_trace_query_valid is False
    storage.assert_called_once()
    meta.assert_not_called()


@pytest.mark.parametrize("shared", [False, True])
def test_existing_precalculation_route_uses_shared_flag(exclusive, shared_pool, shared):
    # 现有写入路由继续以共享标记为准，不因历史查询新增的表名前缀判断而改变。
    exclusive.result_table_id = EXCLUSIVE_RT if shared else SHARED_RT
    exclusive.shared_datasource_id = shared_pool.pk if shared else None
    exclusive.save()
    expected_key = f"0:{EXCLUSIVE_RT}" if shared else "2:demo"
    assert PrecalculateStorage.get_route_key(2, "demo") == expected_key
