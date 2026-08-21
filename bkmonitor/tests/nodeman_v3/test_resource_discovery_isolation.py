import importlib
from pathlib import Path

import yaml

from core.drf_resource import api


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLIENT_ROOT = PROJECT_ROOT / "bkmonitor/nodeman_integration/v3/client"
SNAPSHOT_PATH = Path(__file__).with_name("fixtures") / "v2_contract_snapshots.yaml"


def test_v3_client_is_not_resourcefinder_discoverable():
    forbidden_names = {"default.py", "resources.py", "resources"}

    assert not any(path.name in forbidden_names for path in CLIENT_ROOT.rglob("*"))


def test_importing_v3_client_does_not_change_v2_api_inventory():
    expected = yaml.safe_load(SNAPSHOT_PATH.read_text(encoding="utf-8"))["static_contract"]["node_man_resource_names"]
    before = api.node_man.list_method()

    for module_name in (
        "bkmonitor.nodeman_integration.v3.client",
        "bkmonitor.nodeman_integration.v3.client.package",
        "bkmonitor.nodeman_integration.v3.client.workflow",
        "bkmonitor.nodeman_integration.v3.client.process",
        "bkmonitor.nodeman_integration.v3.client.host",
    ):
        importlib.import_module(module_name)

    assert before == expected
    assert api.node_man.list_method() == expected


def test_v3_client_has_no_v2_api_dependency():
    source = "\n".join(path.read_text(encoding="utf-8") for path in CLIENT_ROOT.rglob("*.py"))

    assert "api.node_man" not in source
