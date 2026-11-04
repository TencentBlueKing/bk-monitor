"""Doris 在配置事务内分配版本，apply 只重复声明。"""

import json
from copy import deepcopy

import pytest
from django.db import transaction
from django.utils import timezone

from metadata import config, models
from metadata.models.data_link.data_link import DataLink
from metadata.models.doris_version import get_doris_config, preserve_optional_config, requires_new_table

pytestmark = pytest.mark.django_db(databases="__all__")


@pytest.fixture(params=[DataLink.BK_LOG, DataLink.CUSTOM_FORMAT_DORIS])
def version_records(request, mocker):
    mocker.patch("bkmonitor.utils.tenant.get_tenant_default_biz_id", return_value=2)
    mocker.patch("metadata.models.doris_version.publish_doris_route")
    mocker.patch("metadata.models.data_link.data_link.utils.get_registered_bkdata_data_id_name", return_value="source")
    mocker.patch("metadata.models.data_link.data_link.compose_databus_monitor_labels", return_value={})
    mocker.patch.object(DataLink, "_get_databus_monitor_label_table", return_value=None)
    mocker.patch.object(DataLink, "get_existing_component_config", return_value=None)
    models.ClusterInfo.objects.create(
        bk_tenant_id="system",
        cluster_id=99991,
        cluster_name="version_doris",
        cluster_type="doris",
        domain_name="localhost",
        port=9030,
        is_default_cluster=False,
    )
    rt = models.ResultTable.objects.create(
        bk_tenant_id="system",
        table_id="2.version",
        table_name_zh="version",
        bk_biz_id=2,
        is_custom_table=True,
        default_storage="doris",
        creator="system",
        last_modify_user="system",
        is_enable=True,
    )
    ds = models.DataSource.objects.create(
        bk_tenant_id="system",
        bk_data_id=99991,
        data_name="version",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="bk_log_text",
        created_from="bkdata",
        is_custom_source=True,
    )
    models.DataSourceResultTable.objects.create(bk_tenant_id="system", bk_data_id=ds.bk_data_id, table_id=rt.table_id)
    models.ResultTableField.objects.create(
        bk_tenant_id="system",
        table_id=rt.table_id,
        field_name="log",
        field_type="string",
        tag="dimension",
        is_config_by_user=True,
        creator="system",
        last_modify_user="system",
    )
    custom = request.param == DataLink.CUSTOM_FORMAT_DORIS
    option_name = (
        models.ResultTableOption.OPTION_CUSTOM_FORMAT_V4_DATA_LINK
        if custom
        else models.ResultTableOption.OPTION_V4_LOG_DATA_LINK
    )
    value = {
        "clean_rules": [{"input_id": "log", "output_id": "log", "operator": {"type": "assign"}}],
        "doris_storage_config": {"storage_keys": [], "tokenizers": {"log": "._"}},
    }
    if custom:
        value["target_storage_type"] = "doris"
    option = models.ResultTableOption.objects.create(
        bk_tenant_id="system",
        table_id=rt.table_id,
        name=option_name,
        value=json.dumps(value),
        value_type="string",
        creator="system",
    )
    link = DataLink.objects.create(
        bk_tenant_id="system",
        namespace="bklog",
        data_link_name="version_link",
        data_link_strategy=request.param,
        table_ids=[rt.table_id],
        bk_data_id=ds.bk_data_id,
    )
    storage = models.DorisStorage.create_table(table_id=rt.table_id, bk_tenant_id="system", storage_cluster_id=99991)
    return rt, ds, storage, link, option


def test_creation_allocates_v1_before_apply(version_records):
    rt, ds, storage, link, _ = version_records
    assert storage.table_version == 1
    assert storage.physical_tables == {"main": f"mapleleaf_2.bkm_doris_{storage.pk}_v1"}
    assert storage.bkbase_table_id == f"2_bkm_doris_{storage.pk}_v1"
    history = models.StorageClusterRecord.objects.get(table_id=rt.table_id)
    assert history.physical_tables == storage.physical_tables
    assert history.is_current
    assert not models.DorisStorageBindingConfig.objects.filter(table_id=rt.table_id).exists()


def test_repeated_apply_uses_explicit_name_and_preserves_version(version_records, mocker):
    rt, ds, storage, link, _ = version_records
    apply = mocker.patch.object(DataLink, "apply_data_link_with_retry", return_value={})
    for _ in range(2):
        link.apply_data_link(bk_biz_id=2, data_source=ds, table_id=rt.table_id)
    storage.refresh_from_db()
    assert storage.table_version == 1
    assert models.StorageClusterRecord.objects.filter(table_id=rt.table_id).count() == 1
    payload = apply.call_args.args[0]
    binding = next(c for c in payload if c["kind"] == "DorisBinding")
    assert binding["spec"]["storage_config"]["table"] == storage.versioned_name
    assert binding["spec"]["storage_config"]["db"] == "mapleleaf_2"
    assert binding["spec"]["data"]["name"] == storage.versioned_name
    assert models.ResultTableConfig.objects.filter(table_id=rt.table_id).count() == 1


def test_failed_apply_keeps_saved_version_and_history(version_records, mocker):
    rt, ds, storage, link, _ = version_records
    with transaction.atomic(using=config.DATABASE_CONNECTION_NAME):
        storage.advance_table_version("tester")
    name = storage.versioned_name
    apply = mocker.patch.object(DataLink, "apply_data_link_with_retry", side_effect=RuntimeError("apply failed"))
    with pytest.raises(RuntimeError, match="apply failed"):
        link.apply_data_link(bk_biz_id=2, data_source=ds, table_id=rt.table_id)
    storage.refresh_from_db()
    assert storage.table_version == 2
    assert models.StorageClusterRecord.objects.filter(table_id=rt.table_id).count() == 2
    apply.side_effect = None
    apply.return_value = {}
    link.apply_data_link(bk_biz_id=2, data_source=ds, table_id=rt.table_id)
    assert next(c for c in apply.call_args.args[0] if c["kind"] == "DorisBinding")["metadata"]["name"] == name


def test_modify_compares_old_configuration_and_retries_do_not_rotate(version_records, mocker):
    rt, ds, storage, link, option = version_records
    mocker.patch.object(models.ResultTable, "apply_datalink")
    mocker.patch("metadata.models.space.utils.get_space_by_table_id", return_value={})
    value = json.loads(option.value)
    value["doris_storage_config"]["tokenizers"] = {}
    rt.modify(operator="tester", option={option.name: value})
    storage.refresh_from_db()
    assert storage.table_version == 2
    rt.modify(operator="tester", option={option.name: value})
    storage.refresh_from_db()
    assert storage.table_version == 2
    value["doris_storage_config"]["support_hour_partition"] = True
    rt.modify(operator="tester", option={option.name: value})
    storage.refresh_from_db()
    assert storage.table_version == 3
    assert [
        r.physical_tables["main"]
        for r in models.StorageClusterRecord.objects.filter(table_id=rt.table_id).order_by("id")
    ] == [f"mapleleaf_2.bkm_doris_{storage.pk}_v{v}" for v in (1, 2, 3)]


def test_historical_resources_are_retained_and_latest_version_selected(version_records, mocker, settings):
    rt, ds, storage, link, _ = version_records
    settings.DATA_LINK_COMPONENT_REUSE_STRATEGIES = [DataLink.BK_LOG]
    apply = mocker.patch.object(DataLink, "apply_data_link_with_retry", return_value={})
    link.apply_data_link(bk_biz_id=2, data_source=ds, table_id=rt.table_id)
    old_name = storage.versioned_name
    with transaction.atomic(using=config.DATABASE_CONNECTION_NAME):
        storage.advance_table_version("tester")
    link.apply_data_link(bk_biz_id=2, data_source=ds, table_id=rt.table_id)
    assert models.ResultTableConfig.objects.filter(name=old_name).exists()
    assert models.DorisStorageBindingConfig.objects.filter(name=old_name).exists()
    assert link._get_absent_components_to_delete(apply.call_args.args[0], force_delete=True) == []
    assert storage.get_doris_binding_config().name == storage.versioned_name
    link.sync_metadata(table_id=rt.table_id, storage_cluster_id=99991)
    assert models.BkBaseResultTable.objects.get(data_link_name=link.pk).bkbase_rt_name == storage.versioned_name


def test_nonstructural_change_does_not_rotate(version_records, mocker):
    rt, _, storage, _, option = version_records
    mocker.patch.object(models.ResultTable, "apply_datalink")
    mocker.patch("metadata.models.space.utils.get_space_by_table_id", return_value={})
    value = json.loads(option.value)
    value["doris_storage_config"].update(alias="新名称", description="说明", flush_timeout=90)
    rt.modify(operator="tester", option={option.name: value})
    storage.refresh_from_db()
    assert storage.table_version == 1


@pytest.mark.parametrize(
    "key,before,after",
    [
        ("tokenizers", {}, {"log": "."}),
        ("tokenizers", {"log": "."}, {"log": ","}),
        ("tokenizers", {"log": "."}, {}),
        ("field_config_group", {}, {"search_zh": ["log"]}),
        ("field_config_group", {"search_zh": ["log"]}, {}),
        ("field_config_group", {}, {"search_en": ["log"]}),
        ("field_config_group", {}, {"bloomfilter": ["log"]}),
        ("json_fields", [], ["log"]),
        ("original_json_fields", ["log"], []),
        ("storage_keys", ["a", "b"], ["b", "a"]),
        ("table_type", "primary_table", "duplicate_table"),
        ("unique_partition_table", True, False),
        ("support_hour_partition", False, True),
        ("use_lowercase_field", False, True),
    ],
)
def test_costly_configuration_changes(key, before, after):
    assert requires_new_table(
        {"fields": [], "storage_config": {key: before}}, {"fields": [], "storage_config": {key: after}}
    )


@pytest.mark.parametrize(
    "old_fields,new_fields,expected",
    [
        ([{"field_name": "a", "field_type": "string"}], [], True),
        ([{"field_name": "a", "field_type": "string"}], [{"field_name": "a", "field_type": "long"}], True),
        ([], [{"field_name": "a", "field_type": "long"}], False),
    ],
)
def test_field_changes(old_fields, new_fields, expected):
    assert (
        requires_new_table({"fields": old_fields, "storage_config": {}}, {"fields": new_fields, "storage_config": {}})
        is expected
    )


def test_unordered_fields_and_explicit_clear(version_records):
    _, _, storage, _, option = version_records
    old = get_doris_config(storage.table_id, storage.bk_tenant_id)
    old["storage_config"]["field_config_group"] = {"search_zh": ["a", "b"]}
    new = deepcopy(old)
    new["storage_config"]["field_config_group"] = {"search_zh": ["b", "a"]}
    assert not requires_new_table(old, new)
    value = {option.name: {"doris_storage_config": {"tokenizers": {}}}}
    preserve_optional_config(value, old)
    assert value[option.name]["doris_storage_config"]["tokenizers"] == {}


def test_legacy_table_keeps_name_until_first_costly_change(version_records, mocker):
    rt, ds, storage, link, option = version_records
    models.StorageClusterRecord.objects.filter(table_id=rt.table_id).delete()
    storage.table_version = 0
    storage.bkbase_table_id = "2_legacy"
    storage.physical_tables = {}
    storage.save()
    mocker.patch.object(
        models.DorisStorage, "get_physical_table_name", return_value={"physical_table_name": "existing_db.legacy_table"}
    )
    with transaction.atomic(using=config.DATABASE_CONNECTION_NAME):
        storage.advance_table_version("tester")
    records = list(models.StorageClusterRecord.objects.filter(table_id=rt.table_id).order_by("id"))
    assert len(records) == 2
    assert records[0].physical_tables == {"main": "existing_db.legacy_table"}
    assert records[0].bkbase_table_id == "2_legacy"
    assert records[0].disable_time == records[1].enable_time
    assert storage.table_version == 1
    assert storage.physical_tables == {"main": f"existing_db.{storage.versioned_name}"}


def test_default_es_history_is_not_closed_by_doris_rotation(version_records):
    rt, _, storage, _, _ = version_records
    rt.default_storage = "elasticsearch"
    rt.save(update_fields=["default_storage"])
    es = models.StorageClusterRecord.objects.create(
        bk_tenant_id="system",
        table_id=rt.table_id,
        cluster_id=99992,
        is_current=True,
        enable_time=timezone.now(),
        creator="tester",
    )
    with transaction.atomic(using=config.DATABASE_CONNECTION_NAME):
        storage.advance_table_version("tester")
    es.refresh_from_db()
    assert es.is_current
    assert es.disable_time is None
    current = models.StorageClusterRecord.objects.get(table_id=rt.table_id, bkbase_table_id=storage.bkbase_table_id)
    assert current.disable_time is None
    assert not current.is_current


def test_log_declaration_is_registered_after_configuration_commit(
    version_records, mocker, django_capture_on_commit_callbacks
):
    rt, ds, storage, link, option = version_records
    if link.data_link_strategy != DataLink.BK_LOG:
        pytest.skip("自定义格式已采用提交后任务")
    mocker.patch.object(models.ResultTable, "get_related_datasource", return_value=ds)
    mocker.patch.object(models.ResultTable, "get_target_bk_biz_id", return_value=2)
    models.ResultTableOption.objects.create(
        bk_tenant_id="system",
        table_id=rt.table_id,
        name=models.ResultTableOption.OPTION_ENABLE_V4_LOG_DATA_LINK,
        value="true",
        value_type="bool",
        creator="tester",
    )
    apply = mocker.patch("metadata.task.datalink.apply_log_datalink")
    with django_capture_on_commit_callbacks(using=config.DATABASE_CONNECTION_NAME, execute=True):
        rt.apply_datalink(delay=False)
        apply.assert_not_called()
    apply.assert_called_once_with(bk_tenant_id="system", table_id=rt.table_id)


def test_versioned_routes_keep_distinct_bkbase_tables(version_records):
    from metadata.models.space.space_table_id_redis import SpaceTableIDRedis

    rt, _, storage, _, _ = version_records
    first_id = storage.bkbase_table_id
    with transaction.atomic(using=config.DATABASE_CONNECTION_NAME):
        storage.advance_table_version("tester")
    details, _ = SpaceTableIDRedis()._compose_log_table_id_detail(bk_tenant_id="system", table_id_list=[rt.table_id])
    route = details[rt.table_id]
    assert route["db"] == storage.bkbase_table_id
    assert {row["db"] for row in route["storage_cluster_records"]} == {first_id, storage.bkbase_table_id}
    assert {row["physical_tables"]["main"] for row in route["storage_cluster_records"]} == {
        f"mapleleaf_2.bkm_doris_{storage.pk}_v1",
        f"mapleleaf_2.bkm_doris_{storage.pk}_v2",
    }


def test_dual_write_reuses_es_alias_and_shared_rt(version_records, mocker):
    rt, ds, storage, link, option = version_records
    if link.data_link_strategy != DataLink.BK_LOG:
        pytest.skip("自定义格式只支持单目标存储")
    models.ClusterInfo.objects.create(
        bk_tenant_id="system",
        cluster_id=99992,
        cluster_name="version_es",
        cluster_type="elasticsearch",
        domain_name="localhost",
        port=9200,
        is_default_cluster=False,
    )
    models.ESStorage.objects.create(bk_tenant_id="system", table_id=rt.table_id, storage_cluster_id=99992)
    value = json.loads(option.value)
    value["es_storage_config"] = {"unique_field_list": []}
    option.value = json.dumps(value)
    option.save()
    apply = mocker.patch.object(DataLink, "apply_data_link_with_retry", return_value={})
    link.apply_data_link(bk_biz_id=2, data_source=ds, table_id=rt.table_id)
    first = next(c for c in apply.call_args.args[0] if c["kind"] == "ElasticSearchBinding")
    with transaction.atomic(using=config.DATABASE_CONNECTION_NAME):
        storage.advance_table_version("tester")
    link.apply_data_link(bk_biz_id=2, data_source=ds, table_id=rt.table_id)
    second = next(c for c in apply.call_args.args[0] if c["kind"] == "ElasticSearchBinding")
    assert first["metadata"]["name"] == second["metadata"]["name"]
    assert {key: value for key, value in first["spec"].items() if key != "data"} == {
        key: value for key, value in second["spec"].items() if key != "data"
    }
    assert second["spec"]["data"]["name"] == storage.versioned_name
