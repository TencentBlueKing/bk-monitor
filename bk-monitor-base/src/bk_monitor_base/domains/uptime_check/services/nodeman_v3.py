"""NodeMan V3 DeployPolicy adapter for uptime-check tasks."""

from typing import Any, Protocol, cast, final

from bkmonitor.nodeman_integration.backend import node_man_backend
from bkmonitor.nodeman_integration.exceptions import NodeManV3CapabilityBlocked, NodeManV3DefiniteFailure
from bkmonitor.nodeman_integration.resources import NodeManResourceType, build_nodeman_resource_key
from bkmonitor.nodeman_integration.v3.client import NodeManV3UnknownResultError
from bkmonitor.nodeman_integration.v3.exceptions import NodeManV3PayloadError, NodeManV3ResultState
from django.db import transaction
from monitor_web.models.node_man import (
    MonitorNodeManOperation,
    MonitorNodeManWorkflow,
    NodeManIntegrationBinding,
    NodeManOperationStatus,
)

from bk_monitor_base.domains.space.cache import bk_biz_id_to_bk_tenant_id
from bk_monitor_base.domains.uptime_check.models import UptimeCheckTaskModel, UptimeCheckTaskSubscription


class PolicyService(Protocol):
    """Minimal shared-policy surface consumed by the uptime adapter."""

    payload_builder: Any

    def ensure(self, **kwargs: Any) -> Any:
        """Prepare a shared NodeMan V3 policy operation."""


@final
class UptimeCheckNodeManV3Service:
    """Bind uptime tasks to the monitor-wide NodeMan V3 control plane."""

    BACKEND = "v3"
    RESULT_UNKNOWN = NodeManV3ResultState.WRITE_RESULT_UNKNOWN
    IN_PROGRESS_STATUSES = {NodeManOperationStatus.DISPATCHING, NodeManOperationStatus.RUNNING}

    def __init__(self, *, policy_service: PolicyService | None = None) -> None:
        self.policy_service = policy_service or node_man_backend.v3.policy_service()

    @staticmethod
    def policy_name(task_id: int, bk_biz_id: int) -> str:
        return f"bkm-uptime-{task_id}-{bk_biz_id}"

    def preflight_deploy(self, task: UptimeCheckTaskModel, configs: list[dict[str, Any]]) -> None:
        """Validate every desired relation before the first NodeMan write is prepared."""

        desired_biz_ids: set[int] = set()
        for config in configs:
            bk_biz_id = self._target_biz_id(config)
            if bk_biz_id in desired_biz_ids:
                raise NodeManV3PayloadError(f"uptime task {task.pk} has duplicate target business {bk_biz_id}")
            desired_biz_ids.add(bk_biz_id)
            self._validate_policy_payload(task, config)

        relations = list(
            UptimeCheckTaskSubscription.objects.filter(uptimecheck_id=task.pk, is_deleted=False).order_by("pk")
        )
        legacy_relations = [relation.pk for relation in relations if relation.node_man_backend != self.BACKEND]
        if legacy_relations:
            message = f"uptime task {task.pk} still has V2 subscriptions"
            message += f" and cannot be reinterpreted as V3 bindings: {legacy_relations}"
            raise NodeManV3CapabilityBlocked(message)

        removed_biz_ids = sorted({relation.bk_biz_id for relation in relations} - desired_biz_ids)
        if removed_biz_ids:
            message = "uptime target shrink requires the DeployPolicy reverse field"
            message += f"; removed target businesses: {removed_biz_ids}"
            raise NodeManV3CapabilityBlocked(message)

        for relation in relations:
            self._validate_bound_relation(task, relation)
            operation = self._latest_operation(relation)
            if relation.node_man_result_state == self.RESULT_UNKNOWN or (
                operation and operation.result_state == self.RESULT_UNKNOWN
            ):
                raise NodeManV3UnknownResultError(
                    f"uptime task {task.pk} has an unresolved NodeMan write on relation {relation.pk}"
                )
            status = operation.status if operation else relation.node_man_operation_status
            if status in self.IN_PROGRESS_STATUSES:
                raise NodeManV3UnknownResultError(
                    f"uptime task {task.pk} has an in-progress NodeMan write on relation {relation.pk}"
                )

    def ensure(
        self,
        task: UptimeCheckTaskModel,
        config: dict[str, Any],
        *,
        force: bool = False,
    ) -> UptimeCheckTaskSubscription:
        """Create/update one stable forward policy and mirror its control-plane state."""

        bk_biz_id = self._target_biz_id(config)
        owner_tenant_id = bk_biz_id_to_bk_tenant_id(task.bk_biz_id)
        execution_tenant_id = bk_biz_id_to_bk_tenant_id(bk_biz_id)
        resource_key = self._resource_key(task)

        with transaction.atomic():
            relation = self._lock_relation(task.pk, bk_biz_id)
            self._validate_bound_relation(task, relation)
            submission = self.policy_service.ensure(
                resource_type=NodeManResourceType.UPTIME_CHECK,
                resource_key=resource_key,
                owner_bk_tenant_id=owner_tenant_id,
                execution_bk_tenant_id=execution_tenant_id,
                bk_biz_id=bk_biz_id,
                policy_name=self.policy_name(task.pk, bk_biz_id),
                description=f"bk-monitor uptime task {task.pk}, target business {bk_biz_id}",
                scope=config.get("scope") or {},
                steps=config.get("steps") or [],
                force=force,
            )
            relation.subscription_id = submission.binding_id
            relation.node_man_backend = self.BACKEND
            relation.node_man_operation_status = NodeManOperationStatus.DISPATCHING if submission.prepared else ""
            relation.node_man_result_state = ""
            relation.node_man_error = ""
            relation.is_deleted = False
            relation.save(
                update_fields=[
                    "subscription_id",
                    "node_man_backend",
                    "node_man_operation_status",
                    "node_man_result_state",
                    "node_man_error",
                    "is_deleted",
                    "update_time",
                ]
            )

        relation = self._sync_relation(relation)
        if relation.node_man_result_state == self.RESULT_UNKNOWN:
            raise NodeManV3UnknownResultError(
                relation.node_man_error or f"uptime policy relation {relation.pk} has an unresolved write"
            )
        if relation.node_man_operation_status in {
            NodeManOperationStatus.PARTIAL_FAILED,
            NodeManOperationStatus.FAILED,
            NodeManOperationStatus.CANCELLED,
        }:
            raise NodeManV3DefiniteFailure(
                relation.node_man_error
                or f"uptime policy relation {relation.pk} failed with {relation.node_man_operation_status}"
            )
        return relation

    def refresh(self, task: UptimeCheckTaskModel, relation: UptimeCheckTaskSubscription) -> str:
        """Mirror the status maintained by the shared workflow poller."""

        self._validate_bound_relation(task, relation)
        return self._sync_relation(relation).node_man_operation_status or NodeManOperationStatus.UNKNOWN

    def _validate_policy_payload(self, task: UptimeCheckTaskModel, config: dict[str, Any]) -> None:
        bk_biz_id = self._target_biz_id(config)
        self.policy_service.payload_builder.build(
            name=self.policy_name(task.pk, bk_biz_id),
            description=f"bk-monitor uptime task {task.pk}, target business {bk_biz_id}",
            bk_biz_id=bk_biz_id,
            scope=config.get("scope") or {},
            steps=config.get("steps") or [],
        )
        steps = cast(list[dict[str, Any]], config.get("steps") or [])
        for step in steps:
            plugin_config = cast(dict[str, Any], step.get("config") or {})
            if plugin_config.get("config_templates") and not plugin_config.get("plugin_version"):
                raise NodeManV3PayloadError(
                    f"uptime config step for {plugin_config.get('plugin_name') or '<missing>'} requires plugin_version"
                )

    def _lock_relation(self, task_id: int, bk_biz_id: int) -> UptimeCheckTaskSubscription:
        relation, created = UptimeCheckTaskSubscription.objects.select_for_update().get_or_create(
            uptimecheck_id=task_id,
            bk_biz_id=bk_biz_id,
            defaults={"node_man_backend": self.BACKEND},
        )
        if not created and not relation.is_deleted and relation.node_man_backend != self.BACKEND:
            raise NodeManV3CapabilityBlocked(
                f"uptime relation {relation.pk} belongs to {relation.node_man_backend}, not V3"
            )
        if relation.is_deleted:
            relation.subscription_id = 0
            relation.node_man_backend = self.BACKEND
            relation.node_man_policy_fingerprint = ""
            relation.node_man_trigger_id = ""
            relation.node_man_operation_status = ""
            relation.node_man_result_state = ""
            relation.node_man_error = ""
            relation.is_deleted = False
            relation.save()
        return relation

    def _validate_bound_relation(
        self,
        task: UptimeCheckTaskModel,
        relation: UptimeCheckTaskSubscription,
    ) -> None:
        if relation.node_man_backend != self.BACKEND or not relation.subscription_id:
            return
        expected_binding_id = (
            NodeManIntegrationBinding.objects.filter(
                resource_type=NodeManResourceType.UPTIME_CHECK,
                resource_key=self._resource_key(task),
                owner_bk_tenant_id=bk_biz_id_to_bk_tenant_id(task.bk_biz_id),
                execution_bk_tenant_id=bk_biz_id_to_bk_tenant_id(relation.bk_biz_id),
                bk_biz_id=relation.bk_biz_id,
            )
            .values_list("pk", flat=True)
            .first()
        )
        if expected_binding_id != relation.subscription_id:
            message = f"uptime relation {relation.pk} references unexpected V3 binding {relation.subscription_id}"
            message += f"; expected {expected_binding_id or '<missing>'}"
            raise NodeManV3PayloadError(message)

    @staticmethod
    def _latest_operation(relation: UptimeCheckTaskSubscription) -> MonitorNodeManOperation | None:
        if not relation.subscription_id:
            return None
        return (
            MonitorNodeManOperation.objects.filter(binding_id=relation.subscription_id)
            .prefetch_related("workflows")
            .order_by("-created_at")
            .first()
        )

    def _sync_relation(self, relation: UptimeCheckTaskSubscription) -> UptimeCheckTaskSubscription:
        binding = NodeManIntegrationBinding.objects.filter(pk=relation.subscription_id).first()
        if binding is None:
            return relation
        operation = self._latest_operation(relation)
        workflows = (
            list(MonitorNodeManWorkflow.objects.filter(monitor_operation=operation).order_by("batch_index"))
            if operation
            else []
        )
        workflow = workflows[0] if workflows else None
        result_state = operation.result_state if operation else ""
        if not result_state:
            result_state = next((item.result_state for item in workflows if item.result_state), "")
        error = operation.error_summary if operation else ""
        if not error:
            error = next((item.dispatch_error for item in workflows if item.dispatch_error), "")

        relation.node_man_policy_fingerprint = binding.node_man_policy_fingerprint
        relation.node_man_trigger_id = str(workflow.trigger_id or "") if workflow else ""
        relation.node_man_operation_status = operation.status if operation else relation.node_man_operation_status
        relation.node_man_result_state = result_state
        relation.node_man_error = error
        relation.save(
            update_fields=[
                "node_man_policy_fingerprint",
                "node_man_trigger_id",
                "node_man_operation_status",
                "node_man_result_state",
                "node_man_error",
                "update_time",
            ]
        )
        return relation

    @staticmethod
    def _target_biz_id(config: dict[str, Any]) -> int:
        scope = cast(dict[str, Any], config.get("scope") or {})
        value: object = scope.get("bk_biz_id")
        if isinstance(value, bool) or not isinstance(value, int | str):
            raise NodeManV3PayloadError("scope.bk_biz_id must be a positive integer")
        try:
            result = int(value)
        except (TypeError, ValueError) as error:
            raise NodeManV3PayloadError("scope.bk_biz_id must be a positive integer") from error
        if result <= 0:
            raise NodeManV3PayloadError("scope.bk_biz_id must be a positive integer")
        return result

    @staticmethod
    def _resource_key(task: UptimeCheckTaskModel) -> str:
        return build_nodeman_resource_key(NodeManResourceType.UPTIME_CHECK, task_id=task.pk)
