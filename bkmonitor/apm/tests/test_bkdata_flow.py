import json
from types import SimpleNamespace
from unittest.mock import mock_open

import pytest

from apm.core.handlers.bk_data.flow import ApmFlow
from apm.core.handlers.bk_data.tail_sampling import TailSamplingFlow
from apm.models import TraceDataSource
from bkmonitor.dataflow.task.apm_tail_sampling import TailSamplingFlinkNode
from bkmonitor.define.global_config import ADVANCED_OPTIONS
from metadata.models import ResultTableOption


def test_resolve_bkdata_biz_id_uses_tenant_default_for_space(settings, mocker):
    settings.ENABLE_MULTI_TENANT_MODE = True
    get_tenant_default_biz_id = mocker.patch(
        "apm.core.handlers.bk_data.flow.get_tenant_default_biz_id", return_value=9527
    )

    result = ApmFlow._resolve_bkdata_biz_id("tenant-a", -100)

    assert result == 9527
    get_tenant_default_biz_id.assert_called_once_with("tenant-a")


def test_resolve_bkdata_biz_id_keeps_single_tenant_behavior(settings):
    settings.ENABLE_MULTI_TENANT_MODE = False
    settings.BK_DATA_BK_BIZ_ID = 2

    assert ApmFlow._resolve_bkdata_biz_id("system", -100) == 2


def test_resolve_bkdata_biz_id_keeps_positive_business(settings, mocker):
    settings.ENABLE_MULTI_TENANT_MODE = True
    get_tenant_default_biz_id = mocker.patch("apm.core.handlers.bk_data.flow.get_tenant_default_biz_id")

    assert ApmFlow._resolve_bkdata_biz_id("tenant-a", 1001) == 1001
    get_tenant_default_biz_id.assert_not_called()


def test_tail_sampling_registers_storage_in_resolved_bkdata_business(settings, mocker):
    settings.APM_APP_BKDATA_TAIL_SAMPLING_PROJECT_ID = 123
    storage = SimpleNamespace(retention=30, storage_cluster_id=1)
    trace_datasource = SimpleNamespace(result_table_id="2_bkapm.trace", storage=storage)
    cluster_info = SimpleNamespace(
        cluster_name="es",
        cluster_id=1,
        consul_config={},
        domain_name="es.example.com",
        password="password",
        port=9300,
        username="username",
    )
    mocker.patch("apm.core.handlers.bk_data.tail_sampling.TraceDataSource.objects.get", return_value=trace_datasource)
    mocker.patch("apm.core.handlers.bk_data.tail_sampling.ClusterInfo.objects.get", return_value=cluster_info)
    mocker.patch("apm.core.handlers.bk_data.tail_sampling.api.bkdata.query_resource_list", return_value=[])
    get_or_create_resource_set = mocker.patch(
        "apm.core.handlers.bk_data.tail_sampling.api.bkdata.get_or_create_resource_set",
        return_value={"resource_set_id": "apm_storage_id_1", "resource_set_name": "apm_storage_es"},
    )
    mocker.patch(
        "apm.core.handlers.bk_data.tail_sampling.api.bkdata.get_resource_set",
        return_value={"authorized_projects": [{"id": 123}]},
    )
    mocker.patch("builtins.open", mock_open(read_data="flink code"))
    mocker.patch.object(ApmFlow, "flow_instance", return_value=object())

    flow = object.__new__(TailSamplingFlow)
    flow.bk_biz_id = -100
    flow.bk_tenant_id = "tenant-a"
    flow.bkdata_bk_biz_id = 9527
    flow.app_name = "demo"
    flow.logger = mocker.Mock()

    flow.flow_instance()

    assert get_or_create_resource_set.call_args.args[0]["bk_biz_id"] == 9527


def test_tail_sampling_v3_flink_code_keeps_output_fields():
    node = TailSamplingFlinkNode(
        source_rt_id="2_bkapm_tail_demo",
        flink_code="  flink code  ",
        name="tail_sampling",
    )

    assert node.code.output_fields == node.output_fields
    assert node.code.code == "flink code"


def test_tail_sampling_v4_settings_are_global_configs():
    assert isinstance(ADVANCED_OPTIONS["ENABLE_APM_TRACE_TAIL_SAMPLING_V4"].default, bool)
    assert isinstance(ADVANCED_OPTIONS["APM_TRACE_TAIL_SAMPLING_V4_KAFKA_CHANNEL"].default, str)
    assert isinstance(ADVANCED_OPTIONS["APM_TRACE_TAIL_SAMPLING_V4_STREAM_CLUSTER"].default, str)


def _build_tail_sampling_v4_flow(settings, mocker, *, flow_id="333"):
    settings.ENABLE_APM_TRACE_TAIL_SAMPLING_V4 = True
    settings.ENABLE_MULTI_TENANT_MODE = False
    settings.APM_APP_BKDATA_TAIL_SAMPLING_PROJECT_ID = 2001
    settings.APM_TRACE_TAIL_SAMPLING_V4_KAFKA_CHANNEL = "default/demo/kafka-demo"
    settings.APM_TRACE_TAIL_SAMPLING_V4_STREAM_CLUSTER = "StreamCluster/demo/stream-demo"
    mocker.patch("builtins.open", mock_open(read_data="flink code"))

    flow = object.__new__(TailSamplingFlow)
    flow.data_id = 10001
    flow.bk_biz_id = 2
    flow.bk_tenant_id = "system"
    flow.bkdata_bk_biz_id = 2
    flow.app_name = "demo"
    flow.config = {"tail_percentage": 25, "tail_conditions": [{"key": "span_name", "method": "eq", "value": ["x"]}]}
    flow.flow = SimpleNamespace(
        flow_id=flow_id,
        project_id="2001" if flow_id else None,
        deploy_bk_biz_id=2,
        databus_clean_id=None,
        databus_clean_config={},
        databus_clean_result_table_id=None,
    )
    flow.application = SimpleNamespace(create_user="demo_user")
    flow.logger = mocker.Mock()
    return flow


def test_tail_sampling_v4_flow_matches_verified_contract(settings, mocker):
    flow = _build_tail_sampling_v4_flow(settings, mocker, flow_id=None)
    source = {
        "tenant": "default",
        "namespace": "bklog",
        "name": "bkapm_tail_10001_tail_v4",
        "result_table_id": "2_bkapm_tail_10001_tail_v4",
    }
    storage = {
        "tenant": "default",
        "namespace": "bklog",
        "name": "es-demo-cluster",
        "retention": 3,
        "replicas": 1,
        "timezone": 0,
        "table_name": "2_bkapm_trace_demo",
    }
    config = flow.compose_v4_flow_config(source=source, storage=storage)

    assert config["metadata"] == {
        "tenant": "default",
        "namespace": "project_v3_2001",
        "name": "bkapm_tail_sampling_10001_tail_v4",
        "labels": {},
        "annotations": {},
    }
    source_node, flink_node, es_node = config["spec"]["nodes"]
    assert source_node["data"] == {
        "kind": "ResultTable",
        "tenant": "default",
        "namespace": "bklog",
        "name": "bkapm_tail_10001_tail_v4",
    }
    programming_args = json.loads(flink_node["programming_args"])
    assert programming_args["input_table_id"] == "2_bkapm_tail_10001_tail_v4"
    assert programming_args["random_sampling_ratio"] == 25
    expected_fields = TailSamplingFlinkNode(
        source_rt_id="2_bkapm_tail_10001_tail_v4", flink_code="", name="tail_sampling"
    ).output_fields
    assert [(field["field_name"], field["field_type"]) for field in flink_node["output_fields"]] == [
        (field.field_name, field.field_type) for field in expected_fields
    ]
    assert es_node["storage"] == {
        "kind": "ElasticSearch",
        "tenant": "default",
        "namespace": "bklog",
        "name": "es-demo-cluster",
    }
    assert es_node["write_alias"]["TimeBased"]["format"] == "write_%Y%m%d_2_bkapm_trace_demo"
    assert config["spec"]["operation_config"]["stream_sql_deploy_config"]["cluster"] == (
        "StreamCluster/demo/stream-demo"
    )
    assert config["spec"]["maintainers"] == ["demo_user"]

    settings.APM_TRACE_TAIL_SAMPLING_V4_STREAM_CLUSTER = "StreamCluster/demo/stream-other"
    updated_config = flow.compose_v4_flow_config(source=source, storage=storage)
    assert updated_config["spec"]["operation_config"]["stream_sql_deploy_config"]["cluster"] == (
        "StreamCluster/demo/stream-other"
    )


def test_tail_sampling_native_source_matches_verified_contract(settings, mocker):
    flow = _build_tail_sampling_v4_flow(settings, mocker, flow_id=None)
    trace = SimpleNamespace(
        bk_data_id=10001,
        bk_biz_id=2,
        result_table_id="2_bkapm.trace_demo",
        is_bkbase_v4_link=lambda: True,
    )
    data_id_config = SimpleNamespace(
        namespace="bklog",
        name="bkm_2_bkapm_trace_demo",
    )
    data_id_configs = mocker.patch("apm.core.handlers.bk_data.tail_sampling.DataIdConfig.objects.filter")
    data_id_configs.return_value.exclude.return_value.order_by.return_value.first.return_value = data_id_config
    get_data_link = mocker.patch(
        "apm.core.handlers.bk_data.tail_sampling.api.bkdata.get_data_link",
    )

    source, configs = flow._compose_v4_tail_source(trace)

    data_id_configs.assert_called_once_with(bk_tenant_id="system", namespace="bklog", bk_data_id=10001)
    get_data_link.assert_not_called()
    assert flow._v4_flow_name() == "bkapm_tail_sampling_10001_tail_v4"
    assert [config["kind"] for config in configs] == ["ResultTable", "ChannelBinding", "Databus"]
    assert [config["metadata"]["labels"] for config in configs] == [{"bk_biz_id": "2"}] * 3
    assert source == {
        "kind": "ResultTable",
        "tenant": "default",
        "namespace": "bklog",
        "name": "bkapm_tail_10001_tail_v4",
        "result_table_id": "2_bkapm_tail_10001_tail_v4",
    }
    assert "kind" not in configs[0]["metadata"]
    assert configs[1]["spec"]["channel"] == {
        "kind": "KafkaChannel",
        "tenant": "default",
        "namespace": "demo",
        "name": "kafka-demo",
    }
    assert configs[2]["metadata"]["name"] == "bkapm_tail_10001_tail_v4"
    assert configs[2]["spec"]["autoOffsetReset"] == "latest"
    assert [rule["output_id"] for rule in configs[2]["spec"]["transforms"][0]["rules"]] == [
        "mid1",
        "items",
        "mid",
        "span_id",
        "trace_id",
        "span_info",
        "datetime",
    ]


def test_tail_sampling_native_source_uses_monitor_tenant_but_configured_kafka_channel(settings, mocker):
    flow = _build_tail_sampling_v4_flow(settings, mocker, flow_id=None)
    settings.ENABLE_MULTI_TENANT_MODE = True
    flow.bk_tenant_id = "tenant-a"
    trace = SimpleNamespace(bk_data_id=10001, is_bkbase_v4_link=lambda: True)
    data_id_config = SimpleNamespace(
        namespace="bklog",
        name="bkm_2_bkapm_trace_demo",
    )
    data_id_configs = mocker.patch("apm.core.handlers.bk_data.tail_sampling.DataIdConfig.objects.filter")
    data_id_configs.return_value.exclude.return_value.order_by.return_value.first.return_value = data_id_config

    source, configs = flow._compose_v4_tail_source(trace)

    data_id_configs.assert_called_once_with(bk_tenant_id="tenant-a", namespace="bklog", bk_data_id=10001)
    assert source["tenant"] == "tenant-a"
    assert configs[0]["metadata"]["tenant"] == "tenant-a"
    assert configs[1]["spec"]["data"]["tenant"] == "tenant-a"
    assert configs[1]["spec"]["channel"] == {
        "kind": "KafkaChannel",
        "tenant": "default",
        "namespace": "demo",
        "name": "kafka-demo",
    }
    assert configs[2]["metadata"]["tenant"] == "tenant-a"


def _remote_tail_flow(
    *,
    flow_name="flow_v3_333",
    source_namespace="default_2",
    source_name="c_2_bkapm_tail_demo",
    input_table_id="2_bkapm_tail_demo",
):
    output_table_id = f"{input_table_id}_output"
    return {
        "kind": "Flow",
        "metadata": {
            "tenant": "default",
            "namespace": "project_v3_2001",
            "name": flow_name,
            "labels": {"owner": "bkbase"},
            "annotations": {"migration": "true"},
            "version": 123,
        },
        "spec": {
            "nodes": [
                {
                    "kind": "StreamSourceNode",
                    "name": "existing-source",
                    "data": {
                        "kind": "ResultTable",
                        "tenant": "default",
                        "namespace": source_namespace,
                        "name": source_name,
                    },
                },
                {
                    "kind": "FlinkCodeNode",
                    "name": "existing-flink",
                    "inputs": ["existing-source"],
                    "output": output_table_id,
                    "programming_args": json.dumps(
                        {
                            "input_table_id": input_table_id,
                            "output_table_id": output_table_id,
                            "random_sampling_ratio": 100,
                            "sampling_conditions": [],
                            "bkbase_extra": "keep",
                        }
                    ),
                    "code": "deployed Java code",
                },
                {
                    "kind": "EsStorageNode",
                    "name": "existing-es",
                    "input": "existing-flink",
                    "storage": {
                        "kind": "ElasticSearch",
                        "tenant": "default",
                        "namespace": "default_2",
                        "name": "es-storage-demo",
                    },
                    "write_alias": {"TimeBased": {"format": "write_%Y%m%d_2_bkapm_trace_demo", "timezone": 0}},
                },
            ],
            "operation_config": {"start_position": "continue"},
            "desired_status": "running",
        },
        "status": {"phase": "Ok"},
    }


def test_tail_sampling_existing_flow_reads_remote_refs_without_guessing_namespace(settings, mocker):
    flow = _build_tail_sampling_v4_flow(settings, mocker)
    flow.flow.databus_clean_result_table_id = "2_bkapm_tail_demo"
    remote = _remote_tail_flow()
    remote["spec"]["desired_status"] = "stopped"
    get_data_link = mocker.patch(
        "apm.core.handlers.bk_data.tail_sampling.api.bkdata.get_data_link", return_value=remote
    )
    apply_resources = mocker.patch.object(flow, "_apply_v4_resources", return_value={"Flow": {}})
    create_source = mocker.patch.object(flow, "_compose_v4_tail_source")
    resolve_storage = mocker.patch.object(flow, "_resolve_v4_es_storage")

    flow._update_existing_v4_flow()

    get_data_link.assert_called_once_with(
        bk_tenant_id="system", kind="flows", namespace="project_v3_2001", name="flow_v3_333"
    )
    create_source.assert_not_called()
    resolve_storage.assert_not_called()
    applied = apply_resources.call_args.args[0]
    assert len(applied) == 1
    assert applied[0]["kind"] == "Flow"
    assert applied[0]["metadata"] == {
        key: remote["metadata"][key] for key in ("tenant", "namespace", "name", "labels", "annotations")
    }
    assert applied[0]["spec"]["nodes"][0]["data"]["namespace"] == "default_2"
    assert applied[0]["spec"]["nodes"][2] == remote["spec"]["nodes"][2]
    args = json.loads(applied[0]["spec"]["nodes"][1]["programming_args"])
    assert args["random_sampling_ratio"] == 25
    assert args["sampling_conditions"] == [{"key": "span_name", "method": "eq", "value": ["x"]}]
    assert args["bkbase_extra"] == "keep"
    assert applied[0]["spec"]["nodes"][1]["code"] == "deployed Java code"
    assert applied[0]["spec"]["desired_status"] == "running"
    assert json.loads(remote["spec"]["nodes"][1]["programming_args"])["random_sampling_ratio"] == 100
    assert remote["spec"]["desired_status"] == "stopped"


def test_tail_sampling_existing_native_v4_flow_reuses_its_bklog_source(settings, mocker):
    flow = _build_tail_sampling_v4_flow(settings, mocker, flow_id="bkapm_tail_sampling_10001_tail_v4")
    flow.flow.databus_clean_result_table_id = "2_bkapm_tail_10001_tail_v4"
    remote = _remote_tail_flow(
        flow_name="bkapm_tail_sampling_10001_tail_v4",
        source_namespace="bklog",
        source_name="bkapm_tail_10001_tail_v4",
        input_table_id="2_bkapm_tail_10001_tail_v4",
    )
    get_data_link = mocker.patch(
        "apm.core.handlers.bk_data.tail_sampling.api.bkdata.get_data_link", return_value=remote
    )
    apply_resources = mocker.patch.object(flow, "_apply_v4_resources", return_value={"Flow": {}})

    flow._update_existing_v4_flow()

    get_data_link.assert_called_once_with(
        bk_tenant_id="system",
        kind="flows",
        namespace="project_v3_2001",
        name="bkapm_tail_sampling_10001_tail_v4",
    )
    assert apply_resources.call_args.args[0][0]["spec"]["nodes"][0]["data"]["namespace"] == "bklog"


def test_tail_sampling_existing_flow_pending_exits_without_apply(settings, mocker):
    flow = _build_tail_sampling_v4_flow(settings, mocker)
    flow.flow.databus_clean_result_table_id = "2_bkapm_tail_demo"
    remote = _remote_tail_flow()
    remote["status"]["phase"] = "Pending"
    mocker.patch("apm.core.handlers.bk_data.tail_sampling.api.bkdata.get_data_link", return_value=remote)
    apply_resources = mocker.patch.object(flow, "_apply_v4_resources")

    with pytest.raises(ValueError, match="状态为 Pending"):
        flow._update_existing_v4_flow()

    apply_resources.assert_not_called()


def test_tail_sampling_v4_es_storage_uses_native_link_resource(settings, mocker):
    flow = _build_tail_sampling_v4_flow(settings, mocker)
    trace = SimpleNamespace(
        result_table_id="2_bkapm.trace_demo",
        storage=SimpleNamespace(
            time_zone=0, retention=3, storage_cluster=SimpleNamespace(cluster_name="es-demo-cluster")
        ),
    )
    query_v3_resources = mocker.patch("apm.core.handlers.bk_data.tail_sampling.api.bkdata.query_resource_list")

    storage = flow._resolve_v4_es_storage(trace)

    assert storage == {
        "tenant": "default",
        "namespace": "bklog",
        "name": "es-demo-cluster",
        "retention": 3,
        "replicas": 1,
        "timezone": 0,
        "table_name": "2_bkapm_trace_demo",
    }
    query_v3_resources.assert_not_called()


def test_tail_sampling_v4_resources_use_one_apply(settings, mocker):
    flow = _build_tail_sampling_v4_flow(settings, mocker)
    configs = [
        {"kind": kind, "metadata": {"tenant": "default", "namespace": "ns", "name": kind.lower()}}
        for kind in ("ResultTable", "ChannelBinding", "Databus", "Flow")
    ]
    apply_data_link = mocker.patch("apm.core.handlers.bk_data.tail_sampling.api.bkdata.apply_data_link")
    wait_resource = mocker.patch.object(flow, "_wait_resource_ok", side_effect=[{}, {}, {}, {}])

    flow._apply_v4_resources(configs)

    apply_data_link.assert_called_once_with(bk_tenant_id="system", config=configs)
    assert [call.args[0] for call in wait_resource.call_args_list] == [
        "resulttables",
        "channelbindings",
        "databuses",
        "flows",
    ]


def test_tail_sampling_v4_switch_disabled_uses_v3(settings, mocker):
    flow = _build_tail_sampling_v4_flow(settings, mocker)
    settings.ENABLE_APM_TRACE_TAIL_SAMPLING_V4 = False
    start_v3 = mocker.patch.object(ApmFlow, "start", return_value="v3")
    start_v4 = mocker.patch.object(flow, "_start_v4")

    assert flow.start() == "v3"
    start_v3.assert_called_once_with()
    start_v4.assert_not_called()


def test_tail_sampling_v4_switch_enabled_uses_v4(settings, mocker):
    flow = _build_tail_sampling_v4_flow(settings, mocker)
    start_v3 = mocker.patch.object(ApmFlow, "start")
    start_v4 = mocker.patch.object(flow, "_start_v4", return_value="v4")

    assert flow.start() == "v4"
    start_v3.assert_not_called()
    start_v4.assert_called_once_with()


def test_tail_sampling_does_not_cut_direct_link_when_apply_fails(settings, mocker):
    flow = _build_tail_sampling_v4_flow(settings, mocker, flow_id=None)
    trace = SimpleNamespace()
    mocker.patch("apm.core.handlers.bk_data.tail_sampling.TraceDataSource.objects.get", return_value=trace)
    mocker.patch.object(
        flow,
        "_compose_v4_tail_source",
        return_value=({"tenant": "default"}, [{"kind": "ResultTable"}]),
    )
    mocker.patch.object(flow, "_resolve_v4_es_storage", return_value={})
    mocker.patch.object(
        flow,
        "compose_v4_flow_config",
        return_value={"kind": "Flow", "metadata": {"name": "tail-flow"}},
    )
    mocker.patch.object(flow, "_apply_v4_resources", side_effect=ValueError("apply failed"))
    disable_direct = mocker.patch.object(flow, "_disable_direct_trace_datalink")
    mocker.patch.object(flow, "_raise_exc", side_effect=ValueError("apply failed"))

    with pytest.raises(ValueError, match="apply failed"):
        flow.start()

    disable_direct.assert_not_called()


def test_tail_sampling_cuts_direct_link_after_applied_resources_are_ok(settings, mocker):
    flow = _build_tail_sampling_v4_flow(settings, mocker, flow_id=None)
    trace = SimpleNamespace(bk_data_id=10001)
    mocker.patch("apm.core.handlers.bk_data.tail_sampling.TraceDataSource.objects.get", return_value=trace)
    mocker.patch.object(
        flow,
        "_compose_v4_tail_source",
        return_value=(
            {
                "tenant": "default",
                "name": "bkapm_tail_10001_tail_v4",
                "result_table_id": "2_bkapm_tail_10001_tail_v4",
            },
            [
                {"kind": "ResultTable", "spec": {"bizId": 2}},
                {"kind": "Databus", "metadata": {"name": "bkapm_tail_10001_tail_v4"}},
            ],
        ),
    )
    mocker.patch.object(flow, "_resolve_v4_es_storage", return_value={})
    flow_config = {"kind": "Flow", "metadata": {"name": "bkapm_tail_sampling_10001_tail_v4"}}
    mocker.patch.object(flow, "compose_v4_flow_config", return_value=flow_config)
    apply_resources = mocker.patch.object(flow, "_apply_v4_resources", return_value={"Flow": {}})
    update_field = mocker.patch.object(flow, "_update_field")
    disable_direct = mocker.patch.object(flow, "_disable_direct_trace_datalink")
    disable_direct.side_effect = lambda _trace: update_field.assert_not_called()

    flow.start()

    apply_resources.assert_called_once_with(
        [
            {"kind": "ResultTable", "spec": {"bizId": 2}},
            {"kind": "Databus", "metadata": {"name": "bkapm_tail_10001_tail_v4"}},
            flow_config,
        ]
    )
    disable_direct.assert_called_once_with(trace)
    assert update_field.call_args_list[0].args[0]["databus_clean_config"] == {
        "kind": "Databus",
        "metadata": {"name": "bkapm_tail_10001_tail_v4"},
    }
    assert "deploy_bk_biz_id" not in update_field.call_args_list[0].args[0]


def test_tail_sampling_retries_new_flow_if_direct_link_cutover_fails(settings, mocker):
    flow = _build_tail_sampling_v4_flow(settings, mocker, flow_id=None)
    trace = SimpleNamespace(bk_data_id=10001)
    mocker.patch("apm.core.handlers.bk_data.tail_sampling.TraceDataSource.objects.get", return_value=trace)
    mocker.patch.object(
        flow,
        "_compose_v4_tail_source",
        return_value=(
            {"name": "bkapm_tail_10001_tail_v4", "result_table_id": "2_bkapm_tail_10001_tail_v4"},
            [{"kind": "Databus"}],
        ),
    )
    mocker.patch.object(flow, "_resolve_v4_es_storage", return_value={})
    mocker.patch.object(
        flow,
        "compose_v4_flow_config",
        return_value={"kind": "Flow", "metadata": {"name": "bkapm_tail_sampling_10001_tail_v4"}},
    )
    mocker.patch.object(flow, "_apply_v4_resources", return_value={"Flow": {}})
    mocker.patch.object(flow, "_disable_direct_trace_datalink", side_effect=ValueError("cutover failed"))
    update_field = mocker.patch.object(flow, "_update_field")
    mocker.patch.object(flow, "_raise_exc", side_effect=ValueError("cutover failed"))

    with pytest.raises(ValueError, match="cutover failed"):
        flow.start()

    update_field.assert_not_called()


def test_tail_sampling_existing_flow_updates_only_flow_without_cutover(settings, mocker):
    flow = _build_tail_sampling_v4_flow(settings, mocker, flow_id="bkapm_tail_sampling_10001_tail_v4")
    flow.flow.databus_clean_result_table_id = "2_bkapm_tail_demo"
    get_trace = mocker.patch("apm.core.handlers.bk_data.tail_sampling.TraceDataSource.objects.get")
    update_existing = mocker.patch.object(flow, "_update_existing_v4_flow")
    create_new = mocker.patch.object(flow, "_create_v4_flow")
    update_field = mocker.patch.object(flow, "_update_field")
    disable_direct = mocker.patch.object(flow, "_disable_direct_trace_datalink")

    flow.start()

    update_existing.assert_called_once_with()
    create_new.assert_not_called()
    get_trace.assert_not_called()
    disable_direct.assert_not_called()
    assert len(update_field.call_args_list) == 1
    assert "databus_clean_config" not in update_field.call_args_list[0].args[0]


def test_tail_sampling_existing_rt_without_flow_id_uses_generated_flow_name(settings, mocker):
    flow = _build_tail_sampling_v4_flow(settings, mocker)
    flow.flow.flow_id = None
    flow.flow.databus_clean_result_table_id = "2_bkapm_tail_demo"
    remote = _remote_tail_flow(flow_name="bkapm_tail_sampling_10001_tail_v4")
    get_data_link = mocker.patch(
        "apm.core.handlers.bk_data.tail_sampling.api.bkdata.get_data_link", return_value=remote
    )
    apply_resources = mocker.patch.object(flow, "_apply_v4_resources", return_value={"Flow": {}})

    flow._update_existing_v4_flow()

    get_data_link.assert_called_once_with(
        bk_tenant_id="system",
        kind="flows",
        namespace="project_v3_2001",
        name="bkapm_tail_sampling_10001_tail_v4",
    )
    assert apply_resources.call_args.args[0][0]["metadata"]["name"] == "bkapm_tail_sampling_10001_tail_v4"


def test_trace_result_table_option_disables_direct_link_when_tail_sampling_is_enabled(mocker):
    trace = object.__new__(TraceDataSource)
    trace.bk_biz_id = 2
    trace.app_name = "demo"
    flow_query = mocker.patch("apm.models.datasource.BkdataFlowConfig.objects.filter")
    flow_query.return_value.exclude.return_value.exclude.return_value.exists.return_value = True

    option = trace._build_result_table_option(use_bkbase_v4_link=True)

    assert option[ResultTableOption.OPTION_ENABLE_V4_LOG_DATA_LINK] is False
    assert ResultTableOption.OPTION_V4_LOG_DATA_LINK not in option
    flow_query.assert_called_once_with(
        bk_biz_id=2,
        app_name="demo",
        flow_type="tail_sampling",
        flow_id__isnull=False,
        databus_clean_result_table_id__isnull=False,
    )


def test_trace_result_table_option_keeps_direct_link_without_tail_sampling(mocker):
    trace = object.__new__(TraceDataSource)
    trace.bk_biz_id = 2
    trace.app_name = "demo"
    flow_query = mocker.patch("apm.models.datasource.BkdataFlowConfig.objects.filter")
    flow_query.return_value.exclude.return_value.exclude.return_value.exists.return_value = False
    build_option = mocker.patch.object(trace, "_build_v4_datalink_option", return_value={"name": "direct"})

    option = trace._build_result_table_option(use_bkbase_v4_link=True)

    assert option[ResultTableOption.OPTION_ENABLE_V4_LOG_DATA_LINK] is True
    assert option[ResultTableOption.OPTION_V4_LOG_DATA_LINK] == {"name": "direct"}
    build_option.assert_called_once_with()
