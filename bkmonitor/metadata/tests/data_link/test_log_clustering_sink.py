"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json

import pytest
from django.db import IntegrityError
from django.test import override_settings

from metadata import models
from metadata.models.data_link import DataLink, utils
from metadata.models.data_link.component_reuse import ALL_DATA_LINK_COMPONENT_KINDS, ExistingComponentContext
from metadata.models.data_link.constants import DataLinkKind, DataLinkNameScene
from metadata.models.data_link.data_link_configs import (
    COMPONENT_CLASS_MAP,
    DataBusConfig,
    ESStorageBindingConfig,
    LogClusteringSinkConfig,
)

RAW_SINK = {"kind": "ElasticSearchBinding", "name": "bkm_raw_es_binding", "namespace": "bklog"}
KAFKA_RESOURCE = {"kind": "Kafka", "name": "registered_clustering_kafka", "namespace": "bklog"}
PATTERN_RESOURCE = {"kind": "ElasticSearch", "name": "registered_pattern_es", "namespace": "bklog"}
BINDING = {
    "task_id": "0f1d2c3b-4a59-4e6f-8a7b-9c0d1e2f3a4b",
    "index_id": "24466",
    "generation": 1,
    "config_revision": 1,
    "kafka": {
        "cluster_ref": "quix-e2e",
        "input_topic": "lc-task-in",
        "output_topic": "lc-task-out",
        "consumer_group": "lc-task-worker",
        "result_group": "lc-task-result",
        "partitions": 2,
        "retention_ms": 604800000,
        "recovery_window_ms": 86400000,
        "source_namespace": "bklog",
        "mapping_revision": "log-v1",
    },
    "log_filter": [{"key": "level", "method": "eq", "value": ["ERROR", "WARN"], "condition": ""}],
    "input_mapping": {"log": "log", "timestamp": "dtEventTimeStamp"},
    "distance_threshold": "0.5",
    "pattern_index": "log-clustering-24466-pattern",
    "state_index": "log-clustering-24466-state",
    "max_message_bytes": 1048576,
}


def build_sink(**overrides) -> LogClusteringSinkConfig:
    fields = {
        "name": "bkm_lcs_50010_abcdefghijkl",
        "namespace": "bklog",
        "bk_tenant_id": "system",
        "bk_biz_id": 2,
        "data_link_name": "bklog_datalink",
        "table_id": "2_bklog.demo",
        "binding": BINDING,
        "kafka_resource": KAFKA_RESOURCE,
        "pattern_resource": PATTERN_RESOURCE,
    }
    fields.update(overrides)
    return LogClusteringSinkConfig(**fields)


@pytest.fixture
def default_biz(mocker):
    mocker.patch("bkmonitor.utils.tenant.get_tenant_default_biz_id", return_value=2)


@override_settings(ENABLE_MULTI_TENANT_MODE=False)
def test_compose_config_outputs_raw_sink_and_clustering(default_biz):
    assert build_sink().compose_config(RAW_SINK) == {
        "kind": "LogClusteringSink",
        "metadata": {"name": "bkm_lcs_50010_abcdefghijkl", "namespace": "bklog", "labels": {"bk_biz_id": "2"}},
        "spec": {
            "rawSink": RAW_SINK,
            "clustering": {
                "kafkaResource": KAFKA_RESOURCE,
                "patternResource": PATTERN_RESOURCE,
                "binding": BINDING,
            },
        },
    }


@override_settings(ENABLE_MULTI_TENANT_MODE=True)
def test_compose_config_and_reference_carry_tenant_in_multi_tenant_mode(default_biz):
    sink = build_sink(bk_tenant_id="tenant-a")

    config = sink.compose_config(RAW_SINK)

    assert config["metadata"]["tenant"] == "tenant-a"
    assert sink.reference == {
        "kind": "LogClusteringSink",
        "name": "bkm_lcs_50010_abcdefghijkl",
        "namespace": "bklog",
        "tenant": "tenant-a",
    }


@override_settings(ENABLE_MULTI_TENANT_MODE=False)
def test_reference_omits_tenant_in_single_tenant_mode():
    assert build_sink().reference == {
        "kind": "LogClusteringSink",
        "name": "bkm_lcs_50010_abcdefghijkl",
        "namespace": "bklog",
    }


@pytest.mark.parametrize("empty_field", ["binding", "kafka_resource", "pattern_resource"])
def test_compose_config_rejects_incomplete_sink(empty_field, default_biz):
    with pytest.raises(ValueError, match=empty_field):
        build_sink(**{empty_field: {}}).compose_config(RAW_SINK)


def test_compose_config_rejects_empty_raw_sink(default_biz):
    with pytest.raises(ValueError, match="raw_sink"):
        build_sink().compose_config({})


def test_kind_is_registered_for_lifecycle():
    assert DataLinkKind.get_choice_value(DataLinkKind.LOGCLUSTERINGSINK.value) == "logclusteringsinks"
    assert COMPONENT_CLASS_MAP[DataLinkKind.LOGCLUSTERINGSINK.value] is LogClusteringSinkConfig
    assert LogClusteringSinkConfig in ALL_DATA_LINK_COMPONENT_KINDS
    assert DataLink.REUSE_LEFTOVER_POLICY[(DataLink.BK_LOG, LogClusteringSinkConfig)] == "keep"


def test_bk_log_delete_order_releases_databus_before_sink_and_sink_before_bindings():
    delete_order = list(reversed(DataLink.STRATEGY_RELATED_COMPONENTS[DataLink.BK_LOG]))

    assert delete_order.index(DataBusConfig) < delete_order.index(LogClusteringSinkConfig)
    assert delete_order.index(LogClusteringSinkConfig) < delete_order.index(ESStorageBindingConfig)


def test_generated_sink_name_fits_bkbase_limit():
    name = utils.generate_bkdata_resource_name(DataLinkNameScene.LOG_CLUSTERING_SINK, 2**63 - 1)

    assert name.startswith("bkm_lcs_")
    assert len(name) <= 40


@pytest.mark.django_db(databases="__all__")
def test_unclaimed_sink_is_kept_by_bk_log_leftover_policy():
    datalink = DataLink.objects.create(
        data_link_name="bklog_datalink",
        bk_tenant_id="system",
        namespace="bklog",
        data_link_strategy=DataLink.BK_LOG,
    )
    sink = build_sink()
    sink.save()

    context = ExistingComponentContext.from_datalink(datalink)

    assert context.leftover() == {LogClusteringSinkConfig: [sink]}
    datalink._check_leftover_or_raise(context)
    assert datalink._get_absent_components_to_delete([], force_delete=True) == []


@pytest.mark.django_db(databases="__all__")
def test_datalink_allows_only_one_sink():
    build_sink().save()

    with pytest.raises(IntegrityError):
        build_sink(name="bkm_lcs_50010_mnopqrstuvwx").save()


LOG_TABLE_ID = "2_bklog.clustering_demo"
LOG_DATA_LINK_NAME = "bklog_clustering_link"


@pytest.fixture
def log_datalink(default_biz):
    data_source = models.DataSource.objects.create(
        bk_data_id=91101,
        data_name="bklog_clustering_demo",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config=DataLink.BK_LOG,
        is_custom_source=False,
        bk_tenant_id="system",
    )
    models.ResultTable.objects.create(
        table_id=LOG_TABLE_ID,
        bk_biz_id=2,
        bk_tenant_id="system",
        is_custom_table=True,
        default_storage=models.ClusterInfo.TYPE_ES,
    )
    models.ClusterInfo.objects.create(
        cluster_name="es_clustering_demo",
        cluster_type=models.ClusterInfo.TYPE_ES,
        domain_name="es.demo",
        port=9200,
        description="",
        cluster_id=710101,
        is_default_cluster=False,
        version="7.10",
        bk_tenant_id="system",
    )
    models.ESStorage.objects.create(table_id=LOG_TABLE_ID, storage_cluster_id=710101, bk_tenant_id="system")
    models.ResultTableOption.objects.create(
        bk_tenant_id="system",
        table_id=LOG_TABLE_ID,
        name=models.ResultTableOption.OPTION_V4_LOG_DATA_LINK,
        value=json.dumps(
            {
                "clean_rules": [
                    {
                        "input_id": "__raw_data",
                        "output_id": "log",
                        "operator": {"type": "assign", "key_index": "log", "output_type": "string"},
                    }
                ],
                "es_storage_config": {"unique_field_list": ["log"]},
            }
        ),
        value_type=models.ResultTableOption.TYPE_STRING,
        creator="pytest",
    )
    datalink = DataLink.objects.create(
        data_link_name=LOG_DATA_LINK_NAME,
        namespace="bklog",
        bk_tenant_id="system",
        data_link_strategy=DataLink.BK_LOG,
    )
    DataBusConfig.objects.create(
        name=LOG_DATA_LINK_NAME,
        namespace="bklog",
        bk_tenant_id="system",
        data_link_name=LOG_DATA_LINK_NAME,
        bk_biz_id=2,
        data_id_name="bkm_registered_data_id",
        bk_data_id=data_source.bk_data_id,
        consumer_group="raw_consumer_group",
    )
    return datalink, data_source


def compose(datalink: DataLink, data_source) -> tuple[list[dict], ExistingComponentContext]:
    context = ExistingComponentContext.from_datalink(datalink)
    configs = datalink.compose_log_configs(
        bk_biz_id=2, data_source=data_source, table_id=LOG_TABLE_ID, existing_context=context
    )
    return configs, context


def find_config(configs: list[dict], kind: str) -> dict:
    return next(config for config in configs if config["kind"] == kind)


def create_clustering_sink(**overrides) -> LogClusteringSinkConfig:
    fields = {"data_link_name": LOG_DATA_LINK_NAME, "table_id": LOG_TABLE_ID, "attached": True}
    fields.update(overrides)
    sink = build_sink(**fields)
    sink.save()
    return sink


@override_settings(ENABLE_MULTI_TENANT_MODE=False)
@pytest.mark.django_db(databases="__all__")
def test_compose_log_configs_without_clustering_sink_keeps_es_binding(log_datalink):
    configs, _ = compose(*log_datalink)

    assert [config["kind"] for config in configs] == ["ResultTable", "ElasticSearchBinding", "Databus"]
    assert find_config(configs, "Databus")["spec"]["sinks"] == [
        {"kind": "ElasticSearchBinding", "name": LOG_DATA_LINK_NAME, "namespace": "bklog"}
    ]


@override_settings(ENABLE_MULTI_TENANT_MODE=False)
@pytest.mark.django_db(databases="__all__")
def test_compose_log_configs_with_attached_sink_only_replaces_databus_sinks(log_datalink):
    plain_configs, _ = compose(*log_datalink)
    sink = create_clustering_sink(raw_sink={})

    configs, context = compose(*log_datalink)

    es_binding_ref = {"kind": "ElasticSearchBinding", "name": LOG_DATA_LINK_NAME, "namespace": "bklog"}
    clustering_config = find_config(configs, "LogClusteringSink")
    assert clustering_config["metadata"]["name"] == sink.name
    assert clustering_config["spec"]["rawSink"] == es_binding_ref
    assert clustering_config["spec"]["clustering"]["binding"] == BINDING

    databus_config = find_config(configs, "Databus")
    plain_databus_config = find_config(plain_configs, "Databus")
    assert databus_config["spec"]["sinks"] == [sink.reference]
    assert {key: value for key, value in databus_config["spec"].items() if key != "sinks"} == {
        key: value for key, value in plain_databus_config["spec"].items() if key != "sinks"
    }
    assert databus_config["spec"]["consumerGroup"] == "raw_consumer_group"
    assert databus_config["metadata"] == plain_databus_config["metadata"]

    assert find_config(configs, "ElasticSearchBinding") == find_config(plain_configs, "ElasticSearchBinding")
    assert LogClusteringSinkConfig not in context.leftover()
    sink.refresh_from_db()
    assert sink.raw_sink == es_binding_ref
    assert DataBusConfig.objects.get(name=LOG_DATA_LINK_NAME).sink_names == [f"LogClusteringSink:{sink.name}"]


ES_BINDING_REF = {"kind": "ElasticSearchBinding", "name": LOG_DATA_LINK_NAME, "namespace": "bklog"}
CLUSTERING_SINK_REF = {"kind": "LogClusteringSink", "name": "bkm_lcs_50010_abcdefghijkl", "namespace": "bklog"}


@pytest.mark.parametrize(
    "remote_sinks, generated_sinks",
    [([ES_BINDING_REF], [CLUSTERING_SINK_REF]), ([CLUSTERING_SINK_REF], [ES_BINDING_REF])],
    ids=["attach", "detach"],
)
def test_merge_with_remote_databus_keeps_generated_sinks(remote_sinks, generated_sinks):
    metadata = {"name": LOG_DATA_LINK_NAME, "namespace": "bklog", "labels": {"bk_biz_id": "2"}}
    remote = {"kind": "Databus", "metadata": metadata, "spec": {"sinks": remote_sinks, "preferCluster": {"name": "c"}}}
    generated = {"kind": "Databus", "metadata": dict(metadata), "spec": {"sinks": generated_sinks}}

    merged = DataLink.merge_component_config(remote, generated)

    assert merged["spec"] == {"sinks": generated_sinks, "preferCluster": {"name": "c"}}


@override_settings(ENABLE_MULTI_TENANT_MODE=False)
@pytest.mark.django_db(databases="__all__")
def test_compose_log_configs_warns_only_when_existing_raw_sink_changes(log_datalink, mocker):
    warning = mocker.patch("metadata.models.data_link.data_link.logger.warning")
    sink = create_clustering_sink(raw_sink={})

    compose(*log_datalink)
    assert not any("raw_sink changed" in call.args[0] for call in warning.call_args_list)

    sink.raw_sink = {**ES_BINDING_REF, "name": "previous_es_binding"}
    sink.save()
    compose(*log_datalink)
    assert any("raw_sink changed" in call.args[0] for call in warning.call_args_list)


@override_settings(ENABLE_MULTI_TENANT_MODE=False)
@pytest.mark.django_db(databases="__all__")
def test_compose_log_configs_with_detached_sink_restores_raw_sink(log_datalink):
    plain_configs, _ = compose(*log_datalink)
    sink = create_clustering_sink(attached=False)

    configs, _ = compose(*log_datalink)

    assert configs == plain_configs
    assert LogClusteringSinkConfig.objects.filter(pk=sink.pk).exists()


@override_settings(ENABLE_MULTI_TENANT_MODE=False)
@pytest.mark.django_db(databases="__all__")
def test_compose_log_configs_rejects_attached_sink_without_single_es_binding(log_datalink):
    create_clustering_sink()
    models.ClusterInfo.objects.create(
        cluster_name="doris_clustering_demo",
        cluster_type=models.ClusterInfo.TYPE_DORIS,
        domain_name="doris.demo",
        port=9030,
        description="",
        cluster_id=710102,
        is_default_cluster=False,
        version="2.x",
        bk_tenant_id="system",
    )
    models.DorisStorage.objects.create(
        table_id=LOG_TABLE_ID,
        bkbase_table_id=f"2_{LOG_DATA_LINK_NAME}",
        storage_cluster_id=710102,
        bk_tenant_id="system",
    )
    option = models.ResultTableOption.objects.get(table_id=LOG_TABLE_ID)
    option.value = json.dumps(
        {
            **json.loads(option.value),
            "doris_storage_config": {
                "storage_keys": ["log"],
                "json_fields": [],
                "original_json_fields": [],
                "field_config_group": {},
                "tokenizers": {},
                "flush_timeout": 30,
            },
        }
    )
    option.save()

    with pytest.raises(ValueError, match="requires exactly one ElasticSearchBinding"):
        compose(*log_datalink)
