from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from iam import Action, Request, Resource, Subject as SDKSubject
from iam_engine.core.config import AuthMode
from bkmonitor.iam.adapters.mcp import MonitorMCPClient
from bkmonitor.iam.adapters.shared_policy import SharedMigrationPolicy
from bkmonitor.iam.iam_engine.core.exceptions import ProviderUnavailable
from bkmonitor.iam.iam_engine.provider.router import ProviderRouter


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
            provider.is_allowed.side_effect = result
        else:
            provider.is_allowed.return_value = result
        providers.append(provider)
    mode = SimpleNamespace(get_mode=lambda resources=(): AuthMode.UNION)
    router = ProviderRouter(SharedMigrationPolicy(providers, mode_provider=mode), Mock())
    client = MonitorMCPClient(SimpleNamespace(router=router), "tenant-a")
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


def test_mcp_keeps_framework_bypass_hook():
    rule = Mock()
    rule.should_bypass.return_value = True
    policy = Mock()
    client = MonitorMCPClient(SimpleNamespace(router=ProviderRouter(policy, Mock(), [rule])), "tenant-a")
    query = Request("bk_monitorv3", SDKSubject("user", "alice"), Action("view_business"), [], None)
    assert client.is_allowed(query)
    policy.decide.assert_not_called()


def test_mcp_normalizes_legacy_v2_action_before_shared_dispatch():
    framework = Mock()
    framework.router.decide.return_value = SimpleNamespace(allowed=True, degraded=False)
    client = MonitorMCPClient(framework, "tenant-a")
    query = Request(
        "bk_monitorv3",
        SDKSubject("user", "alice"),
        Action("view_business_v2"),
        [Resource("bk_monitorv3", "space", "2", {})],
        None,
    )
    assert client.is_allowed(query)
    request = framework.router.decide.call_args.args[0]
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
    framework.get_apply_data.return_value = {"system_id": "v4-display"}
    framework.get_apply_url.return_value = "https://iam.example.test/apply/"
    client = MonitorMCPClient(framework, "tenant-a")
    assert client.get_apply_data(application) == {"system_id": "v4-display"}
    assert client.get_apply_url(application)[2] == "https://iam.example.test/apply/"
    request = framework.get_apply_url.call_args.args[0]
    assert request.action_ids == ("view_apm_application",)
    assert request.resources[0].id == "42"
    assert request.resources[0].ancestor_chain[0].id == "2"
    assert request.subject.tenant_id == "tenant-a"
