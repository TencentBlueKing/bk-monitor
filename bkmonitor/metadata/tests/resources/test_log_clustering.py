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
from metadata.models.space.constants import (
    DATA_LABEL_TO_RESULT_TABLE_KEY,
    RESULT_TABLE_DETAIL_KEY,
    SPACE_TO_RESULT_TABLE_KEY,
)
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis
from metadata.resources.log_datalink import BulkCreateOrUpdateLogRouter
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
    PATTERN_STORE,
    PATTERN_INDEX,
    RUNTIME_CLUSTER,
    RECOVERY_RESOURCE,
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
            state["remote_databus"]
            if kind == "Databus"
            else state["remote_sink"]
            if kind == "LogClusteringSink"
            else state.get((kind, name))
        ),
    )

    def prepare(sink):
        sink.pattern_store = copy.deepcopy(PATTERN_STORE)
        sink.save(update_fields=["pattern_store"])
        return []

    mocker.patch("metadata.models.data_link.log_clustering.prepare_clustering_stores", side_effect=prepare)
    mocker.patch("metadata.models.data_link.log_clustering.publish_clustering_routes")
    state["apply_log_datalink"] = mocker.patch(
        "metadata.resources.log_clustering.apply_log_datalink", side_effect=lambda **kwargs: prepare(get_sink())
    )
    state["apply_data_link"] = mocker.patch("metadata.models.DataLink.apply_data_link_with_retry")
    return state


def build_params(**overrides) -> dict:
    params = {
        "bk_tenant_id": "system",
        "table_id": LOG_TABLE_ID,
        "binding": copy.deepcopy(BINDING),
        "kafka_resource": dict(KAFKA_RESOURCE),
        "runtime_cluster": dict(RUNTIME_CLUSTER),
        "recovery_resource": dict(RECOVERY_RESOURCE),
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
    models.ResultTableConfig.objects.create(
        name="raw", namespace="bklog", bk_tenant_id="system", table_id=LOG_TABLE_ID, bk_biz_id=2
    )
    state[("ElasticSearchBinding", ES_BINDING_REF["name"])] = {
        "metadata": {},
        "status": {"phase": "Ok"},
        "spec": {
            "data": {"kind": "ResultTable", "namespace": "bklog", "name": "raw"},
            "storage": {"kind": "ElasticSearch", "namespace": "bklog", "name": "es_clustering_demo"},
            "write_alias": {"TimeBased": {"format": "write_%Y%m%d_actual_raw"}},
        },
    }
    state[("ElasticSearchBinding", PATTERN_STORE["es_binding"]["name"])] = {
        "metadata": {"annotations": {"physical_table_name": PATTERN_INDEX}},
        "status": {"phase": "Ok"},
        "spec": {"data": PATTERN_STORE["result_table"], "storage": PATTERN_RESOURCE},
    }
    models.ResultTableConfig.objects.create(
        bk_tenant_id="system",
        namespace="bklog",
        name=PATTERN_STORE["result_table"]["name"],
        table_id="bklog.pattern",
        data_type="log",
        bk_biz_id=2,
    )
    state[("ResultTable", PATTERN_STORE["result_table"]["name"])] = {
        "metadata": {"tenant": "system"},
        "status": {"phase": "Ok"},
        "spec": {"dataType": "log", "bizId": 2},
    }
    state["remote_sink"] = get_sink().compose_config(raw_sink=ES_BINDING_REF)
    state["remote_sink"]["status"] = {
        "phase": "Ok",
        "message": json.dumps({"configuration_applied": True, "clustering_closed": False}),
    }
    state["remote_databus"] = {
        "kind": "Databus",
        "metadata": {},
        "spec": {"sinks": [get_sink().reference], "preferCluster": copy.deepcopy(RUNTIME_CLUSTER)},
    }


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


def test_result_mode_is_fixed_at_first_set(clustering_datalink, bkbase):
    set_config(result_mode="append")
    assert get_sink().result == {"mode": "append"}
    set_config()
    assert get_sink().result == {"mode": "append"}
    with pytest.raises(ValidationError, match="不支持切换"):
        set_config(result_mode="update_original")
    assert get_sink().result == {"mode": "append"}


def test_default_result_mode_cannot_be_changed_later(clustering_datalink, bkbase):
    set_config()
    with pytest.raises(ValidationError, match="不支持切换"):
        set_config(result_mode="append")
    assert get_sink().result == {"mode": "update_original"}


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
    assert configs[0]["spec"]["raw_sink"] == ES_BINDING_REF


@pytest.mark.parametrize(
    "binding_names", [[], [ES_BINDING_REF["name"], "previous_es_binding"]], ids=["none", "multiple"]
)
def test_set_without_single_es_binding_applies_whole_datalink(binding_names, clustering_datalink, bkbase):
    set_config()
    bkbase["remote_databus"] = {
        "kind": "Databus",
        "metadata": {},
        "spec": {"sinks": [get_sink().reference], "preferCluster": copy.deepcopy(RUNTIME_CLUSTER)},
    }
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


def test_missing_datasource_is_rejected_before_creating_sink(clustering_datalink, bkbase):
    models.DataSourceResultTable.objects.filter(table_id=LOG_TABLE_ID).delete()

    with pytest.raises(ValidationError, match="related datasource not found"):
        set_config()
    assert not models.LogClusteringSinkConfig.objects.exists()


@pytest.mark.parametrize(
    "field, value",
    [
        ("kafka_resource", {"kind": "KafkaChannel", "name": "k", "namespace": "bklog"}),
        ("recovery_resource", {"kind": "ElasticSearchBinding", "name": "p", "namespace": "bklog"}),
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
def test_non_progress_message_preserves_link_status(message, clustering_datalink, bkbase):
    set_config()
    attach_remotely(bkbase)
    bkbase["remote_sink"]["status"]["message"] = message

    result = get_status()

    assert result["clustering_status"] is None
    assert result["sink_resource"] == bkbase["remote_sink"]
    assert result["sink_referenced"] is True
    assert result["errors"] == []


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


@pytest.mark.parametrize("failure_key", [RESULT_TABLE_DETAIL_KEY, DATA_LABEL_TO_RESULT_TABLE_KEY])
def test_pattern_label_resolves_to_binding_through_bulk_router(clustering_datalink, bkbase, mocker, failure_key):
    set_config()
    attach_remotely(bkbase)
    targets = GetLogClusteringStatusResource().request(
        {"bk_tenant_id": "system", "table_id": LOG_TABLE_ID, "include_query_targets": True}
    )["query_targets"]
    target = targets["pattern"]
    assert target == {
        "cluster_id": PATTERN_CLUSTER_ID,
        "storage_type": "elasticsearch",
        "query_index": PATTERN_INDEX,
        "source_type": "es",
        "need_add_time": False,
        "table_id": "bklog.pattern",
    }
    label = f"bklog_index_set_{BINDING['index_id']}_pattern"
    route = f"{label}.__default__"
    params = {
        "space_type": "bkcc",
        "space_id": "2",
        "bk_tenant_id": "system",
        "data_label": label,
        "table_info": [
            {
                "table_id": route,
                "storage_type": "elasticsearch",
                "source_type": "es",
                "cluster_id": target["cluster_id"],
                "index_set": target["query_index"],
                "is_enable": True,
            }
        ],
    }
    models.Space.objects.create(
        bk_tenant_id="system", space_type_id="bkcc", space_id="2", space_code="test", space_name="test"
    )
    mocker.patch.object(SpaceTableIDRedis, "_compose_metric_table_id_detail", return_value={})
    mocker.patch.object(SpaceTableIDRedis, "_compose_bkcc_space_table_ids", return_value={route: {}})
    hashes = {}

    def write(key, values):
        if key == failure_key:
            raise RuntimeError("Redis write failed")
        hashes.setdefault(key, {}).update(values)
        return True

    mocker.patch("metadata.models.space.space_table_id_redis.RedisTools.hmset_to_redis", side_effect=write)
    mocker.patch("metadata.models.space.space_table_id_redis.RedisTools.publish")
    router = BulkCreateOrUpdateLogRouter()
    with pytest.raises(RuntimeError, match="Redis write failed"):
        router.request(params)
    failure_key = None
    router.request(params)
    (resolved_table,) = json.loads(hashes[DATA_LABEL_TO_RESULT_TABLE_KEY][label])
    assert resolved_table == route
    detail = json.loads(hashes[RESULT_TABLE_DETAIL_KEY][resolved_table])
    assert (detail["storage_id"], detail["db"]) == (PATTERN_CLUSTER_ID, PATTERN_INDEX)
    assert route in json.loads(hashes[SPACE_TO_RESULT_TABLE_KEY]["bkcc__2"])
    assert models.ResultTable.objects.filter(bk_tenant_id="system", table_id=route).count() == 1


@pytest.mark.parametrize("mode", ["update_original", "append"])
def test_query_targets_follow_remote_result_binding(clustering_datalink, bkbase, mocker, mode):
    set_config()
    attach_remotely(bkbase)
    result = {"mode": mode}
    table_id, cluster_id = LOG_TABLE_ID, 710101
    if mode == "append":
        table_id, cluster_id = "2_bklog.predict", PATTERN_CLUSTER_ID
        result.update(
            result_table={"kind": "ResultTable", "name": "predict", "namespace": "bklog"},
            es_binding={"kind": "ElasticSearchBinding", "name": "predict-es", "namespace": "bklog"},
        )
        models.ResultTableConfig.objects.create(
            name="predict", namespace="bklog", bk_tenant_id="system", table_id=table_id, bk_biz_id=2
        )
        models.ESStorage.objects.create(
            bk_tenant_id="system",
            table_id=table_id,
            storage_cluster_id=710101,
            index_set="stale-local-index",
            source_type="bkdata",
        )
        bkbase[("ElasticSearchBinding", "predict-es")] = {
            "metadata": {"annotations": {"physical_table_name": "shadowed-by-fixed-alias"}},
            "status": {"phase": "Ok"},
            "spec": {
                "data": result["result_table"],
                "storage": PATTERN_RESOURCE,
                "write_alias": {"Fixed": "actual-predict-write"},
            },
        }
    bkbase["remote_sink"]["spec"]["clustering"]["result"] = result
    params = {"bk_tenant_id": "system", "table_id": LOG_TABLE_ID, "include_query_targets": True}
    targets = GetLogClusteringStatusResource().request(params)["query_targets"]
    assert targets["clustered"]["table_id"] == table_id
    assert targets["clustered"]["cluster_id"] == cluster_id
    assert targets["clustered"]["query_index"] == ("actual-predict-write" if mode == "append" else "actual_raw")
    assert targets["clustered"]["need_add_time"] == (mode == "update_original")
    assert targets["pattern"]["query_index"] == PATTERN_INDEX
    models.Space.objects.create(
        bk_tenant_id="system", space_type_id="bkcc", space_id="2", space_code="test", space_name="test"
    )
    label = "bklog_index_set_42_clustered"
    route = f"{label}.__default__"
    mocker.patch.object(SpaceTableIDRedis, "_compose_metric_table_id_detail", return_value={})
    mocker.patch.object(SpaceTableIDRedis, "_compose_bkcc_space_table_ids", return_value={route: {}})
    writes = mocker.patch("metadata.models.space.space_table_id_redis.RedisTools.hmset_to_redis", return_value=True)
    mocker.patch("metadata.models.space.space_table_id_redis.RedisTools.publish")
    target = targets["clustered"]
    BulkCreateOrUpdateLogRouter().request(
        {
            "bk_tenant_id": "system",
            "space_type": "bkcc",
            "space_id": "2",
            "data_label": label,
            "table_info": [
                {
                    "table_id": route,
                    "cluster_id": target["cluster_id"],
                    "storage_type": target["storage_type"],
                    "source_type": target["source_type"],
                    "index_set": target["query_index"],
                    "options": [
                        {"name": "need_add_time", "value_type": "bool", "value": json.dumps(target["need_add_time"])}
                    ],
                }
            ],
        }
    )
    writes_by_key = {call.args[0]: call.args[1] for call in writes.call_args_list}
    assert json.loads(writes_by_key[DATA_LABEL_TO_RESULT_TABLE_KEY][label]) == [route]
    detail = json.loads(writes_by_key[RESULT_TABLE_DETAIL_KEY][route])
    assert (detail["storage_id"], detail["db"], detail["options"]["need_add_time"]) == (
        cluster_id,
        target["query_index"],
        mode == "update_original",
    )
    assert detail["source_type"] == ("bkdata" if mode == "append" else "log")
    assert all(r["storage_id"] == cluster_id for r in detail["storage_cluster_records"])
    if mode == "append":
        result["result_table"]["name"] = "mismatched"
        status = GetLogClusteringStatusResource().request(params)
        assert status["query_targets"] is None
        assert status["errors"][0]["source"] == "query_targets"


@pytest.mark.parametrize(
    "annotation,rt_spec,expected",
    [
        ("actual-physical-name", {}, "actual-physical-name"),
        (None, {"predefiendResultTableId": "explicit-id", "bizId": 2}, "explicit-id"),
        (None, {"bizId": 2}, "2_raw"),
    ],
)
def test_result_binding_without_write_alias(clustering_datalink, bkbase, annotation, rt_spec, expected):
    set_config()
    attach_remotely(bkbase)
    binding = bkbase[("ElasticSearchBinding", ES_BINDING_REF["name"])]
    del binding["spec"]["write_alias"]
    binding["metadata"]["annotations"] = {"physical_table_name": annotation}
    bkbase[("ResultTable", "raw")] = {"spec": rt_spec}
    params = {"bk_tenant_id": "system", "table_id": LOG_TABLE_ID, "include_query_targets": True}
    target = GetLogClusteringStatusResource().request(params)["query_targets"]["clustered"]
    assert (target["query_index"], target["need_add_time"]) == (expected, False)


def test_daily_binding_uses_result_table_query_timezone(clustering_datalink, bkbase):
    set_config()
    attach_remotely(bkbase)
    bkbase[("ElasticSearchBinding", ES_BINDING_REF["name"])]["spec"]["write_alias"]["TimeBased"]["timezone"] = 8
    params = {"bk_tenant_id": "system", "table_id": LOG_TABLE_ID, "include_query_targets": True}
    # 日界线附近，UTC 的 log 查询不会覆盖东八区写入的次日别名。
    status = GetLogClusteringStatusResource().request(params)
    assert status["query_targets"] is None
    assert status["errors"][0]["retryable"] is False
    assert "query timezone" in status["errors"][0]["message"]
    models.ESStorage.objects.filter(bk_tenant_id="system", table_id=LOG_TABLE_ID).update(source_type="bkdata")
    target = GetLogClusteringStatusResource().request(params)["query_targets"]["clustered"]
    assert (target["source_type"], target["query_index"], target["need_add_time"]) == ("bkdata", "actual_raw", True)


def test_pending_result_binding_waits_without_error(clustering_datalink, bkbase):
    set_config()
    attach_remotely(bkbase)
    bkbase[("ElasticSearchBinding", ES_BINDING_REF["name"])]["status"] = {"phase": "Pending"}
    status = GetLogClusteringStatusResource().request(
        {"bk_tenant_id": "system", "table_id": LOG_TABLE_ID, "include_query_targets": True}
    )
    assert status["query_targets"] is None
    assert status["errors"] == []
    bkbase[("ElasticSearchBinding", ES_BINDING_REF["name"])]["status"] = {"phase": "Failed", "message": "invalid alias"}
    status = GetLogClusteringStatusResource().request(
        {"bk_tenant_id": "system", "table_id": LOG_TABLE_ID, "include_query_targets": True}
    )
    (error,) = status["errors"]
    assert error["retryable"] is False
    assert "invalid alias" in error["message"]


@pytest.mark.parametrize("field", ["kafka_resource", "runtime_cluster", "recovery_resource"])
def test_resource_refs_reject_other_tenant(clustering_datalink, bkbase, field):
    params = build_params()
    ref = params["pattern_store"][field] if field in PATTERN_STORE else params[field]
    ref["tenant"] = "other"
    serializer = SetLogClusteringConfigResource.RequestSerializer(data=params)
    assert not serializer.is_valid()
    assert "cross-tenant" in str(serializer.errors)
    assert not models.LogClusteringSinkConfig.objects.exists()


def test_runtime_cluster_change_applies_databus_and_sink(clustering_datalink, bkbase):
    set_config()
    attach_remotely(bkbase)
    bkbase["remote_databus"]["spec"]["preferCluster"] = {**RUNTIME_CLUSTER, "name": "old-runtime"}
    bkbase["apply_log_datalink"].reset_mock()
    assert set_config()["applied_scope"] == "datalink"
    bkbase["apply_log_datalink"].assert_called_once_with(bk_tenant_id="system", table_id=LOG_TABLE_ID)
    bkbase["apply_data_link"].assert_not_called()


@pytest.mark.parametrize(
    "explicit_id,expected", [(None, "2_shared_patterns"), ("registered-patterns", "registered-patterns")]
)
def test_pattern_target_uses_registered_table_id(clustering_datalink, bkbase, explicit_id, expected):
    set_config()
    attach_remotely(bkbase)
    binding = bkbase[("ElasticSearchBinding", PATTERN_STORE["es_binding"]["name"])]
    binding["metadata"] = {}
    table = bkbase[("ResultTable", PATTERN_STORE["result_table"]["name"])]
    table["spec"]["predefiendResultTableId"] = explicit_id
    status = GetLogClusteringStatusResource().request(
        {"bk_tenant_id": "system", "table_id": LOG_TABLE_ID, "include_query_targets": True}
    )
    target = status["query_targets"]["pattern"]
    assert target["query_index"] == expected
    assert target["cluster_id"] == PATTERN_CLUSTER_ID
    assert target["source_type"] == "es"
    assert target["need_add_time"] is False


@pytest.mark.parametrize("resource", ["result_table", "es_binding"])
def test_pending_pattern_resources_wait_but_failed_resources_report_error(clustering_datalink, bkbase, resource):
    set_config()
    attach_remotely(bkbase)
    ref = PATTERN_STORE[resource]
    obj = bkbase[(ref["kind"], ref["name"])]
    params = {"bk_tenant_id": "system", "table_id": LOG_TABLE_ID, "include_query_targets": True}
    obj["status"] = {"phase": "Pending"}
    status = GetLogClusteringStatusResource().request(params)
    assert status["query_targets"] is None
    assert status["errors"] == []
    obj["status"] = {"phase": "Failed"}
    status = GetLogClusteringStatusResource().request(params)
    assert status["query_targets"] is None
    assert status["errors"][0]["retryable"] is False


@pytest.mark.parametrize(
    "change", ["wrong_table", "other_tenant", "time_alias", "wrong_fixed_alias", "unregistered_cluster"]
)
def test_invalid_pattern_binding_does_not_publish_route(clustering_datalink, bkbase, change):
    set_config()
    attach_remotely(bkbase)
    spec = bkbase[("ElasticSearchBinding", PATTERN_STORE["es_binding"]["name"])]["spec"]
    if change == "wrong_table":
        spec["data"] = {**spec["data"], "name": "wrong"}
    elif change == "other_tenant":
        spec["storage"] = {**spec["storage"], "tenant": "other"}
    elif change == "unregistered_cluster":
        spec["storage"] = {**spec["storage"], "name": "unregistered"}
    elif change == "time_alias":
        spec["write_alias"] = {"TimeBased": {"format": "write_%Y%m%d_patterns"}}
    else:
        spec["write_alias"] = {"Fixed": "wrong-index"}
    status = GetLogClusteringStatusResource().request(
        {"bk_tenant_id": "system", "table_id": LOG_TABLE_ID, "include_query_targets": True}
    )
    assert status["query_targets"] is None
    assert status["errors"][0]["retryable"] is False


def test_runtime_cluster_default_tenant_does_not_reapply_databus(clustering_datalink, bkbase):
    set_config()
    attach_remotely(bkbase)
    bkbase["remote_databus"]["spec"]["preferCluster"]["tenant"] = "system"
    bkbase["apply_log_datalink"].reset_mock()
    assert set_config()["applied_scope"] == "sink_only"
    bkbase["apply_log_datalink"].assert_not_called()
    bkbase["apply_data_link"].assert_called_once()
