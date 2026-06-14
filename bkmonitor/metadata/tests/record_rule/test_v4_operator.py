"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import datetime
from types import SimpleNamespace

import pytest
from django.utils.timezone import now

from api.unify_query.default import CheckQueryTsByPromqlResource, CheckQueryTsResource
from bkmonitor.utils.tenant import DatalinkBizIds
from metadata import models
from metadata.models.data_link.constants import DataLinkResourceStatus
from metadata.models.record_rule.constants import (
    RECORD_RULE_V4_BKBASE_NAMESPACE,
    RECORD_RULE_V4_DELETED_RETENTION_DAYS,
    RECORD_RULE_V4_BKMONITOR_NAMESPACE,
    RecordRuleV4DesiredStatus,
    RecordRuleV4FlowActionType,
    RecordRuleV4FlowStatus,
    RecordRuleV4InputType,
    RecordRuleV4Status,
)
from metadata.models.record_rule.v4 import (
    CONDITION_FALSE,
    CONDITION_FLOW_HEALTHY,
    CONDITION_RECONCILED,
    CONDITION_RESOLVED,
    EVENT_REASON_OPERATION_LOCKED,
    EVENT_STATUS_SKIPPED,
    EVENT_TYPE_OPERATION_SKIPPED,
    EVENT_TYPE_APPLY_SUCCEEDED,
    EVENT_TYPE_APPLY_STARTED,
    EVENT_TYPE_FLOW_ACTION_STARTED,
    EVENT_TYPE_FLOW_ACTION_SUCCEEDED,
    RecordRuleV4,
    RecordRuleV4Event,
)
from metadata.models.record_rule.v4.operator import RecordRuleV4Operator
from metadata.models.record_rule.v4.output import RecordRuleV4OutputResources
from metadata.models.record_rule.v4.resolver import RecordRuleV4Resolver
from metadata.models.record_rule.v4.runner import RecordRuleV4Runner
from metadata.models.record_rule.v4.source import resolve_vm_result_table_configs
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis
from metadata.task.record_rule_v4 import refresh_record_rule_v4

pytestmark = pytest.mark.django_db(databases="__all__")

TENANT_ID = "tenant_v4_pytest"
SPACE_TYPE = "bkcc"
SPACE_ID = "2"
RULE_NAME = "rr_cpu_group"
SOURCE_TABLE_ID = "system.cpu_summary"
SOURCE_VM_TABLE_ID = "2_system_cpu_summary"
SOURCE_BKBASE_TABLE_NAME = "bkbase_system_cpu_summary"
SECOND_SOURCE_TABLE_ID = "system.cpu_detail"
SECOND_SOURCE_VM_TABLE_ID = "2_system_cpu_detail"
SECOND_SOURCE_BKBASE_TABLE_NAME = "bkbase_system_cpu_detail"
METRICQL = 'avg by (bk_target_ip) ({bk_biz_id="2", result_table_id="2_system_cpu_summary", __name__="usage"})'
CHANGED_METRICQL = f"sum({METRICQL})"


@pytest.fixture
def v4_base_data(settings, mocker):
    settings.DEFAULT_BKDATA_BIZ_ID = 2
    settings.BK_DATA_PROJECT_MAINTAINER = "admin"
    settings.ENABLE_MULTI_TENANT_MODE = True
    datalink_biz_ids = DatalinkBizIds(label_biz_id=int(SPACE_ID), data_biz_id=int(SPACE_ID))
    mocker.patch("metadata.models.record_rule.v4.output.get_tenant_datalink_biz_id", return_value=datalink_biz_ids)
    mocker.patch(
        "metadata.models.data_link.data_link_configs.get_tenant_datalink_biz_id", return_value=datalink_biz_ids
    )
    models.Space.objects.create(
        bk_tenant_id=TENANT_ID,
        space_type_id=SPACE_TYPE,
        space_id=SPACE_ID,
        space_name="biz-2",
    )
    cluster = models.ClusterInfo.objects.create(
        bk_tenant_id=TENANT_ID,
        cluster_id=1001,
        cluster_name="monitor-opsystem",
        cluster_type=models.ClusterInfo.TYPE_VM,
        domain_name="vm.service.local",
        port=9090,
        description="default vm",
        is_default_cluster=True,
    )
    create_source_vm_mapping(
        table_id=SOURCE_TABLE_ID,
        vm_table_id=SOURCE_VM_TABLE_ID,
        bkbase_table_name=SOURCE_BKBASE_TABLE_NAME,
        cluster_id=cluster.cluster_id,
    )
    return SimpleNamespace(cluster=cluster)


@pytest.fixture
def external_api(mocker):
    check_query_ts = mocker.patch(
        "metadata.models.record_rule.v4.resolver.api.unify_query.check_query_ts",
        return_value=build_check_result(),
    )
    check_promql = mocker.patch(
        "metadata.models.record_rule.v4.resolver.api.unify_query.check_query_ts_by_promql",
        return_value=build_check_result(metricql="promql_metricql"),
    )
    apply_data_link = mocker.patch(
        "metadata.models.record_rule.v4.runner.api.bkdata.apply_data_link",
        return_value={"status": "ok"},
    )
    delete_data_link = mocker.patch(
        "metadata.models.record_rule.v4.runner.api.bkdata.delete_data_link",
        return_value={"status": "deleted"},
    )
    get_data_link = mocker.patch(
        "metadata.models.record_rule.v4.runner.api.bkdata.get_data_link",
        return_value={"status": {"state": "ok"}},
    )
    space_redis = mocker.patch("metadata.models.record_rule.v4.output.SpaceTableIDRedis").return_value
    return SimpleNamespace(
        check_query_ts=check_query_ts,
        check_promql=check_promql,
        apply_data_link=apply_data_link,
        delete_data_link=delete_data_link,
        get_data_link=get_data_link,
        space_redis=space_redis,
    )


def build_check_result(
    metricql: str = METRICQL,
    result_table_id: str | list[str] = SOURCE_VM_TABLE_ID,
    storage_type: str = "victoria_metrics",
) -> dict:
    result_table_ids = [result_table_id] if isinstance(result_table_id, str) else result_table_id
    return {
        "data": [
            {
                "storage_type": storage_type,
                "metricql": metricql,
                "result_table_id": result_table_ids,
            }
        ],
    }


def build_query_config() -> dict:
    return {
        "query_list": [
            {
                "data_source": "bk_monitor",
                "table_id": "system.cpu_summary",
                "field_name": "usage",
                "reference_name": "a",
            }
        ],
        "metric_merge": "a",
        "start_time": "1710000000",
        "end_time": "1710000600",
        "step": "1m",
    }


def build_structured_query_config() -> dict:
    return {
        "bk_biz_id": 2,
        "query_configs": [
            {
                "data_source_label": "bk_monitor",
                "data_type_label": "time_series",
                "metrics": [{"field": "in_use", "method": "AVG", "alias": "a"}],
                "table": "system.disk",
                "data_label": "",
                "index_set_id": None,
                "group_by": ["bk_target_cloud_id"],
                "where": [
                    {"key": "mount_point", "method": "eq", "value": ["/data1"]},
                    {"condition": "and", "key": "bk_target_cloud_id", "method": "eq", "value": ["0"]},
                ],
                "interval": 60,
                "interval_unit": "s",
                "time_field": None,
                "filter_dict": {},
                "functions": [{"id": "rate", "params": [{"id": "window", "value": "2m"}]}],
            },
            {
                "data_source_label": "bk_monitor",
                "data_type_label": "time_series",
                "metrics": [{"field": "usage", "method": "AVG", "alias": "b"}],
                "table": "system.cpu_summary",
                "data_label": "",
                "index_set_id": None,
                "group_by": [],
                "where": [],
                "interval": 60,
                "interval_unit": "s",
                "time_field": None,
                "filter_dict": {},
                "functions": [],
            },
        ],
        "expression": "a / b",
        "functions": [],
        "alias": "c",
        "name": "AVG(磁盘空间使用率) / AVG(CPU使用率)",
        "start_time": 1778935339,
        "end_time": 1778938939,
        "slimit": 500,
        "down_sample_range": "7s",
    }


def create_source_vm_mapping(
    *,
    table_id: str,
    vm_table_id: str,
    bkbase_table_name: str,
    cluster_id: int,
    bkbase_table_id: str = "",
) -> None:
    models.AccessVMRecord.objects.create(
        bk_tenant_id=TENANT_ID,
        result_table_id=table_id,
        bk_base_data_id=100,
        vm_result_table_id=vm_table_id,
        vm_cluster_id=cluster_id,
    )
    models.ResultTableConfig.objects.create(
        bk_tenant_id=TENANT_ID,
        namespace=RECORD_RULE_V4_BKMONITOR_NAMESPACE,
        name=bkbase_table_name,
        data_link_name=bkbase_table_name,
        table_id=table_id,
        bkbase_table_id=bkbase_table_id,
        bk_biz_id=int(SPACE_ID),
    )


def build_record(
    *,
    metric_name: str = "cpu_usage_avg",
    input_type: str = RecordRuleV4InputType.QUERY_TS.value,
    input_config: dict | None = None,
    labels: list[dict] | None = None,
    record_key: str = "",
) -> dict:
    record = {
        "input_type": input_type,
        "input_config": input_config or build_query_config(),
        "metric_name": metric_name,
        "labels": [{"scenario": "pytest"}] if labels is None else labels,
    }
    if record_key:
        record["record_key"] = record_key
    return record


def declare_rule(
    *,
    records: list[dict] | None = None,
    name: str = RULE_NAME,
    description: str = "",
    data_label: str = "",
    interval: str = "1min",
    labels: list[dict] | None = None,
    auto_refresh: bool = True,
) -> RecordRuleV4:
    records = [build_record()] if records is None else records
    group_labels = labels or []
    return RecordRuleV4Operator.declare(
        bk_tenant_id=TENANT_ID,
        space_type=SPACE_TYPE,
        space_id=SPACE_ID,
        name=name,
        records=records,
        description=description,
        data_label=data_label,
        raw_config={
            "records": records,
            "interval": interval,
            "labels": group_labels,
            "description": description,
            "data_label": data_label,
        },
        interval=interval,
        labels=group_labels,
        auto_refresh=auto_refresh,
        source="pytest",
        operator="tester",
    )


def create_rule(
    *,
    records: list[dict] | None = None,
    name: str = RULE_NAME,
    description: str = "",
    data_label: str = "",
    interval: str = "1min",
    labels: list[dict] | None = None,
    auto_refresh: bool = True,
    apply_immediately: bool = True,
) -> RecordRuleV4:
    rule = declare_rule(
        records=records,
        name=name,
        description=description,
        data_label=data_label,
        interval=interval,
        labels=labels,
        auto_refresh=auto_refresh,
    )
    RecordRuleV4Operator(rule, source="pytest", operator="tester").execute_declaration(auto_apply=apply_immediately)
    rule.refresh_from_db()
    return rule


def get_recording_rule_node(flow_config: dict) -> dict:
    for node in flow_config["spec"]["nodes"]:
        if node["kind"] == "RecordingRuleNode":
            return node
    raise AssertionError("RecordingRuleNode not found")


def get_source_nodes(flow_config: dict) -> list[dict]:
    return [node for node in flow_config["spec"]["nodes"] if node["kind"] == "VmSourceNode"]


def get_latest_resolved(rule: RecordRuleV4):
    return rule.current_spec.latest_resolved


def get_latest_flow(rule: RecordRuleV4):
    return get_latest_resolved(rule).flow


def get_applied_flow(rule: RecordRuleV4):
    flow = rule.get_applied_flow()
    assert flow is not None
    return flow


def has_unapplied_resolved(rule: RecordRuleV4) -> bool:
    latest_resolved = get_latest_resolved(rule)
    return bool(latest_resolved and latest_resolved.pk != rule.applied_resolved_id)


def assert_output_apply_only(external_api) -> None:
    """只下发 output 资源，不下发 Flow。"""

    assert external_api.apply_data_link.call_count == 1
    assert [item["kind"] for item in external_api.apply_data_link.call_args.kwargs["config"]] == [
        "ResultTable",
        "VmStorageBinding",
    ]


def assert_flow_apply_only(external_api) -> None:
    """只下发 Flow，说明 output 本地配置已存在且被跳过。"""

    assert external_api.apply_data_link.call_count == 1
    assert [item["kind"] for item in external_api.apply_data_link.call_args.kwargs["config"]] == ["Flow"]


def assert_output_then_flow(external_api) -> None:
    """先独立下发 output，再独立下发 Flow。"""

    assert external_api.apply_data_link.call_count == 2
    assert [item["kind"] for item in external_api.apply_data_link.call_args_list[0].kwargs["config"]] == [
        "ResultTable",
        "VmStorageBinding",
    ]
    assert [item["kind"] for item in external_api.apply_data_link.call_args_list[1].kwargs["config"]] == ["Flow"]


def set_output_status(rule: RecordRuleV4, status: str) -> None:
    config_name = RecordRuleV4OutputResources.compose_result_table_config_name(rule.table_id)
    models.ResultTableConfig.objects.filter(
        bk_tenant_id=TENANT_ID,
        namespace=RECORD_RULE_V4_BKMONITOR_NAMESPACE,
        name=config_name,
    ).update(status=status)
    models.VMStorageBindingConfig.objects.filter(
        bk_tenant_id=TENANT_ID,
        namespace=RECORD_RULE_V4_BKMONITOR_NAMESPACE,
        name=config_name,
    ).update(status=status)


def test_declare_only_writes_spec_without_external_side_effects(v4_base_data, external_api):
    rule = declare_rule(description="record rule output", data_label="rr_cpu")

    rule.refresh_from_db()
    assert rule.current_spec is not None
    assert rule.current_spec.records.count() == 1
    assert rule.current_spec.latest_resolved_id is None
    assert rule.applied_resolved_id is None
    assert rule.status == RecordRuleV4Status.PENDING.value
    assert not models.ResultTable.objects.filter(table_id=rule.table_id, bk_tenant_id=TENANT_ID).exists()
    assert rule.get_latest_flow() is None
    external_api.check_query_ts.assert_not_called()
    external_api.check_promql.assert_not_called()
    external_api.apply_data_link.assert_not_called()
    external_api.space_redis.push_space_table_ids.assert_not_called()
    external_api.space_redis.push_table_id_detail.assert_not_called()


def test_create_group_with_two_records_applies_single_flow(v4_base_data, external_api):
    records = [
        build_record(metric_name="cpu_usage_avg"),
        build_record(metric_name="cpu_total_sum"),
    ]

    rule = create_rule(records=records)

    rule.refresh_from_db()
    flow = get_latest_flow(rule)
    resolved = get_latest_resolved(rule)
    table_base_name = rule.table_id.split(".__default__")[0]
    assert len(table_base_name) <= 50
    assert len(rule.dst_vm_table_id) <= 50
    assert table_base_name.startswith(f"bkm_rr_{rule.pk}_rr_cpu_group_")
    assert rule.flow_name == table_base_name
    assert rule.flow_name == flow.flow_name
    assert rule.description == ""
    assert rule.data_label == ""
    assert rule.dst_vm_storage_name == "monitor-opsystem"
    assert resolved.records.count() == 2
    assert resolved.flow.pk == flow.pk
    assert rule.current_spec.bk_tenant_id == TENANT_ID
    assert rule.current_spec.records.filter(bk_tenant_id=TENANT_ID).count() == 2
    assert resolved.bk_tenant_id == TENANT_ID
    assert resolved.records.filter(bk_tenant_id=TENANT_ID).count() == 2
    assert flow.bk_tenant_id == TENANT_ID
    assert rule.events.filter(bk_tenant_id=TENANT_ID).exists()
    assert rule.applied_resolved_id == resolved.pk
    assert rule.applied_desired_status == RecordRuleV4DesiredStatus.RUNNING.value
    assert rule.status == RecordRuleV4Status.RUNNING.value
    assert has_unapplied_resolved(rule) is False
    assert len(flow.flow_name) <= 50

    source_node = get_source_nodes(flow.flow_config)[0]
    recording_rule_node = get_recording_rule_node(flow.flow_config)
    assert flow.flow_config["metadata"]["tenant"] == TENANT_ID
    assert source_node["data"]["name"] == SOURCE_BKBASE_TABLE_NAME
    assert source_node["data"]["tenant"] == TENANT_ID
    assert recording_rule_node["inputs"] == ["vm_source"]
    assert recording_rule_node["output"] == rule.dst_vm_table_id
    assert [item["metric_name"] for item in recording_rule_node["config"]] == ["cpu_usage_avg", "cpu_total_sum"]
    assert recording_rule_node["config"][0]["interval"] == rule.current_spec.interval
    assert recording_rule_node["config"][0]["labels"] == [{"scenario": "pytest"}]
    assert recording_rule_node["storage"] == {
        "kind": "VmStorage",
        "tenant": TENANT_ID,
        "namespace": RECORD_RULE_V4_BKMONITOR_NAMESPACE,
        "name": "monitor-opsystem",
    }
    assert flow.flow_config["metadata"]["namespace"] == RECORD_RULE_V4_BKBASE_NAMESPACE
    assert flow.flow_config["metadata"]["labels"] == {
        "bk_biz_id": SPACE_ID,
        "flow_type": "recording-rule",
    }
    assert flow.flow_config["metadata"]["annotations"] == {
        "record-rule.bkmonitor/space-uid": f"{SPACE_TYPE}__{SPACE_ID}",
        "record-rule.bkmonitor/name": RULE_NAME,
        "record-rule.bkmonitor/generation": str(resolved.generation),
        "record-rule.bkmonitor/resolved-version": str(resolved.resolve_version),
    }

    assert external_api.check_query_ts.call_count == 2
    # 执行链路先确保 output 资源，再下发 Flow；两次 apply_data_link 不应混在同一个 payload 里。
    assert_output_then_flow(external_api)
    first_resolved_record = resolved.get_records()[0]
    assert first_resolved_record.labels == [{"scenario": "pytest"}]
    assert first_resolved_record.src_result_table_configs == [
        {
            "result_table_id": SOURCE_TABLE_ID,
            "vm_result_table_id": SOURCE_VM_TABLE_ID,
            "bkbase_result_table_name": SOURCE_BKBASE_TABLE_NAME,
            "vm_storage_name": "monitor-opsystem",
        }
    ]
    assert models.ResultTable.objects.filter(table_id=rule.table_id, bk_tenant_id=TENANT_ID).exists()
    output_config = models.ResultTableConfig.objects.get(table_id=rule.table_id, bk_tenant_id=TENANT_ID)
    assert output_config.name == RecordRuleV4OutputResources.compose_result_table_config_name(rule.table_id)
    assert rule.dst_vm_table_id == f"{output_config.datalink_biz_ids.data_biz_id}_{output_config.name}"
    assert output_config.bkbase_table_id == rule.dst_vm_table_id
    output_table = models.ResultTable.objects.get(table_id=rule.table_id, bk_tenant_id=TENANT_ID)
    assert output_table.table_name_zh == RULE_NAME
    assert output_table.data_label == ""
    assert models.ResultTableField.objects.filter(
        table_id=rule.table_id,
        bk_tenant_id=TENANT_ID,
        field_name="cpu_usage_avg",
    ).exists()
    assert models.ResultTableField.objects.filter(
        table_id=rule.table_id,
        bk_tenant_id=TENANT_ID,
        field_name="cpu_total_sum",
    ).exists()
    assert models.AccessVMRecord.objects.filter(
        result_table_id=rule.table_id,
        vm_result_table_id=rule.dst_vm_table_id,
        bk_tenant_id=TENANT_ID,
        vm_cluster_id=v4_base_data.cluster.cluster_id,
    ).exists()
    external_api.space_redis.push_space_table_ids.assert_called_once_with(
        space_type=SPACE_TYPE,
        space_id=SPACE_ID,
        is_publish=True,
    )
    external_api.space_redis.push_table_id_detail.assert_called_once_with(
        table_id_list=[rule.table_id],
        is_publish=True,
        bk_tenant_id=TENANT_ID,
    )


def test_space_table_ids_keep_record_rule_v4_until_delete_retention_expires(v4_base_data, external_api):
    rule = create_rule(apply_immediately=False)
    redis_client = SpaceTableIDRedis()

    route_values = redis_client._compose_record_rule_table_ids(
        space_type=SPACE_TYPE,
        space_id=SPACE_ID,
        bk_tenant_id=TENANT_ID,
    )
    assert route_values[rule.table_id] == {"filters": []}

    rule.set_desired_status(RecordRuleV4DesiredStatus.STOPPED.value)
    route_values = redis_client._compose_record_rule_table_ids(
        space_type=SPACE_TYPE,
        space_id=SPACE_ID,
        bk_tenant_id=TENANT_ID,
    )
    assert rule.table_id in route_values

    rule.set_desired_status(RecordRuleV4DesiredStatus.DELETED.value)
    route_values = redis_client._compose_record_rule_table_ids(
        space_type=SPACE_TYPE,
        space_id=SPACE_ID,
        bk_tenant_id=TENANT_ID,
    )
    assert rule.table_id in route_values

    rule.deleted_at = now() - datetime.timedelta(days=RECORD_RULE_V4_DELETED_RETENTION_DAYS - 1)
    rule.save(update_fields=["deleted_at", "updated_at"])
    route_values = redis_client._compose_record_rule_table_ids(
        space_type=SPACE_TYPE,
        space_id=SPACE_ID,
        bk_tenant_id=TENANT_ID,
    )
    assert rule.table_id in route_values

    rule.deleted_at = now() - datetime.timedelta(days=RECORD_RULE_V4_DELETED_RETENTION_DAYS + 1)
    rule.save(update_fields=["deleted_at", "updated_at"])
    route_values = redis_client._compose_record_rule_table_ids(
        space_type=SPACE_TYPE,
        space_id=SPACE_ID,
        bk_tenant_id=TENANT_ID,
    )
    assert rule.table_id not in route_values


def test_create_supports_description_and_data_label(v4_base_data, external_api):
    rule = create_rule(description="record rule output", data_label="rr_cpu")

    output_table = models.ResultTable.objects.get(table_id=rule.table_id, bk_tenant_id=TENANT_ID)
    assert rule.description == "record rule output"
    assert rule.data_label == "rr_cpu"
    assert rule.to_dict()["description"] == "record rule output"
    assert output_table.table_name_zh == RULE_NAME
    assert output_table.data_label == "rr_cpu"


def test_create_rejects_empty_records(v4_base_data, external_api):
    with pytest.raises(ValueError, match="at least one record"):
        create_rule(records=[])

    assert RecordRuleV4.objects.count() == 0
    external_api.check_query_ts.assert_not_called()
    external_api.apply_data_link.assert_not_called()


def test_declare_rejects_deleted_initial_desired_status(v4_base_data, external_api):
    with pytest.raises(ValueError, match="unsupported desired_status: deleted"):
        RecordRuleV4Operator.declare(
            bk_tenant_id=TENANT_ID,
            space_type=SPACE_TYPE,
            space_id=SPACE_ID,
            name=RULE_NAME,
            records=[build_record()],
            desired_status=RecordRuleV4DesiredStatus.DELETED.value,
            source="pytest",
            operator="tester",
        )

    assert RecordRuleV4.objects.count() == 0
    external_api.apply_data_link.assert_not_called()


def test_group_interval_and_labels_merge_into_resolved_and_flow(v4_base_data, external_api):
    record = build_record(labels=[{"scenario": "record"}, {"owner": "record"}])

    rule = create_rule(
        records=[record],
        interval="5min",
        labels=[{"scenario": "group"}, {"env": "prod"}],
    )

    resolved_record = get_latest_resolved(rule).records.get()
    recording_rule_node = get_recording_rule_node(get_latest_flow(rule).flow_config)
    expected_labels = [{"scenario": "record"}, {"env": "prod"}, {"owner": "record"}]
    assert rule.current_spec.interval == "5min"
    assert rule.current_spec.labels == [{"scenario": "group"}, {"env": "prod"}]
    assert resolved_record.labels == expected_labels
    assert recording_rule_node["config"][0]["interval"] == "5min"
    assert recording_rule_node["config"][0]["labels"] == expected_labels


def test_update_raw_config_alone_does_not_create_spec(v4_base_data, external_api):
    rule = create_rule(apply_immediately=False)
    current_spec_id = rule.current_spec_id
    current_generation = rule.generation
    external_api.check_query_ts.reset_mock()

    updated = RecordRuleV4Operator(rule, source="manual", operator="admin").update_declaration(
        raw_config={"records": [], "from": "ui_snapshot"},
    )

    updated.refresh_from_db()
    assert updated.current_spec_id == current_spec_id
    assert updated.generation == current_generation
    external_api.check_query_ts.assert_not_called()


def test_update_declaration_with_same_records_does_not_create_spec(v4_base_data, external_api):
    rule = create_rule(apply_immediately=False)
    current_spec_id = rule.current_spec_id
    current_generation = rule.generation
    external_api.check_query_ts.reset_mock()

    updated = RecordRuleV4Operator(rule, source="manual", operator="admin").update_declaration(
        records=[build_record()],
        interval="1min",
        labels=[],
    )

    updated.refresh_from_db()
    assert updated.current_spec_id == current_spec_id
    assert updated.generation == current_generation
    assert updated.specs.count() == 1
    external_api.check_query_ts.assert_not_called()


def test_update_metadata_waits_for_execute_to_refresh_result_table(v4_base_data, external_api):
    rule = create_rule(apply_immediately=False)
    current_spec_id = rule.current_spec_id
    current_resolved_id = get_latest_resolved(rule).pk
    current_flow_id = get_latest_flow(rule).pk
    external_api.check_query_ts.reset_mock()
    external_api.apply_data_link.reset_mock()
    external_api.space_redis.push_table_id_detail.reset_mock()

    operator = RecordRuleV4Operator(rule, source="manual", operator="admin")
    updated = operator.update_declaration(
        description="更新输出表展示信息",
        data_label="rr_cpu",
    )

    updated.refresh_from_db()
    output_table = models.ResultTable.objects.get(table_id=updated.table_id, bk_tenant_id=TENANT_ID)
    assert updated.current_spec_id == current_spec_id
    assert get_latest_resolved(updated).pk == current_resolved_id
    assert get_latest_flow(updated).pk == current_flow_id
    assert updated.description == "更新输出表展示信息"
    assert updated.data_label == "rr_cpu"
    assert output_table.data_label == ""
    external_api.check_query_ts.assert_not_called()
    external_api.apply_data_link.assert_not_called()
    external_api.space_redis.push_table_id_detail.assert_not_called()

    operator.execute_declaration(auto_apply=False)
    updated.refresh_from_db()
    output_table.refresh_from_db()
    assert output_table.table_name_zh == RULE_NAME
    assert output_table.data_label == "rr_cpu"
    external_api.apply_data_link.assert_not_called()
    external_api.space_redis.push_table_id_detail.assert_called_once_with(
        table_id_list=[updated.table_id],
        is_publish=True,
        bk_tenant_id=TENANT_ID,
    )
    assert updated.events.filter(event_type="user.metadata_changed").exists()


def test_new_generation_does_not_inherit_previous_failed_condition(v4_base_data, external_api):
    rule = create_rule()
    external_api.check_query_ts.side_effect = RuntimeError("unify-query unavailable")

    resolved = RecordRuleV4Operator(rule, source="scheduler").refresh_resolved()

    rule.refresh_from_db()
    assert resolved is None
    assert rule.status == RecordRuleV4Status.FAILED.value
    assert rule.get_condition(CONDITION_RESOLVED)["status"] == CONDITION_FALSE

    external_api.check_query_ts.side_effect = None
    updated = RecordRuleV4Operator(rule, source="manual", operator="admin").update_declaration(
        records=[build_record(metric_name="cpu_usage_v2")],
        raw_config={"records": [build_record(metric_name="cpu_usage_v2")]},
    )

    updated.refresh_from_db()
    assert updated.generation == 2
    assert updated.status == RecordRuleV4Status.PENDING.value
    assert updated.get_condition(CONDITION_RESOLVED)["generation"] == 2
    assert updated.get_condition(CONDITION_RESOLVED)["status"] == "Unknown"


def test_create_allows_duplicate_name_with_random_output_names(v4_base_data, external_api):
    first = create_rule(apply_immediately=False)
    second = create_rule(apply_immediately=False)

    assert first.name == second.name == RULE_NAME
    assert first.table_id != second.table_id
    assert first.dst_vm_table_id != second.dst_vm_table_id


def test_create_name_hint_accepts_chinese(v4_base_data, external_api):
    chinese_rule = create_rule(name="<测试任务>", apply_immediately=False)

    chinese_base_name = chinese_rule.table_id.split(".__default__")[0]
    assert chinese_base_name.startswith(f"bkm_rr_{chinese_rule.pk}_ceshirenwu_")
    assert len(chinese_base_name) <= 50
    assert chinese_rule.flow_name == chinese_base_name


def test_create_prepares_output_metadata_before_apply(v4_base_data, external_api):
    rule = create_rule(apply_immediately=False)

    assert models.ResultTable.objects.filter(table_id=rule.table_id, bk_tenant_id=TENANT_ID).exists()
    output_config = models.ResultTableConfig.objects.get(table_id=rule.table_id, bk_tenant_id=TENANT_ID)
    assert output_config.name == RecordRuleV4OutputResources.compose_result_table_config_name(rule.table_id)
    assert output_config.data_link_name == output_config.name
    assert output_config.bkbase_table_id == rule.dst_vm_table_id
    assert rule.dst_vm_table_id == f"{output_config.datalink_biz_ids.data_biz_id}_{output_config.name}"
    assert rule.dst_vm_storage_name == "monitor-opsystem"
    assert models.AccessVMRecord.objects.filter(
        result_table_id=rule.table_id,
        vm_result_table_id=rule.dst_vm_table_id,
        bk_tenant_id=TENANT_ID,
        vm_cluster_id=v4_base_data.cluster.cluster_id,
    ).exists()
    output_options = {
        option.name: option.get_value()
        for option in models.ResultTableOption.objects.filter(table_id=rule.table_id, bk_tenant_id=TENANT_ID)
    }
    assert output_options == {
        models.ResultTableOption.OPTION_IS_SPLIT_MEASUREMENT: True,
        models.ResultTableOption.OPTION_ENABLE_FIELD_BLACK_LIST: False,
    }
    assert models.ResultTableField.objects.filter(
        table_id=rule.table_id,
        bk_tenant_id=TENANT_ID,
        field_name="cpu_usage_avg",
    ).exists()
    external_api.space_redis.push_space_table_ids.assert_called_once_with(
        space_type=SPACE_TYPE,
        space_id=SPACE_ID,
        is_publish=True,
    )
    external_api.space_redis.push_table_id_detail.assert_called_once_with(
        table_id_list=[rule.table_id],
        is_publish=True,
        bk_tenant_id=TENANT_ID,
    )
    assert_output_apply_only(external_api)


def test_reconcile_skips_output_apply_when_pending_and_configs_exist(v4_base_data, external_api):
    rule = create_rule()
    external_api.apply_data_link.reset_mock()

    changed = RecordRuleV4Operator(rule, source="scheduler").reconcile()

    assert changed is False
    external_api.apply_data_link.assert_not_called()


def test_reconcile_skips_output_apply_when_ok_configs_exist_and_only_applies_changed_flow(v4_base_data, external_api):
    rule = create_rule(auto_refresh=True)
    set_output_status(rule, DataLinkResourceStatus.OK.value)
    external_api.apply_data_link.reset_mock()
    external_api.check_query_ts.return_value = build_check_result(metricql=CHANGED_METRICQL)

    changed = RecordRuleV4Operator(rule, source="scheduler").reconcile()

    rule.refresh_from_db()
    assert changed is True
    assert has_unapplied_resolved(rule) is False
    assert_flow_apply_only(external_api)


def test_reconcile_retries_output_apply_when_failed_and_configs_exist(v4_base_data, external_api):
    rule = create_rule()
    set_output_status(rule, DataLinkResourceStatus.FAILED.value)
    external_api.apply_data_link.reset_mock()

    RecordRuleV4Operator(rule, source="scheduler").reconcile()

    # FAILED 说明上一次 output 下发失败，后台调谐应自动重试，而非永久跳过。
    assert_output_apply_only(external_api)
    config_name = RecordRuleV4OutputResources.compose_result_table_config_name(rule.table_id)
    for config_model in (models.ResultTableConfig, models.VMStorageBindingConfig):
        config_instance = config_model.objects.get(
            bk_tenant_id=TENANT_ID,
            namespace=RECORD_RULE_V4_BKMONITOR_NAMESPACE,
            name=config_name,
        )
        assert config_instance.status == DataLinkResourceStatus.PENDING.value


def test_execute_skips_output_apply_when_configs_exist_even_if_local_fields_drift(v4_base_data, external_api):
    rule = create_rule(apply_immediately=False)
    config_name = RecordRuleV4OutputResources.compose_result_table_config_name(rule.table_id)
    models.VMStorageBindingConfig.objects.filter(
        bk_tenant_id=TENANT_ID,
        namespace=RECORD_RULE_V4_BKMONITOR_NAMESPACE,
        name=config_name,
    ).update(vm_cluster_name="old-storage")
    external_api.apply_data_link.reset_mock()

    RecordRuleV4Operator(rule, source="manual", operator="admin").execute_declaration(auto_apply=False)

    binding = models.VMStorageBindingConfig.objects.get(
        bk_tenant_id=TENANT_ID,
        namespace=RECORD_RULE_V4_BKMONITOR_NAMESPACE,
        name=config_name,
    )
    assert binding.vm_cluster_name == "monitor-opsystem"
    external_api.apply_data_link.assert_not_called()


def test_execute_can_force_retry_output_apply(v4_base_data, external_api):
    rule = create_rule(apply_immediately=False)
    external_api.apply_data_link.reset_mock()

    RecordRuleV4Operator(rule, source="manual", operator="admin").execute_declaration(
        auto_apply=False,
        force_output_apply=True,
    )

    assert_output_apply_only(external_api)


def test_resolve_vm_result_table_configs_falls_back_to_access_record(v4_base_data):
    configs = resolve_vm_result_table_configs(
        bk_tenant_id=TENANT_ID,
        vm_result_table_ids=[SOURCE_VM_TABLE_ID],
    )

    assert configs == [
        {
            "result_table_id": SOURCE_TABLE_ID,
            "vm_result_table_id": SOURCE_VM_TABLE_ID,
            "bkbase_result_table_name": SOURCE_BKBASE_TABLE_NAME,
            "vm_storage_name": "monitor-opsystem",
        }
    ]


def test_resolve_vm_result_table_configs_prefers_bkbase_table_id(v4_base_data):
    direct_bkbase_table_name = "direct_bkbase_system_cpu_summary"
    models.ResultTableConfig.objects.create(
        bk_tenant_id=TENANT_ID,
        namespace=RECORD_RULE_V4_BKMONITOR_NAMESPACE,
        name=direct_bkbase_table_name,
        data_link_name=direct_bkbase_table_name,
        table_id="direct.system.cpu_summary",
        bkbase_table_id=SOURCE_VM_TABLE_ID,
        bk_biz_id=int(SPACE_ID),
    )

    configs = resolve_vm_result_table_configs(
        bk_tenant_id=TENANT_ID,
        vm_result_table_ids=[SOURCE_VM_TABLE_ID],
    )

    assert configs[0]["result_table_id"] == "direct.system.cpu_summary"
    assert configs[0]["bkbase_result_table_name"] == direct_bkbase_table_name
    assert configs[0]["vm_storage_name"] == "monitor-opsystem"


def test_resolve_vm_result_table_configs_keeps_input_order_and_each_storage(v4_base_data):
    second_cluster = models.ClusterInfo.objects.create(
        bk_tenant_id=TENANT_ID,
        cluster_id=2002,
        cluster_name="monitor-second",
        cluster_type=models.ClusterInfo.TYPE_VM,
        domain_name="vm-second.service.local",
        port=9090,
        description="second vm",
        is_default_cluster=False,
    )
    create_source_vm_mapping(
        table_id=SECOND_SOURCE_TABLE_ID,
        vm_table_id=SECOND_SOURCE_VM_TABLE_ID,
        bkbase_table_name=SECOND_SOURCE_BKBASE_TABLE_NAME,
        cluster_id=second_cluster.cluster_id,
    )

    configs = resolve_vm_result_table_configs(
        bk_tenant_id=TENANT_ID,
        vm_result_table_ids=[SECOND_SOURCE_VM_TABLE_ID, SOURCE_VM_TABLE_ID, SECOND_SOURCE_VM_TABLE_ID],
    )

    assert [config["vm_result_table_id"] for config in configs] == [SECOND_SOURCE_VM_TABLE_ID, SOURCE_VM_TABLE_ID]
    assert [config["vm_storage_name"] for config in configs] == ["monitor-second", "monitor-opsystem"]


def test_promql_resolve_uses_actual_multi_vmrt_data(v4_base_data, external_api):
    create_source_vm_mapping(
        table_id=SECOND_SOURCE_TABLE_ID,
        vm_table_id=SECOND_SOURCE_VM_TABLE_ID,
        bkbase_table_name=SECOND_SOURCE_BKBASE_TABLE_NAME,
        cluster_id=v4_base_data.cluster.cluster_id,
    )
    metricql = (
        'count({result_table_id="2_system_cpu_summary", __name__="container_cpu_usage_seconds_total_value" '
        'or result_table_id="2_system_cpu_detail", __name__="container_cpu_usage_seconds_total_value"})'
    )
    external_api.check_promql.return_value = build_check_result(
        metricql=metricql,
        result_table_id=[SOURCE_VM_TABLE_ID, SECOND_SOURCE_VM_TABLE_ID],
    )
    record = build_record(
        input_type=RecordRuleV4InputType.PROMQL.value,
        input_config={"promql": "count(bkmonitor:container_cpu_usage_seconds_total)", "bk_biz_ids": [10]},
        metric_name="container_cpu_usage_seconds_total_count",
    )

    rule = create_rule(records=[record])

    resolved_record = get_latest_resolved(rule).records.get()
    source_node_names = {node["data"]["name"] for node in get_source_nodes(get_latest_flow(rule).flow_config)}
    assert resolved_record.metricql == metricql
    assert resolved_record.src_vm_table_ids == [SOURCE_VM_TABLE_ID, SECOND_SOURCE_VM_TABLE_ID]
    assert source_node_names == {SOURCE_BKBASE_TABLE_NAME, SECOND_SOURCE_BKBASE_TABLE_NAME}


def test_promql_check_uses_default_time_range(v4_base_data, external_api):
    record = build_record(
        input_type=RecordRuleV4InputType.PROMQL.value,
        input_config={"promql": "sum(cpu_usage)", "bk_biz_ids": ["10", "11"], "bk_tenant_id": "wrong_tenant"},
        metric_name="cpu_usage_sum",
    )
    rule = create_rule(records=[record], apply_immediately=False)
    spec_record = rule.current_spec.records.get()
    external_api.check_promql.reset_mock()

    RecordRuleV4Resolver(rule, source="manual").run_check(spec_record)

    _, kwargs = external_api.check_promql.call_args
    assert kwargs["promql"] == "sum(cpu_usage)"
    assert kwargs["bk_tenant_id"] == TENANT_ID
    assert kwargs["space_uid"] == "bkcc__2"
    assert kwargs["bk_biz_ids"] == ["10", "11"]
    assert int(kwargs["end"]) - int(kwargs["start"]) == 3600


def test_query_ts_check_uses_rule_tenant_when_input_config_has_tenant(v4_base_data, external_api):
    input_config = build_query_config()
    input_config["bk_tenant_id"] = "wrong_tenant"
    record = build_record(input_config=input_config)
    rule = create_rule(records=[record], apply_immediately=False)
    spec_record = rule.current_spec.records.get()
    external_api.check_query_ts.reset_mock()

    RecordRuleV4Resolver(rule, source="manual").run_check(spec_record)

    _, kwargs = external_api.check_query_ts.call_args
    assert kwargs["bk_tenant_id"] == TENANT_ID
    assert kwargs["space_uid"] == "bkcc__2"


def test_check_resources_keep_scope_fields_for_headers():
    query_ts_params = CheckQueryTsResource().validate_request_data(
        {
            "query_list": [],
            "start_time": "1",
            "end_time": "2",
            "space_uid": "bkcc__2",
            "bk_tenant_id": TENANT_ID,
        }
    )
    promql_params = CheckQueryTsByPromqlResource().validate_request_data(
        {
            "promql": "sum(cpu_usage)",
            "start": "1",
            "end": "2",
            "space_uid": "bkcc__2",
            "bk_tenant_id": TENANT_ID,
            "bk_biz_ids": ["10", "11"],
        }
    )

    assert query_ts_params["bk_tenant_id"] == TENANT_ID
    assert query_ts_params["space_uid"] == "bkcc__2"
    assert promql_params["bk_tenant_id"] == TENANT_ID
    assert promql_params["space_uid"] == "bkcc__2"
    assert promql_params["bk_biz_ids"] == ["10", "11"]


def test_run_check_converts_structured_query_config_to_query_ts(v4_base_data, external_api):
    record = build_record(input_config=build_structured_query_config())
    rule = create_rule(records=[record], apply_immediately=False)
    spec_record = rule.current_spec.records.get()
    external_api.check_query_ts.reset_mock()

    RecordRuleV4Resolver(rule, source="manual").run_check(spec_record)

    _, kwargs = external_api.check_query_ts.call_args
    assert kwargs["bk_tenant_id"] == TENANT_ID
    assert kwargs["space_uid"] == "bkcc__2"
    assert kwargs["start_time"] == "1778935339"
    assert kwargs["end_time"] == "1778938939"
    assert kwargs["step"] == "60s"
    assert kwargs["order_by"] == ["-time"]
    assert kwargs["metric_merge"] == "a / b"
    assert kwargs["not_time_align"] is False
    for skipped_field in (
        "down_sample_range",
        "timezone",
        "instant",
        "reference",
        "limit",
        "add_dimensions",
    ):
        assert skipped_field not in kwargs

    first_query, second_query = kwargs["query_list"]
    assert first_query["table_id"] == "system.disk"
    assert first_query["field_name"] == "in_use"
    assert first_query["reference_name"] == "a"
    assert first_query["dimensions"] == ["bk_target_cloud_id"]
    assert first_query["time_aggregation"] == {"vargs_list": [], "function": "rate", "window": "2m", "position": 0}
    assert first_query["function"] == [{"method": "mean", "dimensions": ["bk_target_cloud_id"]}]
    assert first_query["conditions"] == {
        "field_list": [
            {"field_name": "mount_point", "value": ["/data1"], "op": "contains"},
            {"field_name": "bk_target_cloud_id", "value": ["0"], "op": "contains"},
        ],
        "condition_list": ["and"],
    }
    assert second_query["table_id"] == "system.cpu_summary"
    assert second_query["field_name"] == "usage"
    assert second_query["reference_name"] == "b"


def test_query_ts_resolve_uses_actual_vmrt_data(v4_base_data, external_api):
    disk_table_id = "system.disk"
    disk_vm_table_id = "2_vm_system_disk"
    disk_bkbase_table_name = "bkbase_system_disk"
    disk_metricql = (
        "avg by (bk_target_ip, bk_target_cloud_id, mount_point) "
        '(avg_over_time({bk_biz_id="42", result_table_id="2_vm_system_disk", __name__="in_use_value"}[1m]))'
    )
    create_source_vm_mapping(
        table_id=disk_table_id,
        vm_table_id=disk_vm_table_id,
        bkbase_table_name=disk_bkbase_table_name,
        cluster_id=v4_base_data.cluster.cluster_id,
        bkbase_table_id=disk_vm_table_id,
    )
    external_api.check_query_ts.return_value = build_check_result(
        metricql=disk_metricql,
        result_table_id=disk_vm_table_id,
    )

    rule = create_rule(records=[build_record(input_config=build_structured_query_config())])

    resolved_record = get_latest_resolved(rule).records.get()
    source_node = get_source_nodes(get_latest_flow(rule).flow_config)[0]
    assert resolved_record.metricql == disk_metricql
    assert resolved_record.src_vm_table_ids == [disk_vm_table_id]
    assert resolved_record.src_result_table_configs == [
        {
            "result_table_id": disk_table_id,
            "vm_result_table_id": disk_vm_table_id,
            "bkbase_result_table_name": disk_bkbase_table_name,
            "vm_storage_name": "monitor-opsystem",
        }
    ]
    assert source_node["data"]["name"] == disk_bkbase_table_name


def test_structured_query_config_uses_default_check_time_range(v4_base_data, external_api):
    input_config = build_structured_query_config()
    input_config.pop("start_time")
    input_config.pop("end_time")
    record = build_record(input_config=input_config)
    rule = create_rule(records=[record], apply_immediately=False)
    spec_record = rule.current_spec.records.get()
    external_api.check_query_ts.reset_mock()

    RecordRuleV4Resolver(rule, source="manual").run_check(spec_record)

    _, kwargs = external_api.check_query_ts.call_args
    assert int(kwargs["end_time"]) - int(kwargs["start_time"]) == 3600


def test_refresh_resolved_only_updates_latest_resolved(v4_base_data, external_api):
    rule = create_rule()
    applied_resolved_id = rule.applied_resolved_id
    external_api.apply_data_link.reset_mock()
    external_api.check_query_ts.return_value = build_check_result(metricql=CHANGED_METRICQL)

    resolved = RecordRuleV4Operator(rule, source="manual", operator="admin").refresh_resolved()

    rule.refresh_from_db()
    assert resolved is not None
    assert rule.current_spec.latest_resolved_id == resolved.pk
    assert rule.applied_resolved_id == applied_resolved_id
    assert rule.current_spec.latest_resolved_id != applied_resolved_id
    assert has_unapplied_resolved(rule) is True
    assert rule.status == RecordRuleV4Status.PENDING.value
    external_api.apply_data_link.assert_not_called()


def test_update_group_interval_and_labels_prepares_single_flow(v4_base_data, external_api):
    rule = create_rule()
    previous_spec_id = rule.current_spec_id
    previous_resolved_id = rule.current_spec.latest_resolved_id
    previous_flow_name = rule.flow_name
    external_api.apply_data_link.reset_mock()

    operator = RecordRuleV4Operator(rule, source="manual", operator="admin")
    operator.update_declaration(
        interval="5min",
        labels=[{"env": "prod"}],
    )
    operator.execute_declaration(auto_apply=False)

    rule.refresh_from_db()
    assert rule.current_spec_id != previous_spec_id
    assert rule.current_spec.latest_resolved_id != previous_resolved_id
    assert rule.current_spec.interval == "5min"
    assert rule.current_spec.labels == [{"env": "prod"}]
    assert get_latest_resolved(rule).records.get().labels == [{"env": "prod"}, {"scenario": "pytest"}]
    assert get_latest_flow(rule).resolved_id == rule.current_spec.latest_resolved_id
    assert rule.flow_name == previous_flow_name
    assert get_latest_flow(rule).flow_name == previous_flow_name
    assert has_unapplied_resolved(rule) is True
    external_api.apply_data_link.assert_not_called()


def test_resolved_unchanged_does_not_prepare_new_flow(v4_base_data, external_api):
    rule = create_rule(auto_refresh=True)
    latest_resolved_id = rule.current_spec.latest_resolved_id
    latest_flow_id = get_latest_flow(rule).pk
    external_api.apply_data_link.reset_mock()

    resolved = RecordRuleV4Operator(rule, source="scheduler").refresh_resolved()

    rule.refresh_from_db()
    assert resolved.pk == latest_resolved_id
    assert get_latest_flow(rule).pk == latest_flow_id
    assert has_unapplied_resolved(rule) is False
    external_api.apply_data_link.assert_not_called()


def test_refresh_resolved_skips_when_operation_lock_is_held(v4_base_data, external_api):
    rule = create_rule()
    token = rule.acquire_operation_lock(owner="scheduler", reason="reconcile", ttl_seconds=60)
    assert token
    external_api.check_query_ts.reset_mock()

    resolved = RecordRuleV4Operator(rule, source="manual", operator="admin").refresh_resolved()

    assert resolved is None
    external_api.check_query_ts.assert_not_called()
    event = RecordRuleV4Event.objects.get(
        rule=rule,
        event_type=EVENT_TYPE_OPERATION_SKIPPED,
        status=EVENT_STATUS_SKIPPED,
        reason=EVENT_REASON_OPERATION_LOCKED,
    )
    assert event.detail["operation"] == "refresh_resolved"
    assert event.detail["owner"] == "scheduler"
    assert event.detail["reason"] == "reconcile"
    rule.release_operation_lock(token)


def test_reconcile_does_not_apply_when_auto_refresh_is_disabled(v4_base_data, external_api):
    rule = create_rule(auto_refresh=False)
    external_api.apply_data_link.reset_mock()
    external_api.check_query_ts.return_value = build_check_result(metricql=CHANGED_METRICQL)

    changed = RecordRuleV4Operator(rule, source="scheduler").reconcile()

    rule.refresh_from_db()
    assert changed is True
    assert has_unapplied_resolved(rule) is True
    assert rule.applied_resolved_id != rule.current_spec.latest_resolved_id
    assert rule.status == RecordRuleV4Status.OUTDATED.value
    external_api.apply_data_link.assert_not_called()


def test_reconcile_applies_changed_resolved_when_auto_refresh_is_enabled(v4_base_data, external_api):
    rule = create_rule(auto_refresh=True)
    external_api.apply_data_link.reset_mock()
    external_api.check_query_ts.return_value = build_check_result(metricql=CHANGED_METRICQL)

    changed = RecordRuleV4Operator(rule, source="scheduler").reconcile()

    rule.refresh_from_db()
    assert changed is True
    assert has_unapplied_resolved(rule) is False
    assert rule.applied_resolved_id == rule.current_spec.latest_resolved_id
    assert get_latest_resolved(rule).records.get().metricql == CHANGED_METRICQL
    assert_flow_apply_only(external_api)


def test_stop_updates_runtime_status_without_new_spec_resolved_or_flow(v4_base_data, external_api):
    rule = create_rule()
    previous_spec_id = rule.current_spec_id
    previous_resolved_id = rule.current_spec.latest_resolved_id
    previous_flow_id = get_latest_flow(rule).pk
    previous_flow_hash = get_latest_flow(rule).content_hash
    external_api.check_query_ts.reset_mock()
    external_api.apply_data_link.reset_mock()

    operator = RecordRuleV4Operator(rule, source="manual", operator="admin")
    operator.update_declaration(desired_status=RecordRuleV4DesiredStatus.STOPPED.value)
    operator.execute_declaration(auto_apply=True)

    rule.refresh_from_db()
    flow = get_applied_flow(rule)
    assert rule.generation == 1
    assert rule.current_spec_id == previous_spec_id
    assert rule.current_spec.latest_resolved_id == previous_resolved_id
    assert get_latest_flow(rule).pk == previous_flow_id
    assert rule.desired_status == RecordRuleV4DesiredStatus.STOPPED.value
    assert rule.applied_desired_status == RecordRuleV4DesiredStatus.STOPPED.value
    assert flow.content_hash == previous_flow_hash
    assert flow.flow_config["spec"]["desired_status"] == RecordRuleV4DesiredStatus.STOPPED.value
    assert rule.status == RecordRuleV4Status.STOPPED.value
    external_api.check_query_ts.assert_not_called()
    assert_flow_apply_only(external_api)
    assert rule.events.filter(event_type=EVENT_TYPE_APPLY_STARTED, flow=flow).exists()
    assert rule.events.filter(event_type=EVENT_TYPE_APPLY_SUCCEEDED, flow=flow).exists()
    action_started = list(rule.events.filter(event_type=EVENT_TYPE_FLOW_ACTION_STARTED, flow=flow))
    action_succeeded = list(rule.events.filter(event_type=EVENT_TYPE_FLOW_ACTION_SUCCEEDED, flow=flow))
    assert any(event.detail["action_type"] == RecordRuleV4FlowActionType.STOP.value for event in action_started)
    assert any(event.detail["action_type"] == RecordRuleV4FlowActionType.STOP.value for event in action_succeeded)


def test_stop_without_applied_flow_records_apply_failure(v4_base_data, external_api):
    rule = create_rule()
    get_applied_flow(rule).delete()
    external_api.apply_data_link.reset_mock()

    operator = RecordRuleV4Operator(rule, source="manual", operator="admin")
    updated = operator.update_declaration(desired_status=RecordRuleV4DesiredStatus.STOPPED.value)
    operator.execute_declaration(auto_apply=True)
    updated.refresh_from_db()

    updated.refresh_from_db()
    assert updated.desired_status == RecordRuleV4DesiredStatus.STOPPED.value
    assert updated.applied_desired_status == RecordRuleV4DesiredStatus.RUNNING.value
    assert updated.status == RecordRuleV4Status.FAILED.value
    assert updated.get_condition(CONDITION_RECONCILED)["reason"] == "FlowMissing"
    assert updated.events.filter(event_type="apply.failed", reason="FlowMissing").exists()
    external_api.apply_data_link.assert_not_called()


def test_delete_removes_applied_flow(v4_base_data, external_api):
    rule = create_rule()
    applied_flow_name = get_applied_flow(rule).flow_name

    operator = RecordRuleV4Operator(rule, source="manual", operator="admin")
    operator.delete_declaration()
    operator.execute_declaration(auto_apply=True)

    rule.refresh_from_db()
    assert rule.desired_status == RecordRuleV4DesiredStatus.DELETED.value
    assert rule.status == RecordRuleV4Status.DELETED.value
    assert rule.deleted_at is not None
    assert rule.applied_resolved_id is None
    assert rule.applied_desired_status == RecordRuleV4DesiredStatus.DELETED.value
    external_api.delete_data_link.assert_called_once()
    _, kwargs = external_api.delete_data_link.call_args
    assert kwargs["name"] == applied_flow_name


def test_reconcile_retries_delete_even_when_auto_refresh_disabled(v4_base_data, external_api):
    rule = create_rule(auto_refresh=False)
    applied_flow_name = get_applied_flow(rule).flow_name
    rule.set_desired_status(RecordRuleV4DesiredStatus.DELETED.value)
    external_api.delete_data_link.reset_mock()

    ok = RecordRuleV4Operator(rule, source="scheduler").reconcile(auto_apply=False)

    rule.refresh_from_db()
    assert ok is True
    assert rule.status == RecordRuleV4Status.DELETED.value
    assert rule.deleted_at is not None
    external_api.delete_data_link.assert_called_once()
    _, kwargs = external_api.delete_data_link.call_args
    assert kwargs["name"] == applied_flow_name


def test_refresh_record_rule_v4_keeps_unfinished_deletes_due(v4_base_data, external_api):
    pending_deleted_rule = create_rule()
    completed_deleted_rule = create_rule()
    pending_deleted_flow_name = get_applied_flow(pending_deleted_rule).flow_name
    pending_deleted_rule.set_desired_status(RecordRuleV4DesiredStatus.DELETED.value)
    completed_deleted_rule.set_desired_status(RecordRuleV4DesiredStatus.DELETED.value)
    completed_deleted_rule.mark_delete_applied()
    external_api.delete_data_link.reset_mock()

    refresh_record_rule_v4()

    pending_deleted_rule.refresh_from_db()
    completed_deleted_rule.refresh_from_db()
    assert pending_deleted_rule.deleted_at is not None
    assert completed_deleted_rule.deleted_at is not None
    external_api.delete_data_link.assert_called_once()
    _, kwargs = external_api.delete_data_link.call_args
    assert kwargs["name"] == pending_deleted_flow_name


def test_refresh_record_rule_v4_calls_reconcile_with_default_auto_apply(v4_base_data, external_api, mocker):
    rule = create_rule(auto_refresh=False)
    rule.last_check_time = None
    rule.save(update_fields=["last_check_time", "updated_at"])
    reconcile = mocker.patch("metadata.task.record_rule_v4.RecordRuleV4Operator.reconcile", return_value=False)

    refresh_record_rule_v4()

    reconcile.assert_called_once_with()


def test_apply_failure_keeps_unapplied_resolved_and_records_action_error(v4_base_data, external_api):
    rule = create_rule(apply_immediately=False)
    flow = get_latest_flow(rule)
    external_api.apply_data_link.reset_mock()
    external_api.apply_data_link.side_effect = RuntimeError("bkbase unavailable")

    ok = RecordRuleV4Operator(rule, source="manual", operator="admin").execute_declaration(auto_apply=True)

    rule.refresh_from_db()
    assert ok is False
    assert rule.applied_resolved_id is None
    assert has_unapplied_resolved(rule) is True
    assert rule.get_condition(CONDITION_RECONCILED)["status"] == CONDITION_FALSE
    assert rule.get_condition(CONDITION_RECONCILED)["message"] == "bkbase unavailable"
    event = RecordRuleV4Event.objects.get(flow=flow, event_type="flow_action.failed")
    assert event.detail == {
        "action_type": RecordRuleV4FlowActionType.CREATE.value,
        "flow_id": flow.pk,
        "flow_name": flow.flow_name,
        "flow_content_hash": flow.content_hash,
    }


def test_declaration_change_makes_previous_flow_stale_without_external_side_effects(v4_base_data, external_api):
    rule = create_rule(apply_immediately=False)
    stale_flow = get_latest_flow(rule)
    external_api.space_redis.reset_mock()
    RecordRuleV4Operator(rule, source="manual", operator="admin").update_declaration(
        records=[build_record(metric_name="cpu_usage_v2")],
        raw_config={"records": [build_record(metric_name="cpu_usage_v2")]},
    )
    external_api.apply_data_link.reset_mock()

    is_current = RecordRuleV4Runner(rule, source="manual", operator="admin").is_flow_current(stale_flow)

    assert is_current is False
    external_api.space_redis.push_space_table_ids.assert_not_called()
    external_api.space_redis.push_table_id_detail.assert_not_called()
    external_api.apply_data_link.assert_not_called()


def test_resolve_failure_keeps_last_applied_flow(v4_base_data, external_api):
    rule = create_rule()
    applied_resolved_id = rule.applied_resolved_id
    latest_resolved_id = rule.current_spec.latest_resolved_id
    external_api.check_query_ts.side_effect = RuntimeError("unify-query unavailable")

    resolved = RecordRuleV4Operator(rule, source="scheduler").refresh_resolved()

    rule.refresh_from_db()
    assert resolved is None
    assert rule.applied_resolved_id == applied_resolved_id
    assert rule.current_spec.latest_resolved_id == latest_resolved_id
    assert rule.get_condition(CONDITION_RESOLVED)["status"] == CONDITION_FALSE
    assert rule.get_condition(CONDITION_RESOLVED)["message"] == "unify-query unavailable"
    assert rule.status == RecordRuleV4Status.FAILED.value


@pytest.mark.parametrize(
    ("check_result", "error_text"),
    [
        ({"data": []}, "data is empty"),
        ({"data": [{"metricql": METRICQL, "result_table_id": [SOURCE_VM_TABLE_ID]}]}, "storage_type"),
        (build_check_result(storage_type="influxdb"), "storage_type"),
        (
            {
                "data": [
                    {
                        "storage_type": "victoria_metrics",
                        "metricql": METRICQL,
                        "result_table_id": [SOURCE_VM_TABLE_ID],
                    },
                    {
                        "storage_type": "victoria_metrics",
                        "metricql": CHANGED_METRICQL,
                        "result_table_id": [SOURCE_VM_TABLE_ID],
                    },
                ]
            },
            "multiple metricql",
        ),
    ],
)
def test_resolve_fails_when_check_data_is_invalid(v4_base_data, external_api, check_result, error_text):
    external_api.check_query_ts.return_value = check_result

    rule = create_rule(apply_immediately=False)

    rule.refresh_from_db()
    assert rule.current_spec.latest_resolved_id is None
    assert rule.get_latest_flow() is None
    assert rule.get_condition(CONDITION_RESOLVED)["status"] == CONDITION_FALSE
    assert error_text in rule.get_condition(CONDITION_RESOLVED)["message"]
    assert_output_apply_only(external_api)


def test_resolve_fails_when_source_result_table_config_missing(v4_base_data, external_api):
    models.ResultTableConfig.objects.filter(
        bk_tenant_id=TENANT_ID,
        namespace=RECORD_RULE_V4_BKMONITOR_NAMESPACE,
        table_id=SOURCE_TABLE_ID,
    ).delete()

    rule = create_rule(apply_immediately=False)

    rule.refresh_from_db()
    assert rule.current_spec.latest_resolved_id is None
    assert rule.get_latest_flow() is None
    assert rule.get_condition(CONDITION_RESOLVED)["status"] == CONDITION_FALSE
    assert "ResultTableConfig" in rule.get_condition(CONDITION_RESOLVED)["message"]
    assert_output_apply_only(external_api)


def test_resolve_fails_when_source_vm_cluster_missing(v4_base_data, external_api):
    missing_cluster_vm_table_id = "2_missing_cluster_vm_table"
    create_source_vm_mapping(
        table_id="system.missing_cluster",
        vm_table_id=missing_cluster_vm_table_id,
        bkbase_table_name="bkbase_system_missing_cluster",
        cluster_id=9999,
    )
    external_api.check_query_ts.return_value = build_check_result(result_table_id=missing_cluster_vm_table_id)

    rule = create_rule(apply_immediately=False)

    rule.refresh_from_db()
    assert rule.current_spec.latest_resolved_id is None
    assert rule.get_condition(CONDITION_RESOLVED)["status"] == CONDITION_FALSE
    assert "ClusterInfo" in rule.get_condition(CONDITION_RESOLVED)["message"]
    assert_output_apply_only(external_api)


def test_self_referenced_precalculated_vm_table_is_excluded_from_source(v4_base_data, external_api):
    rule = create_rule()
    resolver = RecordRuleV4Resolver(rule, source="manual")
    rule_table_base = rule.table_id.split(".", 1)[0]

    src_vm_table_ids = resolver.normalize_src_vm_table_ids(
        [SOURCE_TABLE_ID, SOURCE_VM_TABLE_ID, rule.table_id, rule_table_base, rule.dst_vm_table_id]
    )

    assert src_vm_table_ids == [SOURCE_VM_TABLE_ID]


def test_refresh_flow_health_maps_flow_status_to_group_condition(v4_base_data, external_api):
    rule = create_rule()
    external_api.get_data_link.return_value = {"status": {"state": "not-ok"}}

    status = RecordRuleV4Operator(rule, source="scheduler").refresh_flow_health()

    rule.refresh_from_db()
    assert status == RecordRuleV4FlowStatus.ABNORMAL.value
    assert rule.get_condition(CONDITION_FLOW_HEALTHY)["status"] == CONDITION_FALSE
    assert rule.status == RecordRuleV4Status.FAILED.value
    assert get_applied_flow(rule).flow_status == RecordRuleV4FlowStatus.ABNORMAL.value

    external_api.get_data_link.side_effect = RuntimeError("404 not found")
    status = RecordRuleV4Operator(rule, source="scheduler").refresh_flow_health()

    rule.refresh_from_db()
    assert status == RecordRuleV4FlowStatus.NOT_FOUND.value
    assert rule.get_condition(CONDITION_FLOW_HEALTHY)["reason"] == RecordRuleV4FlowStatus.NOT_FOUND.value


def test_duplicate_metric_name_is_allowed(v4_base_data, external_api):
    duplicated = [
        build_record(metric_name="cpu_usage_avg"),
        build_record(metric_name="cpu_usage_avg"),
    ]

    rule = create_rule(records=duplicated, apply_immediately=False)

    records = list(rule.current_spec.records.order_by("source_index"))
    assert [record.metric_name for record in records] == ["cpu_usage_avg", "cpu_usage_avg"]
    assert records[0].record_key != records[1].record_key
