from unittest.mock import Mock, call

import pytest
from django.db.models import Q

from bk_monitor_base.metadata.models.space import Space
from bk_monitor_base.metadata.task import custom_report
from bk_monitor_base.metadata.task.tasks import refresh_custom_report_config
from bk_monitor_base.metadata.utils import tenant


@pytest.mark.parametrize(("input_id", "business_id"), [("2", 2), (0, 0), ("0", 0), ("-3", -3), (None, None)])
def test_refresh_task_routes_business_and_tenant(
    monkeypatch: pytest.MonkeyPatch, input_id: int | str | None, business_id: int | None
) -> None:
    monkeypatch.setattr(tenant.settings.blueking, "enable_multi_tenancy", True)
    monkeypatch.setattr(custom_report, "bk_biz_id_to_bk_tenant_id", tenant.bk_biz_id_to_bk_tenant_id.__wrapped__)
    get_space = Mock(return_value=Mock(bk_tenant_id="tenant-a"))
    monkeypatch.setattr(Space.objects, "get", get_space)
    list_tenants = Mock(return_value=[{"id": "tenant-a"}, {"id": "tenant-b"}])
    monkeypatch.setattr(custom_report, "list_tenant", list_tenants)
    monkeypatch.setattr(
        custom_report.api.node_man, "get_plugin_info", Mock(return_value=[Mock(is_ready=True, version="1.0.0")])
    )
    refresh = Mock()
    monkeypatch.setattr(custom_report.models.CustomReportSubscription, "refresh_collector_custom_conf", refresh)

    refresh_custom_report_config.run(bk_biz_id=input_id)

    if business_id is None:
        get_space.assert_not_called()
        list_tenants.assert_called_once_with()
        assert refresh.call_args_list == [call(bk_tenant_id=t, bk_biz_id=None) for t in ("tenant-a", "tenant-b")]
    else:
        expected_query = Q(space_type_id="bkcc", space_id=str(business_id)) if business_id >= 0 else Q(pk=-business_id)
        get_space.assert_called_once_with(expected_query)
        list_tenants.assert_not_called()
        refresh.assert_called_once_with(bk_tenant_id="tenant-a", bk_biz_id=business_id)
