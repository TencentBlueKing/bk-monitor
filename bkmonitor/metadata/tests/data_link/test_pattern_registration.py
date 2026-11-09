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
    publish_clustering_routes,
)
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis
from metadata.resources.log_clustering import apply_log_clustering_sink_only, get_log_clustering_query_targets
from metadata.tests.data_link.test_log_clustering_sink import (
    BINDING,
    LOG_TABLE_ID,
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
    assert source["spec"]["dataType"] == "metric"
    assert "dtEventTimeStamp" not in {f["field_name"] for f in source["spec"]["fields"]}

    # 模拟已下发的旧日志链路；下一次生成配置应原地纠正类型并保留资源身份。
    rt = models.ResultTableConfig.objects.get(table_id=LOG_TABLE_ID)
    assert rt.data_type == "metric"
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


def test_unregistered_log_source_preserves_existing_data_type(log_datalink):
    compose(*log_datalink)
    rt = models.ResultTableConfig.objects.get(table_id=LOG_TABLE_ID)
    rt.data_type = "log"
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
    assert storage.index_body["mappings"]["properties"]["log_signature"]["type"] == "keyword"
    assert storage.index_body["mappings"]["properties"]["log_cluster_publish_revision"]["type"] == "long"
    assert sink.compose_config(RAW_SINK)["spec"]["clustering"]["result"] == sink.result
    remote = {(c["kind"], c["metadata"]["name"]): {**c, "status": {"phase": "Ok"}} for c in configs}
    datalink, _ = log_datalink
    mocker.patch.object(
        datalink, "get_existing_component_config", side_effect=lambda kind, name, ns: remote[kind, name]
    )
    targets = get_log_clustering_query_targets(datalink, LOG_TABLE_ID, sink.compose_config(RAW_SINK)["spec"])
    assert targets["clustered"]["query_index"] == storage.index_name
    assert targets["clustered"]["need_add_time"] is True
    assert targets["pattern"]["query_index"] == f"2_bklog_{BINDING['index_id']}_pattern"
    assert targets["pattern"]["need_add_time"] is False
    old_result = copy.deepcopy(sink.result)
    old_pattern = copy.deepcopy(sink.pattern_store)
    old_config = sink.compose_config(RAW_SINK)
    switch_source(710102, timezone.now())
    prepare_clustering_stores(sink)
    assert sink.result["result_table"] == old_result["result_table"]
    assert sink.result["es_binding"] != old_result["es_binding"]
    assert sink.pattern_store["es_binding"] != old_pattern["es_binding"]
    merged = models.DataLink.merge_component_config(old_config, sink.compose_config(RAW_SINK))
    assert merged["spec"]["clustering"]["result"] == sink.result


def test_append_publish_keeps_both_tables_history(log_datalink, mocker):
    datalink, _ = log_datalink
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
    switch_source(710102, timezone.now())
    prepare_clustering_stores(sink)
    mocker.patch.object(SpaceTableIDRedis, "push_table_id_detail")
    publish_clustering_routes(datalink)
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
    prepare_index = mocker.patch.object(models.ESStorage, "update_index_and_aliases", side_effect=[False, True])
    apply = mocker.patch.object(datalink, "apply_data_link_with_retry")
    mocker.patch.object(datalink, "get_existing_component_config", return_value=None)
    with pytest.raises(RuntimeError, match="索引或写别名未准备完成"):
        apply_log_clustering_sink_only(datalink, sink, RAW_SINK)
    apply.assert_not_called()
    apply_log_clustering_sink_only(datalink, sink, RAW_SINK)
    assert prepare_index.call_count == 2
    assert prepare_index.call_args.kwargs["strict"] is True
    configs = apply.call_args.args[0]
    assert len(configs) == 5
    assert configs[-1]["spec"]["clustering"]["result"] == sink.result


@pytest.fixture
def log_datalink(mocker):
    mocker.patch.object(models.ESStorage, "update_index_and_aliases", return_value=True)
    mocker.patch("bkmonitor.utils.tenant.get_tenant_default_biz_id", return_value=2)
    return create_log_datalink()


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


def test_register_fixed_pattern_once_per_index(log_datalink):
    sink = create_clustering_sink()
    first = prepare_clustering_stores(sink)
    assert prepare_clustering_stores(sink) == first
    sink.binding = {**sink.binding, "generation": 2}
    assert prepare_clustering_stores(sink) == first
    rt, binding = first
    assert rt["spec"]["dataType"] == "log"
    assert rt["metadata"]["name"] == f"bklog_{BINDING['index_id']}_pattern"
    expected_index = f"{rt['spec']['bizId']}_{rt['metadata']['name']}"
    assert binding["metadata"]["annotations"]["physical_table_name"] == expected_index
    assert {field["field_name"]: field["field_type"] for field in rt["spec"]["fields"]} == PATTERN_FIELDS
    assert binding["spec"]["data"] == sink.pattern_store["result_table"]
    assert "write_alias" not in binding["spec"]
    assert binding["spec"]["doc_value_fields"] == PATTERN_KEYS
    assert binding["spec"]["unique_field_list"] == PATTERN_KEYS
    storage = pattern_storage(sink)
    assert storage.index_set == binding["metadata"]["annotations"]["physical_table_name"]
    assert storage.storage_cluster_id == models.ESStorage.objects.get(table_id=LOG_TABLE_ID).storage_cluster_id
    assert storage.need_create_index is False
    assert models.StorageClusterRecord.objects.filter(table_id=storage.table_id).count() == 1
    assert not models.DataSourceResultTable.objects.filter(table_id=storage.table_id).exists()
    other = create_clustering_sink(
        name="other-pattern", data_link_name="other-link", binding={**BINDING, "index_id": "other"}
    )
    prepare_clustering_stores(other)
    assert pattern_storage(other).table_id != storage.table_id


def test_switch_storage_keeps_fixed_name_and_all_history(log_datalink):
    sink = create_clustering_sink()
    first = prepare_clustering_stores(sink)
    storage = pattern_storage(sink)
    original_cluster = storage.storage_cluster_id
    second_time = timezone.now()
    switch_source(710102, second_time)
    second = prepare_clustering_stores(sink)
    assert second[0] == first[0]
    assert second[1]["metadata"]["annotations"] == first[1]["metadata"]["annotations"]
    assert second[1]["metadata"]["name"] != first[1]["metadata"]["name"]
    assert second[1]["spec"]["storage"]["name"] == "pattern-test-710102"
    prepare_clustering_stores(sink)
    third_time = second_time + datetime.timedelta(seconds=30)
    switch_source(original_cluster, third_time)
    prepare_clustering_stores(sink)
    records = list(models.StorageClusterRecord.objects.filter(table_id=storage.table_id).order_by("enable_time"))
    assert [r.cluster_id for r in records] == [original_cluster, 710102, original_cluster]
    assert [r.is_current for r in records] == [False, False, True]
    assert all(not r.is_deleted for r in records)
    assert records[1].enable_time == second_time


@pytest.mark.parametrize("multi_tenant, expected_biz", [(False, 91), (True, 17)])
def test_pattern_index_uses_bkbase_storage_business_id(log_datalink, settings, multi_tenant, expected_biz):
    settings.ENABLE_MULTI_TENANT_MODE = multi_tenant
    settings.DEFAULT_BKDATA_BIZ_ID = 91
    sink = create_clustering_sink(bk_biz_id=17, binding={**BINDING, "index_id": "42"})
    rt, binding = prepare_clustering_stores(sink)
    assert rt["metadata"]["name"] == "bklog_42_pattern"
    assert rt["spec"]["bizId"] == expected_biz
    expected_index = f"{expected_biz}_bklog_42_pattern"
    assert binding["metadata"]["annotations"]["physical_table_name"] == expected_index
    assert pattern_storage(sink).index_set == expected_index


def test_publish_retry_preserves_history_and_routes(log_datalink, mocker):
    datalink, _ = log_datalink
    sink = create_clustering_sink()
    prepare_clustering_stores(sink)
    storage = pattern_storage(sink)
    route = "bklog_index_set_test_pattern.__default__"
    models.ResultTable.objects.create(
        table_id=route, bk_tenant_id="system", default_storage="elasticsearch", bk_biz_id=2, is_custom_table=True
    )
    models.ESStorage.objects.create(
        table_id=route,
        bk_tenant_id="system",
        origin_table_id=storage.table_id,
        source_type="es",
        index_set=storage.index_set,
        storage_cluster_id=storage.storage_cluster_id,
    )
    switch_source(710102, timezone.now())
    prepare_clustering_stores(sink)
    publish = mocker.patch.object(
        SpaceTableIDRedis, "push_table_id_detail", side_effect=[RuntimeError("publish failed"), None]
    )
    with pytest.raises(RuntimeError, match="publish failed"):
        publish_clustering_routes(datalink)
    publish_clustering_routes(datalink)
    assert publish.call_args.kwargs["is_publish"] is True
    assert publish.call_args.kwargs["raise_on_log_write_error"] is True
    routes, _ = SpaceTableIDRedis()._compose_log_table_id_detail(bk_tenant_id="system", table_id_list=[route])
    assert routes[route]["storage_id"] == 710102
    assert len(routes[route]["storage_cluster_records"]) == 2
    expected_index = f"2_bklog_{BINDING['index_id']}_pattern"
    assert routes[route]["db"] == expected_index
    assert {r["db"] for r in routes[route]["storage_cluster_records"]} == {expected_index}
    assert models.StorageClusterRecord.objects.filter(table_id=storage.table_id).count() == 2


def test_failed_apply_retries_same_pattern_resources(log_datalink, mocker):
    datalink, _ = log_datalink
    sink = create_clustering_sink()
    mocker.patch.object(datalink, "get_existing_component_config", return_value=None)
    apply = mocker.patch.object(
        datalink, "apply_data_link_with_retry", side_effect=[RuntimeError("apply failed"), None]
    )
    publish = mocker.patch("metadata.models.data_link.log_clustering.publish_clustering_routes")
    with pytest.raises(RuntimeError, match="apply failed"):
        apply_log_clustering_sink_only(datalink, sink, RAW_SINK)
    publish.assert_not_called()
    payload = copy.deepcopy(apply.call_args.args[0])
    apply_log_clustering_sink_only(datalink, sink, RAW_SINK)
    assert apply.call_args.args[0] == payload
    assert [c["kind"] for c in payload] == ["ResultTable", "ElasticSearchBinding", "LogClusteringSink"]
    assert payload[-1]["spec"]["clustering"]["result"]["mode"] == "update_original"
    publish.assert_called_once_with(datalink)


@pytest.mark.parametrize("mode", ["update_original", "append"])
def test_regular_save_and_disabled_clustering_follow_source_storage(log_datalink, mode):
    sink = create_clustering_sink(result={"mode": mode})
    configs, _ = compose(*log_datalink)
    sink.refresh_from_db()
    stored_ref = copy.deepcopy(sink.pattern_store)
    sink.attached = False
    sink.save()
    switch_source(710102, timezone.now())
    configs, context = compose(*log_datalink)
    sink.refresh_from_db()
    assert sink.pattern_store["result_table"] == stored_ref["result_table"]
    assert sink.pattern_store["es_binding"] != stored_ref["es_binding"]
    assert not any(c["kind"] == "LogClusteringSink" for c in configs)
    databus = next(c for c in configs if c["kind"] == "Databus")
    assert databus["spec"]["sinks"][0]["kind"] == "ElasticSearchBinding"
    assert pattern_storage(sink).storage_cluster_id == 710102
    # Pattern 资源独立归组，不占用原日志唯一 RT/Binding 的认领名额。
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
    other = create_clustering_sink(bk_tenant_id="other", name="other-sink", data_link_name="other-link")
    configs = prepare_clustering_stores(other)
    assert other.pattern_store["result_table"]["name"] == first.pattern_store["result_table"]["name"]
    assert pattern_storage(other).pk != pattern_storage(first).pk
    assert all(ref["tenant"] == "other" for ref in other.pattern_store.values())
    assert configs[1]["spec"]["storage"]["name"] == "other-es"


def test_full_apply_publishes_routes_only_after_success(log_datalink, mocker):
    datalink, data_source = log_datalink
    create_clustering_sink()
    mocker.patch.object(datalink, "get_existing_component_config", return_value=None)
    apply = mocker.patch.object(datalink, "apply_data_link_with_retry", side_effect=[RuntimeError("apply failed"), {}])
    publish = mocker.patch("metadata.models.data_link.log_clustering.publish_clustering_routes")
    with pytest.raises(RuntimeError, match="apply failed"):
        datalink.apply_data_link(bk_biz_id=2, data_source=data_source, table_id=LOG_TABLE_ID)
    publish.assert_not_called()
    datalink.apply_data_link(bk_biz_id=2, data_source=data_source, table_id=LOG_TABLE_ID)
    configs = apply.call_args.args[0]
    sink = next(c for c in configs if c["kind"] == "LogClusteringSink")
    assert sink["spec"]["clustering"]["result"]["mode"] == "update_original"
    assert len([c for c in configs if c["kind"] == "ResultTable"]) == 2
    assert len([c for c in configs if c["kind"] == "ElasticSearchBinding"]) == 2
    publish.assert_called_once_with(datalink)
