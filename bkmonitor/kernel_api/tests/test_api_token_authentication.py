from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from bkmonitor.models import ApiAuthToken
from kernel_api.middlewares.authentication import AuthenticationMiddleware


TENANT_ID = "tenant-a"
TENANT_ADMIN = "tenant-admin"


def make_record(token_type, create_user=""):
    return SimpleNamespace(
        type=token_type,
        bk_tenant_id=TENANT_ID,
        create_user=create_user,
        namespaces=["biz#2"],
        is_expired=Mock(return_value=False),
        is_allowed_view=Mock(return_value=True),
        is_allowed_namespace=Mock(return_value=True),
    )


@pytest.mark.parametrize("token_type", ["as_code", "grafana"])
def test_privileged_token_uses_tenant_admin(mocker, token_type):
    record = make_record(token_type)
    request = SimpleNamespace(META={"HTTP_AUTHORIZATION": "Bearer token"}, biz_id=2)
    user = SimpleNamespace(tenant_id=TENANT_ID)
    mocker.patch.object(ApiAuthToken.objects, "get", return_value=record)
    get_admin = mocker.patch("kernel_api.middlewares.authentication.get_admin_username", return_value=TENANT_ADMIN)
    authenticate = mocker.patch("kernel_api.middlewares.authentication.auth.authenticate", return_value=user)
    login = mocker.patch("kernel_api.middlewares.authentication.auth.login")

    assert AuthenticationMiddleware(lambda _: None)._handle_api_token_auth(request, Mock()) is None
    assert request.skip_check is True
    get_admin.assert_called_once_with(TENANT_ID)
    authenticate.assert_called_once_with(username=TENANT_ADMIN, bk_tenant_id=TENANT_ID)
    login.assert_called_once_with(request, user)


@pytest.mark.parametrize("create_user,expected", [("creator", "creator"), ("", TENANT_ADMIN)])
def test_entity_token_uses_creator_or_tenant_admin(mocker, create_user, expected):
    record = make_record("entity", create_user)
    request = SimpleNamespace(META={"HTTP_AUTHORIZATION": "Bearer token"}, biz_id=2)
    user = SimpleNamespace(tenant_id=TENANT_ID)
    mocker.patch.object(ApiAuthToken.objects, "get", return_value=record)
    mocker.patch("kernel_api.middlewares.authentication.get_admin_username", return_value=TENANT_ADMIN)
    authenticate = mocker.patch("kernel_api.middlewares.authentication.auth.authenticate", return_value=user)
    mocker.patch("kernel_api.middlewares.authentication.auth.login")

    assert AuthenticationMiddleware(lambda _: None)._handle_api_token_auth(request, Mock()) is None
    authenticate.assert_called_once_with(username=expected, bk_tenant_id=TENANT_ID)
