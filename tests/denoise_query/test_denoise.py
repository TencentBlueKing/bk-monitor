import ast
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from rest_framework.exceptions import PermissionDenied

from conftest import ROOT, load, module


def params():
    return {
        "bk_biz_id": 2,
        "start_time": "2026-11-15T00:00:00Z",
        "end_time": "2026-11-15T01:00:00Z",
        "alert_ids": ["180000000000000001"],
    }


@pytest.mark.parametrize(
    "key,value",
    [
        ("bk_tenant_id", "tenant-b"),
        ("scope_id", "bkcc_3"),
        ("bk_username", "admin"),
        ("allow_all", True),
        ("alert_source", "partner"),
    ],
)
def test_web_rejects_caller_supplied_identity(boundary, key, value):
    serializer = boundary.web.AlertDenoiseQuerySerializer(data={**params(), key: value})
    assert not serializer.is_valid()


@pytest.mark.parametrize("biz", [0, -1, -2])
def test_web_rejects_all_business_sentinels(boundary, biz):
    serializer = boundary.web.AlertDenoiseQuerySerializer(data={**params(), "bk_biz_id": biz})
    assert not serializer.is_valid()


def test_web_forwards_only_authorized_scope_and_preserves_result(boundary):
    expected = {
        "schema_version": "1.1",
        "results": [{"alert_id": "180000000000000001", "found": False, "outcome": "unrecorded", "decision": None}],
    }
    boundary.api.bk_incident.get_alert_denoise_decisions.return_value = expected
    serializer = boundary.web.AlertDenoiseQuerySerializer(data=params())
    assert serializer.is_valid(), serializer.errors
    result = boundary.web.GetAlertDenoiseDecisionsResource().perform_request(serializer.validated_data)
    assert result is expected
    payload = boundary.api.bk_incident.get_alert_denoise_decisions.call_args.args[0]
    assert payload["bk_tenant_id"] == "tenant-a" and payload["scope_id"] == "bkcc_2"
    assert payload["alert_source"] == "bk_monitor"
    assert payload["alert_ids"] == ["180000000000000001"]
    assert "bk_biz_id" not in payload and "bk_username" not in payload
    boundary.iam.is_allowed.assert_called_once_with(
        action="view_business", resources=[("business", 2)], raise_exception=True
    )


@pytest.mark.parametrize("failure", ["anonymous", "tenant", "business", "permission", "context"])
def test_web_denies_before_remote_call(boundary, failure):
    if failure == "anonymous":
        boundary.request.user.is_authenticated = False
    elif failure == "tenant":
        boundary.spaces.get_space_detail.return_value.bk_tenant_id = "tenant-b"
    elif failure == "business":
        boundary.spaces.get_space_detail.return_value.bk_biz_id = 3
    elif failure == "permission":
        boundary.iam.is_allowed.return_value = False
    else:
        boundary.request.biz_id = 3
    with pytest.raises(PermissionDenied):
        boundary.web.GetAlertDenoiseDecisionsResource().perform_request(params())
    boundary.api.bk_incident.get_alert_denoise_decisions.assert_not_called()


def test_non_bkcc_space_uses_real_type_and_value(boundary):
    boundary.request.biz_id = -89
    boundary.spaces.get_space_detail.return_value = SimpleNamespace(
        bk_biz_id=-89, bk_tenant_id="tenant-a", space_type_id="bkci", space_id="project_a"
    )
    boundary.web.GetAlertDenoiseDecisionsResource().perform_request({**params(), "bk_biz_id": -89})
    payload = boundary.api.bk_incident.get_alert_denoise_decisions.call_args.args[0]
    assert payload["scope_id"] == "bkci_project_a"
    assert payload["scope_type"] == "bkci" and payload["scope_value"] == "project_a"


def test_permission_does_not_depend_on_legacy_analysis_whitelist(boundary):
    boundary.request.data = params()
    assert boundary.web.DenoiseReadPermission().has_permission(
        boundary.request, SimpleNamespace(action="alert_denoise_decisions")
    )
    tree = ast.parse((ROOT / "packages/monitor_web/incident/views.py").read_text())
    view = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "IncidentViewSet")
    permissions = next(
        node for node in view.body if isinstance(node, ast.FunctionDef) and node.name == "get_permissions"
    )
    assert "DenoiseReadPermission" in ast.unparse(permissions.body[0])


def test_transport_uses_current_user_token_and_preserves_payload(boundary, transport):
    data = {
        "bk_tenant_id": "tenant-a",
        "scope_id": "bkcc_2",
        "scope_type": "bkcc",
        "scope_value": "2",
        "start_time": datetime(2026, 11, 15, tzinfo=timezone.utc),
        "alert_ids": ["180000000000000001"],
    }
    expected = {"results": [{"outcome": "unknown", "reason_code": "service_not_returned"}]}
    transport.client.denoise.get_alert_decisions.return_value = {"result": True, "data": expected}
    assert transport.resource.perform_request(data) is expected
    transport.oauth.get_access_token.assert_called_once_with(boundary.request)
    auth = transport.client.update_bkapi_authorization.call_args.kwargs
    assert auth["access_token"] == "synthetic-user-token" and "bk_username" not in auth
    transport.client.update_headers.assert_called_once_with({"X-Bk-Tenant-Id": "tenant-a"})
    sent = transport.client.denoise.get_alert_decisions.call_args.kwargs["data"]
    assert sent["start_time"] == "2026-11-15T00:00:00+00:00"
    transport.client.disable_ssl_verify.assert_not_called()
    transport.resource.perform_request(data)
    assert transport.client_factory.call_count == 2


def test_transport_rejects_cross_tenant_before_oauth(transport):
    with pytest.raises(PermissionDenied):
        transport.resource.perform_request({"bk_tenant_id": "tenant-b"})
    transport.oauth.get_access_token.assert_not_called()


@pytest.mark.parametrize("body", [{"result": False, "data": None}, {}, [], {"result": True, "data": None}])
def test_transport_does_not_turn_backend_errors_into_no_data(transport, body):
    transport.client.denoise.get_alert_decisions.return_value = body
    with pytest.raises(transport.BKAPIError):
        transport.resource.perform_request({"bk_tenant_id": "tenant-a"})


def test_transport_denied_http_is_error(transport):
    transport.client.denoise.get_alert_decisions.side_effect = transport.ResponseError()
    with pytest.raises(transport.BKAPIError):
        transport.resource.perform_request({"bk_tenant_id": "tenant-a"})


def test_client_operations_bind_exact_native_read_paths():
    dependencies = {
        "bkapi_client_core.apigateway": module(
            "bkapi_client_core.apigateway",
            APIGatewayClient=object,
            OperationGroup=object,
            Operation=object,
            bind_property=lambda operation, **kwargs: SimpleNamespace(**kwargs),
        )
    }
    client = load("denoise_client_test", ROOT / "api/bk_incident/client.py", dependencies)
    for name, method in [("list_decisions", "POST"), ("get_alert_decisions", "POST"), ("get_policy", "GET")]:
        operation = getattr(client.DenoiseOperationGroup, name)
        assert operation.method == method
        assert operation.path == f"/core/v1/incident_denoise/{name}/"
