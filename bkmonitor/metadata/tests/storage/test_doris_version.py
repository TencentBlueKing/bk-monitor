"""Doris 在配置事务内分配版本，apply 只重复声明。"""

import json
from copy import deepcopy

import pytest
from django.db import transaction
from django.utils import timezone

from metadata import config, models
from metadata.models.data_link.data_link import DataLink

pytestmark = pytest.mark.django_db(transaction=True, databases="__all__", available_apps=["metadata"])


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
    assert storage.datalink_table_name == f"bkm_doris_{storage.pk}_v1"
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
    assert storage.datalink_table_name == f"bkm_doris_{storage.pk}_v1"
    assert models.StorageClusterRecord.objects.filter(table_id=rt.table_id).count() == 1
    payload = apply.call_args.args[0]
    binding = next(c for c in payload if c["kind"] == "DorisBinding")
    assert binding["spec"]["storage_config"]["table"] == storage.datalink_table_name
    assert binding["spec"]["storage_config"]["db"] == "mapleleaf_2"
    assert binding["spec"]["data"]["name"] == storage.datalink_table_name
    assert models.ResultTableConfig.objects.filter(table_id=rt.table_id).count() == 1


def test_failed_apply_keeps_saved_version_and_history(version_records, mocker):
    rt, ds, storage, link, _ = version_records
    with transaction.atomic(using=config.DATABASE_CONNECTION_NAME):
        storage.advance_table_version("tester")
    name = storage.datalink_table_name
    apply = mocker.patch.object(DataLink, "apply_data_link_with_retry", side_effect=RuntimeError("apply failed"))
    with pytest.raises(RuntimeError, match="apply failed"):
        link.apply_data_link(bk_biz_id=2, data_source=ds, table_id=rt.table_id)
    storage.refresh_from_db()
    assert storage.datalink_table_name == f"bkm_doris_{storage.pk}_v2"
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
    del value["doris_storage_config"]["tokenizers"]
    rt.modify(operator="tester", option={option.name: value})
    saved = models.ResultTableOption.objects.get(table_id=rt.table_id, name=option.name, bk_tenant_id=rt.bk_tenant_id)
    assert "tokenizers" not in saved.get_value()["doris_storage_config"]
    storage.refresh_from_db()
    assert storage.datalink_table_name == f"bkm_doris_{storage.pk}_v2"
    rt.modify(operator="tester", option={option.name: value})
    storage.refresh_from_db()
    assert storage.datalink_table_name == f"bkm_doris_{storage.pk}_v2"
    value["doris_storage_config"]["support_hour_partition"] = True
    rt.modify(operator="tester", option={option.name: value})
    storage.refresh_from_db()
    assert storage.datalink_table_name == f"bkm_doris_{storage.pk}_v3"
    assert [
        r.physical_tables["main"]
        for r in models.StorageClusterRecord.objects.filter(table_id=rt.table_id).order_by("id")
    ] == [f"mapleleaf_2.bkm_doris_{storage.pk}_v{v}" for v in (1, 2, 3)]


def test_historical_resources_are_retained_and_latest_version_selected(version_records, mocker, settings):
    rt, ds, storage, link, _ = version_records
    settings.DATA_LINK_COMPONENT_REUSE_STRATEGIES = [DataLink.BK_LOG]
    mocker.patch.object(DataLink, "apply_data_link_with_retry", return_value={})
    link.apply_data_link(bk_biz_id=2, data_source=ds, table_id=rt.table_id)
    old_name = storage.datalink_table_name
    with transaction.atomic(using=config.DATABASE_CONNECTION_NAME):
        storage.advance_table_version("tester")
    link.apply_data_link(bk_biz_id=2, data_source=ds, table_id=rt.table_id)
    assert models.ResultTableConfig.objects.filter(name=old_name, data_link_name=link.pk).exists()
    assert models.DorisStorageBindingConfig.objects.filter(name=old_name, data_link_name=link.pk).exists()
    assert models.ResultTableConfig.objects.filter(data_link_name=link.pk).count() == 2
    assert models.DorisStorageBindingConfig.objects.filter(data_link_name=link.pk).count() == 2
    assert storage.get_doris_binding_config().name == storage.datalink_table_name
    link.sync_metadata(table_id=rt.table_id, storage_cluster_id=99991, result_table_name=storage.datalink_table_name)
    assert models.BkBaseResultTable.objects.get(data_link_name=link.pk).bkbase_rt_name == storage.datalink_table_name


def test_nonstructural_change_does_not_rotate(version_records, mocker):
    rt, _, storage, _, option = version_records
    mocker.patch.object(models.ResultTable, "apply_datalink")
    mocker.patch("metadata.models.space.utils.get_space_by_table_id", return_value={})
    value = json.loads(option.value)
    value["doris_storage_config"].update(alias="新名称", description="说明", flush_timeout=90)
    rt.modify(operator="tester", option={option.name: value})
    storage.refresh_from_db()
    assert storage.datalink_table_name == f"bkm_doris_{storage.pk}_v1"


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
    assert models.DorisStorage.requires_new_table(
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
        models.DorisStorage.requires_new_table(
            {"fields": old_fields, "storage_config": {}}, {"fields": new_fields, "storage_config": {}}
        )
        is expected
    )


def test_unordered_fields():
    old = {"fields": [], "storage_config": {"field_config_group": {"search_zh": ["a", "b"]}}}
    new = deepcopy(old)
    new["storage_config"]["field_config_group"] = {"search_zh": ["b", "a"]}
    assert not models.DorisStorage.requires_new_table(old, new)


def test_legacy_table_keeps_name_until_first_costly_change(version_records, mocker):
    rt, ds, storage, link, option = version_records
    models.StorageClusterRecord.objects.filter(table_id=rt.table_id).delete()
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
    assert storage.datalink_table_name == f"bkm_doris_{storage.pk}_v1"
    assert storage.physical_tables == {"main": f"existing_db.{storage.datalink_table_name}"}


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
        with transaction.atomic(using=config.DATABASE_CONNECTION_NAME):
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
    assert second["spec"]["data"]["name"] == storage.datalink_table_name


@pytest.mark.parametrize("route_kind", ["origin", "virtual_option", "no_datasource"])
def test_route_tables_do_not_allocate_versions(version_records, route_kind):
    rt, _, storage, _, _ = version_records
    if route_kind == "origin":
        storage.origin_table_id = "entity.table"
        storage.save(update_fields=["origin_table_id"])
    elif route_kind == "virtual_option":
        models.ResultTableOption.objects.create(
            bk_tenant_id="system",
            table_id=rt.table_id,
            name=models.ResultTableOption.OPTION_IS_VIRTUAL_TABLE,
            value="true",
            value_type="bool",
            creator="tester",
        )
    else:
        models.DataSourceResultTable.objects.filter(bk_tenant_id="system", table_id=rt.table_id).delete()
    name = storage.datalink_table_name
    history_count = models.StorageClusterRecord.objects.filter(table_id=rt.table_id).count()
    with transaction.atomic(using=config.DATABASE_CONNECTION_NAME):
        storage.advance_table_version("tester")
    storage.refresh_from_db()
    assert storage.datalink_table_name == name
    assert models.StorageClusterRecord.objects.filter(table_id=rt.table_id).count() == history_count
    assert not models.BkBaseResultTable.objects.filter(monitor_table_id=rt.table_id).exists()


@pytest.mark.parametrize("is_sync_db", [False, True])
def test_route_storage_create_does_not_name_physical_table(version_records, is_sync_db):
    rt, _, storage, _, _ = version_records
    storage.delete()
    models.StorageClusterRecord.objects.filter(table_id=rt.table_id).delete()
    route = models.DorisStorage.create_table(
        table_id=rt.table_id,
        bk_tenant_id="system",
        storage_cluster_id=99991,
        source_type="log",
        is_sync_db=is_sync_db,
        create_storage_cluster_record=False,
    )
    assert route.datalink_table_name is None
    assert route.physical_tables == {}
    assert not route.bkbase_table_id
    assert not models.StorageClusterRecord.objects.filter(table_id=rt.table_id).exists()


@pytest.mark.parametrize("has_datasource", [False, True])
def test_third_party_query_table_allows_empty_physical_table(version_records, mocker, has_datasource):
    from metadata.models.space.space_table_id_redis import SpaceTableIDRedis

    rt, _, storage, _, option = version_records
    option.delete()  # 第三方表只有查询信息，不声明监控侧清洗和 Doris 写入配置。
    if not has_datasource:
        models.DataSourceResultTable.objects.filter(bk_tenant_id="system", table_id=rt.table_id).delete()
    models.StorageClusterRecord.objects.filter(table_id=rt.table_id).delete()
    storage.bkbase_table_id = "2_external_query_table"
    storage.physical_tables = {}
    storage.save()
    physical_lookup = mocker.patch.object(models.DorisStorage, "get_physical_table_name")
    storage.advance_table_version("tester")
    physical_lookup.assert_not_called()
    storage.refresh_from_db()
    assert storage.datalink_table_name is None
    assert storage.bkbase_table_id == "2_external_query_table"
    assert storage.physical_tables == {}
    details, _ = SpaceTableIDRedis()._compose_log_table_id_detail(bk_tenant_id="system", table_id_list=[rt.table_id])
    assert details[rt.table_id]["storage_type"] == "bk_sql"
    assert details[rt.table_id]["db"] == "2_external_query_table"
    assert "physical_tables" not in details[rt.table_id]
    assert not models.StorageClusterRecord.objects.filter(table_id=rt.table_id).exists()


def test_analysis_query_route_matches_external_bkbase_table(mocker):
    """BKOP __analysis__ 示例：外部 RT 存在，但没有监控写入链路或物理表快照。"""
    from metadata.models.space.space_table_id_redis import SpaceTableIDRedis

    table_id = "bklog_index_set_324_2_bklog_pure_v4_log_doris_for_unify_query.__analysis__"
    bkbase_table_id = "2_bklog_pure_v4_log_doris_for_unify_query"
    models.ClusterInfo.objects.create(
        bk_tenant_id="system",
        cluster_id=31,
        cluster_name="doris_log1",
        cluster_type="doris",
        domain_name="localhost",
        port=9030,
        is_default_cluster=False,
    )
    models.ResultTable.objects.create(
        bk_tenant_id="system",
        table_id=table_id,
        table_name_zh=table_id,
        bk_biz_id=2,
        is_custom_table=True,
        default_storage="doris",
        creator="system",
        is_enable=True,
    )
    storage = models.DorisStorage.objects.create(
        bk_tenant_id="system",
        table_id=table_id,
        storage_cluster_id=31,
        source_type="bkdata",
        origin_table_id=None,
        bkbase_table_id=bkbase_table_id,
        physical_tables={},
    )
    history = models.StorageClusterRecord.objects.create(
        bk_tenant_id="system",
        table_id=table_id,
        cluster_id=31,
        is_current=True,
        enable_time=timezone.now(),
        creator="system",
        physical_tables={},
        bkbase_table_id="",
    )
    models.ResultTableConfig.objects.create(
        bk_tenant_id="system",
        namespace="bklog",
        name="bklog_pure_v4_log_doris_for_unify_query",
        table_id="",
        data_link_name="",
        bk_biz_id=2,
        bkbase_table_id=bkbase_table_id,
    )
    lookup = mocker.patch.object(models.DorisStorage, "get_physical_table_name")
    storage.advance_table_version("tester")
    lookup.assert_not_called()
    details, _ = SpaceTableIDRedis()._compose_log_table_id_detail(bk_tenant_id="system", table_id_list=[table_id])
    route = details[table_id]
    assert route["storage_type"] == "bk_sql"
    assert route["db"] == bkbase_table_id
    assert "physical_tables" not in route
    assert route["storage_cluster_records"][0]["db"] == bkbase_table_id
    storage.refresh_from_db()
    history.refresh_from_db()
    assert storage.datalink_table_name is None and storage.physical_tables == {}
    assert history.physical_tables == {} and history.bkbase_table_id == ""
    assert not models.BkBaseResultTable.objects.filter(monitor_table_id=table_id).exists()


def test_apply_reads_version_after_result_table_lock(version_records, mocker):
    rt, ds, storage, link, _ = version_records
    models.DorisStorage.objects.filter(pk=storage.pk).update(physical_tables={})
    select_for_update = models.ResultTable.objects.select_for_update

    def concurrent_version_commit(*args, **kwargs):
        # 模拟任务等待 ResultTable 锁期间，另一个修改事务已提交 v1。
        models.DorisStorage.objects.filter(pk=storage.pk).update(physical_tables=storage.physical_tables)
        return select_for_update(*args, **kwargs)

    mocker.patch.object(models.ResultTable.objects, "select_for_update", side_effect=concurrent_version_commit)
    apply = mocker.patch.object(DataLink, "apply_data_link_with_retry", return_value={})
    link.apply_data_link(bk_biz_id=2, data_source=ds, table_id=rt.table_id)
    binding = next(c for c in apply.call_args.args[0] if c["kind"] == "DorisBinding")
    assert binding["metadata"]["name"] == storage.datalink_table_name


@pytest.mark.parametrize("entry", ["model", "task", "direct"])
@pytest.mark.parametrize("default_storage", ["doris", "elasticsearch"])
def test_dual_write_to_es_only_still_updates_pipeline(version_records, mocker, entry, default_storage):
    from metadata.task.datalink import apply_log_datalink

    rt, ds, storage, link, option = version_records
    if link.data_link_strategy != DataLink.BK_LOG:
        pytest.skip("双写只适用于日志链路")
    models.ClusterInfo.objects.create(
        bk_tenant_id="system",
        cluster_id=99992,
        cluster_name="compat_es",
        cluster_type="elasticsearch",
        domain_name="localhost",
        port=9200,
        is_default_cluster=False,
    )
    models.ESStorage.objects.create(bk_tenant_id="system", table_id=rt.table_id, storage_cluster_id=99992)
    rt.default_storage = default_storage
    rt.save(update_fields=["default_storage"])
    models.ResultTableOption.objects.create(
        bk_tenant_id="system",
        table_id=rt.table_id,
        name=models.ResultTableOption.OPTION_ENABLE_V4_LOG_DATA_LINK,
        value="true",
        value_type="bool",
        creator="tester",
    )
    mocker.patch.object(models.ResultTable, "get_target_bk_biz_id", return_value=2)
    mocker.patch.object(models.DataSource, "delete_consul_config")
    apply = mocker.patch.object(DataLink, "apply_data_link_with_retry", return_value={})
    option.value_type = models.ResultTableOption.TYPE_DICT
    value = json.loads(option.value)
    value["es_storage_config"] = {"unique_field_list": []}
    option.value = json.dumps(value)
    option.save()
    # 先建立双写链路及共享 RT，再保留原 DorisStorage 和 Binding。
    link.apply_data_link(bk_biz_id=2, data_source=ds, table_id=rt.table_id)
    shared_name = storage.datalink_table_name
    bus = models.DataBusConfig.objects.get(data_link_name=link.pk)
    bus.consumer_group = "keep_existing_group"
    bus.save(update_fields=["consumer_group"])
    name = storage.datalink_table_name
    history = list(models.StorageClusterRecord.objects.filter(table_id=rt.table_id).values())
    value.pop("doris_storage_config")

    for iteration in range(2):
        value["es_storage_config"]["json_field_list"] = [] if iteration == 0 else ["body"]
        value["clean_rules"][0]["output_id"] = "log" if iteration == 0 else "body"
        option.value = json.dumps(value)
        option.save()
        if entry == "model":
            rt.apply_datalink(delay=False)
        elif entry == "task":
            apply_log_datalink("system", rt.table_id)
        else:
            link.apply_data_link(bk_biz_id=2, data_source=ds, table_id=rt.table_id)
        payload = apply.call_args.args[0]
        bus_config = next(c for c in payload if c["kind"] == "Databus")
        assert [sink["kind"] for sink in bus_config["spec"]["sinks"]] == ["ElasticSearchBinding"]
        assert bus_config["spec"]["consumerGroup"] == "keep_existing_group"
        es = next(c for c in payload if c["kind"] == "ElasticSearchBinding")
        assert es["spec"]["json_field_list"] == value["es_storage_config"]["json_field_list"]
        assert es["spec"]["data"]["name"] == shared_name
        assert not any(c["kind"] == "DorisBinding" for c in payload)
        assert value["clean_rules"][0]["output_id"] in json.dumps(bus_config["spec"]["transforms"])
    assert apply.call_count == 3
    storage.refresh_from_db()
    assert storage.datalink_table_name == name
    assert list(models.StorageClusterRecord.objects.filter(table_id=rt.table_id).values()) == history
    assert models.DorisStorageBindingConfig.objects.filter(name=shared_name).exists()


@pytest.mark.parametrize(
    "strategy", [DataLink.CUSTOM_FORMAT_VM, DataLink.CUSTOM_FORMAT_ES, DataLink.BK_STANDARD_V2_TIME_SERIES]
)
def test_other_pipeline_components_ignore_historical_doris_version(version_records, strategy):
    from metadata.models.data_link.component_reuse import ExistingComponentContext

    rt, _, _, link, _ = version_records
    link.data_link_strategy = strategy
    link.save(update_fields=["data_link_strategy"])
    current = models.ResultTableConfig.objects.create(
        bk_tenant_id="system",
        namespace=link.namespace,
        data_link_name=link.pk,
        bk_biz_id=2,
        table_id=rt.table_id,
        name="other_storage_rt",
        bkbase_table_id="2_other_storage_rt",
    )
    context = ExistingComponentContext.from_datalink(link)
    assert context.claim(models.ResultTableConfig, lambda component: True).pk == current.pk
    assert current in link._get_absent_components_to_delete([], force_delete=True)
    models.ClusterInfo.objects.create(
        bk_tenant_id="system",
        cluster_id=99992,
        cluster_name="other_storage",
        cluster_type=models.ClusterInfo.TYPE_ES
        if strategy == DataLink.CUSTOM_FORMAT_ES
        else models.ClusterInfo.TYPE_VM,
        domain_name="localhost",
        port=8428,
        is_default_cluster=False,
    )
    link.sync_metadata(table_id=rt.table_id, storage_cluster_id=99992)
    assert models.BkBaseResultTable.objects.get(data_link_name=link.pk).bkbase_rt_name == current.name


@pytest.mark.parametrize("failure_stage", ["merge", "apply"])
def test_remote_failure_keeps_committed_component_configuration(version_records, mocker, failure_stage):
    from django.db import connections

    rt, ds, storage, link, option = version_records
    target_name = storage.datalink_table_name
    remote = mocker.patch.object(DataLink, "apply_data_link_with_retry")

    def fail(*args, **kwargs):
        assert not connections[config.DATABASE_CONNECTION_NAME].in_atomic_block
        local_rt = models.ResultTableConfig.objects.get(data_link_name=link.pk)
        local_binding = models.DorisStorageBindingConfig.objects.get(data_link_name=link.pk)
        local_bus = models.DataBusConfig.objects.get(data_link_name=link.pk)
        assert local_rt.name == target_name
        assert local_binding.name == target_name
        assert local_binding.bkbase_result_table_name == target_name
        assert local_bus.sink_names == [f"DorisBinding:{target_name}"]
        raise RuntimeError("remote failed after commit")

    if failure_stage == "merge":
        merge = mocker.patch.object(DataLink, "merge_existing_component_configs", side_effect=fail)
    else:
        remote.side_effect = fail
    with pytest.raises(RuntimeError, match="remote failed after commit"):
        link.apply_data_link(bk_biz_id=2, data_source=ds, table_id=rt.table_id)
    assert models.ResultTableConfig.objects.get(data_link_name=link.pk).name == target_name
    assert models.DorisStorageBindingConfig.objects.get(data_link_name=link.pk).name == target_name
    bus_pk = models.DataBusConfig.objects.get(data_link_name=link.pk).pk
    if failure_stage == "merge":
        merge.side_effect = lambda configs: configs
    remote.side_effect = None
    remote.return_value = {}
    link.apply_data_link(bk_biz_id=2, data_source=ds, table_id=rt.table_id)
    assert models.DataBusConfig.objects.get(data_link_name=link.pk).pk == bus_pk
    assert models.StorageClusterRecord.objects.filter(table_id=rt.table_id).count() == 1


def test_outer_transaction_commits_latest_configuration_before_failed_apply(version_records, mocker):
    from django.db import connections

    rt, ds, storage, link, option = version_records
    apply = mocker.patch.object(DataLink, "apply_data_link_with_retry", side_effect=RuntimeError("remote failed"))
    with pytest.raises(RuntimeError, match="remote failed"):
        with transaction.atomic(using=config.DATABASE_CONNECTION_NAME):
            link.apply_data_link(bk_biz_id=2, data_source=ds, table_id=rt.table_id)
            apply.assert_not_called()
            # 待执行任务不捕获旧配置；提交之前又修改目标时，应声明最终目标。
            value = json.loads(option.value)
            value["doris_storage_config"]["tokenizers"] = {"log": ","}
            option.value = json.dumps(value)
            option.save(update_fields=["value"])
            storage.advance_table_version("tester")
    assert not connections[config.DATABASE_CONNECTION_NAME].in_atomic_block
    assert models.DorisStorage.objects.get(pk=storage.pk).physical_tables == storage.physical_tables
    assert json.loads(models.ResultTableOption.objects.get(pk=option.pk).value) == value
    payload = apply.call_args.args[0]
    binding = next(item for item in payload if item["kind"] == "DorisBinding")
    assert binding["metadata"]["name"] == storage.datalink_table_name
    assert binding["spec"]["storage_config"]["tokenizers"] == {"log": ","}
    assert models.DorisStorageBindingConfig.objects.get(data_link_name=link.pk).name == storage.datalink_table_name
    assert models.StorageClusterRecord.objects.filter(table_id=rt.table_id).count() == 2


def test_result_table_modify_commits_before_log_apply_failure(version_records, mocker):
    rt, ds, storage, link, option = version_records
    if link.data_link_strategy != DataLink.BK_LOG:
        pytest.skip("自定义格式由提交后的任务执行，下发事务用例已覆盖")
    mocker.patch.object(models.ResultTable, "get_target_bk_biz_id", return_value=2)
    mocker.patch("metadata.models.space.utils.get_space_by_table_id", return_value={})
    apply = mocker.patch.object(DataLink, "apply_data_link_with_retry", return_value={})
    link.apply_data_link(bk_biz_id=2, data_source=ds, table_id=rt.table_id)
    old_name = storage.datalink_table_name
    value = json.loads(option.value)
    value["doris_storage_config"]["tokenizers"] = {}
    apply.side_effect = RuntimeError("apply failed")
    with pytest.raises(RuntimeError, match="apply failed"):
        rt.modify(
            operator="tester",
            option={
                option.name: value,
                models.ResultTableOption.OPTION_ENABLE_V4_LOG_DATA_LINK: True,
            },
        )
    storage.refresh_from_db()
    option = models.ResultTableOption.objects.get(bk_tenant_id="system", table_id=rt.table_id, name=option.name)
    assert option.get_value()["doris_storage_config"]["tokenizers"] == {}
    assert storage.datalink_table_name != old_name
    assert models.StorageClusterRecord.objects.filter(table_id=rt.table_id).count() == 2
    for name in (old_name, storage.datalink_table_name):
        assert models.ResultTableConfig.objects.filter(data_link_name=link.pk, name=name).exists()
        assert models.DorisStorageBindingConfig.objects.filter(data_link_name=link.pk, name=name).exists()
    assert models.DataBusConfig.objects.get(data_link_name=link.pk).sink_names == [
        f"DorisBinding:{storage.datalink_table_name}"
    ]


@pytest.mark.parametrize("version_records", [DataLink.BK_LOG], indirect=True)
@pytest.mark.parametrize("rollback", [False, True], ids=["apply_failure", "outer_rollback"])
def test_es_only_log_apply_follows_outer_commit(version_records, mocker, rollback):
    rt, _, storage, _, option = version_records
    storage.delete()
    models.StorageClusterRecord.objects.filter(table_id=rt.table_id).delete()
    rt.default_storage = models.ClusterInfo.TYPE_ES
    rt.save(update_fields=["default_storage"])
    models.ClusterInfo.objects.create(
        bk_tenant_id="system",
        cluster_id=99992,
        cluster_name="log_es",
        cluster_type=models.ClusterInfo.TYPE_ES,
        domain_name="localhost",
        port=9200,
        is_default_cluster=False,
    )
    models.ESStorage.objects.create(table_id=rt.table_id, bk_tenant_id="system", storage_cluster_id=99992)
    original = json.loads(option.value)
    original.pop("doris_storage_config")
    original["es_storage_config"] = {"unique_field_list": []}
    option.value = json.dumps(original)
    option.save(update_fields=["value"])
    snapshot = mocker.spy(models.DorisStorage, "_table_config")
    saved_write_config = mocker.spy(models.DorisStorage, "_saved_write_config")
    updated = dict(original, es_storage_config={"unique_field_list": ["host"]})
    mocker.patch("metadata.models.space.utils.get_space_by_table_id", return_value={})
    mocker.patch.object(models.ResultTable, "get_target_bk_biz_id", return_value=2)
    apply = mocker.patch("metadata.task.datalink.apply_log_datalink", side_effect=RuntimeError("apply failed"))
    with pytest.raises(RuntimeError, match="rollback" if rollback else "apply failed"):
        with transaction.atomic(using=config.DATABASE_CONNECTION_NAME):
            rt.modify(
                operator="tester",
                option={option.name: updated, models.ResultTableOption.OPTION_ENABLE_V4_LOG_DATA_LINK: True},
            )
            apply.assert_not_called()
            if rollback:
                raise RuntimeError("rollback")
    saved = models.ResultTableOption.objects.get(bk_tenant_id="system", table_id=rt.table_id, name=option.name)
    snapshot.assert_not_called()
    saved_write_config.assert_not_called()
    if rollback:
        apply.assert_not_called()
        assert json.loads(saved.value) == original
    else:
        apply.assert_called_once_with(bk_tenant_id="system", table_id=rt.table_id)
        assert saved.get_value() == updated


@pytest.mark.parametrize("version_records", [DataLink.BK_LOG], indirect=True)
@pytest.mark.parametrize("writes_doris", [False, True], ids=["es_only_with_doris_history", "dual_write"])
def test_es_default_field_only_update(version_records, mocker, writes_doris):
    rt, _, storage, _, option = version_records
    rt.default_storage = models.ClusterInfo.TYPE_ES
    rt.schema_type = rt.SCHEMA_TYPE_FREE
    rt.is_enable = False
    rt.save()
    value = json.loads(option.value)
    value["es_storage_config"] = {"unique_field_list": []}
    if not writes_doris:
        del value["doris_storage_config"]
    option.value = json.dumps(value)
    option.save(update_fields=["value"])
    mocker.patch.object(models.ResultTable, "_get_and_validate_default_cluster_storage")
    mocker.patch("metadata.models.space.utils.get_space_by_table_id", return_value={})
    snapshot = mocker.spy(models.DorisStorage, "_table_config")
    rt.modify(operator="tester", field_list=[])
    storage.refresh_from_db()
    version = 2 if writes_doris else 1
    assert storage.datalink_table_name == f"bkm_doris_{storage.pk}_v{version}"
    if not writes_doris:
        snapshot.assert_not_called()


def test_vm_field_update_skips_doris_configuration(version_records, mocker):
    rt, _, _, _, _ = version_records
    rt.default_storage = models.ClusterInfo.TYPE_VM
    rt.schema_type = rt.SCHEMA_TYPE_FREE
    rt.is_enable = False
    rt.save()
    mocker.patch("metadata.models.space.utils.get_space_by_table_id", return_value={})
    prepare = mocker.spy(models.DorisStorage, "prepare_table_update")
    rt.modify(operator="tester", field_list=[], option={})
    prepare.assert_not_called()
