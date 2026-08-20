"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.test import override_settings

from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import BusinessActionPermission
from bkmonitor.iam.permission import Permission, api_paths
from bkmonitor.utils.tenant import is_biz_in_tenant
from monitor_web.permissions import BusinessViewPermission


def make_request(bk_biz_id=2, bk_tenant_id="tenant-a"):
    return SimpleNamespace(biz_id=bk_biz_id, user=SimpleNamespace(tenant_id=bk_tenant_id))


def make_iam_permission(token="share-token", path="/api/v4/scene_view/host/"):
    permission = Permission.__new__(Permission)
    permission.request = SimpleNamespace(
        token=token,
        path=path,
        user=SimpleNamespace(tenant_id="tenant-a"),
    )
    permission.skip_check = False
    permission.username = "test-user"
    permission.bk_tenant_id = "tenant-a"
    permission.iam_client = SimpleNamespace(
        is_allowed_with_cache=Mock(return_value=False),
        is_allowed=Mock(return_value=False),
    )
    return permission


@pytest.mark.parametrize("action", [ActionEnum.VIEW_HOST, ActionEnum.VIEW_HOST.id])
def test_host_token_allows_view_host_without_iam(mocker, action):
    mocker.patch(
        "bkmonitor.iam.permission.ApiAuthToken.objects.get",
        return_value=SimpleNamespace(type="host"),
    )
    permission = make_iam_permission()

    assert permission.is_allowed(action) is True
    permission.iam_client.is_allowed_with_cache.assert_not_called()


@pytest.mark.parametrize("token_type", ["collect", "custom_metric", "custom_event"])
def test_non_host_scene_token_does_not_bypass_view_host_iam(mocker, token_type):
    mocker.patch(
        "bkmonitor.iam.permission.ApiAuthToken.objects.get",
        return_value=SimpleNamespace(type=token_type),
    )
    permission = make_iam_permission()

    assert permission.is_allowed(ActionEnum.VIEW_HOST) is False
    permission.iam_client.is_allowed_with_cache.assert_called_once()


@pytest.mark.parametrize("api_path", api_paths)
def test_api_query_path_keeps_token_permission_bypass(mocker, api_path):
    mocker.patch(
        "bkmonitor.iam.permission.ApiAuthToken.objects.get",
        return_value=SimpleNamespace(type="api"),
    )
    permission = make_iam_permission(path=f"/api/v4/{api_path.lstrip('/')}")

    assert permission.is_allowed(ActionEnum.VIEW_HOST) is True
    permission.iam_client.is_allowed_with_cache.assert_not_called()


@pytest.mark.parametrize("iam_allowed", [True, False])
def test_request_without_token_keeps_iam_result(iam_allowed):
    permission = make_iam_permission(token=None)
    permission.iam_client.is_allowed_with_cache.return_value = iam_allowed

    assert permission.is_allowed(ActionEnum.VIEW_HOST) is iam_allowed
    permission.iam_client.is_allowed_with_cache.assert_called_once()


@override_settings(ENABLE_MULTI_TENANT_MODE=False)
def test_is_biz_in_tenant_keeps_single_tenant_compatibility(mocker):
    get_biz_tenant = mocker.patch("bkmonitor.utils.tenant.bk_biz_id_to_bk_tenant_id")

    assert is_biz_in_tenant(2, "another-tenant") is True
    get_biz_tenant.assert_not_called()


@override_settings(ENABLE_MULTI_TENANT_MODE=True)
def test_is_biz_in_tenant_checks_business_ownership(mocker):
    get_biz_tenant = mocker.patch("bkmonitor.utils.tenant.bk_biz_id_to_bk_tenant_id", return_value="tenant-a")

    assert is_biz_in_tenant(2, "tenant-a") is True
    assert is_biz_in_tenant(2, "tenant-b") is False
    assert get_biz_tenant.call_count == 2


@override_settings(ENABLE_MULTI_TENANT_MODE=True)
def test_is_biz_in_tenant_normalizes_string_business_id(mocker):
    get_biz_tenant = mocker.patch("bkmonitor.utils.tenant.bk_biz_id_to_bk_tenant_id", return_value="tenant-a")

    assert is_biz_in_tenant("2", "tenant-a") is True
    get_biz_tenant.assert_called_once_with(2)


@override_settings(ENABLE_MULTI_TENANT_MODE=True)
def test_is_biz_in_tenant_denies_invalid_business_id(mocker):
    get_biz_tenant = mocker.patch("bkmonitor.utils.tenant.bk_biz_id_to_bk_tenant_id")

    assert is_biz_in_tenant("invalid", "tenant-a") is False
    get_biz_tenant.assert_not_called()


@override_settings(ENABLE_MULTI_TENANT_MODE=True)
def test_is_biz_in_tenant_denies_unknown_business(mocker):
    mocker.patch("bkmonitor.utils.tenant.bk_biz_id_to_bk_tenant_id", side_effect=ValueError)

    assert is_biz_in_tenant(2, "tenant-a") is False


def test_business_action_permission_denies_cross_tenant_request(mocker):
    check_tenant = mocker.patch("bkmonitor.iam.drf.is_biz_in_tenant", return_value=False)
    iam_permission = mocker.patch("bkmonitor.iam.drf.IAMPermission.has_permission")
    request = make_request()

    allowed = BusinessActionPermission([ActionEnum.VIEW_BUSINESS]).has_permission(request, None)

    assert allowed is False
    check_tenant.assert_called_once_with(request.biz_id, request.user.tenant_id)
    iam_permission.assert_not_called()


def test_business_action_permission_denies_cross_tenant_object(mocker):
    check_tenant = mocker.patch("bkmonitor.iam.drf.is_biz_in_tenant", return_value=False)
    iam_permission = mocker.patch("bkmonitor.iam.drf.IAMPermission.has_object_permission")
    request = make_request()
    obj = SimpleNamespace(bk_biz_id=3)

    allowed = BusinessActionPermission([ActionEnum.VIEW_BUSINESS]).has_object_permission(request, None, obj)

    assert allowed is False
    check_tenant.assert_called_once_with(obj.bk_biz_id, request.user.tenant_id)
    iam_permission.assert_not_called()


def test_business_view_permission_denies_cross_tenant_request(mocker):
    check_tenant = mocker.patch("monitor_web.permissions.is_biz_in_tenant", return_value=False)
    iam_permission = mocker.patch("monitor_web.permissions.Permission")
    request = make_request()

    allowed = BusinessViewPermission().has_permission(request, None)

    assert allowed is False
    check_tenant.assert_called_once_with(request.biz_id, request.user.tenant_id)
    iam_permission.assert_not_called()


def test_business_view_permission_allows_same_tenant_to_continue_iam_check(mocker):
    mocker.patch("monitor_web.permissions.is_biz_in_tenant", return_value=True)
    permission = mocker.patch("monitor_web.permissions.Permission").return_value
    permission.is_allowed_by_biz.return_value = True
    request = make_request()

    allowed = BusinessViewPermission().has_permission(request, None)

    assert allowed is True
    permission.is_allowed_by_biz.assert_called_once_with(
        bk_biz_id=request.biz_id,
        action=ActionEnum.VIEW_BUSINESS,
        raise_exception=True,
    )
