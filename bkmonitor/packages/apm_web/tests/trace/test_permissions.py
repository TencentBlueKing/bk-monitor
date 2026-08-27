from unittest import mock

import pytest
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apm_web.trace.views import TraceQueryViewSet
from bkmonitor.iam.drf import InstanceActionForDataPermission, ViewBusinessPermission


def build_viewset(params, method="post"):
    factory = APIRequestFactory()
    if method == "get":
        raw_request = factory.get("/", params)
    else:
        raw_request = factory.post("/", params, format="json")
    viewset = TraceQueryViewSet()
    viewset.request = Request(raw_request)
    viewset.kwargs = {}
    return viewset


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"bk_biz_id": 2, "app_name": "demo"}, InstanceActionForDataPermission),
        ({"bk_biz_id": 2}, ViewBusinessPermission),
    ],
)
def test_trace_permissions_never_return_empty(params, expected):
    permissions = build_viewset(params).get_permissions()

    assert len(permissions) == 1
    assert isinstance(permissions[0], expected)


@pytest.mark.parametrize(
    "action",
    [
        "list_spans",
        "trace_statistics",
        "trace_diagram",
        "span_detail",
        "trace_list_by_id",
        "apply_trace_comparison",
        "delete_trace_comparison",
        "list_trace_comparison",
    ],
)
def test_previously_unguarded_trace_actions_are_guarded(action):
    viewset = build_viewset({"bk_biz_id": 2, "app_name": "demo"})
    viewset.action = action

    assert viewset.get_permissions()


@mock.patch("bkmonitor.iam.drf.Permission")
@mock.patch("apm_web.trace.views.Application.get_application_id_by_app_name", return_value=9)
def test_trace_permission_checks_resolved_application_resource(application_id_mock, permission_mock):
    viewset = build_viewset({"bk_biz_id": 2, "app_name": "demo"})
    permission = viewset.get_permissions()[0]

    assert permission.has_permission(viewset.request, viewset) is True

    application_id_mock.assert_called_once_with("demo")
    checked_resource = permission_mock.return_value.is_allowed.call_args[1]["resources"][0]
    assert str(checked_resource.id) == "9"
