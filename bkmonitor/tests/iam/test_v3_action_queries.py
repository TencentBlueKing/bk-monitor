"""Action V1 removal preserves current SDK policy and dashboard alias semantics."""

from unittest.mock import Mock

import pytest
from iam.exceptions import AuthAPIError
from monitor.models import GlobalConfig

from bkmonitor.iam.backends.v3.codec import MonitorV3Codec
from bkmonitor.iam.backends.v3.client import V3Client


def client():
    result = V3Client("offline", "offline", "https://iam.example.test", "bk_monitorv3", MonitorV3Codec(), "system")
    result._client = Mock()
    return result


@pytest.mark.parametrize("configured", [True, False, None, GlobalConfig.DoesNotExist(), RuntimeError("DB unavailable")])
@pytest.mark.parametrize("batch", [False, True])
@pytest.mark.parametrize("with_resources", [False, True])
def test_current_policy_queries_ignore_legacy_switch(monkeypatch, configured, batch, with_resources):
    query = Mock()
    if isinstance(configured, Exception):
        query.side_effect = configured
    else:
        query.return_value = Mock(value=configured)
    monkeypatch.setattr(GlobalConfig.objects, "get", query)
    sdk = client()
    request = (
        sdk.make_multi_action_request("alice", ["view_business_v2", "view_event_v2"])
        if batch
        else sdk.make_request("alice", "view_business_v2", [sdk.make_resource("space", "2")])
    )
    wire = sdk._client.v2_policy_query_by_actions if batch else sdk._client.v2_policy_query
    result = [{"action": {"id": "view_business_v2"}, "condition": {}}] if batch else {}
    wire.return_value = (True, "", result)
    method = sdk._do_policy_query_by_actions if batch else sdk._do_policy_query
    assert method(request, with_resources) == result
    expected = request.to_dict()
    if not with_resources:
        expected["resources"] = []
    wire.assert_called_once_with("bk_monitorv3", expected)
    sdk._client.policy_query.assert_not_called()
    sdk._client.policy_query_by_actions.assert_not_called()
    query.assert_not_called()


@pytest.mark.parametrize("batch", [False, True])
def test_sdk_error_propagates_without_legacy_fallback(batch):
    sdk = client()
    wire = sdk._client.v2_policy_query_by_actions if batch else sdk._client.v2_policy_query
    wire.return_value = (False, "unavailable", None)
    request = (
        sdk.make_multi_action_request("alice", ["view_business_v2"])
        if batch
        else sdk.make_request("alice", "view_business_v2")
    )
    method = sdk._do_policy_query_by_actions if batch else sdk._do_policy_query
    with pytest.raises(AuthAPIError):
        method(request)
    sdk._client.policy_query.assert_not_called()
    sdk._client.policy_query_by_actions.assert_not_called()


@pytest.mark.parametrize("allowed", [False, True])
def test_current_action_allow_deny_and_cache(allowed):
    sdk = client()
    sdk._client.policy_query.return_value = (True, "", {"op": "any", "field": "", "value": []})
    sdk._client.v2_policy_query.return_value = (True, "", {"op": "any", "field": "", "value": []} if allowed else {})
    request = sdk.make_request("alice", "view_business_v2", [sdk.make_resource("space", "2", attribute={"id": "2"})])
    assert sdk.is_allowed_with_cache(request) is allowed
    assert sdk.is_allowed_with_cache(request) is allowed
    sdk._client.v2_policy_query.assert_called_once()
    sdk._client.policy_query.assert_not_called()


def test_dashboard_alias_failure_does_not_skip_next_alias():
    sdk = client()
    policy = {"op": "any"}
    sdk._client.v2_policy_query.side_effect = [(True, "", {}), (False, "unavailable", None), (True, "", policy)]
    assert sdk._do_policy_query(sdk.make_request("alice", "new_dashboard")) == policy
    assert [call.args[1]["action"]["id"] for call in sdk._client.v2_policy_query.call_args_list] == [
        "new_dashboard",
        "manage_dashboard_v2",
        "manage_datasource_v2",
    ]
    sdk._client.policy_query.assert_not_called()
