"""The V3 product boundary stays stable while IAM owns shared-engine assembly."""

import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from iam import Resource

from bkmonitor.iam import ActionEnum, Permission, ResourceEnum
from bkmonitor.iam.action import ActionMeta
from bkmonitor.iam.drf import IAMPermission
from bkmonitor.iam.permission import Permission as PublicPermission
from bkmonitor.iam.resource import Business
from iam_engine.core.config import AuthMode
from iam_engine.core.requests import ResourceInstance
from iam_engine.core.types import AuthResult
from iam_engine.exceptions import ProviderUnavailable


def test_original_modules_own_the_public_implementations():
    assert Permission is PublicPermission
    assert Permission.__module__ == "bkmonitor.iam.permission"
    assert ActionMeta.__module__ == "bkmonitor.iam.action"
    assert Business.__module__ == "bkmonitor.iam.resource"
    assert IAMPermission.__module__ == "bkmonitor.iam.drf"
    assert ResourceEnum.BUSINESS is Business


@pytest.mark.parametrize("action", [ActionEnum.VIEW_BUSINESS, "view_business", "view_business_v2"])
def test_original_request_envelope_keeps_v3_action_and_product_metadata(action):
    permission = Permission(username="alice", bk_tenant_id="tenant-a")
    resource = ResourceInstance(
        type="apm_application",
        id="42",
        attributes={"name": "Application", "bk_biz_id": "2"},
        ancestor_chain=(ResourceInstance(type="space", id="2"),),
    )
    query = permission.make_request(action, [resource])
    assert query.to_dict() == {
        "system": "bk_monitorv3",
        "subject": {"type": "user", "id": "alice"},
        "action": {"id": "view_business_v2"},
        "resources": [
            {
                "system": "bk_monitorv3",
                "type": "apm_application",
                "id": "42",
                "attribute": {"name": "Application", "bk_biz_id": "2", "_bk_iam_path_": "/space,2/"},
            }
        ],
        "environment": {},
    }


@pytest.mark.parametrize(
    "mode,v3,v4,allowed,error,called",
    [
        ("v3", True, False, True, False, {"v3"}),
        ("v4", True, False, False, False, {"v4"}),
        ("union", True, False, True, False, {"v3", "v4"}),
        ("union", False, True, True, False, {"v3", "v4"}),
        ("union", False, False, False, False, {"v3", "v4"}),
        ("union", True, None, True, False, {"v3", "v4"}),
        ("union", False, None, False, True, {"v3", "v4"}),
    ],
)
def test_product_client_routes_without_consumer_version_assembly(mode, v3, v4, allowed, error, called):
    permission = Permission(username="alice", bk_tenant_id="tenant-a")
    permission.mode_provider = SimpleNamespace(get_mode=lambda resources=(): AuthMode(mode))
    permission.skip_check = False
    providers = {}
    for name, value in (("v3", v3), ("v4", v4)):
        provider = Mock()
        provider.name = name
        provider.is_allowed.return_value = (
            AuthResult.error(name, "unavailable")
            if value is None
            else AuthResult.allow(name)
            if value
            else AuthResult.deny(name)
        )
        providers[name] = provider
    permission._providers = providers
    query = permission.make_request("view_business_v2", [Resource("bk_monitorv3", "space", "2", {})])
    if error:
        with pytest.raises(ProviderUnavailable):
            permission.iam_client.is_allowed(query)
    else:
        assert permission.iam_client.is_allowed(query) is allowed
    assert permission.iam_client is permission.iam_client
    assert {name for name, provider in providers.items() if provider.is_allowed.called} == called
    for name in called:
        request = providers[name].is_allowed.call_args.args[0]
        assert request.action_id == "view_business"
        assert request.subject.id == "alice"
        assert request.subject.tenant_id == "tenant-a"


def test_business_imports_do_not_follow_iam_internal_relocations():
    root = Path(__file__).resolve().parents[2]
    for directory in ("packages", "kernel_api", "ai_whale", "bkm_ipchooser", "calendars"):
        for path in (root / directory).rglob("*.py"):
            if "tests" in path.parts:
                continue
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.ImportFrom):
                    assert node.module not in {
                        "bkmonitor.iam.handlers.actions",
                        "bkmonitor.iam.handlers.permission",
                        "bkmonitor.iam.handlers.resources",
                        "bkmonitor.iam.handlers.drf",
                        "bkmonitor.iam.handlers.mcp",
                    }, path
    # Plural resources.py was the relocation that accidentally triggered ResourceFinder.
    product = root / "bkmonitor/iam"
    assert not list(product.rglob("resources.py"))
