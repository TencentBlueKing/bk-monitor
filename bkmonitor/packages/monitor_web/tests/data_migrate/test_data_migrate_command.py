import json
from collections import OrderedDict

import pytest
from django.core.management.base import CommandError

from monitor_web.data_migrate import partial as partial_migrate
from monitor_web.management.commands import data_migrate as data_migrate_command


def _rebuild_options(bk_biz_ids):
    return {
        "bk_tenant_id": "tencent",
        "bk_biz_ids": bk_biz_ids,
        "metric_kafka_cluster_name": "metric-kafka-public-1",
        "log_kafka_cluster_name": "log-kafka-public-1",
        "event_kafka_cluster_name": "event-kafka-public-1",
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


def test_rebuild_passes_event_kafka_cluster_name(monkeypatch):
    received = {}

    monkeypatch.setattr(data_migrate_command, "rebuild_dashboard", lambda bk_biz_id: None)
    monkeypatch.setattr(data_migrate_command, "rebuild_bklog_data_source_route", lambda **kwargs: None)
    monkeypatch.setattr(data_migrate_command, "rebuild_system_data", lambda **kwargs: None)
    monkeypatch.setattr(data_migrate_command, "rebuild_uptime_check", lambda **kwargs: None)
    monkeypatch.setattr(
        data_migrate_command,
        "rebuild_collect_plugins",
        lambda **kwargs: received.setdefault("collect", kwargs),
    )
    monkeypatch.setattr(
        data_migrate_command,
        "rebuild_k8s_data",
        lambda **kwargs: received.setdefault("k8s", kwargs),
    )
    monkeypatch.setattr(
        data_migrate_command,
        "rebuild_custom_report",
        lambda **kwargs: received.setdefault("custom_report", kwargs),
    )

    options = {
        **_rebuild_options([2]),
        "event_kafka_cluster_name": "event-kafka-custom",
    }
    data_migrate_command.Command()._handle_rebuild(options)

    assert received["collect"]["kafka_cluster_names"]["event"] == "event-kafka-custom"
    assert received["k8s"]["event_kafka_cluster_name"] == "event-kafka-custom"
    assert received["custom_report"]["event_kafka_cluster_name"] == "event-kafka-custom"


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


def test_partial_export_handler_uses_independent_export_helper(monkeypatch, tmp_path):
    received = {}

    def fake_export_partial_data_to_directory(**kwargs):
        received["export"] = kwargs
        kwargs["directory_path"].mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(data_migrate_command, "export_partial_data_to_directory", fake_export_partial_data_to_directory)
    monkeypatch.setattr(
        data_migrate_command,
        "export_auto_increment_to_directory",
        lambda directory: received.setdefault("sequences", directory),
    )
    monkeypatch.setattr(
        data_migrate_command,
        "disable_models_in_directory",
        lambda **kwargs: received.setdefault("disable", kwargs),
    )
    monkeypatch.setattr(
        data_migrate_command,
        "make_partial_export_archive",
        lambda **kwargs: (
            (_ for _ in ()).throw(AssertionError("partial export should not write data_id_infos"))
            if (kwargs["export_directory"] / data_migrate_command.PARTIAL_DATA_ID_INFOS_FILE).exists()
            else tmp_path / "bkmonitor-partial-data-migrate.zip"
        ),
    )

    data_migrate_command.Command()._handle_partial_export(
        {
            "directory": str(tmp_path),
            "bk_tenant_id": "tencent",
            "bk_biz_id": 2,
            "bcs_cluster_ids": ["BCS-K8S-00000"],
            "custom_report_data_ids": [123],
            "app_names": ["demo"],
            "format": "json",
            "indent": 2,
            "target_tenant_id": None,
            "no_upload": True,
        }
    )

    assert received["export"]["bk_tenant_id"] == "tencent"
    assert received["export"]["bk_biz_id"] == 2
    assert received["export"]["bcs_cluster_ids"] == ["BCS-K8S-00000"]
    assert received["export"]["custom_report_data_ids"] == [123]
    assert received["export"]["app_names"] == ["demo"]
    assert received["sequences"].name.startswith("bkmonitor-partial-data-migrate-")
    assert received["disable"]["directory_path"] == received["sequences"]


def test_partial_import_handler_runs_prechecked_import(monkeypatch, tmp_path):
    received = {}

    def fake_import_partial_data_from_directory(**kwargs):
        received.update(kwargs)
        return {"precheck": {"result": True}, "imported_count": 3}

    monkeypatch.setattr(
        data_migrate_command, "import_partial_data_from_directory", fake_import_partial_data_from_directory
    )

    data_migrate_command.Command()._handle_partial_import(
        {
            "directory": str(tmp_path),
            "bk_biz_id": 2,
            "disable_atomic": True,
        }
    )

    assert received == {
        "directory_path": tmp_path,
        "bk_biz_ids": [2],
        "atomic": False,
    }


def test_partial_import_disables_global_post_import_repairs(monkeypatch, tmp_path):
    received = {}

    monkeypatch.setattr(
        partial_migrate,
        "precheck_partial_import_directory",
        lambda **kwargs: {"result": True, "checked": {"files": 1, "records": 1}, "conflicts": []},
    )

    def fake_import_biz_data_from_directory(**kwargs):
        received.update(kwargs)
        return ["imported"]

    monkeypatch.setattr(partial_migrate, "import_biz_data_from_directory", fake_import_biz_data_from_directory)

    result = partial_migrate.import_partial_data_from_directory(
        directory_path=tmp_path,
        bk_biz_ids=[2],
        atomic=False,
    )

    assert result["imported_count"] == 1
    assert received == {
        "directory_path": tmp_path,
        "bk_biz_ids": [2],
        "atomic": False,
        "cleanup_existing": False,
        "sync_close_records": False,
        "migrate_builtin_system_event_strategy": False,
        "migrate_builtin_gather_up_strategy": False,
        "repair_plugin_strategy": False,
        "repair_plugin_dashboard": False,
    }


def test_partial_import_rejects_zero_biz_id(tmp_path):
    with pytest.raises(CommandError, match="partial-import 动作不支持业务 ID: 0"):
        data_migrate_command.Command()._handle_partial_import(
            {
                "directory": str(tmp_path),
                "bk_biz_id": 0,
                "disable_atomic": True,
            }
        )


def test_partial_rebuild_handler_passes_scope_and_cluster_arguments(monkeypatch):
    received = {}

    def fake_rebuild_partial_data(**kwargs):
        received.update(kwargs)
        return {"operations": []}

    monkeypatch.setattr(data_migrate_command, "rebuild_partial_data", fake_rebuild_partial_data)

    data_migrate_command.Command()._handle_partial_rebuild(
        {
            "directory": None,
            "bk_tenant_id": "tencent",
            "bk_biz_id": 2,
            "bcs_cluster_ids": ["BCS-K8S-00000"],
            "custom_report_data_ids": [123],
            "app_names": ["demo"],
            "metric_kafka_cluster_name": "metric-kafka-public-1",
            "log_kafka_cluster_name": "log-kafka-public-1",
            "event_kafka_cluster_name": "event-kafka-public-1",
            "log_es_cluster_name": "log-es-public-1",
            "event_es_cluster_name": "event-es-public-1",
            "apm_kafka_cluster_name": " ",
            "apm_es_cluster_name": "",
        }
    )

    assert received == {
        "bk_tenant_id": "tencent",
        "bk_biz_id": 2,
        "bcs_cluster_ids": ["BCS-K8S-00000"],
        "custom_report_data_ids": [123],
        "app_names": ["demo"],
        "metric_kafka_cluster_name": "metric-kafka-public-1",
        "log_kafka_cluster_name": "log-kafka-public-1",
        "event_kafka_cluster_name": "event-kafka-public-1",
        "log_es_cluster_name": "log-es-public-1",
        "event_es_cluster_name": "event-es-public-1",
        "apm_kafka_cluster_name": None,
        "apm_es_cluster_name": None,
    }


def test_partial_rebuild_handler_writes_new_environment_data_id_infos(monkeypatch, tmp_path):
    received = {}

    def fake_rebuild_partial_data(**kwargs):
        received.update(kwargs)
        return {
            "operations": [],
            "data_id_infos": {
                123: {
                    "data_id": 123,
                    "topic_name": "new-topic",
                    "kafka_cluster_name": "new-kafka",
                }
            },
        }

    monkeypatch.setattr(data_migrate_command, "rebuild_partial_data", fake_rebuild_partial_data)

    data_migrate_command.Command()._handle_partial_rebuild(
        {
            "directory": str(tmp_path),
            "bk_tenant_id": "tencent",
            "bk_biz_id": 2,
            "bcs_cluster_ids": [],
            "custom_report_data_ids": [123],
            "app_names": [],
            "metric_kafka_cluster_name": "metric-kafka-public-1",
            "log_kafka_cluster_name": "log-kafka-public-1",
            "event_kafka_cluster_name": "event-kafka-public-1",
            "log_es_cluster_name": "log-es-public-1",
            "event_es_cluster_name": "event-es-public-1",
            "apm_kafka_cluster_name": None,
            "apm_es_cluster_name": None,
        }
    )

    assert received["custom_report_data_ids"] == [123]
    data_id_infos_path = tmp_path / data_migrate_command.PARTIAL_DATA_ID_INFOS_FILE
    assert json.loads(data_id_infos_path.read_text(encoding="utf-8")) == {
        "123": {
            "data_id": 123,
            "topic_name": "new-topic",
            "kafka_cluster_name": "new-kafka",
        }
    }


def test_rebuild_partial_data_uses_rebuilt_data_ids_for_route_infos(monkeypatch):
    calls = {}
    context = partial_migrate.PartialMigrationContext(
        module_fetchers=OrderedDict(),
        manifest_scope={
            "data_ids": [100],
            "table_ids": ["2_bkmonitor.old"],
        },
        refs={},
    )

    def fake_collect_current_partial_data_ids(**kwargs):
        calls["collect"] = kwargs
        return [200]

    def fake_build_data_id_infos(**kwargs):
        calls["data_id_infos"] = kwargs
        return {
            200: {
                "data_id": 200,
                "topic_name": "new-topic",
                "kafka_cluster_name": "new-kafka",
            }
        }

    monkeypatch.setattr(partial_migrate, "build_partial_migration_context", lambda **kwargs: context)
    monkeypatch.setattr(partial_migrate, "_collect_current_partial_data_ids", fake_collect_current_partial_data_ids)
    monkeypatch.setattr(partial_migrate, "_build_data_id_infos", fake_build_data_id_infos)

    result = partial_migrate.rebuild_partial_data(
        bk_tenant_id="tencent",
        bk_biz_id=2,
        bcs_cluster_ids=[],
        custom_report_data_ids=[],
        app_names=[],
    )

    assert calls["collect"]["table_ids"] == ["2_bkmonitor.old"]
    assert calls["data_id_infos"]["data_ids"] == [200]
    assert result["rebuilt_data_ids"] == [200]
    assert result["data_id_infos"][200]["topic_name"] == "new-topic"


def test_precheck_partial_import_requires_bk_tenant_id(monkeypatch, tmp_path):
    fixture_path = tmp_path / "biz" / "2" / "metadata_data_source.json"
    fixture_path.parent.mkdir(parents=True)
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "format": "json",
                "bk_biz_ids": [2],
                "global_files": [],
                "biz_files": {"2": [fixture_path.relative_to(tmp_path).as_posix()]},
            }
        ),
        encoding="utf-8",
    )
    fixture_path.write_text(
        json.dumps(
            [
                {
                    "model": partial_migrate.DataSource._meta.label_lower,
                    "pk": 123,
                    "fields": {"data_name": "custom-metric"},
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(partial_migrate, "_has_existing", lambda queryset: False)

    result = partial_migrate.precheck_partial_import_directory(tmp_path)

    assert result["result"] is False
    assert result["conflicts"] == [
        {
            "source_file": "biz/2/metadata_data_source.json",
            "model": partial_migrate.DataSource._meta.label_lower,
            "pk": 123,
            "field": "bk_tenant_id",
            "value": None,
            "reason": "fixture record missing required bk_tenant_id",
        }
    ]


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


def test_repair_plugin_dashboard_result_table_handler_allows_empty_biz_ids(monkeypatch):
    received = {}

    def fake_repair_plugin_dashboard_result_table_id(**kwargs):
        received.update(kwargs)
        return {
            "changed_count": 1,
            "applied_count": 0,
            "stale_count": 0,
            "invalid_json_count": 0,
            "changes": [],
            "invalid_json": [],
        }

    monkeypatch.setattr(
        data_migrate_command,
        "repair_plugin_dashboard_result_table_id",
        fake_repair_plugin_dashboard_result_table_id,
    )

    data_migrate_command.Command()._handle_repair_plugin_dashboard_result_table({"bk_biz_ids": None, "dry_run": True})

    assert received == {"bk_biz_id": None, "dry_run": True}


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


def test_stop_biz_bk_collector_handler_passes_arguments(monkeypatch):
    received = {}

    def fake_stop_biz_bk_collector(**kwargs):
        received.update(kwargs)
        return {
            "summary": {
                "total": {
                    "matched_count": 1,
                    "planned_count": 0,
                    "succeeded_count": 1,
                    "skipped_count": 0,
                    "failed_count": 0,
                }
            }
        }

    monkeypatch.setattr(data_migrate_command, "stop_biz_bk_collector", fake_stop_biz_bk_collector)

    data_migrate_command.Command()._handle_stop_biz_bk_collector(
        {
            "bk_tenant_id": "tencent",
            "bk_biz_ids": [2],
            "operator": "admin",
            "dry_run": True,
            "job_wait_timeout": 30,
            "job_poll_interval": 2,
        }
    )

    assert received == {
        "bk_tenant_id": "tencent",
        "bk_biz_ids": [2],
        "operator": "admin",
        "dry_run": True,
        "job_wait_timeout": 30,
        "job_poll_interval": 2,
        "skip_hosts_without_agent": True,
    }


def test_refresh_biz_bk_collector_configs_handler_passes_delivery_check_arguments(monkeypatch):
    received = {}

    def fake_refresh_biz_bk_collector_proxy_configs(**kwargs):
        received.update(kwargs)
        return {
            "summary": {
                "total": {
                    "matched_count": 1,
                    "planned_count": 0,
                    "succeeded_count": 1,
                    "skipped_count": 0,
                    "failed_count": 0,
                }
            },
            "delivery_check": {"result": True, "timed_out": False},
        }

    monkeypatch.setattr(
        data_migrate_command,
        "refresh_biz_bk_collector_proxy_configs",
        fake_refresh_biz_bk_collector_proxy_configs,
    )

    data_migrate_command.Command()._handle_refresh_biz_bk_collector_configs(
        {
            "bk_tenant_id": "tencent",
            "bk_biz_ids": [2],
            "config_types": ["custom_report"],
            "operator": "admin",
            "dry_run": False,
            "skip_delivery_check": False,
            "include_details": False,
            "delivery_wait_timeout": 30,
            "delivery_poll_interval": 2,
        }
    )

    assert received == {
        "bk_tenant_id": "tencent",
        "bk_biz_ids": [2],
        "config_types": ["custom_report"],
        "operator": "admin",
        "dry_run": False,
        "check_delivery": True,
        "delivery_wait_timeout": 30,
        "delivery_poll_interval": 2,
        "retry_render_failures": True,
        "include_details": False,
    }


def test_bk_collector_report_result_raises_command_error_on_job_timeout():
    result = {
        "summary": {
            "total": {
                "matched_count": 1,
                "planned_count": 0,
                "succeeded_count": 0,
                "pending_count": 0,
                "timeout_count": 1,
                "skipped_count": 0,
                "failed_count": 1,
            }
        }
    }

    with pytest.raises(CommandError, match="timeout jobs"):
        data_migrate_command.Command()._write_report_result(
            result,
            success_message="stop biz bk-collector completed",
            warning_message="stop biz bk-collector completed with failures",
        )


def test_bk_collector_report_result_raises_command_error_on_delivery_timeout():
    result = {
        "summary": {
            "total": {
                "matched_count": 1,
                "planned_count": 0,
                "succeeded_count": 1,
                "pending_count": 0,
                "skipped_count": 0,
                "failed_count": 0,
            }
        },
        "delivery_check": {"result": False, "timed_out": True},
    }

    with pytest.raises(CommandError, match="delivery check timeout"):
        data_migrate_command.Command()._write_report_result(
            result,
            success_message="refresh biz bk-collector configs completed",
            warning_message="refresh biz bk-collector configs completed with failures",
        )


def test_bk_collector_report_result_raises_command_error_on_failed_result():
    result = {
        "summary": {
            "total": {
                "matched_count": 1,
                "planned_count": 0,
                "succeeded_count": 0,
                "pending_count": 0,
                "skipped_count": 0,
                "failed_count": 1,
            }
        }
    }

    with pytest.raises(CommandError, match="completed with failures: 1"):
        data_migrate_command.Command()._write_report_result(
            result,
            success_message="install biz bk-collector completed",
            warning_message="install biz bk-collector completed with failures",
        )
