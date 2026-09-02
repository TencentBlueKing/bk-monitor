import uuid
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone

from bkmonitor.nodeman_integration.v3.client import (
    NodeManV3APIError,
    NodeManV3RequestContext,
    NodeManV3UnknownResultError,
)
from bkmonitor.nodeman_integration.v3.exceptions import NodeManV3ResultState
from monitor_web.collecting.deploy.nodeman_v3.validation import NodeManV3CapabilityBlocked
from monitor_web.models.node_man import (
    CollectDeploymentTarget,
    MonitorNodeManOperation,
    MonitorNodeManWorkflow,
    NodeManExecutionLease,
    NodeManIntegrationBinding,
    NodeManOperationStatus,
    NodeManOperationType,
    NodeManResourceType,
    NodeManWorkflowDispatchStatus,
    NodeManWorkflowStatus,
)
from monitor_web.nodeman_integration.v3.operation import (
    DISPATCH_RECOVERY_GRACE_SECONDS,
    NodeManExecutionLeaseConflict,
    NodeManV3OperationService,
    NodeManV3TargetOperationCoordinator,
    finalize_target_operation,
    recover_submitting_batches,
)
from monitor_web.nodeman_integration.v3.status import refresh_operation_status


class FakeOperation:
    def __init__(self, trace, **attributes):
        self.trace = trace
        self.id = uuid.uuid4()
        self.status = NodeManOperationStatus.PENDING
        self.error_summary = ""
        self.result_state = ""
        for key, value in attributes.items():
            setattr(self, key, value)

    def transition_to(self, status):
        self.trace.append(("transition", status))
        self.status = status

    def save(self, *, update_fields):
        self.trace.append(("operation_save", tuple(update_fields)))


class FakeOperationManager:
    def __init__(self, trace):
        self.trace = trace
        self.created = []

    def create(self, **kwargs):
        self.trace.append(("operation_create", kwargs))
        operation = FakeOperation(self.trace, **kwargs)
        self.created.append(operation)
        return operation


class FakeWorkflowManager:
    def __init__(self, trace):
        self.trace = trace
        self.created = []

    def create(self, **kwargs):
        self.trace.append(("workflow_create", kwargs))
        workflow = FakeWorkflow(self.trace, **kwargs)
        self.created.append(workflow)
        return workflow


class FakeWorkflow:
    def __init__(self, trace, **attributes):
        self.trace = trace
        self.workflow_id = None
        self.trigger_id = None
        self.dispatch_error = ""
        self.result_state = ""
        self.normalized_status = NodeManWorkflowStatus.PENDING
        for key, value in attributes.items():
            setattr(self, key, value)

    def save(self, *, update_fields):
        self.trace.append(("workflow_save", self.batch_index, tuple(update_fields)))


class FakeModel:
    def __init__(self, manager):
        self.objects = manager


def _service(trace, scheduled):
    operation_manager = FakeOperationManager(trace)
    workflow_manager = FakeWorkflowManager(trace)
    return (
        NodeManV3OperationService(
            operation_model=FakeModel(operation_manager),
            workflow_model=FakeModel(workflow_manager),
            poll_scheduler=lambda operation_id: scheduled.append(operation_id),
            terminal_handler=lambda *args: None,
        ),
        operation_manager,
        workflow_manager,
    )


def _binding(generation=1):
    return SimpleNamespace(
        id=1,
        execution_bk_tenant_id="tenant-a",
        bk_biz_id=2,
        generation=generation,
    )


def test_single_and_multiple_workflows_are_persisted_before_polling():
    trace = []
    scheduled = []
    service, operation_manager, workflow_manager = _service(trace, scheduled)
    submitted = []

    def submit(batch, *, context):
        submitted.append((batch, context))
        trace.append(("submit", batch["target_summary"]))
        return {"workflow_id": f"workflow-{len(submitted)}"}

    operation = service.dispatch_batches(
        binding=_binding(),
        operation_type="install",
        generation=1,
        batches=[
            {"target_summary": {"host_ids": [1]}, "target_count": 1},
            {"target_summary": {"host_ids": [2]}, "target_count": 1},
        ],
        request_summary={"release_id": 3},
        submit_batch=submit,
    )

    assert operation is operation_manager.created[0]
    assert [workflow.workflow_id for workflow in workflow_manager.created] == ["workflow-1", "workflow-2"]
    assert operation.status == NodeManOperationStatus.RUNNING
    assert scheduled == [operation.id]
    first_submit = trace.index(("submit", {"host_ids": [1]}))
    assert trace.index(("operation_create", trace[0][1])) < first_submit
    assert all(trace.index(event) < first_submit for event in trace if event[0] == "workflow_create")
    assert all(context.monitor_operation_id == str(operation.id) for _, context in submitted)


def test_deploy_policy_trigger_is_persisted_and_polled_like_a_workflow():
    trace = []
    scheduled = []
    service, operation_manager, workflow_manager = _service(trace, scheduled)

    operation = service.dispatch_batches(
        binding=_binding(),
        operation_type="reconcile",
        generation=1,
        batches=[{"target_summary": {"identity_keys": ["host:1"]}, "target_count": 1}],
        request_summary={},
        submit_batch=lambda *args, **kwargs: {"trigger_id": "trigger-1"},
    )

    workflow = workflow_manager.created[0]
    assert operation is operation_manager.created[0]
    assert operation.status == NodeManOperationStatus.RUNNING
    assert workflow.workflow_id is None
    assert workflow.trigger_id == "trigger-1"
    assert workflow.dispatch_status == NodeManWorkflowDispatchStatus.SUBMITTED
    assert scheduled == [operation.id]


def test_unknown_write_result_is_not_retried_or_polled():
    trace = []
    scheduled = []
    service, operation_manager, workflow_manager = _service(trace, scheduled)
    submit_count = 0

    def submit(batch, *, context):
        nonlocal submit_count
        submit_count += 1
        raise NodeManV3UnknownResultError("timeout")

    operation = service.dispatch_batches(
        binding=_binding(),
        operation_type="install",
        generation=1,
        batches=[{"target_summary": {"host_ids": [1]}, "target_count": 1}],
        request_summary={},
        submit_batch=submit,
    )

    assert operation is operation_manager.created[0]
    assert operation.status == NodeManOperationStatus.UNKNOWN
    assert operation.result_state == NodeManV3ResultState.WRITE_RESULT_UNKNOWN
    assert submit_count == 1
    assert len(workflow_manager.created) == 1
    assert workflow_manager.created[0].workflow_id is None
    assert workflow_manager.created[0].dispatch_status == "unknown"
    assert workflow_manager.created[0].result_state == NodeManV3ResultState.WRITE_RESULT_UNKNOWN
    assert scheduled == []


def test_failure_after_one_workflow_waits_for_submitted_terminal_before_aggregation():
    trace = []
    scheduled = []
    service, _, workflow_manager = _service(trace, scheduled)
    submit_count = 0

    def submit(batch, *, context):
        nonlocal submit_count
        submit_count += 1
        if submit_count == 2:
            raise NodeManV3APIError(code=4001, message="rejected")
        return {"workflow_id": "workflow-1"}

    operation = service.dispatch_batches(
        binding=_binding(),
        operation_type="install",
        generation=1,
        batches=[
            {"target_summary": {"host_ids": [1]}, "target_count": 1},
            {"target_summary": {"host_ids": [2]}, "target_count": 1},
        ],
        request_summary={},
        submit_batch=submit,
    )

    assert operation.status == NodeManOperationStatus.RUNNING
    assert submit_count == 2
    assert [workflow.workflow_id for workflow in workflow_manager.created] == ["workflow-1", None]
    assert workflow_manager.created[1].dispatch_status == "definite_failed"
    assert scheduled == [operation.id]


def _database_binding(resource_key):
    return NodeManIntegrationBinding.objects.create(
        resource_type=NodeManResourceType.COLLECT_CONFIG,
        resource_key=str(resource_key),
        owner_bk_tenant_id="tenant-a",
        execution_bk_tenant_id="tenant-a",
        bk_biz_id=2,
    )


def _database_target(binding, identity_key, host_id, plugin_name="mysql_exporter"):
    return CollectDeploymentTarget.objects.create(
        binding=binding,
        config_meta_id=int(binding.resource_key),
        generation=binding.generation,
        identity_key=identity_key,
        observed_target={"bk_host_id": host_id},
        execution_bk_host_id=host_id,
        plugin_name=plugin_name,
        desired_revision="3.2:revision",
        desired_fingerprint=f"fingerprint-{identity_key}",
    )


@pytest.mark.django_db(transaction=True)
def test_prepare_target_operation_persists_operation_target_and_all_leases_before_dispatch():
    binding = _database_binding(7)
    target_a = _database_target(binding, "host:1", 1)
    target_b = _database_target(binding, "host:2", 2)

    prepared = NodeManV3TargetOperationCoordinator().prepare_action(
        binding=binding,
        operation_type=NodeManOperationType.RECONCILE,
        action="added",
        generation=1,
        targets=[target_b, target_a],
        request_summary={"trigger": "periodic"},
    )

    target_a.refresh_from_db()
    target_b.refresh_from_db()
    leases = list(NodeManExecutionLease.objects.order_by("bk_host_id"))
    assert target_a.last_operation_id == target_b.last_operation_id == prepared.operation.id
    assert [lease.bk_host_id for lease in leases] == [1, 2]
    assert all(lease.holder_operation_id == prepared.operation.id for lease in leases)
    assert [token.bk_host_id for token in prepared.lease_tokens] == [1, 2]
    assert prepared.operation.request_summary["target_action"] == "added"
    assert prepared.operation.request_summary["target_identity_keys"] == ["host:1", "host:2"]


@pytest.mark.django_db(transaction=True)
def test_multi_target_lease_conflict_rolls_back_all_new_leases_and_operation():
    binding_a = _database_binding(7)
    held = _database_target(binding_a, "host:1", 1)
    NodeManV3TargetOperationCoordinator().prepare_action(
        binding=binding_a,
        operation_type=NodeManOperationType.RECONCILE,
        action="added",
        generation=1,
        targets=[held],
        request_summary={},
    )
    operation_count = binding_a.operations.count()

    binding_b = _database_binding(8)
    conflict = _database_target(binding_b, "host:101", 1)
    free = _database_target(binding_b, "host:102", 2)
    with pytest.raises(NodeManExecutionLeaseConflict, match="tenant-a.*1.*mysql_exporter"):
        NodeManV3TargetOperationCoordinator().prepare_action(
            binding=binding_b,
            operation_type=NodeManOperationType.RECONCILE,
            action="added",
            generation=1,
            targets=[free, conflict],
            request_summary={},
        )

    assert NodeManExecutionLease.objects.filter(bk_host_id=2).exists() is False
    assert binding_a.operations.count() == operation_count
    assert binding_b.operations.count() == 0
    assert CollectDeploymentTarget.objects.get(pk=free.pk).last_operation_id is None


@pytest.mark.django_db(transaction=True)
def test_target_batches_must_cover_each_identity_exactly_once_before_dispatch():
    binding = _database_binding(7)
    target_a = _database_target(binding, "host:1", 1)
    target_b = _database_target(binding, "host:2", 2)

    with pytest.raises(ValueError, match="cover every operation identity"):
        NodeManV3TargetOperationCoordinator().prepare_action(
            binding=binding,
            operation_type=NodeManOperationType.RECONCILE,
            action="added",
            generation=1,
            targets=[target_a, target_b],
            request_summary={},
            batches=[{"target_summary": {"identity_keys": ["host:1"]}}],
        )

    assert binding.operations.count() == 0
    assert NodeManExecutionLease.objects.exists() is False


@pytest.mark.django_db(transaction=True)
def test_terminal_success_applies_current_target_and_releases_matching_fenced_lease():
    binding = _database_binding(7)
    target = _database_target(binding, "host:1", 1)
    prepared = NodeManV3TargetOperationCoordinator().prepare_action(
        binding=binding,
        operation_type=NodeManOperationType.RECONCILE,
        action="added",
        generation=1,
        targets=[target],
        request_summary={},
    )
    workflow = prepared.workflows[0]
    workflow.workflow_id = "workflow-1"
    workflow.dispatch_status = NodeManWorkflowDispatchStatus.SUBMITTED
    workflow.normalized_status = NodeManWorkflowStatus.SUCCESS
    workflow.save(update_fields=("workflow_id", "dispatch_status", "normalized_status", "updated_at"))
    prepared.operation.status = NodeManOperationStatus.SUCCESS
    prepared.operation.save(update_fields=("status", "updated_at"))

    finalize_target_operation(prepared.operation, [workflow])

    target.refresh_from_db()
    lease = NodeManExecutionLease.objects.get(bk_host_id=1)
    assert target.applied_present is True
    assert target.applied_fingerprint == target.desired_fingerprint
    assert lease.holder_operation_id is None
    assert lease.lease_generation == prepared.lease_tokens[0].lease_generation


@pytest.mark.django_db(transaction=True)
def test_stale_terminal_only_releases_its_fenced_lease_and_schedules_new_reconcile():
    binding = _database_binding(7)
    target = _database_target(binding, "host:1", 1)
    prepared = NodeManV3TargetOperationCoordinator().prepare_action(
        binding=binding,
        operation_type=NodeManOperationType.RECONCILE,
        action="changed",
        generation=1,
        targets=[target],
        request_summary={},
    )
    workflow = prepared.workflows[0]
    workflow.workflow_id = "workflow-1"
    workflow.dispatch_status = NodeManWorkflowDispatchStatus.SUBMITTED
    workflow.normalized_status = NodeManWorkflowStatus.SUCCESS
    workflow.save(update_fields=("workflow_id", "dispatch_status", "normalized_status", "updated_at"))
    binding.advance_generation(expected_generation=1)
    prepared.operation.status = NodeManOperationStatus.SUCCESS
    prepared.operation.save(update_fields=("status", "updated_at"))
    scheduled = []

    finalize_target_operation(
        prepared.operation,
        [workflow],
        reconcile_scheduler=lambda binding_id: scheduled.append(binding_id),
    )

    target.refresh_from_db()
    lease = NodeManExecutionLease.objects.get(bk_host_id=1)
    assert target.applied_present is None
    assert lease.holder_operation_id is None
    assert scheduled == [binding.id]


@pytest.mark.django_db(transaction=True)
def test_partial_failure_applies_only_successful_workflow_targets_and_releases_closed_leases():
    binding = _database_binding(7)
    target_a = _database_target(binding, "host:1", 1)
    target_b = _database_target(binding, "host:2", 2)
    prepared = NodeManV3TargetOperationCoordinator().prepare_action(
        binding=binding,
        operation_type=NodeManOperationType.RECONCILE,
        action="added",
        generation=1,
        targets=[target_a, target_b],
        request_summary={},
        batches=[
            {"target_summary": {"identity_keys": ["host:1"]}, "target_count": 1},
            {"target_summary": {"identity_keys": ["host:2"]}, "target_count": 1},
        ],
    )
    workflows = list(prepared.workflows)
    workflows[0].workflow_id = "workflow-1"
    workflows[0].dispatch_status = NodeManWorkflowDispatchStatus.SUBMITTED
    workflows[0].normalized_status = NodeManWorkflowStatus.SUCCESS
    workflows[1].workflow_id = "workflow-2"
    workflows[1].dispatch_status = NodeManWorkflowDispatchStatus.SUBMITTED
    workflows[1].normalized_status = NodeManWorkflowStatus.FAILED
    MonitorNodeManWorkflow.objects.bulk_update(
        workflows,
        fields=("workflow_id", "dispatch_status", "normalized_status", "updated_at"),
    )
    prepared.operation.status = NodeManOperationStatus.PARTIAL_FAILED
    prepared.operation.save(update_fields=("status", "updated_at"))

    finalize_target_operation(prepared.operation, workflows)

    target_a.refresh_from_db()
    target_b.refresh_from_db()
    assert target_a.applied_present is True
    assert target_b.applied_present is None
    assert "failed" in target_b.error_summary
    assert NodeManExecutionLease.objects.filter(holder_operation=prepared.operation).exists() is False


@pytest.mark.django_db(transaction=True)
def test_recovery_turns_only_started_submitting_batch_unknown_without_releasing_or_resending():
    binding = _database_binding(7)
    target = _database_target(binding, "host:1", 1)
    prepared = NodeManV3TargetOperationCoordinator().prepare_action(
        binding=binding,
        operation_type=NodeManOperationType.RECONCILE,
        action="added",
        generation=1,
        targets=[target],
        request_summary={},
    )
    workflow = prepared.workflows[0]
    workflow.dispatch_status = NodeManWorkflowDispatchStatus.SUBMITTING
    workflow.save(update_fields=("dispatch_status", "updated_at"))

    assert recover_submitting_batches(prepared.operation, recovery_before=timezone.now()) is True

    prepared.operation.refresh_from_db()
    workflow.refresh_from_db()
    assert prepared.operation.status == NodeManOperationStatus.UNKNOWN
    assert prepared.operation.result_state == NodeManV3ResultState.WRITE_RESULT_UNKNOWN
    assert workflow.dispatch_status == NodeManWorkflowDispatchStatus.UNKNOWN
    assert workflow.result_state == NodeManV3ResultState.WRITE_RESULT_UNKNOWN
    assert NodeManExecutionLease.objects.filter(holder_operation=prepared.operation).exists() is True
    assert recover_submitting_batches(prepared.operation) is False


@pytest.mark.django_db(transaction=True)
def test_recovery_marks_never_submitted_prepared_batches_definite_and_releases_lease():
    binding = _database_binding(7)
    target = _database_target(binding, "host:1", 1)
    prepared = NodeManV3TargetOperationCoordinator().prepare_action(
        binding=binding,
        operation_type=NodeManOperationType.RECONCILE,
        action="added",
        generation=1,
        targets=[target],
        request_summary={},
    )

    assert recover_submitting_batches(prepared.operation, recovery_before=timezone.now()) is True

    prepared.operation.refresh_from_db()
    workflow = MonitorNodeManWorkflow.objects.get(pk=prepared.workflows[0].pk)
    assert prepared.operation.status == NodeManOperationStatus.FAILED
    assert workflow.dispatch_status == NodeManWorkflowDispatchStatus.DEFINITE_FAILED
    assert NodeManExecutionLease.objects.filter(holder_operation=prepared.operation).exists() is False


@pytest.mark.django_db(transaction=True)
def test_protocol_capability_block_is_persisted_as_unsupported():
    binding = _database_binding(7)
    target = _database_target(binding, "host:1", 1)
    coordinator = NodeManV3TargetOperationCoordinator()
    prepared = coordinator.prepare_action(
        binding=binding,
        operation_type=NodeManOperationType.RECONCILE,
        action="changed",
        generation=1,
        targets=[target],
        request_summary={},
    )

    coordinator.mark_definite_failure(prepared, NodeManV3CapabilityBlocked("missing protocol field"))

    prepared.operation.refresh_from_db()
    workflow = MonitorNodeManWorkflow.objects.get(pk=prepared.workflows[0].pk)
    assert prepared.operation.status == NodeManOperationStatus.FAILED
    assert prepared.operation.result_state == NodeManV3ResultState.UNSUPPORTED
    assert workflow.dispatch_status == NodeManWorkflowDispatchStatus.DEFINITE_FAILED
    assert workflow.result_state == NodeManV3ResultState.UNSUPPORTED


@pytest.mark.django_db(transaction=True)
def test_recovery_wins_prepared_compare_and_set_and_prevents_late_external_write():
    binding = _database_binding(7)
    target = _database_target(binding, "host:1", 1)
    prepared = NodeManV3TargetOperationCoordinator().prepare_action(
        binding=binding,
        operation_type=NodeManOperationType.RECONCILE,
        action="added",
        generation=1,
        targets=[target],
        request_summary={},
    )
    assert recover_submitting_batches(prepared.operation, recovery_before=timezone.now()) is True
    submitted = []

    operation = NodeManV3OperationService().dispatch_batches(
        binding=binding,
        operation_type=NodeManOperationType.RECONCILE,
        generation=1,
        batches=[{"target_summary": {"identity_keys": ["host:1"]}, "target_count": 1}],
        request_summary={},
        submit_batch=lambda *args, **kwargs: submitted.append((args, kwargs)),
        prepared_operation=prepared.operation,
        prepared_workflows=prepared.workflows,
    )

    assert submitted == []
    assert operation.status == NodeManOperationStatus.FAILED


@pytest.mark.django_db(transaction=True)
def test_recovery_keeps_submitted_workflow_running_and_marks_only_later_prepared_batch_definite():
    binding = _database_binding(7)
    target_a = _database_target(binding, "host:1", 1)
    target_b = _database_target(binding, "host:2", 2)
    prepared = NodeManV3TargetOperationCoordinator().prepare_action(
        binding=binding,
        operation_type=NodeManOperationType.RECONCILE,
        action="added",
        generation=1,
        targets=[target_a, target_b],
        request_summary={},
        batches=[
            {"target_summary": {"identity_keys": ["host:1"]}},
            {"target_summary": {"identity_keys": ["host:2"]}},
        ],
    )
    submitted, never_submitted = prepared.workflows
    submitted.workflow_id = "workflow-1"
    submitted.dispatch_status = NodeManWorkflowDispatchStatus.SUBMITTED
    submitted.normalized_status = NodeManWorkflowStatus.RUNNING
    submitted.save(update_fields=("workflow_id", "dispatch_status", "normalized_status", "updated_at"))

    assert recover_submitting_batches(prepared.operation, recovery_before=timezone.now()) is True

    prepared.operation.refresh_from_db()
    never_submitted.refresh_from_db()
    assert prepared.operation.status == NodeManOperationStatus.RUNNING
    assert never_submitted.dispatch_status == NodeManWorkflowDispatchStatus.DEFINITE_FAILED
    assert NodeManExecutionLease.objects.filter(holder_operation=prepared.operation).count() == 2


@pytest.mark.django_db(transaction=True)
def test_fresh_dispatch_heartbeat_prevents_poller_from_recovering_an_active_submission():
    binding = _database_binding(7)
    target = _database_target(binding, "host:1", 1)
    prepared = NodeManV3TargetOperationCoordinator().prepare_action(
        binding=binding,
        operation_type=NodeManOperationType.RECONCILE,
        action="added",
        generation=1,
        targets=[target],
        request_summary={},
    )
    workflow = prepared.workflows[0]
    workflow.dispatch_status = NodeManWorkflowDispatchStatus.SUBMITTING
    workflow.save(update_fields=("dispatch_status", "updated_at"))

    assert recover_submitting_batches(prepared.operation) is False

    prepared.operation.refresh_from_db()
    workflow.refresh_from_db()
    assert prepared.operation.status == NodeManOperationStatus.DISPATCHING
    assert workflow.dispatch_status == NodeManWorkflowDispatchStatus.SUBMITTING

    expired_at = timezone.now() - timedelta(seconds=DISPATCH_RECOVERY_GRACE_SECONDS + 1)
    MonitorNodeManOperation.objects.filter(pk=prepared.operation.pk).update(updated_at=expired_at)
    assert recover_submitting_batches(prepared.operation) is True


@pytest.mark.django_db(transaction=True)
def test_poll_operation_reloads_terminal_state_after_prepared_only_crash_recovery():
    from monitor_web.nodeman_integration.v3 import tasks

    binding = _database_binding(7)
    target = _database_target(binding, "host:1", 1)
    prepared = NodeManV3TargetOperationCoordinator().prepare_action(
        binding=binding,
        operation_type=NodeManOperationType.RECONCILE,
        action="added",
        generation=1,
        targets=[target],
        request_summary={},
    )
    expired_at = timezone.now() - timedelta(seconds=DISPATCH_RECOVERY_GRACE_SECONDS + 1)
    MonitorNodeManOperation.objects.filter(pk=prepared.operation.pk).update(updated_at=expired_at)

    result = tasks.poll_operation.run(str(prepared.operation.pk))

    prepared.operation.refresh_from_db()
    assert result == {
        "operation_id": str(prepared.operation.pk),
        "status": NodeManOperationStatus.FAILED,
        "finalized": False,
    }
    assert prepared.operation.status == NodeManOperationStatus.FAILED
    assert NodeManExecutionLease.objects.filter(holder_operation=prepared.operation).exists() is False


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("first_remote_status", ["success", None])
def test_concurrent_poll_commits_are_monotonic_and_cannot_leak_the_execution_lease(first_remote_status):
    binding = _database_binding(7)
    target = _database_target(binding, "host:1", 1)
    prepared = NodeManV3TargetOperationCoordinator().prepare_action(
        binding=binding,
        operation_type=NodeManOperationType.RECONCILE,
        action="added",
        generation=1,
        targets=[target],
        request_summary={},
    )
    workflow = prepared.workflows[0]
    workflow.workflow_id = "workflow-1"
    workflow.dispatch_status = NodeManWorkflowDispatchStatus.SUBMITTED
    workflow.normalized_status = NodeManWorkflowStatus.RUNNING
    workflow.save(update_fields=("workflow_id", "dispatch_status", "normalized_status", "updated_at"))
    prepared.operation.status = NodeManOperationStatus.RUNNING
    prepared.operation.save(update_fields=("status", "updated_at"))
    stale_operations = [
        MonitorNodeManOperation.objects.select_related("binding").get(pk=prepared.operation.pk),
        MonitorNodeManOperation.objects.select_related("binding").get(pk=prepared.operation.pk),
    ]

    class WorkflowClient:
        def __init__(self, remote_status):
            self.remote_status = remote_status

        def list_workflows(self, payload, *, context):
            del payload, context
            items = []
            if self.remote_status:
                items.append({"workflow_id": "workflow-1", "status": self.remote_status})
            return {"total": len(items), "items": items}

    statuses = [first_remote_status, None if first_remote_status else "success"]
    for stale_operation, remote_status in zip(stale_operations, statuses, strict=True):
        refresh_operation_status(
            stale_operation,
            WorkflowClient(remote_status),
            context=NodeManV3RequestContext(bk_tenant_id="tenant-a", bk_biz_id=7),
            on_terminal=finalize_target_operation,
        )

    prepared.operation.refresh_from_db()
    workflow.refresh_from_db()
    assert prepared.operation.status == NodeManOperationStatus.SUCCESS
    assert workflow.normalized_status == NodeManWorkflowStatus.SUCCESS
    assert NodeManExecutionLease.objects.filter(holder_operation=prepared.operation).exists() is False


@pytest.mark.django_db(transaction=True)
def test_terminal_operation_with_incomplete_workflow_evidence_is_repolled_and_releases_lease(monkeypatch):
    from monitor_web.nodeman_integration.v3 import tasks

    binding = _database_binding(7)
    target = _database_target(binding, "host:1", 1)
    prepared = NodeManV3TargetOperationCoordinator().prepare_action(
        binding=binding,
        operation_type=NodeManOperationType.RECONCILE,
        action="added",
        generation=1,
        targets=[target],
        request_summary={},
    )
    workflow = prepared.workflows[0]
    workflow.workflow_id = "workflow-1"
    workflow.dispatch_status = NodeManWorkflowDispatchStatus.SUBMITTED
    workflow.normalized_status = NodeManWorkflowStatus.RUNNING
    workflow.save(update_fields=("workflow_id", "dispatch_status", "normalized_status", "updated_at"))
    prepared.operation.status = NodeManOperationStatus.SUCCESS
    prepared.operation.save(update_fields=("status", "updated_at"))

    class WorkflowClient:
        def list_workflows(self, payload, *, context):
            del payload, context
            return {"total": 1, "items": [{"workflow_id": "workflow-1", "status": "success"}]}

    monkeypatch.setattr(tasks, "NodeManV3HTTPClient", lambda: object())
    monkeypatch.setattr(tasks, "WorkflowClient", lambda client: WorkflowClient())

    result = tasks.poll_operation.run(str(prepared.operation.pk))

    workflow.refresh_from_db()
    assert result == {
        "operation_id": str(prepared.operation.pk),
        "status": NodeManOperationStatus.SUCCESS,
        "stale_generation": False,
    }
    assert workflow.normalized_status == NodeManWorkflowStatus.SUCCESS
    assert NodeManExecutionLease.objects.filter(holder_operation=prepared.operation).exists() is False


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("batch_count", [1, 2])
def test_poll_recovers_crash_after_all_batches_submitted_before_operation_running(monkeypatch, batch_count):
    from monitor_web.nodeman_integration.v3 import tasks

    binding = _database_binding(7)
    targets = [_database_target(binding, f"host:{index}", index) for index in range(1, batch_count + 1)]
    batches = [{"target_summary": {"identity_keys": [target.identity_key]}} for target in targets]
    prepared = NodeManV3TargetOperationCoordinator().prepare_action(
        binding=binding,
        operation_type=NodeManOperationType.RECONCILE,
        action="added",
        generation=1,
        targets=targets,
        request_summary={},
        batches=batches,
    )
    for index, workflow in enumerate(prepared.workflows, start=1):
        workflow.workflow_id = f"workflow-{index}"
        workflow.dispatch_status = NodeManWorkflowDispatchStatus.SUBMITTED
        workflow.normalized_status = NodeManWorkflowStatus.RUNNING
        workflow.save(update_fields=("workflow_id", "dispatch_status", "normalized_status", "updated_at"))
    expired_at = timezone.now() - timedelta(seconds=DISPATCH_RECOVERY_GRACE_SECONDS + 1)
    MonitorNodeManOperation.objects.filter(pk=prepared.operation.pk).update(updated_at=expired_at)

    class WorkflowClient:
        def list_workflows(self, payload, *, context):
            del context
            workflow_ids = payload["exact_include_conditions"]["workflow_id"]
            return {
                "total": len(workflow_ids),
                "items": [{"workflow_id": workflow_id, "status": "success"} for workflow_id in workflow_ids],
            }

    monkeypatch.setattr(tasks, "NodeManV3HTTPClient", lambda: object())
    monkeypatch.setattr(tasks, "WorkflowClient", lambda client: WorkflowClient())

    result = tasks.poll_operation.run(str(prepared.operation.pk))

    prepared.operation.refresh_from_db()
    assert result["status"] == NodeManOperationStatus.SUCCESS
    assert prepared.operation.status == NodeManOperationStatus.SUCCESS
    assert NodeManExecutionLease.objects.filter(holder_operation=prepared.operation).exists() is False


@pytest.mark.django_db(transaction=True)
def test_duplicate_terminal_callback_is_idempotent_after_fenced_lease_release():
    binding = _database_binding(7)
    target = _database_target(binding, "host:1", 1)
    prepared = NodeManV3TargetOperationCoordinator().prepare_action(
        binding=binding,
        operation_type=NodeManOperationType.RECONCILE,
        action="added",
        generation=1,
        targets=[target],
        request_summary={},
    )
    workflow = prepared.workflows[0]
    workflow.workflow_id = "workflow-1"
    workflow.dispatch_status = NodeManWorkflowDispatchStatus.SUBMITTED
    workflow.normalized_status = NodeManWorkflowStatus.SUCCESS
    workflow.save(update_fields=("workflow_id", "dispatch_status", "normalized_status", "updated_at"))
    prepared.operation.status = NodeManOperationStatus.SUCCESS
    prepared.operation.save(update_fields=("status", "updated_at"))

    assert finalize_target_operation(prepared.operation, [workflow]) is True
    target.refresh_from_db()
    applied_at = target.last_applied_at
    assert finalize_target_operation(prepared.operation, [workflow]) is False
    target.refresh_from_db()

    assert target.last_applied_at == applied_at


@pytest.mark.django_db(transaction=True)
def test_old_terminal_callback_cannot_release_or_apply_an_aba_lease_holder():
    binding = _database_binding(7)
    target = _database_target(binding, "host:1", 1)
    prepared = NodeManV3TargetOperationCoordinator().prepare_action(
        binding=binding,
        operation_type=NodeManOperationType.RECONCILE,
        action="added",
        generation=1,
        targets=[target],
        request_summary={},
    )
    workflow = prepared.workflows[0]
    workflow.workflow_id = "workflow-1"
    workflow.dispatch_status = NodeManWorkflowDispatchStatus.SUBMITTED
    workflow.normalized_status = NodeManWorkflowStatus.SUCCESS
    workflow.save(update_fields=("workflow_id", "dispatch_status", "normalized_status", "updated_at"))
    prepared.operation.status = NodeManOperationStatus.SUCCESS
    prepared.operation.save(update_fields=("status", "updated_at"))
    replacement = binding.operations.create(
        operation_type=NodeManOperationType.RECONCILE,
        generation=1,
        status=NodeManOperationStatus.RUNNING,
    )
    lease = NodeManExecutionLease.objects.get(holder_operation=prepared.operation)
    lease.holder_operation = replacement
    lease.lease_generation += 1
    lease.save(update_fields=("holder_operation", "lease_generation", "updated_at"))

    assert finalize_target_operation(prepared.operation, [workflow]) is False

    target.refresh_from_db()
    lease.refresh_from_db()
    assert target.applied_present is None
    assert lease.holder_operation_id == replacement.id


@pytest.mark.django_db(transaction=True)
def test_incomplete_batch_evidence_keeps_lease_even_if_operation_is_marked_terminal():
    binding = _database_binding(7)
    target = _database_target(binding, "host:1", 1)
    prepared = NodeManV3TargetOperationCoordinator().prepare_action(
        binding=binding,
        operation_type=NodeManOperationType.RECONCILE,
        action="added",
        generation=1,
        targets=[target],
        request_summary={},
    )
    prepared.operation.status = NodeManOperationStatus.FAILED
    prepared.operation.save(update_fields=("status", "updated_at"))

    assert finalize_target_operation(prepared.operation, prepared.workflows) is False
    assert NodeManExecutionLease.objects.filter(holder_operation=prepared.operation).exists() is True
