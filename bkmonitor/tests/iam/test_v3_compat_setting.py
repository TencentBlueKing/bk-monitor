"""Keep the existing persisted Action V1/V2 compatibility boundary."""

from unittest.mock import Mock

from iam import IAM

from bkmonitor.iam.backends.v3.compat import is_v1_compat_enabled
from bkmonitor.iam.backends.v3.codec import MonitorV3Codec
from bkmonitor.iam.backends.v3.client import V3Client
from bkmonitor.models import GlobalConfig


def make_client():
    return V3Client(
        "offline",
        "offline",
        "https://iam.example.test",
        "bk_monitorv3",
        MonitorV3Codec(),
        "tenant-a",
        enable_v1_compat=is_v1_compat_enabled,
    )


def test_persisted_false_disables_old_action_double_query(monkeypatch):
    config = Mock(return_value=False)
    monkeypatch.setattr(GlobalConfig, "get", config)
    client = make_client()
    parent = Mock(return_value={"op": "eq", "field": "space.id", "value": "2"})
    monkeypatch.setattr(IAM, "_do_policy_query", parent)
    client._client = Mock()
    query = client.make_request("alice", "view_business_v2")
    assert client._do_policy_query(query) == parent.return_value
    parent.assert_called_once_with(query, True)
    client._client.policy_query.assert_not_called()
    config.assert_called_with("IAM_V1_COMPATIBLE", True)


def test_dynamic_compat_change_invalidates_cached_decisions(monkeypatch):
    enabled = [True]
    monkeypatch.setattr(GlobalConfig, "get", lambda *args: enabled[0])
    client = make_client()
    query = client.make_request("alice", "view_business_v2")
    authorize = Mock(side_effect=[True, False])
    monkeypatch.setattr(client, "is_allowed", authorize)
    assert client.is_allowed_with_cache(query) is True
    assert client.is_allowed_with_cache(query) is True
    enabled[0] = False
    assert client.is_allowed_with_cache(query) is False
    assert authorize.call_count == 2
