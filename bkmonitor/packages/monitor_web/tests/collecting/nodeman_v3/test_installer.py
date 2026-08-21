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

    def disable_config_instance(self, config_instance_id):
        self.calls.append(("disable_config_instance", config_instance_id))

    def stop_plugin_instance(self, plugin_instance_id):
        self.calls.append(("stop_plugin_instance", plugin_instance_id))

    def delete_config_instance(self, config_instance_id):
        self.calls.append(("delete_config_instance", config_instance_id))

    def uninstall_plugin_instance(self, plugin_instance_id):
        self.calls.append(("uninstall_plugin_instance", plugin_instance_id))


def _target(identity, plugin_instance, config_instance):
    return SimpleNamespace(
        identity_key=identity,
        node_man_plugin_instance_id=plugin_instance,
        bkmonitorbeat_config_instance_id=config_instance,
    )


def test_mysql0_stop_and_delete_never_operate_mysql1_resources():
    gateway = FakeGateway()
    orchestrator = NodeManV3Orchestrator(gateway=gateway)
    mysql0 = _target("mysql0", "plugin-instance-a", "config-instance-a")
    mysql1 = _target("mysql1", "plugin-instance-b", "config-instance-b")

    orchestrator.stop_targets([mysql0])
    orchestrator.uninstall_targets([mysql0])

    assert gateway.calls == [
        ("disable_config_instance", "config-instance-a"),
        ("stop_plugin_instance", "plugin-instance-a"),
        ("delete_config_instance", "config-instance-a"),
        ("uninstall_plugin_instance", "plugin-instance-a"),
    ]
    assert all("instance-b" not in value for _, value in gateway.calls)
    assert mysql1.node_man_plugin_instance_id == "plugin-instance-b"
    assert mysql1.bkmonitorbeat_config_instance_id == "config-instance-b"


def test_missing_external_instance_identity_is_an_explicit_e2_e3_blocker():
    gateway = FakeGateway()
    orchestrator = NodeManV3Orchestrator(gateway=gateway)
    target = _target("mysql0", "", "")

    with pytest.raises(NodeManV3CapabilityBlocked, match="E2/E3"):
        orchestrator.stop_targets([target])

    assert gateway.calls == []


def test_installer_implements_base_interface_by_delegating_to_orchestrator():
    calls = []
    orchestrator = SimpleNamespace(
        install=lambda **kwargs: calls.append(("install", kwargs)) or {"status": "deploying"},
        upgrade=lambda **kwargs: calls.append(("upgrade", kwargs)) or {"status": "deploying"},
        uninstall=lambda **kwargs: calls.append(("uninstall", kwargs)),
        rollback=lambda **kwargs: calls.append(("rollback", kwargs)) or {"status": "deploying"},
        stop=lambda **kwargs: calls.append(("stop", kwargs)),
        start=lambda **kwargs: calls.append(("start", kwargs)),
        run=lambda **kwargs: calls.append(("run", kwargs)),
        retry=lambda **kwargs: calls.append(("retry", kwargs)),
        revoke=lambda **kwargs: calls.append(("revoke", kwargs)),
        status=lambda **kwargs: calls.append(("status", kwargs)) or {"status": "running"},
        instance_status=lambda **kwargs: calls.append(("instance_status", kwargs)) or {"status": "running"},
    )
    collect_config = SimpleNamespace(plugin=SimpleNamespace(plugin_type="Exporter"))
    installer = NodeManV3Installer(collect_config, orchestrator=orchestrator)

    assert installer.install({"config": 1}, "CREATE") == {"status": "deploying"}
    assert installer.upgrade({"version": "2.0"}) == {"status": "deploying"}
    installer.uninstall()
    assert installer.rollback(3) == {"status": "deploying"}
    installer.stop()
    installer.start()
    installer.run("restart", {"host_ids": [1]})
    installer.retry(["instance-1"])
    installer.revoke([1])
    assert installer.status(diff=False) == {"status": "running"}
    assert installer.instance_status("instance-1") == {"status": "running"}
    assert [name for name, _ in calls] == [
        "install",
        "upgrade",
        "uninstall",
        "rollback",
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
