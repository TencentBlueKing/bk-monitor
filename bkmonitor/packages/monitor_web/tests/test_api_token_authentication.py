from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.test import override_settings

from bkmonitor.middlewares.authentication import ApiTokenAuthBackend, ApiTokenAuthenticationMiddleware
from bkmonitor.models import ApiAuthToken


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
    get_admin = mocker.patch("bkmonitor.middlewares.authentication.get_admin_username", return_value=TENANT_ADMIN)
    authenticate = mocker.patch("bkmonitor.middlewares.authentication.auth.authenticate", return_value=user)
    login = mocker.patch("bkmonitor.middlewares.authentication.auth.login")

    assert ApiTokenAuthenticationMiddleware(lambda _: None).api_token_auth(request, Mock()) is None
    assert request.skip_check is True
    get_admin.assert_called_once_with(TENANT_ID)
    authenticate.assert_called_once_with(username=TENANT_ADMIN, tenant_id=TENANT_ID)
    login.assert_called_once_with(request, user)


@pytest.mark.parametrize("create_user,expected", [("creator", "creator"), ("", TENANT_ADMIN)])
def test_entity_token_uses_creator_or_tenant_admin(mocker, create_user, expected):
    record = make_record("entity", create_user)
    request = SimpleNamespace(META={"HTTP_AUTHORIZATION": "Bearer token"}, biz_id=2)
    user = SimpleNamespace(tenant_id=TENANT_ID)
    mocker.patch.object(ApiAuthToken.objects, "get", return_value=record)
    mocker.patch("bkmonitor.middlewares.authentication.get_admin_username", return_value=TENANT_ADMIN)
    authenticate = mocker.patch("bkmonitor.middlewares.authentication.auth.authenticate", return_value=user)
    mocker.patch("bkmonitor.middlewares.authentication.auth.login")

    assert ApiTokenAuthenticationMiddleware(lambda _: None).api_token_auth(request, Mock()) is None
    authenticate.assert_called_once_with(username=expected, tenant_id=TENANT_ID)


@override_settings(ENABLE_MULTI_TENANT_MODE=True)
def test_backend_corrects_tenant_admin_tenant(mocker):
    user = SimpleNamespace(username=TENANT_ADMIN, tenant_id="system", save=Mock())
    user_model = mocker.patch("bkmonitor.middlewares.authentication.get_user_model").return_value
    user_model.objects.get_or_create.return_value = (user, False)
    mocker.patch("bkmonitor.middlewares.authentication.get_admin_username", return_value=TENANT_ADMIN)

    assert ApiTokenAuthBackend().authenticate(None, TENANT_ADMIN, TENANT_ID) is user
    assert user.tenant_id == TENANT_ID
    user.save.assert_called_once_with()


@override_settings(ENABLE_MULTI_TENANT_MODE=True)
def test_backend_does_not_correct_regular_user_tenant(mocker):
    user = SimpleNamespace(username="creator", tenant_id="tenant-b", save=Mock())
    user_model = mocker.patch("bkmonitor.middlewares.authentication.get_user_model").return_value
    user_model.objects.get_or_create.return_value = (user, False)
    mocker.patch("bkmonitor.middlewares.authentication.get_admin_username", return_value=TENANT_ADMIN)

    assert ApiTokenAuthBackend().authenticate(None, user.username, TENANT_ID) is user
    assert user.tenant_id == "tenant-b"
    user.save.assert_not_called()
