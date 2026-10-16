from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from iam import Action, Request, Resource, Subject as SDKSubject
from iam_engine.core.config import AuthMode
from iam_engine.core.types import AuthResult
from bkmonitor.iam.handlers.mcp import MonitorMCPClient
from bkmonitor.iam.permission import Permission
from iam_engine.exceptions import ProviderUnavailable


@pytest.mark.parametrize(
    "v3,v4,allowed,error",
    [
        (True, TimeoutError(), True, False),
        (False, False, False, False),
        (False, TimeoutError(), False, True),
        (TimeoutError(), TimeoutError(), False, True),
        (TimeoutError(), True, True, False),
    ],
)
def test_mcp_does_not_treat_degraded_rejection_as_native_fallback(v3, v4, allowed, error):
    providers = []
    for name, result in (("v3", v3), ("v4", v4)):
        provider = Mock(name=name)
        provider.name = name
        if isinstance(result, Exception):
            provider.is_allowed.return_value = AuthResult.error(name, str(result) or type(result).__name__)
        else:
            provider.is_allowed.return_value = AuthResult.allow(name) if result is True else AuthResult.deny(name)
        providers.append(provider)
    mode = SimpleNamespace(get_mode=lambda resources=(): AuthMode.UNION)
    permission = Permission(username="alice", bk_tenant_id="tenant-a")
    permission._providers = {p.name: p for p in providers}
    permission.mode_provider = mode
    client = MonitorMCPClient(permission, "tenant-a")
    query = Request(
        "bk_monitorv3",
        SDKSubject("user", "alice"),
        Action("view_business"),
        [Resource("bk_monitorv3", "space", "2", {})],
        None,
    )
    if error:
        with pytest.raises(ProviderUnavailable):
            client.is_allowed(query)
    else:
        assert client.is_allowed(query) is allowed
    assert providers[0].is_allowed.call_args.args[0].subject.tenant_id == "tenant-a"


def test_mcp_keeps_product_skip_check():
    permission = Permission(username="alice", bk_tenant_id="tenant-a")
    permission.skip_check = True
    permission._providers = {"v3": Mock()}
    client = MonitorMCPClient(permission, "tenant-a")
    query = Request("bk_monitorv3", SDKSubject("user", "alice"), Action("view_business"), [], None)
    assert client.is_allowed(query)
    permission._providers["v3"].is_allowed.assert_not_called()


def test_mcp_normalizes_legacy_v2_action_before_shared_dispatch():
    framework = Mock()
    framework._decide_request.return_value = SimpleNamespace(allowed=True, degraded=False)
    client = MonitorMCPClient(framework, "tenant-a")
    query = Request(
        "bk_monitorv3",
        SDKSubject("user", "alice"),
        Action("view_business_v2"),
        [Resource("bk_monitorv3", "space", "2", {})],
        None,
    )
    assert client.is_allowed(query)
    request = framework._decide_request.call_args.args[0]
    assert request.action_id == "view_business"
    assert request.resource.system == "bk_monitorv3"
    assert request.subject.tenant_id == "tenant-a"


def test_mcp_application_display_and_url_share_business_action_and_parent_chain():
    from iam.apply.models import ActionWithResources, Application, RelatedResourceType, ResourceInstance, ResourceNode

    application = Application(
        "bk_monitorv3",
        [
            ActionWithResources(
                "view_apm_application_v2",
                [
                    RelatedResourceType(
                        "bk_monitorv3",
                        "apm_application",
                        [
                            ResourceInstance(
                                [ResourceNode("space", "2", "Biz"), ResourceNode("apm_application", "42", "App")]
                            )
                        ],
                    )
                ],
            )
        ],
    )
    framework = Mock()
    framework.mode_provider.get_mode.return_value = AuthMode.V4
    framework._application_data.return_value = ({"system_id": "v4-display"}, "https://iam.example.test/apply/")
    client = MonitorMCPClient(framework, "tenant-a")
    assert client.get_apply_data(application) == {"system_id": "v4-display"}
    assert client.get_apply_url(application)[2] == "https://iam.example.test/apply/"
    framework._application_data.assert_called_once()
    actions, resources = framework._application_data.call_args.args
    assert actions == ["view_apm_application"]
    assert resources[0].id == "42"
    assert resources[0].ancestor_chain[0].id == "2"
    assert framework._application_data.call_args.kwargs["mode"] is AuthMode.V4
