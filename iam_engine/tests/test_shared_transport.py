import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests

from iam_engine.v4.client import V4Client
from iam_engine.v4.config import V4Options, load_v4_paths
from iam_engine.v4.exceptions import V4ClientError, V4ResponseError, V4TransportError
from bkmonitor.iam.backends.v4.client import V4Client as MonitorClient


def options(**paths):
    defaults = load_v4_paths(SimpleNamespace())
    defaults.update(paths)
    return V4Options("app", "dummy", "https://iam.example.test/dev", "bk_monitorv3", 10, 100, 4, **defaults)


def response(data=None, status=200, *, empty=False):
    result = Mock(status_code=status, content=b"" if empty else b"json", text="response")
    result.json.return_value = {"data": data}
    return result


@pytest.mark.parametrize("allowed", [True, False])
def test_both_products_share_http_envelope_and_strict_boolean(monkeypatch, allowed):
    send = Mock(return_value=response({"allowed": allowed}))
    monkeypatch.setattr(requests, "request", send)
    shared = V4Client(options(), username="alice", bk_tenant_id="tenant-a")
    monitor = MonitorClient(options(), username="alice", bk_tenant_id="tenant-a")
    assert shared.direct_auth(subject={"type": "user", "id": "alice"}, action_id="view_business") is allowed
    assert monitor.direct_auth(subject={"type": "user", "id": "alice"}, action_id="view_business") is allowed
    for call in send.call_args_list:
        assert (
            call.kwargs["url"]
            == "https://iam.example.test/dev/api/v1/open/rbac/authorization/systems/bk_monitorv3/auth/"
        )
        assert call.kwargs["headers"]["X-Bk-Tenant-Id"] == "tenant-a"
        assert call.kwargs["timeout"] == 10
        assert json.loads(call.kwargs["headers"]["X-Bkapi-Authorization"])["bk_app_code"] == "app"


@pytest.mark.parametrize("data", [{}, {"allowed": "true"}, {"allowed": 1}, None, []])
def test_invalid_decisions_never_allow(monkeypatch, data):
    monkeypatch.setattr(requests, "request", Mock(return_value=response(data)))
    client = V4Client(options(), bk_tenant_id="tenant-a")
    with pytest.raises(V4ResponseError):
        client.direct_auth(subject={"type": "user", "id": "alice"}, action_id="view_business")


@pytest.mark.parametrize(
    "data",
    [
        [],
        [{"resource_id": "1", "allowed": True}] * 2,
        [{"resource_id": "unknown", "allowed": True}],
        [{"resource_id": "1", "allowed": "true"}],
    ],
)
def test_incomplete_duplicate_unknown_batch_results_are_errors(monkeypatch, data):
    monkeypatch.setattr(requests, "request", Mock(return_value=response(data)))
    client = MonitorClient(options(), bk_tenant_id="system")
    with pytest.raises(V4ResponseError):
        client.direct_auth_by_resources(
            subject={"type": "user", "id": "alice"}, action_id="view_business", resources=[{"type": "space", "id": "1"}]
        )


def test_201_empty_grant_custom_path_and_operator(monkeypatch):
    send = Mock(return_value=response(status=201, empty=True))
    monkeypatch.setattr(requests, "request", send)
    client = MonitorClient(
        options(add_authorization_path="custom/{system_id}/grants/"),
        bk_tenant_id="system",
    )
    items = [
        {
            "subject": {"type": "user", "id": "alice"},
            "role_id": "space_operator",
            "related_resource_type_id": "space",
            "resources": [{"type": "space", "id": "space|2"}],
            "expired_at": 1,
        }
    ]
    assert client.add_authorization(items=items, operator="operator") is None
    assert send.call_args.kwargs["url"].endswith("/dev/custom/bk_monitorv3/grants/")
    assert send.call_args.kwargs["json"] == items
    assert send.call_args.kwargs["headers"]["X-Bkiam-Operator"] == "operator"


@pytest.mark.parametrize(
    "status,error",
    [
        (400, V4ClientError),
        (401, V4ClientError),
        (429, V4ClientError),
        (500, V4ClientError),
        (503, V4ClientError),
    ],
)
def test_monitor_error_mapping_preserves_http_failures(monkeypatch, status, error):
    monkeypatch.setattr(requests, "request", Mock(return_value=response(status=status)))
    client = MonitorClient(options(), bk_tenant_id="system")
    with pytest.raises(error):
        client._request("GET", "read/")


def test_business_error_in_200_is_not_success(monkeypatch):
    result = response()
    result.json.return_value = {"error": {"message": "failed"}, "data": {"allowed": True}}
    monkeypatch.setattr(requests, "request", Mock(return_value=result))
    client = V4Client(options(), bk_tenant_id="tenant-a")
    with pytest.raises(V4ClientError):
        client.direct_auth(subject={"type": "user", "id": "alice"}, action_id="view_business")


def test_empty_gateway_and_tenant_never_send(monkeypatch):
    send = Mock()
    monkeypatch.setattr(requests, "request", send)
    for opts, tenant in ((options(), ""), (options(), " ")):
        with pytest.raises(V4TransportError):
            V4Client(opts, bk_tenant_id=tenant)._request("GET", "read/")
    send.assert_not_called()


def test_model_auth_token_paths_and_cache_key_are_shared(monkeypatch):
    send = Mock(return_value=response({"auth_token": "dummy-token"}))
    monkeypatch.setattr(requests, "request", send)
    client = MonitorClient(
        options(auth_token_path="custom/{system_id}/token/", model_base_path="custom/models/"),
        bk_tenant_id="system",
    )
    assert client.retrieve_system_auth_token() == "dummy-token"
    assert send.call_args.kwargs["url"].endswith("/dev/custom/bk_monitorv3/token/")
    send.return_value = response({"count": 0, "results": []})
    assert client.list_actions() == []
    assert send.call_args.kwargs["url"].endswith("/dev/custom/models/bk_monitorv3/actions/?page=1&page_size=100")
