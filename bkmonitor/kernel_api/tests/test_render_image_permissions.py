"""图片渲染仅对网关请求按 options 中的业务校验应用授权，保留仪表盘权限校验。"""

import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory

from bkmonitor.iam.action import ActionEnum
from kernel_api.middlewares import authentication
from kernel_api.views.v4 import mail_report


@pytest.fixture
def render_context(mocker):
    request = RequestFactory().post(
        "/api/v4/render_image/render/",
        data={},
        content_type="application/json",
        HTTP_BK_APP_CODE="render-app",
        HTTP_X_BKAPI_FROM="apigw",
        HTTP_X_BKAPI_JWT="verified-jwt",
    )
    request.jwt = SimpleNamespace(app=authentication.BkJWTClient.AttrDict(app_code="render-app"))
    request.biz_id = None
    request.user = SimpleNamespace(username="admin", tenant_id="tenant-a")
    request.skip_check = True
    mocker.patch.object(mail_report, "get_request", return_value=request)
    mocker.patch.object(mail_report, "get_request_tenant_id", return_value="tenant-a")
    mocker.patch.object(authentication, "APP_CODE_TOKENS", {"tenant-a": {"render-app": ["biz#2"]}})
    mocker.patch.object(authentication, "APP_CODE_UPDATE_TIME", {"tenant-a": time.time()})
    permission = mocker.patch.object(mail_report, "Permission").return_value
    permission.batch_is_allowed.return_value = {"dashboard": {ActionEnum.VIEW_SINGLE_DASHBOARD.id: True}}
    mocker.patch.object(mail_report.ResourceEnum.GRAFANA_DASHBOARD, "create_instance")
    return request, permission


def validate_render(bk_biz_id=2):
    serializer = mail_report.RenderImageResource.RequestSerializer(
        data={
            "type": "dashboard",
            "options": {
                "bk_biz_id": bk_biz_id,
                "dashboard_uid": "dashboard",
                "width": 800,
                "start_time": 1719859200,
                "end_time": 1719862800,
            },
        }
    )
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


@pytest.mark.parametrize("request_biz_id", [None, 2])
def test_denies_unauthorized_nested_business(render_context, request_biz_id):
    request, permission = render_context
    request.biz_id = request_biz_id

    with pytest.raises(PermissionDenied, match="access this business"):
        validate_render(bk_biz_id=3)

    permission.batch_is_allowed.assert_not_called()
    assert request.biz_id == request_biz_id


@pytest.mark.parametrize("namespaces", [["biz#2"], ["biz#all"]])
def test_allows_authorized_business_and_checks_dashboard(render_context, namespaces):
    request, permission = render_context
    authentication.APP_CODE_TOKENS["tenant-a"]["render-app"] = namespaces

    assert validate_render()["options"]["bk_biz_id"] == 2
    permission.batch_is_allowed.assert_called_once()
    assert permission.skip_check is False
    assert request.biz_id is None


def test_preserves_unconfigured_app_behavior(render_context):
    request, permission = render_context
    request.jwt.app["app_code"] = "unconfigured-app"

    assert validate_render(bk_biz_id=3)["options"]["bk_biz_id"] == 3
    permission.batch_is_allowed.assert_called_once()


@pytest.mark.parametrize("header_app_code", [None, "unconfigured-app"])
def test_uses_gateway_app_identity(render_context, header_app_code):
    request, _ = render_context
    if header_app_code is None:
        request.META.pop("HTTP_BK_APP_CODE")
    else:
        request.META["HTTP_BK_APP_CODE"] = header_app_code

    with pytest.raises(PermissionDenied, match="access this business"):
        validate_render(bk_biz_id=3)


def test_uses_current_tenant_authorization(render_context, mocker):
    request, _ = render_context
    request.user.tenant_id = "tenant-b"
    mocker.patch.object(mail_report, "get_request_tenant_id", return_value="tenant-b")
    authentication.APP_CODE_TOKENS["tenant-b"] = {"render-app": ["biz#3"]}
    authentication.APP_CODE_UPDATE_TIME["tenant-b"] = time.time()

    with pytest.raises(PermissionDenied, match="access this business"):
        validate_render(bk_biz_id=2)

    assert validate_render(bk_biz_id=3)["options"]["bk_biz_id"] == 3


@pytest.mark.parametrize("has_request", [False, True])
def test_preserves_calls_without_app_identity(render_context, mocker, has_request):
    request, permission = render_context
    request.META = {}
    if not has_request:
        mocker.patch.object(mail_report, "get_request", return_value=None)
    check = mocker.patch.object(mail_report, "is_match_api_token")

    validate_render()

    check.assert_not_called()
    permission.batch_is_allowed.assert_called_once()


def test_app_authorization_does_not_bypass_dashboard_permission(render_context):
    _, permission = render_context
    permission.batch_is_allowed.return_value = {"dashboard": {ActionEnum.VIEW_SINGLE_DASHBOARD.id: False}}

    with pytest.raises(PermissionDenied, match="view this dashboard"):
        validate_render()


@pytest.mark.parametrize("bk_biz_id", [2, "2", -2, "-2"])
def test_accepts_existing_business_id_formats(render_context, bk_biz_id):
    authentication.APP_CODE_TOKENS["tenant-a"]["render-app"] = ["biz#2", "biz#-2"]

    assert validate_render(bk_biz_id)["options"]["bk_biz_id"] == int(bk_biz_id)


def test_authorized_gateway_app_is_not_rejected_by_header_identity(render_context):
    request, _ = render_context
    request.jwt = authentication.BkJWTClient.AttrDict(app=authentication.BkJWTClient.AttrDict(app_code="render-app"))
    request.META["HTTP_BK_APP_CODE"] = "restricted-app"
    authentication.APP_CODE_TOKENS["tenant-a"]["restricted-app"] = ["biz#3"]

    assert validate_render()["options"]["bk_biz_id"] == 2


@pytest.mark.parametrize("configured", [False, True])
def test_loads_current_tenant_authorizations_on_first_request(render_context, mocker, configured):
    authentication.APP_CODE_TOKENS.clear()
    authentication.APP_CODE_UPDATE_TIME.clear()
    records = [SimpleNamespace(params={"app_code": "render-app"}, namespaces=["biz#2"])] if configured else []
    query = mocker.patch.object(authentication.ApiAuthToken.objects, "filter", return_value=records)

    assert validate_render()["options"]["bk_biz_id"] == 2

    query.assert_called_once_with(type=authentication.AuthType.API, bk_tenant_id="tenant-a")


def test_preserves_authenticated_bearer_token_authorization(render_context, mocker):
    request, permission = render_context
    request.META.pop("HTTP_X_BKAPI_FROM")
    request.META.pop("HTTP_X_BKAPI_JWT")
    del request.jwt
    request.META["HTTP_AUTHORIZATION"] = "Bearer share-token"
    request.biz_id = 3
    record = SimpleNamespace(
        type="dashboard",
        namespaces=["biz#3"],
        is_expired=Mock(return_value=False),
        is_allowed_view=Mock(return_value=True),
        is_allowed_namespace=Mock(side_effect=lambda namespace: namespace == "biz#3"),
    )
    mocker.patch.object(authentication.ApiAuthToken.objects, "get", return_value=record)

    middleware = authentication.AuthenticationMiddleware(lambda _: None)
    assert middleware._handle_api_token_auth(request, Mock()) is None
    assert request.token == "share-token"
    assert validate_render(bk_biz_id=3)["options"]["bk_biz_id"] == 3
    record.is_allowed_namespace.assert_called_once_with("biz#3")
    permission.batch_is_allowed.assert_called_once()


def test_gateway_bearer_header_does_not_skip_app_authorization(render_context):
    request, _ = render_context
    request.META["HTTP_AUTHORIZATION"] = "Bearer unverified-token"

    with pytest.raises(PermissionDenied, match="access this business"):
        validate_render(bk_biz_id=3)


@pytest.mark.parametrize("missing_header", ["HTTP_X_BKAPI_FROM", "HTTP_X_BKAPI_JWT"])
def test_non_gateway_request_does_not_check_app_authorization(render_context, mocker, missing_header):
    request, permission = render_context
    request.META.pop(missing_header)
    del request.jwt
    check = mocker.patch.object(mail_report, "is_match_api_token")

    assert validate_render(bk_biz_id=3)["options"]["bk_biz_id"] == 3
    check.assert_not_called()
    permission.batch_is_allowed.assert_called_once()


@pytest.mark.parametrize(
    "jwt",
    [
        None,
        SimpleNamespace(),
        SimpleNamespace(app=None),
        SimpleNamespace(app={}),
        SimpleNamespace(app=authentication.BkJWTClient.AttrDict()),
        SimpleNamespace(app={"app_code": None}),
        SimpleNamespace(app={"app_code": ""}),
    ],
    ids=["null-jwt", "missing-app", "null-app", "empty-app", "empty-attrdict", "null-app-code", "empty-app-code"],
)
def test_missing_gateway_app_identity_preserves_existing_permissions(render_context, mocker, jwt):
    request, permission = render_context
    request.jwt = jwt
    check = mocker.patch.object(mail_report, "is_match_api_token")

    validate_render(bk_biz_id=3)

    check.assert_not_called()
    permission.batch_is_allowed.assert_called_once()
    permission.batch_is_allowed.return_value = {"dashboard": {ActionEnum.VIEW_SINGLE_DASHBOARD.id: False}}
    with pytest.raises(PermissionDenied, match="view this dashboard"):
        validate_render(bk_biz_id=3)


def test_missing_jwt_attribute_does_not_raise(render_context, mocker):
    request, permission = render_context
    del request.jwt
    check = mocker.patch.object(mail_report, "is_match_api_token")

    validate_render(bk_biz_id=3)

    check.assert_not_called()
    permission.batch_is_allowed.assert_called_once()
