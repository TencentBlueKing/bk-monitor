"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from types import SimpleNamespace

import pytest

from metadata import models
from metadata.models.record_rule.constants import (
    RECORD_RULE_V4_BKBASE_NAMESPACE,
    RECORD_RULE_V4_BKMONITOR_NAMESPACE,
    RECORD_RULE_V4_DEFAULT_TENANT,
    RecordRuleV4ApplyStatus,
    RecordRuleV4DeploymentStrategy,
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
    RecordRuleV4,
    RecordRuleV4Deployment,
    RecordRuleV4Event,
)
from metadata.models.record_rule.v4.operator import RecordRuleV4Operator
from metadata.models.record_rule.v4.output import RecordRuleV4OutputResources
from metadata.models.record_rule.v4.resolver import RecordRuleV4Resolver
from metadata.models.record_rule.v4.source import resolve_vm_result_table_configs

pytestmark = pytest.mark.django_db(databases="__all__")

TENANT_ID = "system"
SPACE_TYPE = "bkcc"
SPACE_ID = "2"
GROUP_NAME = "rr_cpu_group"
SOURCE_TABLE_ID = "system.cpu_summary"
SOURCE_VM_TABLE_ID = "2_system_cpu_summary"
SOURCE_BKBASE_TABLE_NAME = "bkbase_system_cpu_summary"
SECOND_SOURCE_TABLE_ID = "system.cpu_detail"
SECOND_SOURCE_VM_TABLE_ID = "2_system_cpu_detail"
SECOND_SOURCE_BKBASE_TABLE_NAME = "bkbase_system_cpu_detail"
METRICQL = 'avg by (bk_target_ip) ({bk_biz_id="2", result_table_id="2_system_cpu_summary", __name__="usage"})'
CHANGED_METRICQL = f"sum({METRICQL})"


@pytest.fixture
def v4_base_data(settings):
    settings.DEFAULT_BKDATA_BIZ_ID = 2
    settings.BK_DATA_PROJECT_MAINTAINER = "admin"
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
    models.AccessVMRecord.objects.create(
        bk_tenant_id=TENANT_ID,
        result_table_id=SOURCE_TABLE_ID,
        bk_base_data_id=100,
        vm_result_table_id=SOURCE_VM_TABLE_ID,
        vm_cluster_id=cluster.cluster_id,
    )
    models.ResultTableConfig.objects.create(
        bk_tenant_id=TENANT_ID,
        namespace=RECORD_RULE_V4_BKMONITOR_NAMESPACE,
        name=SOURCE_BKBASE_TABLE_NAME,
        data_link_name=SOURCE_BKBASE_TABLE_NAME,
        table_id=SOURCE_TABLE_ID,
        bk_biz_id=int(SPACE_ID),
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
        "metadata.models.record_rule.v4.deployment.runner.api.bkdata.apply_data_link",
        return_value={"status": "ok"},
    )
    delete_data_link = mocker.patch(
        "metadata.models.record_rule.v4.deployment.runner.api.bkdata.delete_data_link",
        return_value={"status": "deleted"},
    )
    get_data_link = mocker.patch(
        "metadata.models.record_rule.v4.deployment.runner.api.bkdata.get_data_link",
        return_value={"status": {"state": "ok"}},
    )
    return SimpleNamespace(
        check_query_ts=check_query_ts,
        check_promql=check_promql,
        apply_data_link=apply_data_link,
        delete_data_link=delete_data_link,
        get_data_link=get_data_link,
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


def create_rule(
    *,
    records: list[dict] | None = None,
    strategy: str | dict | None = None,
    interval: str = "1min",
    labels: list[dict] | None = None,
    auto_refresh: bool = True,
    apply_immediately: bool = True,
) -> RecordRuleV4:
    records = records or [build_record()]
    group_labels = labels or []
    strategy = strategy or RecordRuleV4DeploymentStrategy.PER_RECORD.value
    return RecordRuleV4Operator.create(
        bk_tenant_id=TENANT_ID,
        space_type=SPACE_TYPE,
        space_id=SPACE_ID,
        group_name=GROUP_NAME,
        records=records,
        raw_config={"records": records, "interval": interval, "labels": group_labels},
        interval=interval,
        labels=group_labels,
        deployment_strategy=strategy,
        auto_refresh=auto_refresh,
        source="pytest",
        operator="tester",
        apply_immediately=apply_immediately,
    )


def get_recording_rule_node(flow_config: dict) -> dict:
    for node in flow_config["spec"]["nodes"]:
        if node["kind"] == "RecordingRuleNode":
            return node
    raise AssertionError("RecordingRuleNode not found")


def get_source_nodes(flow_config: dict) -> list[dict]:
    return [node for node in flow_config["spec"]["nodes"] if node["kind"] == "VmSourceNode"]


def test_create_group_with_two_records_applies_per_record_flows(v4_base_data, external_api):
    records = [
        build_record(metric_name="cpu_usage_avg"),
        build_record(metric_name="cpu_total_sum"),
    ]

    rule = create_rule(records=records)

    rule.refresh_from_db()
    assert len(rule.table_id) <= 50
    assert len(rule.dst_vm_table_id) <= 50
    assert rule.table_id.startswith("bkprecal_rr_cpu_group_")
    assert rule.latest_resolved.records.count() == 2
    assert rule.latest_resolved.flows.count() == 2
    assert len(rule.latest_deployment.plan_config["actions"]) == 2
    assert rule.latest_deployment_id == rule.applied_deployment_id
    assert rule.status == RecordRuleV4Status.RUNNING.value
    assert rule.update_available is False

    flows = list(rule.latest_resolved.flows.order_by("id"))
    assert {flow.table_id for flow in flows} == {rule.table_id}
    assert {flow.dst_vm_table_id for flow in flows} == {rule.dst_vm_table_id}
    assert len({flow.flow_name for flow in flows}) == 2
    assert all(len(flow.flow_name) <= 50 for flow in flows)
    assert all(flow.records.count() == 1 for flow in flows)
    assert set(rule.latest_resolved.records.values_list("flow_id", flat=True)) == {flow.pk for flow in flows}

    first_source_node = get_source_nodes(flows[0].flow_config)[0]
    assert first_source_node["data"]["name"] == SOURCE_BKBASE_TABLE_NAME
    first_node = get_recording_rule_node(flows[0].flow_config)
    assert first_node["inputs"] == ["vm_source"]
    assert first_node["output"] == rule.dst_vm_table_id
    assert first_node["config"][0]["interval"] == rule.current_spec.interval
    assert first_node["config"][0]["labels"] == [{"scenario": "pytest"}]
    assert first_node["storage"] == {
        "kind": "VmStorage",
        "tenant": RECORD_RULE_V4_DEFAULT_TENANT,
        "namespace": RECORD_RULE_V4_BKMONITOR_NAMESPACE,
        "name": "monitor-opsystem",
    }
    assert flows[0].flow_config["metadata"]["namespace"] == RECORD_RULE_V4_BKBASE_NAMESPACE

    assert external_api.check_query_ts.call_count == 2
    assert external_api.apply_data_link.call_count == 2
    first_resolved_record = rule.latest_resolved.records.order_by("id").first()
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


def test_single_flow_strategy_groups_records_into_one_flow(v4_base_data, external_api):
    records = [
        build_record(metric_name="cpu_usage_avg"),
        build_record(metric_name="cpu_total_sum"),
    ]
    strategy_config = {
        "strategy": RecordRuleV4DeploymentStrategy.SINGLE_FLOW.value,
        "options": {"unit": "pytest"},
    }

    rule = create_rule(records=records, strategy=strategy_config)

    flow = rule.latest_resolved.flows.get()
    source_node = get_source_nodes(flow.flow_config)[0]
    recording_rule_node = get_recording_rule_node(flow.flow_config)
    assert rule.current_spec.deployment_strategy == strategy_config
    assert rule.latest_deployment.plan_config["strategy"] == strategy_config
    assert rule.latest_resolved.records.count() == 2
    assert flow.flow_key == "group"
    assert flow.strategy == RecordRuleV4DeploymentStrategy.SINGLE_FLOW.value
    assert rule.latest_deployment.strategy == RecordRuleV4DeploymentStrategy.SINGLE_FLOW.value
    assert flow.records.count() == 2
    assert source_node["data"]["name"] == SOURCE_BKBASE_TABLE_NAME
    assert [item["metric_name"] for item in recording_rule_node["config"]] == ["cpu_usage_avg", "cpu_total_sum"]
    assert external_api.apply_data_link.call_count == 1


def test_group_interval_and_labels_merge_into_resolved_and_flow(v4_base_data, external_api):
    record = build_record(labels=[{"scenario": "record"}, {"owner": "record"}])

    rule = create_rule(
        records=[record],
        interval="5min",
        labels=[{"scenario": "group"}, {"env": "prod"}],
    )

    resolved_record = rule.latest_resolved.records.get()
    recording_rule_node = get_recording_rule_node(rule.latest_resolved.flows.get().flow_config)
    expected_labels = [{"scenario": "record"}, {"env": "prod"}, {"owner": "record"}]
    assert rule.current_spec.interval == "5min"
    assert rule.current_spec.labels == [{"scenario": "group"}, {"env": "prod"}]
    assert resolved_record.labels == expected_labels
    assert recording_rule_node["config"][0]["interval"] == "5min"
    assert recording_rule_node["config"][0]["labels"] == expected_labels


def test_update_deployment_strategy_replans_without_resolve(v4_base_data, external_api):
    records = [
        build_record(metric_name="cpu_usage_avg"),
        build_record(metric_name="cpu_total_sum"),
    ]
    rule = create_rule(records=records)
    previous_resolved_id = rule.latest_resolved_id
    strategy_config = {"strategy": RecordRuleV4DeploymentStrategy.SINGLE_FLOW.value, "options": {"unit": "pytest"}}
    external_api.check_query_ts.reset_mock()
    external_api.apply_data_link.reset_mock()

    RecordRuleV4Operator(rule, source="manual", operator="admin").update_spec(
        deployment_strategy=strategy_config,
        apply_immediately=False,
    )

    rule.refresh_from_db()
    action_types = sorted(action["action_type"] for action in rule.latest_deployment.plan_config["actions"])
    assert rule.latest_resolved_id == previous_resolved_id
    assert rule.current_spec.deployment_strategy == strategy_config
    assert rule.latest_deployment.strategy == RecordRuleV4DeploymentStrategy.SINGLE_FLOW.value
    assert rule.latest_deployment.plan_config["strategy"] == strategy_config
    assert action_types == [
        RecordRuleV4FlowActionType.CREATE.value,
        RecordRuleV4FlowActionType.DELETE.value,
        RecordRuleV4FlowActionType.DELETE.value,
    ]
    assert rule.update_available is True
    external_api.check_query_ts.assert_not_called()
    external_api.apply_data_link.assert_not_called()


def test_update_raw_config_alone_does_not_create_spec(v4_base_data, external_api):
    rule = create_rule(apply_immediately=False)
    current_spec_id = rule.current_spec_id
    current_generation = rule.generation
    external_api.check_query_ts.reset_mock()

    updated = RecordRuleV4Operator(rule, source="manual", operator="admin").update_spec(
        raw_config={"records": [], "from": "ui_snapshot"},
        apply_immediately=False,
    )

    updated.refresh_from_db()
    assert updated.current_spec_id == current_spec_id
    assert updated.generation == current_generation
    external_api.check_query_ts.assert_not_called()


def test_create_allows_duplicate_group_name_with_random_output_names(v4_base_data, external_api):
    first = create_rule(apply_immediately=False)
    second = create_rule(apply_immediately=False)

    assert first.group_name == second.group_name == GROUP_NAME
    assert first.table_id != second.table_id
    assert first.dst_vm_table_id != second.dst_vm_table_id


def test_create_prepares_output_metadata_before_apply(v4_base_data, external_api):
    rule = create_rule(apply_immediately=False)

    assert models.ResultTable.objects.filter(table_id=rule.table_id, bk_tenant_id=TENANT_ID).exists()
    output_config = models.ResultTableConfig.objects.get(table_id=rule.table_id, bk_tenant_id=TENANT_ID)
    assert output_config.name == RecordRuleV4OutputResources.compose_result_table_config_name(rule.table_id)
    assert output_config.data_link_name == output_config.name
    assert output_config.bkbase_table_id == rule.dst_vm_table_id
    assert rule.dst_vm_table_id == f"{output_config.datalink_biz_ids.data_biz_id}_{output_config.name}"
    assert models.AccessVMRecord.objects.filter(
        result_table_id=rule.table_id,
        vm_result_table_id=rule.dst_vm_table_id,
        bk_tenant_id=TENANT_ID,
        vm_cluster_id=v4_base_data.cluster.cluster_id,
    ).exists()
    assert models.ResultTableField.objects.filter(
        table_id=rule.table_id,
        bk_tenant_id=TENANT_ID,
        field_name="cpu_usage_avg",
    ).exists()
    external_api.apply_data_link.assert_not_called()


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
        table_id=SOURCE_TABLE_ID,
        bkbase_table_id=SOURCE_VM_TABLE_ID,
        bk_biz_id=int(SPACE_ID),
    )

    configs = resolve_vm_result_table_configs(
        bk_tenant_id=TENANT_ID,
        vm_result_table_ids=[SOURCE_VM_TABLE_ID],
    )

    assert configs[0]["bkbase_result_table_name"] == direct_bkbase_table_name
    assert configs[0]["result_table_id"] == SOURCE_TABLE_ID
    assert configs[0]["vm_storage_name"] == "monitor-opsystem"


def test_resolve_vm_result_table_configs_keeps_order_and_source_storage(v4_base_data):
    second_cluster = models.ClusterInfo.objects.create(
        bk_tenant_id=TENANT_ID,
        cluster_id=1002,
        cluster_name="monitor-secondary",
        cluster_type=models.ClusterInfo.TYPE_VM,
        domain_name="vm-secondary.service.local",
        port=9090,
        description="secondary vm",
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

    assert configs == [
        {
            "result_table_id": SECOND_SOURCE_TABLE_ID,
            "vm_result_table_id": SECOND_SOURCE_VM_TABLE_ID,
            "bkbase_result_table_name": SECOND_SOURCE_BKBASE_TABLE_NAME,
            "vm_storage_name": "monitor-secondary",
        },
        {
            "result_table_id": SOURCE_TABLE_ID,
            "vm_result_table_id": SOURCE_VM_TABLE_ID,
            "bkbase_result_table_name": SOURCE_BKBASE_TABLE_NAME,
            "vm_storage_name": "monitor-opsystem",
        },
    ]


def test_spec_record_key_falls_back_to_metric_name_when_input_key_is_hidden(v4_base_data, external_api):
    rule = create_rule(apply_immediately=False)
    original_record = rule.current_spec.records.get()

    changed_record = build_record(input_config={**build_query_config(), "step": "5m"})
    RecordRuleV4Operator(rule, source="manual", operator="admin").update_spec(
        records=[changed_record],
        raw_config={"records": [changed_record]},
        apply_immediately=False,
    )

    rule.refresh_from_db()
    next_record = rule.current_spec.records.get()
    assert next_record.record_key == original_record.record_key
    assert next_record.input_type == original_record.input_type
    assert next_record.metric_name == original_record.metric_name
    assert next_record.content_hash != original_record.content_hash


def test_spec_record_key_prefers_input_config_when_metric_name_repeats(v4_base_data, external_api):
    config_a = build_query_config()
    config_b = {**build_query_config(), "step": "5m"}
    records = [
        build_record(metric_name="cpu_usage_avg", input_config=config_a),
        build_record(metric_name="cpu_usage_avg", input_config=config_b),
    ]
    rule = create_rule(records=records, apply_immediately=False)
    original_records = list(rule.current_spec.records.order_by("source_index"))

    swapped_records = [
        build_record(metric_name="cpu_usage_avg", input_config=config_b),
        build_record(metric_name="cpu_usage_avg", input_config=config_a),
    ]
    RecordRuleV4Operator(rule, source="manual", operator="admin").update_spec(
        records=swapped_records,
        raw_config={"records": swapped_records},
        apply_immediately=False,
    )

    rule.refresh_from_db()
    next_records = list(rule.current_spec.records.order_by("source_index"))
    assert next_records[0].record_key == original_records[1].record_key
    assert next_records[1].record_key == original_records[0].record_key


def test_run_check_dispatches_promql_input_to_promql_api(v4_base_data, external_api):
    record = build_record(
        input_type=RecordRuleV4InputType.PROMQL.value,
        input_config={"promql": "sum(cpu_usage)", "start": "1", "end": "2"},
        metric_name="cpu_usage_sum",
    )
    rule = create_rule(records=[record], apply_immediately=False)
    spec_record = rule.current_spec.records.get()
    external_api.check_query_ts.reset_mock()
    external_api.check_promql.reset_mock()

    result = RecordRuleV4Resolver(rule, source="manual").run_check(spec_record)

    assert result["data"][0]["metricql"] == "promql_metricql"
    external_api.check_promql.assert_called_once_with(
        bk_tenant_id=TENANT_ID,
        promql="sum(cpu_usage)",
        start="1",
        end="2",
    )
    external_api.check_query_ts.assert_not_called()


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

    resolved_record = rule.latest_resolved.records.get()
    source_node_names = {
        node["data"]["name"] for node in get_source_nodes(rule.latest_resolved.flows.get().flow_config)
    }
    assert resolved_record.metricql == metricql
    assert resolved_record.src_vm_table_ids == [SOURCE_VM_TABLE_ID, SECOND_SOURCE_VM_TABLE_ID]
    assert source_node_names == {SOURCE_BKBASE_TABLE_NAME, SECOND_SOURCE_BKBASE_TABLE_NAME}


def test_promql_check_uses_default_time_range(v4_base_data, external_api):
    record = build_record(
        input_type=RecordRuleV4InputType.PROMQL.value,
        input_config={"promql": "sum(cpu_usage)"},
        metric_name="cpu_usage_sum",
    )
    rule = create_rule(records=[record], apply_immediately=False)
    spec_record = rule.current_spec.records.get()
    external_api.check_promql.reset_mock()

    RecordRuleV4Resolver(rule, source="manual").run_check(spec_record)

    _, kwargs = external_api.check_promql.call_args
    assert kwargs["promql"] == "sum(cpu_usage)"
    assert int(kwargs["end"]) - int(kwargs["start"]) == 3600


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

    resolved_record = rule.latest_resolved.records.get()
    source_node = get_source_nodes(rule.latest_resolved.flows.get().flow_config)[0]
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


def test_manual_refresh_only_marks_update_available(v4_base_data, external_api):
    rule = create_rule()
    applied_deployment_id = rule.applied_deployment_id
    external_api.apply_data_link.reset_mock()
    external_api.check_query_ts.return_value = build_check_result(metricql=CHANGED_METRICQL)

    resolved = RecordRuleV4Operator(rule, source="manual", operator="admin").manual_refresh()

    rule.refresh_from_db()
    assert resolved is not None
    assert rule.latest_resolved_id == resolved.pk
    assert rule.applied_deployment_id == applied_deployment_id
    assert rule.latest_deployment_id != applied_deployment_id
    assert rule.update_available is True
    assert rule.status == RecordRuleV4Status.PENDING.value
    external_api.apply_data_link.assert_not_called()


def test_update_group_interval_and_labels_replans_without_record_changes(v4_base_data, external_api):
    rule = create_rule()
    previous_spec_id = rule.current_spec_id
    previous_resolved_id = rule.latest_resolved_id
    external_api.apply_data_link.reset_mock()

    RecordRuleV4Operator(rule, source="manual", operator="admin").update_spec(
        interval="5min",
        labels=[{"env": "prod"}],
        apply_immediately=False,
    )

    rule.refresh_from_db()
    assert rule.current_spec_id != previous_spec_id
    assert rule.latest_resolved_id != previous_resolved_id
    assert rule.current_spec.interval == "5min"
    assert rule.current_spec.labels == [{"env": "prod"}]
    assert rule.latest_resolved.records.get().labels == [{"env": "prod"}, {"scenario": "pytest"}]
    assert rule.latest_deployment.plan_config["actions"][0]["action_type"] == RecordRuleV4FlowActionType.UPDATE.value
    assert rule.update_available is True
    external_api.apply_data_link.assert_not_called()


def test_resolved_unchanged_does_not_replan_because_flow_template_is_not_the_comparison_source(
    v4_base_data, external_api
):
    rule = create_rule(auto_refresh=True)
    latest_resolved_id = rule.latest_resolved_id
    latest_deployment_id = rule.latest_deployment_id
    external_api.apply_data_link.reset_mock()

    resolved = RecordRuleV4Operator(rule, source="scheduler").manual_refresh()

    rule.refresh_from_db()
    assert resolved.pk == latest_resolved_id
    assert rule.latest_deployment_id == latest_deployment_id
    assert rule.update_available is False
    assert external_api.apply_data_link.call_count == 0


def test_manual_refresh_skips_when_operation_lock_is_held(v4_base_data, external_api):
    rule = create_rule()
    token = rule.acquire_operation_lock(owner="scheduler", reason="reconcile", ttl_seconds=60)
    assert token
    external_api.check_query_ts.reset_mock()

    resolved = RecordRuleV4Operator(rule, source="manual", operator="admin").manual_refresh()

    assert resolved is None
    external_api.check_query_ts.assert_not_called()
    event = RecordRuleV4Event.objects.get(
        rule=rule,
        event_type=EVENT_TYPE_OPERATION_SKIPPED,
        status=EVENT_STATUS_SKIPPED,
        reason=EVENT_REASON_OPERATION_LOCKED,
    )
    assert event.detail["operation"] == "manual_refresh"
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
    assert rule.update_available is True
    assert rule.applied_deployment_id != rule.latest_deployment_id
    assert rule.status == RecordRuleV4Status.OUTDATED.value
    external_api.apply_data_link.assert_not_called()


def test_reconcile_applies_changed_resolved_when_auto_refresh_is_enabled(v4_base_data, external_api):
    rule = create_rule(auto_refresh=True)
    external_api.apply_data_link.reset_mock()
    external_api.check_query_ts.return_value = build_check_result(metricql=CHANGED_METRICQL)

    changed = RecordRuleV4Operator(rule, source="scheduler").reconcile()

    rule.refresh_from_db()
    assert changed is True
    assert rule.update_available is False
    assert rule.applied_deployment_id == rule.latest_deployment_id
    assert rule.latest_resolved.records.get().metricql == CHANGED_METRICQL
    external_api.apply_data_link.assert_called_once()


def test_stop_updates_runtime_status_without_new_spec_resolved_or_plan(v4_base_data, external_api):
    rule = create_rule()
    previous_spec_id = rule.current_spec_id
    previous_resolved_id = rule.latest_resolved_id
    previous_deployment_id = rule.latest_deployment_id
    external_api.check_query_ts.reset_mock()
    external_api.apply_data_link.reset_mock()

    RecordRuleV4Operator(rule, source="manual", operator="admin").update_spec(
        desired_status=RecordRuleV4DesiredStatus.STOPPED.value
    )

    rule.refresh_from_db()
    flow = rule.latest_resolved.flows.get()
    assert rule.generation == 1
    assert rule.observed_generation == 1
    assert rule.current_spec_id == previous_spec_id
    assert rule.latest_resolved_id == previous_resolved_id
    assert rule.latest_deployment_id == previous_deployment_id
    assert rule.desired_status == RecordRuleV4DesiredStatus.STOPPED.value
    assert flow.desired_status == RecordRuleV4DesiredStatus.STOPPED.value
    assert flow.flow_config["spec"]["desired_status"] == RecordRuleV4DesiredStatus.STOPPED.value
    assert rule.status == RecordRuleV4Status.STOPPED.value
    external_api.check_query_ts.assert_not_called()
    external_api.apply_data_link.assert_called_once()


def test_delete_creates_delete_actions_for_applied_flows(v4_base_data, external_api):
    records = [
        build_record(metric_name="cpu_usage_avg"),
        build_record(metric_name="cpu_total_sum"),
    ]
    rule = create_rule(records=records)
    applied_flow_names = sorted(rule.applied_deployment.resolved.flows.values_list("flow_name", flat=True))

    RecordRuleV4Operator(rule, source="manual", operator="admin").delete()

    rule.refresh_from_db()
    delete_actions = sorted(rule.latest_deployment.plan_config["actions"], key=lambda action: action["flow_name"])
    assert rule.desired_status == RecordRuleV4DesiredStatus.DELETED.value
    assert rule.status == RecordRuleV4Status.DELETED.value
    assert rule.deleted_at is not None
    assert [action["flow_name"] for action in delete_actions] == applied_flow_names
    assert all(action["action_type"] == RecordRuleV4FlowActionType.DELETE.value for action in delete_actions)
    assert external_api.delete_data_link.call_count == 2


def test_apply_failure_keeps_update_available_and_records_action_error(v4_base_data, external_api):
    rule = create_rule(apply_immediately=False)
    external_api.apply_data_link.side_effect = RuntimeError("bkbase unavailable")

    ok = RecordRuleV4Operator(rule, source="manual", operator="admin").apply()

    rule.refresh_from_db()
    deployment = RecordRuleV4Deployment.objects.get(pk=rule.latest_deployment_id)
    assert ok is False
    assert deployment.apply_status == RecordRuleV4ApplyStatus.FAILED.value
    assert rule.update_available is True
    assert rule.last_error == "bkbase unavailable"
    assert rule.get_condition(CONDITION_RECONCILED)["status"] == CONDITION_FALSE
    assert RecordRuleV4Event.objects.filter(deployment=deployment, event_type="flow_action.failed").exists()


def test_apply_skips_stale_deployment_before_calling_bkbase(v4_base_data, external_api):
    rule = create_rule(apply_immediately=False)
    stale_deployment = rule.latest_deployment
    RecordRuleV4Operator(rule, source="manual", operator="admin").update_spec(
        records=[build_record(metric_name="cpu_usage_v2")],
        raw_config={"records": [build_record(metric_name="cpu_usage_v2")]},
        apply_immediately=False,
    )
    assert models.ResultTableField.objects.filter(
        table_id=rule.table_id,
        bk_tenant_id=TENANT_ID,
        field_name="cpu_usage_v2",
    ).exists()
    external_api.apply_data_link.reset_mock()

    ok = RecordRuleV4Operator(rule, source="manual", operator="admin").apply(stale_deployment)

    assert ok is False
    external_api.apply_data_link.assert_not_called()


def test_resolve_failure_keeps_last_applied_deployment(v4_base_data, external_api):
    rule = create_rule()
    applied_deployment_id = rule.applied_deployment_id
    latest_resolved_id = rule.latest_resolved_id
    external_api.check_query_ts.side_effect = RuntimeError("unify-query unavailable")

    resolved = RecordRuleV4Operator(rule, source="scheduler").manual_refresh()

    rule.refresh_from_db()
    assert resolved is None
    assert rule.applied_deployment_id == applied_deployment_id
    assert rule.latest_resolved_id == latest_resolved_id
    assert rule.last_error == "unify-query unavailable"
    assert rule.get_condition(CONDITION_RESOLVED)["status"] == CONDITION_FALSE
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
    assert rule.latest_resolved_id is None
    assert rule.get_condition(CONDITION_RESOLVED)["status"] == CONDITION_FALSE
    assert error_text in rule.last_error
    external_api.apply_data_link.assert_not_called()


def test_resolve_fails_when_source_result_table_config_missing(v4_base_data, external_api):
    models.ResultTableConfig.objects.filter(
        bk_tenant_id=TENANT_ID,
        namespace=RECORD_RULE_V4_BKMONITOR_NAMESPACE,
        table_id=SOURCE_TABLE_ID,
    ).delete()

    rule = create_rule(apply_immediately=False)

    rule.refresh_from_db()
    assert rule.latest_resolved_id is None
    assert rule.latest_deployment_id is None
    assert rule.get_condition(CONDITION_RESOLVED)["status"] == CONDITION_FALSE
    assert "ResultTableConfig" in rule.last_error
    external_api.apply_data_link.assert_not_called()


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
    assert rule.latest_resolved_id is None
    assert rule.get_condition(CONDITION_RESOLVED)["status"] == CONDITION_FALSE
    assert "ClusterInfo" in rule.last_error
    external_api.apply_data_link.assert_not_called()


def test_self_referenced_precalculated_vm_table_is_excluded_from_source(v4_base_data, external_api):
    rule = create_rule()
    resolver = RecordRuleV4Resolver(rule, source="manual")

    src_vm_table_ids = resolver.normalize_src_vm_table_ids(
        [SOURCE_TABLE_ID, SOURCE_VM_TABLE_ID, rule.table_id, rule.dst_vm_table_id]
    )

    assert src_vm_table_ids == [SOURCE_VM_TABLE_ID]


def test_refresh_flow_health_maps_each_flow_status_to_group_condition(v4_base_data, external_api):
    rule = create_rule()
    external_api.get_data_link.return_value = {"status": {"state": "not-ok"}}

    status = RecordRuleV4Operator(rule, source="scheduler").refresh_flow_health()

    rule.refresh_from_db()
    assert status == RecordRuleV4FlowStatus.ABNORMAL.value
    assert rule.get_condition(CONDITION_FLOW_HEALTHY)["status"] == CONDITION_FALSE
    assert rule.status == RecordRuleV4Status.FAILED.value
    assert rule.applied_deployment.resolved.flows.get().flow_status == RecordRuleV4FlowStatus.ABNORMAL.value

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
