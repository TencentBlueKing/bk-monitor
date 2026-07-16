import datetime

import pytest
from django.utils import timezone

from metadata import models
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis
from metadata.resources.log_datalink import BulkCreateOrUpdateLogRouter, CreateOrUpdateLogRouter


TENANT_ID = "system"
SPACE_ID = "99101"
ENTITY_TABLE_ID = "99101_bklog.entity"
VIRTUAL_TABLE_ID = "99101_bklog.index_set"
ES_CLUSTER_ID = 99111
DORIS_CLUSTER_ID = 99112


@pytest.fixture
def route_storage_records(mocker):
    models.Space.objects.create(
        bk_tenant_id=TENANT_ID,
        space_type_id="bkcc",
        space_id=SPACE_ID,
        space_code="log-router-switch",
        space_name="log-router-switch",
    )
    models.ClusterInfo.objects.create(
        bk_tenant_id=TENANT_ID,
        cluster_id=ES_CLUSTER_ID,
        cluster_name="log-router-es",
        cluster_type=models.ClusterInfo.TYPE_ES,
        domain_name="es.example.com",
        port=9200,
        is_default_cluster=False,
    )
    models.ClusterInfo.objects.create(
        bk_tenant_id=TENANT_ID,
        cluster_id=DORIS_CLUSTER_ID,
        cluster_name="log-router-doris",
        cluster_type=models.ClusterInfo.TYPE_DORIS,
        domain_name="doris.example.com",
        port=9030,
        is_default_cluster=False,
    )
    entity = models.ResultTable.objects.create(
        bk_tenant_id=TENANT_ID,
        table_id=ENTITY_TABLE_ID,
        table_name_zh="entity",
        is_custom_table=True,
        default_storage=models.ClusterInfo.TYPE_ES,
        creator="system",
        bk_biz_id=int(SPACE_ID),
    )
    models.ESStorage.objects.create(
        bk_tenant_id=TENANT_ID,
        table_id=ENTITY_TABLE_ID,
        storage_cluster_id=ES_CLUSTER_ID,
        source_type="bkdata",
        index_set="entity_es",
    )
    models.DorisStorage.objects.create(
        bk_tenant_id=TENANT_ID,
        table_id=ENTITY_TABLE_ID,
        storage_cluster_id=DORIS_CLUSTER_ID,
        source_type="bkdata",
        bkbase_table_id="99101_bklog_entity",
        index_set="entity_doris",
    )
    models.StorageClusterRecord.objects.create(
        bk_tenant_id=TENANT_ID,
        table_id=ENTITY_TABLE_ID,
        cluster_id=ES_CLUSTER_ID,
        is_current=True,
        enable_time=datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc),
        creator="system",
    )

    mocker.patch("metadata.resources.log_datalink.get_request_tenant_id", return_value=TENANT_ID)
    mocker.patch.object(SpaceTableIDRedis, "push_space_table_ids")
    mocker.patch.object(SpaceTableIDRedis, "push_table_id_detail")
    mocker.patch.object(SpaceTableIDRedis, "push_data_label_table_ids")
    return entity


def create_virtual_es_route():
    CreateOrUpdateLogRouter().request(
        bk_tenant_id=TENANT_ID,
        space_type="bkcc",
        space_id=SPACE_ID,
        table_id=VIRTUAL_TABLE_ID,
        storage_type=models.ClusterInfo.TYPE_ES,
        origin_table_id=ENTITY_TABLE_ID,
        cluster_id=ES_CLUSTER_ID,
        source_type="bkdata",
        index_set="virtual_es",
    )


def test_log_router_serializers_do_not_expose_need_create_index():
    assert "need_create_index" not in CreateOrUpdateLogRouter.RequestSerializer().fields
    assert "need_create_index" not in BulkCreateOrUpdateLogRouter.RequestSerializer.TableInfoSerializer().fields


@pytest.mark.django_db(databases="__all__")
def test_create_virtual_es_route_uses_entity_history_without_virtual_record(route_storage_records, mocker):
    modify = mocker.patch.object(models.ResultTable, "modify", autospec=True)

    create_virtual_es_route()

    virtual_rt = models.ResultTable.objects.get(bk_tenant_id=TENANT_ID, table_id=VIRTUAL_TABLE_ID)
    virtual_es = models.ESStorage.objects.get(bk_tenant_id=TENANT_ID, table_id=VIRTUAL_TABLE_ID)
    assert virtual_rt.default_storage == models.ClusterInfo.TYPE_ES
    assert virtual_es.origin_table_id == ENTITY_TABLE_ID
    assert virtual_es.storage_cluster_id == ES_CLUSTER_ID
    assert virtual_es.need_create_index is False
    assert not models.StorageClusterRecord.objects.filter(
        bk_tenant_id=TENANT_ID,
        table_id=VIRTUAL_TABLE_ID,
    ).exists()
    assert models.StorageClusterRecord.compose_table_id_storage_cluster_records(
        VIRTUAL_TABLE_ID,
        bk_tenant_id=TENANT_ID,
    ) == [{"storage_id": ES_CLUSTER_ID, "enable_time": 0}]
    modify.assert_not_called()


@pytest.mark.django_db(databases="__all__")
def test_single_virtual_route_can_switch_es_to_doris_and_back(route_storage_records, mocker):
    modify = mocker.patch.object(models.ResultTable, "modify", autospec=True)
    create_virtual_es_route()

    entity = models.ResultTable.objects.get(bk_tenant_id=TENANT_ID, table_id=ENTITY_TABLE_ID)
    entity.default_storage = models.ClusterInfo.TYPE_DORIS
    entity.save(update_fields=["default_storage"])
    models.StorageClusterRecord.objects.filter(
        bk_tenant_id=TENANT_ID,
        table_id=ENTITY_TABLE_ID,
        is_current=True,
    ).update(is_current=False, disable_time=timezone.now())
    models.StorageClusterRecord.objects.create(
        bk_tenant_id=TENANT_ID,
        table_id=ENTITY_TABLE_ID,
        cluster_id=DORIS_CLUSTER_ID,
        is_current=True,
        enable_time=timezone.now(),
        creator="system",
    )

    CreateOrUpdateLogRouter().request(
        bk_tenant_id=TENANT_ID,
        space_type="bkcc",
        space_id=SPACE_ID,
        table_id=VIRTUAL_TABLE_ID,
        storage_type=models.ClusterInfo.TYPE_DORIS,
        origin_table_id=ENTITY_TABLE_ID,
        cluster_id=DORIS_CLUSTER_ID,
        source_type="bkdata",
        index_set="virtual_doris",
        bkbase_table_id="99101_bklog_virtual",
    )

    virtual_rt = models.ResultTable.objects.get(bk_tenant_id=TENANT_ID, table_id=VIRTUAL_TABLE_ID)
    virtual_doris = models.DorisStorage.objects.get(bk_tenant_id=TENANT_ID, table_id=VIRTUAL_TABLE_ID)
    assert virtual_rt.default_storage == models.ClusterInfo.TYPE_DORIS
    assert virtual_doris.origin_table_id == ENTITY_TABLE_ID
    assert virtual_doris.storage_cluster_id == DORIS_CLUSTER_ID
    assert models.ESStorage.objects.filter(bk_tenant_id=TENANT_ID, table_id=VIRTUAL_TABLE_ID).exists()
    assert not models.StorageClusterRecord.objects.filter(
        bk_tenant_id=TENANT_ID,
        table_id=VIRTUAL_TABLE_ID,
    ).exists()

    entity.default_storage = models.ClusterInfo.TYPE_ES
    entity.save(update_fields=["default_storage"])
    models.StorageClusterRecord.objects.filter(
        bk_tenant_id=TENANT_ID,
        table_id=ENTITY_TABLE_ID,
        is_current=True,
    ).update(is_current=False, disable_time=timezone.now())
    models.StorageClusterRecord.objects.create(
        bk_tenant_id=TENANT_ID,
        table_id=ENTITY_TABLE_ID,
        cluster_id=ES_CLUSTER_ID,
        is_current=True,
        enable_time=timezone.now(),
        creator="system",
    )
    CreateOrUpdateLogRouter().request(
        bk_tenant_id=TENANT_ID,
        space_type="bkcc",
        space_id=SPACE_ID,
        table_id=VIRTUAL_TABLE_ID,
        storage_type=models.ClusterInfo.TYPE_ES,
        cluster_id=ES_CLUSTER_ID,
        source_type="bkdata",
        index_set="virtual_es_again",
    )

    virtual_rt.refresh_from_db()
    virtual_es = models.ESStorage.objects.get(bk_tenant_id=TENANT_ID, table_id=VIRTUAL_TABLE_ID)
    assert virtual_rt.default_storage == models.ClusterInfo.TYPE_ES
    assert virtual_es.origin_table_id == ENTITY_TABLE_ID
    assert virtual_es.index_set == "virtual_es_again"
    assert virtual_es.need_create_index is False
    assert models.DorisStorage.objects.filter(bk_tenant_id=TENANT_ID, table_id=VIRTUAL_TABLE_ID).exists()
    modify.assert_not_called()


@pytest.mark.django_db(databases="__all__")
def test_bulk_switch_does_not_inherit_origin_from_es_storage(route_storage_records):
    create_virtual_es_route()
    models.ResultTable.objects.filter(bk_tenant_id=TENANT_ID, table_id=ENTITY_TABLE_ID).update(
        default_storage=models.ClusterInfo.TYPE_DORIS
    )
    models.StorageClusterRecord.objects.filter(
        bk_tenant_id=TENANT_ID,
        table_id=ENTITY_TABLE_ID,
        is_current=True,
    ).update(is_current=False, disable_time=timezone.now())
    models.StorageClusterRecord.objects.create(
        bk_tenant_id=TENANT_ID,
        table_id=ENTITY_TABLE_ID,
        cluster_id=DORIS_CLUSTER_ID,
        is_current=True,
        enable_time=timezone.now(),
        creator="system",
    )

    BulkCreateOrUpdateLogRouter().request(
        bk_tenant_id=TENANT_ID,
        space_type="bkcc",
        space_id=SPACE_ID,
        data_label="",
        table_info=[
            {
                "table_id": VIRTUAL_TABLE_ID,
                "storage_type": models.ClusterInfo.TYPE_DORIS,
                "cluster_id": DORIS_CLUSTER_ID,
                "bkbase_table_id": "99101_bklog_virtual",
                "index_set": "virtual_doris",
                "source_type": "bkdata",
            }
        ],
    )

    virtual_rt = models.ResultTable.objects.get(bk_tenant_id=TENANT_ID, table_id=VIRTUAL_TABLE_ID)
    virtual_doris = models.DorisStorage.objects.get(bk_tenant_id=TENANT_ID, table_id=VIRTUAL_TABLE_ID)
    assert virtual_rt.default_storage == models.ClusterInfo.TYPE_DORIS
    assert virtual_doris.origin_table_id in (None, "")
    assert virtual_doris.storage_cluster_id == DORIS_CLUSTER_ID
    assert not models.StorageClusterRecord.objects.filter(
        bk_tenant_id=TENANT_ID,
        table_id=VIRTUAL_TABLE_ID,
    ).exists()


@pytest.mark.django_db(databases="__all__")
def test_bulk_create_and_update_virtual_route_with_options(route_storage_records):
    table_id = "99101_bklog.bulk_index_set"

    BulkCreateOrUpdateLogRouter().request(
        bk_tenant_id=TENANT_ID,
        space_type="bkcc",
        space_id=SPACE_ID,
        data_label="",
        table_info=[
            {
                "table_id": table_id,
                "storage_type": models.ClusterInfo.TYPE_ES,
                "origin_table_id": ENTITY_TABLE_ID,
                "index_set": "bulk_es",
                "source_type": "bkdata",
                "options": [{"name": "route_option", "value": "before"}],
            }
        ],
    )

    virtual_rt = models.ResultTable.objects.get(bk_tenant_id=TENANT_ID, table_id=table_id)
    virtual_es = models.ESStorage.objects.get(bk_tenant_id=TENANT_ID, table_id=table_id)
    option = models.ResultTableOption.objects.get(
        bk_tenant_id=TENANT_ID,
        table_id=table_id,
        name="route_option",
    )
    assert virtual_rt.default_storage == models.ClusterInfo.TYPE_ES
    assert virtual_es.origin_table_id == ENTITY_TABLE_ID
    assert virtual_es.index_set == "bulk_es"
    assert virtual_es.need_create_index is False
    assert option.value == "before"
    assert not models.StorageClusterRecord.objects.filter(bk_tenant_id=TENANT_ID, table_id=table_id).exists()

    BulkCreateOrUpdateLogRouter().request(
        bk_tenant_id=TENANT_ID,
        space_type="bkcc",
        space_id=SPACE_ID,
        data_label="",
        table_info=[
            {
                "table_id": table_id,
                "storage_type": models.ClusterInfo.TYPE_ES,
                "options": [{"name": "route_option", "value": "after"}],
            }
        ],
    )

    virtual_es.refresh_from_db()
    option.refresh_from_db()
    assert virtual_es.index_set == "bulk_es"
    assert option.value == "after"
    assert (
        models.ResultTableOption.objects.filter(
            bk_tenant_id=TENANT_ID,
            table_id=table_id,
            name="route_option",
        ).count()
        == 1
    )


@pytest.mark.django_db(databases="__all__")
def test_invalid_target_cluster_rolls_back_alias_and_storage_switch(route_storage_records):
    create_virtual_es_route()
    models.ResultTable.objects.filter(bk_tenant_id=TENANT_ID, table_id=ENTITY_TABLE_ID).update(
        default_storage=models.ClusterInfo.TYPE_DORIS
    )

    with pytest.raises(ValueError, match="Doris.*配置有误"):
        CreateOrUpdateLogRouter().request(
            bk_tenant_id=TENANT_ID,
            space_type="bkcc",
            space_id=SPACE_ID,
            table_id=VIRTUAL_TABLE_ID,
            storage_type=models.ClusterInfo.TYPE_DORIS,
            origin_table_id=ENTITY_TABLE_ID,
            cluster_id=ES_CLUSTER_ID,
            query_alias_settings=[{"field_name": "__ext.pod", "query_alias": "pod"}],
        )

    virtual_rt = models.ResultTable.objects.get(bk_tenant_id=TENANT_ID, table_id=VIRTUAL_TABLE_ID)
    assert virtual_rt.default_storage == models.ClusterInfo.TYPE_ES
    assert not models.DorisStorage.objects.filter(bk_tenant_id=TENANT_ID, table_id=VIRTUAL_TABLE_ID).exists()
    assert not models.ESFieldQueryAliasOption.objects.filter(
        bk_tenant_id=TENANT_ID,
        table_id=VIRTUAL_TABLE_ID,
    ).exists()


@pytest.mark.django_db(databases="__all__")
def test_entity_current_record_mismatch_does_not_block_virtual_switch(route_storage_records):
    create_virtual_es_route()
    models.ResultTable.objects.filter(bk_tenant_id=TENANT_ID, table_id=ENTITY_TABLE_ID).update(
        default_storage=models.ClusterInfo.TYPE_DORIS
    )

    CreateOrUpdateLogRouter().request(
        bk_tenant_id=TENANT_ID,
        space_type="bkcc",
        space_id=SPACE_ID,
        table_id=VIRTUAL_TABLE_ID,
        storage_type=models.ClusterInfo.TYPE_DORIS,
        origin_table_id=ENTITY_TABLE_ID,
    )

    virtual_rt = models.ResultTable.objects.get(bk_tenant_id=TENANT_ID, table_id=VIRTUAL_TABLE_ID)
    virtual_doris = models.DorisStorage.objects.get(bk_tenant_id=TENANT_ID, table_id=VIRTUAL_TABLE_ID)
    assert virtual_rt.default_storage == models.ClusterInfo.TYPE_DORIS
    assert virtual_doris.storage_cluster_id == DORIS_CLUSTER_ID


@pytest.mark.django_db(databases="__all__")
def test_create_direct_es_route_without_origin_table(route_storage_records):
    table_id = "99101_bklog.direct_es"

    CreateOrUpdateLogRouter().request(
        bk_tenant_id=TENANT_ID,
        space_type="bkcc",
        space_id=SPACE_ID,
        table_id=table_id,
        storage_type=models.ClusterInfo.TYPE_ES,
        cluster_id=ES_CLUSTER_ID,
        index_set="direct_es",
    )

    result_table = models.ResultTable.objects.get(bk_tenant_id=TENANT_ID, table_id=table_id)
    es_storage = models.ESStorage.objects.get(bk_tenant_id=TENANT_ID, table_id=table_id)
    assert result_table.default_storage == models.ClusterInfo.TYPE_ES
    assert es_storage.origin_table_id in (None, "")
    assert es_storage.storage_cluster_id == ES_CLUSTER_ID
    assert not models.StorageClusterRecord.objects.filter(bk_tenant_id=TENANT_ID, table_id=table_id).exists()


@pytest.mark.django_db(databases="__all__")
def test_direct_route_can_switch_storage_without_origin_table(route_storage_records):
    table_id = "99101_bklog.direct_switch"
    CreateOrUpdateLogRouter().request(
        bk_tenant_id=TENANT_ID,
        space_type="bkcc",
        space_id=SPACE_ID,
        table_id=table_id,
        storage_type=models.ClusterInfo.TYPE_ES,
        cluster_id=ES_CLUSTER_ID,
    )

    CreateOrUpdateLogRouter().request(
        bk_tenant_id=TENANT_ID,
        space_type="bkcc",
        space_id=SPACE_ID,
        table_id=table_id,
        storage_type=models.ClusterInfo.TYPE_DORIS,
        cluster_id=DORIS_CLUSTER_ID,
        bkbase_table_id="99101_bklog_direct_switch",
    )

    result_table = models.ResultTable.objects.get(bk_tenant_id=TENANT_ID, table_id=table_id)
    doris_storage = models.DorisStorage.objects.get(bk_tenant_id=TENANT_ID, table_id=table_id)
    assert result_table.default_storage == models.ClusterInfo.TYPE_DORIS
    assert doris_storage.origin_table_id in (None, "")
    assert doris_storage.storage_cluster_id == DORIS_CLUSTER_ID
    assert not models.StorageClusterRecord.objects.filter(bk_tenant_id=TENANT_ID, table_id=table_id).exists()


@pytest.mark.django_db(databases="__all__")
def test_virtual_es_route_accepts_blank_route_fields(route_storage_records):
    create_virtual_es_route()

    CreateOrUpdateLogRouter().request(
        bk_tenant_id=TENANT_ID,
        space_type="bkcc",
        space_id=SPACE_ID,
        table_id=VIRTUAL_TABLE_ID,
        storage_type=models.ClusterInfo.TYPE_ES,
        data_label="",
        index_set="",
        source_type="",
    )

    virtual_es = models.ESStorage.objects.get(bk_tenant_id=TENANT_ID, table_id=VIRTUAL_TABLE_ID)
    assert virtual_es.index_set == ""
    assert virtual_es.source_type == ""
