import logging
from collections import defaultdict

from django.db.models import F, Q

from bkmonitor.nodeman_integration.v3.client import (
    NodeManV3ClientError,
    NodeManV3HTTPClient,
    NodeManV3RequestContext,
)
from bkmonitor.nodeman_integration.v3.client.workflow import WorkflowClient
from monitor_web.models.node_man import (
    MonitorNodeManOperation,
    NodeManIntegrationBinding,
    NodeManOperationStatus,
    NodeManOperationType,
    NodeManResourceType,
    NodeManWorkflowDispatchStatus,
    build_nodeman_resource_key,
)
from monitor_web.nodeman_integration.v3.status import fetch_trigger_statuses


logger = logging.getLogger(__name__)

_PENDING_INSTANCE_STATES = {"init"}
_RUNNING_INSTANCE_STATES = {"launched", "running"}
_FAILED_INSTANCE_STATES = {"failed", "timeout", "terminated", "cancelled", "partial_failed"}
_KNOWN_INSTANCE_STATES = _PENDING_INSTANCE_STATES | _RUNNING_INSTANCE_STATES | _FAILED_INSTANCE_STATES | {"success"}


class NodeManV3CollectStatusService:
    """Expose DeployPolicy trigger state through the existing collection status surface."""

    def __init__(self, *, workflow_client=None):
        self.workflow_client = workflow_client or WorkflowClient(NodeManV3HTTPClient())

    @staticmethod
    def status_key(collect_config) -> int:
        return collect_config.pk

    def fetch_statistics(self, config_data_list):
        configs = list(config_data_list)
        config_by_identity = {
            (
                build_nodeman_resource_key(NodeManResourceType.COLLECT_CONFIG, object_id=config.pk),
                config.bk_tenant_id,
                config.bk_biz_id,
            ): config
            for config in configs
        }
        if not config_by_identity:
            return {}, []

        bindings = list(
            NodeManIntegrationBinding.objects.filter(
                resource_type=NodeManResourceType.COLLECT_CONFIG,
                resource_key__in={identity[0] for identity in config_by_identity},
            )
        )
        config_by_binding_id = {
            binding.pk: config_by_identity[(binding.resource_key, binding.owner_bk_tenant_id, binding.bk_biz_id)]
            for binding in bindings
            if (binding.resource_key, binding.owner_bk_tenant_id, binding.bk_biz_id) in config_by_identity
        }
        if not config_by_binding_id:
            return {}, []

        operations = (
            MonitorNodeManOperation.objects.filter(
                binding_id__in=config_by_binding_id,
                operation_type=NodeManOperationType.RECONCILE,
                generation=F("binding__generation"),
            )
            .select_related("binding")
            .prefetch_related("workflows")
            .order_by("binding_id", "-created_at")
        )
        operation_by_binding_id = {}
        workflows_by_operation_id = {}
        for operation in operations:
            if operation.binding_id in operation_by_binding_id:
                continue
            operation_by_binding_id[operation.binding_id] = operation
            workflows_by_operation_id[operation.pk] = list(operation.workflows.all())

        trigger_ids_by_context = defaultdict(list)
        for operation in operation_by_binding_id.values():
            context_key = self._context_key(operation.binding)
            for workflow in workflows_by_operation_id[operation.pk]:
                if workflow.dispatch_status == NodeManWorkflowDispatchStatus.SUBMITTED and workflow.trigger_id:
                    trigger_ids_by_context[context_key].append(workflow.trigger_id)

        observations = {}
        for context_key, trigger_ids in trigger_ids_by_context.items():
            unique_trigger_ids = list(dict.fromkeys(trigger_ids))
            context = NodeManV3RequestContext(bk_tenant_id=context_key[0], bk_biz_id=context_key[1])
            try:
                context_observations = fetch_trigger_statuses(
                    self.workflow_client,
                    unique_trigger_ids,
                    context=context,
                )
            except NodeManV3ClientError:
                # A failed read must not erase the last known collection counts.
                logger.exception(
                    "Failed to query NodeMan V3 collection status: bk_tenant_id=%s, bk_biz_id=%s",
                    context.bk_tenant_id,
                    context.bk_biz_id,
                )
                continue
            for trigger_id, observation in context_observations.items():
                observations[(context_key, trigger_id)] = observation

        statistics_by_key = {}
        for binding_id, operation in operation_by_binding_id.items():
            context_key = self._context_key(operation.binding)
            trigger_ids = list(
                dict.fromkeys(
                    workflow.trigger_id
                    for workflow in workflows_by_operation_id[operation.pk]
                    if workflow.dispatch_status == NodeManWorkflowDispatchStatus.SUBMITTED and workflow.trigger_id
                )
            )
            trigger_observations = [observations.get((context_key, trigger_id)) for trigger_id in trigger_ids]
            if not trigger_ids or any(observation is None for observation in trigger_observations):
                continue

            config = config_by_binding_id[binding_id]
            distribution = self._merge_distributions(
                observation["distribution"] for observation in trigger_observations
            )
            statistics_by_key[config.pk] = self._statistics(config.pk, distribution)

        config_by_key = {config.pk: config for config in configs if config.pk in statistics_by_key}
        return config_by_key, [statistics_by_key[config.pk] for config in configs if config.pk in statistics_by_key]

    @staticmethod
    def is_task_ready(collect_config) -> bool:
        resource_key = build_nodeman_resource_key(
            NodeManResourceType.COLLECT_CONFIG,
            object_id=collect_config.pk,
        )
        binding = NodeManIntegrationBinding.objects.filter(
            resource_type=NodeManResourceType.COLLECT_CONFIG,
            resource_key=resource_key,
            owner_bk_tenant_id=collect_config.bk_tenant_id,
            bk_biz_id=collect_config.bk_biz_id,
        ).first()
        if binding is None:
            # Kubernetes and other non-NodeMan collections have no V3 task to wait for.
            return True

        operation = (
            MonitorNodeManOperation.objects.filter(
                binding=binding,
                operation_type=NodeManOperationType.RECONCILE,
                generation=binding.generation,
            )
            .order_by("-created_at")
            .first()
        )
        if operation is None:
            return False
        if operation.status not in {NodeManOperationStatus.PENDING, NodeManOperationStatus.DISPATCHING}:
            return True
        return (
            operation.workflows.filter(dispatch_status=NodeManWorkflowDispatchStatus.SUBMITTED)
            .filter(
                (Q(workflow_id__isnull=False) & ~Q(workflow_id="")) | (Q(trigger_id__isnull=False) & ~Q(trigger_id=""))
            )
            .exists()
        )

    @staticmethod
    def _context_key(binding) -> tuple[str, int]:
        return binding.execution_bk_tenant_id, binding.bk_biz_id

    @staticmethod
    def _merge_distributions(distributions) -> dict:
        not_inited_count = 0
        state_counts = defaultdict(int)
        for distribution in distributions:
            distribution = distribution or {}
            not_inited_count += distribution.get("not_inited_count", 0)
            for state, count in distribution.get("state_counts", {}).items():
                state_counts[state] += count
        return {"not_inited_count": not_inited_count, "state_counts": dict(state_counts)}

    @staticmethod
    def _statistics(key: int, distribution: dict) -> dict:
        state_counts = distribution.get("state_counts", {})
        not_inited_count = distribution.get("not_inited_count", 0)
        pending_count = not_inited_count + sum(state_counts.get(state, 0) for state in _PENDING_INSTANCE_STATES)
        running_count = sum(state_counts.get(state, 0) for state in _RUNNING_INSTANCE_STATES)
        unknown_count = sum(count for state, count in state_counts.items() if state not in _KNOWN_INSTANCE_STATES)
        error_count = unknown_count + sum(state_counts.get(state, 0) for state in _FAILED_INSTANCE_STATES)
        total_count = not_inited_count + sum(state_counts.values())
        return {
            "key": key,
            "error_instance_count": error_count,
            "total_instance_count": total_count,
            "pending_instance_count": pending_count,
            "running_instance_count": running_count,
        }
