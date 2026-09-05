import importlib
from types import SimpleNamespace

import pytest
from django.test import override_settings

from bkmonitor.nodeman_integration.v3.exceptions import NodeManV3AdapterPending, NodeManV3ResultState
from monitor_web.collecting.deploy.nodeman_v3.installer import NodeManV3Installer
from monitor_web.collecting.deploy.nodeman_v3.orchestrator import NodeManV3Orchestrator
from monitor_web.collecting.deploy.nodeman_v3.validation import NodeManV3CapabilityBlocked


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


@pytest.mark.parametrize("method", ["retry", "revoke", "status", "instance_status"])
def test_protocol_backed_lifecycle_remains_adapter_pending(method):
    orchestrator = NodeManV3Orchestrator()

    with pytest.raises(NodeManV3AdapterPending, match="adapter is pending"):
        getattr(orchestrator, method)()


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
