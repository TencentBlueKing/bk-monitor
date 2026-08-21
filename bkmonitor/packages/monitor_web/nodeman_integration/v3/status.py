from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from bkmonitor.nodeman_integration.v3.client import NodeManV3RequestContext
from monitor_web.models.node_man import (
    MonitorNodeManOperation,
    MonitorNodeManWorkflow,
    NodeManOperationStatus,
    NodeManWorkflowDispatchStatus,
    NodeManWorkflowStatus,
)


TERMINAL_OPERATION_STATUSES = {
    NodeManOperationStatus.SUCCESS,
    NodeManOperationStatus.PARTIAL_FAILED,
    NodeManOperationStatus.FAILED,
    NodeManOperationStatus.CANCELLED,
}
TERMINAL_WORKFLOW_STATUSES = {
    NodeManWorkflowStatus.SUCCESS,
    NodeManWorkflowStatus.PARTIAL_FAILED,
    NodeManWorkflowStatus.FAILED,
    NodeManWorkflowStatus.CANCELLED,
}


@dataclass(frozen=True)
class OperationRefreshResult:
    status: str
    stale_generation: bool
    workflow_count: int


def normalize_workflow_status(raw_status: str | None) -> str:
    mapping = {
        "running": NodeManWorkflowStatus.RUNNING,
        "success": NodeManWorkflowStatus.SUCCESS,
        "partial_failed": NodeManWorkflowStatus.PARTIAL_FAILED,
        "failed": NodeManWorkflowStatus.FAILED,
        "cancelled": NodeManWorkflowStatus.CANCELLED,
    }
    return mapping.get(raw_status, NodeManWorkflowStatus.UNKNOWN)


def aggregate_workflow_status(statuses: list[str]) -> str:
    if not statuses or NodeManWorkflowStatus.UNKNOWN in statuses:
        return NodeManOperationStatus.UNKNOWN
    if NodeManWorkflowStatus.RUNNING in statuses or NodeManWorkflowStatus.PENDING in statuses:
        return NodeManOperationStatus.RUNNING
    if all(status == NodeManWorkflowStatus.SUCCESS for status in statuses):
        return NodeManOperationStatus.SUCCESS
    if all(status == NodeManWorkflowStatus.FAILED for status in statuses):
        return NodeManOperationStatus.FAILED
    if all(status == NodeManWorkflowStatus.CANCELLED for status in statuses):
        return NodeManOperationStatus.CANCELLED
    return NodeManOperationStatus.PARTIAL_FAILED


def fetch_workflow_statuses(
    workflow_client,
    workflow_ids: list[str],
    *,
    context: NodeManV3RequestContext,
    page_size: int = 100,
) -> dict[str, dict]:
    if not workflow_ids:
        return {}

    result = {}
    offset = 0
    while True:
        response = workflow_client.list_workflows(
            {
                "exact_include_conditions": {"workflow_id": workflow_ids},
                "page": {"offset": offset, "limit": page_size},
            },
            context=context,
        )
        items = response.get("items", [])
        for item in items:
            if item.get("workflow_id"):
                result[str(item["workflow_id"])] = item

        offset += len(items)
        total = response.get("total", len(items))
        if not items or offset >= total:
            break
    return result


def is_current_generation(operation) -> bool:
    return not operation.binding or operation.binding.generation == operation.generation


def refresh_operation_status(
    operation,
    workflow_client,
    *,
    context: NodeManV3RequestContext,
    on_terminal=None,
    on_current_terminal=None,
    page_size: int = 100,
) -> OperationRefreshResult:
    workflows = list(operation.workflows.all())
    submitted_workflows = [
        workflow
        for workflow in workflows
        if workflow.dispatch_status == NodeManWorkflowDispatchStatus.SUBMITTED and workflow.workflow_id
    ]
    workflow_map = fetch_workflow_statuses(
        workflow_client,
        [workflow.workflow_id for workflow in submitted_workflows],
        context=context,
        page_size=page_size,
    )
    if hasattr(operation, "_meta"):
        operation, workflows, status = _commit_workflow_observations(operation, workflow_map)
    else:
        status = _commit_in_memory_observations(operation, workflows, workflow_map)

    stale_generation = not is_current_generation(operation)
    if status in TERMINAL_OPERATION_STATUSES:
        if on_terminal:
            on_terminal(operation, workflows)
        if not stale_generation and on_current_terminal:
            on_current_terminal(operation, workflows)
    return OperationRefreshResult(
        status=status,
        stale_generation=stale_generation,
        workflow_count=len(workflows),
    )


def _commit_workflow_observations(operation, workflow_map):
    with transaction.atomic():
        locked_operation = (
            MonitorNodeManOperation.objects.select_for_update().select_related("binding").get(pk=operation.pk)
        )
        workflows = list(
            MonitorNodeManWorkflow.objects.select_for_update()
            .filter(monitor_operation=locked_operation)
            .order_by("batch_index")
        )
        status = _apply_workflow_observations(workflows, workflow_map)
        submitted_workflows = [
            workflow
            for workflow in workflows
            if workflow.dispatch_status == NodeManWorkflowDispatchStatus.SUBMITTED and workflow.workflow_id
        ]
        if submitted_workflows:
            MonitorNodeManWorkflow.objects.bulk_update(
                submitted_workflows,
                fields=("raw_status", "normalized_status", "last_synced_at", "updated_at"),
            )
        if locked_operation.status in TERMINAL_OPERATION_STATUSES:
            status = locked_operation.status
        elif status != locked_operation.status:
            locked_operation.transition_to(status)
    return locked_operation, workflows, status


def _commit_in_memory_observations(operation, workflows, workflow_map):
    status = _apply_workflow_observations(workflows, workflow_map)
    submitted_workflows = [
        workflow
        for workflow in workflows
        if workflow.dispatch_status == NodeManWorkflowDispatchStatus.SUBMITTED and workflow.workflow_id
    ]
    if submitted_workflows:
        MonitorNodeManWorkflow.objects.bulk_update(
            submitted_workflows,
            fields=("raw_status", "normalized_status", "last_synced_at", "updated_at"),
        )
    if status != operation.status:
        operation.transition_to(status)
    return status


def _apply_workflow_observations(workflows, workflow_map):
    synced_at = timezone.now()
    normalized_statuses = []
    for workflow in workflows:
        if workflow.dispatch_status == NodeManWorkflowDispatchStatus.SUBMITTED:
            remote = workflow_map.get(workflow.workflow_id, {})
            raw_status = remote.get("status", "")
            observed_status = normalize_workflow_status(raw_status)
            merged_status = _merge_workflow_status(workflow.normalized_status, observed_status)
            if merged_status == observed_status:
                workflow.raw_status = raw_status
            workflow.normalized_status = merged_status
            workflow.last_synced_at = synced_at
            workflow.updated_at = synced_at
        elif workflow.dispatch_status == NodeManWorkflowDispatchStatus.DEFINITE_FAILED:
            workflow.normalized_status = NodeManWorkflowStatus.FAILED
        elif workflow.dispatch_status == NodeManWorkflowDispatchStatus.PREPARED:
            workflow.normalized_status = NodeManWorkflowStatus.PENDING
        else:
            workflow.normalized_status = NodeManWorkflowStatus.UNKNOWN
        normalized_statuses.append(workflow.normalized_status)
    return aggregate_workflow_status(normalized_statuses)


def _merge_workflow_status(current_status: str, observed_status: str) -> str:
    if current_status in TERMINAL_WORKFLOW_STATUSES:
        return current_status
    if observed_status in TERMINAL_WORKFLOW_STATUSES:
        return observed_status
    if observed_status == NodeManWorkflowStatus.RUNNING:
        return observed_status
    if current_status == NodeManWorkflowStatus.RUNNING and observed_status == NodeManWorkflowStatus.UNKNOWN:
        return current_status
    return observed_status
