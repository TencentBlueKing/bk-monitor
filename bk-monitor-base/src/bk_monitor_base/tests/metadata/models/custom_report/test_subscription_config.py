from unittest.mock import Mock

import pytest

from bk_monitor_base.metadata.models.custom_report.subscription_config import CustomReportSubscription


def test_refresh_custom_report_with_string_business_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """数字字符串形式的业务 ID 应将指标配置下发到业务及默认出口。"""
    configs = [({"bk_data_id": 2001}, "json")]
    monkeypatch.setattr(CustomReportSubscription, "get_custom_time_series_config", Mock(return_value={2: configs}))
    monkeypatch.setattr(CustomReportSubscription, "get_custom_event_config", Mock(return_value={}))
    node_man = Mock()
    k8s = Mock()
    monkeypatch.setattr(CustomReportSubscription, "_refresh_collect_custom_config_by_biz", node_man)
    monkeypatch.setattr(CustomReportSubscription, "_refresh_k8s_custom_config_by_biz", k8s)

    CustomReportSubscription.refresh_collector_custom_conf(bk_tenant_id="system", bk_biz_id="2")

    for target in (node_man, k8s):
        assert {call.kwargs["bk_biz_id"]: call.kwargs["data_id_configs"] for call in target.call_args_list} == {
            2: configs,
            0: configs,
        }
