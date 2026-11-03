"""Doris 物理表反向同步：用途解析、当前存储及历史快照。"""

import pytest
from django.utils import timezone

from metadata import models
from metadata.models.data_link.constants import DataLinkKind
from metadata.task.bkbase import _get_doris_physical_tables, _reconcile_data_link_components

pytestmark = pytest.mark.django_db(databases="__all__")


def binding_config(storage_config=None, annotations=None):
    return {
        "metadata": {"name": "doris_binding", "annotations": annotations or {}, "labels": {"bk_biz_id": "2"}},
        "spec": {
            "data": {"name": "log_rt"},
            "storage": {"name": "doris_cluster"},
            "storage_config": storage_config or {},
        },
        "status": {"phase": "Ok"},
    }


@pytest.mark.parametrize("annotation_key", ["physical_table_name", "PhysicalTableName"])
def test_log_preserves_annotation_rule(annotation_key):
    config = binding_config({"db": "db", "table": "fallback"}, {annotation_key: "db.logs_*"})
    assert _get_doris_physical_tables(config) == {"main": "db.logs_*"}


@pytest.mark.parametrize(
    "storage_config,expected",
    [
        ({"db": "db", "table": "logs_*"}, {"main": "db.logs_*"}),
        ({"db": "db"}, {}),
        ({}, {}),
        (
            {
                "is_profiling": True,
                "db": "db",
                "table": "unused",
                "sample_table_name": "samples",
                "label_table_name": "labels",
            },
            {"sample": "db.samples", "label": "db.labels"},
        ),
        ({"is_profiling": True, "db": "db", "sample_table_name": "samples"}, {"sample": "db.samples"}),
        ({"is_profiling": True, "db": "db", "table": "unused"}, {}),
        ({"is_profiling": True, "sample_table_name": "samples"}, {}),
    ],
)
def test_physical_table_roles(storage_config, expected):
    annotations = {"physical_table_name": "db.not_a_third_table"} if storage_config.get("is_profiling") else {}
    assert _get_doris_physical_tables(binding_config(storage_config, annotations)) == expected


@pytest.fixture
def sync_environment(mocker):
    mocker.patch("metadata.task.bkbase.report_metadata_data_link_status_info")
    mocker.patch("metadata.task.bkbase.api.bk_login.list_tenant", return_value=[{"id": "system"}])
    mocker.patch("metadata.task.bkbase._check_storage_binding_references", return_value=[])
    rt = models.ResultTableConfig.objects.create(
        bk_tenant_id="system",
        namespace="bklog",
        name="log_rt",
        table_id="2.log",
        bkbase_table_id="2_log_rt",
        bk_biz_id=2,
        data_type="log",
        status="Ok",
    )
    remote = binding_config({"db": "db", "table": "logs_*"})
    rt_remote = {
        "metadata": {"name": "log_rt", "annotations": {"ResultTableId": "2_log_rt"}},
        "spec": {"bizId": 2, "dataType": "log"},
        "status": {"phase": "Ok"},
    }

    def list_components(**kwargs):
        if kwargs["bk_tenant_id"] != "system" or kwargs["namespace"] != "bklog":
            return []
        if kwargs["kind"] == DataLinkKind.get_choice_value(DataLinkKind.DORISBINDING.value):
            return [remote]
        if kwargs["kind"] == DataLinkKind.get_choice_value(DataLinkKind.RESULTTABLE.value):
            return [rt_remote]
        return []

    mocker.patch("metadata.task.bkbase.api.bkdata.list_data_link", side_effect=list_components)
    return rt, remote


def create_storage(**kwargs):
    values = dict(bk_tenant_id="system", table_id="2.log", bkbase_table_id="2_log_rt", storage_cluster_id=123)
    values.update(kwargs)
    return models.DorisStorage.objects.create(**values)


def create_record(**kwargs):
    values = dict(
        bk_tenant_id="system",
        table_id="2.log",
        cluster_id=123,
        creator="system",
        enable_time=timezone.now(),
        is_current=True,
    )
    values.update(kwargs)
    return models.StorageClusterRecord.objects.create(**values)


def test_sync_current_storage_and_preserve_history(sync_environment):
    storage = create_storage()
    current = create_record()
    preserved = [
        create_record(is_current=False),
        create_record(is_deleted=True),
        create_record(cluster_id=456),
        create_record(bk_tenant_id="other"),
        create_record(bkbase_table_id="2_old_rt"),
        create_record(physical_tables={"main": "db.old"}),
    ]
    before = [(record.bkbase_table_id, record.physical_tables) for record in preserved]
    other_storage = create_storage(bk_tenant_id="other")
    virtual = create_storage(table_id="2.virtual", origin_table_id="2.log")
    _reconcile_data_link_components()
    storage.refresh_from_db()
    current.refresh_from_db()
    assert storage.physical_tables == {"main": "db.logs_*"}
    assert (current.bkbase_table_id, current.physical_tables) == ("2_log_rt", storage.physical_tables)
    for record, original in zip(preserved, before):
        record.refresh_from_db()
        assert (record.bkbase_table_id, record.physical_tables) == original
    for untouched in (other_storage, virtual):
        untouched.refresh_from_db()
        assert untouched.physical_tables == {}

    binding = models.DorisStorageBindingConfig.objects.get(
        bk_tenant_id="system", namespace="bklog", name="doris_binding"
    )
    assert binding.table_id == "2.log"
    assert binding.physical_tables == storage.physical_tables
    count = models.StorageClusterRecord.objects.count()
    _reconcile_data_link_components()
    assert models.StorageClusterRecord.objects.count() == count


def test_late_association_and_empty_remote_preserves_data(sync_environment):
    rt, remote = sync_environment
    rt.table_id = ""
    rt.save(update_fields=["table_id"])
    _reconcile_data_link_components()
    assert not models.DorisStorage.objects.exists()
    storage = create_storage()
    record = create_record()
    rt.table_id = storage.table_id
    rt.save(update_fields=["table_id"])
    _reconcile_data_link_components()
    storage.refresh_from_db()
    assert storage.physical_tables == {"main": "db.logs_*"}
    remote["spec"]["storage_config"] = {}
    _reconcile_data_link_components()
    storage.refresh_from_db()
    record.refresh_from_db()
    binding = models.DorisStorageBindingConfig.objects.get(name="doris_binding")
    assert binding.physical_tables == storage.physical_tables == record.physical_tables == {"main": "db.logs_*"}


def test_profiling_binding_without_metadata_storage(sync_environment):
    _, remote = sync_environment
    remote["metadata"]["annotations"] = {"physical_table_name": "db.unused"}
    remote["spec"]["storage_config"] = {
        "is_profiling": True,
        "db": "db",
        "table": "unused",
        "sample_table_name": "samples",
        "label_table_name": "labels",
    }
    _reconcile_data_link_components()
    binding = models.DorisStorageBindingConfig.objects.get(name="doris_binding")
    assert binding.physical_tables == {"sample": "db.samples", "label": "db.labels"}
    assert not models.DorisStorage.objects.exists()
    assert not models.StorageClusterRecord.objects.exists()


def test_changed_tables_do_not_overwrite_snapshot(sync_environment):
    _, remote = sync_environment
    storage = create_storage()
    record = create_record()
    _reconcile_data_link_components()
    remote["spec"]["storage_config"]["table"] = "new_*"
    _reconcile_data_link_components()
    storage.refresh_from_db()
    record.refresh_from_db()
    assert storage.physical_tables == {"main": "db.new_*"}
    assert record.physical_tables == {"main": "db.logs_*"}
    assert models.StorageClusterRecord.objects.count() == 1


@pytest.mark.parametrize(
    "snapshot",
    [{"bkbase_table_id": "2_log_rt"}, {"physical_tables": {"main": "db.logs_*"}}],
)
def test_fill_only_missing_snapshot_field(sync_environment, snapshot):
    create_storage()
    record = create_record(**snapshot)
    _reconcile_data_link_components()
    record.refresh_from_db()
    assert record.bkbase_table_id == "2_log_rt"
    assert record.physical_tables == {"main": "db.logs_*"}


def test_different_bkbase_rt_is_not_updated(sync_environment):
    storage = create_storage(bkbase_table_id="2_other_rt")
    record = create_record()
    _reconcile_data_link_components()
    storage.refresh_from_db()
    record.refresh_from_db()
    assert storage.physical_tables == record.physical_tables == {}
    assert record.bkbase_table_id == ""


def test_no_history_record_is_created(sync_environment):
    storage = create_storage()
    _reconcile_data_link_components()
    storage.refresh_from_db()
    assert storage.physical_tables == {"main": "db.logs_*"}
    assert not models.StorageClusterRecord.objects.exists()
