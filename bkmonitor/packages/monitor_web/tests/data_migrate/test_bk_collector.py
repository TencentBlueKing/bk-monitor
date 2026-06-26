from types import SimpleNamespace

from bkmonitor.utils.local import local
from monitor_web.data_migrate import bk_collector


def _application(bk_biz_id=2, app_name="demo"):
    return SimpleNamespace(bk_biz_id=bk_biz_id, app_name=app_name)


def _log_group(log_group_id=1, bk_biz_id=2, log_group_name="demo-log"):
    return SimpleNamespace(log_group_id=log_group_id, bk_biz_id=bk_biz_id, log_group_name=log_group_name)


class FakeEmptyQuerySet(list):
    def values(self, *fields):
        return self

    def order_by(self, *fields):
        return self


def _patch_new_env_scope_sync(monkeypatch):
    calls = []

    def fake_sync(**kwargs):
        calls.append(kwargs)
        return {
            "config_key": kwargs["config_key"],
            "bk_biz_ids": kwargs["bk_biz_ids"],
            "action": "dry_run" if kwargs["dry_run"] else bk_collector.UPDATE,
            "result": None if kwargs["dry_run"] else True,
            "message": "success",
        }

    monkeypatch.setattr(bk_collector, "_sync_new_env_biz_scope_config", fake_sync)
    return calls


def _plugin_job_detail(job_id=123, status="SUCCESS", instance_status="SUCCESS"):
    return {
        "job_id": job_id,
        "job_type": "MAIN_INSTALL_PLUGIN",
        "status": status,
        "start_time": "2026-06-25 18:09:19 +0800",
        "end_time": "2026-06-25 18:10:14 +0800" if status == "SUCCESS" else None,
        "cost_time": "54",
        "statistics": {
            "total_count": 1,
            "failed_count": 0 if instance_status in {"SUCCESS", "RUNNING"} else 1,
            "ignored_count": 0,
            "pending_count": 0,
            "running_count": 1 if instance_status == "RUNNING" else 0,
            "success_count": 1 if instance_status == "SUCCESS" else 0,
        },
        "list": [
            {
                "instance_id": "host|instance|host|101",
                "ip": "127.0.0.1",
                "inner_ip": "127.0.0.1",
                "bk_host_id": 101,
                "bk_cloud_id": 1,
                "bk_biz_id": 2,
                "status": instance_status,
                "status_display": "执行成功" if instance_status == "SUCCESS" else "等待执行",
                "op_type": "INSTALL",
                "step": "重置重试次数",
            }
        ],
    }


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


def test_install_biz_bk_collector_temporarily_switches_and_restores_nodeman_api(settings, monkeypatch):
    seen_base_urls = []

    settings.ENABLE_MULTI_TENANT_MODE = False
    settings.BK_COMPONENT_API_URL = "https://component.example.com"
    settings.BKNODEMAN_API_BASE_URL = "https://old.example.com/api/c/compapi/v2/nodeman/"

    def fake_find_latest_plugin_version(**kwargs):
        seen_base_urls.append(settings.BKNODEMAN_API_BASE_URL)
        return "1.2.3"

    monkeypatch.setattr(bk_collector, "_find_latest_plugin_version", fake_find_latest_plugin_version)
    monkeypatch.setattr(
        bk_collector.BkCollectorConfig,
        "get_target_host_ids_by_biz_id",
        classmethod(lambda cls, bk_tenant_id, bk_biz_id: []),
    )

    bk_collector.install_biz_bk_collector(bk_tenant_id="system", bk_biz_ids=[2], operator="admin", dry_run=True)

    assert seen_base_urls == ["https://component.example.com/api/bk-nodeman/prod/"]
    assert settings.BKNODEMAN_API_BASE_URL == "https://old.example.com/api/c/compapi/v2/nodeman/"


def test_install_biz_bk_collector_reinstalls_all_proxy_hosts(monkeypatch):
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
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("install should not skip hosts by current version")),
    )
    monkeypatch.setattr(
        bk_collector.api.node_man,
        "plugin_operate",
        lambda **kwargs: calls.append(kwargs) or {"job_id": 123},
    )
    monkeypatch.setattr(
        bk_collector.api.node_man,
        "job_detail",
        lambda **kwargs: _plugin_job_detail(job_id=kwargs["id"], status="SUCCESS", instance_status="SUCCESS"),
    )

    result = bk_collector.install_biz_bk_collector(
        bk_tenant_id="system", bk_biz_ids=[2], operator="admin", dry_run=False
    )

    assert calls[0]["bk_host_id"] == [101, 102, 103]
    assert calls[0]["plugin_params"] == {"name": "bk-collector", "version": "1.2.3"}
    assert calls[0]["job_type"] == "MAIN_INSTALL_PLUGIN"
    install_detail = result["details"][bk_collector.INSTALL][0]
    assert install_detail["skipped_host_ids"] == []
    assert install_detail["operate_result"] == {"job_id": 123}
    assert install_detail["job_status"]["status"] == "SUCCESS"
    assert install_detail["job_status"]["instances"][0]["status"] == "SUCCESS"
    assert result["summary"][bk_collector.INSTALL]["succeeded_count"] == 1


def test_install_biz_bk_collector_reports_failed_hosts_in_failure_summary(monkeypatch):
    monkeypatch.setattr(bk_collector, "_find_latest_plugin_version", lambda **kwargs: "1.2.3")
    monkeypatch.setattr(
        bk_collector.BkCollectorConfig,
        "get_target_host_ids_by_biz_id",
        classmethod(lambda cls, bk_tenant_id, bk_biz_id: [101]),
    )
    monkeypatch.setattr(
        bk_collector.api.node_man,
        "plugin_search",
        lambda **kwargs: {"list": [{"bk_host_id": 101, "plugin_status": []}]},
    )
    monkeypatch.setattr(bk_collector.api.node_man, "plugin_operate", lambda **kwargs: {"job_id": 123})
    monkeypatch.setattr(
        bk_collector.api.node_man,
        "job_detail",
        lambda **kwargs: _plugin_job_detail(job_id=kwargs["id"], status="FAILED", instance_status="FAILED"),
    )

    result = bk_collector.install_biz_bk_collector(
        bk_tenant_id="system", bk_biz_ids=[2], operator="admin", dry_run=False
    )

    failure_summary = result["failure_summary"]
    assert failure_summary["record_count"] == 1
    assert failure_summary["host_count"] == 1
    failure_record = failure_summary["records"][0]
    assert failure_record["bk_biz_id"] == 2
    assert failure_record["operation_host_ids"] == [101]
    assert failure_record["job_id"] == 123
    assert failure_record["job_status"] == "FAILED"
    assert failure_record["hosts"][0]["bk_host_id"] == 101
    assert failure_record["hosts"][0]["status"] == "FAILED"


def test_disable_biz_bk_collector_subscription_auto_inspection_disables_subscriptions_and_blacklists(monkeypatch):
    switch_calls = []
    sync_calls = _patch_new_env_scope_sync(monkeypatch)

    def fake_list_subscriptions(**kwargs):
        assert kwargs["config_types"] == bk_collector.CONFIG_TYPES
        return [
            {
                "config_type": bk_collector.APM_APPLICATION,
                "bk_tenant_id": "tencent",
                "bk_biz_id": 2,
                "subscription_id": 1001,
                "name": "demo-apm",
            },
            {
                "config_type": bk_collector.CUSTOM_REPORT,
                "bk_tenant_id": "tencent",
                "bk_biz_id": 2,
                "subscription_id": 1002,
                "bk_data_id": 2001,
            },
            {
                "config_type": bk_collector.LOG,
                "bk_tenant_id": "tencent",
                "bk_biz_id": 2,
                "subscription_id": 1003,
                "name": "demo-log",
            },
        ]

    monkeypatch.setattr(bk_collector, "_list_proxy_config_delivery_subscriptions", fake_list_subscriptions)
    monkeypatch.setattr(
        bk_collector.api.node_man,
        "switch_subscription",
        lambda **kwargs: switch_calls.append(kwargs) or {"result": True},
    )

    result = bk_collector.disable_biz_bk_collector_subscription_auto_inspection(
        bk_tenant_id="tencent",
        bk_biz_ids=[2],
        operator="admin",
        dry_run=False,
    )

    assert [call["subscription_id"] for call in switch_calls] == [1001, 1002, 1003]
    assert {call["action"] for call in switch_calls} == {"disable"}
    assert result["details"][bk_collector.APM_APPLICATION][0]["action"] == bk_collector.DISABLE_AUTO_INSPECTION
    assert result["details"][bk_collector.CUSTOM_REPORT][0]["switch_result"] == {"result": True}
    assert result["summary"]["total"]["succeeded_count"] == 4
    assert sync_calls[0]["config_key"] == bk_collector.NEW_ENV_BIZ_BLACK_LIST_CONFIG_KEY
    assert sync_calls[0]["bk_biz_ids"] == [2]
    assert sync_calls[0]["remove_config_keys"] == (bk_collector.NEW_ENV_BIZ_WHITE_LIST_CONFIG_KEY,)


def test_disable_biz_bk_collector_subscription_auto_inspection_does_not_switch_nodeman_api(monkeypatch):
    _patch_new_env_scope_sync(monkeypatch)
    monkeypatch.setattr(
        bk_collector,
        "_set_nodeman_api",
        lambda: (_ for _ in ()).throw(AssertionError("disable subscription checks should not switch nodeman api")),
    )
    monkeypatch.setattr(bk_collector, "_list_proxy_config_delivery_subscriptions", lambda **kwargs: [])

    result = bk_collector.disable_biz_bk_collector_subscription_auto_inspection(
        bk_tenant_id="tencent",
        bk_biz_ids=[2],
        operator="admin",
        dry_run=False,
    )

    assert result["summary"][bk_collector.NEW_ENV_BLACK_LIST]["succeeded_count"] == 1


def test_check_biz_bk_collector_proxy_config_delivery_does_not_switch_nodeman_api(monkeypatch):
    monkeypatch.setattr(
        bk_collector,
        "_set_nodeman_api",
        lambda: (_ for _ in ()).throw(AssertionError("delivery check should not switch nodeman api")),
    )
    monkeypatch.setattr(bk_collector, "_list_proxy_config_delivery_subscriptions", lambda **kwargs: [])

    result = bk_collector.check_biz_bk_collector_proxy_config_delivery(
        bk_tenant_id="tencent",
        bk_biz_ids=[2],
        config_types=[bk_collector.CUSTOM_REPORT],
        operator="admin",
    )

    assert result["message"] == "no matched bk-collector proxy config subscription"


def test_list_proxy_config_delivery_subscriptions_only_queries_requested_biz(monkeypatch):
    filter_biz_ids = []

    class FakeObjects:
        def filter(self, **kwargs):
            filter_biz_ids.append(kwargs["bk_biz_id__in"])
            return FakeEmptyQuerySet()

    monkeypatch.setattr(bk_collector, "SubscriptionConfig", SimpleNamespace(objects=FakeObjects()))
    monkeypatch.setattr(bk_collector, "CustomReportSubscription", SimpleNamespace(objects=FakeObjects()))
    monkeypatch.setattr(bk_collector, "LogSubscriptionConfig", SimpleNamespace(objects=FakeObjects()))

    result = bk_collector._list_proxy_config_delivery_subscriptions(
        bk_tenant_id="tencent",
        bk_biz_ids=[19078],
        config_types=bk_collector.CONFIG_TYPES,
    )

    assert result == []
    assert filter_biz_ids == [[19078], [19078], [19078]]


def test_sync_new_env_biz_scope_config_updates_global_config_and_removes_opposite_list(monkeypatch, settings):
    stored_configs = {
        bk_collector.NEW_ENV_BIZ_BLACK_LIST_CONFIG_KEY: [1, "2"],
        bk_collector.NEW_ENV_BIZ_WHITE_LIST_CONFIG_KEY: [2, 3],
    }
    set_calls = []

    monkeypatch.setattr(
        bk_collector.GlobalConfig,
        "get",
        staticmethod(lambda key, defaults=None: stored_configs.get(key, defaults)),
    )
    monkeypatch.setattr(
        bk_collector.GlobalConfig,
        "set",
        staticmethod(lambda key, value: set_calls.append((key, value)) or stored_configs.update({key: value})),
    )
    settings.NEW_ENV_BIZ_BLACK_LIST = [1, 2]
    settings.NEW_ENV_BIZ_WHITE_LIST = [2, 3]

    result = bk_collector._sync_new_env_biz_scope_config(
        config_key=bk_collector.NEW_ENV_BIZ_BLACK_LIST_CONFIG_KEY,
        bk_biz_ids=[2, 4],
        dry_run=False,
        remove_config_keys=(bk_collector.NEW_ENV_BIZ_WHITE_LIST_CONFIG_KEY,),
        empty_message="empty",
    )

    assert result["action"] == bk_collector.UPDATE
    assert set_calls == [
        (bk_collector.NEW_ENV_BIZ_BLACK_LIST_CONFIG_KEY, [1, 2, 4]),
        (bk_collector.NEW_ENV_BIZ_WHITE_LIST_CONFIG_KEY, [3]),
    ]
    assert settings.NEW_ENV_BIZ_BLACK_LIST == [1, 2, 4]
    assert settings.NEW_ENV_BIZ_WHITE_LIST == [3]


def test_stop_biz_bk_collector_dry_run_only_stops_installed_hosts(monkeypatch):
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
                {"bk_host_id": 102, "plugin_status": [{"name": "bkmonitorbeat", "version": "1.0.0"}]},
            ]
        },
    )
    monkeypatch.setattr(
        bk_collector.api.node_man,
        "plugin_operate",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("dry-run should not stop plugin")),
    )

    result = bk_collector.stop_biz_bk_collector(bk_tenant_id="system", bk_biz_ids=[2], operator="admin", dry_run=True)

    stop_detail = result["details"][bk_collector.STOP][0]
    assert stop_detail["stop_host_ids"] == [101]
    assert stop_detail["skipped_host_ids"] == [102, 103]
    assert result["summary"][bk_collector.STOP]["planned_count"] == 1


def test_stop_biz_bk_collector_temporarily_switches_and_restores_nodeman_api(settings, monkeypatch):
    seen_base_urls = []

    settings.ENABLE_MULTI_TENANT_MODE = False
    settings.BK_COMPONENT_API_URL = "https://component.example.com"
    settings.BKNODEMAN_API_BASE_URL = "https://old.example.com/api/c/compapi/v2/nodeman/"

    def fake_get_target_host_ids_by_biz_id(cls, bk_tenant_id, bk_biz_id):
        seen_base_urls.append(settings.BKNODEMAN_API_BASE_URL)
        return []

    monkeypatch.setattr(
        bk_collector.BkCollectorConfig,
        "get_target_host_ids_by_biz_id",
        classmethod(fake_get_target_host_ids_by_biz_id),
    )

    bk_collector.stop_biz_bk_collector(bk_tenant_id="system", bk_biz_ids=[2], operator="admin", dry_run=True)

    assert seen_base_urls == ["https://component.example.com/api/bk-nodeman/prod/"]
    assert settings.BKNODEMAN_API_BASE_URL == "https://old.example.com/api/c/compapi/v2/nodeman/"


def test_stop_biz_bk_collector_calls_main_stop_plugin(monkeypatch):
    calls = []

    monkeypatch.setattr(
        bk_collector.BkCollectorConfig,
        "get_target_host_ids_by_biz_id",
        classmethod(lambda cls, bk_tenant_id, bk_biz_id: [101]),
    )
    monkeypatch.setattr(
        bk_collector.api.node_man,
        "plugin_search",
        lambda **kwargs: {
            "list": [{"bk_host_id": 101, "plugin_status": [{"name": "bk-collector", "version": "1.2.3"}]}]
        },
    )
    monkeypatch.setattr(
        bk_collector.api.node_man,
        "plugin_operate",
        lambda **kwargs: calls.append(kwargs) or {"job_id": 456},
    )
    monkeypatch.setattr(
        bk_collector.api.node_man,
        "job_detail",
        lambda **kwargs: _plugin_job_detail(job_id=kwargs["id"], status="SUCCESS", instance_status="SUCCESS"),
    )

    result = bk_collector.stop_biz_bk_collector(bk_tenant_id="system", bk_biz_ids=[2], operator="admin", dry_run=False)

    assert calls == [
        {
            "bk_tenant_id": "system",
            "plugin_params": {"name": "bk-collector"},
            "job_type": "MAIN_STOP_PLUGIN",
            "bk_host_id": [101],
        }
    ]
    assert result["details"][bk_collector.STOP][0]["operate_result"] == {"job_id": 456}
    assert result["details"][bk_collector.STOP][0]["job_status"]["status"] == "SUCCESS"
    assert result["summary"][bk_collector.STOP]["succeeded_count"] == 1


def test_install_biz_bk_collector_polls_job_until_success(monkeypatch):
    job_details = [
        _plugin_job_detail(job_id=123, status="RUNNING", instance_status="RUNNING"),
        _plugin_job_detail(job_id=123, status="SUCCESS", instance_status="SUCCESS"),
    ]
    sleep_calls = []

    monkeypatch.setattr(bk_collector, "_find_latest_plugin_version", lambda **kwargs: "1.2.3")
    monkeypatch.setattr(
        bk_collector.BkCollectorConfig,
        "get_target_host_ids_by_biz_id",
        classmethod(lambda cls, bk_tenant_id, bk_biz_id: [101]),
    )
    monkeypatch.setattr(
        bk_collector.api.node_man,
        "plugin_search",
        lambda **kwargs: {"list": [{"bk_host_id": 101, "plugin_status": []}]},
    )
    monkeypatch.setattr(bk_collector.api.node_man, "plugin_operate", lambda **kwargs: {"job_id": 123})
    monkeypatch.setattr(bk_collector.api.node_man, "job_detail", lambda **kwargs: job_details.pop(0))
    monkeypatch.setattr(bk_collector.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    result = bk_collector.install_biz_bk_collector(
        bk_tenant_id="system",
        bk_biz_ids=[2],
        operator="admin",
        dry_run=False,
        job_wait_timeout=10,
        job_poll_interval=1,
    )

    install_detail = result["details"][bk_collector.INSTALL][0]
    assert install_detail["result"] is True
    assert install_detail["job_status"]["poll_attempts"] == 2
    assert install_detail["job_status"]["timed_out"] is False
    assert sleep_calls == [1]
    assert result["summary"][bk_collector.INSTALL]["succeeded_count"] == 1


def test_stop_biz_bk_collector_reports_running_job_as_timeout(monkeypatch):
    monkeypatch.setattr(
        bk_collector.BkCollectorConfig,
        "get_target_host_ids_by_biz_id",
        classmethod(lambda cls, bk_tenant_id, bk_biz_id: [101]),
    )
    monkeypatch.setattr(
        bk_collector.api.node_man,
        "plugin_search",
        lambda **kwargs: {
            "list": [{"bk_host_id": 101, "plugin_status": [{"name": "bk-collector", "version": "1.2.3"}]}]
        },
    )
    monkeypatch.setattr(bk_collector.api.node_man, "plugin_operate", lambda **kwargs: {"job_id": 456})
    monkeypatch.setattr(
        bk_collector.api.node_man,
        "job_detail",
        lambda **kwargs: _plugin_job_detail(job_id=kwargs["id"], status="RUNNING", instance_status="RUNNING"),
    )

    result = bk_collector.stop_biz_bk_collector(
        bk_tenant_id="system",
        bk_biz_ids=[2],
        operator="admin",
        dry_run=False,
        job_wait_timeout=0,
        job_poll_interval=0,
    )

    stop_detail = result["details"][bk_collector.STOP][0]
    assert stop_detail["result"] is False
    assert stop_detail["message"] == "nodeman job wait timeout, last status: RUNNING"
    assert stop_detail["job_status"]["status"] == "TIMEOUT"
    assert stop_detail["job_status"]["last_status"] == "RUNNING"
    assert stop_detail["job_status"]["timed_out"] is True
    assert stop_detail["job_status"]["statistics"]["pending_count"] == 1
    assert result["summary"][bk_collector.STOP]["timeout_count"] == 1
    assert result["summary"][bk_collector.STOP]["failed_count"] == 1
    assert result["summary"][bk_collector.STOP]["pending_count"] == 0
    assert result["summary"][bk_collector.STOP]["succeeded_count"] == 0
    failure_summary = result["failure_summary"]
    assert failure_summary["record_count"] == 1
    assert failure_summary["host_count"] == 1
    assert failure_summary["records"][0]["timed_out"] is True
    assert failure_summary["records"][0]["operation_host_ids"] == [101]
    assert failure_summary["records"][0]["hosts"][0]["status"] == "RUNNING"


def _proxy_config_delivery_task(render_status="SUCCESS", instance_status="FAILED"):
    return {
        "instance_id": "host|instance|host|101",
        "status": instance_status,
        "instance_info": {
            "host": {
                "bk_biz_id": 2,
                "bk_host_id": 101,
                "bk_cloud_id": 1,
                "bk_host_innerip": "127.0.0.1",
            },
        },
        "last_task": {
            "status": instance_status,
            "steps": [
                {
                    "id": "bk-collector",
                    "status": instance_status,
                    "target_hosts": [
                        {
                            "status": instance_status,
                            "sub_steps": [
                                {
                                    "step_code": "render_and_push_config",
                                    "status": render_status,
                                    "pipeline_id": "pipeline-id",
                                },
                                {"step_code": "gse_operate_proc", "status": instance_status},
                            ],
                        }
                    ],
                }
            ],
        },
    }


def test_check_biz_bk_collector_proxy_config_delivery_uses_render_step_success(monkeypatch):
    monkeypatch.setattr(
        bk_collector,
        "_list_proxy_config_delivery_subscriptions",
        lambda **kwargs: [
            {
                "config_type": bk_collector.CUSTOM_REPORT,
                "bk_tenant_id": "system",
                "bk_biz_id": 2,
                "subscription_id": 1001,
                "bk_data_id": 2001,
            }
        ],
    )
    monkeypatch.setattr(
        bk_collector.api.node_man,
        "batch_task_result",
        lambda **kwargs: [_proxy_config_delivery_task(render_status="SUCCESS", instance_status="FAILED")],
    )

    result = bk_collector.check_biz_bk_collector_proxy_config_delivery(
        bk_tenant_id="system",
        bk_biz_ids=[2],
        config_types=[bk_collector.CUSTOM_REPORT],
    )

    assert result["result"] is True
    assert result["summary"]["total"]["succeeded_count"] == 1
    assert result["summary"]["total"]["failed_count"] == 0
    instance = result["details"][bk_collector.CUSTOM_REPORT][0]["instances"][0]
    assert instance["status"] == "SUCCESS"
    assert instance["render_steps"][0]["status"] == "SUCCESS"


def test_check_biz_bk_collector_proxy_config_delivery_reports_render_failure(monkeypatch):
    monkeypatch.setattr(
        bk_collector,
        "_list_proxy_config_delivery_subscriptions",
        lambda **kwargs: [
            {
                "config_type": bk_collector.CUSTOM_REPORT,
                "bk_tenant_id": "system",
                "bk_biz_id": 2,
                "subscription_id": 1001,
                "bk_data_id": 2001,
            }
        ],
    )
    monkeypatch.setattr(
        bk_collector.api.node_man,
        "batch_task_result",
        lambda **kwargs: [_proxy_config_delivery_task(render_status="FAILED", instance_status="FAILED")],
    )

    result = bk_collector.check_biz_bk_collector_proxy_config_delivery(
        bk_tenant_id="system",
        bk_biz_ids=[2],
        config_types=[bk_collector.CUSTOM_REPORT],
    )

    assert result["result"] is False
    assert result["summary"]["total"]["failed_count"] == 1
    assert (
        result["details"][bk_collector.CUSTOM_REPORT][0]["instances"][0]["message"] == "render_and_push_config failed"
    )


def test_check_biz_bk_collector_proxy_config_delivery_waits_until_render_success(monkeypatch):
    task_results = [
        [_proxy_config_delivery_task(render_status="RUNNING", instance_status="RUNNING")],
        [_proxy_config_delivery_task(render_status="SUCCESS", instance_status="FAILED")],
    ]
    sleep_calls = []

    monkeypatch.setattr(
        bk_collector,
        "_list_proxy_config_delivery_subscriptions",
        lambda **kwargs: [
            {
                "config_type": bk_collector.CUSTOM_REPORT,
                "bk_tenant_id": "system",
                "bk_biz_id": 2,
                "subscription_id": 1001,
                "bk_data_id": 2001,
            }
        ],
    )
    monkeypatch.setattr(bk_collector.api.node_man, "batch_task_result", lambda **kwargs: task_results.pop(0))
    monkeypatch.setattr(bk_collector.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    result = bk_collector.check_biz_bk_collector_proxy_config_delivery(
        bk_tenant_id="system",
        bk_biz_ids=[2],
        config_types=[bk_collector.CUSTOM_REPORT],
        wait_timeout=10,
        poll_interval=1,
    )

    assert result["result"] is True
    assert result["poll_attempts"] == 2
    assert result["timed_out"] is False
    assert sleep_calls == [1]


def test_refresh_biz_bk_collector_configs_checks_delivery_after_refresh(monkeypatch):
    custom_report_calls = []
    delivery_check_calls = []

    def fake_refresh_custom_report(**kwargs):
        custom_report_calls.append(kwargs)
        return {"summary": {"failed_count": 0}, "details": []}

    def fake_check_delivery(**kwargs):
        delivery_check_calls.append(kwargs)
        return {"result": True, "summary": {"total": {"failed_count": 0}}, "message": "success"}

    monkeypatch.setattr(
        bk_collector.CustomReportSubscription,
        "refresh_collector_custom_conf",
        fake_refresh_custom_report,
    )
    monkeypatch.setattr(bk_collector, "check_biz_bk_collector_proxy_config_delivery", fake_check_delivery)

    result = bk_collector.refresh_biz_bk_collector_proxy_configs(
        bk_tenant_id="system",
        bk_biz_ids=[2],
        config_types=[bk_collector.CUSTOM_REPORT],
        operator="admin",
        dry_run=False,
        delivery_wait_timeout=30,
        delivery_poll_interval=2,
    )

    assert custom_report_calls == [
        {"bk_tenant_id": "system", "bk_biz_id": 2, "deploy_targets": ("node_man",), "dry_run": False}
    ]
    assert delivery_check_calls == [
        {
            "bk_tenant_id": "system",
            "bk_biz_ids": [2],
            "config_types": (bk_collector.CUSTOM_REPORT,),
            "operator": "admin",
            "wait_timeout": 30,
            "poll_interval": 2,
        }
    ]
    assert result["delivery_check"]["result"] is True
    assert result["result"] is True
    assert "details" not in result


def test_refresh_biz_bk_collector_configs_drops_delivery_check_details_by_default(monkeypatch):
    monkeypatch.setattr(
        bk_collector.CustomReportSubscription,
        "refresh_collector_custom_conf",
        lambda **kwargs: {"summary": {"failed_count": 0}, "details": []},
    )
    monkeypatch.setattr(
        bk_collector,
        "check_biz_bk_collector_proxy_config_delivery",
        lambda **kwargs: {
            "result": True,
            "summary": {"total": {"failed_count": 0}},
            "message": "success",
            "details": {bk_collector.CUSTOM_REPORT: [{"subscription_id": 1001}]},
        },
    )

    result = bk_collector.refresh_biz_bk_collector_proxy_configs(
        bk_tenant_id="system",
        bk_biz_ids=[2],
        config_types=[bk_collector.CUSTOM_REPORT],
    )

    assert "details" not in result
    assert "details" not in result["delivery_check"]


def test_refresh_biz_bk_collector_configs_keeps_failure_summary_without_details(monkeypatch):
    monkeypatch.setattr(
        bk_collector.CustomReportSubscription,
        "refresh_collector_custom_conf",
        lambda **kwargs: {"summary": {"failed_count": 0}, "details": []},
    )
    monkeypatch.setattr(
        bk_collector,
        "_list_proxy_config_delivery_subscriptions",
        lambda **kwargs: [
            {
                "config_type": bk_collector.CUSTOM_REPORT,
                "bk_tenant_id": "system",
                "bk_biz_id": 2,
                "subscription_id": 1001,
                "bk_data_id": 2001,
            }
        ],
    )
    monkeypatch.setattr(
        bk_collector.api.node_man,
        "batch_task_result",
        lambda **kwargs: [_proxy_config_delivery_task(render_status="FAILED", instance_status="FAILED")],
    )

    result = bk_collector.refresh_biz_bk_collector_proxy_configs(
        bk_tenant_id="system",
        bk_biz_ids=[2],
        config_types=[bk_collector.CUSTOM_REPORT],
    )

    assert result["result"] is False
    assert "details" not in result
    assert "details" not in result["delivery_check"]
    failure_summary = result["delivery_check"]["failure_summary"]
    assert failure_summary["subscription_count"] == 1
    assert failure_summary["proxy_count"] == 1
    subscription = failure_summary["subscriptions"][0]
    assert subscription["subscription_id"] == 1001
    assert subscription["bk_data_id"] == 2001
    assert subscription["hosts"] == [
        {
            "instance_id": "host|instance|host|101",
            "bk_host_id": 101,
            "bk_cloud_id": 1,
            "ip": "127.0.0.1",
            "status": "FAILED",
            "message": "render_and_push_config failed",
            "render_step_statuses": ["FAILED"],
        }
    ]


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
        check_delivery=False,
        include_details=True,
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
        return {
            "summary": {"failed_count": 0},
            "details": [
                {
                    "bk_biz_id": 2,
                    "data_ids": [2001],
                    "targets": {"node_man": {"action": "refresh", "result": True, "message": "success"}},
                }
            ],
        }

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
        check_delivery=False,
        include_details=True,
    )

    assert custom_report_calls == [
        {"bk_tenant_id": "system", "bk_biz_id": 2, "deploy_targets": ("node_man",), "dry_run": False}
    ]
    custom_report_detail = result["details"][bk_collector.CUSTOM_REPORT][0]
    assert custom_report_detail["refresh_result"]["details"][0]["data_ids"] == [2001]
    assert log_calls == [1, 2]
    assert result["summary"]["total"]["failed_count"] == 1
    assert result["details"][bk_collector.LOG][1]["message"] == "log refresh failed"


def test_refresh_biz_bk_collector_configs_dry_run_and_local_context_restore(monkeypatch):
    custom_report_calls = []

    def fake_refresh_custom_report(**kwargs):
        custom_report_calls.append(kwargs)
        return {
            "dry_run": True,
            "summary": {"failed_count": 0},
            "details": [
                {
                    "bk_biz_id": 2,
                    "data_ids": [2001],
                    "targets": {"node_man": {"action": "dry_run", "result": None}},
                }
            ],
        }

    monkeypatch.setattr(
        bk_collector.CustomReportSubscription, "refresh_collector_custom_conf", fake_refresh_custom_report
    )

    local.username = "origin"
    local.bk_tenant_id = "origin_tenant"
    result = bk_collector.refresh_biz_bk_collector_proxy_configs(
        bk_tenant_id="system",
        bk_biz_ids=[2],
        config_types=[bk_collector.CUSTOM_REPORT],
        operator="admin",
        dry_run=True,
        check_delivery=False,
        include_details=True,
    )

    assert result["details"][bk_collector.CUSTOM_REPORT][0]["action"] == "dry_run"
    assert custom_report_calls == [
        {"bk_tenant_id": "system", "bk_biz_id": 2, "deploy_targets": ("node_man",), "dry_run": True}
    ]
    assert result["details"][bk_collector.CUSTOM_REPORT][0]["refresh_result"]["details"][0]["data_ids"] == [2001]
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
        classmethod(
            lambda cls, **kwargs: node_man_calls.append(kwargs)
            or {
                "action": "dry_run" if kwargs.get("dry_run") else "refresh",
                "result": None if kwargs.get("dry_run") else True,
                "message": "success",
                "proxy_host_ids": [101],
                "proxy_hosts": [
                    {"bk_host_id": 101, "bk_biz_id": kwargs["bk_biz_id"], "bk_cloud_id": 1, "ip": "127.0.0.1"}
                ],
                "proxy_count": 1,
            }
        ),
    )
    monkeypatch.setattr(
        CustomReportSubscription,
        "_refresh_k8s_custom_config_by_biz",
        classmethod(lambda cls, **kwargs: k8s_calls.append(kwargs)),
    )

    result = CustomReportSubscription.refresh_collector_custom_conf(bk_tenant_id="system", bk_biz_id=2)

    assert [call["bk_biz_id"] for call in node_man_calls] == [2, 0]
    assert [call["bk_biz_id"] for call in k8s_calls] == [2, 0]
    assert result["summary"] == {
        "matched_biz_count": 2,
        "data_id_count": 2,
        "target_count": 4,
        "planned_count": 0,
        "succeeded_count": 4,
        "skipped_count": 0,
        "failed_count": 0,
    }
    assert result["details"][0]["data_ids"] == [2001]
    assert result["details"][0]["targets"]["node_man"]["proxy_host_ids"] == [101]

    node_man_calls.clear()
    k8s_calls.clear()
    result = CustomReportSubscription.refresh_collector_custom_conf(
        bk_tenant_id="system",
        bk_biz_id=2,
        deploy_targets=("node_man",),
    )

    assert [call["bk_biz_id"] for call in node_man_calls] == [2, 0]
    assert k8s_calls == []
    assert result["summary"]["target_count"] == 2

    node_man_calls.clear()
    result = CustomReportSubscription.refresh_collector_custom_conf(
        bk_tenant_id="system",
        bk_biz_id=2,
        deploy_targets=("node_man",),
        dry_run=True,
    )

    assert [call["bk_biz_id"] for call in node_man_calls] == [2, 0]
    assert all(call["dry_run"] is True for call in node_man_calls)
    assert result["dry_run"] is True
    assert result["summary"]["planned_count"] == 2
    assert result["details"][0]["targets"]["node_man"]["action"] == "dry_run"


def test_custom_report_refresh_keeps_biz_zero_when_filters_skip_biz(monkeypatch):
    from metadata.models.custom_report import subscription_config
    from metadata.models.custom_report.subscription_config import CustomReportSubscription

    node_man_calls = []
    k8s_calls = []

    monkeypatch.setattr(subscription_config.settings, "NEW_ENV_START_BIZ_ID", "10", raising=False)
    monkeypatch.setattr(subscription_config.settings, "NEW_ENV_BIZ_BLACK_LIST", [2, 0], raising=False)
    monkeypatch.setattr(subscription_config.settings, "NEW_ENV_BIZ_WHITE_LIST", [], raising=False)
    monkeypatch.setattr(
        subscription_config.api.cmdb,
        "get_business",
        lambda **kwargs: [SimpleNamespace(bk_biz_id=2)],
    )
    monkeypatch.setattr(
        CustomReportSubscription,
        "get_custom_event_config",
        classmethod(lambda cls, **kwargs: {2: [({"bk_data_id": 2001}, "json")]}),
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

    result = CustomReportSubscription.refresh_collector_custom_conf(
        bk_tenant_id="system",
    )

    assert [call["bk_biz_id"] for call in node_man_calls] == [0]
    assert [call["bk_biz_id"] for call in k8s_calls] == [0]
    assert [detail["bk_biz_id"] for detail in result["details"]] == [2, 0]
    assert result["details"][0]["targets"]["node_man"]["action"] == "skip"
    assert result["details"][0]["targets"]["k8s"]["action"] == "skip"
    assert result["details"][1]["data_ids"] == [2001]
    assert result["summary"]["matched_biz_count"] == 2
    assert result["summary"]["target_count"] == 4
    assert result["summary"]["skipped_count"] == 2


def test_refresh_collect_custom_config_by_biz_dry_run_returns_proxy_hosts(monkeypatch):
    from metadata.models.custom_report import subscription_config
    from metadata.models.custom_report.subscription_config import CustomReportSubscription

    monkeypatch.setattr(
        subscription_config.api.node_man,
        "get_proxies_by_biz",
        lambda **kwargs: [
            {"bk_biz_id": 200, "inner_ip": "127.0.0.1", "bk_cloud_id": 1},
            {"bk_biz_id": 200, "inner_ip": "127.0.0.2", "bk_cloud_id": 1},
        ],
    )
    monkeypatch.setattr(
        subscription_config.api.cmdb,
        "get_host_by_ip",
        lambda **kwargs: [
            {"bk_host_id": 101, "bk_cloud_id": 1, "bk_host_innerip": "127.0.0.1"},
            {"bk_host_id": 102, "bk_cloud_id": 1, "bk_host_innerip": "127.0.0.2"},
        ],
    )
    monkeypatch.setattr(
        CustomReportSubscription,
        "create_subscription",
        classmethod(
            lambda cls, **kwargs: (_ for _ in ()).throw(AssertionError("dry-run should not create subscription"))
        ),
    )

    result = CustomReportSubscription._refresh_collect_custom_config_by_biz(
        bk_tenant_id="system",
        bk_biz_id=2,
        op_type="add",
        data_id_configs=[({"bk_data_id": 2001}, "json")],
        dry_run=True,
    )

    assert result["action"] == "dry_run"
    assert result["proxy_host_ids"] == [101, 102]
    assert result["proxy_hosts"] == [
        {"bk_host_id": 101, "bk_biz_id": 200, "bk_cloud_id": 1, "ip": "127.0.0.1"},
        {"bk_host_id": 102, "bk_biz_id": 200, "bk_cloud_id": 1, "ip": "127.0.0.2"},
    ]


def test_custom_report_refresh_skips_bk_saas_space_with_structured_target(monkeypatch):
    from metadata.models.custom_report import subscription_config
    from metadata.models.custom_report.subscription_config import CustomReportSubscription

    monkeypatch.setattr(subscription_config, "bk_biz_id_to_space_uid", lambda bk_biz_id: f"bk_saas__{bk_biz_id}")
    monkeypatch.setattr(subscription_config, "is_bk_saas_space", lambda space_uid: True)
    monkeypatch.setattr(
        subscription_config.api.node_man,
        "get_proxies_by_biz",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("bk saas space should not query node_man proxy")),
    )
    monkeypatch.setattr(subscription_config.api.cmdb, "get_host_without_biz", lambda **kwargs: {"hosts": []})
    monkeypatch.setattr(
        CustomReportSubscription,
        "get_custom_event_config",
        classmethod(lambda cls, **kwargs: {-42: [({"bk_data_id": 2001}, "json")]}),
    )
    monkeypatch.setattr(
        CustomReportSubscription,
        "get_custom_time_series_config",
        classmethod(lambda cls, **kwargs: {}),
    )

    result = CustomReportSubscription.refresh_collector_custom_conf(
        bk_tenant_id="system",
        bk_biz_id=-42,
        deploy_targets=("node_man",),
        dry_run=True,
    )

    saas_target = result["details"][0]["targets"]["node_man"]
    assert result["details"][0]["bk_biz_id"] == -42
    assert saas_target == {
        "action": "skip",
        "result": True,
        "message": "bk saas space skipped",
        "proxy_host_ids": [],
        "proxy_hosts": [],
        "proxy_count": 0,
    }
    assert result["summary"]["skipped_count"] == 2
    assert result["summary"]["failed_count"] == 0


def test_custom_report_k8s_refresh_reports_deploy_failures_in_summary(monkeypatch):
    from metadata.models.custom_report import subscription_config
    from metadata.models.custom_report.subscription_config import CustomReportSubscription

    monkeypatch.setattr(subscription_config.settings, "CUSTOM_REPORT_DEFAULT_DEPLOY_CLUSTER", [], raising=False)
    monkeypatch.setattr(
        subscription_config.BkCollectorClusterConfig,
        "get_cluster_mapping",
        lambda: {"cluster-1": [2]},
    )
    monkeypatch.setattr(
        subscription_config.BkCollectorClusterConfig,
        "sub_config_tpl",
        lambda cluster_id, tpl_name: "data_id={{ bk_data_id }}",
    )
    monkeypatch.setattr(
        subscription_config.BkCollectorClusterConfig,
        "deploy_to_k8s_with_hash",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("deploy failed")),
    )
    monkeypatch.setattr(
        subscription_config.BkCollectorClusterConfig,
        "clean_dup_secrets_in_multi_protocol",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        CustomReportSubscription,
        "get_custom_event_config",
        classmethod(lambda cls, **kwargs: {2: [({"bk_data_id": 2001}, "json")]}),
    )
    monkeypatch.setattr(
        CustomReportSubscription,
        "get_custom_time_series_config",
        classmethod(lambda cls, **kwargs: {}),
    )

    result = CustomReportSubscription.refresh_collector_custom_conf(
        bk_tenant_id="system",
        bk_biz_id=2,
        deploy_targets=("k8s",),
    )

    k8s_target = result["details"][0]["targets"]["k8s"]
    assert k8s_target["result"] is False
    assert k8s_target["failed_count"] == 1
    assert k8s_target["clusters"][0]["message"] == "deploy failed"
    assert result["summary"]["failed_count"] == 1
    assert result["summary"]["skipped_count"] == 1


def test_refresh_k8s_custom_config_by_biz_keeps_render_failure(monkeypatch):
    from metadata.models.custom_report import subscription_config
    from metadata.models.custom_report.subscription_config import CustomReportSubscription

    class BadTemplate:
        def render(self, context):
            raise RuntimeError("render failed")

    monkeypatch.setattr(subscription_config.settings, "CUSTOM_REPORT_DEFAULT_DEPLOY_CLUSTER", [], raising=False)
    monkeypatch.setattr(
        subscription_config.BkCollectorClusterConfig,
        "get_cluster_mapping",
        lambda: {"cluster-1": [2]},
    )
    monkeypatch.setattr(
        subscription_config.BkCollectorClusterConfig,
        "sub_config_tpl",
        lambda cluster_id, tpl_name: "tpl",
    )
    monkeypatch.setattr(subscription_config.jinja_env, "from_string", lambda tpl: BadTemplate())
    monkeypatch.setattr(
        subscription_config.BkCollectorClusterConfig,
        "deploy_to_k8s_with_hash",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("render failure should not deploy")),
    )

    result = CustomReportSubscription._refresh_k8s_custom_config_by_biz(
        bk_biz_id=2,
        data_id_configs=[({"bk_data_id": 2001}, "json")],
    )

    assert result["result"] is False
    assert result["failed_count"] == 1
    assert result["clusters"][0]["action"] == "refresh"
    assert result["clusters"][0]["result"] is False
    assert result["clusters"][0]["message"] == "render failed"
