import datetime
import json
from unittest.mock import patch

import pytest
from django.db import connections
from django.test import override_settings
from django.test.utils import CaptureQueriesContext

from metadata import config, models
from metadata.models.space.constants import RESULT_TABLE_DETAIL_CHANNEL, RESULT_TABLE_DETAIL_KEY
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis


TENANT_ID = "mixed-storage-tenant"
OTHER_TENANT_ID = "mixed-storage-other-tenant"
ES_CLUSTER_ID = 198201
DORIS_CLUSTER_ID = 198301
ES_ENABLE_TIME = datetime.datetime(2024, 7, 1, tzinfo=datetime.timezone.utc)
DORIS_ENABLE_TIME = datetime.datetime(2024, 8, 1, tzinfo=datetime.timezone.utc)


def _create_cluster(*, bk_tenant_id: str, cluster_id: int, cluster_type: str, cluster_name: str) -> None:
    models.ClusterInfo.objects.create(
        bk_tenant_id=bk_tenant_id,
        cluster_id=cluster_id,
        cluster_name=cluster_name,
        cluster_type=cluster_type,
        domain_name=f"{cluster_name}.example.com",
        port=9200,
        description="",
        is_default_cluster=False,
        version="7.x",
    )


def _create_result_table(
    *,
    bk_tenant_id: str,
    table_id: str,
    default_storage: str,
    data_label: str = "2_bklog_demo",
    labels: dict | None = None,
) -> None:
    models.ResultTable.objects.create(
        bk_tenant_id=bk_tenant_id,
        table_id=table_id,
        table_name_zh=table_id,
        is_custom_table=False,
        schema_type=models.ResultTable.SCHEMA_TYPE_FREE,
        default_storage=default_storage,
        creator="system",
        last_modify_user="system",
        data_label=data_label,
        labels=labels or {"scene": "log"},
    )


def _create_es_storage(
    *,
    bk_tenant_id: str,
    table_id: str,
    cluster_id: int,
    index_set: str,
    source_type: str = "log",
    origin_table_id: str | None = None,
) -> None:
    models.ESStorage.objects.create(
        bk_tenant_id=bk_tenant_id,
        table_id=table_id,
        storage_cluster_id=cluster_id,
        index_set=index_set,
        source_type=source_type,
        origin_table_id=origin_table_id,
        need_create_index=False,
    )


def _create_doris_storage(
    *,
    bk_tenant_id: str,
    table_id: str,
    cluster_id: int,
    bkbase_table_id: str | None,
    index_set: str,
    source_type: str = "log",
    origin_table_id: str | None = None,
) -> None:
    models.DorisStorage.objects.create(
        bk_tenant_id=bk_tenant_id,
        table_id=table_id,
        storage_cluster_id=cluster_id,
        bkbase_table_id=bkbase_table_id,
        index_set=index_set,
        source_type=source_type,
        origin_table_id=origin_table_id,
    )


def _create_storage_segment(
    *,
    bk_tenant_id: str,
    table_id: str,
    cluster_id: int,
    enable_time: datetime.datetime,
    is_current: bool,
) -> None:
    models.StorageClusterRecord.objects.create(
        bk_tenant_id=bk_tenant_id,
        table_id=table_id,
        cluster_id=cluster_id,
        enable_time=enable_time,
        is_current=is_current,
        creator="system",
    )


def _create_vm_metric_route(*, bk_tenant_id: str, table_id: str, cluster_id: int = 198401) -> None:
    models.AccessVMRecord.objects.create(
        bk_tenant_id=bk_tenant_id,
        result_table_id=table_id,
        vm_cluster_id=cluster_id,
        storage_cluster_id=cluster_id,
        bk_base_data_id=50010,
        vm_result_table_id=f"vm_{table_id.replace('.', '_')}",
    )


def _push_and_get_detail(
    *,
    bk_tenant_id: str,
    table_id: str,
    expected_redis_table_id: str | None = None,
) -> dict:
    with (
        patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis") as mock_hmset,
        patch("metadata.utils.redis_tools.RedisTools.publish") as mock_publish,
    ):
        SpaceTableIDRedis().push_table_id_detail(
            bk_tenant_id=bk_tenant_id,
            table_id_list=[table_id],
            is_publish=True,
        )

    redis_values = mock_hmset.call_args.args[1]
    redis_field = f"{expected_redis_table_id or table_id}|{bk_tenant_id}"
    assert list(redis_values) == [redis_field]
    mock_hmset.assert_called_once()
    mock_publish.assert_called_once_with(RESULT_TABLE_DETAIL_CHANNEL, [redis_field])
    return json.loads(redis_values[redis_field])


@pytest.mark.django_db(databases="__all__")
@override_settings(ENABLE_MULTI_TENANT_MODE=True)
def test_push_es_current_with_doris_history_exact_detail():
    table_id = "2_bklog.demo"
    _create_cluster(
        bk_tenant_id=TENANT_ID,
        cluster_id=ES_CLUSTER_ID,
        cluster_type=models.ClusterInfo.TYPE_ES,
        cluster_name="es-prod",
    )
    _create_cluster(
        bk_tenant_id=TENANT_ID,
        cluster_id=DORIS_CLUSTER_ID,
        cluster_type=models.ClusterInfo.TYPE_DORIS,
        cluster_name="doris-prod",
    )
    _create_result_table(
        bk_tenant_id=TENANT_ID,
        table_id=table_id,
        default_storage=models.ClusterInfo.TYPE_ES,
    )
    _create_es_storage(
        bk_tenant_id=TENANT_ID,
        table_id=table_id,
        cluster_id=ES_CLUSTER_ID,
        index_set="bklog_index_set_123",
    )
    _create_doris_storage(
        bk_tenant_id=TENANT_ID,
        table_id=table_id,
        cluster_id=DORIS_CLUSTER_ID,
        bkbase_table_id="2_bklog_demo_analysis",
        index_set="bklog_index_set_123",
    )
    _create_storage_segment(
        bk_tenant_id=TENANT_ID,
        table_id=table_id,
        cluster_id=DORIS_CLUSTER_ID,
        enable_time=ES_ENABLE_TIME,
        is_current=False,
    )
    _create_storage_segment(
        bk_tenant_id=TENANT_ID,
        table_id=table_id,
        cluster_id=ES_CLUSTER_ID,
        enable_time=DORIS_ENABLE_TIME,
        is_current=True,
    )
    models.ResultTableOption.objects.create(
        bk_tenant_id=TENANT_ID,
        table_id=table_id,
        name="time_field",
        value='{"name":"dtEventTimeStamp","type":"date","unit":"millisecond"}',
        value_type="dict",
    )
    models.ResultTableOption.objects.create(
        bk_tenant_id=TENANT_ID,
        table_id=table_id,
        name="need_add_time",
        value="true",
        value_type=models.ResultTableOption.TYPE_BOOL,
    )
    models.ESFieldQueryAliasOption.objects.create(
        bk_tenant_id=TENANT_ID,
        table_id=table_id,
        query_alias="message",
        field_path="log",
        is_deleted=False,
    )

    detail = _push_and_get_detail(bk_tenant_id=TENANT_ID, table_id=table_id)

    assert detail == {
        "storage_type": "elasticsearch",
        "storage_id": ES_CLUSTER_ID,
        "db": "bklog_index_set_123",
        "measurement": "__default__",
        "source_type": "log",
        "options": {
            "time_field": {"name": "dtEventTimeStamp", "type": "date", "unit": "millisecond"},
            "need_add_time": True,
        },
        "storage_cluster_records": [
            {
                "storage_id": ES_CLUSTER_ID,
                "storage_type": "elasticsearch",
                "db": "bklog_index_set_123",
                "measurement": "__default__",
                "source_type": "log",
                "enable_time": int(DORIS_ENABLE_TIME.timestamp()),
            },
            {
                "storage_id": DORIS_CLUSTER_ID,
                "storage_type": "bk_sql",
                "storage_name": "doris-prod",
                "cluster_name": "doris-prod",
                "db": "2_bklog_demo_analysis",
                "measurement": "doris",
                "enable_time": int(ES_ENABLE_TIME.timestamp()),
            },
        ],
        "data_label": "2_bklog_demo",
        "labels": {"scene": "log"},
        "field_alias": {"message": "log"},
    }


@pytest.mark.django_db(databases="__all__")
@override_settings(ENABLE_MULTI_TENANT_MODE=True)
def test_push_doris_current_with_es_history_exact_detail():
    table_id = "2_bklog.demo"
    _create_cluster(
        bk_tenant_id=TENANT_ID,
        cluster_id=ES_CLUSTER_ID,
        cluster_type=models.ClusterInfo.TYPE_ES,
        cluster_name="es-prod",
    )
    _create_cluster(
        bk_tenant_id=TENANT_ID,
        cluster_id=DORIS_CLUSTER_ID,
        cluster_type=models.ClusterInfo.TYPE_DORIS,
        cluster_name="doris-prod",
    )
    _create_result_table(
        bk_tenant_id=TENANT_ID,
        table_id=table_id,
        default_storage=models.ClusterInfo.TYPE_DORIS,
    )
    _create_es_storage(
        bk_tenant_id=TENANT_ID,
        table_id=table_id,
        cluster_id=ES_CLUSTER_ID,
        index_set="bklog_index_set_123",
    )
    _create_doris_storage(
        bk_tenant_id=TENANT_ID,
        table_id=table_id,
        cluster_id=DORIS_CLUSTER_ID,
        bkbase_table_id="2_bklog_demo_analysis",
        index_set="bklog_index_set_123",
    )
    _create_storage_segment(
        bk_tenant_id=TENANT_ID,
        table_id=table_id,
        cluster_id=ES_CLUSTER_ID,
        enable_time=ES_ENABLE_TIME,
        is_current=False,
    )
    _create_storage_segment(
        bk_tenant_id=TENANT_ID,
        table_id=table_id,
        cluster_id=DORIS_CLUSTER_ID,
        enable_time=DORIS_ENABLE_TIME,
        is_current=True,
    )
    models.ESFieldQueryAliasOption.objects.create(
        bk_tenant_id=TENANT_ID,
        table_id=table_id,
        query_alias="message",
        field_path="log",
        is_deleted=False,
    )

    detail = _push_and_get_detail(bk_tenant_id=TENANT_ID, table_id=table_id)

    assert detail == {
        "storage_type": "bk_sql",
        "storage_id": DORIS_CLUSTER_ID,
        "storage_name": "doris-prod",
        "cluster_name": "doris-prod",
        "db": "2_bklog_demo_analysis",
        "measurement": "doris",
        "storage_cluster_records": [
            {
                "storage_id": DORIS_CLUSTER_ID,
                "storage_type": "bk_sql",
                "storage_name": "doris-prod",
                "cluster_name": "doris-prod",
                "db": "2_bklog_demo_analysis",
                "measurement": "doris",
                "enable_time": int(DORIS_ENABLE_TIME.timestamp()),
            },
            {
                "storage_id": ES_CLUSTER_ID,
                "storage_type": "elasticsearch",
                "db": "bklog_index_set_123",
                "measurement": "__default__",
                "source_type": "log",
                "enable_time": int(ES_ENABLE_TIME.timestamp()),
            },
        ],
        "data_label": "2_bklog_demo",
        "labels": {"scene": "log"},
        "field_alias": {"message": "log"},
    }


@pytest.mark.django_db(databases="__all__")
@override_settings(ENABLE_MULTI_TENANT_MODE=True)
def test_virtual_result_table_uses_origin_storage_history():
    entity_table_id = "2_bklog.entity"
    virtual_table_id = "2_bklog.virtual"
    _create_cluster(
        bk_tenant_id=TENANT_ID,
        cluster_id=ES_CLUSTER_ID,
        cluster_type=models.ClusterInfo.TYPE_ES,
        cluster_name="es-prod",
    )
    _create_cluster(
        bk_tenant_id=TENANT_ID,
        cluster_id=DORIS_CLUSTER_ID,
        cluster_type=models.ClusterInfo.TYPE_DORIS,
        cluster_name="doris-prod",
    )
    _create_result_table(
        bk_tenant_id=TENANT_ID,
        table_id=entity_table_id,
        default_storage=models.ClusterInfo.TYPE_ES,
        data_label="entity-label",
    )
    _create_result_table(
        bk_tenant_id=TENANT_ID,
        table_id=virtual_table_id,
        default_storage=models.ClusterInfo.TYPE_ES,
        data_label="virtual-label",
        labels={"scene": "virtual-log"},
    )
    _create_es_storage(
        bk_tenant_id=TENANT_ID,
        table_id=entity_table_id,
        cluster_id=ES_CLUSTER_ID,
        index_set="entity_es_index",
    )
    _create_doris_storage(
        bk_tenant_id=TENANT_ID,
        table_id=entity_table_id,
        cluster_id=DORIS_CLUSTER_ID,
        bkbase_table_id="entity_doris_table",
        index_set="entity_es_index",
    )
    _create_es_storage(
        bk_tenant_id=TENANT_ID,
        table_id=virtual_table_id,
        cluster_id=ES_CLUSTER_ID,
        index_set="virtual_es_index",
        source_type="bkdata",
        origin_table_id=entity_table_id,
    )
    _create_storage_segment(
        bk_tenant_id=TENANT_ID,
        table_id=entity_table_id,
        cluster_id=DORIS_CLUSTER_ID,
        enable_time=ES_ENABLE_TIME,
        is_current=False,
    )
    _create_storage_segment(
        bk_tenant_id=TENANT_ID,
        table_id=entity_table_id,
        cluster_id=ES_CLUSTER_ID,
        enable_time=DORIS_ENABLE_TIME,
        is_current=True,
    )
    models.ESFieldQueryAliasOption.objects.create(
        bk_tenant_id=TENANT_ID,
        table_id=virtual_table_id,
        query_alias="virtual_message",
        field_path="virtual.log",
        is_deleted=False,
    )

    detail = _push_and_get_detail(bk_tenant_id=TENANT_ID, table_id=virtual_table_id)

    assert detail["db"] == "virtual_es_index"
    assert detail["source_type"] == "bkdata"
    assert detail["data_label"] == "virtual-label"
    assert detail["labels"] == {"scene": "virtual-log"}
    assert detail["field_alias"] == {"virtual_message": "virtual.log"}
    assert detail["storage_cluster_records"] == [
        {
            "storage_id": ES_CLUSTER_ID,
            "storage_type": "elasticsearch",
            "db": "virtual_es_index",
            "measurement": "__default__",
            "source_type": "bkdata",
            "enable_time": int(DORIS_ENABLE_TIME.timestamp()),
        },
        {
            "storage_id": DORIS_CLUSTER_ID,
            "storage_type": "bk_sql",
            "storage_name": "doris-prod",
            "cluster_name": "doris-prod",
            "db": "entity_doris_table",
            "measurement": "doris",
            "enable_time": int(ES_ENABLE_TIME.timestamp()),
        },
    ]


@pytest.mark.django_db(databases="__all__")
@override_settings(ENABLE_MULTI_TENANT_MODE=True)
def test_virtual_result_table_missing_metadata_falls_back_to_origin():
    entity_table_id = "2_bklog.entity_fallback"
    virtual_table_id = "2_bklog.virtual_fallback"
    _create_cluster(
        bk_tenant_id=TENANT_ID,
        cluster_id=ES_CLUSTER_ID,
        cluster_type=models.ClusterInfo.TYPE_ES,
        cluster_name="es-prod",
    )
    _create_result_table(
        bk_tenant_id=TENANT_ID,
        table_id=entity_table_id,
        default_storage=models.ClusterInfo.TYPE_ES,
        data_label="entity-label",
        labels={"scene": "entity-log"},
    )
    _create_result_table(
        bk_tenant_id=TENANT_ID,
        table_id=virtual_table_id,
        default_storage=models.ClusterInfo.TYPE_ES,
    )
    models.ResultTable.objects.filter(bk_tenant_id=TENANT_ID, table_id=virtual_table_id).update(
        data_label="",
        labels={},
    )
    _create_es_storage(
        bk_tenant_id=TENANT_ID,
        table_id=entity_table_id,
        cluster_id=ES_CLUSTER_ID,
        index_set="entity_fallback_index",
    )
    _create_es_storage(
        bk_tenant_id=TENANT_ID,
        table_id=virtual_table_id,
        cluster_id=ES_CLUSTER_ID,
        index_set="virtual_fallback_index",
        origin_table_id=entity_table_id,
    )
    models.ESFieldQueryAliasOption.objects.create(
        bk_tenant_id=TENANT_ID,
        table_id=entity_table_id,
        query_alias="message",
        field_path="origin.message",
        is_deleted=False,
    )

    detail = _push_and_get_detail(bk_tenant_id=TENANT_ID, table_id=virtual_table_id)

    assert detail["db"] == "virtual_fallback_index"
    assert detail["data_label"] == "entity-label"
    assert detail["labels"] == {"scene": "entity-log"}
    assert detail["field_alias"] == {"message": "origin.message"}


@pytest.mark.django_db(databases="__all__")
@override_settings(ENABLE_MULTI_TENANT_MODE=True)
def test_doris_only_virtual_route_uses_origin_es_history_config():
    entity_table_id = "2_bklog.doris_entity"
    virtual_table_id = "2_bklog.doris_virtual"
    _create_cluster(
        bk_tenant_id=TENANT_ID,
        cluster_id=ES_CLUSTER_ID,
        cluster_type=models.ClusterInfo.TYPE_ES,
        cluster_name="es-prod",
    )
    _create_cluster(
        bk_tenant_id=TENANT_ID,
        cluster_id=DORIS_CLUSTER_ID,
        cluster_type=models.ClusterInfo.TYPE_DORIS,
        cluster_name="doris-prod",
    )
    _create_result_table(
        bk_tenant_id=TENANT_ID,
        table_id=entity_table_id,
        default_storage=models.ClusterInfo.TYPE_DORIS,
    )
    _create_result_table(
        bk_tenant_id=TENANT_ID,
        table_id=virtual_table_id,
        default_storage=models.ClusterInfo.TYPE_DORIS,
    )
    _create_es_storage(
        bk_tenant_id=TENANT_ID,
        table_id=entity_table_id,
        cluster_id=ES_CLUSTER_ID,
        index_set="entity_es_index",
        source_type="entity-source",
    )
    _create_doris_storage(
        bk_tenant_id=TENANT_ID,
        table_id=entity_table_id,
        cluster_id=DORIS_CLUSTER_ID,
        bkbase_table_id="entity_doris_table",
        index_set="entity_doris_index_should_not_be_used",
        source_type="entity-doris-source",
    )
    _create_doris_storage(
        bk_tenant_id=TENANT_ID,
        table_id=virtual_table_id,
        cluster_id=DORIS_CLUSTER_ID,
        bkbase_table_id="virtual_doris_table",
        index_set="virtual_es_index",
        source_type="virtual-source",
        origin_table_id=entity_table_id,
    )
    _create_storage_segment(
        bk_tenant_id=TENANT_ID,
        table_id=entity_table_id,
        cluster_id=ES_CLUSTER_ID,
        enable_time=ES_ENABLE_TIME,
        is_current=False,
    )
    _create_storage_segment(
        bk_tenant_id=TENANT_ID,
        table_id=entity_table_id,
        cluster_id=DORIS_CLUSTER_ID,
        enable_time=DORIS_ENABLE_TIME,
        is_current=True,
    )

    detail = _push_and_get_detail(bk_tenant_id=TENANT_ID, table_id=virtual_table_id)

    assert detail["db"] == "virtual_doris_table"
    assert detail["storage_cluster_records"] == [
        {
            "storage_id": DORIS_CLUSTER_ID,
            "storage_type": "bk_sql",
            "storage_name": "doris-prod",
            "cluster_name": "doris-prod",
            "db": "virtual_doris_table",
            "measurement": "doris",
            "enable_time": int(DORIS_ENABLE_TIME.timestamp()),
        },
        {
            "storage_id": ES_CLUSTER_ID,
            "storage_type": "elasticsearch",
            "db": "entity_es_index",
            "measurement": "__default__",
            "source_type": "entity-source",
            "enable_time": int(ES_ENABLE_TIME.timestamp()),
        },
    ]

    # ESStorage 缺失时不能使用 DorisStorage 的同名字段伪造 ES 历史配置。
    models.ESStorage.objects.filter(bk_tenant_id=TENANT_ID, table_id=entity_table_id).delete()
    detail_without_es_storage = _push_and_get_detail(bk_tenant_id=TENANT_ID, table_id=virtual_table_id)
    assert detail_without_es_storage["storage_cluster_records"] == [
        {
            "storage_id": DORIS_CLUSTER_ID,
            "storage_type": "bk_sql",
            "storage_name": "doris-prod",
            "cluster_name": "doris-prod",
            "db": "virtual_doris_table",
            "measurement": "doris",
            "enable_time": int(DORIS_ENABLE_TIME.timestamp()),
        }
    ]


@pytest.mark.django_db(databases="__all__")
@override_settings(ENABLE_MULTI_TENANT_MODE=True)
def test_orphan_es_storage_without_result_table_keeps_legacy_route():
    table_id = "legacy_orphan_es"
    _create_cluster(
        bk_tenant_id=TENANT_ID,
        cluster_id=ES_CLUSTER_ID,
        cluster_type=models.ClusterInfo.TYPE_ES,
        cluster_name="es-prod",
    )
    _create_es_storage(
        bk_tenant_id=TENANT_ID,
        table_id=table_id,
        cluster_id=ES_CLUSTER_ID,
        index_set="legacy_orphan_index",
        source_type="legacy-source",
    )

    detail = _push_and_get_detail(
        bk_tenant_id=TENANT_ID,
        table_id=table_id,
        expected_redis_table_id=f"{table_id}.__default__",
    )

    assert detail == {
        "storage_id": ES_CLUSTER_ID,
        "db": "legacy_orphan_index",
        "measurement": "__default__",
        "source_type": "legacy-source",
        "options": {},
        "storage_type": "elasticsearch",
        "storage_cluster_records": [],
        "data_label": "",
        "labels": {},
        "field_alias": {},
    }


@pytest.mark.django_db(databases="__all__")
@override_settings(ENABLE_MULTI_TENANT_MODE=True)
def test_same_table_id_is_isolated_by_tenant():
    table_id = "2_bklog.same_table"
    tenant_configs = [
        (TENANT_ID, ES_CLUSTER_ID, DORIS_CLUSTER_ID, "tenant-a-es", "tenant-a-doris"),
        (OTHER_TENANT_ID, ES_CLUSTER_ID + 10, DORIS_CLUSTER_ID + 10, "tenant-b-es", "tenant-b-doris"),
    ]
    for tenant_id, es_cluster_id, doris_cluster_id, es_index, doris_table in tenant_configs:
        _create_cluster(
            bk_tenant_id=tenant_id,
            cluster_id=es_cluster_id,
            cluster_type=models.ClusterInfo.TYPE_ES,
            cluster_name=f"{tenant_id}-es",
        )
        _create_cluster(
            bk_tenant_id=tenant_id,
            cluster_id=doris_cluster_id,
            cluster_type=models.ClusterInfo.TYPE_DORIS,
            cluster_name=f"{tenant_id}-doris",
        )
        _create_result_table(
            bk_tenant_id=tenant_id,
            table_id=table_id,
            default_storage=models.ClusterInfo.TYPE_ES,
            data_label=f"{tenant_id}-label",
        )
        _create_es_storage(
            bk_tenant_id=tenant_id,
            table_id=table_id,
            cluster_id=es_cluster_id,
            index_set=es_index,
        )
        _create_doris_storage(
            bk_tenant_id=tenant_id,
            table_id=table_id,
            cluster_id=doris_cluster_id,
            bkbase_table_id=doris_table,
            index_set=es_index,
        )
        _create_storage_segment(
            bk_tenant_id=tenant_id,
            table_id=table_id,
            cluster_id=doris_cluster_id,
            enable_time=ES_ENABLE_TIME,
            is_current=False,
        )
        _create_storage_segment(
            bk_tenant_id=tenant_id,
            table_id=table_id,
            cluster_id=es_cluster_id,
            enable_time=DORIS_ENABLE_TIME,
            is_current=True,
        )

    tenant_a_detail = _push_and_get_detail(bk_tenant_id=TENANT_ID, table_id=table_id)
    tenant_b_detail = _push_and_get_detail(bk_tenant_id=OTHER_TENANT_ID, table_id=table_id)

    assert tenant_a_detail["db"] == "tenant-a-es"
    assert tenant_a_detail["data_label"] == f"{TENANT_ID}-label"
    assert {record["storage_id"] for record in tenant_a_detail["storage_cluster_records"]} == {
        ES_CLUSTER_ID,
        DORIS_CLUSTER_ID,
    }
    assert "tenant-b" not in json.dumps(tenant_a_detail)

    assert tenant_b_detail["db"] == "tenant-b-es"
    assert tenant_b_detail["data_label"] == f"{OTHER_TENANT_ID}-label"
    assert {record["storage_id"] for record in tenant_b_detail["storage_cluster_records"]} == {
        ES_CLUSTER_ID + 10,
        DORIS_CLUSTER_ID + 10,
    }
    assert "tenant-a" not in json.dumps(tenant_b_detail)


@pytest.mark.django_db(databases="__all__")
def test_same_metric_table_id_fields_are_isolated_by_tenant():
    table_id = "2_bkmonitor.same_metric_table"
    groups = []
    for index, tenant_id in enumerate([TENANT_ID, OTHER_TENANT_ID], start=1):
        group = models.TimeSeriesGroup.objects.create(
            bk_tenant_id=tenant_id,
            bk_data_id=50010 + index,
            bk_biz_id=2,
            table_id=table_id,
            time_series_group_name=f"tenant-group-{index}",
            creator="system",
            last_modify_user="system",
        )
        models.TimeSeriesMetric.objects.create(
            group_id=group.time_series_group_id,
            table_id=table_id,
            field_name=f"metric_{index}",
        )
        groups.append(group)

    redis_client = SpaceTableIDRedis()
    tenant_fields = redis_client._compose_table_id_fields(table_ids={table_id}, bk_tenant_id=TENANT_ID)
    other_tenant_fields = redis_client._compose_table_id_fields(
        table_ids={table_id},
        bk_tenant_id=OTHER_TENANT_ID,
    )

    assert tenant_fields[table_id] == {"metric_1"}
    assert other_tenant_fields[table_id] == {"metric_2"}


@pytest.mark.django_db(databases="__all__")
@override_settings(ENABLE_MULTI_TENANT_MODE=True)
def test_es_a_to_b_to_a_keeps_all_history_segments():
    table_id = "2_bklog.es_a_b_a"
    second_es_cluster_id = ES_CLUSTER_ID + 1
    _create_cluster(
        bk_tenant_id=TENANT_ID,
        cluster_id=ES_CLUSTER_ID,
        cluster_type=models.ClusterInfo.TYPE_ES,
        cluster_name="es-a",
    )
    _create_cluster(
        bk_tenant_id=TENANT_ID,
        cluster_id=second_es_cluster_id,
        cluster_type=models.ClusterInfo.TYPE_ES,
        cluster_name="es-b",
    )
    _create_result_table(
        bk_tenant_id=TENANT_ID,
        table_id=table_id,
        default_storage=models.ClusterInfo.TYPE_ES,
    )
    _create_es_storage(
        bk_tenant_id=TENANT_ID,
        table_id=table_id,
        cluster_id=ES_CLUSTER_ID,
        index_set="es_a_b_a_index",
    )
    segment_times = [
        datetime.datetime(2024, 7, 1, tzinfo=datetime.timezone.utc),
        datetime.datetime(2024, 8, 1, tzinfo=datetime.timezone.utc),
        datetime.datetime(2024, 9, 1, tzinfo=datetime.timezone.utc),
    ]
    for cluster_id, enable_time, is_current in zip(
        [ES_CLUSTER_ID, second_es_cluster_id, ES_CLUSTER_ID],
        segment_times,
        [False, False, True],
        strict=True,
    ):
        _create_storage_segment(
            bk_tenant_id=TENANT_ID,
            table_id=table_id,
            cluster_id=cluster_id,
            enable_time=enable_time,
            is_current=is_current,
        )

    detail = _push_and_get_detail(bk_tenant_id=TENANT_ID, table_id=table_id)

    assert [record["storage_id"] for record in detail["storage_cluster_records"]] == [
        ES_CLUSTER_ID,
        second_es_cluster_id,
        ES_CLUSTER_ID,
    ]
    assert [record["enable_time"] for record in detail["storage_cluster_records"]] == [
        int(enable_time.timestamp()) for enable_time in reversed(segment_times)
    ]


@pytest.mark.django_db(databases="__all__")
@override_settings(ENABLE_MULTI_TENANT_MODE=True)
def test_batch_mixed_storage_detail_queries_do_not_grow_per_table():
    _create_cluster(
        bk_tenant_id=TENANT_ID,
        cluster_id=ES_CLUSTER_ID,
        cluster_type=models.ClusterInfo.TYPE_ES,
        cluster_name="es-prod",
    )
    _create_cluster(
        bk_tenant_id=TENANT_ID,
        cluster_id=DORIS_CLUSTER_ID,
        cluster_type=models.ClusterInfo.TYPE_DORIS,
        cluster_name="doris-prod",
    )
    table_ids = []
    for index in range(12):
        table_id = f"2_bklog.batch_{index}"
        table_ids.append(table_id)
        _create_result_table(
            bk_tenant_id=TENANT_ID,
            table_id=table_id,
            default_storage=models.ClusterInfo.TYPE_ES if index % 2 == 0 else models.ClusterInfo.TYPE_DORIS,
        )
        _create_es_storage(
            bk_tenant_id=TENANT_ID,
            table_id=table_id,
            cluster_id=ES_CLUSTER_ID,
            index_set=f"batch_es_{index}",
        )
        _create_doris_storage(
            bk_tenant_id=TENANT_ID,
            table_id=table_id,
            cluster_id=DORIS_CLUSTER_ID,
            bkbase_table_id=f"batch_doris_{index}",
            index_set=f"batch_es_{index}",
        )
        _create_storage_segment(
            bk_tenant_id=TENANT_ID,
            table_id=table_id,
            cluster_id=DORIS_CLUSTER_ID if index % 2 == 0 else ES_CLUSTER_ID,
            enable_time=ES_ENABLE_TIME,
            is_current=False,
        )
        _create_storage_segment(
            bk_tenant_id=TENANT_ID,
            table_id=table_id,
            cluster_id=ES_CLUSTER_ID if index % 2 == 0 else DORIS_CLUSTER_ID,
            enable_time=DORIS_ENABLE_TIME,
            is_current=True,
        )

    def capture_queries(target_table_ids: list[str]) -> list[dict]:
        connection = connections[config.DATABASE_CONNECTION_NAME]
        with (
            patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis"),
            patch("metadata.utils.redis_tools.RedisTools.publish"),
            CaptureQueriesContext(connection) as captured_queries,
        ):
            SpaceTableIDRedis().push_table_id_detail(
                bk_tenant_id=TENANT_ID,
                table_id_list=target_table_ids,
                is_publish=False,
            )
        return captured_queries.captured_queries

    small_batch_queries = capture_queries(table_ids[:2])
    large_batch_queries = capture_queries(table_ids)

    assert len(large_batch_queries) <= len(small_batch_queries) + 2, (
        f"query count should remain effectively constant: small={len(small_batch_queries)}, "
        f"large={len(large_batch_queries)}"
    )

    select_sql = [query["sql"].lower() for query in large_batch_queries if "select" in query["sql"].lower()]
    table_query_limits = {
        "metadata_storageclusterrecord": 1,
        # metric、RecordRule 和日志存储路由各有一次固定批量查询，不随结果表数量增长。
        "metadata_clusterinfo": 3,
        "metadata_esstorage": 2,
        "metadata_dorisstorage": 2,
        "metadata_resulttableoption": 2,
        "metadata_esfieldqueryaliasoption": 2,
    }
    for table_name, max_query_count in table_query_limits.items():
        matching_queries = [sql for sql in select_sql if table_name in sql]
        assert len(matching_queries) <= max_query_count, (
            f"{table_name} should be loaded in batches, got {len(matching_queries)} queries: {matching_queries}"
        )


@pytest.mark.django_db(databases="__all__")
@override_settings(ENABLE_MULTI_TENANT_MODE=True)
def test_influx_metric_payload_keeps_existing_shape():
    table_id = "2_bkmonitor.influx_metric"
    proxy_storage_id = 198501
    _create_result_table(
        bk_tenant_id=TENANT_ID,
        table_id=table_id,
        default_storage=models.ClusterInfo.TYPE_INFLUXDB,
        data_label="influx-label",
        labels={"scene": "metric"},
    )
    models.InfluxDBProxyStorage.objects.create(
        id=proxy_storage_id,
        instance_cluster_name="influx-proxy",
        is_default=False,
        proxy_cluster_id=198502,
    )
    models.InfluxDBStorage.objects.create(
        bk_tenant_id=TENANT_ID,
        table_id=table_id,
        storage_cluster_id=198503,
        influxdb_proxy_storage_id=proxy_storage_id,
        database="metric_db",
        real_table_name="metric_measurement",
        partition_tag="bk_target_ip,bk_target_cloud_id",
    )
    models.ResultTableField.objects.create(
        bk_tenant_id=TENANT_ID,
        table_id=table_id,
        field_name="influx_metric_value",
        field_type=models.ResultTableField.FIELD_TYPE_FLOAT,
        tag=models.ResultTableField.FIELD_TAG_METRIC,
        is_config_by_user=False,
    )

    detail = _push_and_get_detail(bk_tenant_id=TENANT_ID, table_id=table_id)

    assert detail == {
        "storage_id": 198502,
        "storage_name": "",
        "cluster_name": "influx-proxy",
        "db": "metric_db",
        "measurement": "metric_measurement",
        "vm_rt": "",
        "tags_key": ["bk_target_ip", "bk_target_cloud_id"],
        "storage_type": models.InfluxDBStorage.STORAGE_TYPE,
        "fields": ["influx_metric_value"],
        "measurement_type": "bk_exporter",
        "bcs_cluster_id": "",
        "data_label": "influx-label",
        "labels": {"scene": "metric"},
        "bk_data_id": 0,
    }


@pytest.mark.django_db(databases="__all__")
@override_settings(ENABLE_MULTI_TENANT_MODE=True)
def test_metric_payload_is_unchanged_when_pushed_with_log_table():
    metric_table_id = "2_bkmonitor.mixed_metric"
    log_table_id = "2_bklog.mixed_log"
    record_rule_table_id = "2_bkmonitor.record_rule.__default__"
    _create_result_table(
        bk_tenant_id=TENANT_ID,
        table_id=metric_table_id,
        default_storage=models.ClusterInfo.TYPE_VM,
    )
    _create_vm_metric_route(bk_tenant_id=TENANT_ID, table_id=metric_table_id)
    models.ResultTableField.objects.create(
        bk_tenant_id=TENANT_ID,
        table_id=metric_table_id,
        field_name="metric_value",
        field_type=models.ResultTableField.FIELD_TYPE_FLOAT,
        tag=models.ResultTableField.FIELD_TAG_METRIC,
        is_config_by_user=False,
    )
    _create_cluster(
        bk_tenant_id=TENANT_ID,
        cluster_id=ES_CLUSTER_ID,
        cluster_type=models.ClusterInfo.TYPE_ES,
        cluster_name="es-prod",
    )
    _create_result_table(
        bk_tenant_id=TENANT_ID,
        table_id=log_table_id,
        default_storage=models.ClusterInfo.TYPE_ES,
    )
    _create_es_storage(
        bk_tenant_id=TENANT_ID,
        table_id=log_table_id,
        cluster_id=ES_CLUSTER_ID,
        index_set="mixed_log_index",
    )
    models.RecordRule.objects.create(
        bk_tenant_id=TENANT_ID,
        space_type="bkcc",
        space_id="2",
        table_id=record_rule_table_id,
        record_name="mixed-record-rule",
        rule_metrics={"record": "precomputed_metric"},
        vm_cluster_id=198402,
        dst_vm_table_id="vm_record_rule",
        creator="system",
        updater="system",
    )

    def push_and_collect(table_ids: list[str]) -> dict[str, str]:
        with (
            patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis") as mock_hmset,
            patch("metadata.utils.redis_tools.RedisTools.publish"),
        ):
            SpaceTableIDRedis().push_table_id_detail(
                bk_tenant_id=TENANT_ID,
                table_id_list=table_ids,
                is_publish=True,
            )
        result = {}
        for call in mock_hmset.call_args_list:
            result.update(call.args[1])
        return result

    metric_only = push_and_collect([metric_table_id])
    mixed = push_and_collect([metric_table_id, log_table_id])
    metric_redis_field = f"{metric_table_id}|{TENANT_ID}"
    log_redis_field = f"{log_table_id}|{TENANT_ID}"

    assert mixed[metric_redis_field] == metric_only[metric_redis_field]
    assert log_redis_field in mixed
    assert json.loads(mixed[f"{record_rule_table_id}|{TENANT_ID}"]) == {
        "vm_rt": "vm_record_rule",
        "storage_id": 198402,
        "cluster_name": "",
        "storage_name": "",
        "db": "",
        "measurement": "",
        "tags_key": [],
        "fields": ["precomputed_metric"],
        "measurement_type": "bk_split_measurement",
        "bcs_cluster_id": "",
        "data_label": "",
        "labels": {},
        "storage_type": models.RecordRule.STORAGE_TYPE,
        "bk_data_id": None,
    }


@pytest.mark.django_db(databases="__all__")
@override_settings(ENABLE_MULTI_TENANT_MODE=True)
def test_501_log_tables_are_written_and_published_in_two_batches():
    _create_cluster(
        bk_tenant_id=TENANT_ID,
        cluster_id=ES_CLUSTER_ID,
        cluster_type=models.ClusterInfo.TYPE_ES,
        cluster_name="es-prod",
    )
    table_ids = [f"2_bklog.batch_boundary_{index}" for index in range(501)]
    models.ResultTable.objects.bulk_create(
        [
            models.ResultTable(
                bk_tenant_id=TENANT_ID,
                table_id=table_id,
                table_name_zh=table_id,
                is_custom_table=False,
                schema_type=models.ResultTable.SCHEMA_TYPE_FREE,
                default_storage=models.ClusterInfo.TYPE_ES,
                creator="system",
                last_modify_user="system",
            )
            for table_id in table_ids
        ]
    )
    models.ESStorage.objects.bulk_create(
        [
            models.ESStorage(
                bk_tenant_id=TENANT_ID,
                table_id=table_id,
                storage_cluster_id=ES_CLUSTER_ID,
                index_set=f"batch_boundary_{index}",
                source_type="log",
                need_create_index=False,
            )
            for index, table_id in enumerate(table_ids)
        ]
    )

    with (
        patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis") as mock_hmset,
        patch("metadata.utils.redis_tools.RedisTools.publish") as mock_publish,
    ):
        SpaceTableIDRedis().push_table_id_detail(
            bk_tenant_id=TENANT_ID,
            table_id_list=table_ids,
            is_publish=True,
        )

    assert mock_hmset.call_count == 2
    assert mock_publish.call_count == 2
    written_fields = set()
    published_fields = set()
    for redis_key, redis_values in (call.args for call in mock_hmset.call_args_list):
        assert redis_key == RESULT_TABLE_DETAIL_KEY
        assert len(redis_values) <= SpaceTableIDRedis.TABLE_ID_DETAIL_BATCH_SIZE
        written_fields.update(redis_values)
    for channel, redis_fields in (call.args for call in mock_publish.call_args_list):
        assert channel == RESULT_TABLE_DETAIL_CHANNEL
        assert len(redis_fields) <= SpaceTableIDRedis.TABLE_ID_DETAIL_BATCH_SIZE
        published_fields.update(redis_fields)

    expected_fields = {f"{table_id}|{TENANT_ID}" for table_id in table_ids}
    assert written_fields == expected_fields
    assert published_fields == expected_fields


@pytest.mark.django_db(databases="__all__")
@override_settings(ENABLE_MULTI_TENANT_MODE=True)
@pytest.mark.parametrize("default_storage", [models.ClusterInfo.TYPE_ES, models.ClusterInfo.TYPE_DORIS])
def test_incomplete_default_log_storage_does_not_fall_back_to_metric_route(default_storage):
    table_id = f"2_bklog.incomplete_{default_storage}"
    _create_result_table(
        bk_tenant_id=TENANT_ID,
        table_id=table_id,
        default_storage=default_storage,
    )
    # 保留旧指标存储记录，模拟 ES/Doris 切换完成但当前日志 Storage 配置不完整的异常状态。
    _create_vm_metric_route(bk_tenant_id=TENANT_ID, table_id=table_id)

    with (
        patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis") as mock_hmset,
        patch("metadata.utils.redis_tools.RedisTools.publish") as mock_publish,
    ):
        SpaceTableIDRedis().push_table_id_detail(
            bk_tenant_id=TENANT_ID,
            table_id_list=[table_id],
            is_publish=True,
        )

    mock_hmset.assert_not_called()
    mock_publish.assert_not_called()


@pytest.mark.django_db(databases="__all__")
@override_settings(ENABLE_MULTI_TENANT_MODE=True)
def test_metric_route_redis_write_error_keeps_propagating():
    table_id = "2_bkmonitor.metric_write_error"
    _create_result_table(
        bk_tenant_id=TENANT_ID,
        table_id=table_id,
        default_storage=models.ClusterInfo.TYPE_VM,
    )
    _create_vm_metric_route(bk_tenant_id=TENANT_ID, table_id=table_id)

    with (
        patch(
            "metadata.utils.redis_tools.RedisTools.hmset_to_redis",
            side_effect=RuntimeError("redis unavailable"),
        ),
        patch("metadata.utils.redis_tools.RedisTools.publish") as mock_publish,
        pytest.raises(RuntimeError, match="redis unavailable"),
    ):
        SpaceTableIDRedis().push_table_id_detail(
            bk_tenant_id=TENANT_ID,
            table_id_list=[table_id],
            is_publish=True,
        )

    mock_publish.assert_not_called()


@pytest.mark.django_db(databases="__all__")
@override_settings(ENABLE_MULTI_TENANT_MODE=True)
def test_log_route_redis_write_error_keeps_post_process_tolerance():
    table_id = "2_bklog.log_write_error"
    _create_cluster(
        bk_tenant_id=TENANT_ID,
        cluster_id=ES_CLUSTER_ID,
        cluster_type=models.ClusterInfo.TYPE_ES,
        cluster_name="es-prod",
    )
    _create_result_table(
        bk_tenant_id=TENANT_ID,
        table_id=table_id,
        default_storage=models.ClusterInfo.TYPE_ES,
    )
    _create_es_storage(
        bk_tenant_id=TENANT_ID,
        table_id=table_id,
        cluster_id=ES_CLUSTER_ID,
        index_set="log_write_error_index",
    )

    with (
        patch(
            "metadata.utils.redis_tools.RedisTools.hmset_to_redis",
            side_effect=RuntimeError("redis unavailable"),
        ),
        patch("metadata.utils.redis_tools.RedisTools.publish") as mock_publish,
    ):
        SpaceTableIDRedis().push_table_id_detail(
            bk_tenant_id=TENANT_ID,
            table_id_list=[table_id],
            is_publish=True,
        )

    mock_publish.assert_not_called()


@pytest.mark.django_db(databases="__all__")
@override_settings(ENABLE_MULTI_TENANT_MODE=True)
@pytest.mark.parametrize("table_id_list", [None, []])
def test_none_and_empty_table_id_list_keep_tenant_full_refresh_compatibility(table_id_list):
    _create_cluster(
        bk_tenant_id=TENANT_ID,
        cluster_id=ES_CLUSTER_ID,
        cluster_type=models.ClusterInfo.TYPE_ES,
        cluster_name="es-prod",
    )
    expected_fields = set()
    for index in range(2):
        table_id = f"one_part_table_{index}"
        expected_fields.add(f"{table_id}.__default__|{TENANT_ID}")
        _create_result_table(
            bk_tenant_id=TENANT_ID,
            table_id=table_id,
            default_storage=models.ClusterInfo.TYPE_ES,
        )
        _create_es_storage(
            bk_tenant_id=TENANT_ID,
            table_id=table_id,
            cluster_id=ES_CLUSTER_ID,
            index_set=f"full_refresh_{index}",
        )
    metric_table_id = "2_bkmonitor.full_refresh_metric"
    expected_fields.add(f"{metric_table_id}|{TENANT_ID}")
    _create_result_table(
        bk_tenant_id=TENANT_ID,
        table_id=metric_table_id,
        default_storage=models.ClusterInfo.TYPE_VM,
    )
    _create_vm_metric_route(bk_tenant_id=TENANT_ID, table_id=metric_table_id)

    with (
        patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis") as mock_hmset,
        patch("metadata.utils.redis_tools.RedisTools.publish") as mock_publish,
    ):
        SpaceTableIDRedis().push_table_id_detail(
            bk_tenant_id=TENANT_ID,
            table_id_list=table_id_list,
            is_publish=False,
        )

    redis_fields = {redis_field for call in mock_hmset.call_args_list for redis_field in call.args[1]}
    assert expected_fields <= redis_fields
    mock_publish.assert_not_called()
    assert all(redis_field.endswith(f"|{TENANT_ID}") for redis_field in redis_fields)
    assert all(call.args[0] == RESULT_TABLE_DETAIL_KEY for call in mock_hmset.call_args_list)


def test_empty_tenant_is_rejected():
    with pytest.raises(ValueError, match="bk_tenant_id is required"):
        SpaceTableIDRedis().push_table_id_detail(bk_tenant_id="")
