from types import SimpleNamespace

from bkmonitor.utils.local import local
from monitor_web.data_migrate import bk_collector


def _application(bk_biz_id=2, app_name="demo"):
    return SimpleNamespace(bk_biz_id=bk_biz_id, app_name=app_name)


def _log_group(log_group_id=1, bk_biz_id=2, log_group_name="demo-log"):
    return SimpleNamespace(log_group_id=log_group_id, bk_biz_id=bk_biz_id, log_group_name=log_group_name)


def test_install_biz_bk_collector_dry_run_does_not_call_plugin_operate(monkeypatch):
    monkeypatch.setattr(bk_collector, "_find_latest_plugin_version", lambda **kwargs: "1.2.3")
    monkeypatch.setattr(
        bk_collector.BkCollectorConfig,
        "get_target_host_ids_by_biz_id",
        classmethod(lambda cls, bk_tenant_id, bk_biz_id: [101, 102]),
    )
    monkeypatch.setattr(
        bk_collector,
        "_get_deploy_host_ids",
        lambda **kwargs: ([101], [102]),
    )
    monkeypatch.setattr(
        bk_collector.api.node_man,
        "plugin_operate",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("dry-run should not install plugin")),
    )

    result = bk_collector.install_biz_bk_collector(
        bk_tenant_id="system", bk_biz_ids=[2], operator="admin", dry_run=True
    )

    assert result["plugin_version"] == "1.2.3"
    assert result["details"][bk_collector.INSTALL][0]["deploy_host_ids"] == [101]
    assert result["summary"][bk_collector.INSTALL]["planned_count"] == 1


def test_install_biz_bk_collector_skips_latest_and_installs_outdated_hosts(monkeypatch):
    calls = []

    monkeypatch.setattr(bk_collector, "_find_latest_plugin_version", lambda **kwargs: "1.2.3")
    monkeypatch.setattr(
        bk_collector.BkCollectorConfig,
        "get_target_host_ids_by_biz_id",
        classmethod(lambda cls, bk_tenant_id, bk_biz_id: [101, 102, 103]),
    )
    monkeypatch.setattr(
        bk_collector.api.node_man,
        "plugin_search",
        lambda **kwargs: {
            "list": [
                {"bk_host_id": 101, "plugin_status": [{"name": "bk-collector", "version": "1.2.3"}]},
                {"bk_host_id": 102, "plugin_status": [{"name": "bk-collector", "version": "1.0.0"}]},
            ]
        },
    )
    monkeypatch.setattr(
        bk_collector.api.node_man,
        "plugin_operate",
        lambda **kwargs: calls.append(kwargs),
    )

    result = bk_collector.install_biz_bk_collector(
        bk_tenant_id="system", bk_biz_ids=[2], operator="admin", dry_run=False
    )

    assert calls[0]["bk_host_id"] == [102, 103]
    assert calls[0]["plugin_params"] == {"name": "bk-collector", "version": "1.2.3"}
    assert result["details"][bk_collector.INSTALL][0]["skipped_host_ids"] == [101]
    assert result["summary"][bk_collector.INSTALL]["succeeded_count"] == 1


def test_refresh_biz_bk_collector_configs_refreshes_apm_application(monkeypatch):
    application_calls = []

    class FakeApplicationConfig:
        def __init__(self, application):
            self.application = application

        def refresh(self):
            application_calls.append((self.application.bk_biz_id, self.application.app_name))

    monkeypatch.setattr(bk_collector, "_list_apm_applications", lambda **kwargs: [_application()])
    monkeypatch.setattr(bk_collector, "ApplicationConfig", FakeApplicationConfig)

    application_result = bk_collector.refresh_biz_bk_collector_proxy_configs(
        bk_tenant_id="system",
        bk_biz_ids=[2],
        config_types=[bk_collector.APM_APPLICATION],
        operator="admin",
        dry_run=False,
    )

    assert application_calls == [(2, "demo")]
    assert list(application_result["details"].keys()) == [bk_collector.APM_APPLICATION]


def test_refresh_biz_bk_collector_configs_refreshes_custom_report_with_node_man_only_and_records_failures(
    monkeypatch,
):
    custom_report_calls = []
    log_calls = []

    def fake_refresh_custom_report(**kwargs):
        custom_report_calls.append(kwargs)

    def fake_refresh_log(log_group):
        log_calls.append(log_group.log_group_id)
        if log_group.log_group_id == 2:
            raise RuntimeError("log refresh failed")

    monkeypatch.setattr(
        bk_collector.CustomReportSubscription,
        "refresh_collector_custom_conf",
        fake_refresh_custom_report,
    )
    monkeypatch.setattr(bk_collector, "_list_log_groups", lambda **kwargs: [_log_group(1), _log_group(2)])
    monkeypatch.setattr(bk_collector.LogSubscriptionConfig, "refresh", fake_refresh_log)

    result = bk_collector.refresh_biz_bk_collector_proxy_configs(
        bk_tenant_id="system",
        bk_biz_ids=[2],
        config_types=[bk_collector.CUSTOM_REPORT, bk_collector.LOG],
        operator="admin",
        dry_run=False,
    )

    assert custom_report_calls == [{"bk_tenant_id": "system", "bk_biz_id": 2, "deploy_targets": ("node_man",)}]
    assert log_calls == [1, 2]
    assert result["summary"]["total"]["failed_count"] == 1
    assert result["details"][bk_collector.LOG][1]["message"] == "log refresh failed"


def test_refresh_biz_bk_collector_configs_dry_run_and_local_context_restore(monkeypatch):
    monkeypatch.setattr(
        bk_collector.CustomReportSubscription,
        "refresh_collector_custom_conf",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("dry-run should not refresh custom report")),
    )

    local.username = "origin"
    local.bk_tenant_id = "origin_tenant"
    result = bk_collector.refresh_biz_bk_collector_proxy_configs(
        bk_tenant_id="system",
        bk_biz_ids=[2],
        config_types=[bk_collector.CUSTOM_REPORT],
        operator="admin",
        dry_run=True,
    )

    assert result["details"][bk_collector.CUSTOM_REPORT][0]["action"] == "dry_run"
    assert result["summary"][bk_collector.CUSTOM_REPORT]["planned_count"] == 1
    assert local.username == "origin"
    assert local.bk_tenant_id == "origin_tenant"


def test_custom_report_refresh_deploy_targets_keep_default_and_allow_node_man_only(monkeypatch):
    from metadata.models.custom_report.subscription_config import CustomReportSubscription

    node_man_calls = []
    k8s_calls = []
    data_id_configs = {2: [({"bk_data_id": 2001}, "json")]}

    monkeypatch.setattr(
        CustomReportSubscription,
        "get_custom_event_config",
        classmethod(lambda cls, **kwargs: data_id_configs),
    )
    monkeypatch.setattr(
        CustomReportSubscription,
        "get_custom_time_series_config",
        classmethod(lambda cls, **kwargs: {}),
    )
    monkeypatch.setattr(
        CustomReportSubscription,
        "_refresh_collect_custom_config_by_biz",
        classmethod(lambda cls, **kwargs: node_man_calls.append(kwargs)),
    )
    monkeypatch.setattr(
        CustomReportSubscription,
        "_refresh_k8s_custom_config_by_biz",
        classmethod(lambda cls, **kwargs: k8s_calls.append(kwargs)),
    )

    CustomReportSubscription.refresh_collector_custom_conf(bk_tenant_id="system", bk_biz_id=2)

    assert [call["bk_biz_id"] for call in node_man_calls] == [2, 0]
    assert [call["bk_biz_id"] for call in k8s_calls] == [2, 0]

    node_man_calls.clear()
    k8s_calls.clear()
    CustomReportSubscription.refresh_collector_custom_conf(
        bk_tenant_id="system",
        bk_biz_id=2,
        deploy_targets=("node_man",),
    )

    assert [call["bk_biz_id"] for call in node_man_calls] == [2, 0]
    assert k8s_calls == []
