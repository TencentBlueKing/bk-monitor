"""Real V4 client validation and request-local reuse, with synthetic HTTP data."""

from copy import deepcopy
from dataclasses import fields, replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests

from bkmonitor.iam.backends.v4.client import V4Client
from iam_engine.v4.config import V4Options, load_v4_paths
from iam_engine.v4.exceptions import V4ClientError, V4ResponseError


OPTIONS = V4Options(
    "example-app",
    "example-secret",
    "https://iam.example.test",
    "example-system",
    1,
    20,
    4,
    **load_v4_paths(SimpleNamespace()),
)
SUBJECT = {"type": "user", "id": "alice"}
RESOURCE = {
    "type": "dashboard",
    "id": "1",
    "attributes": {"region": "east", "_bk_iam_path_": "/space,1/"},
    "ancestors": [{"type": "space", "id": "1"}],
}
READ_ACTIONS = ("view_dashboard", "view_other")


@pytest.fixture
def context(monkeypatch):
    request = SimpleNamespace()
    send = Mock(return_value={"allowed": True})
    monkeypatch.setattr(V4Client, "_request", send)
    return request, send


def client(request, **kwargs):
    defaults = {
        "request_getter": lambda: request,
        "read_action_ids": READ_ACTIONS,
        "username": "gateway-user",
        "bk_tenant_id": "tenant-a",
    }
    defaults.update(kwargs)
    return V4Client(defaults.pop("options", OPTIONS), **defaults)


def auth(client, **kwargs):
    arguments = {"subject": deepcopy(SUBJECT), "action_id": "view_dashboard", "resource": deepcopy(RESOURCE)}
    arguments.update(kwargs)
    return client.direct_auth(**arguments)


@pytest.mark.parametrize("field,value", [("id", "bob"), ("type", "group")])
def test_subject_identity_isolated(context, field, value):
    request, send = context
    instance = client(request)
    assert auth(instance)
    assert auth(instance, subject={**SUBJECT, field: value})
    assert auth(instance)
    assert send.call_count == 2


@pytest.mark.parametrize(
    "resource",
    [
        None,
        {**RESOURCE, "type": "panel"},
        {**RESOURCE, "id": "2"},
        {**RESOURCE, "attributes": {**RESOURCE["attributes"], "region": "west"}},
        {**RESOURCE, "attributes": {**RESOURCE["attributes"], "_bk_iam_path_": "/space,2/"}},
        {**RESOURCE, "ancestors": [{"type": "space", "id": "2"}]},
    ],
)
def test_resource_shape_isolated(context, resource):
    request, send = context
    instance = client(request)
    assert auth(instance)
    assert auth(instance, resource=resource)
    assert auth(instance)
    assert send.call_count == 2


def test_action_and_request_isolated(context):
    request, send = context
    assert auth(client(request))
    assert auth(client(request), action_id="view_other")
    assert auth(client(SimpleNamespace()))
    assert auth(client(request))
    assert send.call_count == 3


@pytest.mark.parametrize("option", [field.name for field in fields(V4Options)])
def test_every_client_option_isolated(context, option):
    request, send = context
    value = getattr(OPTIONS, option)
    changed = value + 1 if isinstance(value, int | float) else value + "changed"
    assert auth(client(request))
    assert auth(client(request, options=replace(OPTIONS, **{option: changed})))
    assert auth(client(request, options=replace(OPTIONS)))
    assert send.call_count == 2


@pytest.mark.parametrize("identity", [{"username": "other-gateway-user"}, {"bk_tenant_id": "tenant-b"}])
def test_gateway_user_and_tenant_isolated(context, identity):
    request, send = context
    assert auth(client(request))
    assert auth(client(request, **identity))
    assert auth(client(request))
    assert send.call_count == 2


def test_methods_and_resource_type_isolated(context):
    request, send = context
    instance = client(request)
    assert auth(instance)
    send.return_value = [{"resource_id": "1", "allowed": True}]
    assert instance.direct_auth_by_resources(subject=SUBJECT, action_id="view_dashboard", resources=[RESOURCE]) == {
        "1": True
    }
    send.return_value = []
    for resource_type in ("space", "dashboard", "space"):
        assert instance.list_authorized_resource(
            subject=SUBJECT, action_id="view_dashboard", resource_type=resource_type
        ) == {"type": resource_type, "ids": []}
    assert send.call_count == 4


@pytest.mark.parametrize("method", ["direct_auth", "direct_auth_by_resources", "list_authorized_resource"])
@pytest.mark.parametrize("action", ["edit_dashboard", "unknown_action"])
def test_write_and_unknown_actions_bypass(context, method, action):
    request, send = context
    instance = client(request)
    arguments = {"subject": SUBJECT, "action_id": action}
    if method == "direct_auth_by_resources":
        arguments["resources"] = []
    send.return_value = {"allowed": True} if method == "direct_auth" else []
    for _ in range(2):
        getattr(instance, method)(**arguments)
    assert send.call_count == 2
    assert not hasattr(request, "_iam_v4_read_cache")


@pytest.mark.parametrize(
    "overrides", [{"request_getter": None}, {"request_getter": lambda: None}, {"read_action_ids": ()}]
)
def test_no_request_or_no_allowlist_bypasses(context, overrides):
    request, send = context
    instance = client(request, **overrides)
    assert auth(instance)
    assert auth(instance)
    assert send.call_count == 2
    assert not hasattr(request, "_iam_v4_read_cache")


def test_authorization_writes_are_never_cached(context):
    request, send = context
    send.return_value = None
    instance = client(request)
    for _ in range(2):
        instance.add_authorization(items=[{"resources": [{"type": "space", "id": "1"}]}], operator="alice")
    assert send.call_count == 2
    assert not hasattr(request, "_iam_v4_read_cache")


def test_false_and_empty_results_are_cached(context):
    request, send = context
    instance = client(request)
    send.return_value = {"allowed": False}
    assert auth(instance) is False
    assert auth(instance) is False
    send.return_value = []
    for _ in range(2):
        assert instance.direct_auth_by_resources(subject=SUBJECT, action_id="view_dashboard", resources=[]) == {}
        assert instance.list_authorized_resource(subject=SUBJECT, action_id="view_dashboard") == {
            "type": "space",
            "ids": [],
        }
    assert send.call_count == 3


@pytest.mark.parametrize(
    "bad", [{}, {"allowed": "true"}, None, V4ClientError("synthetic failure"), TimeoutError("synthetic timeout")]
)
def test_invalid_or_failed_auth_remains_retryable(context, bad):
    request, send = context
    instance = client(request)
    send.side_effect = [bad, {"allowed": False}]
    with pytest.raises((V4ResponseError, V4ClientError, TimeoutError)):
        auth(instance)
    assert auth(instance) is False
    assert auth(instance) is False
    assert send.call_count == 2


@pytest.mark.parametrize(
    "method,arguments,bad,good",
    [
        ("direct_auth_by_resources", {"resources": [RESOURCE]}, [], [{"resource_id": "1", "allowed": True}]),
        ("list_authorized_resource", {}, [{"type": "space", "ids": [None]}], []),
    ],
)
def test_incomplete_batch_and_invalid_scope_are_not_cached(context, method, arguments, bad, good):
    request, send = context
    instance = client(request)
    send.side_effect = [bad, good]
    call = getattr(instance, method)
    with pytest.raises(V4ResponseError):
        call(subject=SUBJECT, action_id="view_dashboard", **arguments)
    expected = call(subject=SUBJECT, action_id="view_dashboard", **arguments)
    assert call(subject=SUBJECT, action_id="view_dashboard", **arguments) == expected
    assert send.call_count == 2


def test_mutable_inputs_and_outputs_do_not_alias_cache(context):
    request, send = context
    instance = client(request)
    resource = deepcopy(RESOURCE)
    assert auth(instance, resource=resource)
    sent = send.call_args.kwargs["body"]
    resource["ancestors"][0]["id"] = "changed"
    assert sent["resource"]["ancestors"][0]["id"] == "1"
    assert auth(instance, resource=resource)
    assert send.call_count == 2
    send.return_value = [{"type": "space", "ids": ["1"]}]
    result = instance.list_authorized_resource(subject=SUBJECT, action_id="view_dashboard")
    result["ids"].append("injected")
    send.return_value[0]["ids"].append("also-injected")
    assert instance.list_authorized_resource(subject=SUBJECT, action_id="view_dashboard") == {
        "type": "space",
        "ids": ["1"],
    }
    assert send.call_count == 3


@pytest.mark.parametrize(
    "status,payload", [(503, {}), (200, {"error": {"message": "failure"}}), (200, {"wrong": "shape"})]
)
def test_real_http_validation_failure_is_not_cached(monkeypatch, status, payload):
    response = Mock(status_code=status, content=b"json", text="synthetic")
    response.json.return_value = payload
    success = Mock(status_code=200, content=b"json")
    success.json.return_value = {"data": {"allowed": True}}
    send = Mock(side_effect=[response, success])
    monkeypatch.setattr(requests, "request", send)
    instance = client(SimpleNamespace())
    with pytest.raises(V4ClientError):
        auth(instance)
    assert auth(instance)
    assert auth(instance)
    assert send.call_count == 2


@pytest.mark.parametrize("change", ["order", "attributes", "ancestors", "subject", "action"])
def test_batch_complete_arguments_are_isolated(context, change):
    request, send = context
    instance = client(request)
    resources = [deepcopy(RESOURCE), {**deepcopy(RESOURCE), "id": "2"}]
    arguments = {"subject": deepcopy(SUBJECT), "action_id": "view_dashboard", "resources": resources}
    send.return_value = [{"resource_id": "1", "allowed": True}, {"resource_id": "2", "allowed": False}]
    assert instance.direct_auth_by_resources(**arguments) == {"1": True, "2": False}
    changed = deepcopy(arguments)
    if change == "order":
        changed["resources"].reverse()
    elif change == "attributes":
        changed["resources"][0]["attributes"]["region"] = "west"
    elif change == "ancestors":
        changed["resources"][0]["ancestors"][0]["id"] = "changed"
    elif change == "subject":
        changed["subject"]["id"] = "bob"
    else:
        changed["action_id"] = "view_other"
    result = instance.direct_auth_by_resources(**changed)
    result["1"] = False
    assert instance.direct_auth_by_resources(**changed) == {"1": True, "2": False}
    assert instance.direct_auth_by_resources(**arguments) == {"1": True, "2": False}
    assert send.call_count == 2
