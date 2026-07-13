"""ResultTable 在 ES 与 Doris 间切换默认存储的测试。"""

import datetime

import pytest
from django.utils import timezone

from metadata import models

pytestmark = pytest.mark.django_db(databases="__all__")

TENANT_ID = "system"
TABLE_ID = "2_bklog.storage_switch"


@pytest.fixture
def storage_switch_records():
    clusters = {}
    for cluster_id, cluster_name, cluster_type, port in (
        (101, "es-a", models.ClusterInfo.TYPE_ES, 9200),
        (102, "es-b", models.ClusterInfo.TYPE_ES, 9200),
        (201, "doris-a", models.ClusterInfo.TYPE_DORIS, 9030),
        (202, "doris-b", models.ClusterInfo.TYPE_DORIS, 9030),
        (203, "doris-other-tenant", models.ClusterInfo.TYPE_DORIS, 9030),
    ):
        tenant_id = "other" if cluster_id == 203 else TENANT_ID
        clusters[cluster_id] = models.ClusterInfo.objects.create(
            cluster_id=cluster_id,
            bk_tenant_id=tenant_id,
            cluster_name=cluster_name,
            cluster_type=cluster_type,
            domain_name="127.0.0.1",
            port=port,
            description="",
            is_default_cluster=False,
            version="2.x" if cluster_type == models.ClusterInfo.TYPE_DORIS else "7.x",
        )

    result_table = models.ResultTable.objects.create(
        table_id=TABLE_ID,
        bk_tenant_id=TENANT_ID,
        table_name_zh="storage switch",
        is_custom_table=True,
        schema_type=models.ResultTable.SCHEMA_TYPE_FIXED,
        default_storage=models.ClusterInfo.TYPE_ES,
        creator="admin",
        last_modify_user="admin",
        is_enable=True,
        is_deleted=False,
        bk_biz_id=2,
    )
    es_storage = models.ESStorage.objects.create(
        table_id=TABLE_ID,
        bk_tenant_id=TENANT_ID,
        storage_cluster_id=101,
        index_settings='{"index.number_of_shards": 1}',
        mapping_settings='{"dynamic": true}',
        need_create_index=True,
    )
    doris_storage = models.DorisStorage.objects.create(
        table_id=TABLE_ID,
        bk_tenant_id=TENANT_ID,
        storage_cluster_id=201,
        field_config_mapping="{}",
    )
    current_record = models.StorageClusterRecord.objects.create(
        table_id=TABLE_ID,
        bk_tenant_id=TENANT_ID,
        cluster_id=101,
        creator="admin",
        enable_time=timezone.now() - datetime.timedelta(days=1),
        is_current=True,
        is_deleted=False,
    )
    return {
        "clusters": clusters,
        "result_table": result_table,
        "es_storage": es_storage,
        "doris_storage": doris_storage,
        "current_record": current_record,
    }


@pytest.fixture(autouse=True)
def mock_unrelated_space_refresh(mocker):
    mocker.patch("metadata.models.space.utils.get_space_by_table_id", return_value={})


def test_es_to_doris_to_es_creates_continuous_segments(storage_switch_records, mocker):
    result_table = storage_switch_records["result_table"]
    events = []

    def prepare_es(*args, **kwargs):
        events.append("prepare_es")
        return True

    def apply_datalink(rt, *args, **kwargs):
        refreshed_rt = models.ResultTable.objects.get(table_id=TABLE_ID, bk_tenant_id=TENANT_ID)
        current = models.StorageClusterRecord.objects.get(table_id=TABLE_ID, bk_tenant_id=TENANT_ID, is_current=True)
        assert refreshed_rt.default_storage == rt.default_storage
        assert current.cluster_id == rt.get_storage(rt.default_storage).storage_cluster_id
        events.append("apply_datalink")

    prepare_mock = mocker.patch.object(
        models.ESStorage, "update_index_and_aliases", autospec=True, side_effect=prepare_es
    )
    mocker.patch.object(models.ResultTable, "apply_datalink", autospec=True, side_effect=apply_datalink)

    result_table.modify(operator="admin", default_storage=models.ClusterInfo.TYPE_DORIS)
    prepare_mock.assert_not_called()

    es_first_segment = models.StorageClusterRecord.objects.get(
        table_id=TABLE_ID, bk_tenant_id=TENANT_ID, cluster_id=101, is_current=False
    )
    doris_segment = models.StorageClusterRecord.objects.get(
        table_id=TABLE_ID, bk_tenant_id=TENANT_ID, cluster_id=201, is_current=True
    )
    assert es_first_segment.disable_time == doris_segment.enable_time
    assert models.ESStorage.objects.filter(table_id=TABLE_ID, bk_tenant_id=TENANT_ID).exists()
    assert models.DorisStorage.objects.filter(table_id=TABLE_ID, bk_tenant_id=TENANT_ID).exists()
    es_storage = models.ESStorage.objects.get(table_id=TABLE_ID, bk_tenant_id=TENANT_ID)
    assert es_storage.is_index_enable() is False
    assert es_storage.is_index_enable(require_default_storage=False) is True

    events.clear()
    result_table.refresh_from_db()
    result_table.modify(operator="admin", default_storage=models.ClusterInfo.TYPE_ES)

    assert events == ["prepare_es", "apply_datalink"]
    prepare_mock.assert_called_once()
    assert prepare_mock.call_args.kwargs == {
        "ahead_time": 0,
        "is_moving_cluster": True,
        "strict": True,
    }

    doris_segment.refresh_from_db()
    es_second_segment = models.StorageClusterRecord.objects.get(
        table_id=TABLE_ID, bk_tenant_id=TENANT_ID, cluster_id=101, is_current=True
    )
    assert doris_segment.disable_time == es_second_segment.enable_time
    assert (
        models.StorageClusterRecord.objects.filter(table_id=TABLE_ID, bk_tenant_id=TENANT_ID, cluster_id=101).count()
        == 2
    )
    assert (
        models.StorageClusterRecord.objects.filter(table_id=TABLE_ID, bk_tenant_id=TENANT_ID, is_current=True).count()
        == 1
    )


def test_same_cluster_modify_is_idempotent(storage_switch_records, mocker):
    result_table = storage_switch_records["result_table"]
    original_record = storage_switch_records["current_record"]
    mocker.patch.object(models.ResultTable, "apply_datalink", autospec=True)
    prepare_mock = mocker.patch.object(models.ESStorage, "update_index_and_aliases", autospec=True)

    result_table.modify(operator="admin", default_storage=models.ClusterInfo.TYPE_ES)

    prepare_mock.assert_not_called()
    current_record = models.StorageClusterRecord.objects.get(table_id=TABLE_ID, bk_tenant_id=TENANT_ID, is_current=True)
    assert current_record.id == original_record.id
    assert current_record.enable_time == original_record.enable_time
    assert models.StorageClusterRecord.objects.filter(table_id=TABLE_ID, bk_tenant_id=TENANT_ID).count() == 1


def test_reenable_es_updates_existing_index_before_datalink(storage_switch_records, mocker):
    result_table = storage_switch_records["result_table"]
    result_table.is_enable = False
    result_table.save(update_fields=["is_enable"])
    events = []

    def prepare_es(*args, **kwargs):
        events.append("prepare_es")
        return True

    def apply_datalink(*args, **kwargs):
        events.append("apply_datalink")

    mocker.patch.object(models.ESStorage, "index_exist", autospec=True, return_value=True)
    create_mock = mocker.patch.object(models.ESStorage, "create_index_and_aliases", autospec=True)
    update_mock = mocker.patch.object(
        models.ESStorage,
        "update_index_and_aliases",
        autospec=True,
        side_effect=prepare_es,
    )
    mocker.patch.object(models.ResultTable, "apply_datalink", autospec=True, side_effect=apply_datalink)

    result_table.modify(operator="admin", is_enable=True)

    assert events == ["prepare_es", "apply_datalink"]
    create_mock.assert_not_called()
    assert update_mock.call_args.kwargs == {
        "ahead_time": storage_switch_records["es_storage"].slice_gap,
        "is_moving_cluster": False,
        "strict": True,
    }


def test_reenable_es_creates_missing_index_before_datalink(storage_switch_records, mocker):
    result_table = storage_switch_records["result_table"]
    result_table.is_enable = False
    result_table.save(update_fields=["is_enable"])
    events = []

    mocker.patch.object(models.ESStorage, "index_exist", autospec=True, return_value=False)

    def create_index(*args, **kwargs):
        events.append("create_index")
        return True

    create_mock = mocker.patch.object(
        models.ESStorage,
        "create_index_and_aliases",
        autospec=True,
        side_effect=create_index,
    )
    update_mock = mocker.patch.object(models.ESStorage, "update_index_and_aliases", autospec=True)

    def apply_datalink(*args, **kwargs):
        events.append("apply_datalink")

    mocker.patch.object(models.ResultTable, "apply_datalink", autospec=True, side_effect=apply_datalink)

    result_table.modify(operator="admin", is_enable=True)

    assert events == ["create_index", "apply_datalink"]
    update_mock.assert_not_called()
    assert create_mock.call_args.kwargs == {
        "ahead_time": storage_switch_records["es_storage"].slice_gap,
        "strict": True,
    }


def test_es_cluster_a_to_b_to_a_creates_new_segment_on_switch_back(storage_switch_records, mocker):
    result_table = storage_switch_records["result_table"]
    mocker.patch.object(models.ResultTable, "apply_datalink", autospec=True)
    prepare_mock = mocker.patch.object(
        models.ESStorage,
        "update_index_and_aliases",
        autospec=True,
        return_value=True,
    )

    result_table.modify(
        operator="admin",
        external_storage={models.ClusterInfo.TYPE_ES: {"storage_cluster_id": 102}},
    )
    first_es_segment = models.StorageClusterRecord.objects.get(
        table_id=TABLE_ID, bk_tenant_id=TENANT_ID, cluster_id=101, is_current=False
    )
    second_es_segment = models.StorageClusterRecord.objects.get(
        table_id=TABLE_ID, bk_tenant_id=TENANT_ID, cluster_id=102, is_current=True
    )
    assert first_es_segment.disable_time == second_es_segment.enable_time

    result_table.refresh_from_db()
    result_table.modify(
        operator="admin",
        external_storage={models.ClusterInfo.TYPE_ES: {"storage_cluster_id": 101}},
    )

    assert prepare_mock.call_count == 2
    assert all(call.kwargs["strict"] is True for call in prepare_mock.call_args_list)
    second_es_segment.refresh_from_db()
    third_es_segment = models.StorageClusterRecord.objects.get(
        table_id=TABLE_ID, bk_tenant_id=TENANT_ID, cluster_id=101, is_current=True
    )
    assert second_es_segment.disable_time == third_es_segment.enable_time
    assert (
        models.StorageClusterRecord.objects.filter(table_id=TABLE_ID, bk_tenant_id=TENANT_ID, cluster_id=101).count()
        == 2
    )
    assert (
        models.StorageClusterRecord.objects.filter(table_id=TABLE_ID, bk_tenant_id=TENANT_ID, is_current=True).count()
        == 1
    )


def test_doris_cluster_a_to_b_creates_continuous_segment(storage_switch_records, mocker):
    result_table = storage_switch_records["result_table"]
    result_table.default_storage = models.ClusterInfo.TYPE_DORIS
    result_table.save(update_fields=["default_storage"])
    models.StorageClusterRecord.objects.all().delete()
    first_segment = models.StorageClusterRecord.objects.create(
        table_id=TABLE_ID,
        bk_tenant_id=TENANT_ID,
        cluster_id=201,
        creator="admin",
        enable_time=timezone.now() - datetime.timedelta(hours=1),
        is_current=True,
    )
    mocker.patch.object(models.ResultTable, "apply_datalink", autospec=True)
    prepare_mock = mocker.patch.object(models.ESStorage, "update_index_and_aliases", autospec=True)

    result_table.modify(
        operator="admin",
        external_storage={models.ClusterInfo.TYPE_DORIS: {"storage_cluster_id": 202}},
    )

    prepare_mock.assert_not_called()
    first_segment.refresh_from_db()
    second_segment = models.StorageClusterRecord.objects.get(
        table_id=TABLE_ID, bk_tenant_id=TENANT_ID, cluster_id=202, is_current=True
    )
    assert first_segment.disable_time == second_segment.enable_time
    assert models.DorisStorage.objects.get(table_id=TABLE_ID, bk_tenant_id=TENANT_ID).storage_cluster_id == 202


def test_non_default_external_storage_does_not_advance_current(storage_switch_records, mocker):
    result_table = storage_switch_records["result_table"]
    models.DorisStorage.objects.filter(table_id=TABLE_ID, bk_tenant_id=TENANT_ID).delete()
    mocker.patch.object(models.ResultTable, "apply_datalink", autospec=True)

    result_table.modify(
        operator="admin",
        external_storage={
            models.ClusterInfo.TYPE_DORIS: {
                "storage_cluster_id": 201,
                "field_config_mapping": {},
            }
        },
    )

    assert models.DorisStorage.objects.get(table_id=TABLE_ID, bk_tenant_id=TENANT_ID).storage_cluster_id == 201
    current_records = models.StorageClusterRecord.objects.filter(
        table_id=TABLE_ID, bk_tenant_id=TENANT_ID, is_current=True
    )
    assert current_records.count() == 1
    assert current_records.get().cluster_id == 101
    assert (
        models.StorageClusterRecord.objects.filter(table_id=TABLE_ID, bk_tenant_id=TENANT_ID, cluster_id=201).count()
        == 0
    )

    result_table.refresh_from_db()
    result_table.modify(
        operator="admin",
        external_storage={models.ClusterInfo.TYPE_DORIS: {"storage_cluster_id": 202}},
    )
    assert models.DorisStorage.objects.get(table_id=TABLE_ID, bk_tenant_id=TENANT_ID).storage_cluster_id == 202
    current_records = models.StorageClusterRecord.objects.filter(
        table_id=TABLE_ID, bk_tenant_id=TENANT_ID, is_current=True
    )
    assert current_records.count() == 1
    assert current_records.get().cluster_id == 101
    assert not models.StorageClusterRecord.objects.filter(
        table_id=TABLE_ID,
        bk_tenant_id=TENANT_ID,
        cluster_id__in=[201, 202],
    ).exists()


def test_new_non_default_es_uses_requested_cluster_without_advancing_current(storage_switch_records, mocker):
    result_table = storage_switch_records["result_table"]
    result_table.default_storage = models.ClusterInfo.TYPE_DORIS
    result_table.save(update_fields=["default_storage"])
    models.ESStorage.objects.filter(table_id=TABLE_ID, bk_tenant_id=TENANT_ID).delete()
    models.StorageClusterRecord.objects.all().delete()
    models.StorageClusterRecord.objects.create(
        table_id=TABLE_ID,
        bk_tenant_id=TENANT_ID,
        cluster_id=201,
        creator="admin",
        enable_time=timezone.now() - datetime.timedelta(hours=1),
        is_current=True,
    )
    mocker.patch.object(models.ResultTable, "apply_datalink", autospec=True)
    mocker.patch(
        "metadata.models.space.space_table_id_redis.SpaceTableIDRedis.push_es_table_id_detail",
        return_value=None,
    )

    result_table.modify(
        operator="admin",
        external_storage={
            models.ClusterInfo.TYPE_ES: {
                "storage_cluster_id": 102,
                "index_settings": {},
                "mapping_settings": {},
            }
        },
    )

    assert models.ESStorage.objects.get(table_id=TABLE_ID, bk_tenant_id=TENANT_ID).storage_cluster_id == 102
    current_records = models.StorageClusterRecord.objects.filter(
        table_id=TABLE_ID, bk_tenant_id=TENANT_ID, is_current=True
    )
    assert current_records.count() == 1
    assert current_records.get().cluster_id == 201
    assert not models.StorageClusterRecord.objects.filter(
        table_id=TABLE_ID, bk_tenant_id=TENANT_ID, cluster_id=102
    ).exists()


def test_es_prepare_failure_rolls_back_and_blocks_datalink(storage_switch_records, mocker):
    result_table = storage_switch_records["result_table"]
    result_table.default_storage = models.ClusterInfo.TYPE_DORIS
    result_table.save(update_fields=["default_storage"])
    models.StorageClusterRecord.objects.all().delete()
    models.StorageClusterRecord.objects.create(
        table_id=TABLE_ID,
        bk_tenant_id=TENANT_ID,
        cluster_id=201,
        creator="admin",
        enable_time=timezone.now() - datetime.timedelta(hours=1),
        is_current=True,
    )
    mocker.patch.object(
        models.ESStorage,
        "update_index_and_aliases",
        autospec=True,
        side_effect=RuntimeError("ES alias failed"),
    )
    apply_mock = mocker.patch.object(models.ResultTable, "apply_datalink", autospec=True)

    with pytest.raises(RuntimeError, match="ES alias failed"):
        result_table.modify(operator="admin", default_storage=models.ClusterInfo.TYPE_ES)

    apply_mock.assert_not_called()
    assert (
        models.ResultTable.objects.get(table_id=TABLE_ID, bk_tenant_id=TENANT_ID).default_storage
        == models.ClusterInfo.TYPE_DORIS
    )
    current = models.StorageClusterRecord.objects.get(table_id=TABLE_ID, bk_tenant_id=TENANT_ID, is_current=True)
    assert current.cluster_id == 201
    assert models.StorageClusterRecord.objects.filter(table_id=TABLE_ID, bk_tenant_id=TENANT_ID).count() == 1


def test_apply_datalink_failure_rolls_back_storage_switch(storage_switch_records, mocker):
    result_table = storage_switch_records["result_table"]
    mocker.patch.object(
        models.ResultTable,
        "apply_datalink",
        autospec=True,
        side_effect=RuntimeError("apply datalink failed"),
    )

    with pytest.raises(RuntimeError, match="apply datalink failed"):
        result_table.modify(
            operator="admin",
            default_storage=models.ClusterInfo.TYPE_DORIS,
            external_storage={models.ClusterInfo.TYPE_DORIS: {"storage_cluster_id": 202}},
        )

    assert (
        models.ResultTable.objects.get(table_id=TABLE_ID, bk_tenant_id=TENANT_ID).default_storage
        == models.ClusterInfo.TYPE_ES
    )
    assert models.DorisStorage.objects.get(table_id=TABLE_ID, bk_tenant_id=TENANT_ID).storage_cluster_id == 201
    current = models.StorageClusterRecord.objects.get(table_id=TABLE_ID, bk_tenant_id=TENANT_ID, is_current=True)
    assert current.cluster_id == 101
    assert current.disable_time is None
    assert models.StorageClusterRecord.objects.filter(table_id=TABLE_ID, bk_tenant_id=TENANT_ID).count() == 1


def test_storage_record_failure_rolls_back_before_applying_datalink(storage_switch_records, mocker):
    result_table = storage_switch_records["result_table"]
    mocker.patch.object(
        models.StorageClusterRecord,
        "switch_current_cluster",
        side_effect=RuntimeError("write storage history failed"),
    )
    apply_mock = mocker.patch.object(models.ResultTable, "apply_datalink", autospec=True)

    with pytest.raises(RuntimeError, match="write storage history failed"):
        result_table.modify(operator="admin", default_storage=models.ClusterInfo.TYPE_DORIS)

    apply_mock.assert_not_called()
    assert (
        models.ResultTable.objects.get(table_id=TABLE_ID, bk_tenant_id=TENANT_ID).default_storage
        == models.ClusterInfo.TYPE_ES
    )
    assert (
        models.StorageClusterRecord.objects.get(table_id=TABLE_ID, bk_tenant_id=TENANT_ID, is_current=True).cluster_id
        == 101
    )


@pytest.mark.parametrize("invalid_cluster_id", [101, 203])
def test_target_cluster_type_or_tenant_mismatch_rolls_back(storage_switch_records, mocker, invalid_cluster_id):
    result_table = storage_switch_records["result_table"]
    apply_mock = mocker.patch.object(models.ResultTable, "apply_datalink", autospec=True)

    with pytest.raises(ValueError, match="默认存储集群"):
        result_table.modify(
            operator="admin",
            default_storage=models.ClusterInfo.TYPE_DORIS,
            external_storage={
                models.ClusterInfo.TYPE_DORIS: {"storage_cluster_id": invalid_cluster_id},
            },
        )

    apply_mock.assert_not_called()
    assert (
        models.ResultTable.objects.get(table_id=TABLE_ID, bk_tenant_id=TENANT_ID).default_storage
        == models.ClusterInfo.TYPE_ES
    )
    assert models.DorisStorage.objects.get(table_id=TABLE_ID, bk_tenant_id=TENANT_ID).storage_cluster_id == 201
    assert (
        models.StorageClusterRecord.objects.get(table_id=TABLE_ID, bk_tenant_id=TENANT_ID, is_current=True).cluster_id
        == 101
    )


def test_cannot_delete_storage_with_live_history(storage_switch_records, mocker):
    result_table = storage_switch_records["result_table"]
    models.StorageClusterRecord.objects.create(
        table_id=TABLE_ID,
        bk_tenant_id=TENANT_ID,
        cluster_id=201,
        creator="admin",
        enable_time=timezone.now() - datetime.timedelta(days=2),
        disable_time=timezone.now() - datetime.timedelta(days=1),
        is_current=False,
        is_deleted=False,
    )
    apply_mock = mocker.patch.object(models.ResultTable, "apply_datalink", autospec=True)

    with pytest.raises(ValueError, match="有效历史数据"):
        result_table.modify(
            operator="admin",
            need_delete_storages={models.ClusterInfo.TYPE_DORIS: True},
        )

    apply_mock.assert_not_called()
    assert models.DorisStorage.objects.filter(table_id=TABLE_ID, bk_tenant_id=TENANT_ID).exists()
