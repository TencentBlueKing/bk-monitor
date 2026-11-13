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
    PATTERN_STORE,
    PATTERN_INDEX,
    RUNTIME_CLUSTER,
    RECOVERY_RESOURCE,
    create_log_datalink,
)

pytestmark = pytest.mark.django_db(databases="__all__")

PATTERN_CLUSTER_ID = 710103
PATTERN_TARGET = {"table_id": f"2_bklog.{BINDING['index_id']}_pattern", "cluster_id": PATTERN_CLUSTER_ID}
CLUSTERED_TARGET = {"table_id": f"2_bklog.{BINDING['index_id']}_clustered", "cluster_id": PATTERN_CLUSTER_ID}


@pytest.fixture(autouse=True)
def single_tenant(settings):
    settings.ENABLE_MULTI_TENANT_MODE = False


@pytest.fixture
def clustering_datalink(mocker):
    mocker.patch("bkmonitor.utils.tenant.get_tenant_default_biz_id", return_value=2)
    datalink, data_source = create_log_datalink()
    models.ResultTableConfig.objects.create(
        table_id=LOG_TABLE_ID,
        bk_tenant_id="system",
        namespace=datalink.namespace,
        data_link_name=datalink.data_link_name,
        name=datalink.data_link_name,
        data_type="log",
        bk_biz_id=2,
    )
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
        sink.pattern_store = {**sink.pattern_store, **copy.deepcopy(PATTERN_STORE)}
        sink.save(update_fields=["pattern_store"])
        return []

    mocker.patch("metadata.models.data_link.log_clustering.prepare_clustering_stores", side_effect=prepare)
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
        "pattern_store": dict(PATTERN_TARGET),
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
    models.ESStorage.objects.create(
        bk_tenant_id="system",
        table_id="bklog.pattern",
        storage_cluster_id=PATTERN_CLUSTER_ID,
        index_set=PATTERN_INDEX,
        source_type="log",
        need_create_index=True,
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


def test_result_mode_is_kept_unless_requested(clustering_datalink, bkbase):
    set_config(result_mode="append", result_store=CLUSTERED_TARGET)
    assert get_sink().result == {"mode": "append", **CLUSTERED_TARGET}
    # 日志平台只在首次开启时传入写入模式，重试和更新不传时沿用。
    set_config()
    assert get_sink().result == {"mode": "append", **CLUSTERED_TARGET}


def test_store_tables_are_declared_by_caller(clustering_datalink, bkbase):
    set_config()
    sink = get_sink()
    assert sink.pattern_store == {**PATTERN_TARGET, **PATTERN_STORE}
    assert sink.result == {"mode": "update_original"}
    # 调用方声明新集群时覆盖登记值，已准备的资源引用保留到重新准备。
    set_config(pattern_store={**PATTERN_TARGET, "cluster_id": 710101})
    assert get_sink().pattern_store == {**PATTERN_TARGET, "cluster_id": 710101, **PATTERN_STORE}


@pytest.mark.parametrize(
    "overrides, field",
    [({"pattern_store": None}, "pattern_store"), ({"result_mode": "append"}, "result_store")],
    ids=["pattern", "append-result"],
)
def test_store_tables_are_required(clustering_datalink, bkbase, overrides, field):
    params = build_params(**overrides)
    params = {key: value for key, value in params.items() if value is not None}
    serializer = SetLogClusteringConfigResource.RequestSerializer(data=params)
    assert not serializer.is_valid()
    assert field in serializer.errors
    assert not models.LogClusteringSinkConfig.objects.exists()


def test_binding_is_forwarded_as_is(clustering_datalink, bkbase):
    binding = {**copy.deepcopy(BINDING), "future_field": {"keep": True}}
    set_config(binding=binding)
    assert get_sink().binding == binding


def test_binding_requires_index_id(clustering_datalink, bkbase):
    binding = copy.deepcopy(BINDING)
    binding.pop("index_id")
    with pytest.raises(CustomException):
        set_config(binding=binding)
    assert not models.LogClusteringSinkConfig.objects.exists()


def test_set_on_attached_sink_only_applies_sink(clustering_datalink, bkbase):
    set_config()
    attach_remotely(bkbase)
    binding = copy.deepcopy(BINDING)
    binding["log_filter"] = [{"key": "level", "method": "eq", "value": ["INFO"], "condition": ""}]

    binding["input_mapping"]["log"] = "message"
    result = set_config(binding=binding)

    assert result["applied_scope"] == "sink_only"
    assert bkbase["apply_log_datalink"].call_count == 1
    (configs,), _ = bkbase["apply_data_link"].call_args
    assert [config["kind"] for config in configs] == ["ResultTable", "LogClusteringSink"]
    assert configs[-1]["spec"]["clustering"]["binding"]["log_filter"] == binding["log_filter"]
    assert configs[-1]["spec"]["clustering"]["binding"]["input_mapping"] == binding["input_mapping"]
    assert configs[-1]["spec"]["raw_sink"] == ES_BINDING_REF


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


def test_filter_values_keep_surrounding_whitespace(clustering_datalink, bkbase):
    binding = copy.deepcopy(BINDING)
    binding["log_filter"] = [
        {"key": "level", "method": "eq", "value": [" ERROR ", " ", "\t"], "condition": ""},
    ]

    set_config(binding=binding)

    assert get_sink().binding["log_filter"][0]["value"] == [" ERROR ", " ", "\t"]


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
    assert configs[-1]["spec"]["clustering"]["binding"]["log_filter"] == [rule]


def test_retry_after_failed_apply_reapplies_whole_datalink(clustering_datalink, bkbase):
    bkbase["apply_log_datalink"].side_effect = RuntimeError("bkbase apply failed")
    with pytest.raises(RuntimeError):
        set_config()

    bkbase["apply_log_datalink"].side_effect = None
    result = set_config()

    assert result["applied_scope"] == "datalink"
    assert result["sink"]["name"] == get_sink().name
    assert bkbase["apply_log_datalink"].call_count == 2


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


def test_retry_resends_enable_switch_without_changing_binding(clustering_datalink, bkbase):
    set_config()
    attach_remotely(bkbase)
    bkbase["apply_data_link"].side_effect = RuntimeError("bkbase apply failed")
    with pytest.raises(RuntimeError):
        operate("disable")

    first_request = copy.deepcopy(bkbase["apply_data_link"].call_args.args)
    bkbase["apply_data_link"].side_effect = None
    result = operate("disable")

    assert result == {"action": "disable", "attached": True}
    assert bkbase["apply_data_link"].call_args.args == first_request
    assert bkbase["apply_data_link"].call_count == 2


def test_operate_without_config_is_rejected(clustering_datalink, bkbase):
    with pytest.raises(ValidationError, match="no log clustering config"):
        operate("disable")
    bkbase["apply_data_link"].assert_not_called()


def test_status_without_config_reports_not_configured(clustering_datalink, bkbase):
    assert get_status() == {"configured": False}


def test_filter_update_preserves_remote_disabled_state(clustering_datalink, bkbase):
    set_config()
    attach_remotely(bkbase)
    bkbase["remote_sink"]["spec"]["clustering"]["enabled"] = False
    binding = copy.deepcopy(BINDING)
    binding["log_filter"] = [{"key": "level", "method": "eq", "value": ["INFO"], "condition": ""}]

    set_config(binding=binding)

    (configs,), _ = bkbase["apply_data_link"].call_args
    assert configs[-1]["spec"]["clustering"]["enabled"] is False
    assert configs[-1]["spec"]["clustering"]["binding"]["log_filter"] == binding["log_filter"]
    assert bkbase["apply_log_datalink"].call_count == 1


def test_status_summarizes_link_state(clustering_datalink, bkbase):
    set_config()
    attach_remotely(bkbase)
    bkbase["remote_databus"]["status"] = {"phase": "Ok"}
    bkbase["remote_sink"]["spec"]["clustering"]["enabled"] = True

    result = get_status()

    sink = get_sink()
    assert result == {
        "configured": True,
        "attached": True,
        "sink": {"tenant": "system", "namespace": "bklog", "name": sink.name},
        "databus": {"tenant": "system", "namespace": "bklog", "name": LOG_DATA_LINK_NAME},
        "enabled": True,
        "sink_phase": "Ok",
        "ready": True,
        "detached": False,
        "clustering_status": {"configuration_applied": True, "clustering_closed": False},
        "errors": [],
    }

    bkbase["remote_databus"]["spec"]["sinks"] = [ES_BINDING_REF]
    result = get_status()
    assert (result["ready"], result["detached"]) == (False, True)


@pytest.mark.parametrize("sink_status", [None, {"phase": "Pending"}, {"phase": "Ok", "message": "running"}])
def test_status_waits_until_sink_ok(clustering_datalink, bkbase, sink_status):
    set_config()
    attach_remotely(bkbase)
    bkbase["remote_databus"]["status"] = {"phase": "Ok"}
    bkbase["remote_sink"]["status"] = sink_status

    result = get_status()

    assert result["ready"] is (sink_status is not None and sink_status["phase"] == "Ok")
    # 普通文本 message 不是停用收尾回执。
    assert result["clustering_status"] is None
    assert result["errors"] == []


def test_status_keeps_databus_when_sink_query_fails(clustering_datalink, bkbase, mocker):
    set_config()
    attach_remotely(bkbase)
    databus = {**bkbase["remote_databus"], "spec": {"sinks": [ES_BINDING_REF]}, "status": {"phase": "Ok"}}

    def fetch(kind, name, namespace):
        if kind == "LogClusteringSink":
            raise RuntimeError("resource unavailable")
        return databus

    mocker.patch("metadata.models.DataLink.get_existing_component_config", side_effect=fetch)
    result = get_status()

    assert (result["ready"], result["detached"]) == (False, True)
    assert result["errors"] == [{"source": "sink_resource", "message": "resource unavailable"}]


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


def test_runtime_cluster_default_tenant_does_not_reapply_databus(clustering_datalink, bkbase):
    set_config()
    attach_remotely(bkbase)
    bkbase["remote_databus"]["spec"]["preferCluster"]["tenant"] = "system"
    bkbase["apply_log_datalink"].reset_mock()
    assert set_config()["applied_scope"] == "sink_only"
    bkbase["apply_log_datalink"].assert_not_called()
    bkbase["apply_data_link"].assert_called_once()
