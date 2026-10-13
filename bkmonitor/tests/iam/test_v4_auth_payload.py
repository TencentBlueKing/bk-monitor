"""Monitor V4 native Provider payloads, with the real product codec and no network."""

from unittest.mock import MagicMock

import pytest

from bkmonitor.iam.backends.config import build_provider
from iam_engine.core.requests import AuthRequest, BatchAuthRequest, ResourceInstance, Subject
from iam_engine.core.types import AuthStatus


def _build_provider():
    provider = build_provider(
        "v4",
    )
    client = MagicMock()
    provider._get_client = MagicMock(return_value=client)
    provider.resolver = None
    return provider, client


SUBJECT = Subject(id="alice", tenant_id="tenant-a")
SPACE = ResourceInstance(type="space", id="2")
DASHBOARD = ResourceInstance(type="grafana_dashboard", id="folder:3|182", ancestor_chain=(SPACE,))


@pytest.mark.parametrize(
    "resource,expected",
    [
        (SPACE, {"type": "space", "id": "space|2"}),
        (ResourceInstance(type="space", id="-42"), {"type": "space", "id": "space|-42"}),
        (
            DASHBOARD,
            {"type": "grafana_dashboard", "id": "folder:3|182", "attributes": {"_bk_iam_path_": "/space,space|2/"}},
        ),
    ],
)
def test_single_payload_uses_product_codec(resource, expected):
    provider, client = _build_provider()
    client.direct_auth.return_value = True
    action = "view_business" if resource.type == "space" else "view_single_dashboard"
    result = provider.is_allowed(AuthRequest(SUBJECT, action, (resource,)))
    assert result.allowed
    client.direct_auth.assert_called_once_with(
        subject={"type": "user", "id": "alice"}, action_id=action, resource=expected
    )
    provider._get_client.assert_called_once_with("tenant-a")


@pytest.mark.parametrize(
    "raw,status",
    [(True, AuthStatus.ALLOW), (False, AuthStatus.DENY), (None, AuthStatus.ERROR), ("true", AuthStatus.ERROR)],
)
def test_single_retains_three_states(raw, status):
    provider, client = _build_provider()
    client.direct_auth.return_value = raw
    assert provider.is_allowed(AuthRequest(SUBJECT, "view_business", (SPACE,))).status is status


def test_transport_error_is_not_an_explicit_deny():
    provider, client = _build_provider()
    client.direct_auth.side_effect = TimeoutError("offline")
    assert provider.is_allowed(AuthRequest(SUBJECT, "view_business", (SPACE,))).status is AuthStatus.ERROR


def test_batch_ancestor_payload_and_missing_result():
    provider, client = _build_provider()
    other = ResourceInstance(type="grafana_dashboard", id="3|missing", ancestor_chain=(SPACE,))
    client.direct_auth_by_resources.return_value = {DASHBOARD.id: True}
    result = provider.batch_is_allowed(BatchAuthRequest(SUBJECT, ("view_single_dashboard",), ((DASHBOARD,), (other,))))
    assert result.items[0].result.allowed
    assert result.items[1].result.error_type == "IncompleteBatchResult"
    sent = client.direct_auth_by_resources.call_args.kwargs["resources"]
    assert all(r["attributes"]["_bk_iam_path_"] == "/space,space|2/" for r in sent)


def test_resource_free_batch_uses_direct_auth():
    provider, client = _build_provider()
    provider.resolver = MagicMock()
    provider.resolver.resolve.side_effect = AssertionError("global actions must not resolve unrelated resources")
    client.direct_auth.return_value = False
    result = provider.batch_is_allowed(BatchAuthRequest(SUBJECT, ("manage_global_setting",), ((SPACE,),)))
    assert result.items[0].result.status is AuthStatus.DENY
    client.direct_auth_by_resources.assert_not_called()


def test_resource_free_single_uses_direct_auth_without_enrichment():
    provider, client = _build_provider()
    provider.resolver = MagicMock()
    provider.resolver.resolve.side_effect = AssertionError("global actions must not resolve unrelated resources")
    client.direct_auth.return_value = True
    result = provider.is_allowed(AuthRequest(SUBJECT, "manage_global_setting", (SPACE,)))
    assert result.allowed
    client.direct_auth.assert_called_once_with(
        subject={"type": "user", "id": "alice"}, action_id="manage_global_setting", resource=None
    )


def test_application_tuple_resolves_product_names():
    provider, client = _build_provider()

    class Resolver:
        def resolve(self, resource, *, tenant_id):
            assert tenant_id == "system"
            return ResourceInstance(type=resource.type, id=resource.id, name="业务 2")

    provider.resolver = Resolver()
    client.generate_perm_apply_url.return_value = "https://iam.example.test/apply"
    data, url = provider.get_apply_data(["view_business"], [SPACE])
    assert data["actions"][0]["related_resource_types"][0]["instances"][0][0] == {
        "type": "space",
        "id": "space|2",
        "name": "业务 2",
    }
    assert url == "https://iam.example.test/apply"
    assert not hasattr(provider, "callback_service")
