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

from api.bkdata.default import GetLogClusteringStatus, LogClusteringAction
from core.drf_resource.exceptions import CustomException
from metadata import models
from metadata.resources.log_clustering import (
    GetLogClusteringStatusResource,
    OperateLogClusteringResource,
    SetLogClusteringConfigResource,
)
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


class FakeDistributedLock:
    held: set[str] = set()

    def __init__(self, redis_client, lock_name, timeout):
        self.lock_name = lock_name

    def acquire(self):
        if self.lock_name in self.held:
            return False
        self.held.add(self.lock_name)
        return True

    def release(self):
        self.held.discard(self.lock_name)


@pytest.fixture(autouse=True)
def change_lock(mocker):
    FakeDistributedLock.held = set()
    mocker.patch("metadata.resources.log_clustering.DistributedLock", FakeDistributedLock)
    mocker.patch("metadata.resources.log_clustering.RedisTools")
    return FakeDistributedLock


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
    state["action"] = mocker.patch(
        "metadata.resources.log_clustering.api.bkdata.log_clustering_action", return_value={"accepted": True}
    )
    state["status"] = mocker.patch(
        "metadata.resources.log_clustering.api.bkdata.get_log_clustering_status",
        return_value={"boundary_ready": True, "can_unbind": False},
    )
    return state


def build_params(**overrides) -> dict:
    params = {
        "bk_tenant_id": "system",
        "table_id": LOG_TABLE_ID,
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


def create_es_binding(name: str = ES_BINDING_REF["name"]) -> models.ESStorageBindingConfig:
    return models.ESStorageBindingConfig.objects.create(
        name=name,
        namespace="bklog",
        bk_tenant_id="system",
        bk_biz_id=2,
        data_link_name=LOG_DATA_LINK_NAME,
        es_cluster_name="es_clustering_demo",
        table_id=LOG_TABLE_ID,
    )


def attach_remotely(state: dict) -> None:
    """模拟首次完整下发后的状态：已生成 ES 存储绑定，远端 Databus 已引用聚类 Sink"""
    create_es_binding()
    state["remote_databus"] = {"kind": "Databus", "metadata": {}, "spec": {"sinks": [get_sink().reference]}}


def test_first_set_creates_sink_and_applies_whole_datalink(clustering_datalink, bkbase):
    result = set_config()

    sink = get_sink()
    assert sink.name.startswith("bkm_lcs_91101_")
    assert sink.attached is True
    assert sink.binding["log_filter"] == BINDING["log_filter"]
    assert sink.kafka_resource == KAFKA_RESOURCE
    bkbase["apply_log_datalink"].assert_called_once_with(bk_tenant_id="system", table_id=LOG_TABLE_ID)
    bkbase["apply_data_link"].assert_not_called()
    assert result["applied_scope"] == "datalink"
    assert result["sink"] == {"tenant": "system", "namespace": "bklog", "name": sink.name}
    assert result["databus"] == {"tenant": "system", "namespace": "bklog", "name": LOG_DATA_LINK_NAME}


def test_set_on_attached_sink_only_applies_sink(clustering_datalink, bkbase):
    set_config()
    attach_remotely(bkbase)
    binding = copy.deepcopy(BINDING)
    binding["log_filter"] = [{"key": "level", "method": "eq", "value": ["INFO"], "condition": ""}]

    result = set_config(binding=binding)

    assert result["applied_scope"] == "sink_only"
    assert bkbase["apply_log_datalink"].call_count == 1
    (configs,), _ = bkbase["apply_data_link"].call_args
    assert [config["kind"] for config in configs] == ["LogClusteringSink"]
    assert configs[0]["spec"]["clustering"]["binding"]["log_filter"] == binding["log_filter"]
    assert configs[0]["spec"]["rawSink"] == ES_BINDING_REF


@pytest.mark.parametrize(
    "binding_names", [[], [ES_BINDING_REF["name"], "previous_es_binding"]], ids=["none", "multiple"]
)
def test_set_without_single_es_binding_applies_whole_datalink(binding_names, clustering_datalink, bkbase):
    set_config()
    bkbase["remote_databus"] = {"kind": "Databus", "metadata": {}, "spec": {"sinks": [get_sink().reference]}}
    for name in binding_names:
        create_es_binding(name)

    result = set_config()

    assert result["applied_scope"] == "datalink"
    assert bkbase["apply_log_datalink"].call_count == 2
    bkbase["apply_data_link"].assert_not_called()


def test_change_in_progress_on_same_datalink_is_rejected_without_changes(clustering_datalink, bkbase, change_lock):
    change_lock.held.add(f"metadata:log_clustering:system:{LOG_DATA_LINK_NAME}")

    with pytest.raises(ValidationError, match="in progress"):
        set_config()
    assert not models.LogClusteringSinkConfig.objects.exists()
    bkbase["apply_log_datalink"].assert_not_called()


def test_lock_covers_remote_apply_and_is_released_after_failure(clustering_datalink, bkbase, change_lock):
    lock_name = f"metadata:log_clustering:system:{LOG_DATA_LINK_NAME}"
    held_during_apply = []
    bkbase["apply_log_datalink"].side_effect = lambda **kwargs: held_during_apply.append(lock_name in change_lock.held)
    set_config()
    bkbase["apply_log_datalink"].side_effect = RuntimeError("bkbase apply failed")

    with pytest.raises(RuntimeError):
        set_config()

    assert held_during_apply == [True]
    assert lock_name not in change_lock.held


def test_filter_values_keep_surrounding_whitespace(clustering_datalink, bkbase):
    binding = copy.deepcopy(BINDING)
    binding["log_filter"] = [
        {"key": "level", "method": "eq", "value": [" ERROR ", " ", "\t"], "condition": ""},
    ]

    set_config(binding=binding)

    assert get_sink().binding["log_filter"][0]["value"] == [" ERROR ", " ", "\t"]


def test_retry_after_failed_apply_reapplies_whole_datalink(clustering_datalink, bkbase):
    bkbase["apply_log_datalink"].side_effect = RuntimeError("bkbase apply failed")
    with pytest.raises(RuntimeError):
        set_config()

    bkbase["apply_log_datalink"].side_effect = None
    result = set_config()

    assert result["applied_scope"] == "datalink"
    assert result["sink"]["name"] == get_sink().name
    assert bkbase["apply_log_datalink"].call_count == 2


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

    assert set_config()["applied_scope"] == "datalink"


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


def operate(action: str, expected_revision: int, operation_id: str | None = None) -> dict:
    return OperateLogClusteringResource().request(
        {
            "bk_tenant_id": "system",
            "table_id": LOG_TABLE_ID,
            "operation_id": operation_id or f"{action}-{expected_revision}",
            "expected_revision": expected_revision,
            "action": action,
        }
    )


def get_status() -> dict:
    return GetLogClusteringStatusResource().request({"bk_tenant_id": "system", "table_id": LOG_TABLE_ID})


def test_bkbase_action_is_sent_to_databus_identity(clustering_datalink, bkbase):
    set_config()

    result = operate("drain", expected_revision=1)

    bkbase["action"].assert_called_once_with(
        bk_tenant_id="system", tenant="default", namespace="bklog", databus_name=LOG_DATA_LINK_NAME, action="drain"
    )
    assert result == {"revision": 2, "action": "drain", "attached": True, "bkbase_result": {"accepted": True}}


def test_bkbase_action_uses_request_tenant_in_multi_tenant_mode(clustering_datalink, bkbase, settings):
    set_config()
    settings.ENABLE_MULTI_TENANT_MODE = True

    operate("finish", expected_revision=1)

    assert bkbase["action"].call_args.kwargs["tenant"] == "system"


def test_detach_and_attach_switch_databus_reference_and_reapply_datalink(clustering_datalink, bkbase):
    set_config()

    detached = operate("detach", expected_revision=1)
    attached = operate("attach", expected_revision=2)

    assert (detached["attached"], detached["revision"], detached["bkbase_result"]) == (False, 2, None)
    assert (attached["attached"], attached["revision"]) == (True, 3)
    assert bkbase["apply_log_datalink"].call_count == 3
    bkbase["action"].assert_not_called()
    assert get_sink().attached is True


def test_operation_replay_keeps_revision_and_resends_action(clustering_datalink, bkbase):
    set_config()
    operate("drain", expected_revision=1, operation_id="drain-op")

    result = operate("drain", expected_revision=1, operation_id="drain-op")

    assert result["revision"] == 2
    assert bkbase["action"].call_count == 2
    with pytest.raises(ValidationError, match="different request"):
        operate("finish", expected_revision=1, operation_id="drain-op")


def test_operation_is_rejected_while_another_change_is_in_progress(clustering_datalink, bkbase, change_lock):
    set_config()
    change_lock.held.add(f"metadata:log_clustering:system:{LOG_DATA_LINK_NAME}")

    with pytest.raises(ValidationError, match="in progress"):
        operate("detach", expected_revision=1)
    assert get_sink().revision == 1
    assert get_sink().attached is True


def test_detach_reapplies_datalink_while_holding_change_lock(clustering_datalink, bkbase, change_lock):
    set_config()
    lock_name = f"metadata:log_clustering:system:{LOG_DATA_LINK_NAME}"
    held_during_apply = []
    bkbase["apply_log_datalink"].side_effect = lambda **kwargs: held_during_apply.append(lock_name in change_lock.held)

    result = operate("detach", expected_revision=1)

    assert result["revision"] == 2
    assert held_during_apply == [True]
    assert lock_name not in change_lock.held


def test_operate_without_config_is_rejected(clustering_datalink, bkbase):
    with pytest.raises(ValidationError, match="no log clustering config"):
        operate("drain", expected_revision=0)
    bkbase["action"].assert_not_called()


def test_status_without_config_reports_not_configured(clustering_datalink, bkbase):
    assert get_status() == {"configured": False}


def test_status_reports_local_binding_remote_reference_and_raw_bkbase_status(clustering_datalink, bkbase):
    set_config()
    attach_remotely(bkbase)

    result = get_status()

    sink = get_sink()
    assert result["configured"] is True
    assert result["revision"] == 1
    assert result["binding"] == sink.binding
    assert result["sink"] == {"tenant": "system", "namespace": "bklog", "name": sink.name}
    assert result["databus_resource"] == bkbase["remote_databus"]
    assert (result["sink_referenced"], result["raw_sink_referenced"]) == (True, False)
    assert result["clustering_status"] == {"boundary_ready": True, "can_unbind": False}
    assert result["errors"] == []


def test_status_keeps_other_fields_when_bkbase_status_fails(clustering_datalink, bkbase):
    set_config()
    attach_remotely(bkbase)
    bkbase["remote_databus"]["spec"]["sinks"] = [ES_BINDING_REF]
    bkbase["status"].side_effect = RuntimeError("status unavailable")

    result = get_status()

    assert (result["sink_referenced"], result["raw_sink_referenced"]) == (False, True)
    assert result["clustering_status"] is None
    assert result["errors"] == [{"source": "clustering_status", "message": "status unavailable"}]


def test_bkbase_log_clustering_api_paths():
    params = {"bk_tenant_id": "system", "tenant": "default", "namespace": "bklog", "databus_name": "bklog_db"}

    action_url = LogClusteringAction().get_request_url({**params, "action": "drain"})
    status_url = GetLogClusteringStatus().get_request_url(params)

    assert action_url.endswith("/v4/databus/log_clustering/default/bklog/bklog_db/action/")
    assert status_url.endswith("/v4/databus/log_clustering/default/bklog/bklog_db/status/")
