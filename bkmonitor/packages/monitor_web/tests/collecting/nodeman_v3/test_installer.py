import importlib
from types import SimpleNamespace

import pytest
from django.test import override_settings

from monitor_web.collecting.deploy.nodeman_v3.installer import NodeManV3Installer
from monitor_web.collecting.deploy.nodeman_v3.orchestrator import NodeManV3Orchestrator
from monitor_web.collecting.deploy.nodeman_v3.validation import NodeManV3CapabilityBlocked


class FakeGateway:
    def __init__(self):
        self.calls = []

    def ensure_target(self, target, *, context):
        self.calls.append(("ensure_target", target.identity_key, context))
        return {"trigger_id": "trigger-1"}

    def update_target(self, target, *, context):
        self.calls.append(("update_target", target.identity_key, context))
        return {"trigger_id": "trigger-2"}


def _target(identity, plugin_instance, config_instance):
    return SimpleNamespace(
        identity_key=identity,
        node_man_plugin_instance_id=plugin_instance,
        bkmonitorbeat_config_instance_id=config_instance,
    )


def test_deploy_policy_target_submission_keeps_each_target_isolated():
    gateway = FakeGateway()
    orchestrator = NodeManV3Orchestrator(gateway=gateway)
    mysql0 = _target("mysql0", "plugin-instance-a", "config-instance-a")
    context = SimpleNamespace(monitor_operation_id="operation-1")

    assert orchestrator.ensure_targets([mysql0], context=context) == {"trigger_id": "trigger-1"}
    assert orchestrator.update_targets([mysql0], context=context) == {"trigger_id": "trigger-2"}

    assert gateway.calls == [
        ("ensure_target", "mysql0", context),
        ("update_target", "mysql0", context),
    ]


def test_stop_and_delete_remain_explicit_protocol_blockers():
    gateway = FakeGateway()
    orchestrator = NodeManV3Orchestrator(gateway=gateway)
    target = _target("mysql0", "", "")

    with pytest.raises(NodeManV3CapabilityBlocked, match="stop semantics"):
        orchestrator.stop_targets([target])
    with pytest.raises(NodeManV3CapabilityBlocked, match="delete semantics"):
        orchestrator.uninstall_targets([target])

    assert gateway.calls == []


def test_installer_install_persists_desired_version_then_reconciles(monkeypatch):
    calls = []
    packaged_release = SimpleNamespace(is_packaged=True)
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
        pk=7,
        name="mysql",
        need_upgrade=False,
        deployment_config_id=6,
        deployment_config=SimpleNamespace(pk=6),
        plugin=SimpleNamespace(plugin_type="Exporter", packaged_release_version=packaged_release),
    )
    reconciler = SimpleNamespace()
    installer = NodeManV3Installer(collect_config, orchestrator=orchestrator, reconciler=reconciler)
    new_version = SimpleNamespace(pk=8, target_nodes=[{"bk_inst_id": 3}])
    monkeypatch.setattr(installer, "_create_deployment_version", lambda **kwargs: new_version)
    monkeypatch.setattr(installer, "_node_diff", lambda *args: {"added": [{"bk_inst_id": 3}]})
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
        "diff_node": {"added": [{"bk_inst_id": 3}]},
        "can_rollback": True,
        "id": 7,
        "deployment_id": 8,
    }
    assert calls == [("activate", new_version, "EDIT"), ("reconcile", "install:edit")]


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
    installer.run("restart", {"host_ids": [1]})
    installer.retry(["instance-1"])
    installer.revoke([1])
    assert installer.status(diff=False) == {"status": "running"}
    assert installer.instance_status("instance-1") == {"status": "running"}
    assert [name for name, _ in calls] == [
        "uninstall",
        "stop",
        "start",
        "run",
        "retry",
        "revoke",
        "status",
        "instance_status",
    ]


def test_real_v3_route_returns_real_v3_installer():
    with override_settings(NODEMAN_INTEGRATION_MODE="v3_fresh"):
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
