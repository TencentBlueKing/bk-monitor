from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Sequence
from contextlib import nullcontext
from dataclasses import asdict, dataclass
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from bkmonitor.nodeman_integration.v3.client import (
    NodeManV3HTTPClient,
    NodeManV3ClientError,
    NodeManV3RequestContext,
    NodeManV3UnknownResultError,
)
from bkmonitor.nodeman_integration.v3.exceptions import NodeManV3ResultState
from monitor_web.models.node_man import (
    CollectDeploymentTarget,
    MonitorNodeManOperation,
    MonitorNodeManWorkflow,
    NodeManExecutionLease,
    NodeManIntegrationBinding,
    NodeManOperationStatus,
    NodeManWorkflowDispatchStatus,
    NodeManWorkflowStatus,
)


DISPATCH_RECOVERY_GRACE_SECONDS = NodeManV3HTTPClient.DEFAULT_TIMEOUT * 2 + 60


class NodeManExecutionLeaseConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class NodeManExecutionLeaseToken:
    lease_id: int
    execution_bk_tenant_id: str
    bk_host_id: int
    plugin_name: str
    lease_generation: int
    identity_keys: tuple[str, ...]


@dataclass(frozen=True)
class PreparedTargetOperation:
    operation: MonitorNodeManOperation
    workflows: tuple[MonitorNodeManWorkflow, ...]
    lease_tokens: tuple[NodeManExecutionLeaseToken, ...]


class NodeManV3TargetOperationCoordinator:
    """Persist target ownership before any NodeMan write can be attempted."""

    def prepare_action(
        self,
        *,
        binding,
        operation_type: str,
        action: str,
        generation: int,
        targets: Sequence,
        request_summary: dict,
        batches: Sequence[dict] | None = None,
        parent_operation=None,
        config_meta_id: int | None = None,
        deployment_config_version_id: int | None = None,
    ) -> PreparedTargetOperation:
        target_ids = [target.pk for target in targets]
        if not target_ids:
            raise ValueError("target operation requires at least one target")
        if len(target_ids) != len(set(target_ids)):
            raise ValueError("target operation contains duplicate targets")

        with transaction.atomic():
            locked_binding = NodeManIntegrationBinding.objects.select_for_update().get(pk=binding.pk)
            if locked_binding.generation != generation:
                raise ValueError(
                    f"binding {locked_binding.pk} generation changed from {generation} to {locked_binding.generation}"
                )
            locked_targets = list(
                CollectDeploymentTarget.objects.select_for_update()
                .filter(binding=locked_binding, pk__in=target_ids)
                .order_by("identity_key")
            )
            if len(locked_targets) != len(target_ids):
                raise ValueError("target operation contains a missing target")
            if any(target.generation != generation for target in locked_targets):
                raise ValueError("target operation contains a stale target generation")

            targets_by_lease_key = defaultdict(list)
            for target in locked_targets:
                key = (
                    locked_binding.execution_bk_tenant_id,
                    target.execution_bk_host_id,
                    target.plugin_name,
                )
                targets_by_lease_key[key].append(target.identity_key)

            locked_leases = []
            for lease_key in sorted(targets_by_lease_key):
                lease = self._lock_or_create_lease(*lease_key)
                if lease.holder_operation_id:
                    tenant_id, host_id, plugin_name = lease_key
                    raise NodeManExecutionLeaseConflict(
                        f"NodeMan execution lease is held for {tenant_id}/{host_id}/{plugin_name} "
                        f"by operation {lease.holder_operation_id}"
                    )
                locked_leases.append(lease)

            target_identity_keys = [target.identity_key for target in locked_targets]
            normalized_batches = self._normalize_batches(batches, target_identity_keys)
            summary = dict(request_summary)
            summary.update(
                {
                    "target_action": action,
                    "target_identity_keys": target_identity_keys,
                }
            )
            operation = MonitorNodeManOperation.objects.create(
                binding=locked_binding,
                operation_type=operation_type,
                generation=generation,
                request_summary=summary,
                target_count=len(locked_targets),
                status=NodeManOperationStatus.DISPATCHING,
                started_at=timezone.now(),
                parent_operation=parent_operation,
                config_meta_id=config_meta_id,
                deployment_config_version_id=deployment_config_version_id,
            )
            workflows = tuple(
                MonitorNodeManWorkflow.objects.create(
                    monitor_operation=operation,
                    batch_index=batch_index,
                    target_summary=batch["target_summary"],
                    target_count=batch["target_count"],
                    dispatch_status=NodeManWorkflowDispatchStatus.PREPARED,
                )
                for batch_index, batch in enumerate(normalized_batches)
            )

            acquired_at = timezone.now()
            lease_tokens = []
            for lease in locked_leases:
                lease.lease_generation += 1
                lease.holder_operation = operation
                lease.acquired_at = acquired_at
                lease.save(
                    update_fields=(
                        "holder_operation",
                        "lease_generation",
                        "acquired_at",
                        "updated_at",
                    )
                )
                key = (lease.execution_bk_tenant_id, lease.bk_host_id, lease.plugin_name)
                lease_tokens.append(
                    NodeManExecutionLeaseToken(
                        lease_id=lease.id,
                        execution_bk_tenant_id=lease.execution_bk_tenant_id,
                        bk_host_id=lease.bk_host_id,
                        plugin_name=lease.plugin_name,
                        lease_generation=lease.lease_generation,
                        identity_keys=tuple(sorted(targets_by_lease_key[key])),
                    )
                )

            summary["execution_lease_tokens"] = [asdict(token) for token in lease_tokens]
            operation.request_summary = summary
            operation.save(update_fields=("request_summary", "updated_at"))
            CollectDeploymentTarget.objects.filter(pk__in=target_ids).update(
                last_operation=operation,
                updated_at=timezone.now(),
            )

        return PreparedTargetOperation(
            operation=operation,
            workflows=workflows,
            lease_tokens=tuple(lease_tokens),
        )

    @staticmethod
    def _normalize_batches(batches: Sequence[dict] | None, identity_keys: list[str]) -> list[dict]:
        if batches is None:
            return [
                {
                    "target_summary": {"identity_keys": identity_keys},
                    "target_count": len(identity_keys),
                }
            ]
        normalized = []
        covered_identity_keys = []
        for batch in batches:
            target_summary = dict(batch.get("target_summary", {}))
            batch_identity_keys = list(target_summary.get("identity_keys", ()))
            if not batch_identity_keys:
                raise ValueError("each target batch requires target_summary.identity_keys")
            if not set(batch_identity_keys) <= set(identity_keys):
                raise ValueError("target batch contains an identity outside the operation")
            covered_identity_keys.extend(batch_identity_keys)
            target_summary["identity_keys"] = sorted(batch_identity_keys)
            normalized.append(
                {
                    "target_summary": target_summary,
                    "target_count": len(batch_identity_keys),
                }
            )
        if not normalized:
            raise ValueError("target operation requires at least one batch")
        if len(covered_identity_keys) != len(set(covered_identity_keys)):
            raise ValueError("target identity appears in more than one batch")
        if set(covered_identity_keys) != set(identity_keys):
            raise ValueError("target batches must cover every operation identity")
        return normalized

    @staticmethod
    def _lock_or_create_lease(execution_bk_tenant_id: str, bk_host_id: int, plugin_name: str):
        filters = {
            "execution_bk_tenant_id": execution_bk_tenant_id,
            "bk_host_id": bk_host_id,
            "plugin_name": plugin_name,
        }
        lease = NodeManExecutionLease.objects.select_for_update().filter(**filters).first()
        if lease:
            return lease
        try:
            with transaction.atomic():
                NodeManExecutionLease.objects.create(**filters)
        except IntegrityError:
            pass
        return NodeManExecutionLease.objects.select_for_update().get(**filters)

    @staticmethod
    def mark_unknown(prepared: PreparedTargetOperation, error: Exception) -> None:
        _mark_unresolved_batches(
            prepared.operation,
            prepared.workflows,
            current_status=NodeManWorkflowDispatchStatus.UNKNOWN,
            remaining_status=NodeManWorkflowDispatchStatus.DEFINITE_FAILED,
            error=error,
        )

    @staticmethod
    def mark_definite_failure(prepared: PreparedTargetOperation, error: Exception) -> None:
        _mark_all_submitting_batches(
            prepared.workflows,
            dispatch_status=NodeManWorkflowDispatchStatus.DEFINITE_FAILED,
            error=error,
        )
        if any(workflow.dispatch_status == NodeManWorkflowDispatchStatus.SUBMITTED for workflow in prepared.workflows):
            _set_operation_status(prepared.operation, NodeManOperationStatus.RUNNING, error=error)
            NodeManV3OperationService._schedule_poll(prepared.operation.id)
        else:
            _set_operation_status(prepared.operation, NodeManOperationStatus.FAILED, error=error)
            finalize_target_operation(prepared.operation, prepared.workflows)


class NodeManV3OperationService:
    def __init__(
        self,
        *,
        operation_model=MonitorNodeManOperation,
        workflow_model=MonitorNodeManWorkflow,
        poll_scheduler: Callable | None = None,
        terminal_handler: Callable | None = None,
    ):
        self.operation_model = operation_model
        self.workflow_model = workflow_model
        self.poll_scheduler = poll_scheduler or self._schedule_poll
        self.terminal_handler = terminal_handler or finalize_target_operation

    def dispatch_batches(
        self,
        *,
        binding,
        operation_type: str,
        generation: int,
        batches: Sequence[dict],
        request_summary: dict,
        submit_batch: Callable,
        parent_operation=None,
        config_meta_id: int | None = None,
        deployment_config_version_id: int | None = None,
        prepared_operation=None,
        prepared_workflows: Sequence | None = None,
    ):
        batches = list(batches)
        if prepared_operation is None:
            operation, workflows = self._create_operation_and_batches(
                binding=binding,
                operation_type=operation_type,
                generation=generation,
                batches=batches,
                request_summary=request_summary,
                parent_operation=parent_operation,
                config_meta_id=config_meta_id,
                deployment_config_version_id=deployment_config_version_id,
            )
        else:
            operation = prepared_operation
            workflows = list(prepared_workflows or ())
            if len(workflows) != len(batches):
                raise ValueError("prepared workflow count does not match dispatch batches")

        context = NodeManV3RequestContext(
            bk_tenant_id=binding.execution_bk_tenant_id,
            bk_biz_id=binding.bk_biz_id,
            monitor_operation_id=str(operation.id),
        )
        submitted_count = 0
        for batch_index, (batch, workflow) in enumerate(zip(batches, workflows, strict=True)):
            if not self._begin_submission(operation, workflow):
                return operation
            try:
                result = submit_batch(batch, context=context)
                workflow_id = result.get("workflow_id") if isinstance(result, dict) else None
                trigger_id = result.get("trigger_id") if isinstance(result, dict) else None
                if not workflow_id and not trigger_id:
                    raise NodeManV3UnknownResultError(
                        "NodeMan V3 write response has neither workflow_id nor trigger_id"
                    )
            except NodeManV3UnknownResultError as error:
                self._mark_unknown_from(
                    operation,
                    workflows,
                    current_index=batch_index,
                    error=error,
                )
                if submitted_count:
                    self.poll_scheduler(operation.id)
                return operation
            except NodeManV3ClientError as error:
                self._mark_definite_failure_from(
                    operation,
                    workflows,
                    current_index=batch_index,
                    error=error,
                )
                if submitted_count:
                    _set_operation_status(operation, NodeManOperationStatus.RUNNING, error=error)
                    self.poll_scheduler(operation.id)
                else:
                    _set_operation_status(operation, NodeManOperationStatus.FAILED, error=error)
                    self.terminal_handler(operation, workflows)
                return operation

            if not self._persist_submitted(
                operation,
                workflow,
                workflow_id=workflow_id,
                trigger_id=trigger_id,
            ):
                return operation
            submitted_count += 1

        if not workflows:
            _set_operation_status(
                operation,
                NodeManOperationStatus.FAILED,
                error=ValueError("operation has no target batches"),
            )
            self.terminal_handler(operation, workflows)
            return operation

        _set_operation_status(operation, NodeManOperationStatus.RUNNING)
        self.poll_scheduler(operation.id)
        return operation

    def _create_operation_and_batches(self, **kwargs):
        batches = kwargs.pop("batches")
        target_count = sum(batch.get("target_count", 0) for batch in batches)
        atomic = transaction.atomic() if hasattr(self.operation_model, "_meta") else nullcontext()
        with atomic:
            operation = self.operation_model.objects.create(
                **kwargs,
                target_count=target_count,
                status=NodeManOperationStatus.DISPATCHING,
                started_at=timezone.now(),
            )
            workflows = [
                self.workflow_model.objects.create(
                    monitor_operation=operation,
                    batch_index=batch_index,
                    target_summary=batch.get("target_summary", {}),
                    target_count=batch.get("target_count", 0),
                    dispatch_status=NodeManWorkflowDispatchStatus.PREPARED,
                )
                for batch_index, batch in enumerate(batches)
            ]
        return operation, workflows

    def _begin_submission(self, operation, workflow) -> bool:
        if hasattr(self.workflow_model, "_meta"):
            with transaction.atomic():
                locked_operation = self.operation_model.objects.select_for_update().get(pk=operation.pk)
                if locked_operation.status != NodeManOperationStatus.DISPATCHING:
                    operation.status = locked_operation.status
                    return False
                now = timezone.now()
                updated = self.workflow_model.objects.filter(
                    pk=workflow.pk,
                    monitor_operation=locked_operation,
                    dispatch_status=NodeManWorkflowDispatchStatus.PREPARED,
                ).update(
                    dispatch_status=NodeManWorkflowDispatchStatus.SUBMITTING,
                    updated_at=now,
                )
                if updated != 1:
                    operation.refresh_from_db()
                    return False
                locked_operation.updated_at = now
                locked_operation.save(update_fields=("updated_at",))
                operation.updated_at = now
        elif workflow.dispatch_status != NodeManWorkflowDispatchStatus.PREPARED:
            return False
        workflow.dispatch_status = NodeManWorkflowDispatchStatus.SUBMITTING
        if not hasattr(self.workflow_model, "_meta"):
            workflow.save(update_fields=("dispatch_status", "updated_at"))
        return True

    def _persist_submitted(
        self,
        operation,
        workflow,
        *,
        workflow_id: str | None,
        trigger_id: str | None,
    ) -> bool:
        if hasattr(self.workflow_model, "_meta"):
            with transaction.atomic():
                locked_operation = self.operation_model.objects.select_for_update().get(pk=operation.pk)
                if locked_operation.status != NodeManOperationStatus.DISPATCHING:
                    operation.status = locked_operation.status
                    return False
                now = timezone.now()
                updated = self.workflow_model.objects.filter(
                    pk=workflow.pk,
                    monitor_operation=locked_operation,
                    dispatch_status=NodeManWorkflowDispatchStatus.SUBMITTING,
                ).update(
                    workflow_id=str(workflow_id) if workflow_id else None,
                    trigger_id=str(trigger_id) if trigger_id else None,
                    dispatch_status=NodeManWorkflowDispatchStatus.SUBMITTED,
                    dispatch_error="",
                    result_state="",
                    updated_at=now,
                )
                if updated != 1:
                    operation.refresh_from_db()
                    return False
                locked_operation.updated_at = now
                locked_operation.save(update_fields=("updated_at",))
                operation.updated_at = now
        else:
            workflow.workflow_id = str(workflow_id) if workflow_id else None
            workflow.trigger_id = str(trigger_id) if trigger_id else None
            workflow.dispatch_status = NodeManWorkflowDispatchStatus.SUBMITTED
            workflow.dispatch_error = ""
            workflow.result_state = ""
            workflow.save(
                update_fields=(
                    "workflow_id",
                    "trigger_id",
                    "dispatch_status",
                    "dispatch_error",
                    "result_state",
                    "updated_at",
                )
            )
            return True
        workflow.workflow_id = str(workflow_id) if workflow_id else None
        workflow.trigger_id = str(trigger_id) if trigger_id else None
        workflow.dispatch_status = NodeManWorkflowDispatchStatus.SUBMITTED
        workflow.dispatch_error = ""
        workflow.result_state = ""
        return True

    @staticmethod
    def _mark_unknown_from(operation, workflows, *, current_index: int, error: Exception) -> None:
        current = workflows[current_index]
        current.dispatch_status = NodeManWorkflowDispatchStatus.UNKNOWN
        current.dispatch_error = str(error)
        current.result_state = NodeManV3ResultState.WRITE_RESULT_UNKNOWN
        current.normalized_status = NodeManWorkflowStatus.UNKNOWN
        current.save(
            update_fields=("dispatch_status", "dispatch_error", "result_state", "normalized_status", "updated_at")
        )
        for workflow in workflows[current_index + 1 :]:
            workflow.dispatch_status = NodeManWorkflowDispatchStatus.DEFINITE_FAILED
            workflow.dispatch_error = "not dispatched after an unknown earlier batch"
            workflow.result_state = ""
            workflow.normalized_status = NodeManWorkflowStatus.FAILED
            workflow.save(
                update_fields=("dispatch_status", "dispatch_error", "result_state", "normalized_status", "updated_at")
            )
        _set_operation_status(operation, NodeManOperationStatus.UNKNOWN, error=error)

    @staticmethod
    def _mark_definite_failure_from(operation, workflows, *, current_index: int, error: Exception) -> None:
        for workflow in workflows[current_index:]:
            workflow.dispatch_status = NodeManWorkflowDispatchStatus.DEFINITE_FAILED
            workflow.dispatch_error = str(error)
            workflow.result_state = _result_state_for_error(error)
            workflow.normalized_status = NodeManWorkflowStatus.FAILED
            workflow.save(
                update_fields=("dispatch_status", "dispatch_error", "result_state", "normalized_status", "updated_at")
            )

    @staticmethod
    def _schedule_poll(operation_id) -> None:
        from monitor_web.nodeman_integration.v3.tasks import V3_TASK_QUEUE, poll_operation

        poll_operation.apply_async(args=(str(operation_id),), countdown=5, queue=V3_TASK_QUEUE)


def recover_submitting_batches(operation, *, recovery_before=None) -> bool:
    """Conservatively close the crash window without replaying a possible write."""

    if recovery_before is None:
        recovery_before = timezone.now() - timedelta(seconds=DISPATCH_RECOVERY_GRACE_SECONDS)
    with transaction.atomic():
        locked_operation = MonitorNodeManOperation.objects.select_for_update().get(pk=operation.pk)
        if (
            locked_operation.status != NodeManOperationStatus.DISPATCHING
            or locked_operation.updated_at > recovery_before
        ):
            operation.status = locked_operation.status
            return False
        unknown_count = MonitorNodeManWorkflow.objects.filter(
            monitor_operation=locked_operation,
            dispatch_status=NodeManWorkflowDispatchStatus.SUBMITTING,
        ).update(
            dispatch_status=NodeManWorkflowDispatchStatus.UNKNOWN,
            normalized_status=NodeManWorkflowStatus.UNKNOWN,
            dispatch_error="dispatcher exited before a conclusive response was persisted",
            result_state=NodeManV3ResultState.WRITE_RESULT_UNKNOWN,
            updated_at=timezone.now(),
        )
        prepared_count = MonitorNodeManWorkflow.objects.filter(
            monitor_operation=locked_operation,
            dispatch_status=NodeManWorkflowDispatchStatus.PREPARED,
        ).update(
            dispatch_status=NodeManWorkflowDispatchStatus.DEFINITE_FAILED,
            normalized_status=NodeManWorkflowStatus.FAILED,
            dispatch_error="dispatcher exited before this batch was submitted",
            result_state="",
            updated_at=timezone.now(),
        )
        submitted_exists = MonitorNodeManWorkflow.objects.filter(
            monitor_operation=locked_operation,
            dispatch_status=NodeManWorkflowDispatchStatus.SUBMITTED,
        ).exists()
        unknown_exists = MonitorNodeManWorkflow.objects.filter(
            monitor_operation=locked_operation,
            dispatch_status=NodeManWorkflowDispatchStatus.UNKNOWN,
        ).exists()
        if unknown_exists:
            if locked_operation.status != NodeManOperationStatus.UNKNOWN:
                _set_operation_status(
                    locked_operation,
                    NodeManOperationStatus.UNKNOWN,
                    error=NodeManV3UnknownResultError("recovered an unresolved submitting batch"),
                )
        else:
            recovered_status = NodeManOperationStatus.RUNNING if submitted_exists else NodeManOperationStatus.FAILED
            _set_operation_status(
                locked_operation,
                recovered_status,
                error=RuntimeError("recovered a dispatcher that exited before persisting its operation status"),
            )
    recovered = bool(unknown_count or prepared_count or operation.status != locked_operation.status)
    if unknown_exists:
        operation.status = NodeManOperationStatus.UNKNOWN
    else:
        operation.status = NodeManOperationStatus.RUNNING if submitted_exists else NodeManOperationStatus.FAILED
    if not unknown_exists and not submitted_exists:
        finalize_target_operation(operation, list(operation.workflows.all()))
    return recovered


def finalize_target_operation(operation, workflows, *, reconcile_scheduler: Callable | None = None) -> bool:
    terminal_statuses = {
        NodeManOperationStatus.SUCCESS,
        NodeManOperationStatus.PARTIAL_FAILED,
        NodeManOperationStatus.FAILED,
        NodeManOperationStatus.CANCELLED,
    }
    if operation.status not in terminal_statuses:
        return False

    reconcile_binding_id = None
    finalized = False
    with transaction.atomic():
        locked_operation = (
            MonitorNodeManOperation.objects.select_for_update().select_related("binding").get(pk=operation.pk)
        )
        if locked_operation.status not in terminal_statuses:
            return False

        tokens = {
            int(token["lease_id"]): token
            for token in locked_operation.request_summary.get("execution_lease_tokens", ())
        }
        held_leases = list(NodeManExecutionLease.objects.select_for_update().filter(holder_operation=locked_operation))
        matching_leases = [
            lease
            for lease in held_leases
            if lease.id in tokens and lease.lease_generation == int(tokens[lease.id]["lease_generation"])
        ]
        if not matching_leases:
            return False

        locked_workflows = list(
            MonitorNodeManWorkflow.objects.filter(monitor_operation=locked_operation).order_by("batch_index")
        )
        del workflows
        statuses_by_identity = _target_statuses(locked_workflows)
        terminal_workflow_statuses = {
            NodeManWorkflowStatus.SUCCESS,
            NodeManWorkflowStatus.PARTIAL_FAILED,
            NodeManWorkflowStatus.FAILED,
            NodeManWorkflowStatus.CANCELLED,
        }
        matching_leases = [
            lease
            for lease in matching_leases
            if all(
                statuses_by_identity.get(identity_key) in terminal_workflow_statuses
                for identity_key in tokens[lease.id].get("identity_keys", ())
            )
        ]
        if not matching_leases:
            return False
        binding = locked_operation.binding
        current_generation = bool(binding and binding.generation == locked_operation.generation)
        matching_identity_keys = {
            identity_key for lease in matching_leases for identity_key in tokens[lease.id].get("identity_keys", ())
        }

        if current_generation:
            action = locked_operation.request_summary.get("target_action")
            successful = {
                identity_key
                for identity_key, status in statuses_by_identity.items()
                if status == NodeManWorkflowStatus.SUCCESS and identity_key in matching_identity_keys
            }
            failed = {
                identity_key
                for identity_key, status in statuses_by_identity.items()
                if status != NodeManWorkflowStatus.SUCCESS and identity_key in matching_identity_keys
            }
            _apply_successful_targets(locked_operation, action=action, identity_keys=successful)
            if failed:
                CollectDeploymentTarget.objects.filter(
                    binding=binding,
                    generation=locked_operation.generation,
                    last_operation=locked_operation,
                    identity_key__in=failed,
                ).update(
                    error_summary=f"NodeMan operation {locked_operation.status}",
                    updated_at=timezone.now(),
                )
        elif binding:
            reconcile_binding_id = binding.id

        now = timezone.now()
        for lease in matching_leases:
            released = NodeManExecutionLease.objects.filter(
                pk=lease.pk,
                holder_operation=locked_operation,
                lease_generation=lease.lease_generation,
            ).update(holder_operation=None, acquired_at=None, updated_at=now)
            finalized = finalized or bool(released)

    if reconcile_binding_id and finalized:
        scheduler = reconcile_scheduler or _schedule_reconcile
        scheduler(reconcile_binding_id)
    return finalized


def _target_statuses(workflows) -> dict[str, str]:
    statuses = {}
    for workflow in workflows:
        if workflow.dispatch_status in {
            NodeManWorkflowDispatchStatus.SUBMITTING,
            NodeManWorkflowDispatchStatus.UNKNOWN,
        }:
            status = NodeManWorkflowStatus.UNKNOWN
        elif workflow.dispatch_status == NodeManWorkflowDispatchStatus.PREPARED:
            status = NodeManWorkflowStatus.PENDING
        elif workflow.dispatch_status == NodeManWorkflowDispatchStatus.DEFINITE_FAILED:
            status = NodeManWorkflowStatus.FAILED
        else:
            status = workflow.normalized_status
        for identity_key in workflow.target_summary.get("identity_keys", ()):
            previous = statuses.get(identity_key)
            if previous == NodeManWorkflowStatus.UNKNOWN or status == NodeManWorkflowStatus.UNKNOWN:
                statuses[identity_key] = NodeManWorkflowStatus.UNKNOWN
            elif previous and previous != status:
                statuses[identity_key] = NodeManWorkflowStatus.PARTIAL_FAILED
            else:
                statuses[identity_key] = status
    return statuses


def _apply_successful_targets(operation, *, action: str | None, identity_keys: set[str]) -> None:
    if not identity_keys or not operation.binding_id:
        return
    targets = CollectDeploymentTarget.objects.filter(
        binding_id=operation.binding_id,
        generation=operation.generation,
        last_operation=operation,
        identity_key__in=identity_keys,
    )
    now = timezone.now()
    if action == "removed":
        targets.update(
            applied_present=False,
            applied_enabled=False,
            applied_revision="",
            applied_fingerprint="",
            error_summary="",
            last_applied_at=now,
            updated_at=now,
        )
    else:
        targets.update(
            applied_present=True,
            applied_enabled=F("desired_enabled"),
            applied_revision=F("desired_revision"),
            applied_fingerprint=F("desired_fingerprint"),
            error_summary="",
            last_applied_at=now,
            updated_at=now,
        )


def _mark_unresolved_batches(
    operation,
    workflows,
    *,
    current_status: str,
    remaining_status: str,
    error: Exception,
) -> None:
    first = True
    for workflow in workflows:
        if workflow.dispatch_status not in {
            NodeManWorkflowDispatchStatus.PREPARED,
            NodeManWorkflowDispatchStatus.SUBMITTING,
        }:
            continue
        if workflow.dispatch_status == NodeManWorkflowDispatchStatus.SUBMITTING and first:
            workflow.dispatch_status = current_status
            workflow.result_state = (
                NodeManV3ResultState.WRITE_RESULT_UNKNOWN
                if current_status == NodeManWorkflowDispatchStatus.UNKNOWN
                else _result_state_for_error(error)
            )
            first = False
        else:
            workflow.dispatch_status = remaining_status
            workflow.result_state = (
                _result_state_for_error(error)
                if remaining_status != NodeManWorkflowDispatchStatus.DEFINITE_FAILED
                else ""
            )
        workflow.dispatch_error = str(error)
        workflow.normalized_status = (
            NodeManWorkflowStatus.UNKNOWN
            if workflow.dispatch_status == NodeManWorkflowDispatchStatus.UNKNOWN
            else NodeManWorkflowStatus.FAILED
        )
        workflow.save(
            update_fields=("dispatch_status", "dispatch_error", "result_state", "normalized_status", "updated_at")
        )
    _set_operation_status(operation, NodeManOperationStatus.UNKNOWN, error=error)


def _mark_all_submitting_batches(workflows, *, dispatch_status: str, error: Exception) -> None:
    for workflow in workflows:
        if workflow.dispatch_status not in {
            NodeManWorkflowDispatchStatus.PREPARED,
            NodeManWorkflowDispatchStatus.SUBMITTING,
        }:
            continue
        workflow.dispatch_status = dispatch_status
        workflow.dispatch_error = str(error)
        workflow.result_state = _result_state_for_error(error)
        workflow.normalized_status = NodeManWorkflowStatus.FAILED
        workflow.save(
            update_fields=("dispatch_status", "dispatch_error", "result_state", "normalized_status", "updated_at")
        )


def _set_operation_status(operation, status: str, *, error: Exception | None = None) -> None:
    update_fields = ["status", "updated_at"]
    operation.status = status
    if error is not None:
        operation.error_summary = str(error)
        operation.result_state = (
            NodeManV3ResultState.WRITE_RESULT_UNKNOWN
            if status == NodeManOperationStatus.UNKNOWN
            else _result_state_for_error(error)
        )
        update_fields.extend(("error_summary", "result_state"))
    if status in {
        NodeManOperationStatus.SUCCESS,
        NodeManOperationStatus.PARTIAL_FAILED,
        NodeManOperationStatus.FAILED,
        NodeManOperationStatus.CANCELLED,
    }:
        operation.finished_at = timezone.now()
        update_fields.append("finished_at")
    operation.save(update_fields=tuple(update_fields))


def _result_state_for_error(error: Exception) -> str:
    result_state = getattr(error, "result_state", "")
    if result_state in {
        NodeManV3ResultState.UNSUPPORTED,
        NodeManV3ResultState.WRITE_RESULT_UNKNOWN,
    }:
        return result_state
    return ""


def _schedule_reconcile(binding_id: int) -> None:
    from monitor_web.nodeman_integration.v3.tasks import V3_TASK_QUEUE, reconcile_binding

    reconcile_binding.apply_async(args=(binding_id, "terminal"), queue=V3_TASK_QUEUE)
