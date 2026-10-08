"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from types import SimpleNamespace

import pytest

from bkmonitor.iam import ActionEnum, Permission
from bkmonitor.middlewares.authentication import ApiTokenAuthenticationMiddleware
from bkmonitor.models import ApiAuthToken
from bkmonitor.utils.local import local
from calendars.views import CalendarsViewSet
from core.errors.iam import PermissionDeniedError


@pytest.fixture
def calendar_request(mocker, monkeypatch, settings):
    settings.SKIP_IAM_PERMISSION_CHECK = False
    request = SimpleNamespace(
        method="POST",
        path="/calendars/save_calendar/",
        biz_id=None,
        data={},
        COOKIES={},
        user=SimpleNamespace(username="calendar-manager", is_superuser=False),
        skip_check=False,
    )
    monkeypatch.setattr(local, "current_request", request, raising=False)
    iam = mocker.Mock()
    mocker.patch.object(Permission, "get_iam_client", return_value=iam)
    mocker.patch.object(Permission, "get_apply_data", return_value=({}, ""))
    view = CalendarsViewSet()
    view.request = request
    view.action = "save_calendar"
    return request, view, iam


@pytest.mark.parametrize("biz_id", [None, "0", "2", "-2"])
@pytest.mark.parametrize("allowed", [False, True])
def test_calendar_management_uses_global_permission(calendar_request, biz_id, allowed):
    request, view, iam = calendar_request
    request.biz_id = biz_id
    request.data = {"bk_biz_id": 999}
    iam.is_allowed.return_value = allowed

    if allowed:
        view.check_permissions(request)
    else:
        with pytest.raises(PermissionDeniedError):
            view.check_permissions(request)

    iam.is_allowed.assert_called_once()
    iam_request = iam.is_allowed.call_args[0][0]
    assert iam_request.action.id == ActionEnum.MANAGE_CALENDAR.id
    assert iam_request.subject.id == request.user.username
    assert iam_request.resources == []


@pytest.mark.parametrize(
    "action", ["save_calendar", "edit_calendar", "delete_calendar", "save_item", "edit_item", "delete_item"]
)
def test_every_calendar_write_requires_management(calendar_request, action):
    request, view, iam = calendar_request
    view.action = action
    iam.is_allowed.return_value = False
    with pytest.raises(PermissionDeniedError):
        view.check_permissions(request)


@pytest.mark.parametrize(
    ("method", "action"),
    [("GET", "get_calendar"), ("GET", "list_calendar"), ("POST", "item_detail"), ("POST", "item_list")],
)
def test_calendar_reads_do_not_require_management(calendar_request, method, action):
    request, view, iam = calendar_request
    request.method = method
    view.action = action
    view.check_permissions(request)
    iam.is_allowed.assert_not_called()


@pytest.mark.parametrize("token_type", ["as_code", "grafana"])
def test_tokens_with_permission_bypass_cannot_access_calendar_writes(calendar_request, mocker, token_type):
    request, _, iam = calendar_request
    request.META = {"HTTP_AUTHORIZATION": "Bearer calendar-test-token"}
    token = ApiAuthToken(type=token_type, namespaces=["biz#all"])
    mocker.patch.object(ApiAuthToken.objects, "get", return_value=token)
    login = mocker.patch("bkmonitor.middlewares.authentication.auth.login")
    endpoint = CalendarsViewSet.as_view({"post": "save_calendar"})

    response = ApiTokenAuthenticationMiddleware(lambda request: None).process_view(request, endpoint)

    assert response.status_code == 403
    assert request.skip_check is False
    login.assert_not_called()
    iam.is_allowed.assert_not_called()


def test_share_token_does_not_grant_calendar_management(calendar_request, mocker):
    request, view, iam = calendar_request
    request.META = {"HTTP_AUTHORIZATION": "Bearer calendar-test-token"}
    token = ApiAuthToken(type="event", namespaces=["biz#all"])
    mocker.patch.object(ApiAuthToken.objects, "get", return_value=token)
    endpoint = CalendarsViewSet.as_view({"post": "save_calendar"})
    assert ApiTokenAuthenticationMiddleware(lambda request: None).process_view(request, endpoint) is None
    assert request.skip_check is False

    iam.is_allowed.return_value = False
    with pytest.raises(PermissionDeniedError):
        view.check_permissions(request)
    iam.is_allowed.assert_called_once()
