from types import SimpleNamespace

import pytest
from rest_framework.exceptions import ValidationError

from bkmonitor.iam import ActionEnum
from monitor_web import permissions
from monitor_web.custom_report import views


@pytest.mark.parametrize(
    "view_class,action,method,permission_action",
    [
        (views.CustomEventReportViewSet, "query_custom_event_group", "GET", ActionEnum.VIEW_CUSTOM_EVENT),
        (views.CustomEventReportViewSet, "modify_custom_event_group", "POST", ActionEnum.MANAGE_CUSTOM_EVENT),
        (views.CustomMetricReportViewSet, "custom_time_series", "GET", ActionEnum.VIEW_CUSTOM_METRIC),
        (views.CustomMetricReportViewSet, "get_custom_ts_fields", "POST", ActionEnum.VIEW_CUSTOM_METRIC),
        (views.CustomMetricReportViewSet, "modify_custom_ts_fields", "POST", ActionEnum.MANAGE_CUSTOM_METRIC),
    ],
)
@pytest.mark.parametrize("biz_id", [None, 0, "0", 2, -2])
def test_business_context_required_even_for_platform_data(
    monkeypatch, view_class, action, method, permission_action, biz_id
):
    monkeypatch.setattr(permissions, "is_biz_in_tenant", lambda *_: True)
    view = view_class()
    view.action = action
    view.request = SimpleNamespace(
        biz_id=biz_id,
        method=method,
        user=SimpleNamespace(tenant_id="tenant-a"),
        query_params={"is_platform": True, "table_id": "platform.events"},
    )

    if biz_id in (None, 0, "0"):
        with pytest.raises(ValidationError):
            view.get_permissions()
    else:
        assert view.get_permissions()[0].actions == [permission_action]


def test_proxy_host_info_keeps_its_independent_contract():
    view = views.CustomEventReportViewSet()
    view.action = "proxy_host_info"
    view.request = SimpleNamespace(biz_id=None, method="GET")
    assert view.get_permissions() == []
