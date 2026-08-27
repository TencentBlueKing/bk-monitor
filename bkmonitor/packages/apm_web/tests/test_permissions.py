from types import SimpleNamespace
from unittest import mock

import pytest
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apm_web.meta.views import ApplicationViewSet
from apm_web.service.views import ServiceViewSet
from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import InstanceActionForDataPermission, InstanceActionPermission


def build_viewset(view_class, action, data=None, method="post"):
    factory = APIRequestFactory()
    if method == "get":
        raw_request = factory.get("/", data or {})
    else:
        raw_request = factory.post("/", data or {}, format="json")
    viewset = view_class()
    viewset.request = Request(raw_request)
    viewset.action = action
    viewset.kwargs = {}
    return viewset


@pytest.mark.parametrize(
    ("action", "permission_type"),
    [
        ("dimension_data", InstanceActionPermission),
        ("indices_info", InstanceActionPermission),
        ("custom_service_data_view_config", InstanceActionPermission),
        ("service_list", InstanceActionForDataPermission),
        ("query_exception_event", InstanceActionForDataPermission),
        ("instance_discover_keys", InstanceActionForDataPermission),
        ("custom_service_list", InstanceActionForDataPermission),
        ("custom_service_url_list", InstanceActionForDataPermission),
    ],
)
def test_application_read_actions_require_apm_instance_permission(action, permission_type):
    permissions = build_viewset(ApplicationViewSet, action, {"bk_biz_id": 2, "app_name": "demo"}).get_permissions()

    assert len(permissions) == 1
    assert isinstance(permissions[0], permission_type)
    assert permissions[0].actions == [ActionEnum.VIEW_APM_APPLICATION]


@pytest.mark.parametrize(
    ("action", "data", "permission_type"),
    [
        ("modify_metric", {"bk_biz_id": 2, "application_id": 1}, InstanceActionPermission),
        ("delete_application", {"bk_biz_id": 2, "app_name": "demo"}, InstanceActionForDataPermission),
        ("custom_service_config", {"bk_biz_id": 2, "app_name": "demo"}, InstanceActionForDataPermission),
    ],
)
def test_application_write_actions_require_manage_permission(action, data, permission_type):
    permissions = build_viewset(ApplicationViewSet, action, data).get_permissions()

    assert len(permissions) == 1
    assert isinstance(permissions[0], permission_type)
    assert permissions[0].actions == [ActionEnum.MANAGE_APM_APPLICATION]


def test_delete_custom_service_requires_manage_permission():
    permissions = build_viewset(
        ApplicationViewSet, "delete_custom_service", {"bk_biz_id": 2, "id": 1}
    ).get_permissions()

    assert len(permissions) == 1
    assert permissions[0].actions == [ActionEnum.MANAGE_APM_APPLICATION]


@mock.patch("bkmonitor.iam.drf.Permission")
@mock.patch("apm_web.meta.views.Application.objects")
@mock.patch("apm_web.meta.views.ApplicationCustomService.objects")
def test_delete_custom_service_permission_resolves_owning_application(
    custom_service_objects, application_objects, permission_mock
):
    custom_service_objects.only.return_value.filter.return_value.first.return_value = SimpleNamespace(
        bk_biz_id=2, app_name="demo"
    )
    application_objects.only.return_value.filter.return_value.first.return_value = SimpleNamespace(application_id=9)
    viewset = build_viewset(ApplicationViewSet, "delete_custom_service", {"bk_biz_id": 2, "id": 1})
    permission = viewset.get_permissions()[0]

    assert permission.has_permission(viewset.request, viewset) is True

    custom_service_objects.only.return_value.filter.assert_called_once_with(id=1, bk_biz_id=2)
    checked_resource = permission_mock.return_value.is_allowed.call_args[1]["resources"][0]
    assert str(checked_resource.id) == "9"


def test_service_config_requires_manage_permission():
    permissions = build_viewset(
        ServiceViewSet, "service_config", {"bk_biz_id": 2, "app_name": "demo"}
    ).get_permissions()

    assert len(permissions) == 1
    assert isinstance(permissions[0], InstanceActionForDataPermission)
    assert permissions[0].actions == [ActionEnum.MANAGE_APM_APPLICATION]
