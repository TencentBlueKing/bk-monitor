"""Request-local policy reuse through the real IAM SDK evaluation paths."""

import copy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from iam import Subject
from iam.exceptions import AuthAPIError

from bkmonitor.iam.backends.v3.client import V3Client
from bkmonitor.iam.backends.v3.codec import MonitorV3Codec


@pytest.fixture
def context():
    return [SimpleNamespace()]


def make_client(context, *, tenant="tenant-a", compat=False):
    client = V3Client(
        "test-app",
        "test-secret",
        "https://iam.example.test",
        "test-system",
        MonitorV3Codec(
            action_id_map={"view_business": "view_business_v2"},
            action_types={"view_business": "view", "read": "view", "other_read": "view", "write": "manage"},
        ),
        bk_tenant_id=tenant,
        enable_v1_compat=compat,
        request_getter=lambda: context[0],
    )
    client._api_version = "v1"
    client._client = Mock()
    client._client.policy_query.return_value = (True, "", None)
    return client


def test_real_sdk_batch_reuses_policy_but_evaluates_each_resource(context):
    client = make_client(context)
    client._client.policy_query_by_actions.return_value = (
        True,
        "",
        [{"action": {"id": "read"}, "condition": {"op": "eq", "field": "space.id", "value": "1"}}],
    )
    request = client.make_multi_action_request("alice", ["read"])
    allowed = client.batch_resource_multi_actions_allowed(request, [[client.make_resource("space", "1")]])
    denied = client.batch_resource_multi_actions_allowed(request, [[client.make_resource("space", "2")]])
    assert allowed == {"1": {"read": True}}
    assert denied == {"2": {"read": False}}
    assert client._client.policy_query_by_actions.call_count == 1


def test_permission_batch_uses_production_factory_request_context(monkeypatch):
    from bkmonitor.iam import ActionEnum
    from bkmonitor.iam.backends import config
    from bkmonitor.iam.backends.v3 import compat
    from bkmonitor.iam.permission import Permission
    from bkmonitor.utils.local import local
    from iam_engine.core.config import AuthMode
    from iam_engine.core.requests import ResourceInstance

    monkeypatch.setattr(config, "_v3_clients", {})
    monkeypatch.setattr(compat, "is_v1_compat_enabled", lambda: False)
    monkeypatch.setattr(local, "current_request", SimpleNamespace(), raising=False)
    permission = Permission(username="alice", bk_tenant_id="system")
    permission.skip_check = False
    permission.mode_provider = SimpleNamespace(get_mode=lambda resources=(): AuthMode.V3)
    client = permission.get_provider("v3")._get_client("system")
    transport = Mock(
        return_value=(
            True,
            "",
            [{"action": {"id": "view_business_v2"}, "condition": {"op": "eq", "field": "space.id", "value": "1"}}],
        )
    )
    method = "v2_policy_query_by_actions" if client._api_version == "v2" else "policy_query_by_actions"
    monkeypatch.setattr(client._client, method, transport)
    allowed = permission.batch_is_allowed([ActionEnum.VIEW_BUSINESS], [[ResourceInstance("space", "1")]])
    denied = permission.batch_is_allowed([ActionEnum.VIEW_BUSINESS], [[ResourceInstance("space", "2")]])
    assert allowed == {"1": {"view_business_v2": True}}
    assert denied == {"2": {"view_business_v2": False}}
    assert transport.call_count == 1
    monkeypatch.setattr(local, "current_request", SimpleNamespace())
    assert permission.batch_is_allowed([ActionEnum.VIEW_BUSINESS], [[ResourceInstance("space", "1")]]) == allowed
    assert transport.call_count == 2


@pytest.mark.parametrize(
    "dimension", ["subject", "subject_type", "action", "resource", "attribute", "system", "environment"]
)
def test_complete_request_key(context, dimension):
    client = make_client(context)
    request = client.make_request("alice", "read", [client.make_resource("space", "1")])
    changed = copy.deepcopy(request)
    if dimension == "subject":
        changed.subject = Subject("user", "bob")
    elif dimension == "subject_type":
        changed.subject = Subject("department", "alice")
    elif dimension == "action":
        changed.action = client.make_action("other_read")
    elif dimension == "resource":
        changed.resources = [client.make_resource("space", "2")]
    elif dimension == "attribute":
        changed.resources = [client.make_resource("space", "1", attribute={"region": "other"})]
    elif dimension == "system":
        changed.system = "other-system"
    else:
        changed.environment = {"ip": "192.0.2.1"}
    client._do_policy_query(request)
    client._do_policy_query(changed)
    client._do_policy_query(request)
    assert client._client.policy_query.call_count == 2


def test_request_and_client_tenant_isolation(context):
    first = make_client(context)
    second = make_client(context, tenant="tenant-b")
    query = first.make_request("alice", "read")
    first._do_policy_query(query)
    second._do_policy_query(query)
    context[0] = SimpleNamespace()
    first._do_policy_query(query)
    assert first._client.policy_query.call_count == 2
    assert second._client.policy_query.call_count == 1


def test_no_http_request_never_reuses(context):
    context[0] = None
    client = make_client(context)
    request = client.make_request("alice", "read")
    client._do_policy_query(request)
    client._do_policy_query(request)
    assert client._client.policy_query.call_count == 2


def test_v2_transport_preserves_system_argument_and_reuses_success(context):
    client = make_client(context)
    client._api_version = "v2"
    client._client.v2_policy_query.return_value = (True, "", None)
    request = client.make_request("alice", "read")
    client._do_policy_query(request)
    client._do_policy_query(request)
    client._client.v2_policy_query.assert_called_once_with("test-system", request.to_dict())


def test_resourceful_and_resource_free_queries_do_not_collide(context):
    client = make_client(context)
    request = client.make_request("alice", "read", [client.make_resource("space", "1")])
    client._do_policy_query(request, with_resources=True)
    client._do_policy_query(request, with_resources=False)
    client._do_policy_query(request, with_resources=True)
    assert client._client.policy_query.call_count == 2


def test_single_write_policy_never_reuses(context):
    client = make_client(context)
    request = client.make_request("alice", "write")
    client._do_policy_query(request)
    client._do_policy_query(request)
    assert client._client.policy_query.call_count == 2


@pytest.mark.parametrize("actions", [["write"], ["unknown"], ["read", "write"]])
def test_write_unknown_and_mixed_actions_are_not_cached(context, actions):
    client = make_client(context)
    client._client.policy_query_by_actions.return_value = (True, "", [])
    request = client.make_multi_action_request("alice", actions)
    client._do_policy_query_by_actions(request)
    client._do_policy_query_by_actions(request)
    assert client._client.policy_query_by_actions.call_count == 2


@pytest.mark.parametrize("failure", [(False, "temporary failure", None), RuntimeError("transport failure")])
def test_failures_retry_and_successful_empty_policy_is_cached(context, failure):
    client = make_client(context)
    client._client.policy_query.side_effect = [failure, (True, "", None)]
    request = client.make_request("alice", "read")
    with pytest.raises((AuthAPIError, RuntimeError)):
        client._do_policy_query(request)
    assert client._do_policy_query(request) is None
    assert client._do_policy_query(request) is None
    assert client._client.policy_query.call_count == 2


def test_v1_batch_compatibility_and_caller_mutation_do_not_pollute_cache(context):
    client = make_client(context, compat=True)

    def query(data):
        action = data["actions"][0]["id"]
        condition = {"op": "eq", "field": "biz.id", "value": "biz|1"} if action == "view_business" else None
        return True, "", [{"action": {"id": action}, "condition": condition}]

    client._client.policy_query_by_actions.side_effect = query
    request = client.make_multi_action_request("alice", ["view_business_v2"])
    first = client._do_policy_query_by_actions(request, with_resources=False)
    expected = [
        {"action": {"id": "view_business_v2"}, "condition": {"op": "eq", "field": "space.id", "value": "space|1"}}
    ]
    assert first == expected
    first[0]["action"]["id"] = "corrupted"
    first[0]["condition"]["value"] = "corrupted"
    assert client._do_policy_query_by_actions(request, with_resources=False) == expected
    assert client._client.policy_query_by_actions.call_count == 2
