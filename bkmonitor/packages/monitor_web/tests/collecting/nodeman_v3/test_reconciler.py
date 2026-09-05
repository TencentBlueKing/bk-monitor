from types import SimpleNamespace

import pytest
from django.db import transaction

from bkmonitor.nodeman_integration.v3.client import NodeManV3UnknownResultError
from bkmonitor.nodeman_integration.v3.exceptions import NodeManV3AdapterPending, NodeManV3ResultState
from monitor_web.collecting.deploy.nodeman_v3.deploy_policy import (
    CollectDeployPolicyPayloadBuilder,
    NodeManV3DeployPolicyGateway,
)
from monitor_web.collecting.deploy.nodeman_v3.reconciler import CollectDeployPolicyReconciler
from monitor_web.collecting.deploy.nodeman_v3.validation import NodeManV3CapabilityBlocked
from monitor_web.models import CollectConfigMeta, DeploymentConfigVersion
from monitor_web.models.plugin import (
    CollectorPluginMeta,
    CollectorPluginConfig,
    CollectorPluginInfo,
    PluginVersionHistory,
)
from monitor_web.models.node_man import (
    CollectDeploymentTarget,
    MonitorNodeManOperation,
    NodeManBindingState,
    NodeManIntegrationBinding,
    NodeManOperationStatus,
    NodeManOperationType,
    NodeManResourceType,
)
from monitor_web.nodeman_integration.v3.operation import NodeManExecutionLeaseConflict, NodeManV3OperationService
from monitor_web.tests.collecting.nodeman_v3.test_deploy_policy import FakeDeployPolicyClient


@pytest.fixture
def collection(db):
    plugin = CollectorPluginMeta.objects.create(bk_tenant_id="tenant-a", plugin_id="test-script", plugin_type="Script")
    version = PluginVersionHistory.objects.create(
        bk_tenant_id="tenant-a",
        plugin_id=plugin.plugin_id,
        config=CollectorPluginConfig.objects.create(),
        info=CollectorPluginInfo.objects.create(),
        stage="release",
        is_packaged=True,
    )
    deployment = DeploymentConfigVersion.objects.create(
        plugin_version=version,
        config_meta_id=0,
        target_node_type="INSTANCE",
        target_nodes=[{"bk_host_id": 41}, {"bk_host_id": 42}],
        params={"collector": {"period": 60}, "plugin": {}},
    )
    collection = CollectConfigMeta.objects.create(
        bk_tenant_id="tenant-a",
        bk_biz_id=2,
        name="test collection",
        plugin_id=plugin.plugin_id,
        collect_type="Script",
        target_object_type="HOST",
        deployment_config=deployment,
        last_operation="CREATE",
        operation_result="PREPARING",
    )
    deployment.config_meta_id = collection.pk
    deployment.save()
    return collection


@pytest.fixture
def policy_case(collection):
    binding = NodeManIntegrationBinding.objects.create(
        resource_type=NodeManResourceType.COLLECT_CONFIG,
        resource_key=str(collection.pk),
        owner_bk_tenant_id="tenant-a",
        execution_bk_tenant_id="tenant-a",
        bk_biz_id=2,
    )
    client = FakeDeployPolicyClient()
    builder = CollectDeployPolicyPayloadBuilder(
        step_builder=lambda config, deployment: [
            {
                "config": {
                    "plugin_name": "bkmonitorbeat",
                    "config_templates": [{"name": "test.conf", "content": "{{ period }}"}],
                },
                "params": {
                    "context": {
                        **deployment.params["collector"],
                        "version": deployment.plugin_version.config_version,
                    }
                },
            }
        ]
    )
    scheduled = []
    service = NodeManV3OperationService(poll_scheduler=lambda operation_id: scheduled.append(operation_id))
    reconciler = CollectDeployPolicyReconciler(
        payload_builder=builder,
        gateway=NodeManV3DeployPolicyGateway(client=client, payload_builder=builder),
        operation_service=service,
    )
    return SimpleNamespace(
        binding=binding,
        collection=collection,
        client=client,
        builder=builder,
        reconciler=reconciler,
        scheduled=scheduled,
    )


def submit(case, callbacks, *, force=False):
    case.binding.refresh_from_db()
    with callbacks(execute=True):
        return case.reconciler.reconcile(
            binding=case.binding,
            collect_config=case.collection,
            trigger="test",
            force=force,
        )


def test_many_hosts_create_one_policy_and_keep_trigger_distinct(policy_case, django_capture_on_commit_callbacks):
    case = policy_case
    result = submit(case, django_capture_on_commit_callbacks)
    assert result.prepared is True
    assert [call[0] for call in case.client.calls] == ["list", "create", "execute"]
    payload = case.client.calls[1][1]
    assert payload["scopes"][0]["scope"]["instance_ids"] == [41, 42]
    assert payload["name"] == f"bkm-collect-{case.collection.pk}"
    operation = MonitorNodeManOperation.objects.get(pk=result.operation_id)
    assert operation.status == NodeManOperationStatus.RUNNING
    assert operation.target_count == 0
    workflow = operation.workflows.get()
    assert workflow.trigger_id == "trigger-301"
    assert workflow.workflow_id is None
    assert CollectDeploymentTarget.objects.count() == 0
    assert case.scheduled == [operation.pk]
    assert "period" not in operation.request_summary  # do not persist secret-bearing full contexts


def test_no_remote_write_until_outer_transaction_commits(policy_case, django_capture_on_commit_callbacks):
    case = policy_case
    with django_capture_on_commit_callbacks(execute=True):
        with transaction.atomic():
            result = case.reconciler.reconcile(binding=case.binding, collect_config=case.collection, trigger="test")
            assert MonitorNodeManOperation.objects.filter(pk=result.operation_id).exists()
            assert case.client.calls == []
        assert case.client.calls == []
    assert len(case.client.calls) == 3


def test_transaction_rollback_discards_submission(policy_case, django_capture_on_commit_callbacks):
    case = policy_case
    with django_capture_on_commit_callbacks(execute=True):
        with pytest.raises(ValueError, match="rollback"):
            with transaction.atomic():
                case.reconciler.reconcile(binding=case.binding, collect_config=case.collection, trigger="test")
                raise ValueError("rollback")
    assert case.client.calls == []
    assert MonitorNodeManOperation.objects.count() == 0


def test_unchanged_policy_is_not_reexecuted_but_explicit_run_is(policy_case, django_capture_on_commit_callbacks):
    case = policy_case
    submit(case, django_capture_on_commit_callbacks)
    assert submit(case, django_capture_on_commit_callbacks).prepared is False
    assert len(case.client.calls) == 3
    assert submit(case, django_capture_on_commit_callbacks, force=True).prepared is True
    assert [call[0] for call in case.client.calls[3:]] == ["update", "execute"]


@pytest.mark.parametrize("change", ["shrink", "context", "dynamic_group"])
def test_edits_reuse_same_policy_and_replace_desired_scope_or_specs(
    policy_case,
    django_capture_on_commit_callbacks,
    change,
):
    case = policy_case
    submit(case, django_capture_on_commit_callbacks)
    deployment = case.collection.deployment_config
    if change == "shrink":
        deployment.target_nodes = [{"bk_host_id": 42}]
    elif change == "context":
        deployment.params["collector"]["period"] = 30
    else:
        deployment.target_node_type = "DYNAMIC_GROUP"
        deployment.target_nodes = [{"bk_inst_id": "group-1"}]
    deployment.save()
    submit(case, django_capture_on_commit_callbacks)
    assert [call[0] for call in case.client.calls] == ["list", "create", "execute", "update", "execute"]
    updated = case.client.calls[3][1]["deploy_policies"][0]
    assert updated["deploy_policy_id"] == 301
    if change == "shrink":
        assert updated["scopes"][0]["scope"]["instance_ids"] == [42]
    elif change == "context":
        assert updated["specs"][0]["param"]["custom_config_context"]["period"] == 30
    else:
        assert updated["scopes"][0]["scope"]["dynamic_group_ids"] == ["group-1"]


def test_unknown_write_is_durable_and_blocks_later_replay(policy_case, django_capture_on_commit_callbacks):
    case = policy_case
    case.client.execute = lambda *args, **kwargs: {}  # NodeMan may have accepted the write.
    result = submit(case, django_capture_on_commit_callbacks)
    operation = MonitorNodeManOperation.objects.get(pk=result.operation_id)
    assert operation.result_state == NodeManV3ResultState.WRITE_RESULT_UNKNOWN
    assert operation.status == NodeManOperationStatus.UNKNOWN
    calls = len(case.client.calls)
    with pytest.raises(NodeManV3UnknownResultError, match="unresolved"):
        submit(case, django_capture_on_commit_callbacks, force=True)
    assert len(case.client.calls) == calls


def test_existing_target_policies_require_explicit_migration(policy_case, django_capture_on_commit_callbacks):
    case = policy_case
    CollectDeploymentTarget.objects.create(
        binding=case.binding,
        config_meta_id=case.collection.pk,
        generation=case.binding.generation,
        identity_key="host:41",
        execution_bk_host_id=41,
        plugin_name="bkmonitorbeat",
        node_man_deploy_policy_id=99,
    )
    with pytest.raises(NodeManV3AdapterPending, match="require migration"):
        submit(case, django_capture_on_commit_callbacks)
    assert case.client.calls == []


@pytest.mark.parametrize("state", [NodeManBindingState.DELETING, NodeManBindingState.ORPHANED])
def test_inactive_binding_is_not_silently_reactivated(policy_case, django_capture_on_commit_callbacks, state):
    case = policy_case
    case.binding.state = state
    case.binding.save()
    with pytest.raises(NodeManV3AdapterPending, match="cleanup"):
        submit(case, django_capture_on_commit_callbacks)
    assert case.client.calls == []


def test_concurrent_dispatch_is_rejected(policy_case, django_capture_on_commit_callbacks):
    case = policy_case
    MonitorNodeManOperation.objects.create(
        binding=case.binding,
        generation=case.binding.generation,
        operation_type=NodeManOperationType.RECONCILE,
        status=NodeManOperationStatus.DISPATCHING,
    )
    with pytest.raises(NodeManExecutionLeaseConflict, match="already in progress"):
        submit(case, django_capture_on_commit_callbacks)
    assert case.client.calls == []


def test_stale_desired_version_cannot_overwrite_newer_policy(policy_case, django_capture_on_commit_callbacks):
    case = policy_case
    stale = CollectConfigMeta.objects.get(pk=case.collection.pk)
    deployment = case.collection.deployment_config
    deployment.pk = None
    deployment.save()
    CollectConfigMeta.objects.filter(pk=case.collection.pk).update(deployment_config=deployment)
    case.collection = stale
    with pytest.raises(NodeManExecutionLeaseConflict, match="deployment version changed"):
        submit(case, django_capture_on_commit_callbacks)
    assert case.client.calls == []


@pytest.mark.parametrize("condition", ["remote", "stopped"])
def test_unsupported_collection_is_blocked_before_policy_submission(
    policy_case,
    django_capture_on_commit_callbacks,
    condition,
):
    case = policy_case
    if condition == "remote":
        case.collection.deployment_config.remote_collecting_host = {"bk_host_id": 100}
    else:
        case.collection.last_operation = "STOP"
    with pytest.raises(NodeManV3CapabilityBlocked):
        submit(case, django_capture_on_commit_callbacks)
    assert case.client.calls == []
    assert MonitorNodeManOperation.objects.count() == 0


def test_poll_scheduler_failure_does_not_reclassify_a_known_write(policy_case, django_capture_on_commit_callbacks):
    case = policy_case

    def fail_schedule(operation_id):
        raise RuntimeError("broker unavailable")

    case.reconciler.operation_service.poll_scheduler = fail_schedule
    result = submit(case, django_capture_on_commit_callbacks)
    operation = MonitorNodeManOperation.objects.get(pk=result.operation_id)
    assert operation.status == NodeManOperationStatus.RUNNING
    assert operation.result_state == ""
    assert operation.workflows.get().trigger_id == "trigger-301"


def test_installer_edit_and_upgrade_submit_committed_deployment_versions(
    policy_case,
    django_capture_on_commit_callbacks,
    monkeypatch,
):
    from monitor_web.collecting.deploy.nodeman_v3.installer import NodeManV3Installer

    case = policy_case
    submit(case, django_capture_on_commit_callbacks)
    installer = NodeManV3Installer(case.collection, reconciler=case.reconciler)
    monkeypatch.setattr(installer, "_node_diff", lambda *args: {"is_modified": True})
    with django_capture_on_commit_callbacks(execute=True):
        response = installer.install(
            {
                "target_node_type": "TOPO",
                "target_nodes": [{"bk_obj_id": "module", "bk_inst_id": 8}],
                "params": {"collector": {"period": 30}},
            },
            "EDIT",
        )
        assert len(case.client.calls) == 3
    assert len(case.client.calls) == 5
    case.collection.refresh_from_db()
    assert case.collection.deployment_config_id == response["deployment_id"]
    assert case.collection.deployment_config.subscription_id == 0
    assert case.collection.deployment_config.task_ids == []
    assert case.client.calls[-2][1]["deploy_policies"][0]["scopes"][0]["type"] == "topo"

    release = PluginVersionHistory.objects.get(pk=case.collection.deployment_config.plugin_version_id)
    release.pk = None
    release.config_version = 2
    release.save()
    with django_capture_on_commit_callbacks(execute=True):
        result = installer.upgrade({"collector": {"period": 60}, "plugin": {}})
    assert len(case.client.calls) == 7
    case.collection.refresh_from_db()
    assert case.collection.deployment_config_id == result["deployment_id"]
    assert case.collection.deployment_config.plugin_version_id == release.pk
    assert case.client.calls[-2][1]["deploy_policies"][0]["deploy_policy_id"] == 301


def test_installer_invalid_edit_rolls_back_version_and_sends_nothing(
    policy_case,
    django_capture_on_commit_callbacks,
    monkeypatch,
):
    from monitor_web.collecting.deploy.nodeman_v3.installer import NodeManV3Installer
    from bkmonitor.nodeman_integration.v3.exceptions import NodeManV3PayloadError

    case = policy_case
    original_version = case.collection.deployment_config_id
    installer = NodeManV3Installer(case.collection, reconciler=case.reconciler)
    monkeypatch.setattr(installer, "_node_diff", lambda *args: {})
    with django_capture_on_commit_callbacks(execute=True):
        with pytest.raises(NodeManV3PayloadError):
            installer.install(
                {
                    "target_node_type": "INSTANCE",
                    "target_nodes": [],
                    "params": {"collector": {"period": 60}},
                },
                "EDIT",
            )
    case.collection.refresh_from_db()
    assert case.collection.deployment_config_id == original_version
    assert DeploymentConfigVersion.objects.count() == 1
    assert case.client.calls == []


def test_installer_creates_new_collection_and_policy_in_one_committed_operation(
    policy_case,
    django_capture_on_commit_callbacks,
):
    from monitor_web.collecting.deploy.nodeman_v3.installer import NodeManV3Installer

    case = policy_case
    collection = CollectConfigMeta(
        bk_tenant_id="tenant-a",
        bk_biz_id=2,
        name="new collection",
        plugin_id=case.collection.plugin_id,
        collect_type="Script",
        target_object_type="HOST",
    )
    installer = NodeManV3Installer(collection, reconciler=case.reconciler)
    with django_capture_on_commit_callbacks(execute=True):
        result = installer.install(
            {
                "target_node_type": "INSTANCE",
                "target_nodes": [{"bk_host_id": 41}, {"bk_host_id": 42}],
                "params": {"collector": {"period": 60}},
            },
            "CREATE",
        )
        assert case.client.calls == []
    assert collection.pk == result["id"]
    assert [call[0] for call in case.client.calls] == ["list", "create", "execute"]
    assert case.client.calls[1][1]["name"] == f"bkm-collect-{collection.pk}"
    binding = NodeManIntegrationBinding.objects.get(resource_key=str(collection.pk))
    assert binding.node_man_deploy_policy_id == 301
    assert binding.operations.get().deployment_config_version_id == result["deployment_id"]


@pytest.mark.parametrize("method", ["install", "upgrade"])
def test_stopped_collection_is_not_reenabled_by_edit_or_upgrade(policy_case, method):
    from monitor_web.collecting.deploy.nodeman_v3.installer import NodeManV3Installer

    case = policy_case
    case.collection.last_operation = "STOP"
    case.collection.save()
    installer = NodeManV3Installer(case.collection, reconciler=case.reconciler)
    with pytest.raises(NodeManV3CapabilityBlocked, match="stopped collection"):
        if method == "install":
            installer.install({}, "EDIT")
        else:
            installer.upgrade({})
    case.collection.refresh_from_db()
    assert case.collection.last_operation == "STOP"
    assert case.client.calls == []
