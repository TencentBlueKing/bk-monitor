"""Both Monitor and BKLog use native shared V4 transport errors."""

from types import SimpleNamespace
from unittest.mock import Mock
import pytest
import requests
from bkmonitor.iam.backends.v4.client import V4Client
from iam_engine.v4.config import V4Options, load_v4_paths
from iam_engine.v4.exceptions import V4ClientError, V4TransportError, V4TimeoutError


def client(gateway="https://iam.example.test"):
    options = V4Options("offline", "offline", gateway, "bk_monitorv3", 1, 20, 4, **load_v4_paths(SimpleNamespace()))
    return V4Client(options, bk_tenant_id="system")


@pytest.mark.parametrize("method", ["POST", "GET", "PUT", "DELETE"])
def test_empty_gateway_rejects_before_network(monkeypatch, method):
    send = Mock()
    monkeypatch.setattr(requests, "request", send)
    with pytest.raises(V4TransportError):
        client("")._request(method, "path/")
    send.assert_not_called()


@pytest.mark.parametrize(
    "error,expected",
    [
        (requests.ConnectionError("dns"), V4TransportError),
        (requests.Timeout("timeout"), V4TimeoutError),
        (requests.exceptions.InvalidURL("invalid"), V4TransportError),
    ],
)
def test_request_exceptions_share_native_mapping(monkeypatch, error, expected):
    monkeypatch.setattr(requests, "request", Mock(side_effect=error))
    with pytest.raises(expected) as caught:
        client()._request("POST", "path/", body={})
    assert caught.value.__cause__ is error


def test_http_status_preserved_for_retry_classification(monkeypatch):
    response = Mock(status_code=502, text="bad gateway", content=b"json")
    response.json.return_value = {"error": {"message": "bad gateway"}}
    monkeypatch.setattr(requests, "request", Mock(return_value=response))
    with pytest.raises(V4ClientError) as caught:
        client()._request("GET", "path/")
    assert caught.value.status_code == 502
