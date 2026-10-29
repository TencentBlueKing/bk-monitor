import pytest

from apm.models import TraceDataSource, SharedTraceDataSource
from apm.tests.trace_switch_history import EXCLUSIVE_RT, SHARED_RT, T1, T2
from core.errors.api import BKAPIError

pytestmark = pytest.mark.django_db(databases="__all__")


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


@pytest.mark.parametrize("code", ["3623301", 3623301])
def test_return_to_exclusive_recreates_deleted_index_set(exclusive, shared_pool, datasource_apis, code):
    TraceDataSource.apply_datasource(2, "demo", option=True, is_shared=True, es_storage_cluster=1)
    datasource_apis["update_index"].side_effect = BKAPIError(result={"code": code, "message": "索引集不存在"})

    TraceDataSource.apply_datasource(2, "demo", option=True, is_shared=False, es_storage_cluster=1)

    exclusive.refresh_from_db()
    shared_pool.refresh_from_db()
    assert exclusive.result_table_id == EXCLUSIVE_RT
    assert (exclusive.index_set_id, exclusive.index_set_name) == (22, "new-index")
    assert shared_pool.usage_count == 0
    params = dict(datasource_apis["update_index"].call_args.kwargs)
    assert params.pop("index_set_id") == 11
    datasource_apis["create_index"].assert_called_once_with(**params)
    assert datasource_apis["modify"].call_args.args[0]["is_enable"] is True


def test_index_set_recreation_failure_rolls_back_migration(exclusive, shared_pool, datasource_apis):
    TraceDataSource.apply_datasource(2, "demo", option=True, is_shared=True, es_storage_cluster=1)
    exclusive.refresh_from_db()
    old_history = exclusive.history_link_info
    datasource_apis["update_index"].side_effect = BKAPIError(result={"code": "3623301"})
    datasource_apis["create_index"].side_effect = RuntimeError("create index failed")

    with pytest.raises(RuntimeError, match="create index failed"):
        TraceDataSource.apply_datasource(2, "demo", option=True, is_shared=False, es_storage_cluster=1)

    exclusive.refresh_from_db()
    shared_pool.refresh_from_db()
    assert exclusive.result_table_id == SHARED_RT
    assert exclusive.index_set_id == 21
    assert exclusive.history_link_info == old_history
    assert exclusive.backup_link_info["index_set_id"] == 11
    assert shared_pool.usage_count == 1
    datasource_apis["modify"].assert_not_called()


@pytest.mark.parametrize(
    "error",
    [
        BKAPIError(result={"code": 403, "message": "permission denied"}),
        BKAPIError(result={"message": "timeout"}),
        RuntimeError("索引集不存在"),
    ],
)
def test_other_index_set_errors_preserve_existing_fallback(exclusive, datasource_apis, error):
    datasource_apis["update_index"].side_effect = error

    assert exclusive.update_or_create_index_set(1, 2, EXCLUSIVE_RT, 11) == (11, "old-index")
    datasource_apis["create_index"].assert_not_called()


def test_explicit_stop_still_disables_exclusive_rt(exclusive, datasource_apis):
    TraceDataSource.stop(2, "demo")
    assert datasource_apis["modify"].call_args.args[0]["is_enable"] is False
    datasource_apis["delete_index"].assert_called_once_with(index_set_id=11)
    exclusive.refresh_from_db()
    assert exclusive.history_link_info == []


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


def test_exclusive_update_does_not_read_shared_pool_or_append_history(
    exclusive, datasource_apis, django_assert_num_queries, mocker
):
    release = mocker.patch.object(TraceDataSource, "release_for_migration", side_effect=AssertionError("不应迁出"))
    with django_assert_num_queries(4):
        # savepoint、应用读取、索引集字段更新、release savepoint；外部 RT API 已替换。
        TraceDataSource.apply_datasource(2, "demo", option=True, es_storage_cluster=1)
    exclusive.refresh_from_db()
    assert exclusive.history_link_info == []
    assert exclusive.backup_link_info == {}
    assert exclusive.result_table_id == EXCLUSIVE_RT
    release.assert_not_called()
    datasource_apis["modify"].assert_called_once()
    datasource_apis["delete_index"].assert_not_called()


def test_new_exclusive_datasource_does_not_allocate_shared_pool(datasource_apis, new_data_id, mocker):
    allocate = mocker.patch.object(SharedTraceDataSource, "allocate", side_effect=AssertionError("不应分配共享池"))
    TraceDataSource.apply_datasource(2, "demo", option=True, es_storage_cluster=1)
    source = TraceDataSource.objects.get(bk_biz_id=2, app_name="demo")
    assert source.result_table_id == EXCLUSIVE_RT
    assert source.bk_data_id == 301
    assert source.history_link_info == []
    assert source.backup_link_info == {}
    assert not source.is_shared
    allocate.assert_not_called()
    datasource_apis["create_rt"].assert_called_once()
