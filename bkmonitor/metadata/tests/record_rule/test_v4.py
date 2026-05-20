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
from uuid import uuid4

import pytest
from django.utils import timezone

from metadata.models.record_rule.constants import (
    RECORD_RULE_V4_DEFAULT_TENANT,
    RecordRuleV4DesiredStatus,
    RecordRuleV4FlowStatus,
    RecordRuleV4Status,
)
from metadata.models.record_rule.v4 import (
    CONDITION_FALSE,
    CONDITION_FLOW_HEALTHY,
    CONDITION_RECONCILED,
    CONDITION_TRUE,
    EVENT_REASON_APPLY_FAILED,
    EVENT_TYPE_APPLY_FAILED,
    EVENT_TYPE_FLOW_ACTION_FAILED,
    RecordRuleV4,
    RecordRuleV4Event,
    RecordRuleV4Flow,
    RecordRuleV4Resolved,
    RecordRuleV4Spec,
    stable_hash,
)
from metadata.models.record_rule.v4.output import RecordRuleV4OutputResources

pytestmark = pytest.mark.django_db(databases="__all__")


def create_rule(**overrides) -> RecordRuleV4:
    suffix = overrides.pop("suffix", uuid4().hex[:8])
    defaults = {
        "bk_tenant_id": "tenant_v4_unit",
        "space_type": "bkcc",
        "space_id": "2",
        "name": "cpu-group",
        "flow_name": f"bkm_rr_1_cpu_group_{suffix}",
        "table_id": f"bkm_rr_1_cpu_group_{suffix}.__default__",
        "dst_vm_table_id": f"vm_bkm_rr_1_cpu_group_{suffix}",
        "dst_vm_storage_name": "monitor-opsystem",
        "creator": "pytest",
        "updater": "pytest",
    }
    defaults.update(overrides)
    return RecordRuleV4.objects.create(**defaults)


def create_spec(rule: RecordRuleV4, **overrides) -> RecordRuleV4Spec:
    defaults = {
        "rule": rule,
        "bk_tenant_id": rule.bk_tenant_id,
        "generation": rule.generation + 1,
        "raw_config": {"records": []},
        "interval": "1min",
        "labels": [],
        "content_hash": stable_hash(
            {
                "records": [],
                "interval": "1min",
                "labels": [],
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
        "bk_tenant_id": rule.bk_tenant_id,
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


def create_flow(rule: RecordRuleV4, resolved: RecordRuleV4Resolved, **overrides) -> RecordRuleV4Flow:
    defaults = {
        "rule": rule,
        "resolved": resolved,
        "bk_tenant_id": rule.bk_tenant_id,
        "flow_name": rule.flow_name,
        "flow_config": {"kind": "Flow"},
        "content_hash": "flow-hash",
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
        pk=123,
        name="cpu-usage.with/slashes-and-very-long-name",
        random_suffix="abcdef12",
    )
    result_table_config_name = RecordRuleV4OutputResources.compose_result_table_config_name(table_id)
    flow_name = RecordRuleV4.compose_flow_name(
        pk=123,
        name="cpu-usage.with/slashes-and-very-long-name",
        random_suffix="abcdef12",
    )
    group_flow_name = RecordRuleV4.compose_group_flow_name(
        pk=123,
        name="cpu-usage.with/slashes-and-very-long-name",
        table_id=table_id,
    )
    table_base_name = table_id.split(".__default__")[0]

    assert len(table_base_name) <= 50
    assert len(result_table_config_name) <= 40
    assert len(flow_name) <= 50
    assert len(group_flow_name) <= 50
    assert table_base_name.startswith("bkm_rr_123_cpu_usage")
    assert table_id.endswith("_abcdef12.__default__")
    assert result_table_config_name.startswith("bkm_bkm_rr_123_cpu_usage")
    assert "abcdef12" in flow_name
    assert "abcdef12" in group_flow_name


def test_compose_names_accept_any_display_name():
    table_id = RecordRuleV4.compose_table_id(pk=456, name="<测试任务>", random_suffix="abcdef12")
    fallback_table_id = RecordRuleV4.compose_table_id(pk=789, name="🔥<>", random_suffix="abcdef12")
    long_table_id = RecordRuleV4.compose_table_id(pk=987, name="测试任务" * 80, random_suffix="abcdef12")

    assert table_id.startswith("bkm_rr_456_ceshirenwu_")
    assert fallback_table_id.startswith("bkm_rr_789_group_")
    assert len(long_table_id.split(".__default__")[0]) <= 50


def test_flow_bkbase_tenant_follows_multi_tenant_mode(settings):
    rule = create_rule()

    settings.ENABLE_MULTI_TENANT_MODE = False
    assert RecordRuleV4Flow.compose_bkbase_tenant(rule) == RECORD_RULE_V4_DEFAULT_TENANT

    settings.ENABLE_MULTI_TENANT_MODE = True
    assert RecordRuleV4Flow.compose_bkbase_tenant(rule) == rule.bk_tenant_id


def test_conditions_are_updated_by_type_instead_of_accumulated():
    rule = create_rule()

    rule.set_condition(CONDITION_RECONCILED, CONDITION_FALSE, "ApplyFailed")
    rule.set_condition(CONDITION_RECONCILED, CONDITION_TRUE, "ApplySucceeded")

    assert list(rule.conditions) == [CONDITION_RECONCILED]
    assert rule.get_condition(CONDITION_RECONCILED)["status"] == CONDITION_TRUE
    assert rule.get_condition(CONDITION_RECONCILED)["reason"] == "ApplySucceeded"


def test_sync_phase_distinguishes_main_states():
    pending_rule = create_rule()
    pending_rule.use_spec(create_spec(pending_rule))
    pending_rule.refresh_from_db()
    pending_rule.sync_phase()
    assert pending_rule.status == RecordRuleV4Status.PENDING.value

    outdated_rule = create_rule(auto_refresh=False)
    spec = create_spec(outdated_rule)
    resolved = create_resolved(outdated_rule, spec)
    outdated_rule.use_spec(spec)
    outdated_rule.use_resolved(resolved)
    outdated_rule.refresh_from_db()
    outdated_rule.sync_phase()
    assert outdated_rule.status == RecordRuleV4Status.OUTDATED.value

    outdated_rule.set_condition(CONDITION_FLOW_HEALTHY, CONDITION_FALSE, "not_found")
    outdated_rule.sync_phase()
    assert outdated_rule.status == RecordRuleV4Status.FAILED.value

    stopped_rule = create_rule()
    spec = create_spec(stopped_rule)
    resolved = create_resolved(stopped_rule, spec)
    flow = create_flow(stopped_rule, resolved)
    stopped_rule.use_spec(spec)
    stopped_rule.use_resolved(resolved)
    stopped_rule.mark_flow_applied(flow)
    stopped_rule.desired_status = RecordRuleV4DesiredStatus.STOPPED.value
    stopped_rule.applied_desired_status = RecordRuleV4DesiredStatus.RUNNING.value
    stopped_rule.sync_phase()
    assert stopped_rule.status == RecordRuleV4Status.PENDING.value

    stopped_rule.applied_desired_status = RecordRuleV4DesiredStatus.STOPPED.value
    stopped_rule.desired_status = RecordRuleV4DesiredStatus.STOPPED.value
    stopped_rule.sync_phase()
    assert stopped_rule.status == RecordRuleV4Status.STOPPED.value

    deleted_rule = create_rule(desired_status=RecordRuleV4DesiredStatus.DELETED.value)
    deleted_rule.sync_phase()
    assert deleted_rule.status == RecordRuleV4Status.DELETING.value

    deleted_rule.deleted_at = timezone.now()
    deleted_rule.sync_phase()
    assert deleted_rule.status == RecordRuleV4Status.DELETED.value


def test_use_spec_resolved_flow_tracks_latest_on_spec_and_applied_on_group():
    rule = create_rule()
    spec = create_spec(rule)
    resolved = create_resolved(rule, spec)
    flow = create_flow(rule, resolved)

    rule.use_spec(spec)
    rule.use_resolved(resolved)
    rule.mark_flow_ready(flow)

    rule.refresh_from_db()
    spec.refresh_from_db()
    assert rule.current_spec_id == spec.pk
    assert spec.latest_resolved_id == resolved.pk
    assert rule.get_latest_flow().pk == flow.pk
    assert spec.latest_resolved_id != rule.applied_resolved_id
    assert spec.bk_tenant_id == rule.bk_tenant_id
    assert resolved.bk_tenant_id == rule.bk_tenant_id
    assert flow.bk_tenant_id == rule.bk_tenant_id

    rule.mark_flow_applied(flow)
    rule.refresh_from_db()
    assert rule.applied_resolved_id == resolved.pk
    assert rule.applied_desired_status == RecordRuleV4DesiredStatus.RUNNING.value
    assert rule.current_spec.latest_resolved_id == rule.applied_resolved_id
    assert rule.status == RecordRuleV4Status.RUNNING.value


def test_mark_delete_applied_clears_effective_resolved():
    rule = create_rule(desired_status=RecordRuleV4DesiredStatus.DELETED.value, generation=2)
    spec = create_spec(rule, generation=2)
    resolved = create_resolved(rule, spec)
    rule.applied_resolved = resolved
    rule.save()

    rule.mark_delete_applied()

    rule.refresh_from_db()
    assert rule.applied_resolved_id is None
    assert rule.applied_desired_status == RecordRuleV4DesiredStatus.DELETED.value
    assert rule.deleted_at is not None
    assert rule.status == RecordRuleV4Status.DELETED.value


def test_flow_mark_runtime_observe_result():
    rule = create_rule()
    spec = create_spec(rule)
    resolved = create_resolved(rule, spec)
    flow = create_flow(rule, resolved)

    flow.mark_flow_observed(RecordRuleV4FlowStatus.ABNORMAL.value)

    flow.refresh_from_db()
    assert flow.flow_status == RecordRuleV4FlowStatus.ABNORMAL.value
    assert flow.last_observed_at is not None


def test_event_methods_persist_structured_context_and_validate_payload():
    rule = create_rule()
    spec = create_spec(rule)
    resolved = create_resolved(rule, spec)
    flow = create_flow(rule, resolved)

    event = RecordRuleV4Event.record_apply_failed(
        rule,
        flow=flow,
        source="manual",
        operator="admin",
        message="bkbase unavailable",
    )

    assert event.event_type == EVENT_TYPE_APPLY_FAILED
    assert event.reason == EVENT_REASON_APPLY_FAILED
    assert event.spec_id == spec.pk
    assert event.resolved_id == resolved.pk
    assert event.flow_id == flow.pk
    assert event.bk_tenant_id == rule.bk_tenant_id
    assert event.message == "bkbase unavailable"

    with pytest.raises(ValueError):
        RecordRuleV4Event.objects.create(
            rule=rule,
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
            flow=flow,
            event_type=EVENT_TYPE_FLOW_ACTION_FAILED,
            status="failed",
            source="manual",
            operator="admin",
            detail={"unexpected": True},
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
