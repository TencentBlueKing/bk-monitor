from monitor_web.management.commands import data_migrate as data_migrate_command


def _rebuild_options(bk_biz_ids):
    return {
        "bk_tenant_id": "tencent",
        "bk_biz_ids": bk_biz_ids,
        "metric_kafka_cluster_name": "metric-kafka-public-1",
        "log_kafka_cluster_name": "log-kafka-public-1",
        "log_es_cluster_name": "log-es-public-1",
        "event_es_cluster_name": "event-es-public-1",
    }


def test_rebuild_negative_biz_skips_bkcc_subscription_steps(monkeypatch):
    calls = []

    monkeypatch.setattr(
        data_migrate_command, "rebuild_dashboard", lambda bk_biz_id: calls.append(("dashboard", bk_biz_id))
    )
    monkeypatch.setattr(
        data_migrate_command,
        "rebuild_bklog_data_source_route",
        lambda **kwargs: calls.append(("bklog", kwargs["bk_biz_id"])),
    )
    monkeypatch.setattr(
        data_migrate_command,
        "rebuild_system_data",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("negative biz should skip system data")),
    )
    monkeypatch.setattr(
        data_migrate_command,
        "rebuild_uptime_check",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("negative biz should skip uptime check")),
    )
    monkeypatch.setattr(
        data_migrate_command,
        "rebuild_collect_plugins",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("negative biz should skip collect plugins")),
    )
    monkeypatch.setattr(
        data_migrate_command,
        "rebuild_k8s_data",
        lambda **kwargs: calls.append(("k8s", kwargs["bk_biz_id"])),
    )
    monkeypatch.setattr(
        data_migrate_command,
        "rebuild_custom_report",
        lambda **kwargs: calls.append(("custom_report", kwargs["bk_biz_id"])),
    )

    data_migrate_command.Command()._handle_rebuild(_rebuild_options([-4759]))

    assert calls == [
        ("dashboard", -4759),
        ("bklog", -4759),
        ("k8s", -4759),
        ("custom_report", -4759),
    ]


def test_rebuild_positive_biz_keeps_full_steps(monkeypatch):
    calls = []

    monkeypatch.setattr(
        data_migrate_command, "rebuild_dashboard", lambda bk_biz_id: calls.append(("dashboard", bk_biz_id))
    )
    monkeypatch.setattr(
        data_migrate_command,
        "rebuild_bklog_data_source_route",
        lambda **kwargs: calls.append(("bklog", kwargs["bk_biz_id"])),
    )
    monkeypatch.setattr(
        data_migrate_command,
        "rebuild_system_data",
        lambda **kwargs: calls.append(("system", kwargs["bk_biz_id"])),
    )
    monkeypatch.setattr(
        data_migrate_command,
        "rebuild_uptime_check",
        lambda **kwargs: calls.append(("uptime", kwargs["bk_biz_id"])),
    )
    monkeypatch.setattr(
        data_migrate_command,
        "rebuild_collect_plugins",
        lambda **kwargs: calls.append(("collect", kwargs["bk_biz_id"])),
    )
    monkeypatch.setattr(
        data_migrate_command,
        "rebuild_k8s_data",
        lambda **kwargs: calls.append(("k8s", kwargs["bk_biz_id"])),
    )
    monkeypatch.setattr(
        data_migrate_command,
        "rebuild_custom_report",
        lambda **kwargs: calls.append(("custom_report", kwargs["bk_biz_id"])),
    )

    data_migrate_command.Command()._handle_rebuild(_rebuild_options([2]))

    assert calls == [
        ("dashboard", 2),
        ("bklog", 2),
        ("system", 2),
        ("uptime", 2),
        ("collect", 2),
        ("k8s", 2),
        ("custom_report", 2),
    ]


def test_rebuild_passes_apm_cluster_names_when_provided(monkeypatch):
    received = {}

    monkeypatch.setattr(data_migrate_command, "rebuild_dashboard", lambda bk_biz_id: None)
    monkeypatch.setattr(
        data_migrate_command,
        "rebuild_bklog_data_source_route",
        lambda **kwargs: received.setdefault("bklog", kwargs),
    )
    monkeypatch.setattr(data_migrate_command, "rebuild_system_data", lambda **kwargs: None)
    monkeypatch.setattr(data_migrate_command, "rebuild_uptime_check", lambda **kwargs: None)
    monkeypatch.setattr(data_migrate_command, "rebuild_collect_plugins", lambda **kwargs: None)
    monkeypatch.setattr(data_migrate_command, "rebuild_k8s_data", lambda **kwargs: None)
    monkeypatch.setattr(
        data_migrate_command,
        "rebuild_custom_report",
        lambda **kwargs: received.setdefault("custom_report", kwargs),
    )

    options = {
        **_rebuild_options([2]),
        "apm_kafka_cluster_name": "apm-kafka-public-1",
        "apm_es_cluster_name": "apm-es-public-1",
    }
    data_migrate_command.Command()._handle_rebuild(options)

    assert received["bklog"]["apm_kafka_cluster_name"] == "apm-kafka-public-1"
    assert received["bklog"]["apm_es_cluster_name"] == "apm-es-public-1"
    assert received["custom_report"]["apm_kafka_cluster_name"] == "apm-kafka-public-1"


def test_rebuild_treats_blank_apm_cluster_names_as_default(monkeypatch):
    received = {}

    monkeypatch.setattr(data_migrate_command, "rebuild_dashboard", lambda bk_biz_id: None)
    monkeypatch.setattr(
        data_migrate_command,
        "rebuild_bklog_data_source_route",
        lambda **kwargs: received.setdefault("bklog", kwargs),
    )
    monkeypatch.setattr(data_migrate_command, "rebuild_system_data", lambda **kwargs: None)
    monkeypatch.setattr(data_migrate_command, "rebuild_uptime_check", lambda **kwargs: None)
    monkeypatch.setattr(data_migrate_command, "rebuild_collect_plugins", lambda **kwargs: None)
    monkeypatch.setattr(data_migrate_command, "rebuild_k8s_data", lambda **kwargs: None)
    monkeypatch.setattr(
        data_migrate_command,
        "rebuild_custom_report",
        lambda **kwargs: received.setdefault("custom_report", kwargs),
    )

    options = {
        **_rebuild_options([2]),
        "apm_kafka_cluster_name": " ",
        "apm_es_cluster_name": "",
    }
    data_migrate_command.Command()._handle_rebuild(options)

    assert received["bklog"]["apm_kafka_cluster_name"] is None
    assert received["bklog"]["apm_es_cluster_name"] is None
    assert received["custom_report"]["apm_kafka_cluster_name"] is None


def test_find_custom_report_data_ids_accepts_negative_biz_ids(monkeypatch):
    received = {}

    def fake_find_biz_custom_report_data_ids(*, bk_tenant_id, bk_biz_ids):
        received["bk_tenant_id"] = bk_tenant_id
        received["bk_biz_ids"] = bk_biz_ids
        return {"custom_metric": {}, "custom_event": {}, "k8s": {}, "apm": {}, "log": {}}

    monkeypatch.setattr(
        data_migrate_command,
        "find_biz_custom_report_data_ids",
        fake_find_biz_custom_report_data_ids,
    )

    data_migrate_command.Command()._handle_find_custom_report_data_ids(
        {"bk_tenant_id": "tencent", "bk_biz_ids": [-4759, 2]}
    )

    assert received == {"bk_tenant_id": "tencent", "bk_biz_ids": [-4759, 2]}


def test_enable_closed_strategies_accepts_negative_biz_ids(monkeypatch):
    received = {}

    def fake_enable_closed_strategies_from_application_config(*, bk_biz_ids):
        received["bk_biz_ids"] = bk_biz_ids
        return {
            -4759: {
                "configured_count": 0,
                "existing_count": 0,
                "enabled_count": 0,
                "missing_ids": [],
            },
            2: {
                "configured_count": 1,
                "existing_count": 1,
                "enabled_count": 1,
                "missing_ids": [],
            },
        }

    monkeypatch.setattr(
        data_migrate_command,
        "enable_closed_strategies_from_application_config",
        fake_enable_closed_strategies_from_application_config,
    )

    data_migrate_command.Command()._handle_enable_closed_strategies({"bk_biz_ids": [-4759, 2]})

    assert received["bk_biz_ids"] == [-4759, 2]


def test_stop_biz_subscription_tasks_handler_passes_negative_biz_ids(monkeypatch):
    received = {}

    def fake_stop_biz_subscription_tasks(**kwargs):
        received.update(kwargs)
        return {
            "summary": {
                "total": {
                    "matched_count": 0,
                    "planned_count": 0,
                    "stopped_count": 0,
                    "skipped_count": 0,
                    "failed_count": 0,
                }
            }
        }

    monkeypatch.setattr(data_migrate_command, "stop_biz_subscription_tasks", fake_stop_biz_subscription_tasks)

    data_migrate_command.Command()._handle_stop_biz_subscription_tasks(
        {
            "bk_tenant_id": "tencent",
            "bk_biz_ids": [-4759, 2],
            "operator": "admin",
            "dry_run": False,
        }
    )

    assert received == {
        "bk_tenant_id": "tencent",
        "bk_biz_ids": [-4759, 2],
        "operator": "admin",
        "dry_run": False,
    }
