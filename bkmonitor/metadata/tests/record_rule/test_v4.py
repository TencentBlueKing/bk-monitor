"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from metadata.models.record_rule.constants import (
    RecordRuleV4ApplyStatus,
    RecordRuleV4DeploymentStrategy,
    RecordRuleV4DesiredStatus,
    RecordRuleV4FlowStatus,
    RecordRuleV4Status,
)
from metadata.models.record_rule.v4 import (
    CONDITION_FALSE,
    CONDITION_FLOW_HEALTHY,
    CONDITION_RECONCILED,
    CONDITION_TRUE,
    CONDITION_UPDATE_AVAILABLE,
    EVENT_REASON_APPLY_FAILED,
    EVENT_TYPE_APPLY_FAILED,
    EVENT_TYPE_FLOW_ACTION_FAILED,
    RecordRuleV4,
    RecordRuleV4Deployment,
    RecordRuleV4Event,
    RecordRuleV4Flow,
    RecordRuleV4Resolved,
    RecordRuleV4Spec,
    stable_hash,
)
from metadata.models.record_rule.v4.output import RecordRuleV4OutputResources

pytestmark = pytest.mark.django_db(databases="__all__")


def create_rule(**overrides) -> RecordRuleV4:
    defaults = {
        "bk_tenant_id": "system",
        "space_type": "bkcc",
        "space_id": "2",
        "group_name": "cpu-group",
        "table_id": "bkprecal_cpu_group_abcd1234.__default__",
        "dst_vm_table_id": "vm_bkprecal_cpu_group_abcd1234",
        "creator": "pytest",
        "updater": "pytest",
    }
    defaults.update(overrides)
    return RecordRuleV4.objects.create(**defaults)


def create_spec(rule: RecordRuleV4, **overrides) -> RecordRuleV4Spec:
    defaults = {
        "rule": rule,
        "generation": rule.generation + 1,
        "raw_config": {"records": []},
        "interval": "1min",
        "labels": [],
        "deployment_strategy": {"strategy": RecordRuleV4DeploymentStrategy.PER_RECORD.value, "options": {}},
        "desired_status": RecordRuleV4DesiredStatus.RUNNING.value,
        "content_hash": stable_hash(
            {
                "records": [],
                "interval": "1min",
                "labels": [],
                "deployment_strategy": {"strategy": RecordRuleV4DeploymentStrategy.PER_RECORD.value, "options": {}},
            }
        ),
        "source": "pytest",
        "operator": "tester",
        "creator": "tester",
        "updater": "tester",
    }
    defaults.update(overrides)
    return RecordRuleV4Spec.objects.create(**defaults)


def create_resolved(rule: RecordRuleV4, spec: RecordRuleV4Spec, **overrides) -> RecordRuleV4Resolved:
    defaults = {
        "rule": rule,
        "spec": spec,
        "generation": spec.generation,
        "resolve_version": 1,
        "resolved_config": {"records": []},
        "content_hash": stable_hash({"records": []}),
        "source": "pytest",
        "creator": "pytest",
        "updater": "pytest",
    }
    defaults.update(overrides)
    return RecordRuleV4Resolved.objects.create(**defaults)


def create_deployment(
    rule: RecordRuleV4, spec: RecordRuleV4Spec, resolved: RecordRuleV4Resolved, **overrides
) -> RecordRuleV4Deployment:
    defaults = {
        "rule": rule,
        "spec": spec,
        "resolved": resolved,
        "generation": spec.generation,
        "deployment_version": 1,
        "strategy": spec.deployment_strategy_name,
        "content_hash": "deployment-hash",
        "plan_config": {"actions": []},
        "source": "pytest",
        "creator": "pytest",
        "updater": "pytest",
    }
    defaults.update(overrides)
    return RecordRuleV4Deployment.objects.create(**defaults)


def create_flow(rule: RecordRuleV4, resolved: RecordRuleV4Resolved, **overrides) -> RecordRuleV4Flow:
    defaults = {
        "rule": rule,
        "resolved": resolved,
        "flow_key": "rr_abcd1234",
        "flow_name": "rrv4_cpu_group_cpu_abcd1234",
        "strategy": RecordRuleV4DeploymentStrategy.PER_RECORD.value,
        "table_id": rule.table_id,
        "dst_vm_table_id": rule.dst_vm_table_id,
        "flow_config": {"kind": "Flow"},
        "content_hash": "flow-hash",
        "desired_status": RecordRuleV4DesiredStatus.RUNNING.value,
        "creator": "pytest",
        "updater": "pytest",
    }
    defaults.update(overrides)
    return RecordRuleV4Flow.objects.create(**defaults)


def test_stable_hash_is_independent_from_dict_key_order():
    left = {"records": [{"metricql": "a", "src_vm_table_ids": ["2_vm_system_cpu"]}]}
    right = {"records": [{"src_vm_table_ids": ["2_vm_system_cpu"], "metricql": "a"}]}

    assert stable_hash(left) == stable_hash(right)


def test_compose_names_keep_hint_random_suffix_and_short_length():
    table_id = RecordRuleV4.compose_table_id(
        group_name="cpu-usage.with/slashes-and-very-long-name",
        random_suffix="abcdef12",
    )
    result_table_config_name = RecordRuleV4OutputResources.compose_result_table_config_name(table_id)
    flow_name = RecordRuleV4.compose_flow_name(
        group_name="cpu-usage.with/slashes-and-very-long-name",
        flow_hint="record:cpu-total",
        random_suffix="abcdef12",
    )

    assert len(table_id) <= 50
    assert len(result_table_config_name) <= 40
    assert len(flow_name) <= 50
    assert table_id.startswith("bkprecal_cpu_usage")
    assert table_id.endswith("_abcdef12.__default__")
    assert result_table_config_name.startswith("bkm_bkprecal_cpu_usage")
    assert "abcdef12" in flow_name


def test_conditions_are_updated_by_type_instead_of_accumulated():
    rule = create_rule()

    rule.set_condition(CONDITION_RECONCILED, CONDITION_FALSE, "ApplyFailed")
    rule.set_condition(CONDITION_RECONCILED, CONDITION_TRUE, "ApplySucceeded")

    assert list(rule.conditions) == [CONDITION_RECONCILED]
    assert rule.get_condition(CONDITION_RECONCILED)["status"] == CONDITION_TRUE
    assert rule.get_condition(CONDITION_RECONCILED)["reason"] == "ApplySucceeded"


def test_sync_phase_distinguishes_main_states():
    rule = create_rule(generation=2, observed_generation=1)

    rule.sync_phase()
    assert rule.status == RecordRuleV4Status.PENDING.value

    rule.observed_generation = 2
    rule.update_available = True
    rule.auto_refresh = False
    rule.sync_phase()
    assert rule.status == RecordRuleV4Status.OUTDATED.value

    rule.set_condition(CONDITION_FLOW_HEALTHY, CONDITION_FALSE, "not_found")
    rule.sync_phase()
    assert rule.status == RecordRuleV4Status.FAILED.value

    rule.conditions = {}
    rule.update_available = False
    rule.desired_status = RecordRuleV4DesiredStatus.STOPPED.value
    rule.sync_phase()
    assert rule.status == RecordRuleV4Status.STOPPED.value

    rule.desired_status = RecordRuleV4DesiredStatus.DELETED.value
    rule.sync_phase()
    assert rule.status == RecordRuleV4Status.DELETING.value

    rule.deleted_at = timezone.now()
    rule.sync_phase()
    assert rule.status == RecordRuleV4Status.DELETED.value


def test_use_spec_resolved_deployment_updates_group_pointers_and_update_flag():
    rule = create_rule()
    spec = create_spec(rule)
    resolved = create_resolved(rule, spec)
    deployment = create_deployment(rule, spec, resolved)

    rule.use_spec(spec)
    rule.use_resolved(resolved)
    rule.use_deployment(deployment)

    rule.refresh_from_db()
    assert rule.current_spec_id == spec.pk
    assert rule.latest_resolved_id == resolved.pk
    assert rule.latest_deployment_id == deployment.pk
    assert rule.update_available is True
    assert rule.get_condition(CONDITION_UPDATE_AVAILABLE)["status"] == CONDITION_TRUE

    rule.mark_deployment_applied(deployment)
    rule.refresh_from_db()
    assert rule.applied_deployment_id == deployment.pk
    assert rule.observed_generation == deployment.generation
    assert rule.update_available is False
    assert rule.status == RecordRuleV4Status.RUNNING.value


def test_deployment_and_flow_mark_runtime_result():
    rule = create_rule()
    spec = create_spec(rule)
    resolved = create_resolved(rule, spec)
    deployment = create_deployment(rule, spec, resolved)
    flow = create_flow(rule, resolved)

    flow.mark_flow_observed(RecordRuleV4FlowStatus.ABNORMAL.value)
    deployment.mark_apply_failed("deployment failed")

    flow.refresh_from_db()
    deployment.refresh_from_db()
    assert flow.flow_status == RecordRuleV4FlowStatus.ABNORMAL.value
    assert flow.last_observed_at is not None
    assert deployment.apply_status == RecordRuleV4ApplyStatus.FAILED.value
    assert deployment.apply_error == "deployment failed"

    deployment.mark_apply_succeeded()
    deployment.refresh_from_db()
    assert deployment.apply_status == RecordRuleV4ApplyStatus.SUCCEEDED.value
    assert deployment.apply_error == ""


def test_event_methods_persist_structured_context_and_validate_payload():
    rule = create_rule()
    spec = create_spec(rule)
    resolved = create_resolved(rule, spec)
    deployment = create_deployment(rule, spec, resolved)
    flow = create_flow(rule, resolved)

    event = RecordRuleV4Event.record_apply_failed(
        rule,
        deployment,
        flow=flow,
        source="manual",
        operator="admin",
        message="bkbase unavailable",
    )

    assert event.event_type == EVENT_TYPE_APPLY_FAILED
    assert event.reason == EVENT_REASON_APPLY_FAILED
    assert event.spec_id == spec.pk
    assert event.resolved_id == resolved.pk
    assert event.deployment_id == deployment.pk
    assert event.flow_id == flow.pk
    assert event.message == "bkbase unavailable"

    with pytest.raises(ValueError):
        RecordRuleV4Event.objects.create(
            rule=rule,
            deployment=deployment,
            flow=flow,
            event_type=EVENT_TYPE_FLOW_ACTION_FAILED,
            status="unknown",
            source="manual",
            operator="admin",
            creator="admin",
            updater="admin",
        )
    with pytest.raises(ValueError):
        RecordRuleV4Event.record(
            rule=rule,
            deployment=deployment,
            flow=flow,
            event_type=EVENT_TYPE_FLOW_ACTION_FAILED,
            status="unknown",
            source="manual",
            operator="admin",
        )
    with pytest.raises(ValueError):
        RecordRuleV4Event.record(
            rule=rule,
            event_type="unknown",
            status="failed",
            source="manual",
            operator="admin",
        )


def test_operation_lock_can_expire_and_be_released():
    rule = create_rule()

    first_token = rule.acquire_operation_lock(owner="scheduler", reason="reconcile", ttl_seconds=60)
    second_token = rule.acquire_operation_lock(owner="manual", reason="apply", ttl_seconds=60)
    assert first_token
    assert second_token == ""

    RecordRuleV4.objects.filter(pk=rule.pk).update(operation_lock_expires_at=timezone.now() - timedelta(seconds=1))
    expired_token = rule.acquire_operation_lock(owner="manual", reason="apply", ttl_seconds=60)
    assert expired_token
    assert rule.release_operation_lock(expired_token) is True
