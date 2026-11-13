import copy
import datetime
import json

import pytest
from django.utils import timezone

from metadata import models
from metadata.models.data_link.log_clustering import (
    PATTERN_FIELDS,
    PATTERN_KEYS,
    RESULT_FIELDS,
    prepare_clustering_stores,
)
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis
from metadata.resources.log_clustering import apply_log_clustering_sink_only
from metadata.tests.data_link.test_log_clustering_sink import (
    BINDING,
    CLUSTERED_TARGET,
    LOG_TABLE_ID,
    PATTERN_TARGET,
    RAW_SINK,
    compose,
    create_clustering_sink,
    create_log_datalink,
)

pytestmark = pytest.mark.django_db(databases="__all__")


@pytest.mark.parametrize("timestamp_is_key", [False, True])
def test_log_source_and_append_table_match_es_document_keys(log_datalink, timestamp_is_key):
    option = models.ResultTableOption.objects.get(
        table_id=LOG_TABLE_ID, name=models.ResultTableOption.OPTION_V4_LOG_DATA_LINK
    )
    config = json.loads(option.value)
    keys = ["log", "dtEventTimeStamp"] if timestamp_is_key else ["log"]
    config["es_storage_config"]["unique_field_list"] = keys
    option.value = json.dumps(config)
    option.save(update_fields=["value"])
    for name, kind in [("log", "string"), ("dtEventTimeStamp", "timestamp")]:
        models.ResultTableField.objects.create(
            table_id=LOG_TABLE_ID,
            bk_tenant_id="system",
            field_name=name,
            field_type=kind,
            tag="dimension",
            is_config_by_user=True,
        )

    configs, _ = compose(*log_datalink)
    source = next(c for c in configs if c["kind"] == "ResultTable")
    assert source["spec"]["dataType"] == "log"
    assert ("dtEventTimeStamp" in {f["field_name"] for f in source["spec"]["fields"]}) == timestamp_is_key

    rt = models.ResultTableConfig.objects.get(table_id=LOG_TABLE_ID)
    sink = create_clustering_sink(result={"mode": "append"})
    configs, _ = compose(*log_datalink)
    rt.refresh_from_db()
    assert rt.data_type == "log"
    sink.refresh_from_db()
    for name in (source["metadata"]["name"], sink.result["result_table"]["name"]):
        result = next(c for c in configs if c["kind"] == "ResultTable" and c["metadata"]["name"] == name)
        binding = next(c for c in configs if c["kind"] == "ElasticSearchBinding" and c["spec"]["data"]["name"] == name)
        fields = {f["field_name"]: f["field_type"] for f in result["spec"]["fields"]}
        assert result["spec"]["dataType"] == "log"
        assert binding["spec"]["unique_field_list"] == keys
        assert set(keys) <= fields.keys()
        assert fields.get("dtEventTimeStamp") == ("timestamp" if timestamp_is_key else None)

    # 解绑、再次下发及重开复用同一源表；只有 Databus 的写入目标随 attached 变化。
    for attached in (False, False, True):
        sink.attached = attached
        sink.save(update_fields=["attached"])
        configs, _ = compose(*log_datalink)
        rt.refresh_from_db()
        result = next(c for c in configs if c["kind"] == "ResultTable" and c["metadata"]["name"] == rt.name)
        assert rt.data_type == result["spec"]["dataType"] == "log"
        assert ("dtEventTimeStamp" in {f["field_name"] for f in result["spec"]["fields"]}) == timestamp_is_key
        databus = next(c for c in configs if c["kind"] == "Databus")
        assert databus["spec"]["sinks"][0]["kind"] == ("LogClusteringSink" if attached else "ElasticSearchBinding")


@pytest.mark.parametrize("result", [{"mode": "update_original"}, {"mode": "append"}])
def test_first_full_apply_composes_sink_with_prepared_pattern_store(log_datalink, result):
    """首次开启走完整下发时，Sink 只有日志平台声明的表，组装须使用本轮准备的引用。"""
    sink = create_clustering_sink(result=result)

    configs, _ = compose(*log_datalink)

    sink.refresh_from_db()
    assert sink.pattern_store["result_table"]["name"] == f"bklog_{BINDING['index_id']}_pattern"
    clustering = next(c for c in configs if c["kind"] == "LogClusteringSink")["spec"]["clustering"]
    assert clustering["pattern_store"] == bkbase_refs(sink.pattern_store)
    assert next(c for c in configs if c["kind"] == "Databus")["spec"]["sinks"][0]["kind"] == "LogClusteringSink"


def test_pattern_table_must_be_declared(log_datalink):
    sink = create_clustering_sink(pattern_store={})
    with pytest.raises(ValueError, match="pattern storage is not declared"):
        prepare_clustering_stores(sink)


def test_existing_log_source_corrects_metric_without_clustering(log_datalink):
    compose(*log_datalink)
    rt = models.ResultTableConfig.objects.get(table_id=LOG_TABLE_ID)
    rt.data_type = "metric"
    rt.save(update_fields=["data_type"])
    configs, _ = compose(*log_datalink)
    rt.refresh_from_db()
    assert rt.data_type == "log"
    assert next(c for c in configs if c["kind"] == "ResultTable")["spec"]["dataType"] == "log"


def test_append_registers_original_fields_and_separate_targets(log_datalink, mocker):
    models.ResultTableField.objects.create(
        bk_tenant_id="system",
        table_id=LOG_TABLE_ID,
        field_name="message",
        field_type="string",
        tag="dimension",
        is_config_by_user=True,
    )
    models.ResultTableFieldOption.create_option(
        LOG_TABLE_ID, "message", "es_type", "text", creator="system", bk_tenant_id="system"
    )
    sink = create_clustering_sink(result={"mode": "append"})
    configs = prepare_clustering_stores(sink)
    assert prepare_clustering_stores(sink) == configs
    rt, binding = configs[2:]
    assert rt["metadata"]["name"] == f"bklog_{BINDING['index_id']}_clustered"
    fields = {f["field_name"]: f["field_type"] for f in rt["spec"]["fields"]}
    assert fields["message"] == "string"
    assert all(fields[k] == v for k, v in RESULT_FIELDS.items())
    assert sink.result["result_table"] != sink.pattern_store["result_table"]
    assert binding["spec"]["data"] == sink.result["result_table"]
    rt_model = models.ResultTableConfig.objects.get(name=rt["metadata"]["name"])
    storage = models.ESStorage.objects.get(table_id=rt_model.table_id)
    assert storage.need_create_index is True
    assert storage.index_name == binding["metadata"]["annotations"]["physical_table_name"]
    assert binding["spec"]["write_alias"] == {
        "TimeBased": {"format": f"write_%Y%m%d_{storage.index_name}", "timezone": 0}
    }
    assert storage.index_body["mappings"]["properties"]["message"]["type"] == "text"
    assert storage.index_body["mappings"]["properties"]["__log_signature"]["type"] == "keyword"
    assert storage.index_body["mappings"]["properties"]["__log_cluster_publish_revision"]["type"] == "long"
    assert sink.compose_config(RAW_SINK)["spec"]["clustering"]["result"] == bkbase_refs(sink.result)
    # 表名由日志平台声明，物理名与原日志表一样由 table_id 推导。
    assert rt_model.table_id == CLUSTERED_TARGET["table_id"]
    assert storage.index_name == CLUSTERED_TARGET["table_id"].replace(".", "_")
    assert pattern_storage(sink).index_name == PATTERN_TARGET["table_id"].replace(".", "_")
    assert set(fields) == {"message", "__log_signature", "__log_cluster_publish_revision"}
    # 旧表重新生成时补齐系统字段，保留原日志中与旧系统字段同名的业务列。
    models.ResultTableField.objects.filter(table_id=rt_model.table_id, field_name__in=RESULT_FIELDS).delete()
    models.ResultTableField.objects.create(
        table_id=LOG_TABLE_ID,
        bk_tenant_id="system",
        field_name="log_signature",
        field_type="int",
        tag="dimension",
        is_config_by_user=True,
    )
    updated = prepare_clustering_stores(sink)[2]
    declared = {f["field_name"]: f["field_type"] for f in updated["spec"]["fields"]}
    assert declared["log_signature"] == "int"
    assert declared["__log_signature"] == "string"
    assert models.ResultTableField.objects.filter(table_id=rt_model.table_id, field_name__in=RESULT_FIELDS).count() == 2
    old_result = copy.deepcopy(sink.result)
    old_pattern = copy.deepcopy(sink.pattern_store)
    old_config = sink.compose_config(RAW_SINK)
    switch_source(710102, timezone.now())
    declare_cluster(sink, 710102)
    prepare_clustering_stores(sink)
    assert sink.result["result_table"] == old_result["result_table"]
    assert sink.result["es_binding"] != old_result["es_binding"]
    assert sink.pattern_store["es_binding"] != old_pattern["es_binding"]
    merged = models.DataLink.merge_component_config(old_config, sink.compose_config(RAW_SINK))
    assert merged["spec"]["clustering"]["result"] == bkbase_refs(sink.result)


def test_declared_cluster_switch_leaves_routes_to_caller(log_datalink, mocker):
    sink = create_clustering_sink(result={"mode": "append"})
    prepare_clustering_stores(sink)
    routes = []
    for suffix, ref in (("pattern", sink.pattern_store), ("clustered", sink.result)):
        table = models.ResultTableConfig.objects.get(name=ref["result_table"]["name"])
        storage = models.ESStorage.objects.get(table_id=table.table_id)
        route = f"bklog_index_set_test_{suffix}.__default__"
        routes.append(route)
        models.ResultTable.objects.create(
            table_id=route, bk_tenant_id="system", default_storage="elasticsearch", is_custom_table=True
        )
        models.ESStorage.objects.create(
            table_id=route,
            bk_tenant_id="system",
            origin_table_id=table.table_id,
            source_type="es",
            index_set=storage.index_set,
            storage_cluster_id=storage.storage_cluster_id,
        )
    publish = mocker.patch.object(SpaceTableIDRedis, "push_table_id_detail")
    switch_source(710102, timezone.now())
    declare_cluster(sink, 710102)
    prepare_clustering_stores(sink)

    # metadata 只切换实体表存储，不改写也不发布日志平台注册的路由。
    publish.assert_not_called()
    assert set(models.ESStorage.objects.filter(table_id__in=routes).values_list("storage_cluster_id", flat=True)) == {
        710101
    }
    # 日志平台按新集群重新注册后，路由带上实体表的全部历史分段。
    models.ESStorage.objects.filter(table_id__in=routes).update(storage_cluster_id=710102)
    detail, _ = SpaceTableIDRedis()._compose_log_table_id_detail(bk_tenant_id="system", table_id_list=routes)
    assert len(detail) == 2
    for route, suffix in zip(routes, ("pattern", "clustered")):
        assert detail[route]["storage_id"] == 710102
        assert len(detail[route]["storage_cluster_records"]) == 2
        assert {r["db"] for r in detail[route]["storage_cluster_records"]} == {
            f"2_bklog_{BINDING['index_id']}_{suffix}"
        }


def test_append_index_preparation_failure_retries_before_apply(log_datalink, mocker):
    datalink, _ = log_datalink
    sink = create_clustering_sink(result={"mode": "append"})
    prepare_index = mocker.patch.object(
        models.ESStorage, "update_index_and_aliases", side_effect=[True, False, True, True]
    )
    apply = mocker.patch.object(datalink, "apply_data_link_with_retry")
    mocker.patch.object(datalink, "get_existing_component_config", return_value=None)
    with pytest.raises(RuntimeError, match="索引或写别名未准备完成"):
        apply_log_clustering_sink_only(datalink, sink, RAW_SINK)
    apply.assert_not_called()
    apply_log_clustering_sink_only(datalink, sink, RAW_SINK)
    assert prepare_index.call_count == 4
    assert prepare_index.call_args.kwargs["strict"] is True
    configs = apply.call_args.args[0]
    assert len(configs) == 5
    assert configs[-1]["spec"]["clustering"]["result"] == bkbase_refs(sink.result)


@pytest.fixture
def log_datalink(mocker):
    mocker.patch.object(models.ESStorage, "update_index_and_aliases", return_value=True)
    mocker.patch("bkmonitor.utils.tenant.get_tenant_default_biz_id", return_value=2)
    return create_log_datalink()


def bkbase_refs(store):
    return {key: value for key, value in store.items() if key not in ("table_id", "cluster_id")}


def declare_cluster(sink, cluster_id):
    """模拟日志平台切存储后按索引集当前集群重新声明聚类表。"""
    sink.pattern_store = {**sink.pattern_store, "cluster_id": cluster_id}
    if sink.result.get("mode") == "append":
        sink.result = {**sink.result, "cluster_id": cluster_id}


def pattern_storage(sink):
    ref = sink.pattern_store["result_table"]
    rt = models.ResultTableConfig.objects.get(
        bk_tenant_id=sink.bk_tenant_id, namespace=ref["namespace"], name=ref["name"]
    )
    return models.ESStorage.objects.get(bk_tenant_id=sink.bk_tenant_id, table_id=rt.table_id)


def switch_source(cluster_id, when):
    models.ClusterInfo.objects.get_or_create(
        cluster_id=cluster_id,
        bk_tenant_id="system",
        defaults={
            "cluster_name": f"pattern-test-{cluster_id}",
            "cluster_type": "elasticsearch",
            "domain_name": "example.com",
            "port": 9200,
            "is_default_cluster": False,
        },
    )
    models.ESStorage.objects.filter(table_id=LOG_TABLE_ID, bk_tenant_id="system").update(storage_cluster_id=cluster_id)
    models.StorageClusterRecord.switch_current_cluster(
        table_id=LOG_TABLE_ID,
        bk_tenant_id="system",
        target_cluster_id=cluster_id,
        target_storage_type="elasticsearch",
        switch_time=when,
        creator="system",
    )


def test_register_managed_pattern_once_per_index(log_datalink):
    settings = {"index.routing.allocation.include.rack": "test-rack", "number_of_shards": 3}
    models.ESStorage.objects.filter(table_id=LOG_TABLE_ID).update(index_settings=json.dumps(settings), retention=7)
    sink = create_clustering_sink()
    first = prepare_clustering_stores(sink)
    assert prepare_clustering_stores(sink) == first
    sink.binding = {**sink.binding, "generation": 2}
    assert prepare_clustering_stores(sink) == first
    rt, binding = first
    assert rt["spec"]["dataType"] == "log"
    assert rt["metadata"]["name"] == f"bklog_{BINDING['index_id']}_pattern"
    expected_index = PATTERN_TARGET["table_id"].replace(".", "_")
    assert binding["metadata"]["annotations"]["physical_table_name"] == expected_index
    assert {field["field_name"]: field["field_type"] for field in rt["spec"]["fields"]} == PATTERN_FIELDS
    assert binding["spec"]["data"] == sink.pattern_store["result_table"]
    assert binding["spec"]["write_alias"]["TimeBased"]["format"] == f"write_%Y%m%d_{expected_index}"
    assert binding["spec"]["doc_value_fields"] == PATTERN_KEYS
    assert binding["spec"]["unique_field_list"] == PATTERN_KEYS
    storage = pattern_storage(sink)
    assert storage.index_set == binding["metadata"]["annotations"]["physical_table_name"]
    assert storage.storage_cluster_id == models.ESStorage.objects.get(table_id=LOG_TABLE_ID).storage_cluster_id
    assert storage.need_create_index is True
    assert storage.index_body["settings"] == settings
    assert storage.retention == 7
    assert storage.source_type == "log"
    assert storage.index_name == expected_index
    assert storage.index_body["mappings"]["properties"]["signature"]["type"] == "keyword"
    assert storage.index_body["mappings"]["properties"]["dtEventTimeStamp"] == {
        "type": "date",
        "format": "epoch_millis",
    }
    models.ESStorage.objects.filter(pk=storage.pk).update(need_create_index=False)
    assert prepare_clustering_stores(sink) == first
    storage.refresh_from_db()
    assert storage.need_create_index is True
    assert models.StorageClusterRecord.objects.filter(table_id=storage.table_id).count() == 1
    assert not models.DataSourceResultTable.objects.filter(table_id=storage.table_id).exists()
    other = create_clustering_sink(
        name="other-pattern",
        data_link_name="other-link",
        binding={**BINDING, "index_id": "other"},
        pattern_store={**PATTERN_TARGET, "table_id": "2_bklog.other_pattern"},
    )
    prepare_clustering_stores(other)
    assert pattern_storage(other).table_id != storage.table_id


@pytest.mark.parametrize("reapply", [False, True], ids=["register", "reapply"])
def test_pattern_daily_alias_with_hourly_source(log_datalink, reapply):
    hourly = "%Y%m%d%H"
    source = models.ESStorage.objects.get(table_id=LOG_TABLE_ID)
    source.date_format = hourly
    source.save(update_fields=["date_format"])
    sink = create_clustering_sink(result={"mode": "append"})
    if reapply:
        prepare_clustering_stores(sink)
        # 模拟此前沿用了源表小时格式的 Pattern 登记。
        models.ESStorage.objects.filter(pk=pattern_storage(sink).pk).update(date_format=hourly)

    _, binding, clustered_rt, _ = prepare_clustering_stores(sink)

    pattern = pattern_storage(sink)
    assert pattern.date_format == "%Y%m%d"
    at = datetime.datetime(2026, 1, 2, 13)
    alias = f"write_{at.strftime(pattern.date_format)}_{pattern.index_name}"
    assert alias == at.strftime(binding["spec"]["write_alias"]["TimeBased"]["format"])
    source.refresh_from_db()
    assert source.date_format == hourly
    table = models.ResultTableConfig.objects.get(name=clustered_rt["metadata"]["name"])
    assert models.ESStorage.objects.get(table_id=table.table_id).date_format == hourly


def test_switch_storage_keeps_fixed_name_and_all_history(log_datalink):
    sink = create_clustering_sink()
    first = prepare_clustering_stores(sink)
    storage = pattern_storage(sink)
    original_cluster = storage.storage_cluster_id
    second_time = timezone.now()
    switch_source(710102, second_time)
    declare_cluster(sink, 710102)
    second = prepare_clustering_stores(sink)
    assert second[0] == first[0]
    assert second[1]["metadata"]["annotations"] == first[1]["metadata"]["annotations"]
    assert second[1]["metadata"]["name"] != first[1]["metadata"]["name"]
    assert second[1]["spec"]["storage"]["name"] == "pattern-test-710102"
    prepare_clustering_stores(sink)
    third_time = second_time + datetime.timedelta(seconds=30)
    switch_source(original_cluster, third_time)
    declare_cluster(sink, original_cluster)
    prepare_clustering_stores(sink)
    records = list(models.StorageClusterRecord.objects.filter(table_id=storage.table_id).order_by("enable_time"))
    assert [r.cluster_id for r in records] == [original_cluster, 710102, original_cluster]
    assert [r.is_current for r in records] == [False, False, True]
    assert all(not r.is_deleted for r in records)
    assert records[1].enable_time == second_time


@pytest.mark.parametrize("multi_tenant, expected_biz", [(False, 91), (True, 17)])
def test_pattern_physical_name_follows_declared_table(log_datalink, settings, multi_tenant, expected_biz):
    settings.ENABLE_MULTI_TENANT_MODE = multi_tenant
    settings.DEFAULT_BKDATA_BIZ_ID = 91
    sink = create_clustering_sink(
        bk_biz_id=17,
        binding={**BINDING, "index_id": "42"},
        pattern_store={"table_id": "17_bklog.42_pattern", "cluster_id": 710101},
    )
    rt, binding = prepare_clustering_stores(sink)
    assert rt["metadata"]["name"] == "bklog_42_pattern"
    assert rt["spec"]["bizId"] == expected_biz
    # 物理名通过注解指定，与 BKBase 侧业务 ID 无关。
    assert binding["metadata"]["annotations"]["physical_table_name"] == "17_bklog_42_pattern"
    assert pattern_storage(sink).table_id == "17_bklog.42_pattern"
    assert pattern_storage(sink).index_set == "17_bklog_42_pattern"


def test_failed_apply_retries_same_pattern_resources(log_datalink, mocker):
    datalink, _ = log_datalink
    compose(*log_datalink)
    sink = create_clustering_sink()
    mocker.patch.object(datalink, "get_existing_component_config", return_value=None)
    apply = mocker.patch.object(
        datalink, "apply_data_link_with_retry", side_effect=[RuntimeError("apply failed"), None]
    )
    with pytest.raises(RuntimeError, match="apply failed"):
        apply_log_clustering_sink_only(datalink, sink, RAW_SINK)
    payload = copy.deepcopy(apply.call_args.args[0])
    apply_log_clustering_sink_only(datalink, sink, RAW_SINK)
    assert apply.call_args.args[0] == payload
    assert [c["kind"] for c in payload] == ["ResultTable", "ResultTable", "ElasticSearchBinding", "LogClusteringSink"]
    assert payload[-1]["spec"]["clustering"]["result"]["mode"] == "update_original"
    assert set(RESULT_FIELDS) <= {field["field_name"] for field in payload[0]["spec"]["fields"]}
    assert not any(config["kind"] == "Databus" for config in payload)


@pytest.mark.parametrize("mode", ["update_original", "append"])
def test_detached_clustering_does_not_prepare_stores(log_datalink, mode):
    sink = create_clustering_sink(result={"mode": mode})
    compose(*log_datalink)
    sink.refresh_from_db()
    original_cluster = pattern_storage(sink).storage_cluster_id
    sink.attached = False
    sink.save()
    switch_source(710102, timezone.now())
    configs, context = compose(*log_datalink)
    assert not any(c["kind"] == "LogClusteringSink" for c in configs)
    assert not any(c["metadata"]["name"].endswith(("_pattern", "_clustered")) for c in configs)
    databus = next(c for c in configs if c["kind"] == "Databus")
    assert databus["spec"]["sinks"][0]["kind"] == "ElasticSearchBinding"
    assert "preferCluster" not in databus["spec"]
    # 未接入聚类时普通下发不处理聚类资源。
    assert pattern_storage(sink).storage_cluster_id == original_cluster
    assert not context.leftover().get(models.ResultTableConfig)
    assert not context.leftover().get(models.ESStorageBindingConfig)


def test_same_index_in_different_tenants_gets_separate_pattern_table(log_datalink, settings):
    settings.ENABLE_MULTI_TENANT_MODE = True
    first = create_clustering_sink()
    prepare_clustering_stores(first)
    models.ClusterInfo.objects.create(
        bk_tenant_id="other",
        cluster_id=710103,
        cluster_name="other-es",
        cluster_type="elasticsearch",
        domain_name="example.com",
        port=9200,
        is_default_cluster=False,
    )
    models.ESStorage.objects.create(bk_tenant_id="other", table_id=LOG_TABLE_ID, storage_cluster_id=710103)
    other = create_clustering_sink(
        bk_tenant_id="other",
        name="other-sink",
        data_link_name="other-link",
        pattern_store={**PATTERN_TARGET, "cluster_id": 710103},
    )
    configs = prepare_clustering_stores(other)
    assert other.pattern_store["result_table"]["name"] == first.pattern_store["result_table"]["name"]
    assert pattern_storage(other).pk != pattern_storage(first).pk
    assert all(ref["tenant"] == "other" for ref in bkbase_refs(other.pattern_store).values())
    assert configs[1]["spec"]["storage"]["name"] == "other-es"


def test_full_apply_retries_with_clustering_stores(log_datalink, mocker):
    datalink, data_source = log_datalink
    create_clustering_sink()
    mocker.patch.object(datalink, "get_existing_component_config", return_value=None)
    apply = mocker.patch.object(datalink, "apply_data_link_with_retry", side_effect=[RuntimeError("apply failed"), {}])
    with pytest.raises(RuntimeError, match="apply failed"):
        datalink.apply_data_link(bk_biz_id=2, data_source=data_source, table_id=LOG_TABLE_ID)
    datalink.apply_data_link(bk_biz_id=2, data_source=data_source, table_id=LOG_TABLE_ID)
    configs = apply.call_args.args[0]
    sink = next(c for c in configs if c["kind"] == "LogClusteringSink")
    assert sink["spec"]["clustering"]["result"]["mode"] == "update_original"
    assert len([c for c in configs if c["kind"] == "ResultTable"]) == 2
    assert len([c for c in configs if c["kind"] == "ElasticSearchBinding"]) == 2
    databus = next(c for c in configs if c["kind"] == "Databus")
    assert [ref["kind"] for ref in databus["spec"]["sinks"]] == ["LogClusteringSink"]
    assert databus["spec"]["preferCluster"]["kind"] == "DatabusCluster"


@pytest.mark.parametrize("mode", ["update_original", "append"])
def test_result_schema_and_normal_query_alias_survive_reapply(log_datalink, mocker, mode):
    models.ESStorage.objects.filter(table_id=LOG_TABLE_ID).update(index_settings="{}", mapping_settings="{}")
    models.ResultTableField.objects.create(
        table_id=LOG_TABLE_ID,
        bk_tenant_id="system",
        field_name="message",
        field_type="string",
        tag="dimension",
        is_config_by_user=True,
    )
    models.ResultTableFieldOption.create_option(
        LOG_TABLE_ID, "message", "es_type", "text", creator="system", bk_tenant_id="system"
    )
    route = "bklog_index_set_schema_test.__default__"
    models.ResultTable.objects.create(
        table_id=route, bk_tenant_id="system", default_storage="elasticsearch", bk_biz_id=2, is_custom_table=True
    )
    models.ESStorage.objects.create(
        table_id=route,
        bk_tenant_id="system",
        origin_table_id=LOG_TABLE_ID,
        source_type="es",
        index_set="source_logs",
        storage_cluster_id=710101,
    )
    for table_id in (LOG_TABLE_ID, route):
        models.ESFieldQueryAliasOption.objects.create(
            table_id=table_id, bk_tenant_id="system", query_alias="body", field_path="message", path_type="text"
        )
    sink = create_clustering_sink(result={"mode": mode})
    publish = mocker.patch.object(SpaceTableIDRedis, "push_table_id_detail")
    for attached in (True, False, True):
        sink.attached = attached
        sink.save(update_fields=["attached"])
        configs, _ = compose(*log_datalink)
        sink.refresh_from_db()
        source_rt = models.ResultTableConfig.objects.get(table_id=LOG_TABLE_ID)
        source_config = next(
            c for c in configs if c["kind"] == "ResultTable" and c["metadata"]["name"] == source_rt.name
        )
        fields = {f["field_name"] for f in source_config["spec"]["fields"]}
        assert (set(RESULT_FIELDS) <= fields) == (mode == "update_original")
        source = models.ESStorage.objects.get(table_id=LOG_TABLE_ID)
        mapping = source.index_body["mappings"]["properties"]
        assert mapping["message"]["type"] == "text"
        if mode == "update_original":
            assert mapping["__log_signature"]["type"] == "keyword"
            assert mapping["__log_cluster_publish_revision"]["type"] == "long"
        else:
            assert "__log_signature" not in mapping
        detail, _ = SpaceTableIDRedis()._compose_log_table_id_detail(bk_tenant_id="system", table_id_list=[route])
        # signature 别名由日志平台随路由下发，metadata 不改业务别名。
        assert detail[route]["field_alias"] == {"body": "message"}
        # 查询路由由日志平台注册和发布，metadata 不重新发布源表路由。
        assert not any(route in call.kwargs.get("table_id_list", []) for call in publish.call_args_list)


def test_pattern_timestamp_added_to_existing_table_and_rotation(log_datalink, mocker):
    sink = create_clustering_sink()
    prepare_clustering_stores(sink)
    storage = pattern_storage(sink)
    # 模拟升级前的登记；只靠新表初始化不能修复这些存量表。
    models.ResultTableField.objects.filter(table_id=storage.table_id, field_name="dtEventTimeStamp").delete()
    models.ResultTableFieldOption.objects.filter(table_id=storage.table_id, field_name="dtEventTimeStamp").delete()
    checked = []

    def prepare_index(self, **kwargs):
        if self.table_id == storage.table_id:
            checked.append(self.index_body["mappings"]["properties"]["dtEventTimeStamp"])
        return True

    mocker.patch.object(models.ESStorage, "update_index_and_aliases", new=prepare_index)
    for _ in range(2):
        configs = prepare_clustering_stores(sink)
        timestamp = next(f for f in configs[0]["spec"]["fields"] if f["field_name"] == "dtEventTimeStamp")
        assert timestamp["field_type"] == "long"
    assert checked == [{"type": "date", "format": "epoch_millis"}] * 2
    assert models.ResultTableField.objects.filter(table_id=storage.table_id, field_name="dtEventTimeStamp").count() == 1
    # 后续轮转重新加载持久化配置仍生成同一时间 mapping。
    reloaded = models.ESStorage.objects.get(pk=storage.pk)
    assert reloaded.index_body["mappings"]["properties"]["dtEventTimeStamp"] == checked[-1]
