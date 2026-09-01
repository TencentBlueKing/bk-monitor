from dataclasses import dataclass

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from bkmonitor.nodeman_integration.v3.exceptions import NodeManV3DefiniteFailure
from monitor_web.collecting.deploy.nodeman_v3.orchestrator import NodeManV3Orchestrator
from monitor_web.collecting.deploy.nodeman_v3.targets import CMDBCollectTargetResolver
from monitor_web.models import CollectConfigMeta
from monitor_web.models.node_man import (
    CollectDeploymentTarget,
    NodeManIntegrationBinding,
    NodeManOperationType,
    NodeManOperationStatus,
    NodeManResourceType,
)
from monitor_web.nodeman_integration.v3.operation import (
    NodeManExecutionLeaseConflict,
    NodeManV3OperationService,
    NodeManV3TargetOperationCoordinator,
)


INFLIGHT_OPERATION_STATUSES = {
    NodeManOperationStatus.PENDING,
    NodeManOperationStatus.DISPATCHING,
    NodeManOperationStatus.RUNNING,
    NodeManOperationStatus.UNKNOWN,
}
BLOCKED_OPERATION_STATUSES = {
    NodeManOperationStatus.PARTIAL_FAILED,
    NodeManOperationStatus.FAILED,
    NodeManOperationStatus.CANCELLED,
}


@dataclass(frozen=True)
class StoredTargetState:
    identity_key: str
    desired_present: bool
    applied_present: bool | None
    desired_fingerprint: str = ""
    applied_fingerprint: str = ""
    operation_inflight: bool = False
    operation_blocked: bool = False


@dataclass(frozen=True)
class ReconcileDiff:
    added: tuple[str, ...]
    removed: tuple[str, ...]
    changed: tuple[str, ...]
    unchanged: tuple[str, ...]
    inflight: tuple[str, ...]
    blocked: tuple[str, ...]


@dataclass(frozen=True)
class PreparedReconcile:
    binding_id: int
    generation: int
    added: tuple
    removed: tuple
    changed: tuple
    unchanged: tuple
    inflight: tuple
    blocked: tuple


@dataclass(frozen=True)
class ReconcileResult:
    binding_id: int
    generation: int
    trigger: str
    added: int
    removed: int
    changed: int
    unchanged: int
    inflight: int
    blocked: int


def calculate_reconcile_diff(stored: dict[str, StoredTargetState], desired: dict[str, object]) -> ReconcileDiff:
    added = []
    removed = []
    changed = []
    unchanged = []
    inflight = []
    blocked = []
    for identity_key in sorted(set(stored) | set(desired)):
        state = stored.get(identity_key)
        target = desired.get(identity_key)
        if state and state.operation_inflight:
            inflight.append(identity_key)
        elif state and state.operation_blocked:
            blocked.append(identity_key)
        elif target is None:
            if state and state.applied_present is not False:
                removed.append(identity_key)
            else:
                unchanged.append(identity_key)
        elif not state or state.applied_present is not True:
            added.append(identity_key)
        elif state.applied_fingerprint != target.fingerprint:
            changed.append(identity_key)
        else:
            unchanged.append(identity_key)
    return ReconcileDiff(
        added=tuple(added),
        removed=tuple(removed),
        changed=tuple(changed),
        unchanged=tuple(unchanged),
        inflight=tuple(inflight),
        blocked=tuple(blocked),
    )


class DjangoCollectTargetSnapshotStore:
    def prepare(self, binding_id: int, desired) -> PreparedReconcile:
        desired_by_key = {target.identity_key: target for target in desired}
        with transaction.atomic():
            binding = NodeManIntegrationBinding.objects.select_for_update().get(pk=binding_id)
            rows = list(
                CollectDeploymentTarget.objects.select_related("last_operation")
                .prefetch_related("last_operation__execution_leases")
                .filter(binding=binding)
                .order_by("identity_key")
            )
            rows_by_key = {row.identity_key: row for row in rows}
            snapshot_changed = self._snapshot_changed(rows_by_key, desired_by_key)
            generation = binding.generation
            if snapshot_changed and rows:
                binding.advance_generation(expected_generation=binding.generation)
                generation = binding.generation

            if snapshot_changed:
                rows_by_key = self._persist_snapshot(
                    binding=binding,
                    generation=generation,
                    rows_by_key=rows_by_key,
                    desired_by_key=desired_by_key,
                )

            states = {
                identity_key: StoredTargetState(
                    identity_key=identity_key,
                    desired_present=row.desired_present,
                    applied_present=row.applied_present,
                    desired_fingerprint=row.desired_fingerprint,
                    applied_fingerprint=row.applied_fingerprint,
                    operation_inflight=self._operation_inflight(row),
                    operation_blocked=self._operation_blocked(row),
                )
                for identity_key, row in rows_by_key.items()
            }
            diff = calculate_reconcile_diff(states, desired_by_key)
            return PreparedReconcile(
                binding_id=binding.id,
                generation=generation,
                added=tuple(rows_by_key[key] for key in diff.added),
                removed=tuple(rows_by_key[key] for key in diff.removed),
                changed=tuple(rows_by_key[key] for key in diff.changed),
                unchanged=tuple(rows_by_key[key] for key in diff.unchanged),
                inflight=tuple(rows_by_key[key] for key in diff.inflight),
                blocked=tuple(rows_by_key[key] for key in diff.blocked),
            )

    @staticmethod
    def _snapshot_changed(rows_by_key, desired_by_key) -> bool:
        active_keys = {key for key, row in rows_by_key.items() if row.desired_present}
        if active_keys != set(desired_by_key):
            return True
        return any(rows_by_key[key].desired_fingerprint != target.fingerprint for key, target in desired_by_key.items())

    @staticmethod
    def _persist_snapshot(*, binding, generation, rows_by_key, desired_by_key):
        now = timezone.now()
        to_create = []
        to_update = []
        for identity_key, target in desired_by_key.items():
            row = rows_by_key.get(identity_key)
            if not row:
                row = CollectDeploymentTarget(binding=binding, identity_key=identity_key)
                rows_by_key[identity_key] = row
                to_create.append(row)
            else:
                to_update.append(row)
            row.config_meta_id = int(binding.resource_key)
            row.generation = generation
            row.observed_target = target.observed_target
            row.service_instance_id = target.service_instance_id
            row.execution_bk_host_id = target.execution_bk_host_id
            row.remote_target = target.remote_target
            row.plugin_name = target.plugin_name
            row.desired_present = True
            row.desired_enabled = target.desired_enabled
            row.desired_revision = target.desired_revision
            row.desired_fingerprint = target.fingerprint
            row.error_summary = ""
            row.updated_at = now

        for identity_key, row in rows_by_key.items():
            if identity_key in desired_by_key:
                continue
            row.generation = generation
            row.desired_present = False
            row.desired_enabled = False
            row.desired_fingerprint = ""
            row.error_summary = ""
            row.updated_at = now
            to_update.append(row)

        if to_create:
            CollectDeploymentTarget.objects.bulk_create(to_create)
        if to_update:
            CollectDeploymentTarget.objects.bulk_update(
                to_update,
                fields=(
                    "config_meta_id",
                    "generation",
                    "observed_target",
                    "service_instance_id",
                    "execution_bk_host_id",
                    "remote_target",
                    "plugin_name",
                    "desired_present",
                    "desired_enabled",
                    "desired_revision",
                    "desired_fingerprint",
                    "error_summary",
                    "updated_at",
                ),
            )
        return rows_by_key

    @staticmethod
    def _operation_inflight(row) -> bool:
        if not row.last_operation_id:
            return False
        return bool(
            row.last_operation.status in INFLIGHT_OPERATION_STATUSES or list(row.last_operation.execution_leases.all())
        )

    @staticmethod
    def _operation_blocked(row) -> bool:
        return bool(
            row.last_operation_id
            and row.last_operation.generation == row.generation
            and row.last_operation.status in BLOCKED_OPERATION_STATUSES
        )

    def mark_applied(self, prepared: PreparedReconcile, identity_keys) -> None:
        identity_keys = tuple(identity_keys)
        if not identity_keys:
            return
        base = CollectDeploymentTarget.objects.filter(
            binding_id=prepared.binding_id,
            generation=prepared.generation,
            identity_key__in=identity_keys,
        )
        now = timezone.now()
        base.filter(desired_present=True).update(
            applied_present=True,
            applied_enabled=F("desired_enabled"),
            applied_revision=F("desired_revision"),
            applied_fingerprint=F("desired_fingerprint"),
            error_summary="",
            last_applied_at=now,
            updated_at=now,
        )
        base.filter(desired_present=False).update(
            applied_present=False,
            applied_enabled=False,
            applied_revision="",
            applied_fingerprint="",
            error_summary="",
            last_applied_at=now,
            updated_at=now,
        )

    def mark_error(self, prepared: PreparedReconcile, identity_keys, error: Exception) -> None:
        identity_keys = tuple(identity_keys)
        if not identity_keys:
            return
        CollectDeploymentTarget.objects.filter(
            binding_id=prepared.binding_id,
            generation=prepared.generation,
            identity_key__in=identity_keys,
        ).update(error_summary=str(error), updated_at=timezone.now())


class NodeManV3TargetExecutor:
    def __init__(self, *, orchestrator=None, operation_service=None, coordinator=None):
        self.orchestrator = orchestrator or NodeManV3Orchestrator()
        self.operation_service = operation_service or NodeManV3OperationService()
        self.coordinator = coordinator or NodeManV3TargetOperationCoordinator()

    def execute(self, category: str, targets, prepared) -> None:
        target_method = {
            "added": self.orchestrator.ensure_targets,
            "changed": self.orchestrator.update_targets,
            "removed": self.orchestrator.uninstall_targets,
        }[category]
        batches = [
            {
                "targets": (target,),
                "target_summary": {"identity_keys": [target.identity_key]},
                "target_count": 1,
            }
            for target in targets
        ]

        try:
            self.operation_service.dispatch_batches(
                binding=prepared.operation.binding,
                operation_type=prepared.operation.operation_type,
                generation=prepared.operation.generation,
                batches=batches,
                request_summary=prepared.operation.request_summary,
                submit_batch=lambda current_batch, **kwargs: target_method(
                    current_batch["targets"], context=kwargs["context"]
                ),
                prepared_operation=prepared.operation,
                prepared_workflows=prepared.workflows,
            )
        except NodeManV3DefiniteFailure as error:
            self.coordinator.mark_definite_failure(prepared, error)
            raise
        except Exception as error:
            self.coordinator.mark_unknown(prepared, error)
            raise


class CollectTargetReconciler:
    def __init__(self, *, resolver=None, store=None, executor=None, coordinator=None):
        self.resolver = resolver or CMDBCollectTargetResolver()
        self.store = store or DjangoCollectTargetSnapshotStore()
        self.coordinator = coordinator or NodeManV3TargetOperationCoordinator()
        self.executor = executor or NodeManV3TargetExecutor(coordinator=self.coordinator)

    def reconcile(self, *, binding, collect_config, trigger: str) -> ReconcileResult:
        desired = self.resolver.resolve(collect_config)
        prepared = self.store.prepare(binding.id, desired)
        self._execute(binding, prepared, "added", trigger)
        self._execute(binding, prepared, "changed", trigger)
        self._execute(binding, prepared, "removed", trigger)
        return ReconcileResult(
            binding_id=binding.id,
            generation=prepared.generation,
            trigger=trigger,
            added=len(prepared.added),
            removed=len(prepared.removed),
            changed=len(prepared.changed),
            unchanged=len(prepared.unchanged),
            inflight=len(prepared.inflight),
            blocked=len(prepared.blocked),
        )

    def _execute(self, binding, prepared, category: str, trigger: str) -> None:
        targets = getattr(prepared, category)
        if not targets:
            return
        identity_keys = tuple(target.identity_key for target in targets)
        try:
            target_operation = self.coordinator.prepare_action(
                binding=binding,
                operation_type=NodeManOperationType.RECONCILE,
                action=category,
                generation=prepared.generation,
                targets=targets,
                request_summary={"trigger": trigger},
                batches=[
                    {
                        "target_summary": {"identity_keys": [target.identity_key]},
                        "target_count": 1,
                    }
                    for target in targets
                ],
                config_meta_id=int(binding.resource_key),
            )
            self.executor.execute(category, targets, target_operation)
        except NodeManExecutionLeaseConflict:
            return
        except Exception as error:
            self.store.mark_error(prepared, identity_keys, error)
            raise

    def reconcile_binding(self, binding_id: int, *, trigger: str) -> ReconcileResult:
        binding = NodeManIntegrationBinding.objects.get(pk=binding_id)
        if binding.resource_type != NodeManResourceType.COLLECT_CONFIG:
            raise ValueError(f"binding {binding_id} is not a collect configuration")
        collect_config = CollectConfigMeta.objects.select_related("deployment_config__plugin_version").get(
            pk=int(binding.resource_key)
        )
        return self.reconcile(binding=binding, collect_config=collect_config, trigger=trigger)
