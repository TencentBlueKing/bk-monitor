"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import pytest
from django.db import IntegrityError
from django.test import override_settings

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
