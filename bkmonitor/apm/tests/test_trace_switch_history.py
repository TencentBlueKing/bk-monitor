import datetime
from unittest.mock import PropertyMock

import pytest

from apm.core.discover.precalculation.storage import PrecalculateStorage, RendezvousHash
from apm.core.handlers.query.define import QueryMode
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
                levels=[LevelTarget("trace", ["precalculated.trace"])],
            )
        ]
    )
    assert [q.query.table_name for q in query.build_queries()] == ["precalculated.trace"]


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
        targets = QueryProxy(2, "demo").span_query.data_sources
        assert {target.table_id for target in targets} == {EXCLUSIVE_RT, SHARED_RT}
        assert all(not hasattr(target, "history_link_info") for target in targets)
    finally:
        _get_app_meta.cache_clear()


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
    storage = PrecalculateStorage.__new__(PrecalculateStorage)
    storage.bk_biz_id, storage.app_name, storage.hash_ring, storage.is_valid = 2, "demo", ring, True
    mocker.patch("apm.core.handlers.query.proxy.PrecalculateStorage", return_value=storage)
    trace_query = QueryProxy(2, "demo")._get_query(QueryMode.TRACE, start, end)
    queries = trace_query.build_queries()
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
def second_pool():
    return SharedTraceDataSource.objects.create(
        bk_data_id=202,
        result_table_id="apm_global.shared_trace_0002",
        is_enabled=True,
        usage_count=0,
        quota=2,
        index_set_id=22,
        index_set_name="second-index",
    )


def test_shared_pool_switch_preserves_exclusive_backup_and_history(
    exclusive, shared_pool, second_pool, datasource_apis
):
    for pool in (shared_pool, second_pool, shared_pool):
        TraceDataSource.apply_datasource(
            2,
            "demo",
            option=True,
            is_shared=True,
            shared_datasource_id=pool.pk,
            es_storage_cluster=1,
        )
    exclusive.refresh_from_db()
    shared_pool.refresh_from_db()
    second_pool.refresh_from_db()
    assert exclusive.shared_datasource_id == shared_pool.pk
    assert exclusive.backup_link_info["result_table_id"] == EXCLUSIVE_RT
    assert [link["table_id"] for link in exclusive.history_link_info] == [
        EXCLUSIVE_RT,
        SHARED_RT,
        second_pool.result_table_id,
    ]
    assert (shared_pool.usage_count, second_pool.usage_count) == (1, 0)
    TraceDataSource.apply_datasource(
        2,
        "demo",
        option=True,
        is_shared=True,
        shared_datasource_id=shared_pool.pk,
        es_storage_cluster=1,
    )
    exclusive.refresh_from_db()
    shared_pool.refresh_from_db()
    assert len(exclusive.history_link_info) == 3
    assert shared_pool.usage_count == 1
    datasource_apis["modify"].assert_not_called()
    datasource_apis["delete_index"].assert_not_called()
    TraceDataSource.apply_datasource(2, "demo", option=True, is_shared=False, es_storage_cluster=1)
    exclusive.refresh_from_db()
    assert exclusive.result_table_id == EXCLUSIVE_RT
    assert exclusive.index_set_id == 11


@pytest.mark.parametrize("unavailable", ["disabled", "full", "missing", "race"])
def test_explicit_pool_failure_does_not_fallback_or_release_source(
    exclusive,
    shared_pool,
    second_pool,
    datasource_apis,
    mocker,
    unavailable,
):
    TraceDataSource.apply_datasource(2, "demo", option=True, is_shared=True, es_storage_cluster=1)
    exclusive.refresh_from_db()
    history = exclusive.history_link_info
    target_id = second_pool.pk
    if unavailable == "disabled":
        second_pool.is_enabled = False
        second_pool.save()
    elif unavailable == "full":
        second_pool.usage_count = second_pool.quota
        second_pool.save()
    elif unavailable == "missing":
        target_id = second_pool.pk + 100
    else:
        mocker.patch.object(SharedTraceDataSource, "acquire", return_value=False)
    with pytest.raises(ValueError, match="不可用或容量不足"):
        TraceDataSource.apply_datasource(
            2,
            "demo",
            option=True,
            is_shared=True,
            shared_datasource_id=target_id,
            es_storage_cluster=1,
        )
    exclusive.refresh_from_db()
    shared_pool.refresh_from_db()
    assert exclusive.shared_datasource_id == shared_pool.pk
    assert exclusive.history_link_info == history
    assert shared_pool.usage_count == 1
    assert SharedTraceDataSource.objects.count() == 2
    datasource_apis["create_rt"].assert_not_called()


def test_disabled_pool_cannot_be_acquired(shared_pool):
    SharedTraceDataSource.objects.filter(pk=shared_pool.pk).update(is_enabled=False)
    assert not shared_pool.acquire()
    shared_pool.refresh_from_db()
    assert shared_pool.usage_count == 0


@pytest.fixture
def migration_command():
    from io import StringIO
    from apm.management.commands.migrate_apm_trace_datasource import Command

    return Command(stdout=StringIO())


@pytest.fixture
def migration_context(exclusive):
    from types import SimpleNamespace
    from apm.management.commands.migrate_apm_trace_datasource import TraceDataSourceMigrationContext

    return TraceDataSourceMigrationContext(2, "demo", SimpleNamespace(id=1), exclusive)


def test_batch_plan_balances_only_requested_pools(migration_command, migration_context, shared_pool, second_pool):
    from dataclasses import replace

    shared_pool.quota = 1
    shared_pool.save()
    contexts = [replace(migration_context, app_name=f"app-{i}") for i in range(3)]
    assert migration_command.plan_shared_targets(contexts, [second_pool.pk, shared_pool.pk]) == [
        shared_pool.pk,
        second_pool.pk,
        second_pool.pk,
    ]
    # 预览不占用池配额。
    shared_pool.refresh_from_db()
    second_pool.refresh_from_db()
    assert (shared_pool.usage_count, second_pool.usage_count) == (0, 0)


def test_batch_keeps_apps_already_in_target_pool(migration_command, migration_context, shared_pool):
    migration_context.trace_datasource.shared_datasource_id = shared_pool.pk
    shared_pool.usage_count = shared_pool.quota
    shared_pool.save()
    assert migration_command.plan_shared_targets([migration_context], [shared_pool.pk]) == [shared_pool.pk]


@pytest.mark.parametrize("invalid", ["full", "disabled", "missing_index", "missing"])
def test_batch_preflight_rejects_unavailable_capacity(
    migration_command,
    migration_context,
    shared_pool,
    mocker,
    invalid,
):
    from django.core.management import CommandError

    pool_id = shared_pool.pk
    if invalid == "full":
        shared_pool.usage_count = shared_pool.quota
    elif invalid == "disabled":
        shared_pool.is_enabled = False
    elif invalid == "missing_index":
        shared_pool.index_set_id = None
    else:
        pool_id += 100
    shared_pool.save()
    mocker.patch.object(migration_command, "get_migration_context", return_value=migration_context)
    migrate = mocker.patch.object(migration_command, "migrate_app")
    with pytest.raises(CommandError):
        migration_command.handle(target="shared", apps=["2:demo"], dry_run=False, shared_datasource_ids=[pool_id])
    migrate.assert_not_called()


def test_batch_dry_run_shows_target_without_mutation(migration_command, migration_context, shared_pool, mocker):
    mocker.patch.object(migration_command, "get_migration_context", return_value=migration_context)
    migrate = mocker.patch.object(migration_command, "migrate_app")
    migration_command.handle(target="shared", apps=["2:demo"], dry_run=True, shared_datasource_ids=[shared_pool.pk])
    assert f"target_shared_datasource_id：{shared_pool.pk}" in migration_command.stdout.getvalue()
    migrate.assert_not_called()


@pytest.mark.parametrize("already_in_pool", [False, True])
def test_command_passes_selected_pool_through_resource(
    migration_command,
    migration_context,
    shared_pool,
    mocker,
    already_in_pool,
):
    if already_in_pool:
        migration_context.trace_datasource.shared_datasource_id = shared_pool.pk
    module = "apm.management.commands.migrate_apm_trace_datasource"
    mocker.patch(f"{module}.ApplicationHelper.get_default_storage_config", return_value={"es_storage_cluster": 1})
    request = mocker.patch(f"{module}.ApplyDatasourceResource.request")
    refresh = mocker.patch(f"{module}.ApplicationConfig")
    migration_command.migrate_app(migration_context, "shared", shared_pool.pk)
    payload = request.call_args.args[0]
    assert payload["trace_datasource_option"]["shared_datasource_id"] == shared_pool.pk
    from apm.resources import ApplyDatasourceResource

    serializer = ApplyDatasourceResource.RequestSerializer(data=payload)
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["trace_datasource_option"]["shared_datasource_id"] == shared_pool.pk
    refresh.return_value.refresh.assert_called_once()
    refresh.refresh_k8s.assert_called_once()


def test_shared_target_is_invalid_for_exclusive_mode(exclusive, shared_pool, datasource_apis):
    with pytest.raises(ValueError, match="目标模式必须"):
        TraceDataSource.apply_datasource(
            2,
            "demo",
            option=True,
            is_shared=False,
            shared_datasource_id=shared_pool.pk,
            es_storage_cluster=1,
        )
    exclusive.refresh_from_db()
    assert exclusive.history_link_info == []


def test_command_parser_keeps_target_pools_and_deduplicates_apps(migration_command):
    parser = migration_command.create_parser("manage.py", "migrate_apm_trace_datasource")
    args = parser.parse_args(
        ["--target", "shared", "--apps", "2:a", "2:b", "2:a", "--shared-datasource-ids", "1", "2", "--dry-run"]
    )
    assert args.shared_datasource_ids == [1, 2]
    assert migration_command.parse_apps(args.apps) == [(2, "a"), (2, "b")]
    assert args.dry_run
