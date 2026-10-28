import datetime
from unittest.mock import PropertyMock

import pytest

from apm.core.discover.precalculation.storage import RendezvousHash
from apm.core.handlers.query.proxy import QueryProxy, _get_app_meta
from apm.core.handlers.query.span_query import SpanQuery
from apm.core.handlers.query.trace_query import TraceQuery
from apm.models import TraceDataSource
from apm.models.shared_datasource import SharedTraceDataSource
from bkmonitor.data_source.utils.apm import LevelTarget, TraceDatasourceTarget

pytestmark = pytest.mark.django_db(databases="__all__")

EXCLUSIVE_RT = "2_bkapm.trace_demo"
SHARED_RT = "apm_global.shared_trace_0001"
T1 = 1_800_000_000
T2 = T1 + 7200


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
def span_query(history):
    return SpanQuery([TraceDatasourceTarget.build(2, "demo", EXCLUSIVE_RT, retention=7, history_link_info=history)])


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
def test_query_routes_by_switch_window_then_deduplicates(span_query, start, end, tables):
    queries = span_query.build_queries(start_time=start, end_time=end)
    assert [q.query.table_name for q in queries] == tables


def test_historical_shared_table_keeps_application_filter(span_query):
    queries = span_query.build_queries(start_time=T1 - 3600, end_time=T2 + 3600)
    assert "bk_biz_id" not in str(queries[0].query.where)
    assert "bk_biz_id__eq" in str(queries[1].query.where)
    assert "app_name__eq" in str(queries[1].query.where)
    assert "demo" in str(queries[1].query.where)


def test_span_list_preserves_user_time_range_and_pagination(span_query, mocker):
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


def test_no_history_preserves_single_table_query():
    query = SpanQuery([TraceDatasourceTarget.build(2, "demo", EXCLUSIVE_RT, retention=7)])
    assert [q.query.table_name for q in query.build_queries()] == [EXCLUSIVE_RT]
    assert query.retention == 7


def test_default_range_preserves_longer_historical_retention(span_query):
    assert span_query.retention == 14


def test_shared_rt_for_two_apps_is_not_deduplicated_across_apps():
    query = SpanQuery([TraceDatasourceTarget.build(2, app, SHARED_RT, retention=7) for app in ("demo", "another")])
    queries = query.build_queries()
    assert len(queries) == 2
    assert queries[0].query.where != queries[1].query.where


def test_precalculated_trace_query_does_not_expand_raw_history(history):
    query = TraceQuery(
        [
            TraceDatasourceTarget.build(
                2,
                "demo",
                EXCLUSIVE_RT,
                retention=7,
                history_link_info=history,
                levels=[LevelTarget("trace", ["precalculated.trace"])],
            )
        ]
    )
    assert [q.query.table_name for q in query.build_queries(start_time=T1, end_time=T2)] == ["precalculated.trace"]


@pytest.fixture
def datasource_apis(mocker):
    mocker.patch.object(TraceDataSource, "retention", new_callable=PropertyMock, return_value=7)
    mocker.patch("apm.models.datasource.bk_biz_id_to_bk_tenant_id", return_value="default")
    mocker.patch("apm.models.datasource.get_global_user", return_value="admin")
    mocker.patch.object(TraceDataSource, "_should_enable_bkdata_datalink", return_value=False)
    mocker.patch.object(TraceDataSource, "_build_result_table_option", return_value={})
    mocker.patch(
        "apm.models.datasource.api.metadata.query_cluster_info",
        return_value=[{"cluster_config": {"custom_option": "{}"}}],
    )
    return {
        "modify": mocker.patch("apm.models.datasource.resource.metadata.modify_result_table", create=True),
        "create_rt": mocker.patch("apm.models.datasource.resource.metadata.create_result_table", create=True),
        "create_index": mocker.patch(
            "apm.models.datasource.api.log_search.create_index_set",
            return_value={"index_set_id": 22, "index_set_name": "new-index"},
        ),
        "update_index": mocker.patch(
            "apm.models.datasource.api.log_search.update_index_set",
            return_value={"index_set_id": 11, "index_set_name": "old-index"},
        ),
        "delete_index": mocker.patch("apm.models.datasource.api.log_search.delete_index_set"),
        "datalink": mocker.patch.object(TraceDataSource, "apply_datalink"),
    }


@pytest.fixture
def exclusive(db):
    return TraceDataSource.objects.create(
        bk_biz_id=2,
        app_name="demo",
        bk_data_id=101,
        result_table_id=EXCLUSIVE_RT,
        index_set_id=11,
        index_set_name="old-index",
        bkdata_datalink_config={"version": 4},
    )


@pytest.fixture
def shared_pool(db):
    return SharedTraceDataSource.objects.create(
        bk_data_id=201,
        result_table_id=SHARED_RT,
        is_enabled=True,
        usage_count=0,
        index_set_id=21,
        index_set_name="shared-index",
        bkdata_datalink_config={"version": 4},
    )


def test_exclusive_shared_exclusive_round_trip(exclusive, shared_pool, datasource_apis, mocker):
    clock = mocker.patch("apm.models.datasource.time.time", return_value=T1)
    TraceDataSource.apply_datasource(2, "demo", option=True, is_shared=True, es_storage_cluster=1)
    exclusive.refresh_from_db()
    shared_pool.refresh_from_db()
    assert exclusive.result_table_id == SHARED_RT
    assert shared_pool.usage_count == 1
    assert exclusive.backup_link_info["index_set_id"] == 11
    datasource_apis["modify"].assert_not_called()
    datasource_apis["delete_index"].assert_not_called()

    # 同模式重试不重复记录历史，也不重复占用共享池。
    TraceDataSource.apply_datasource(2, "demo", option=True, is_shared=True, es_storage_cluster=1)
    exclusive.refresh_from_db()
    shared_pool.refresh_from_db()
    assert len(exclusive.history_link_info) == 1
    assert shared_pool.usage_count == 1

    clock.return_value = T2
    TraceDataSource.apply_datasource(2, "demo", option=True, is_shared=False, es_storage_cluster=1)
    exclusive.refresh_from_db()
    shared_pool.refresh_from_db()
    assert exclusive.result_table_id == EXCLUSIVE_RT
    assert exclusive.bk_data_id == 101
    assert exclusive.shared_datasource_id is None
    assert exclusive.index_set_id == 11
    assert exclusive.bkdata_datalink_config == {"version": 4}
    assert exclusive.history_link_info == [
        {"table_id": EXCLUSIVE_RT, "switched_at": T1, "retention": 7},
        {"table_id": SHARED_RT, "switched_at": T2, "retention": 7},
    ]
    assert shared_pool.usage_count == 0
    assert shared_pool.is_enabled
    datasource_apis["delete_index"].assert_not_called()
    datasource_apis["create_index"].assert_not_called()
    datasource_apis["update_index"].assert_called_once()
    assert datasource_apis["update_index"].call_args.kwargs["index_set_id"] == 11
    params = datasource_apis["modify"].call_args.args[0]
    assert params["table_id"] == EXCLUSIVE_RT
    assert params["is_enable"] is True


def test_migration_failure_rolls_back_history_and_pool(exclusive, shared_pool, datasource_apis):
    TraceDataSource.apply_datasource(2, "demo", option=True, is_shared=True, es_storage_cluster=1)
    exclusive.refresh_from_db()
    old_history = exclusive.history_link_info
    datasource_apis["modify"].side_effect = RuntimeError("target unavailable")
    with pytest.raises(RuntimeError, match="target unavailable"):
        TraceDataSource.apply_datasource(2, "demo", option=True, is_shared=False, es_storage_cluster=1)
    exclusive.refresh_from_db()
    shared_pool.refresh_from_db()
    assert exclusive.result_table_id == SHARED_RT
    assert exclusive.history_link_info == old_history
    assert shared_pool.usage_count == 1


def test_legacy_backup_without_index_is_supported(exclusive, shared_pool, datasource_apis):
    exclusive.shared_datasource_id = shared_pool.pk
    exclusive.result_table_id = SHARED_RT
    exclusive.backup_link_info = {"bk_data_id": 101, "result_table_id": EXCLUSIVE_RT, "bkdata_datalink_config": {}}
    exclusive.save()
    TraceDataSource.apply_datasource(2, "demo", option=True, is_shared=False, es_storage_cluster=1)
    exclusive.refresh_from_db()
    assert exclusive.result_table_id == EXCLUSIVE_RT
    assert exclusive.index_set_id == 22
    datasource_apis["create_index"].assert_called_once()
    datasource_apis["delete_index"].assert_not_called()


def test_explicit_stop_still_disables_exclusive_rt(exclusive, datasource_apis):
    TraceDataSource.stop(2, "demo")
    assert datasource_apis["modify"].call_args.args[0]["is_enable"] is False
    datasource_apis["delete_index"].assert_called_once_with(index_set_id=11)
    exclusive.refresh_from_db()
    assert exclusive.history_link_info == []


def test_query_proxy_loads_history_from_metadata(exclusive, history, datasource_apis):
    exclusive.history_link_info = history
    exclusive.save()
    _get_app_meta.cache_clear()
    try:
        target = QueryProxy(2, "demo").span_query.data_sources[0]
        assert target.history_link_info == history
    finally:
        _get_app_meta.cache_clear()


@pytest.mark.parametrize(
    ("sort", "expected"),
    [("end_time desc", [4, 3, 2]), ("end_time", [3, 4, 5])],
)
def test_multi_rt_list_sorts_before_global_pagination(span_query, mocker, sort, expected):
    rows = {EXCLUSIVE_RT: [1, 3, 5], SHARED_RT: [2, 4, 6]}

    def query_records(*, query_body, **kwargs):
        assert query_body["offset"] == 0
        assert query_body["limit"] == 5
        assert (query_body["start_time"], query_body["end_time"]) == ((T1 - 60) * 1000, (T2 + 60) * 1000)
        table = query_body["query_configs"][0]["table"]
        return [{"end_time": value} for value in sorted(rows[table], reverse=sort.endswith("desc"))]

    query = mocker.patch("bkmonitor.data_source.unify_query.builder.QueryHelper.query", side_effect=query_records)
    records = span_query.query_list(T1 - 60, T2 + 60, 2, 3, sort=[sort])
    assert [row["end_time"] for row in records] == expected
    assert query.call_count == 2


def test_multi_rt_group_list_deduplicates_before_pagination(span_query, mocker):
    rows = {
        EXCLUSIVE_RT: [{"trace_id": "same", "end_time": 6}, {"trace_id": "old", "end_time": 4}],
        SHARED_RT: [{"trace_id": "same", "end_time": 5}, {"trace_id": "new", "end_time": 3}],
    }
    mocker.patch(
        "bkmonitor.data_source.unify_query.builder.QueryHelper.query",
        side_effect=lambda *, query_body, **kwargs: rows[query_body["query_configs"][0]["table"]],
    )
    records = span_query.query_group_list(T1 - 60, T2 + 60, "trace_id", offset=1, limit=2)
    assert [row["trace_id"] for row in records] == ["old", "new"]


def test_multi_rt_list_supports_object_fields_and_secondary_sort(span_query, mocker):
    rows = {
        EXCLUSIVE_RT: [{"resource": {"service.name": "b"}, "end_time": 1}, {"end_time": 100}],
        SHARED_RT: [
            {"resource": {"service.name": "a"}, "end_time": 3},
            {"resource": {"service.name": "b"}, "end_time": 2},
        ],
    }
    mocker.patch(
        "bkmonitor.data_source.unify_query.builder.QueryHelper.query",
        side_effect=lambda *, query_body, **kwargs: rows[query_body["query_configs"][0]["table"]],
    )
    records = span_query.query_list(T1 - 60, T2 + 60, 0, 4, sort=["resource.service.name", "end_time desc"])
    assert [row["end_time"] for row in records] == [3, 2, 1, 100]


def test_history_query_failure_is_not_silently_returned_as_partial_page(span_query, mocker):
    def query_records(*, query_body, **kwargs):
        if query_body["query_configs"][0]["table"] == EXCLUSIVE_RT:
            raise RuntimeError("historical RT unavailable")
        return [{"end_time": 1}]

    mocker.patch("bkmonitor.data_source.unify_query.builder.QueryHelper.query", side_effect=query_records)
    with pytest.raises(RuntimeError, match="historical RT unavailable"):
        span_query.query_list(T1 - 60, T2 + 60, 0, 20)


@pytest.fixture
def new_data_id(mocker):
    return mocker.patch(
        "apm.models.datasource.resource.metadata.query_data_source", return_value={"bk_data_id": 301}, create=True
    )


def test_migration_into_new_shared_pool(exclusive, datasource_apis, new_data_id):
    TraceDataSource.apply_datasource(2, "demo", option=True, is_shared=True, es_storage_cluster=1)
    exclusive.refresh_from_db()
    shared = SharedTraceDataSource.objects.get(pk=exclusive.shared_datasource_id)
    assert shared.is_enabled and shared.usage_count == 1
    assert shared.result_table_id == exclusive.result_table_id
    assert shared.bk_data_id == exclusive.bk_data_id == 301
    assert exclusive.history_link_info[0]["table_id"] == EXCLUSIVE_RT
    params = datasource_apis["create_rt"].call_args.args[0]
    assert params["is_enable"] is True
    assert params["bk_biz_id_alias"] == "bk_biz_id"
    assert params["table_id"] == shared.result_table_id
    datasource_apis["modify"].assert_not_called()
    datasource_apis["delete_index"].assert_not_called()


def test_first_shared_to_exclusive_creates_target(db, shared_pool, datasource_apis, new_data_id):
    shared_pool.usage_count = 1
    shared_pool.save()
    app_source = TraceDataSource.objects.create(
        bk_biz_id=2,
        app_name="demo",
        bk_data_id=201,
        result_table_id=SHARED_RT,
        shared_datasource_id=shared_pool.pk,
        index_set_id=21,
    )
    TraceDataSource.apply_datasource(2, "demo", option=True, is_shared=False, es_storage_cluster=1)
    app_source.refresh_from_db()
    shared_pool.refresh_from_db()
    assert not app_source.is_shared
    assert app_source.result_table_id == app_source.table_id
    assert app_source.bk_data_id == 301
    assert app_source.index_set_id == 22
    assert app_source.history_link_info[0]["table_id"] == SHARED_RT
    assert shared_pool.is_enabled and shared_pool.usage_count == 0
    assert datasource_apis["create_rt"].call_args.args[0]["is_enable"] is True
    datasource_apis["modify"].assert_not_called()
    datasource_apis["delete_index"].assert_not_called()


def test_new_pool_creation_failure_preserves_exclusive_source(exclusive, datasource_apis, new_data_id):
    datasource_apis["create_rt"].side_effect = RuntimeError("create failed")
    with pytest.raises(RuntimeError, match="create failed"):
        TraceDataSource.apply_datasource(2, "demo", option=True, is_shared=True, es_storage_cluster=1)
    exclusive.refresh_from_db()
    assert exclusive.result_table_id == EXCLUSIVE_RT
    assert exclusive.bk_data_id == 101
    assert exclusive.history_link_info == []
    assert not SharedTraceDataSource.objects.exists()
    datasource_apis["modify"].assert_not_called()
    datasource_apis["delete_index"].assert_not_called()


def test_uq_query_reaches_old_and_new_rt_with_application_isolation(span_query, mocker):
    mocker.patch("bkmonitor.data_source.unify_query.query.bk_biz_id_to_space_uid", return_value="bkcc__2")
    mocker.patch("bkmonitor.data_source.unify_query.query.UnifyQuery.use_unify_query", return_value=True)

    def query_raw(**params):
        query = params["query_list"][0]
        assert params["order_by"] == ["-end_time"]
        assert params["_from"] == 0
        assert params["limit"] == 2
        if query["table_id"] == EXCLUSIVE_RT:
            return {"list": [{"span_id": "old", "end_time": 1}]}
        assert query["table_id"] == SHARED_RT
        assert "demo" in str(query)
        assert "bk_biz_id" in str(query)
        return {"list": [{"span_id": "new", "end_time": 2}]}

    request = mocker.patch("bkmonitor.data_source.unify_query.query.api.unify_query.query_raw", side_effect=query_raw)
    records = span_query.query_list(T1 - 60, T2 + 60, 0, 2)
    assert [row["span_id"] for row in records] == ["new", "old"]
    assert request.call_count == 2


@pytest.mark.parametrize(
    ("start", "end", "shared", "exclusive"),
    [
        (T1 - 3600, T1 - 1801, False, True),
        (T1 + 1801, T2 - 1801, True, False),
        (T2 + 1801, T2 + 3600, False, True),
        (T1 - 60, T2 + 60, True, True),
    ],
)
def test_trace_list_routes_precalculation_history(history, mocker, start, end, shared, exclusive):
    ring = RendezvousHash([f"1-precalculate.trace_{i}" for i in range(10)])
    old_table = ring.select_node("2:demo").split("-", 1)[-1]
    shared_table = ring.select_node(f"0:{SHARED_RT}").split("-", 1)[-1]
    assert old_table != shared_table
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
    trace_query = QueryProxy(2, "demo")._get_trace_query(old_table, ring)
    queries = trace_query.build_queries(start_time=start, end_time=end)
    assert {q.query.table_name for q in queries} == (
        ({old_table} if exclusive else set()) | ({shared_table} if shared else set())
    )
    for query in queries:
        assert "biz_id__eq" in str(query.query.where)
        assert "app_name__eq" in str(query.query.where)
        assert "demo" in str(query.query.where)
    # 查询上下文的预计算路由不回写到持久化切换记录。
    assert all("levels" not in link for link in history)


def test_explicit_precalculation_table_keeps_relation_query_scope(history, mocker):
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
    query = QueryProxy(2, "demo")._get_trace_query("precalculate.relation")
    assert [q.query.table_name for q in query.build_queries(start_time=T1 + 1801, end_time=T2 - 1801)] == [
        "precalculate.relation"
    ]
