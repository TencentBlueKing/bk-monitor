"""图片渲染按 options 中的业务校验应用授权，并保留用户仪表盘权限校验。"""

import time
from types import SimpleNamespace

import pytest
from django.core.exceptions import PermissionDenied

from bkmonitor.iam.action import ActionEnum
from kernel_api.middlewares import authentication
from kernel_api.views.v4 import mail_report


@pytest.fixture
def render_context(mocker):
    request = SimpleNamespace(
        META={"HTTP_BK_APP_CODE": "render-app"},
        biz_id=None,
        user=SimpleNamespace(username="admin", tenant_id="tenant-a"),
        skip_check=True,
    )
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
    request.META["HTTP_BK_APP_CODE"] = "unconfigured-app"

    assert validate_render(bk_biz_id=3)["options"]["bk_biz_id"] == 3
    permission.batch_is_allowed.assert_called_once()


@pytest.mark.parametrize("header_app_code", [None, "unconfigured-app"])
def test_uses_gateway_app_identity(render_context, header_app_code):
    request, _ = render_context
    request.jwt = SimpleNamespace(app=SimpleNamespace(app_code="render-app"))
    request.META = {} if header_app_code is None else {"HTTP_BK_APP_CODE": header_app_code}

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
