import logging
from dataclasses import dataclass

from django.db import transaction

from bkmonitor.nodeman_integration.v3.client import NodeManV3UnknownResultError
from bkmonitor.nodeman_integration.v3.exceptions import NodeManV3DefiniteFailure, NodeManV3PayloadError
from monitor_web.collecting.constant import OperationResult
from monitor_web.models import CollectConfigMeta
from monitor_web.models.node_man import (
    MonitorNodeManOperation,
    MonitorNodeManWorkflow,
    NodeManBindingState,
    NodeManIntegrationBinding,
    NodeManOperationStatus,
    NodeManOperationType,
    NodeManResourceType,
    NodeManV3ResultState,
    NodeManWorkflowDispatchStatus,
)
from monitor_web.nodeman_integration.v3.operation import (
    NodeManExecutionLeaseConflict,
    NodeManV3OperationService,
    NodeManV3TargetOperationCoordinator,
    PreparedTargetOperation,
)

from .deploy_policy import CollectDeployPolicyPayloadBuilder, NodeManV3DeployPolicyGateway
from .validation import NodeManV3CapabilityBlocked


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReconcileResult:
    binding_id: int
    generation: int
    trigger: str
    operation_id: str
    prepared: bool


class CollectDeployPolicyReconciler:
    """Submit one desired policy per collection; NodeMan owns member reconciliation."""

    def __init__(self, *, payload_builder=None, gateway=None, operation_service=None):
        self.payload_builder = payload_builder or CollectDeployPolicyPayloadBuilder()
        self.gateway = gateway or NodeManV3DeployPolicyGateway(payload_builder=self.payload_builder)
        self.operation_service = operation_service or NodeManV3OperationService()

    def reconcile(self, *, binding, collect_config, trigger: str, force: bool = False) -> ReconcileResult:
        # Complete validation before recording or issuing any NodeMan write.
        payload = self.payload_builder.build(collect_config)
        prepared = self._prepare(binding, collect_config, payload, trigger=trigger, force=force)
        if prepared is None:
            return ReconcileResult(binding.pk, binding.generation, trigger, "", False)
        transaction.on_commit(lambda: self._dispatch(prepared, payload))
        return ReconcileResult(binding.pk, prepared.operation.generation, trigger, str(prepared.operation.pk), True)

    def reconcile_binding(self, binding_id: int, *, trigger: str = "event") -> ReconcileResult:
        binding = NodeManIntegrationBinding.objects.get(pk=binding_id, resource_type=NodeManResourceType.COLLECT_CONFIG)
        collect_config = CollectConfigMeta.objects.get(pk=int(binding.resource_key))
        return self.reconcile(binding=binding, collect_config=collect_config, trigger=trigger)

    def _prepare(self, binding, collect_config, payload, *, trigger, force):
        fingerprint = self.payload_builder.fingerprint(payload)
        with transaction.atomic():
            current = CollectConfigMeta.objects.select_for_update().get(pk=collect_config.pk)
            if current.deployment_config_id != collect_config.deployment_config_id:
                raise NodeManExecutionLeaseConflict("collection deployment version changed; reload before submitting")
            locked = NodeManIntegrationBinding.objects.select_for_update().get(pk=binding.pk)
            if locked.generation != binding.generation:
                raise NodeManExecutionLeaseConflict("collection policy generation changed; reload before submitting")
            if locked.state != NodeManBindingState.ACTIVE:
                raise NodeManV3PayloadError("collection binding must be active before submitting a policy")
            if locked.collect_targets.filter(node_man_deploy_policy_id__isnull=False).exists():
                raise NodeManV3CapabilityBlocked(
                    "existing per-target deploy policies must be reverse-converged before they are detached; "
                    "the DeployPolicy reverse field is not defined"
                )
            if locked.operations.filter(result_state=NodeManV3ResultState.WRITE_RESULT_UNKNOWN).exists():
                raise NodeManV3UnknownResultError("an earlier collection policy write is unresolved; do not replay it")
            if locked.operations.filter(
                status__in=(NodeManOperationStatus.PENDING, NodeManOperationStatus.DISPATCHING)
            ).exists():
                raise NodeManExecutionLeaseConflict("a collection policy submission is already in progress")
            latest = locked.operations.order_by("-created_at").first()
            if (
                not force
                and locked.node_man_deploy_policy_id
                and locked.node_man_policy_fingerprint == fingerprint
                and latest
                and latest.status in (NodeManOperationStatus.RUNNING, NodeManOperationStatus.SUCCESS)
            ):
                return None

            locked.advance_generation(expected_generation=locked.generation)
            current.operation_result = OperationResult.PREPARING
            current.save(update_fields=("operation_result", "update_time"))
            summary = {"trigger": trigger, "policy_fingerprint": fingerprint, "scopes": payload["scopes"]}
            operation = MonitorNodeManOperation.objects.create(
                binding=locked,
                operation_type=NodeManOperationType.RECONCILE,
                generation=locked.generation,
                config_meta_id=collect_config.pk,
                deployment_config_version_id=collect_config.deployment_config_id,
                request_summary=summary,
                status=NodeManOperationStatus.DISPATCHING,
            )
            # Selector count is not target count. Do not report empty/success before NodeMan expands it.
            workflow = MonitorNodeManWorkflow.objects.create(
                monitor_operation=operation, batch_index=0, target_summary={"scopes": payload["scopes"]}
            )
            return PreparedTargetOperation(operation, (workflow,), ())

    def _dispatch(self, prepared, payload):
        operation = prepared.operation
        try:
            self.operation_service.dispatch_batches(
                binding=operation.binding,
                operation_type=operation.operation_type,
                generation=operation.generation,
                batches=[{"target_summary": {"scopes": payload["scopes"]}, "target_count": 0}],
                request_summary=operation.request_summary,
                submit_batch=lambda batch, *, context: self.gateway.ensure_policy(
                    operation.binding, payload, context=context
                ),
                prepared_operation=operation,
                prepared_workflows=prepared.workflows,
            )
        except NodeManV3DefiniteFailure as error:
            NodeManV3TargetOperationCoordinator.mark_definite_failure(prepared, error)
            raise
        except Exception as error:
            if all(
                workflow.dispatch_status == NodeManWorkflowDispatchStatus.SUBMITTED for workflow in prepared.workflows
            ):
                # The durable poll_pending_operations sweep recovers scheduling failures.
                logger.exception("NodeMan policy submitted; deferred polling must recover operation %s", operation.pk)
                return
            NodeManV3TargetOperationCoordinator.mark_unknown(prepared, error)
            raise
