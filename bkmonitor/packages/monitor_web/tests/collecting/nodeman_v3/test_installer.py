import importlib
from types import SimpleNamespace

import pytest
from django.test import override_settings

from bkmonitor.nodeman_integration.v3.client import NodeManV3UnknownResultError
from bkmonitor.nodeman_integration.v3.exceptions import NodeManV3ResultState
from monitor_web.collecting.deploy.nodeman_v3.installer import NodeManV3Installer
from monitor_web.collecting.deploy.nodeman_v3.orchestrator import NodeManV3Orchestrator
from monitor_web.collecting.deploy.nodeman_v3.validation import NodeManV3CapabilityBlocked
from monitor_web.models.node_man import (
    MonitorNodeManOperation,
    MonitorNodeManWorkflow,
    NodeManIntegrationBinding,
    NodeManOperationStatus,
    NodeManOperationType,
    NodeManResourceType,
    NodeManWorkflowDispatchStatus,
)


@pytest.mark.parametrize("method", ["stop", "start", "uninstall"])
def test_stop_start_and_delete_await_reverse_protocol(method):
    with pytest.raises(NodeManV3CapabilityBlocked, match="reverse protocol") as error:
        getattr(NodeManV3Orchestrator(), method)()
    assert error.value.result_state == NodeManV3ResultState.UNSUPPORTED


@pytest.mark.django_db
def test_installer_create_persists_desired_version_then_reconciles(monkeypatch):
    calls = []
    packaged_release = SimpleNamespace(is_packaged=True, config_version=1)
    orchestrator = SimpleNamespace(
        uninstall=lambda **kwargs: calls.append(("uninstall", kwargs)),
        stop=lambda **kwargs: calls.append(("stop", kwargs)),
        start=lambda **kwargs: calls.append(("start", kwargs)),
        run=lambda **kwargs: calls.append(("run", kwargs)),
        retry=lambda **kwargs: calls.append(("retry", kwargs)),
        revoke=lambda **kwargs: calls.append(("revoke", kwargs)),
        status=lambda **kwargs: calls.append(("status", kwargs)) or {"status": "running"},
        instance_status=lambda **kwargs: calls.append(("instance_status", kwargs)) or {"status": "running"},
    )
    collect_config = SimpleNamespace(
        pk=None,
        name="mysql",
        last_operation="CREATE",
        deployment_config_id=None,
        deployment_config=None,
        plugin=SimpleNamespace(plugin_type="Exporter", packaged_release_version=packaged_release),
    )
    reconciler = SimpleNamespace()
    installer = NodeManV3Installer(collect_config, orchestrator=orchestrator, reconciler=reconciler)
    new_version = SimpleNamespace(pk=8, target_nodes=[{"bk_inst_id": 3}])
    monkeypatch.setattr(installer, "_create_deployment_version", lambda **kwargs: new_version)
    monkeypatch.setattr(installer, "_node_diff", lambda *args: {"added": [{"bk_inst_id": 3}]})

    def activate(deployment, *, last_operation):
        calls.append(("activate", deployment, last_operation))
        collect_config.pk = 7

    monkeypatch.setattr(installer, "_activate_version", activate)
    monkeypatch.setattr(installer, "_reconcile", lambda *, trigger: calls.append(("reconcile", trigger)))

    result = installer.install(
        {
            "target_node_type": "TOPO",
            "target_nodes": [{"bk_inst_id": 3}],
            "params": {"collector": {"period": 60}},
        },
        "CREATE",
    )

    assert result == {
        "diff_node": {"added": [{"bk_inst_id": 3}]},
        "can_rollback": False,
        "id": 7,
        "deployment_id": 8,
    }
    assert calls == [("activate", new_version, "CREATE"), ("reconcile", "install:create")]


@pytest.mark.django_db
def test_installer_edit_persists_desired_version_then_updates_targets(monkeypatch):
    calls = []
    packaged_release = SimpleNamespace(is_packaged=True, config_version=1)
    current_version = SimpleNamespace(pk=6, target_nodes=[{"bk_inst_id": 2}], plugin_version=packaged_release)
    collect_config = SimpleNamespace(
        pk=7,
        name="mysql",
        last_operation="CREATE",
        deployment_config_id=6,
        deployment_config=current_version,
        plugin=SimpleNamespace(plugin_type="Exporter", packaged_release_version=packaged_release),
    )
    installer = NodeManV3Installer(collect_config, reconciler=SimpleNamespace())
    new_version = SimpleNamespace(pk=8, target_nodes=[{"bk_inst_id": 3}])
    monkeypatch.setattr(installer, "_create_deployment_version", lambda **kwargs: new_version)
    monkeypatch.setattr(installer, "_node_diff", lambda *args: {"updated": [{"bk_inst_id": 3}]})
    monkeypatch.setattr(
        installer,
        "_activate_version",
        lambda deployment, *, last_operation: calls.append(("activate", deployment, last_operation)),
    )
    monkeypatch.setattr(installer, "_reconcile", lambda *, trigger: calls.append(("reconcile", trigger)))

    result = installer.install(
        {
            "target_node_type": "TOPO",
            "target_nodes": [{"bk_inst_id": 3}],
            "params": {"collector": {"period": 60}},
        },
        "EDIT",
    )

    assert result == {
        "diff_node": {"updated": [{"bk_inst_id": 3}]},
        "can_rollback": False,
        "id": 7,
        "deployment_id": 8,
    }
    assert calls == [("activate", new_version, "EDIT"), ("reconcile", "install:edit")]


@pytest.mark.django_db
def test_installer_upgrade_persists_desired_version_then_updates_targets(monkeypatch):
    calls = []
    packaged_release = SimpleNamespace(is_packaged=True, config_version=1)
    current_version = SimpleNamespace(
        pk=6,
        plugin_version=SimpleNamespace(config_version=0),
        target_node_type="TOPO",
        target_nodes=[{"bk_inst_id": 2}],
        params={"collector": {"period": 60, "timeout": 30}},
        remote_collecting_host=None,
    )
    collect_config = SimpleNamespace(
        pk=7,
        name="mysql",
        last_operation="EDIT",
        deployment_config=current_version,
        plugin=SimpleNamespace(plugin_type="Exporter", packaged_release_version=packaged_release),
    )
    installer = NodeManV3Installer(collect_config, reconciler=SimpleNamespace())
    new_version = SimpleNamespace(pk=8)
    created = []
    monkeypatch.setattr(installer, "_create_deployment_version", lambda **kwargs: created.append(kwargs) or new_version)
    monkeypatch.setattr(
        installer,
        "_activate_version",
        lambda deployment, *, last_operation: calls.append(("activate", deployment, last_operation)),
    )
    monkeypatch.setattr(installer, "_reconcile", lambda *, trigger: calls.append(("reconcile", trigger)))

    params = {"collector": {"period": 10, "timeout": 5}, "plugin": {}}
    assert installer.upgrade(params) == {"id": 7, "deployment_id": 8}
    assert created == [
        {
            "plugin_version": packaged_release,
            "target_node_type": "TOPO",
            "target_nodes": [{"bk_inst_id": 2}],
            "params": {"collector": {"period": 60, "timeout": 30}, "plugin": {}},
            "remote_collecting_host": None,
            "parent_id": 6,
        }
    ]
    assert calls == [("activate", new_version, "UPGRADE"), ("reconcile", "upgrade")]


def test_installer_marks_rollback_as_unsupported_before_mutating_desired_version():
    collect_config = SimpleNamespace(
        pk=7,
        name="mysql",
        last_operation="CREATE",
        plugin=SimpleNamespace(plugin_type="Exporter"),
    )
    installer = NodeManV3Installer(collect_config, reconciler=SimpleNamespace())

    with pytest.raises(NodeManV3CapabilityBlocked, match="rollback and replacement") as error:
        installer.rollback()

    assert error.value.result_state == NodeManV3ResultState.UNSUPPORTED


class FakeWorkflowClient:
    def __init__(self, *, operations=None, retry_error=None, terminate_error_at=None):
        self.operations = operations or []
        self.retry_error = retry_error
        self.terminate_error_at = terminate_error_at
        self.calls = []

    def list_operations(self, payload, *, context):
        self.calls.append(("list_operations", payload, context))
        return {"total": len(self.operations), "operations": self.operations}

    def retry_operation(self, payload, *, context):
        self.calls.append(("retry_operation", payload, context))
        if self.retry_error:
            raise self.retry_error

    def terminate_operation(self, payload, *, context):
        self.calls.append(("terminate_operation", payload, context))
        terminate_call_count = sum(call[0] == "terminate_operation" for call in self.calls)
        if self.terminate_error_at == terminate_call_count:
            raise ValueError("invalid second terminate request")

    def get_operation_instance_log(self, payload, *, context):
        self.calls.append(("get_operation_instance_log", payload, context))
        return {
            "oper_inst_logs": {
                "install": {
                    "display_name_zh": "安装插件",
                    "message": {"logs": [{"text_zh": "安装完成"}]},
                }
            },
            "extra_execution_logs": {"logs": [{"text_en": "retried"}]},
        }


def _workflow_operation(operation_id, instance_id, state):
    return {
        "operation_id": operation_id,
        "instance_ids": [instance_id],
        "plugin_deployment_info": {
            "bk_host_id": 41,
            "bk_networkarea_id": 0,
            "bk_host_innerip_list": ["host-a.invalid"],
            "plugin_name": "mysql_exporter",
            "plugin_version": "1.2.3",
        },
        "latest_oper_inst_brief_data": {
            "life_cycle": {"state": state},
            "latest_action_inst_brief_data": {"name": "install_plugin"},
        },
    }


@pytest.fixture
def direct_workflow_case(db):
    config = SimpleNamespace(
        pk=7,
        bk_tenant_id="tenant-a",
        bk_biz_id=2,
        deployment_config_id=8,
        last_operation="CREATE",
    )
    binding = NodeManIntegrationBinding.objects.create(
        resource_type=NodeManResourceType.COLLECT_CONFIG,
        resource_key="7",
        owner_bk_tenant_id="tenant-a",
        execution_bk_tenant_id="tenant-a",
        bk_biz_id=2,
    )
    operation = MonitorNodeManOperation.objects.create(
        binding=binding,
        config_meta_id=7,
        deployment_config_version_id=8,
        operation_type=NodeManOperationType.INSTALL,
        generation=binding.generation,
        status=NodeManOperationStatus.RUNNING,
    )
    workflow = MonitorNodeManWorkflow.objects.create(
        monitor_operation=operation,
        workflow_id="workflow-1",
        batch_index=0,
        dispatch_status=NodeManWorkflowDispatchStatus.SUBMITTED,
    )
    return SimpleNamespace(config=config, binding=binding, operation=operation, workflow=workflow)


@pytest.mark.django_db(transaction=True)
def test_direct_workflow_status_retry_terminate_and_log_are_wired(direct_workflow_case):
    operations = [
        _workflow_operation("operation-failed", "instance-failed", "failed"),
        _workflow_operation("operation-running", "instance-running", "running"),
    ]
    client = FakeWorkflowClient(operations=operations)
    scheduled = []
    orchestrator = NodeManV3Orchestrator(workflow_client=client, poll_scheduler=scheduled.append)

    status = orchestrator.status(collect_config=direct_workflow_case.config)
    assert [item["status"] for item in status[0]["child"]] == ["FAILED", "RUNNING"]
    assert status[0]["child"][0]["instance_id"] == "instance-failed"

    retry = orchestrator.retry(collect_config=direct_workflow_case.config)
    assert retry["operation_id"]
    assert client.calls[-1][0] == "retry_operation"
    assert client.calls[-1][1] == {
        "workflow_id": "workflow-1",
        "retry_mod": "PARTIAL",
        "operation_ids": ["operation-failed"],
    }

    revoke = orchestrator.revoke(
        collect_config=direct_workflow_case.config,
        instance_ids=["instance-running"],
    )
    assert revoke["operation_id"]
    assert client.calls[-1][0] == "terminate_operation"
    assert client.calls[-1][1] == {
        "workflow_id": "workflow-1",
        "operation_ids": ["operation-running"],
    }
    assert len(scheduled) == 2

    detail = orchestrator.instance_status(
        collect_config=direct_workflow_case.config,
        instance_id="instance-failed",
    )
    assert detail == {"log_detail": "====================安装插件====================\n安装完成\nretried"}


@pytest.mark.django_db
def test_deploy_policy_trigger_control_waits_for_aggregate_workflow_contract(direct_workflow_case):
    direct_workflow_case.workflow.workflow_id = None
    direct_workflow_case.workflow.trigger_id = "trigger-1"
    direct_workflow_case.workflow.save(update_fields=("workflow_id", "trigger_id", "updated_at"))
    orchestrator = NodeManV3Orchestrator(workflow_client=FakeWorkflowClient())

    with pytest.raises(NodeManV3CapabilityBlocked, match="aggregate DeployPolicy Workflow"):
        orchestrator.status(collect_config=direct_workflow_case.config)


@pytest.mark.django_db(transaction=True)
def test_unknown_retry_result_is_persisted_and_not_reported_as_failed(direct_workflow_case):
    error = NodeManV3UnknownResultError("timeout")
    client = FakeWorkflowClient(
        operations=[_workflow_operation("operation-failed", "instance-failed", "failed")],
        retry_error=error,
    )
    orchestrator = NodeManV3Orchestrator(workflow_client=client, poll_scheduler=lambda operation_id: None)

    with pytest.raises(NodeManV3UnknownResultError, match="timeout"):
        orchestrator.retry(collect_config=direct_workflow_case.config)

    operation = MonitorNodeManOperation.objects.order_by("-created_at").first()
    assert operation.status == NodeManOperationStatus.UNKNOWN
    assert operation.result_state == NodeManV3ResultState.WRITE_RESULT_UNKNOWN


@pytest.mark.django_db(transaction=True)
def test_partial_control_submission_keeps_polling_the_submitted_workflow(direct_workflow_case):
    MonitorNodeManWorkflow.objects.create(
        monitor_operation=direct_workflow_case.operation,
        workflow_id="workflow-2",
        batch_index=1,
        dispatch_status=NodeManWorkflowDispatchStatus.SUBMITTED,
    )
    client = FakeWorkflowClient(
        operations=[_workflow_operation("operation-running", "instance-running", "running")],
        terminate_error_at=2,
    )
    scheduled = []
    orchestrator = NodeManV3Orchestrator(workflow_client=client, poll_scheduler=scheduled.append)

    with pytest.raises(ValueError, match="invalid second terminate request"):
        orchestrator.revoke(collect_config=direct_workflow_case.config)

    operation = MonitorNodeManOperation.objects.order_by("-created_at").first()
    workflows = list(operation.workflows.order_by("batch_index"))
    assert operation.status == NodeManOperationStatus.RUNNING
    assert [workflow.dispatch_status for workflow in workflows] == [
        NodeManWorkflowDispatchStatus.SUBMITTED,
        NodeManWorkflowDispatchStatus.DEFINITE_FAILED,
    ]
    assert scheduled == [str(operation.pk)]


def test_installer_keeps_unclosed_lifecycle_methods_blocked_by_orchestrator():
    calls = []
    orchestrator = SimpleNamespace(
        uninstall=lambda **kwargs: calls.append(("uninstall", kwargs)),
        stop=lambda **kwargs: calls.append(("stop", kwargs)),
        start=lambda **kwargs: calls.append(("start", kwargs)),
        run=lambda **kwargs: calls.append(("run", kwargs)),
        retry=lambda **kwargs: calls.append(("retry", kwargs)),
        revoke=lambda **kwargs: calls.append(("revoke", kwargs)),
        status=lambda **kwargs: calls.append(("status", kwargs)) or {"status": "running"},
        instance_status=lambda **kwargs: calls.append(("instance_status", kwargs)) or {"status": "running"},
    )
    collect_config = SimpleNamespace(plugin=SimpleNamespace(plugin_type="Exporter"))
    installer = NodeManV3Installer(
        collect_config,
        orchestrator=orchestrator,
        reconciler=SimpleNamespace(),
    )

    installer.uninstall()
    installer.stop()
    installer.start()
    installer.retry(["instance-1"])
    installer.revoke([1])
    assert installer.status(diff=False) == {"status": "running"}
    assert installer.instance_status("instance-1") == {"status": "running"}
    assert [name for name, _ in calls] == [
        "uninstall",
        "stop",
        "start",
        "retry",
        "revoke",
        "status",
        "instance_status",
    ]


def test_real_v3_route_returns_real_v3_installer():
    with override_settings(NODEMAN_INTEGRATION_MODE="v3_fresh", BKNODEMAN_API_BASE_URL="https://nodeman.invalid"):
        mode_module = importlib.import_module("bkmonitor.nodeman_integration.mode")
        importlib.reload(mode_module)
        deploy_module = importlib.import_module("monitor_web.collecting.deploy")
        importlib.reload(deploy_module)

        collect_config = SimpleNamespace(plugin=SimpleNamespace(plugin_type="Exporter"))
        installer = deploy_module.get_collect_installer(collect_config)

    current_installer_class = importlib.import_module(
        "monitor_web.collecting.deploy.nodeman_v3.installer"
    ).NodeManV3Installer
    assert installer.__class__ is current_installer_class

    with override_settings(NODEMAN_INTEGRATION_MODE="v2"):
        importlib.reload(mode_module)
        importlib.reload(deploy_module)


def test_installer_explicit_run_submits_whole_policy(monkeypatch):
    config = SimpleNamespace(plugin=SimpleNamespace(plugin_type="Script"))
    installer = NodeManV3Installer(config, reconciler=SimpleNamespace())
    calls = []
    monkeypatch.setattr(installer, "_reconcile", lambda **kwargs: calls.append(kwargs))
    installer.run("install")
    assert calls == [{"trigger": "run", "force": True}]


@pytest.mark.parametrize("action, scope", [("restart", None), ("stop", None), ("install", {"nodes": [1]})])
def test_run_never_discards_scoped_or_action_specific_intent(action, scope):
    config = SimpleNamespace(plugin=SimpleNamespace(plugin_type="Script"))
    installer = NodeManV3Installer(config, reconciler=SimpleNamespace())
    with pytest.raises(NodeManV3CapabilityBlocked, match="action override"):
        installer.run(action, scope)
