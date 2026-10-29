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
    state = {"remote_databus": None, "remote_sink": None}
    mocker.patch(
        "metadata.models.DataLink.get_existing_component_config",
        side_effect=lambda kind, name, namespace: copy.deepcopy(
            state["remote_databus"] if kind == "Databus" else state["remote_sink"]
        ),
    )
    state["apply_log_datalink"] = mocker.patch("metadata.resources.log_clustering.apply_log_datalink")
    state["apply_data_link"] = mocker.patch("metadata.models.DataLink.apply_data_link_with_retry")
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
    state["remote_sink"] = get_sink().compose_config(raw_sink=ES_BINDING_REF)
    state["remote_sink"]["status"] = {
        "phase": "Ok",
        "message": json.dumps({"configuration_applied": True, "clustering_closed": False}),
    }
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


def test_omitted_binding_defaults_are_saved_and_applied(clustering_datalink, bkbase):
    set_config()
    attach_remotely(bkbase)
    binding = copy.deepcopy(BINDING)
    binding.pop("distance_threshold")
    binding.pop("max_message_bytes")

    set_config(binding=binding)

    expected = {**binding, "distance_threshold": "0.5", "max_message_bytes": 1048576}
    assert get_sink().binding == expected
    (configs,), _ = bkbase["apply_data_link"].call_args
    assert configs[0]["spec"]["clustering"]["binding"] == expected


@pytest.mark.parametrize(
    "method",
    ["eq", "neq", "include", "exclude", "starts_with", "not_starts_with", "ends_with", "not_ends_with"],
)
def test_all_filter_methods_are_saved_and_forwarded(method, clustering_datalink, bkbase):
    set_config()
    attach_remotely(bkbase)
    binding = copy.deepcopy(BINDING)
    rule = {"key": "log", "method": method, "value": [" ERROR_%* ", "", "\t"], "condition": ""}
    binding["log_filter"] = [rule]

    set_config(binding=binding)

    assert get_sink().binding["log_filter"] == [rule]
    (configs,), _ = bkbase["apply_data_link"].call_args
    assert configs[0]["spec"]["clustering"]["binding"]["log_filter"] == [rule]


def test_candidate_message_size_upper_bound_is_forwarded(clustering_datalink, bkbase):
    set_config()
    attach_remotely(bkbase)
    binding = copy.deepcopy(BINDING)
    binding["max_message_bytes"] = 16 * 1024 * 1024

    set_config(binding=binding)

    (configs,), _ = bkbase["apply_data_link"].call_args
    assert configs[0]["spec"]["clustering"]["binding"]["max_message_bytes"] == 16 * 1024 * 1024


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
        ("binding.max_message_bytes", 0),
        ("binding.max_message_bytes", 16 * 1024 * 1024 + 1),
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


def operate(action: str) -> dict:
    return OperateLogClusteringResource().request(
        {"bk_tenant_id": "system", "table_id": LOG_TABLE_ID, "action": action}
    )


def get_status() -> dict:
    return GetLogClusteringStatusResource().request({"bk_tenant_id": "system", "table_id": LOG_TABLE_ID})


@pytest.mark.parametrize("action,enabled", [("disable", False), ("enable", True)])
@pytest.mark.parametrize("multi_tenant", [False, True])
def test_enable_switch_applies_only_remote_sink(action, enabled, multi_tenant, clustering_datalink, bkbase, settings):
    set_config()
    attach_remotely(bkbase)
    settings.ENABLE_MULTI_TENANT_MODE = multi_tenant
    remote = bkbase["remote_sink"]
    if multi_tenant:
        remote["metadata"]["tenant"] = "system"
    remote["metadata"]["annotations"] = {"keep": "annotation"}
    remote["spec"]["clustering"]["enabled"] = not enabled
    remote["spec"]["clustering"]["retryFailures"] = ["event-1"]
    before = copy.deepcopy(remote)
    binding = copy.deepcopy(get_sink().binding)

    result = operate(action)

    expected = {key: copy.deepcopy(before[key]) for key in ("kind", "metadata", "spec")}
    expected["spec"]["clustering"]["enabled"] = enabled
    bkbase["apply_data_link"].assert_called_once_with([expected])
    assert bkbase["remote_sink"] == before
    assert result == {"action": action, "attached": True}
    assert get_sink().binding == binding
    assert get_sink().attached is True
    assert bkbase["apply_log_datalink"].call_count == 1


def test_enable_switch_requires_existing_remote_resource(clustering_datalink, bkbase):
    set_config()
    with pytest.raises(ValidationError, match="does not exist in BKBase"):
        operate("disable")
    bkbase["apply_data_link"].assert_not_called()
    assert get_sink().attached is True


@pytest.mark.parametrize("action", ["drain", "finish", "resume"])
def test_removed_actions_are_rejected(action, clustering_datalink, bkbase):
    with pytest.raises(CustomException):
        operate(action)
    bkbase["apply_data_link"].assert_not_called()
    bkbase["apply_log_datalink"].assert_not_called()


def test_detach_and_attach_only_switch_databus_reference(clustering_datalink, bkbase):
    set_config()
    attach_remotely(bkbase)
    bkbase["remote_sink"]["spec"]["clustering"]["enabled"] = False

    detached = operate("detach")
    attached = operate("attach")

    assert detached == {"action": "detach", "attached": False}
    assert attached == {"action": "attach", "attached": True}
    assert bkbase["apply_log_datalink"].call_count == 3
    bkbase["apply_data_link"].assert_not_called()
    assert bkbase["remote_sink"]["spec"]["clustering"]["enabled"] is False
    assert get_sink().attached is True


def test_retry_resends_enable_switch_without_changing_binding(clustering_datalink, bkbase, change_lock):
    set_config()
    attach_remotely(bkbase)
    bkbase["apply_data_link"].side_effect = RuntimeError("bkbase apply failed")
    with pytest.raises(RuntimeError):
        operate("disable")
    assert not change_lock.held

    first_request = copy.deepcopy(bkbase["apply_data_link"].call_args.args)
    bkbase["apply_data_link"].side_effect = None
    result = operate("disable")

    assert result == {"action": "disable", "attached": True}
    assert bkbase["apply_data_link"].call_args.args == first_request
    assert bkbase["apply_data_link"].call_count == 2


@pytest.mark.parametrize("action", ["detach", "disable"])
def test_operation_is_rejected_while_another_change_is_in_progress(action, clustering_datalink, bkbase, change_lock):
    set_config()
    change_lock.held.add(f"metadata:log_clustering:system:{LOG_DATA_LINK_NAME}")

    with pytest.raises(ValidationError, match="in progress"):
        operate(action)
    assert get_sink().attached is True
    bkbase["apply_data_link"].assert_not_called()


@pytest.mark.parametrize("action", ["detach", "disable"])
def test_operation_holds_change_lock_during_apply(action, clustering_datalink, bkbase, change_lock):
    set_config()
    attach_remotely(bkbase)
    lock_name = f"metadata:log_clustering:system:{LOG_DATA_LINK_NAME}"
    held_during_apply = []
    apply = bkbase["apply_log_datalink"] if action == "detach" else bkbase["apply_data_link"]
    apply.side_effect = lambda *args, **kwargs: held_during_apply.append(lock_name in change_lock.held)

    operate(action)

    assert held_during_apply == [True]
    assert lock_name not in change_lock.held


def test_operate_without_config_is_rejected(clustering_datalink, bkbase):
    with pytest.raises(ValidationError, match="no log clustering config"):
        operate("disable")
    bkbase["apply_data_link"].assert_not_called()


def test_status_without_config_reports_not_configured(clustering_datalink, bkbase):
    assert get_status() == {"configured": False}


def test_status_reads_progress_from_sink_resource(clustering_datalink, bkbase):
    set_config()
    attach_remotely(bkbase)

    result = get_status()

    sink = get_sink()
    assert result["configured"] is True
    assert result["binding"] == sink.binding
    assert result["raw_sink"] == ES_BINDING_REF
    assert result["sink"] == {"tenant": "system", "namespace": "bklog", "name": sink.name}
    assert result["databus_resource"] == bkbase["remote_databus"]
    assert result["sink_resource"] == bkbase["remote_sink"]
    assert (result["sink_referenced"], result["raw_sink_referenced"]) == (True, False)
    assert result["clustering_status"] == {"configuration_applied": True, "clustering_closed": False}
    assert result["errors"] == []


@pytest.mark.parametrize("status", [None, {}, {"phase": "Pending", "message": ""}])
def test_status_without_progress_does_not_claim_completion(status, clustering_datalink, bkbase):
    set_config()
    attach_remotely(bkbase)
    bkbase["remote_sink"]["status"] = status

    result = get_status()

    assert result["clustering_status"] is None
    assert result["errors"] == []
    assert result["sink_referenced"] is True


@pytest.mark.parametrize("message", ["not json", "[]", "null", "true"])
def test_invalid_progress_reports_error_and_preserves_other_status(message, clustering_datalink, bkbase):
    set_config()
    attach_remotely(bkbase)
    bkbase["remote_sink"]["status"]["message"] = message

    result = get_status()

    assert result["clustering_status"] is None
    assert result["sink_resource"] == bkbase["remote_sink"]
    assert result["sink_referenced"] is True
    assert len(result["errors"]) == 1
    assert result["errors"][0]["source"] == "clustering_status"


def test_status_keeps_databus_when_sink_query_fails(clustering_datalink, bkbase, mocker):
    set_config()
    attach_remotely(bkbase)
    bkbase["remote_databus"]["spec"]["sinks"] = [ES_BINDING_REF]

    def fetch(kind, name, namespace):
        if kind == "LogClusteringSink":
            raise RuntimeError("resource unavailable")
        return bkbase["remote_databus"]

    mocker.patch("metadata.models.DataLink.get_existing_component_config", side_effect=fetch)
    result = get_status()

    assert (result["sink_referenced"], result["raw_sink_referenced"]) == (False, True)
    assert result["clustering_status"] is None
    assert result["errors"] == [{"source": "sink_resource", "message": "resource unavailable"}]


def test_status_without_single_es_binding_reports_raw_sink_unreferenced(clustering_datalink, bkbase):
    set_config()
    bkbase["remote_databus"] = {"kind": "Databus", "metadata": {}, "spec": {"sinks": [ES_BINDING_REF]}}

    result = get_status()

    assert (result["raw_sink"], result["raw_sink_referenced"]) == (None, False)


def test_filter_update_preserves_remote_disabled_state(clustering_datalink, bkbase):
    set_config()
    attach_remotely(bkbase)
    bkbase["remote_sink"]["spec"]["clustering"]["enabled"] = False
    binding = copy.deepcopy(BINDING)
    binding["log_filter"] = [{"key": "level", "method": "eq", "value": ["INFO"], "condition": ""}]

    set_config(binding=binding)

    (configs,), _ = bkbase["apply_data_link"].call_args
    assert configs[0]["spec"]["clustering"]["enabled"] is False
    assert configs[0]["spec"]["clustering"]["binding"]["log_filter"] == binding["log_filter"]
    assert bkbase["apply_log_datalink"].call_count == 1
