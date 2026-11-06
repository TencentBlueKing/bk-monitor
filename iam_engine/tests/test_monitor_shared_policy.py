from unittest.mock import Mock

import pytest

from iam_engine.core.config import AuthMode
from iam_engine.core.types import (
    AuthorizedResourceScope,
    AuthResult,
    BatchAuthResult as NativeBatchResult,
    BatchAuthResultItem,
)
from iam_engine.core.exceptions import InvalidAuthModeError
from iam_engine.exceptions import ProviderUnavailable
from bkmonitor.iam.permission import Permission
from iam_engine.provider.requests import (
    ApplyURLRequest,
    AuthRequest,
    BatchByActionRequest,
    BatchByResourceRequest,
    ResourceInstance,
    Subject,
    VisibleResult,
)


def provider(name, result):
    value = Mock()
    value.name = name
    if isinstance(result, Exception):
        value.is_allowed.return_value = AuthResult.error(name, str(result) or type(result).__name__)
        value.has_any_permission.side_effect = result
    else:
        value.is_allowed.return_value = (
            AuthResult.allow(name)
            if result is True
            else AuthResult.deny(name)
            if result is False
            else AuthResult.error(name, "invalid response")
        )
        value.has_any_permission.return_value = result
    return value


def policy(mode="union", left=False, right=False):
    v3, v4 = provider("v3", left), provider("v4", right)
    selector = Mock()
    selector.get_mode.return_value = AuthMode(mode)
    permission = Permission(username="user", bk_tenant_id="tenant-a")
    permission._providers = {"v3": v3, "v4": v4}
    permission.mode_provider = selector
    return permission, v3, v4, selector


SUBJECT = Subject(id="user", tenant_id="tenant-a")
RESOURCE = ResourceInstance(type="space", id="-1")


@pytest.mark.parametrize(
    "left,right",
    [
        (left, right)
        for left in (True, False, TimeoutError("offline"))
        for right in (True, False, TimeoutError("offline"))
    ],
)
def test_union_tri_state_matrix(left, right):
    engine, v3, v4, _ = policy(left=left, right=right)
    assert engine._decide_request(AuthRequest(SUBJECT, "view_business", RESOURCE)).allowed is (
        left is True or right is True
    )
    assert engine.has_any_permission(SUBJECT, "view_business") is (left is True or right is True)
    v3.is_allowed.assert_called_once()
    v4.is_allowed.assert_called_once()
    assert v4.is_allowed.call_args.args[0].subject.tenant_id == "tenant-a"


@pytest.mark.parametrize("mode,expected", [("v3", True), ("v4", False)])
def test_single_modes_do_not_consult_other_side(mode, expected):
    engine, v3, v4, _ = policy(mode, True, False)
    assert engine._decide_request(AuthRequest(SUBJECT, "view_business", RESOURCE)).allowed is expected
    assert (v3 if mode == "v4" else v4).is_allowed.call_count == 0


def test_dynamic_mode_is_read_for_each_request():
    engine, _, _, selector = policy(left=True)
    selector.get_mode.side_effect = [AuthMode.V3, AuthMode.V4, AuthMode.UNION]
    request = AuthRequest(SUBJECT, "view_business", RESOURCE)
    assert [engine._decide_request(request).allowed for _ in range(3)] == [True, False, True]


def test_invalid_mode_denies_without_provider_calls():
    engine, v3, v4, selector = policy(left=True, right=True)
    selector.get_mode.side_effect = InvalidAuthModeError("bad", "invalid mode")
    assert not engine._decide_request(AuthRequest(SUBJECT, "view_business", RESOURCE)).allowed
    assert not engine.has_any_permission(SUBJECT, "view_business")
    with pytest.raises(ProviderUnavailable):
        engine.filter_visible_resources(SUBJECT, "view_business", (RESOURCE,))
    v3.is_allowed.assert_not_called()
    v4.is_allowed.assert_not_called()


def test_union_batch_missing_result_is_not_allow_and_mode_is_snapshotted():
    engine, v3, v4, selector = policy()
    v3.batch_is_allowed.return_value = NativeBatchResult(
        (BatchAuthResultItem("view_business", "-1", AuthResult.allow("v3")),)
    )
    v4.batch_is_allowed.return_value = NativeBatchResult()
    result = engine._batch_by_resource(BatchByResourceRequest(SUBJECT, "view_business", (RESOURCE,)))
    assert result.items[0].allowed
    selector.get_mode.assert_called_once()
    v3.batch_is_allowed.return_value = NativeBatchResult()
    assert not engine._batch_by_resource(BatchByResourceRequest(SUBJECT, "view_business", (RESOURCE,))).items[0].allowed


def test_resource_free_batch_snapshots_mode_once():
    engine, _, _, selector = policy(left=True)
    result = engine._batch_by_action(BatchByActionRequest(SUBJECT, ("create_a", "create_b")))
    assert all(item.allowed for item in result.items)
    selector.get_mode.assert_called_once()


def test_union_application_selects_v4_and_empty_is_unavailable():
    engine, v3, v4, _ = policy()
    v3.get_apply_data.return_value, v4.get_apply_data.return_value = ({}, "legacy"), ({}, "current")
    request = ApplyURLRequest(SUBJECT, ("view_business",), (RESOURCE,))
    assert engine._apply_url_request(request) == "current"
    v3.get_apply_data.assert_not_called()
    v4.get_apply_data.return_value = ({}, "")
    assert engine._apply_url_request(request) == ""
    v3.get_apply_data.assert_not_called()
    v3.get_apply_data.return_value, v4.get_apply_data.return_value = (
        ({"system": "legacy"}, "legacy"),
        ({"system": "current"}, "current"),
    )
    assert engine._apply_data_request(["view_business"], [RESOURCE], SUBJECT) == {"system": "current"}


def test_union_scope_merges_healthy_side_and_never_invents_wildcard():
    engine, v3, v4, _ = policy()
    v3.list_authorized_resources.return_value = AuthorizedResourceScope.error(
        "space", provider_name="v3", reason="offline"
    )
    v4.list_authorized_resources.return_value = AuthorizedResourceScope.concrete("space", {"-1"}, provider_name="v4")
    assert engine.filter_visible_resources(SUBJECT, "view_business", (RESOURCE,)) == VisibleResult(False, ("-1",))
    v4.list_authorized_resources.return_value = AuthorizedResourceScope.error(
        "space", provider_name="v4", reason="offline"
    )
    with pytest.raises(ProviderUnavailable):
        engine.filter_visible_resources(SUBJECT, "view_business", (RESOURCE,))


@pytest.mark.parametrize("value", ["false", "true", 1, None])
def test_truthy_provider_response_is_not_explicit_allow(value):
    engine, _, _, _ = policy(left=value)
    decision = engine._decide_request(AuthRequest(SUBJECT, "view_business", RESOURCE))
    assert not decision.allowed
    assert decision.degraded


def test_action_policy_query_is_bulk_and_reads_mode_once():
    engine, v3, v4, selector = policy()
    v3.query_policy_by_actions.return_value = {"view_business": "legacy", "view_host": None}
    v4.query_policy_by_actions.return_value = {"view_business": "current", "view_host": "host"}
    assert engine.query_policies_by_actions(SUBJECT, ["view_business", "view_host"]) == {
        "view_business": ["legacy", "current"],
        "view_host": ["host"],
    }
    selector.get_mode.assert_called_once()
    v3.query_policy_by_actions.assert_called_once()
    v4.query_policy_by_actions.assert_called_once()
