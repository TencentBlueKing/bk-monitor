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

import pytest
from django.db import connections
from rest_framework.exceptions import ValidationError

from bkmonitor.iam import ActionEnum, Permission
from bkmonitor.middlewares.authentication import ApiTokenAuthenticationMiddleware
from bkmonitor.models import ApiAuthToken
from bkmonitor.utils.local import local
from calendars.models import CalendarItemModel, CalendarModel
from calendars.resources.calendar import DeleteCalendarResource, EditCalendarResource, GetCalendarResource
from calendars.resources.item import DeleteItemResource, EditItemResource, ItemListResource, SaveItemResource
from calendars.views import CalendarsViewSet
from core.errors.iam import PermissionDeniedError


@pytest.fixture
def calendar_request(mocker, monkeypatch):
    request = SimpleNamespace(
        method="POST",
        path="/calendars/save_calendar/",
        biz_id=None,
        data={},
        user=SimpleNamespace(username="calendar-manager", tenant_id="tenant-a", is_superuser=False),
        skip_check=False,
    )
    monkeypatch.setattr(local, "current_request", request, raising=False)
    iam = mocker.Mock()
    mocker.patch.object(Permission, "get_iam_client", return_value=iam)
    mocker.patch.object(Permission, "get_apply_data", return_value=({}, ""))
    return request, iam


@pytest.mark.parametrize("biz_id", [None, "0", "2", "-2"])
@pytest.mark.parametrize("allowed", [False, True])
def test_calendar_management_checks_global_permission(calendar_request, biz_id, allowed):
    request, iam = calendar_request
    request.biz_id = biz_id
    request.data = {"bk_biz_id": 999}
    iam.is_allowed.return_value = allowed
    view = CalendarsViewSet()
    view.request = request
    view.action = "save_calendar"

    if allowed:
        view.check_permissions(request)
    else:
        with pytest.raises(PermissionDeniedError):
            view.check_permissions(request)

    iam_request = iam.is_allowed.call_args.args[0]
    assert iam_request.action.id == ActionEnum.MANAGE_CALENDAR.id
    assert iam_request.subject.id == request.user.username
    assert iam_request.resources == []
    iam.is_allowed.assert_called_once()
    Permission.get_iam_client.assert_called_once_with("tenant-a")


@pytest.mark.parametrize(
    "action", ["save_calendar", "edit_calendar", "delete_calendar", "save_item", "edit_item", "delete_item"]
)
def test_every_calendar_write_requires_management(calendar_request, action):
    request, iam = calendar_request
    iam.is_allowed.return_value = False
    view = CalendarsViewSet()
    view.request = request
    view.action = action
    with pytest.raises(PermissionDeniedError):
        view.check_permissions(request)


@pytest.mark.parametrize(
    ("method", "action"),
    [("GET", "get_calendar"), ("GET", "list_calendar"), ("POST", "item_detail"), ("POST", "item_list")],
)
def test_calendar_reads_do_not_require_management(calendar_request, method, action):
    request, iam = calendar_request
    request.method = method
    view = CalendarsViewSet()
    view.request = request
    view.action = action
    view.check_permissions(request)
    iam.is_allowed.assert_not_called()


@pytest.mark.parametrize("token_type", ["as_code", "grafana", "entity"])
def test_tokens_with_permission_bypass_cannot_access_calendar_writes(calendar_request, mocker, token_type):
    request, _ = calendar_request
    request.META = {"HTTP_AUTHORIZATION": "Bearer calendar-test-token"}
    token = ApiAuthToken(type=token_type, namespaces=["biz#all"])
    mocker.patch.object(ApiAuthToken.objects, "get", return_value=token)
    login = mocker.patch("bkmonitor.middlewares.authentication.auth.login")
    view = CalendarsViewSet.as_view({"post": "save_calendar"})
    response = ApiTokenAuthenticationMiddleware(lambda request: None).api_token_auth(request, view)
    assert response.status_code == 403
    assert request.skip_check is False
    login.assert_not_called()


def test_share_token_does_not_grant_calendar_management(calendar_request, mocker):
    request, iam = calendar_request
    request.token = "calendar-test-token"
    mocker.patch.object(ApiAuthToken.objects, "get", return_value=ApiAuthToken(type="event"))
    iam.is_allowed.return_value = False
    view = CalendarsViewSet()
    view.request = request
    view.action = "save_calendar"
    with pytest.raises(PermissionDeniedError):
        view.check_permissions(request)
    iam.is_allowed.assert_called_once()


@pytest.fixture
def calendar_rows(calendar_request, django_db_blocker, monkeypatch):
    """Use real tenant-filtered ORM queries without bootstrapping unrelated application tables."""
    alias = "calendar_permission_test"
    connections.databases[alias] = {
        **connections.databases["default"],
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
        "OPTIONS": {},
    }
    connection = connections[alias]
    monkeypatch.setattr(CalendarModel, "objects", CalendarModel.objects.db_manager(alias))
    monkeypatch.setattr(CalendarItemModel, "objects", CalendarItemModel.objects.db_manager(alias))
    with django_db_blocker.unblock():
        try:
            with connection.schema_editor() as editor:
                editor.create_model(CalendarModel)
                editor.create_model(CalendarItemModel)
            rows = []
            for tenant in ("tenant-a", "tenant-b"):
                calendar = CalendarModel.objects.create(bk_tenant_id=tenant, name=tenant, classify="custom")
                item = CalendarItemModel.objects.create(
                    bk_tenant_id=tenant,
                    calendar_id=calendar.id,
                    name=tenant,
                    start_time=1700000000,
                    end_time=1700003600,
                    repeat={},
                    time_zone="UTC",
                )
                rows.append((calendar, item))
            yield rows
        finally:
            connection.close()
            del connections[alias]
            del connections.databases[alias]


@pytest.mark.parametrize("resource", [GetCalendarResource, EditCalendarResource, DeleteCalendarResource])
def test_calendar_objects_remain_tenant_scoped(calendar_rows, resource):
    own_calendar, _ = calendar_rows[0]
    other_calendar, _ = calendar_rows[1]
    assert GetCalendarResource().perform_request({"id": own_calendar.id})["id"] == own_calendar.id
    with pytest.raises(CalendarModel.DoesNotExist):
        resource().perform_request({"id": other_calendar.id, "name": "changed"})
    other_calendar.refresh_from_db(using=other_calendar._state.db)
    assert other_calendar.name == "tenant-b"


@pytest.mark.parametrize("resource", [EditItemResource, DeleteItemResource])
def test_calendar_item_mutations_remain_tenant_scoped(calendar_rows, resource):
    _, other_item = calendar_rows[1]
    with pytest.raises(CalendarItemModel.DoesNotExist):
        resource.RequestSerializer().validate_id(other_item.id)
    other_item.refresh_from_db(using=other_item._state.db)
    assert other_item.name == "tenant-b"


@pytest.mark.parametrize("resource", [SaveItemResource, EditItemResource])
def test_cannot_attach_items_to_another_tenant_calendar(calendar_rows, resource):
    own_calendar, _ = calendar_rows[0]
    other_calendar, _ = calendar_rows[1]
    serializer = resource.RequestSerializer()
    assert serializer.validate_calendar_id(own_calendar.id) == own_calendar.id
    with pytest.raises(ValidationError):
        serializer.validate_calendar_id(other_calendar.id)


def test_calendar_item_reads_ignore_requested_foreign_tenant(calendar_rows):
    own_calendar, own_item = calendar_rows[0]
    other_calendar, _ = calendar_rows[1]
    serializer = ItemListResource.RequestSerializer(
        data={
            "bk_tenant_id": "tenant-b",
            "calendar_ids": [own_calendar.id, other_calendar.id],
            "start_time": 1700000000,
            "end_time": 1700003600,
            "time_zone": "UTC",
        }
    )
    serializer.is_valid(raise_exception=True)
    result = ItemListResource().perform_request(serializer.validated_data)
    assert [item["id"] for day in result for item in day["list"]] == [own_item.id]
