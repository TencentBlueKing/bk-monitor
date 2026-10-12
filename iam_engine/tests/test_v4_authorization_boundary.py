from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from bkmonitor.iam.iam_engine.core.types import Subject
from bkmonitor.iam.iam_engine.provider.dialect_types import DialectAuthRequest
from bkmonitor.iam.iam_v4.provider import V4PermissionProvider


def make_provider(resource_type="grafana_dashboard"):
    provider = object.__new__(V4PermissionProvider)
    provider.schema = Mock()
    provider.schema.get_action.return_value = SimpleNamespace(resource_type=resource_type)
    provider.get_authorized_resources = Mock()
    provider._get_client = Mock()
    provider.is_allowed = Mock(return_value=False)
    return provider


@pytest.mark.parametrize(
    "grants,expected",
    [
        ([], False),
        ([{"type": "space", "ids": []}], False),
        ([{"type": "space", "ids": ["2"]}], True),
        ([{"type": "grafana_dashboard", "ids": ["*"]}], True),
    ],
)
def test_has_any_permission_requires_real_grants(grants, expected):
    provider = make_provider()
    provider.get_authorized_resources.return_value = grants
    assert provider.has_any_permission(Subject("user", tenant_id="tenant-b"), "view_single_dashboard") is expected
    assert provider.get_authorized_resources.call_args.args[0].tenant_id == "tenant-b"


def test_resource_free_action_uses_direct_authorization():
    provider = make_provider("")
    assert not provider.has_any_permission(Subject("user"), "create_resource")
    provider.is_allowed.assert_called_once()
    provider.get_authorized_resources.assert_not_called()


def test_provider_failure_is_not_collapsed_to_business_deny():
    provider = make_provider()
    provider._get_client.return_value.direct_auth.side_effect = TimeoutError("offline timeout")
    with pytest.raises(TimeoutError):
        provider._is_allowed_dialect(DialectAuthRequest(subject=Subject("user"), action_id="create_resource"))
