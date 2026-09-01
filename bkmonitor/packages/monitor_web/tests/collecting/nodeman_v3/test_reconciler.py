from types import SimpleNamespace

import pytest

from bkmonitor.nodeman_integration.v3.exceptions import NodeManV3AdapterPending
from constants.cmdb import TargetNodeType, TargetObjectType
from monitor_web.collecting.deploy.nodeman_v3.reconciler import (
    CollectTargetReconciler,
    DjangoCollectTargetSnapshotStore,
    NodeManV3TargetExecutor,
    StoredTargetState,
    calculate_reconcile_diff,
)
from monitor_web.collecting.deploy.nodeman_v3.targets import CMDBCollectTargetResolver, ResolvedCollectTarget
from monitor_web.collecting.deploy.nodeman_v3.validation import NodeManV3CapabilityBlocked
from monitor_web.models.node_man import (
    CollectDeploymentTarget,
    NodeManIntegrationBinding,
    NodeManResourceType,
)
from monitor_web.nodeman_integration.v3.operation import NodeManExecutionLeaseConflict


def _host(host_id):
    return SimpleNamespace(bk_host_id=host_id)


def _service(service_instance_id, host_id):
    return SimpleNamespace(service_instance_id=service_instance_id, bk_host_id=host_id)


class FakeCMDB:
    def __init__(self):
        self.calls = []

    def get_host_by_id(self, **kwargs):
        self.calls.append(("get_host_by_id", kwargs))
        return [_host(host_id) for host_id in kwargs["bk_host_ids"]]

    def get_host_by_ip(self, **kwargs):
        self.calls.append(("get_host_by_ip", kwargs))
        return [_host(900)]

    def get_host_by_topo_node(self, **kwargs):
        self.calls.append(("get_host_by_topo_node", kwargs))
        return [_host(11), _host(12)]

    def get_host_by_template(self, **kwargs):
        self.calls.append(("get_host_by_template", kwargs))
        return [_host(21)]

    def batch_execute_dynamic_group(self, **kwargs):
        self.calls.append(("batch_execute_dynamic_group", kwargs))
        return {"group-a": [_host(31)], "group-b": [_host(32), _host(31)]}

    def get_service_instance_by_topo_node(self, **kwargs):
        self.calls.append(("get_service_instance_by_topo_node", kwargs))
        return [_service(101, 41)]

    def get_service_instance_by_template(self, **kwargs):
        self.calls.append(("get_service_instance_by_template", kwargs))
        return [_service(102, 42)]


def _collect_config(*, target_object_type, target_node_type, target_nodes, remote=None):
    deployment = SimpleNamespace(
        id=80,
        target_node_type=target_node_type,
        target_nodes=target_nodes,
        remote_collecting_host=remote,
        params={"collector": {"period": 60}},
        plugin_version=SimpleNamespace(config_version=3, info_version=2),
    )
    return SimpleNamespace(
        id=7,
        bk_biz_id=2,
        plugin_id="mysql_exporter",
        target_object_type=target_object_type,
        deployment_config=deployment,
    )


def test_host_target_types_have_stable_sorted_identity_keys():
    cmdb = FakeCMDB()
    resolver = CMDBCollectTargetResolver(cmdb=cmdb)
    cases = [
        (TargetNodeType.INSTANCE, [{"bk_host_id": 2}, {"bk_host_id": 1}], ["host:1", "host:2"]),
        (TargetNodeType.TOPO, [{"bk_obj_id": "module", "bk_inst_id": 3}], ["host:11", "host:12"]),
        (TargetNodeType.SET_TEMPLATE, [{"bk_inst_id": 4}], ["host:21"]),
        (TargetNodeType.SERVICE_TEMPLATE, [{"bk_inst_id": 5}], ["host:21"]),
        (
            TargetNodeType.DYNAMIC_GROUP,
            [{"bk_inst_id": "group-a"}, {"bk_inst_id": "group-b"}],
            ["host:31", "host:32"],
        ),
    ]

    for node_type, target_nodes, expected in cases:
        targets = resolver.resolve(
            _collect_config(
                target_object_type=TargetObjectType.HOST,
                target_node_type=node_type,
                target_nodes=target_nodes,
            )
        )
        assert [target.identity_key for target in targets] == expected


def test_service_target_identity_survives_host_movement_and_marks_execution_change():
    cmdb = FakeCMDB()
    resolver = CMDBCollectTargetResolver(cmdb=cmdb)
    config = _collect_config(
        target_object_type=TargetObjectType.SERVICE,
        target_node_type=TargetNodeType.TOPO,
        target_nodes=[{"bk_obj_id": "module", "bk_inst_id": 3}],
    )

    before = resolver.resolve(config)[0]
    cmdb.get_service_instance_by_topo_node = lambda **kwargs: [_service(101, 99)]
    after = resolver.resolve(config)[0]

    assert before.identity_key == after.identity_key == "service:101"
    assert before.execution_bk_host_id == 41
    assert after.execution_bk_host_id == 99
    assert before.fingerprint != after.fingerprint


def test_template_service_and_remote_collection_keep_observed_identity_separate_from_execution_host():
    cmdb = FakeCMDB()
    resolver = CMDBCollectTargetResolver(cmdb=cmdb)
    config = _collect_config(
        target_object_type=TargetObjectType.SERVICE,
        target_node_type=TargetNodeType.SERVICE_TEMPLATE,
        target_nodes=[{"bk_inst_id": 5}],
        remote={"bk_host_id": 900, "is_collecting_only": True},
    )

    target = resolver.resolve(config)[0]

    assert target.identity_key == "service:102"
    assert target.service_instance_id == 102
    assert target.observed_target == {"bk_host_id": 42, "service_instance_id": 102}
    assert target.execution_bk_host_id == 900
    assert target.remote_target == {"bk_host_id": 42, "service_instance_id": 102}


def _desired(identity, fingerprint):
    return SimpleNamespace(identity_key=identity, fingerprint=fingerprint)


def test_diff_uses_applied_fingerprint_and_preserves_inflight_targets():
    stored = {
        "add": StoredTargetState("add", desired_present=True, applied_present=None),
        "change": StoredTargetState(
            "change", desired_present=True, applied_present=True, desired_fingerprint="old", applied_fingerprint="old"
        ),
        "same": StoredTargetState(
            "same", desired_present=True, applied_present=True, desired_fingerprint="same", applied_fingerprint="same"
        ),
        "remove": StoredTargetState("remove", desired_present=True, applied_present=True),
        "inflight": StoredTargetState("inflight", desired_present=True, applied_present=None, operation_inflight=True),
        "blocked": StoredTargetState("blocked", desired_present=True, applied_present=None, operation_blocked=True),
    }
    desired = {
        target.identity_key: target
        for target in [
            _desired("add", "new"),
            _desired("change", "new"),
            _desired("same", "same"),
            _desired("inflight", "new"),
            _desired("blocked", "new"),
        ]
    }

    diff = calculate_reconcile_diff(stored, desired)

    assert diff.added == ("add",)
    assert diff.changed == ("change",)
    assert diff.removed == ("remove",)
    assert diff.unchanged == ("same",)
    assert diff.inflight == ("inflight",)
    assert diff.blocked == ("blocked",)


class FakeSnapshotStore:
    def __init__(self, plans):
        self.plans = list(plans)
        self.calls = []

    def prepare(self, binding_id, desired):
        self.calls.append((binding_id, tuple(target.identity_key for target in desired)))
        return self.plans.pop(0)

    def mark_applied(self, prepared, identity_keys):
        self.calls.append(("applied", prepared.generation, tuple(identity_keys)))

    def mark_error(self, prepared, identity_keys, error):
        self.calls.append(("error", prepared.generation, tuple(identity_keys), str(error)))


class FakeExecutor:
    def __init__(self):
        self.calls = []

    def execute(self, category, targets, prepared):
        self.calls.append((category, tuple(target.identity_key for target in targets), prepared))


class FakeCoordinator:
    def __init__(self):
        self.calls = []

    def prepare_action(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            operation=SimpleNamespace(
                binding=kwargs["binding"],
                operation_type=kwargs["operation_type"],
                generation=kwargs["generation"],
                request_summary=kwargs["request_summary"],
            ),
            workflows=(SimpleNamespace(),),
        )


def test_event_and_periodic_paths_share_idempotent_reconciler_and_restart_from_store():
    desired = [_desired("host:1", "a")]
    plan = SimpleNamespace(
        generation=3,
        added=(desired[0],),
        changed=(),
        removed=(),
        unchanged=(),
        inflight=(),
        blocked=(),
    )
    no_op = SimpleNamespace(
        generation=3,
        added=(),
        changed=(),
        removed=(),
        unchanged=(desired[0],),
        inflight=(),
        blocked=(),
    )
    store = FakeSnapshotStore([plan, no_op])
    executor = FakeExecutor()
    coordinator = FakeCoordinator()
    resolver = SimpleNamespace(resolve=lambda collect_config: desired)
    reconciler = CollectTargetReconciler(
        resolver=resolver,
        store=store,
        executor=executor,
        coordinator=coordinator,
    )
    binding = SimpleNamespace(id=8, resource_key="7")
    collect_config = SimpleNamespace(id=7)

    event_result = reconciler.reconcile(binding=binding, collect_config=collect_config, trigger="event")
    periodic_result = reconciler.reconcile(binding=binding, collect_config=collect_config, trigger="periodic")

    assert event_result.trigger == "event"
    assert periodic_result.trigger == "periodic"
    assert executor.calls[0][:2] == ("added", ("host:1",))
    assert len(coordinator.calls) == 1
    assert not any(call[0] == "applied" for call in store.calls)
    assert store.calls[-1] == (8, ("host:1",))


def test_scale_down_removes_only_the_exact_stored_target():
    mysql0 = SimpleNamespace(identity_key="service:100", node_man_plugin_instance_id="plugin-a")
    mysql1 = SimpleNamespace(identity_key="service:101", node_man_plugin_instance_id="plugin-b")
    plan = SimpleNamespace(
        generation=4,
        added=(),
        changed=(),
        removed=(mysql0,),
        unchanged=(mysql1,),
        inflight=(),
        blocked=(),
    )
    store = FakeSnapshotStore([plan])
    executor = FakeExecutor()
    coordinator = FakeCoordinator()
    reconciler = CollectTargetReconciler(
        resolver=SimpleNamespace(resolve=lambda collect_config: []),
        store=store,
        executor=executor,
        coordinator=coordinator,
    )

    reconciler.reconcile(
        binding=SimpleNamespace(id=8, resource_key="7"),
        collect_config=SimpleNamespace(id=7),
        trigger="periodic",
    )

    assert executor.calls[0][:2] == ("removed", ("service:100",))


def test_concurrent_reconcile_lease_conflict_defers_without_marking_target_error():
    target = SimpleNamespace(identity_key="host:1")
    plan = SimpleNamespace(
        generation=3,
        added=(target,),
        changed=(),
        removed=(),
        unchanged=(),
        inflight=(),
        blocked=(),
    )
    store = FakeSnapshotStore([plan])
    executor = FakeExecutor()
    coordinator = SimpleNamespace(
        prepare_action=lambda **kwargs: (_ for _ in ()).throw(
            NodeManExecutionLeaseConflict("held by concurrent reconcile")
        )
    )
    reconciler = CollectTargetReconciler(
        resolver=SimpleNamespace(resolve=lambda collect_config: [target]),
        store=store,
        executor=executor,
        coordinator=coordinator,
    )

    reconciler.reconcile(
        binding=SimpleNamespace(id=8, resource_key="7"),
        collect_config=SimpleNamespace(id=7),
        trigger="periodic",
    )

    assert executor.calls == []
    assert not any(call[0] == "error" for call in store.calls)


@pytest.mark.parametrize(
    ("error", "expected_method"),
    [
        (NodeManV3CapabilityBlocked("missing contract"), "definite"),
        (NodeManV3AdapterPending("monitor adapter pending"), "definite"),
        (RuntimeError("write outcome is not classified"), "unknown"),
    ],
)
def test_target_executor_classifies_only_proven_local_blockers_as_definite(error, expected_method):
    class RaisingOperationService:
        def dispatch_batches(self, **kwargs):
            del kwargs
            raise error

    calls = []
    coordinator = SimpleNamespace(
        mark_definite_failure=lambda *args: calls.append("definite"),
        mark_unknown=lambda *args: calls.append("unknown"),
    )
    executor = NodeManV3TargetExecutor(
        orchestrator=SimpleNamespace(
            ensure_targets=lambda targets, **kwargs: None,
            update_targets=lambda targets, **kwargs: None,
            uninstall_targets=lambda targets, **kwargs: None,
        ),
        operation_service=RaisingOperationService(),
        coordinator=coordinator,
    )
    prepared = SimpleNamespace(
        operation=SimpleNamespace(
            binding=SimpleNamespace(),
            operation_type="reconcile",
            generation=1,
            request_summary={},
        ),
        workflows=(SimpleNamespace(),),
    )

    with pytest.raises(type(error), match=str(error)):
        executor.execute("added", [SimpleNamespace(identity_key="host:1")], prepared)

    assert calls == [expected_method]


def _resolved_target(*, host_id=1, service_instance_id=None):
    identity_key = f"service:{service_instance_id}" if service_instance_id else f"host:{host_id}"
    observed_target = {"bk_host_id": host_id}
    if service_instance_id:
        observed_target["service_instance_id"] = service_instance_id
    return ResolvedCollectTarget(
        identity_key=identity_key,
        observed_target=observed_target,
        service_instance_id=service_instance_id,
        execution_bk_host_id=host_id,
        remote_target={},
        plugin_name="mysql_exporter",
        desired_enabled=True,
        desired_revision="3.2:revision",
    )


@pytest.mark.django_db(transaction=True)
def test_snapshot_store_is_idempotent_and_old_generation_cannot_ack_new_desire():
    binding = NodeManIntegrationBinding.objects.create(
        resource_type=NodeManResourceType.COLLECT_CONFIG,
        resource_key="7",
        owner_bk_tenant_id="tenant-a",
        execution_bk_tenant_id="tenant-a",
        bk_biz_id=2,
    )
    store = DjangoCollectTargetSnapshotStore()
    first_target = _resolved_target(host_id=1)

    first = store.prepare(binding.id, [first_target])
    store.mark_applied(first, [first_target.identity_key])
    repeated = store.prepare(binding.id, [first_target])

    assert first.generation == repeated.generation == 1
    assert repeated.added == ()
    assert [target.identity_key for target in repeated.unchanged] == ["host:1"]

    moved_target = _resolved_target(host_id=1)
    object.__setattr__(moved_target, "execution_bk_host_id", 9)
    changed = store.prepare(binding.id, [moved_target])
    store.mark_applied(first, [first_target.identity_key])
    target = CollectDeploymentTarget.objects.get(binding=binding, identity_key="host:1")

    assert changed.generation == 2
    assert [item.identity_key for item in changed.changed] == ["host:1"]
    assert target.applied_fingerprint == first_target.fingerprint
    assert target.desired_fingerprint == moved_target.fingerprint


@pytest.mark.django_db(transaction=True)
def test_removed_snapshot_preserves_exact_external_instance_id_for_scale_down():
    binding = NodeManIntegrationBinding.objects.create(
        resource_type=NodeManResourceType.COLLECT_CONFIG,
        resource_key="8",
        owner_bk_tenant_id="tenant-a",
        execution_bk_tenant_id="tenant-a",
        bk_biz_id=2,
    )
    store = DjangoCollectTargetSnapshotStore()
    target = _resolved_target(host_id=41, service_instance_id=101)
    first = store.prepare(binding.id, [target])
    store.mark_applied(first, [target.identity_key])
    CollectDeploymentTarget.objects.filter(binding=binding).update(
        node_man_plugin_instance_id="plugin-instance-a",
        bkmonitorbeat_config_instance_id="config-instance-a",
    )

    removed = store.prepare(binding.id, [])

    assert removed.generation == 2
    assert len(removed.removed) == 1
    assert removed.removed[0].identity_key == "service:101"
    assert removed.removed[0].node_man_plugin_instance_id == "plugin-instance-a"
    assert removed.removed[0].bkmonitorbeat_config_instance_id == "config-instance-a"
