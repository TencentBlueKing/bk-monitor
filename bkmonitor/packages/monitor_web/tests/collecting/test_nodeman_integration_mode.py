import importlib
import json
import os
import subprocess
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from django.conf import settings
from django.test import override_settings

from monitor_web.models.collecting import CollectConfigMeta
from monitor_web.plugin.constant import PluginType


MODE_MODULE = "bkmonitor.nodeman_integration.mode"
DEPLOY_MODULE = "monitor_web.collecting.deploy"
V3_PACKAGE = "monitor_web.collecting.deploy.nodeman_v3"
V3_INSTALLER_MODULE = f"{V3_PACKAGE}.installer"
V2_SNAPSHOT_PATH = Path(__file__).resolve().parents[4] / "tests/nodeman_v3/fixtures/v2_contract_snapshots.yaml"


class FakeV3Installer:
    def __init__(self, collect_config, *args, **kwargs):
        self.collect_config = collect_config
        self.args = args
        self.kwargs = kwargs


def _collect_config(plugin_type="Script", node_man_backend="v2"):
    return SimpleNamespace(
        pk=42,
        plugin=SimpleNamespace(plugin_type=plugin_type),
        node_man_backend=node_man_backend,
    )


def _clear_v3_modules():
    for module_name in list(sys.modules):
        if module_name == V3_PACKAGE or module_name.startswith(f"{V3_PACKAGE}."):
            sys.modules.pop(module_name)


def _install_fake_v3_module(monkeypatch):
    package = types.ModuleType(V3_PACKAGE)
    package.__path__ = []
    installer_module = types.ModuleType(V3_INSTALLER_MODULE)
    installer_module.NodeManV3Installer = FakeV3Installer
    monkeypatch.setitem(sys.modules, V3_PACKAGE, package)
    monkeypatch.setitem(sys.modules, V3_INSTALLER_MODULE, installer_module)


def _reload_route(mode):
    with override_settings(NODEMAN_INTEGRATION_MODE=mode):
        mode_module = importlib.import_module(MODE_MODULE)
        importlib.reload(mode_module)
        deploy_module = importlib.import_module(DEPLOY_MODULE)
        importlib.reload(deploy_module)
    return mode_module, deploy_module


@pytest.fixture(autouse=True)
def restore_v2_route():
    yield
    _clear_v3_modules()
    if MODE_MODULE in sys.modules:
        _reload_route("v2")


def test_default_mode_returns_current_v2_installer():
    assert settings.NODEMAN_INTEGRATION_MODE == "v2"

    _clear_v3_modules()
    _, deploy_module = _reload_route("v2")
    installer = deploy_module.get_collect_installer(_collect_config())

    assert installer.__class__ is deploy_module.NodeManInstaller
    assert V3_INSTALLER_MODULE not in sys.modules


def test_explicit_v2_mode_does_not_import_v3_modules():
    _clear_v3_modules()
    _, deploy_module = _reload_route("v2")

    assert deploy_module.get_collect_installer(_collect_config()).__class__.__name__ == "NodeManInstaller"
    assert not any(name == V3_PACKAGE or name.startswith(f"{V3_PACKAGE}.") for name in sys.modules)


def test_mode_is_cached_when_mode_module_is_loaded():
    mode_module, _ = _reload_route("v2")

    with override_settings(NODEMAN_INTEGRATION_MODE="v3_fresh"):
        assert mode_module.get_nodeman_integration_mode() == "v2"


def test_v2_hot_path_does_not_recheck_mode(monkeypatch):
    mode_module, deploy_module = _reload_route("v2")
    monkeypatch.setattr(
        mode_module,
        "get_nodeman_integration_mode",
        lambda: (_ for _ in ()).throw(AssertionError("mode must not be read on the request path")),
    )

    for _ in range(10):
        assert deploy_module.get_collect_installer(_collect_config()).__class__ is deploy_module.NodeManInstaller


def test_v2_clean_process_keeps_resource_and_task_inventory_without_v3_imports():
    environment = os.environ.copy()
    environment.update(
        {
            "DJANGO_SETTINGS_MODULE": "settings",
            "DJANGO_CONF_MODULE": "config.web.development.community",
            "BKAPP_DEPLOY_PLATFORM": "community",
            "USE_DYNAMIC_SETTINGS": "0",
            "BK_MONITOR_APP_CODE": "bk_monitorv3",
            "BK_MONITOR_APP_SECRET": "secret",
            "BKAPP_NODEMAN_INTEGRATION_MODE": "v2",
        }
    )
    script = """
import json
import sys
import django

django.setup()
from celery import current_app
from core.drf_resource import api
import monitor_web.collecting.deploy

payload = {
    "resources": api.node_man.list_method(),
    "tasks": sorted(current_app.tasks.keys()),
    "v3_modules": sorted(
        name
        for name in sys.modules
        if name.startswith("bkmonitor.nodeman_integration.v3")
        or name.startswith("monitor_web.collecting.deploy.nodeman_v3")
        or name.startswith("monitor_web.nodeman_integration.v3")
    ),
}
print("NODEMAN_V2_CONTRACT=" + json.dumps(payload))
"""

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=settings.BASE_DIR,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload_line = next(line for line in result.stdout.splitlines() if line.startswith("NODEMAN_V2_CONTRACT="))
    actual = json.loads(payload_line.removeprefix("NODEMAN_V2_CONTRACT="))
    snapshot = yaml.safe_load(V2_SNAPSHOT_PATH.read_text(encoding="utf-8"))["static_contract"]
    assert actual == {
        "resources": snapshot["node_man_resource_names"],
        "tasks": snapshot["celery_task_names"],
        "v3_modules": [],
    }


@pytest.mark.parametrize("mode", ["v2", "v3_fresh", "v3_gray"])
def test_k8s_always_uses_current_k8s_installer(mode, monkeypatch):
    if mode in {"v3_fresh", "v3_gray"}:
        _install_fake_v3_module(monkeypatch)
    _, deploy_module = _reload_route(mode)

    installer = deploy_module.get_collect_installer(_collect_config(PluginType.K8S))

    assert installer.__class__ is deploy_module.K8sInstaller


def test_v3_fresh_route_is_bound_at_module_load(monkeypatch):
    _install_fake_v3_module(monkeypatch)
    mode_module, deploy_module = _reload_route("v3_fresh")

    with override_settings(NODEMAN_INTEGRATION_MODE="v2"):
        installer = deploy_module.get_collect_installer(_collect_config(), "arg", key="value")

    assert mode_module.get_nodeman_integration_mode() == "v3_fresh"
    assert installer.__class__ is FakeV3Installer
    assert installer.args == ("arg",)
    assert installer.kwargs == {"key": "value"}


@pytest.mark.parametrize(
    ("mode", "gray_biz_ids", "bk_biz_id", "expected_backend"),
    [
        ("v2", [2], 2, "v2"),
        ("v3_fresh", [], 2, "v3"),
        ("v3_gray", [2], 2, "v3"),
        ("v3_gray", [2], 3, "v2"),
        ("v3_gray", ["2"], 2, "v3"),
    ],
)
def test_new_collect_config_backend_is_selected_once(mode, gray_biz_ids, bk_biz_id, expected_backend):
    with override_settings(NODEMAN_INTEGRATION_MODE=mode, NODEMAN_V3_GRAY_BIZ_LIST=gray_biz_ids):
        mode_module = importlib.import_module(MODE_MODULE)
        importlib.reload(mode_module)

        assert mode_module.get_new_collect_config_backend(bk_biz_id) == expected_backend


def test_existing_rows_default_to_v2_backend():
    field = CollectConfigMeta._meta.get_field("node_man_backend")

    assert field.get_default() == "v2"
    assert list(field.choices) == [("v2", "NodeMan V2"), ("v3", "NodeMan V3")]


def test_v3_gray_routes_by_persisted_collect_config_backend(monkeypatch):
    _install_fake_v3_module(monkeypatch)
    _, deploy_module = _reload_route("v3_gray")

    assert (
        deploy_module.get_collect_installer(_collect_config(node_man_backend="v2")).__class__
        is deploy_module.node_man_v2.NodeManInstaller
    )
    assert deploy_module.get_collect_installer(_collect_config(node_man_backend="v3")).__class__ is FakeV3Installer


def test_v3_gray_does_not_reroute_existing_config_when_gray_list_changes(monkeypatch):
    _install_fake_v3_module(monkeypatch)
    _, deploy_module = _reload_route("v3_gray")
    collect_config = _collect_config(node_man_backend="v2")

    with override_settings(NODEMAN_V3_GRAY_BIZ_LIST=[2]):
        installer = deploy_module.get_collect_installer(collect_config)

    assert installer.__class__ is deploy_module.node_man_v2.NodeManInstaller


def test_v3_gray_rejects_unknown_persisted_backend(monkeypatch):
    _install_fake_v3_module(monkeypatch)
    _, deploy_module = _reload_route("v3_gray")

    with pytest.raises(ValueError, match="unsupported NodeMan backend"):
        deploy_module.get_collect_installer(_collect_config(node_man_backend="unknown"))


def test_save_collect_config_persists_selected_backend_before_install(monkeypatch):
    from monitor_web.collecting.resources import backend as backend_resources

    captured = {}

    class FakeInstaller:
        def __init__(self, collect_config):
            captured["collect_config"] = collect_config

        def install(self, data, operation):
            return {"operation": operation}

    class FakeStrategyLoader:
        def __init__(self, **kwargs):
            pass

        def run(self):
            return None

    save_resource = backend_resources.SaveCollectConfigResource()
    monkeypatch.setattr(
        save_resource,
        "get_collector_plugin",
        lambda data: SimpleNamespace(plugin_id="test_plugin"),
    )
    monkeypatch.setattr(save_resource, "update_metric_cache", lambda plugin: None)
    monkeypatch.setattr(backend_resources, "get_request_tenant_id", lambda: "system")
    monkeypatch.setattr(backend_resources, "get_global_user", lambda: "admin")
    monkeypatch.setattr(backend_resources, "get_new_collect_config_backend", lambda bk_biz_id: "v3")
    monkeypatch.setattr(backend_resources, "get_collect_installer", FakeInstaller)
    monkeypatch.setattr(backend_resources, "DatalinkDefaultAlarmStrategyLoader", FakeStrategyLoader)

    result = save_resource.perform_request(
        {
            "bk_biz_id": 2,
            "name": "gray-config",
            "collect_type": "Script",
            "target_object_type": "HOST",
            "target_node_type": "INSTANCE",
            "label": "component",
            "metric_relabel_configs": [],
            "params": {"collector": {}},
        }
    )

    assert result == {"operation": "CREATE"}
    assert captured["collect_config"].node_man_backend == "v3"


def test_invalid_mode_fails_during_django_startup():
    environment = os.environ.copy()
    environment.update(
        {
            "DJANGO_SETTINGS_MODULE": "settings",
            "DJANGO_CONF_MODULE": "config.web.development.community",
            "BKAPP_DEPLOY_PLATFORM": "community",
            "USE_DYNAMIC_SETTINGS": "0",
            "BK_MONITOR_APP_CODE": "bk_monitorv3",
            "BK_MONITOR_APP_SECRET": "secret",
            "BKAPP_NODEMAN_INTEGRATION_MODE": "hybrid_migration",
        }
    )

    result = subprocess.run(
        [sys.executable, "-c", "import django; django.setup()"],
        cwd=settings.BASE_DIR,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "BKAPP_NODEMAN_INTEGRATION_MODE" in result.stderr
    assert "hybrid_migration" in result.stderr
