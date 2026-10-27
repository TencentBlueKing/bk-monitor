"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy
import json

import pytest
from rest_framework.exceptions import ValidationError

from core.drf_resource.exceptions import CustomException
from metadata import models
from metadata.resources.log_clustering import SetLogClusteringConfigResource
from metadata.tests.data_link.test_log_clustering_sink import (
    BINDING,
    ES_BINDING_REF,
    KAFKA_RESOURCE,
    LOG_DATA_LINK_NAME,
    LOG_TABLE_ID,
    PATTERN_RESOURCE,
    create_log_datalink,
)

pytestmark = pytest.mark.django_db(databases="__all__")

PATTERN_CLUSTER_ID = 710103


@pytest.fixture(autouse=True)
def single_tenant(settings):
    settings.ENABLE_MULTI_TENANT_MODE = False


@pytest.fixture
def clustering_datalink(mocker):
    mocker.patch("bkmonitor.utils.tenant.get_tenant_default_biz_id", return_value=2)
    datalink, data_source = create_log_datalink()
    models.ClusterInfo.objects.create(
        cluster_name=PATTERN_RESOURCE["name"],
        cluster_type=models.ClusterInfo.TYPE_ES,
        domain_name="es.pattern",
        port=9200,
        description="",
        cluster_id=PATTERN_CLUSTER_ID,
        is_default_cluster=False,
        version="7.10",
        bk_tenant_id="system",
    )
    models.BkBaseResultTable.objects.create(
        bk_tenant_id="system",
        data_link_name=LOG_DATA_LINK_NAME,
        monitor_table_id=LOG_TABLE_ID,
        storage_type=models.ClusterInfo.TYPE_ES,
    )
    models.DataSourceResultTable.objects.create(
        bk_tenant_id="system", bk_data_id=data_source.bk_data_id, table_id=LOG_TABLE_ID
    )
    return datalink


@pytest.fixture
def bkbase(mocker):
    """remote_databus 为远端 Databus 当前配置；None 表示远端不存在"""
    state = {"remote_databus": None}
    mocker.patch(
        "metadata.models.DataLink.get_existing_component_config",
        side_effect=lambda kind, name, namespace: copy.deepcopy(state["remote_databus"]) if kind == "Databus" else None,
    )
    state["apply_log_datalink"] = mocker.patch("metadata.resources.log_clustering.apply_log_datalink")
    state["apply_data_link"] = mocker.patch("metadata.models.DataLink.apply_data_link_with_retry")
    return state


def build_params(**overrides) -> dict:
    params = {
        "bk_tenant_id": "system",
        "table_id": LOG_TABLE_ID,
        "operation_id": "enable-0001",
        "expected_revision": 0,
        "binding": copy.deepcopy(BINDING),
        "kafka_resource": dict(KAFKA_RESOURCE),
        "pattern_resource": dict(PATTERN_RESOURCE),
    }
    params.update(overrides)
    return params


def set_config(**overrides) -> dict:
    return SetLogClusteringConfigResource().request(build_params(**overrides))


def get_sink() -> models.LogClusteringSinkConfig:
    return models.LogClusteringSinkConfig.objects.get(data_link_name=LOG_DATA_LINK_NAME)


def attach_remotely(state: dict) -> None:
    """模拟首次完整下发后的状态：compose 已回写 rawSink，远端 Databus 已引用聚类 Sink"""
    sink = get_sink()
    sink.raw_sink = ES_BINDING_REF
    sink.save()
    state["remote_databus"] = {"kind": "Databus", "metadata": {}, "spec": {"sinks": [sink.reference]}}


def test_first_set_creates_sink_and_applies_whole_datalink(clustering_datalink, bkbase):
    result = set_config()

    sink = get_sink()
    assert sink.name.startswith("bkm_lcs_91101_")
    assert sink.attached is True
    assert sink.revision == 1
    assert sink.binding["log_filter"] == BINDING["log_filter"]
    assert sink.kafka_resource == KAFKA_RESOURCE
    bkbase["apply_log_datalink"].assert_called_once_with(bk_tenant_id="system", table_id=LOG_TABLE_ID)
    bkbase["apply_data_link"].assert_not_called()
    assert result["revision"] == 1
    assert result["applied_scope"] == "datalink"
    assert result["sink"] == {"tenant": "system", "namespace": "bklog", "name": sink.name}
    assert result["databus"] == {"tenant": "system", "namespace": "bklog", "name": LOG_DATA_LINK_NAME}


def test_set_on_attached_sink_only_applies_sink(clustering_datalink, bkbase):
    set_config()
    attach_remotely(bkbase)
    binding = copy.deepcopy(BINDING)
    binding["log_filter"] = [{"key": "level", "method": "eq", "value": ["INFO"], "condition": ""}]

    result = set_config(operation_id="update-0001", expected_revision=1, binding=binding)

    assert result["revision"] == 2
    assert result["applied_scope"] == "sink_only"
    assert bkbase["apply_log_datalink"].call_count == 1
    (configs,), _ = bkbase["apply_data_link"].call_args
    assert [config["kind"] for config in configs] == ["LogClusteringSink"]
    assert configs[0]["spec"]["clustering"]["binding"]["log_filter"] == binding["log_filter"]
    assert configs[0]["spec"]["rawSink"] == ES_BINDING_REF


def test_replay_after_failed_apply_keeps_revision_and_reapplies_whole_datalink(clustering_datalink, bkbase):
    bkbase["apply_log_datalink"].side_effect = RuntimeError("bkbase apply failed")
    with pytest.raises(RuntimeError):
        set_config()
    assert get_sink().revision == 1

    bkbase["apply_log_datalink"].side_effect = None
    result = set_config()

    assert result["revision"] == 1
    assert result["applied_scope"] == "datalink"
    assert get_sink().revision == 1
    assert bkbase["apply_log_datalink"].call_count == 2


def test_same_operation_with_different_payload_is_rejected(clustering_datalink, bkbase):
    set_config()
    binding = copy.deepcopy(BINDING)
    binding["distance_threshold"] = "0.7"

    with pytest.raises(ValidationError, match="different request"):
        set_config(binding=binding)


def test_stale_expected_revision_is_rejected_without_changes(clustering_datalink, bkbase):
    set_config()

    with pytest.raises(ValidationError, match="stale"):
        set_config(operation_id="update-0001", expected_revision=0)
    assert get_sink().last_operation_id == "enable-0001"


def enable_doris_storage_option():
    option = models.ResultTableOption.objects.get(
        table_id=LOG_TABLE_ID, name=models.ResultTableOption.OPTION_V4_LOG_DATA_LINK
    )
    option.value = json.dumps({**json.loads(option.value), "doris_storage_config": {"storage_keys": ["log"]}})
    option.save()


def test_doris_storage_is_rejected_before_creating_sink(clustering_datalink, bkbase):
    models.DorisStorage.objects.create(table_id=LOG_TABLE_ID, storage_cluster_id=710101, bk_tenant_id="system")
    enable_doris_storage_option()

    with pytest.raises(ValidationError, match="doris"):
        set_config()
    assert not models.LogClusteringSinkConfig.objects.exists()


def test_historical_doris_storage_without_doris_option_is_accepted(clustering_datalink, bkbase):
    models.DorisStorage.objects.create(table_id=LOG_TABLE_ID, storage_cluster_id=710101, bk_tenant_id="system")

    assert set_config()["revision"] == 1


def test_es_storage_without_es_option_is_rejected(clustering_datalink, bkbase):
    models.DorisStorage.objects.create(table_id=LOG_TABLE_ID, storage_cluster_id=710101, bk_tenant_id="system")
    option = models.ResultTableOption.objects.get(
        table_id=LOG_TABLE_ID, name=models.ResultTableOption.OPTION_V4_LOG_DATA_LINK
    )
    option.value = json.dumps(
        {"clean_rules": json.loads(option.value)["clean_rules"], "doris_storage_config": {"storage_keys": ["log"]}}
    )
    option.save()

    with pytest.raises(ValidationError, match="elasticsearch storage"):
        set_config()


def test_unregistered_pattern_cluster_is_rejected_before_creating_sink(clustering_datalink, bkbase):
    models.ClusterInfo.objects.filter(cluster_id=PATTERN_CLUSTER_ID).delete()

    with pytest.raises(ValidationError, match="not a metadata elasticsearch cluster"):
        set_config()
    assert not models.LogClusteringSinkConfig.objects.exists()
    bkbase["apply_log_datalink"].assert_not_called()


def test_missing_datasource_is_rejected_before_creating_sink(clustering_datalink, bkbase):
    models.DataSourceResultTable.objects.filter(table_id=LOG_TABLE_ID).delete()

    with pytest.raises(ValidationError, match="related datasource not found"):
        set_config()
    assert not models.LogClusteringSinkConfig.objects.exists()


@pytest.mark.parametrize(
    "field, value",
    [
        ("kafka_resource", {"kind": "KafkaChannel", "name": "k", "namespace": "bklog"}),
        ("pattern_resource", {"kind": "ElasticSearchBinding", "name": "p", "namespace": "bklog"}),
        ("binding.log_filter", [{"key": "level", "method": "eq", "value": ["ERROR"], "condition": "and"}]),
        ("binding.log_filter", [{"key": "level", "method": "contains", "value": ["ERROR"], "condition": ""}]),
        ("binding.distance_threshold", "0.4"),
        ("binding.kafka.recovery_window_ms", 604800001),
    ],
)
def test_invalid_request_is_rejected(field, value, clustering_datalink, bkbase):
    params = build_params()
    target = params
    *parents, leaf = field.split(".")
    for parent in parents:
        target = target[parent]
    target[leaf] = value

    with pytest.raises(CustomException):
        SetLogClusteringConfigResource().request(params)
    assert not models.LogClusteringSinkConfig.objects.exists()
