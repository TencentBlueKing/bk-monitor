"""V4 any-resource queries use top-level action scopes, never imply a grant."""

from unittest.mock import Mock
import pytest
from bkmonitor.iam.backends.config import build_provider
from iam_engine.core.requests import AuthRequest, Subject
from iam_engine.core.types import AuthStatus


def make_provider():
    p = build_provider(
        "v4",
        username="user",
        tenant_id="tenant-b",
    )
    client = Mock()
    p._get_client = Mock(return_value=client)
    return p, client


@pytest.mark.parametrize("ids,expected", [([], False), (["2"], True), (["*"], True)])
def test_has_any_permission_requires_real_grants(ids, expected):
    provider, client = make_provider()
    client.list_authorized_resource.return_value = {"type": "space", "ids": ids}
    assert provider.has_any_permission(Subject("user", tenant_id="tenant-b"), "view_single_dashboard") is expected
    client.list_authorized_resource.assert_called_once_with(
        subject={"type": "user", "id": "user"}, action_id="view_single_dashboard", resource_type="space"
    )
    assert provider.tenant_id == "tenant-b"


def test_resource_free_action_uses_direct_authorization():
    provider, client = make_provider()
    client.direct_auth.return_value = False
    assert not provider.has_any_permission(Subject("user", tenant_id="tenant-b"), "manage_global_setting")
    client.list_authorized_resource.assert_not_called()


def test_provider_failure_is_not_collapsed_to_business_deny():
    provider, client = make_provider()
    client.direct_auth.side_effect = TimeoutError("offline")
    result = provider.is_allowed(AuthRequest(Subject("user", tenant_id="tenant-b"), "manage_global_setting"))
    assert result.status is AuthStatus.ERROR
    assert not result.allowed
