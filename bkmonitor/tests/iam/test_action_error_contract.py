"""Offline product/DRF contracts; mocked IAM transport, not live HTTP E2E."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from bkmonitor.iam import ActionEnum, Permission
from bkmonitor.iam import permission as permission_module
from bkmonitor.views.renderers import MonitorJSONRenderer
from core.drf_resource.exceptions import custom_exception_handler
from core.errors.iam import ActionNotExistError
from iam_engine.core.config import AuthMode
from iam_engine.core.requests import ResourceInstance
from iam_engine.exceptions import ProviderUnavailable
from monitor_web.iam.views import IAMViewSet


UNKNOWN_ACTION = "__iam_v3_acceptance_unknown_action__"
ENDPOINTS = [
    ("check_allowed_by_action_ids", {"bk_biz_id": 2}),
    ("check_allowed_by_apm_application", {"bk_biz_id": 2, "application_id": 7}),
    ("check_allowed", {"resources": [{"type": "space", "id": "2"}]}),
]


@pytest.fixture
def permission(monkeypatch):
    request = SimpleNamespace(token=None, skip_check=False, user=SimpleNamespace(username="alice", tenant_id="system"))
    monkeypatch.setattr(permission_module, "get_request", lambda **kwargs: request)
    instance = Permission(request=request)
    instance.mode_provider = Mock(get_mode=Mock(return_value=AuthMode.V3))
    instance._is_allowed_request = Mock(return_value=False)
    instance.get_apply_data = Mock(return_value=({}, "https://iam.example.test/apply"))
    # Preserve the real constructor, product entry points and resource constructors.
    monkeypatch.setattr(permission_module, "get_mode_provider", lambda: instance.mode_provider)
    monkeypatch.setattr(Permission, "_is_allowed_request", instance._is_allowed_request)
    monkeypatch.setattr(Permission, "get_apply_data", instance.get_apply_data)
    return instance


@pytest.mark.parametrize("raise_exception", [False, True])
@pytest.mark.parametrize("mode", list(AuthMode))
@pytest.mark.parametrize(
    "resources",
    [[], [ResourceInstance("space", "2")], [ResourceInstance("space", "2"), ResourceInstance("space", "3")]],
)
def test_unknown_action_is_input_error_before_authentication(permission, mode, raise_exception, resources):
    permission.mode_provider.get_mode.return_value = mode
    with pytest.raises(ActionNotExistError) as error:
        permission.is_allowed(UNKNOWN_ACTION, resources, raise_exception=raise_exception)
    assert error.value.status_code == 400
    assert error.value.code == 3399001
    permission.mode_provider.get_mode.assert_not_called()
    permission._is_allowed_request.assert_not_called()
    permission.get_apply_data.assert_not_called()


@pytest.mark.parametrize("endpoint,payload", ENDPOINTS)
@pytest.mark.parametrize("known_first", [False, True])
def test_unknown_action_keeps_real_drf_error_response(permission, endpoint, payload, known_first):
    IAMViewSet.generate_endpoint()
    known_action = "view_apm_application_v2" if "application_id" in payload else "view_business_v2"
    actions = ([known_action] if known_first else []) + [UNKNOWN_ACTION]
    request = APIRequestFactory().post(f"/rest/v2/iam/{endpoint}/", {**payload, "action_ids": actions}, format="json")
    force_authenticate(request, user=SimpleNamespace(is_authenticated=True))
    response = IAMViewSet.as_view({"post": endpoint})(request)
    assert response.data["code"] == 3399001
    response.render()
    body = json.loads(response.content)
    assert response.status_code == 400
    assert body["result"] is False
    # The unchanged V3 renderer keeps code=200 at the top level for this Error.
    assert body["code"] == 200
    assert body["error_details"]["code"] == 3399001
    assert UNKNOWN_ACTION in body["message"]
    assert "apply_url" not in (body.get("data") or {})
    assert "permission" not in body
    legacy_error = custom_exception_handler(ActionNotExistError({"action_id": UNKNOWN_ACTION}), {})
    expected = MonitorJSONRenderer().render(legacy_error.data, renderer_context={"response": legacy_error})
    assert body == json.loads(expected)
    assert permission._is_allowed_request.call_count == int(known_first)
    permission.get_apply_data.assert_not_called()


@pytest.mark.parametrize("action", [ActionEnum.VIEW_BUSINESS, "view_business", "view_business_v2"])
@pytest.mark.parametrize("mode", list(AuthMode))
def test_registered_actions_keep_normal_denial(permission, action, mode):
    permission.mode_provider.get_mode.return_value = mode
    assert permission.is_allowed(action, [ResourceInstance("space", "2")]) is False
    permission._is_allowed_request.assert_called_once()


@pytest.mark.parametrize("endpoint,payload", ENDPOINTS)
@pytest.mark.parametrize("allowed", [False, True])
def test_registered_actions_keep_real_drf_success_contract(permission, endpoint, payload, allowed):
    action = "view_apm_application_v2" if "application_id" in payload else "view_business_v2"
    permission._is_allowed_request.return_value = allowed
    IAMViewSet.generate_endpoint()
    request = APIRequestFactory().post(f"/rest/v2/iam/{endpoint}/", {**payload, "action_ids": [action]}, format="json")
    force_authenticate(request, user=SimpleNamespace(is_authenticated=True))
    response = IAMViewSet.as_view({"post": endpoint})(request)
    response.render()
    body = json.loads(response.content)
    assert response.status_code == 200
    assert body["result"] is True
    assert body["code"] == 200
    detail = body["data"]["detail"] if endpoint == "check_allowed" else body["data"]
    assert detail == [{"action_id": action, "is_allowed": allowed}]


def test_provider_failure_is_not_an_unknown_action_error(permission):
    permission._is_allowed_request.side_effect = ProviderUnavailable("offline timeout")
    assert permission.is_allowed("view_business_v2", [ResourceInstance("space", "2")]) is False


def test_skip_check_still_precedes_action_validation(permission):
    permission.skip_check = True
    assert permission.is_allowed(UNKNOWN_ACTION) is True
    permission._is_allowed_request.assert_not_called()


def test_share_query_exemption_still_precedes_action_validation(permission, monkeypatch):
    permission.request.token = "offline-share"
    permission.request.path = "/time_series/unify_query/"
    monkeypatch.setattr(
        permission_module.ApiAuthToken, "objects", Mock(get=Mock(return_value=SimpleNamespace(type="host")))
    )
    assert permission.is_allowed(UNKNOWN_ACTION) is True
    permission._is_allowed_request.assert_not_called()
