import logging

from celery import shared_task
from django.db.models import Q

from bkmonitor.nodeman_integration.v3.client import (
    NodeManV3HTTPClient,
    NodeManV3RequestContext,
    NodeManV3TransportError,
)
from bkmonitor.nodeman_integration.v3.client.workflow import WorkflowClient
from monitor_web.collecting.deploy.nodeman_v3.reconciler import CollectTargetReconciler
from monitor_web.models.node_man import (
    MonitorNodeManOperation,
    NodeManBindingState,
    NodeManIntegrationBinding,
    NodeManOperationStatus,
    NodeManResourceType,
)
from monitor_web.nodeman_integration.v3.status import refresh_operation_status
from monitor_web.nodeman_integration.v3.operation import (
    finalize_target_operation,
    recover_submitting_batches,
)
from monitor_web.nodeman_integration.v3.status import TERMINAL_OPERATION_STATUSES


V3_TASK_QUEUE = "celery"
logger = logging.getLogger(__name__)


def _bounded_primary_key_page(queryset, *, cursor=None, upper_bound=None, limit: int = 200):
    if upper_bound is None:
        upper_bound = queryset.order_by("-pk").values_list("pk", flat=True).first()
    if upper_bound is None:
        return [], None
    page = queryset.filter(pk__lte=upper_bound)
    if cursor is not None:
        page = page.filter(pk__gt=cursor)
    ids = list(page.order_by("pk").values_list("pk", flat=True)[:limit])
    return ids, upper_bound


@shared_task(bind=True, max_retries=6, name="monitor_web.nodeman_integration.v3.tasks.poll_operation")
def poll_operation(self, operation_id: str):
    operation = MonitorNodeManOperation.objects.select_related("binding").get(pk=operation_id)
    if operation.status in TERMINAL_OPERATION_STATUSES:
        finalized = finalize_target_operation(operation, list(operation.workflows.all()))
        if finalized or not operation.execution_leases.exists():
            return {"operation_id": operation_id, "status": operation.status, "finalized": finalized}

    if operation.status == NodeManOperationStatus.DISPATCHING:
        recover_submitting_batches(operation)
        operation.refresh_from_db()
        if operation.status in TERMINAL_OPERATION_STATUSES:
            finalized = finalize_target_operation(operation, list(operation.workflows.all()))
            return {"operation_id": operation_id, "status": operation.status, "finalized": finalized}
        if operation.status == NodeManOperationStatus.DISPATCHING:
            return {"operation_id": operation_id, "status": operation.status, "skipped": "dispatch_active"}
    if not operation.binding:
        return {"operation_id": operation_id, "status": operation.status, "skipped": "binding_deleted"}

    context = NodeManV3RequestContext(
        bk_tenant_id=operation.binding.execution_bk_tenant_id,
        bk_biz_id=operation.binding.bk_biz_id,
        monitor_operation_id=str(operation.id),
    )
    try:
        result = refresh_operation_status(
            operation,
            WorkflowClient(NodeManV3HTTPClient()),
            context=context,
            on_terminal=finalize_target_operation,
        )
    except NodeManV3TransportError as error:
        raise self.retry(exc=error, countdown=min(300, 2 ** (self.request.retries + 1))) from error
    response = {
        "operation_id": operation_id,
        "status": result.status,
        "stale_generation": result.stale_generation,
    }
    if result.status in TERMINAL_OPERATION_STATUSES and operation.execution_leases.exists():
        logger.error(
            "NodeMan V3 operation %s is terminal but its workflow evidence cannot release all execution leases",
            operation_id,
        )
        response["blocked"] = "terminal_evidence_incomplete"
    return response


@shared_task(bind=True, name="monitor_web.nodeman_integration.v3.tasks.poll_pending_operations")
def poll_pending_operations(self, limit: int = 200, cursor=None, upper_bound=None):
    queryset = MonitorNodeManOperation.objects.filter(
        Q(
            status__in=(
                NodeManOperationStatus.DISPATCHING,
                NodeManOperationStatus.RUNNING,
                NodeManOperationStatus.UNKNOWN,
            )
        )
        | Q(execution_leases__isnull=False)
    ).distinct()
    operation_ids, upper_bound = _bounded_primary_key_page(
        queryset,
        cursor=cursor,
        upper_bound=upper_bound,
        limit=limit,
    )
    for operation_id in operation_ids:
        poll_operation.apply_async(args=(str(operation_id),), queue=V3_TASK_QUEUE)
    if operation_ids and str(operation_ids[-1]) != str(upper_bound):
        self.apply_async(
            kwargs={
                "limit": limit,
                "cursor": str(operation_ids[-1]),
                "upper_bound": str(upper_bound),
            },
            queue=V3_TASK_QUEUE,
        )
    return len(operation_ids)


@shared_task(name="monitor_web.nodeman_integration.v3.tasks.reconcile_binding")
def reconcile_binding(binding_id: int, trigger: str = "event"):
    result = CollectTargetReconciler().reconcile_binding(binding_id, trigger=trigger)
    return {
        "binding_id": result.binding_id,
        "generation": result.generation,
        "trigger": result.trigger,
        "added": result.added,
        "removed": result.removed,
        "changed": result.changed,
        "unchanged": result.unchanged,
        "inflight": result.inflight,
        "blocked": result.blocked,
    }


@shared_task(bind=True, name="monitor_web.nodeman_integration.v3.tasks.reconcile_active_bindings")
def reconcile_active_bindings(self, limit: int = 200, cursor=None, upper_bound=None):
    queryset = NodeManIntegrationBinding.objects.filter(
        resource_type=NodeManResourceType.COLLECT_CONFIG,
        state__in=(NodeManBindingState.ACTIVE, NodeManBindingState.ORPHANED),
    )
    binding_ids, upper_bound = _bounded_primary_key_page(
        queryset,
        cursor=cursor,
        upper_bound=upper_bound,
        limit=limit,
    )
    for binding_id in binding_ids:
        reconcile_binding.apply_async(args=(binding_id, "periodic"), queue=V3_TASK_QUEUE)
    if binding_ids and str(binding_ids[-1]) != str(upper_bound):
        self.apply_async(
            kwargs={
                "limit": limit,
                "cursor": str(binding_ids[-1]),
                "upper_bound": str(upper_bound),
            },
            queue=V3_TASK_QUEUE,
        )
    return len(binding_ids)
