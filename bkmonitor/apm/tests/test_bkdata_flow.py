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
        "storage": {"kind": "ElasticSearch", "tenant": "default", "namespace": "bklog", "name": "es-demo-cluster"},
        "write_alias": {"TimeBased": {"format": "write_%Y%m%d_2_bkapm_trace_demo", "timezone": 0}},
        "unique_field_list": ["trace_id", "span_id", "parent_span_id", "start_time", "end_time", "span_name"],
        "retention": 3,
        "replicas": 1,
    }
    config = flow.compose_v4_flow_config(source=source, storage=storage)

    assert config["metadata"] == {
        "tenant": "default",
        "namespace": "project_v3_2001",
        "name": "bkapm_tail_sampling_10001_tail_v4",
        "labels": {},
        "annotations": {"task_stopped": "false"},
    }
    # BKBase 不保存 desired_status，启停只走 annotations.task_stopped
    assert "desired_status" not in config["spec"]
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
    assert es_node["write_alias"] == {"TimeBased": {"format": "write_%Y%m%d_2_bkapm_trace_demo", "timezone": 0}}
    assert es_node["expires"] == "3d"
    assert es_node["unique_field_list"] == storage["unique_field_list"]
    assert config["spec"]["operation_config"]["stream_sql_deploy_config"]["cluster"] == (
        "StreamCluster/demo/stream-demo"
    )
    assert config["spec"]["maintainers"] == ["demo_user"]
    assert config["spec"]["alias"] == "bkapm_tail_sampling_10001_tail_v4"

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
    # 运行中的 Flow：先带新参数停止，再启动，让 Flink 作业按新参数重新提交
    stop_configs, start_configs = [call.args[0] for call in apply_resources.call_args_list]
    assert len(stop_configs) == len(start_configs) == 1
    stop, start = stop_configs[0], start_configs[0]
    assert stop["kind"] == start["kind"] == "Flow"
    assert stop["metadata"]["annotations"] == {"migration": "true", "task_stopped": "true"}
    assert start["metadata"]["annotations"] == {"migration": "true", "task_stopped": "false"}
    assert {key: start["metadata"][key] for key in ("tenant", "namespace", "name", "labels")} == {
        key: remote["metadata"][key] for key in ("tenant", "namespace", "name", "labels")
    }
    assert "version" not in start["metadata"]
    assert stop["spec"] == start["spec"]
    assert start["spec"]["nodes"][0]["data"]["namespace"] == "default_2"
    assert start["spec"]["nodes"][2] == remote["spec"]["nodes"][2]
    args = json.loads(start["spec"]["nodes"][1]["programming_args"])
    assert args["random_sampling_ratio"] == 25
    assert args["sampling_conditions"] == [{"key": "span_name", "method": "eq", "value": ["x"]}]
    assert args["bkbase_extra"] == "keep"
    assert start["spec"]["nodes"][1]["code"] == "deployed Java code"
    assert "desired_status" not in start["spec"]
    # 远端 alias 为空时补 Flow 名称，绕过 BKBase 更新不下发的问题
    assert start["spec"]["alias"] == "flow_v3_333"
    # 不修改远端读回的对象
    assert json.loads(remote["spec"]["nodes"][1]["programming_args"])["random_sampling_ratio"] == 100
    assert remote["spec"]["desired_status"] == "stopped"
    assert "alias" not in remote["spec"]
    assert remote["metadata"]["annotations"] == {"migration": "true"}


def test_tail_sampling_existing_flow_skips_apply_when_args_unchanged(settings, mocker):
    flow = _build_tail_sampling_v4_flow(settings, mocker)
    flow.flow.databus_clean_result_table_id = "2_bkapm_tail_demo"
    flow.config = {}
    remote = _remote_tail_flow()
    args = json.loads(remote["spec"]["nodes"][1]["programming_args"])
    args.update(flow._v4_programming_args(args["input_table_id"], args["output_table_id"]))
    remote["spec"]["nodes"][1]["programming_args"] = json.dumps(args)
    mocker.patch("apm.core.handlers.bk_data.tail_sampling.api.bkdata.get_data_link", return_value=remote)
    apply_resources = mocker.patch.object(flow, "_apply_v4_resources")

    flow._update_existing_v4_flow()

    apply_resources.assert_not_called()


def test_tail_sampling_existing_stopped_flow_only_starts_with_new_args(settings, mocker):
    flow = _build_tail_sampling_v4_flow(settings, mocker)
    flow.flow.databus_clean_result_table_id = "2_bkapm_tail_demo"
    remote = _remote_tail_flow()
    remote["metadata"]["annotations"]["task_stopped"] = "true"
    mocker.patch("apm.core.handlers.bk_data.tail_sampling.api.bkdata.get_data_link", return_value=remote)
    apply_resources = mocker.patch.object(flow, "_apply_v4_resources")

    flow._update_existing_v4_flow()

    apply_resources.assert_called_once()
    start = apply_resources.call_args.args[0][0]
    assert start["metadata"]["annotations"]["task_stopped"] == "false"
    assert json.loads(start["spec"]["nodes"][1]["programming_args"])["random_sampling_ratio"] == 25


def test_tail_sampling_existing_native_v4_flow_reuses_its_bklog_source(settings, mocker):
    flow = _build_tail_sampling_v4_flow(settings, mocker, flow_id="bkapm_tail_sampling_10001_tail_v4")
    flow.flow.databus_clean_result_table_id = "2_bkapm_tail_10001_tail_v4"
    remote = _remote_tail_flow(
        flow_name="bkapm_tail_sampling_10001_tail_v4",
        source_namespace="bklog",
        source_name="bkapm_tail_10001_tail_v4",
        input_table_id="2_bkapm_tail_10001_tail_v4",
    )
    remote["spec"]["alias"] = "existing alias"
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
    # 远端已有非空 alias 时保留
    assert apply_resources.call_args.args[0][0]["spec"]["alias"] == "existing alias"


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


def _es_storage_case(settings, mocker, binding_spec, binding=True):
    """构造 ES 存储解析用例：监控侧集群名故意与 BKBase 绑定不同，验证以绑定为准。"""
    flow = _build_tail_sampling_v4_flow(settings, mocker)
    trace = SimpleNamespace(
        result_table_id="5005578_bkapm.trace_bk_dbm",
        storage=SimpleNamespace(retention=7, storage_cluster=SimpleNamespace(cluster_name="DBM_ES")),
    )
    direct_link = SimpleNamespace(namespace="bklog", data_link_name="l_559760")
    binding_filter = mocker.patch("apm.core.handlers.bk_data.tail_sampling.ESStorageBindingConfig.objects.filter")
    binding_filter.return_value.first.return_value = (
        SimpleNamespace(kind="ElasticSearchBinding", namespace="bklog", name="l_559760") if binding else None
    )
    get_data_link = mocker.patch(
        "apm.core.handlers.bk_data.tail_sampling.api.bkdata.get_data_link", return_value={"spec": binding_spec}
    )
    return flow, trace, direct_link, binding_filter, get_data_link


def test_tail_sampling_v4_es_storage_follows_direct_link_binding(settings, mocker):
    binding_spec = {
        "storage": {"kind": "ElasticSearch", "tenant": "default", "namespace": "bklog", "name": "dbm-logs1"},
        "write_alias": {"TimeBased": {"format": "write_%Y%m%d_5005578_bkapm_trace_bk_dbm", "timezone": 0}},
        "unique_field_list": ["trace_id", "span_id", "x"],
    }
    flow, trace, direct_link, binding_filter, get_data_link = _es_storage_case(settings, mocker, binding_spec)
    query_v3_resources = mocker.patch("apm.core.handlers.bk_data.tail_sampling.api.bkdata.query_resource_list")

    storage = flow._resolve_v4_es_storage(trace, direct_link)

    # ES 资源名取 BKBase 绑定的 dbm-logs1，而不是监控侧 ClusterInfo 的 DBM_ES
    assert storage == {
        "storage": {"kind": "ElasticSearch", "tenant": "default", "namespace": "bklog", "name": "dbm-logs1"},
        "write_alias": {"TimeBased": {"format": "write_%Y%m%d_5005578_bkapm_trace_bk_dbm", "timezone": 0}},
        "unique_field_list": ["trace_id", "span_id", "x"],
        "retention": 7,
        "replicas": 1,
    }
    binding_filter.assert_called_once_with(bk_tenant_id="system", namespace="bklog", data_link_name="l_559760")
    get_data_link.assert_called_once_with(
        bk_tenant_id="system", kind="elasticsearchbindings", namespace="bklog", name="l_559760"
    )
    query_v3_resources.assert_not_called()


def test_tail_sampling_v4_es_storage_unique_fields_fallback_to_trace_default(settings, mocker):
    binding_spec = {
        "storage": {"kind": "ElasticSearch", "tenant": "default", "namespace": "bklog", "name": "dbm-logs1"},
        "write_alias": {"TimeBased": {"format": "write_%Y%m%d_5005578_bkapm_trace_bk_dbm", "timezone": 0}},
    }
    flow, trace, direct_link, *_ = _es_storage_case(settings, mocker, binding_spec)

    storage = flow._resolve_v4_es_storage(trace, direct_link)

    assert storage["unique_field_list"] == [
        "trace_id",
        "span_id",
        "parent_span_id",
        "start_time",
        "end_time",
        "span_name",
    ]


def test_tail_sampling_v4_es_storage_requires_direct_link_binding(settings, mocker):
    flow, trace, direct_link, _, get_data_link = _es_storage_case(settings, mocker, {}, binding=False)

    with pytest.raises(ValueError, match="未找到 ES 存储绑定"):
        flow._resolve_v4_es_storage(trace, direct_link)

    get_data_link.assert_not_called()


def test_tail_sampling_v4_es_storage_rejects_incomplete_binding(settings, mocker):
    flow, trace, direct_link, *_ = _es_storage_case(settings, mocker, {"storage": {"name": "dbm-logs1"}})

    with pytest.raises(ValueError, match="缺少 storage 或 write_alias"):
        flow._resolve_v4_es_storage(trace, direct_link)


def test_tail_sampling_disable_direct_link_stops_given_link_and_marks_option(settings, mocker):
    flow = _build_tail_sampling_v4_flow(settings, mocker)
    trace = SimpleNamespace(result_table_id="5005578_bkapm.trace_bk_dbm")
    direct_link = mocker.Mock()
    update_option = mocker.patch("apm.core.handlers.bk_data.tail_sampling.ResultTableOption.objects.update_or_create")

    flow._disable_direct_trace_datalink(trace, direct_link)

    assert update_option.call_args.kwargs["table_id"] == "5005578_bkapm.trace_bk_dbm"
    assert update_option.call_args.kwargs["name"] == "enable_log_v4_data_link"
    assert update_option.call_args.kwargs["defaults"]["value"] == "false"
    direct_link.delete_data_link.assert_called_once_with()


def test_tail_sampling_direct_link_is_resolved_from_metadata(settings, mocker):
    flow = _build_tail_sampling_v4_flow(settings, mocker)
    trace = SimpleNamespace(bk_data_id=559760, result_table_id="5005578_bkapm.trace_bk_dbm")
    target = SimpleNamespace(data_link_name="l_559760", table_ids=["5005578_bkapm.trace_bk_dbm"])
    other = SimpleNamespace(data_link_name="l_other", table_ids=["5005578_bkapm.other"])
    link_filter = mocker.patch(
        "apm.core.handlers.bk_data.tail_sampling.DataLink.objects.filter", return_value=[other, target]
    )

    assert flow._get_direct_trace_datalink(trace) is target
    link_filter.assert_called_once_with(bk_tenant_id="system", data_link_strategy="bk_log", bk_data_id=559760)

    link_filter.return_value = [other]
    assert flow._get_direct_trace_datalink(trace) is None

    link_filter.return_value = [target, SimpleNamespace(data_link_name="l_dup", table_ids=[trace.result_table_id])]
    with pytest.raises(ValueError, match="多个直写 DataLink"):
        flow._get_direct_trace_datalink(trace)


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


DIRECT_LINK = SimpleNamespace(namespace="bklog", data_link_name="l_10001")


def _native_v4_trace(flow, mocker, **kwargs):
    """非共享且 metadata 中存在直写链路的 Trace（不依赖 APM 侧 version 标记）。"""
    trace = SimpleNamespace(is_shared=False, **kwargs)
    mocker.patch("apm.core.handlers.bk_data.tail_sampling.TraceDataSource.objects.get", return_value=trace)
    mocker.patch.object(flow, "_get_direct_trace_datalink", return_value=DIRECT_LINK)
    return trace


def test_tail_sampling_rejects_shared_trace_datasource(settings, mocker):
    flow = _build_tail_sampling_v4_flow(settings, mocker, flow_id=None)
    trace = SimpleNamespace(is_shared=True)
    mocker.patch("apm.core.handlers.bk_data.tail_sampling.TraceDataSource.objects.get", return_value=trace)
    get_direct_link = mocker.patch.object(flow, "_get_direct_trace_datalink")
    create_new = mocker.patch.object(flow, "_create_v4_flow")
    start_v3 = mocker.patch.object(ApmFlow, "start")
    mocker.patch.object(flow, "_raise_exc", side_effect=ValueError("shared"))

    with pytest.raises(ValueError, match="shared"):
        flow.start()

    get_direct_link.assert_not_called()
    create_new.assert_not_called()
    start_v3.assert_not_called()


def test_tail_sampling_without_direct_link_falls_back_to_v3(settings, mocker):
    flow = _build_tail_sampling_v4_flow(settings, mocker, flow_id=None)
    trace = SimpleNamespace(is_shared=False)
    mocker.patch("apm.core.handlers.bk_data.tail_sampling.TraceDataSource.objects.get", return_value=trace)
    mocker.patch.object(flow, "_get_direct_trace_datalink", return_value=None)
    create_new = mocker.patch.object(flow, "_create_v4_flow")
    update_field = mocker.patch.object(flow, "_update_field")
    start_v3 = mocker.patch.object(ApmFlow, "start", return_value="v3")

    assert flow.start() == "v3"

    start_v3.assert_called_once_with()
    create_new.assert_not_called()
    update_field.assert_not_called()


def test_tail_sampling_multiple_direct_links_fail_before_create(settings, mocker):
    flow = _build_tail_sampling_v4_flow(settings, mocker, flow_id=None)
    trace = SimpleNamespace(is_shared=False)
    mocker.patch("apm.core.handlers.bk_data.tail_sampling.TraceDataSource.objects.get", return_value=trace)
    mocker.patch.object(flow, "_get_direct_trace_datalink", side_effect=ValueError("匹配到多个直写 DataLink"))
    create_new = mocker.patch.object(flow, "_create_v4_flow")
    start_v3 = mocker.patch.object(ApmFlow, "start")
    raise_exc = mocker.patch.object(flow, "_raise_exc", side_effect=ValueError("匹配到多个直写 DataLink"))

    with pytest.raises(ValueError, match="多个直写"):
        flow.start()

    raise_exc.assert_called_once()
    create_new.assert_not_called()
    start_v3.assert_not_called()


def test_tail_sampling_does_not_cut_direct_link_when_apply_fails(settings, mocker):
    flow = _build_tail_sampling_v4_flow(settings, mocker, flow_id=None)
    _native_v4_trace(flow, mocker)
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
    trace = _native_v4_trace(flow, mocker, bk_data_id=10001)
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
    resolve_storage = mocker.patch.object(flow, "_resolve_v4_es_storage", return_value={})
    flow_config = {"kind": "Flow", "metadata": {"name": "bkapm_tail_sampling_10001_tail_v4"}}
    mocker.patch.object(flow, "compose_v4_flow_config", return_value=flow_config)
    apply_resources = mocker.patch.object(flow, "_apply_v4_resources", return_value={"Flow": {}})
    update_field = mocker.patch.object(flow, "_update_field")
    disable_direct = mocker.patch.object(flow, "_disable_direct_trace_datalink")
    disable_direct.side_effect = lambda _trace, _link: update_field.assert_not_called()

    flow.start()

    # ES 写入目标与停用的都是 metadata 中查到的同一条直写链路
    resolve_storage.assert_called_once_with(trace, DIRECT_LINK)

    apply_resources.assert_called_once_with(
        [
            {"kind": "ResultTable", "spec": {"bizId": 2}},
            {"kind": "Databus", "metadata": {"name": "bkapm_tail_10001_tail_v4"}},
            flow_config,
        ]
    )
    disable_direct.assert_called_once_with(trace, DIRECT_LINK)
    assert update_field.call_args_list[0].args[0]["databus_clean_config"] == {
        "kind": "Databus",
        "metadata": {"name": "bkapm_tail_10001_tail_v4"},
    }
    assert "deploy_bk_biz_id" not in update_field.call_args_list[0].args[0]


def test_tail_sampling_retries_new_flow_if_direct_link_cutover_fails(settings, mocker):
    flow = _build_tail_sampling_v4_flow(settings, mocker, flow_id=None)
    _native_v4_trace(flow, mocker, bk_data_id=10001)
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
