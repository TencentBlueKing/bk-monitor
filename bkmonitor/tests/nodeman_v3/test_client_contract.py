import json

import pytest
import requests
from django.test import override_settings

from bkmonitor.nodeman_integration.v3.client import (
    NodeManV3APIError,
    NodeManV3HTTPClient,
    NodeManV3RequestContext,
    NodeManV3TransportError,
    NodeManV3UnknownResultError,
)
from bkmonitor.nodeman_integration.v3.client.host import HostClient, NetworkUnitClient, ProxyClient
from bkmonitor.nodeman_integration.v3.client.deploy_policy import DeployPolicyClient
from bkmonitor.nodeman_integration.v3.client.package import PackageClient, PluginClient
from bkmonitor.nodeman_integration.v3.client.process import ProcessClient
from bkmonitor.nodeman_integration.v3.client.workflow import WorkflowClient


class FakeResponse:
    def __init__(self, payload=None, status_code=200):
        self.payload = payload if payload is not None else {"result": True, "code": 0, "data": {"ok": True}}
        self.status_code = status_code
        self.headers = {"x-bkapi-request-id": "request-id"}
        self.content = json.dumps(self.payload).encode()

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, response=None, error=None):
        self.response = response or FakeResponse()
        self.error = error
        self.calls = []

    def request(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


class InvalidJSONResponse(FakeResponse):
    def json(self):
        raise ValueError("invalid json")


def _context(operation_id="operation-id"):
    return NodeManV3RequestContext(
        bk_tenant_id="tenant-a",
        bk_biz_id=2,
        monitor_operation_id=operation_id,
    )


@override_settings(APP_CODE="bk_monitorv3", SECRET_KEY="secret")
def test_plugin_write_contract_uses_v3_path_service_identity_and_audit(monkeypatch):
    session = FakeSession(FakeResponse({"result": True, "code": 0, "data": {"workflow_id": 101}}))
    events = []
    monkeypatch.setattr("bkmonitor.nodeman_integration.v3.client.get_admin_username", lambda **kwargs: "admin")
    client = NodeManV3HTTPClient(
        base_url="https://nodeman.example/gateway/",
        session=session,
        audit_recorder=events.append,
    )

    result = PluginClient(client).install(
        {"bk_biz_id": 2, "host_ids": [1, 2], "release_id": 3},
        context=_context(),
    )

    assert result == {"workflow_id": 101}
    assert len(session.calls) == 1
    request = session.calls[0]
    assert request["method"] == "POST"
    assert request["url"] == "https://nodeman.example/gateway/api/v3/plugin/install"
    assert request["json"] == {"bk_biz_id": 2, "host_ids": [1, 2], "release_id": 3}
    assert request["timeout"] == 300
    assert request["verify"] is False
    assert request["headers"]["X-Bk-Tenant-Id"] == "tenant-a"
    assert json.loads(request["headers"]["x-bkapi-authorization"]) == {
        "bk_app_code": "bk_monitorv3",
        "bk_app_secret": "secret",
        "bk_username": "admin",
    }
    assert [(event.api_version, event.action, event.monitor_operation_id, event.outcome) for event in events] == [
        ("v3", "api/v3/plugin/install", "operation-id", "dispatching"),
        ("v3", "api/v3/plugin/install", "operation-id", "success"),
    ]


@pytest.mark.parametrize(
    ("invoke", "expected_action", "write"),
    [
        (
            lambda client, context: PackageClient(client).publish_plugin_v3(
                {"upload_id": "upload-id", "version": "1.0.0"}, context=context
            ),
            "api/v3/package/publish/release/v3/plugin",
            True,
        ),
        (
            lambda client, context: PackageClient(client).list_plugin_releases(
                {"conditions": {}, "page": 1, "page_size": 20}, context=context
            ),
            "api/v3/package/release/plugin/list",
            False,
        ),
        (
            lambda client, context: WorkflowClient(client).list_workflows(
                {"bk_biz_id": [2], "page": 1, "page_size": 20}, context=context
            ),
            "api/v3/plugin/workflow/list",
            False,
        ),
        (
            lambda client, context: WorkflowClient(client).retry_operation(
                {"workflow_id": 101, "operation_id": 102}, context=context
            ),
            "api/v3/plugin/workflow/operation/retry",
            True,
        ),
        (
            lambda client, context: WorkflowClient(client).list_operation_instance_status_distribution(
                {"trigger_id": ["trigger-1"]}, context=context
            ),
            "api/v3/plugin/workflow/operation/instance/status_distribution/list",
            False,
        ),
        (
            lambda client, context: DeployPolicyClient(client).create(
                {"name": "policy", "specs": [], "scopes": []}, context=context
            ),
            "api/v3/deploy_policy/create",
            True,
        ),
        (
            lambda client, context: DeployPolicyClient(client).update(
                {"deploy_policies": [], "fields": {}}, context=context
            ),
            "api/v3/deploy_policy/update",
            True,
        ),
        (
            lambda client, context: DeployPolicyClient(client).execute({"deploy_policy_id": 1}, context=context),
            "api/v3/deploy_policy/execute",
            True,
        ),
        (
            lambda client, context: DeployPolicyClient(client).list(
                {"page": {"offset": 0, "limit": 20}}, context=context
            ),
            "api/v3/deploy_policy/list",
            False,
        ),
        (
            lambda client, context: ProcessClient(client).list(
                {"bk_biz_id": [2], "page": 1, "page_size": 20}, context=context
            ),
            "api/v3/process/list",
            False,
        ),
        (
            lambda client, context: HostClient(client).list({"exact_conditions": {"bk_biz_id": [2]}}, context=context),
            "api/v3/topo/host/list",
            False,
        ),
        (
            lambda client, context: ProxyClient(client).install(
                {"bk_biz_id": 2, "hosts": [{"host_id": 1}]}, context=context
            ),
            "api/v3/node/proxy/install",
            True,
        ),
        (
            lambda client, context: NetworkUnitClient(client).list(
                {"exact_conditions": {"bk_biz_id": [2]}}, context=context
            ),
            "api/v3/topo/networkunit/list",
            False,
        ),
    ],
)
def test_grouped_client_methods_keep_exact_path_method_and_payload(monkeypatch, invoke, expected_action, write):
    session = FakeSession()
    monkeypatch.setattr("bkmonitor.nodeman_integration.v3.client.get_admin_username", lambda **kwargs: "admin")
    client = NodeManV3HTTPClient(base_url="https://nodeman.example", session=session)
    context = _context() if write else _context(operation_id=None)

    invoke(client, context)

    assert session.calls[0]["method"] == "POST"
    assert session.calls[0]["url"] == f"https://nodeman.example/{expected_action}"


def test_write_requires_monitor_operation_id(monkeypatch):
    session = FakeSession()
    monkeypatch.setattr("bkmonitor.nodeman_integration.v3.client.get_admin_username", lambda **kwargs: "admin")
    client = NodeManV3HTTPClient(base_url="https://nodeman.example", session=session)

    with pytest.raises(ValueError, match="monitor_operation_id"):
        PluginClient(client).stop({"bk_biz_id": 2, "host_ids": [1]}, context=_context(operation_id=None))

    assert session.calls == []


def test_business_id_mismatch_is_rejected_before_request(monkeypatch):
    session = FakeSession()
    monkeypatch.setattr("bkmonitor.nodeman_integration.v3.client.get_admin_username", lambda **kwargs: "admin")
    client = NodeManV3HTTPClient(base_url="https://nodeman.example", session=session)

    with pytest.raises(ValueError, match="bk_biz_id"):
        PluginClient(client).install({"bk_biz_id": 3, "host_ids": [1]}, context=_context())

    assert session.calls == []


@pytest.mark.parametrize(
    ("write", "error", "expected_exception"),
    [
        (True, requests.Timeout("timeout"), NodeManV3UnknownResultError),
        (False, requests.Timeout("timeout"), NodeManV3TransportError),
        (True, requests.ConnectionError("connection"), NodeManV3UnknownResultError),
        (False, requests.ConnectionError("connection"), NodeManV3TransportError),
    ],
)
def test_transport_error_mapping_preserves_unknown_write_result(monkeypatch, write, error, expected_exception):
    session = FakeSession(error=error)
    monkeypatch.setattr("bkmonitor.nodeman_integration.v3.client.get_admin_username", lambda **kwargs: "admin")
    client = NodeManV3HTTPClient(base_url="https://nodeman.example", session=session)

    with pytest.raises(expected_exception):
        client.post("api/v3/plugin/install", {"bk_biz_id": 2}, context=_context(), write=write)


def test_api_error_keeps_code_message_and_request_id(monkeypatch):
    session = FakeSession(FakeResponse({"result": False, "code": 4001001, "message": "invalid release", "data": None}))
    monkeypatch.setattr("bkmonitor.nodeman_integration.v3.client.get_admin_username", lambda **kwargs: "admin")
    client = NodeManV3HTTPClient(base_url="https://nodeman.example", session=session)

    with pytest.raises(NodeManV3APIError) as error:
        client.post("api/v3/plugin/install", {"bk_biz_id": 2}, context=_context(), write=True)

    assert error.value.code == 4001001
    assert error.value.message == "invalid release"
    assert error.value.request_id == "request-id"


@pytest.mark.parametrize("response", [InvalidJSONResponse(), FakeResponse(["unexpected"])])
def test_unusable_success_response_keeps_write_result_unknown(monkeypatch, response):
    session = FakeSession(response)
    monkeypatch.setattr("bkmonitor.nodeman_integration.v3.client.get_admin_username", lambda **kwargs: "admin")
    client = NodeManV3HTTPClient(base_url="https://nodeman.example", session=session)

    with pytest.raises(NodeManV3UnknownResultError):
        client.post("api/v3/plugin/install", {"bk_biz_id": 2}, context=_context(), write=True)


@pytest.mark.parametrize(
    ("status_code", "write", "expected_exception"),
    [(403, True, NodeManV3TransportError), (502, True, NodeManV3UnknownResultError)],
)
def test_http_error_mapping_distinguishes_rejection_from_unknown(monkeypatch, status_code, write, expected_exception):
    session = FakeSession(FakeResponse(status_code=status_code))
    monkeypatch.setattr("bkmonitor.nodeman_integration.v3.client.get_admin_username", lambda **kwargs: "admin")
    client = NodeManV3HTTPClient(base_url="https://nodeman.example", session=session)

    with pytest.raises(expected_exception):
        client.post("api/v3/plugin/install", {"bk_biz_id": 2}, context=_context(), write=write)
