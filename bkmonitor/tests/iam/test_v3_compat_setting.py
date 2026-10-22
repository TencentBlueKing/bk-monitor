"""Keep the existing persisted Action V1/V2 compatibility boundary."""

from unittest.mock import Mock

import pytest
from iam import IAM
from monitor.models import GlobalConfig

from bkmonitor.iam.backends.v3.compat import is_v1_compat_enabled
from bkmonitor.iam.backends.v3.codec import MonitorV3Codec
from bkmonitor.iam.backends.v3.client import V3Client


@pytest.fixture(autouse=True)
def clear_compat_cache():
    is_v1_compat_enabled.cache_clear()
    yield
    is_v1_compat_enabled.cache_clear()


def persisted(monkeypatch, value):
    objects = Mock()
    objects.get.return_value = Mock(value=value)
    monkeypatch.setattr(GlobalConfig, "objects", objects)
    return objects


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
    objects = persisted(monkeypatch, False)
    client = make_client()
    parent = Mock(return_value={"op": "eq", "field": "space.id", "value": "2"})
    monkeypatch.setattr(IAM, "_do_policy_query", parent)
    client._client = Mock()
    query = client.make_request("alice", "view_business_v2")
    assert client._do_policy_query(query) == parent.return_value
    parent.assert_called_once_with(query, True)
    client._client.policy_query.assert_not_called()
    objects.get.assert_called_with(key="IAM_V1_COMPATIBLE")


def test_missing_switch_keeps_compat_and_reads_once(monkeypatch):
    objects = persisted(monkeypatch, None)
    objects.get.side_effect = GlobalConfig.DoesNotExist
    assert is_v1_compat_enabled() is True
    assert is_v1_compat_enabled() is True
    assert objects.get.call_count == 1


def test_dynamic_compat_change_invalidates_cached_decisions(monkeypatch):
    objects = persisted(monkeypatch, True)
    client = make_client()
    query = client.make_request("alice", "view_business_v2")
    authorize = Mock(side_effect=[True, False])
    monkeypatch.setattr(client, "is_allowed", authorize)
    assert client.is_allowed_with_cache(query) is True
    assert client.is_allowed_with_cache(query) is True
    objects.get.return_value = Mock(value=False)
    is_v1_compat_enabled.cache_clear()
    assert client.is_allowed_with_cache(query) is False
    assert authorize.call_count == 2
