"""MCP Server 声明及发布顺序的独立回归测试。

运行：python -m pytest -c /dev/null support-files/apigw/scripts/test_mcp_servers.py
需要安装项目锁定的 apigw-manager、Django、PyYAML 和 pytest；不连接网关或业务数据库。
"""

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import django
import pytest
import yaml
from django.conf import settings
from django.core.management.base import CommandError
from django.template import Context, Engine

_APIGW_DIR = Path(__file__).resolve().parent.parent
_BASE_DIR = _APIGW_DIR.parent.parent
_DEFINITION = _APIGW_DIR / "definition.yaml"
_COMMAND_PATH = _BASE_DIR / "bkmonitor/management/commands/sync_apigw.py"
_SPEC = importlib.util.spec_from_file_location("monitor_sync_apigw", _COMMAND_PATH)
sync_apigw = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(sync_apigw)


def _settings(stage="prod", enabled=True):
    return SimpleNamespace(
        BASE_DIR=str(_BASE_DIR),
        APIGW_STAGE=stage,
        APIGW_MANAGERS=["admin"],
        BK_MONITOR_API_HOST="http://monitor-api.example.com",
        APP_CODE="bk_monitorv3",
        SYNC_APIGATEWAY_ENABLED=enabled,
    )


def _definition(stage="prod"):
    rendered = (
        Engine().from_string(_DEFINITION.read_text()).render(Context({"settings": _settings(stage)}, autoescape=False))
    )
    return yaml.safe_load(rendered)


def _source_operations(filename):
    paths = yaml.safe_load((_APIGW_DIR / "resources/internal/user" / filename).read_text())["paths"]
    return {operation["operationId"] for methods in paths.values() for operation in methods.values()}


@pytest.mark.parametrize("stage", ["prod", "stage"])
def test_only_target_stage_is_rendered_with_existing_backend(stage):
    definition = _definition(stage)
    assert definition["spec_version"] == 2
    assert "stage" not in definition
    assert len(definition["stages"]) == 1
    stage_definition = definition["stages"][0]
    assert stage_definition["name"] == stage
    assert stage_definition["proxy_http"] == {
        "timeout": 60,
        "upstreams": {
            "loadbalance": "roundrobin",
            "hosts": [{"host": _settings().BK_MONITOR_API_HOST, "weight": 100}],
        },
        "transform_headers": {"set": {"x-bkapi-from": "apigw"}},
    }


def test_server_names_and_access_modes_preserve_existing_contracts():
    servers = _definition()["stages"][0]["mcp_servers"]
    names = [server["name"] for server in servers]
    assert len(names) == len(set(names)) == 16
    assert set(names) == {
        "metadata-query",
        "metrics-query",
        "log-query",
        "log-scene-search",
        "event-query",
        "alarm",
        "alarm-handling",
        "dashboard-query",
        "dashboard-edit",
        "tracing",
        "profiling-query",
        "relation-query",
        "log-collector",
        "log-extract",
        "recording-rule",
        "unified",
    }
    for server in servers:
        assert not server["name"].startswith("bk-monitor-")
        assert server["protocol_type"] == "streamable_http"
        assert server["status"] == 1
        assert server["raw_response_enabled"] is False
        assert not server.get("target_app_codes")
        assert server["is_public"] is True
        assert server["oauth2_public_client_enabled"] is True
        assert server["oauth2_personal_client_enabled"] is True


def test_tools_exist_have_request_schemas_and_cover_reviewed_sources():
    resources = {}
    for file in (_APIGW_DIR / "resources").glob("*/*/*.yaml"):
        for methods in yaml.safe_load(file.read_text())["paths"].values():
            for operation in methods.values():
                assert operation["operationId"] not in resources
                resources[operation["operationId"]] = operation

    servers = _definition()["stages"][0]["mcp_servers"]
    declared = set()
    for server in servers:
        names = server["resource_names"]
        assert names and len(names) == len(set(names))
        for name in names:
            operation = resources[name]
            assert (
                operation.get("parameters")
                or operation.get("requestBody")
                or operation["x-bk-apigateway-resource"].get("noneSchema")
            ), name
        declared.update(names)

    # 内部运营不再注册，专用诊断和 OpenClaw 入口不随普通业务 MCP 发布。
    excluded = {"operation_mcp.yaml", "ops_mcp.yaml", "openclaw_recovering_mcp.yaml"}
    reviewed = set()
    for file in (_APIGW_DIR / "resources/internal/user").glob("*mcp.yaml"):
        if file.name not in excluded:
            reviewed.update(_source_operations(file.name))
    assert declared == reviewed
    assert declared.isdisjoint(_source_operations("operation_mcp.yaml"))


def test_query_and_write_groups_remain_separate():
    servers = {server["name"]: set(server["resource_names"]) for server in _definition()["stages"][0]["mcp_servers"]}
    assert servers["alarm"] == _source_operations("alert_mcp.yaml")
    assert servers["alarm-handling"] == _source_operations("alert_handling_mcp.yaml")
    assert servers["alarm"].isdisjoint(servers["alarm-handling"])
    assert servers["tracing"].isdisjoint(servers["profiling-query"])
    assert servers["tracing"] | servers["profiling-query"] == _source_operations("apm_mcp.yaml")
    assert servers["dashboard-query"].isdisjoint(servers["dashboard-edit"])
    assert servers["dashboard-query"] | servers["dashboard-edit"] == _source_operations("dashboard_mcp.yaml")
    assert servers["log-query"] & servers["log-scene-search"] == {"search_logs"}
    assert servers["log-query"] | servers["log-scene-search"] == _source_operations("log_mcp.yaml")


def test_disabled_sync_makes_no_changes():
    with (
        patch.object(sync_apigw, "settings", _settings(enabled=False)),
        patch.object(sync_apigw.subprocess, "run") as merge,
        patch.object(sync_apigw, "call_command") as call_command,
    ):
        sync_apigw.Command().handle()
    merge.assert_not_called()
    call_command.assert_not_called()


def test_merge_failure_stops_release_and_server_sync():
    error = subprocess.CalledProcessError(1, "merge_resources", stderr="duplicate operationId")
    with (
        patch.object(sync_apigw, "settings", _settings()),
        patch.object(sync_apigw.subprocess, "run", side_effect=error),
        patch.object(sync_apigw, "call_command") as call_command,
        pytest.raises(CommandError, match="duplicate operationId"),
    ):
        sync_apigw.Command().handle()
    call_command.assert_not_called()


@pytest.mark.parametrize("stage", ["prod", "stage"])
def test_server_sync_runs_after_resource_release(stage):
    with (
        patch.object(sync_apigw, "settings", _settings(stage)),
        patch.object(sync_apigw.subprocess, "run", return_value=SimpleNamespace(stdout="")) as merge,
        patch.object(sync_apigw, "call_command") as call_command,
    ):
        sync_apigw.Command().handle()
    assert merge.call_args.args[0][0] == sys.executable
    calls = call_command.call_args_list
    names = [call.args[0] for call in calls]
    assert names == [
        "sync_apigw_config",
        "sync_apigw_stage",
        "sync_apigw_resources",
        "sync_resource_docs_by_archive",
        "create_version_and_release_apigw",
        "sync_apigw_stage_mcp_servers",
        "grant_apigw_permissions",
        "fetch_apigw_public_key",
    ]
    assert f"--stage={stage}" in calls[4].args
    assert calls[5].args[1:] == ("--gateway-name=bk-monitor", f"--file={_DEFINITION}")


@pytest.mark.parametrize("failed_command", ["create_version_and_release_apigw", "sync_apigw_stage_mcp_servers"])
def test_remote_failures_are_not_reported_as_success(failed_command):
    def fail(command, *args):
        if command == failed_command:
            raise CommandError("upstream failed")

    with (
        patch.object(sync_apigw, "settings", _settings()),
        patch.object(sync_apigw.subprocess, "run", return_value=SimpleNamespace(stdout="")),
        patch.object(sync_apigw, "call_command", side_effect=fail) as call_command,
        pytest.raises(CommandError, match="upstream failed"),
    ):
        sync_apigw.Command().handle()
    assert call_command.call_args.args[0] == failed_command


def test_locked_sdk_loads_v2_definition_and_sends_mcp_servers():
    # 让独立运行也能加载 SDK 的实际 Django Command；不建立数据库连接。
    if not settings.configured:
        settings.configure(
            INSTALLED_APPS=["apigw_manager.apigw"],
            TEMPLATES=[{"BACKEND": "django.template.backends.django.DjangoTemplates"}],
            SECRET_KEY="apigw-sync-test",
        )
        django.setup()
    from apigw_manager.apigw.management.commands.sync_apigw_stage import Command as StageCommand
    from apigw_manager.apigw.management.commands.sync_apigw_stage_mcp_servers import Command as McpCommand
    from django.test import override_settings

    with override_settings(**vars(_settings())):
        stage_command = StageCommand()
        stages = stage_command.get_definition(define=[], file=str(_DEFINITION), namespace="stage")
        command = McpCommand()
        definitions = command.get_definition(define=[], file=str(_DEFINITION), namespace="stages")
    assert stages == definitions
    assert len(definitions[0]["mcp_servers"]) == 16
    manager = Mock()
    manager.sync_stage_mcp_servers.return_value = {
        "data": [{"id": 1, "name": "bk-monitor-prod-alarm", "action": "update"}]
    }
    command.do(manager, definitions)
    manager.sync_stage_mcp_servers.assert_called_once_with(**definitions[0])
