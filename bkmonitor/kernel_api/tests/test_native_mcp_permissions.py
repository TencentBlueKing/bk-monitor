"""Native MCP MVP checks, runnable without project settings or external services.

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=bkmonitor bkmonitor/.venv/bin/python -m pytest \
  -c /dev/null -p no:cacheprovider bkmonitor/kernel_api/tests/test_native_mcp_permissions.py

Native permission/registry modules run normally. Heavy HTTP facade methods are
executed from their unchanged AST with mocked adapters; not an end-to-end server test.
"""

from __future__ import annotations

import ast
import json
import logging
import secrets
import socket
import sys
import time
from dataclasses import replace
from pathlib import Path
from types import ModuleType, SimpleNamespace as NS
from unittest.mock import Mock

import django
import pytest
import yaml
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.cache.backends.locmem import LocMemCache
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.test import RequestFactory
from jsonschema import Draft7Validator
from iam import Action, Request, Resource, Subject
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError

BASE = Path(__file__).resolve().parents[2]
if not settings.configured:
    settings.configure(SECRET_KEY="offline", INSTALLED_APPS=[], DATABASES={}, USE_I18N=False, BASE_DIR=str(BASE))
    django.setup()

from bkmonitor.utils import tenant
from kernel_api.unified_mcp import permissions as auth, registry


def source_method(path, name, **namespace):
    node = ast.parse((BASE / path).read_text())
    for part in name.split("."):
        node = next(child for child in node.body if getattr(child, "name", None) == part)
    node.decorator_list = []
    tree = ast.Module(
        body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), node],
        type_ignores=[],
    )
    exec(compile(ast.fix_missing_locations(tree), str(BASE / path), "exec"), namespace)
    return namespace[node.name]


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    for key, value in {
        "BASE_DIR": str(BASE),
        "MCP_NATIVE_PERMISSION_TOOLS": list(registry.NATIVE_PERMISSIONS),
        "MCP_LOG_IAM_PROFILE": {"mode": "v3-current", "gateway_url": "https://iam.invalid/"},
        "ENABLE_MULTI_TENANT_MODE": False,
        "ROLE": "api",
        "BK_IAM_SYSTEM_ID": "bk_monitorv3",
        "SAAS_APP_CODE": "monitor-saas",
        "SAAS_SECRET_KEY": "offline",
        "MCP_PERMISSION_EXEMPT_TOOLS": ["list_spaces"],
    }.items():
        monkeypatch.setattr(settings, key, value, raising=False)
    monkeypatch.setattr(socket.socket, "connect", Mock(side_effect=AssertionError("network forbidden")))
    monkeypatch.setattr(socket, "getaddrinfo", Mock(side_effect=AssertionError("DNS forbidden")))
    registry._cached_tool_registry.cache_clear()
    yield
    registry._cached_tool_registry.cache_clear()


@pytest.fixture
def request_factory():
    def build(path="/api/v4/unified_mcp/execute_tool/", body=None, method="POST"):
        factory = RequestFactory()
        if method == "GET":
            request = factory.get(path, body or {})
        else:
            request = factory.post(path, json.dumps(body or {}), content_type="application/json")
        request.META["HTTP_X_BKAPI_MCP_SERVER_NAME"] = "bk-monitor-prod-unified"
        request.user = NS(username="alice", tenant_id="system", is_authenticated=True)
        request.jwt = NS(is_valid=True, user={"username": "alice", "verified": True})
        request.skip_check = True
        request.unified_mcp_permission_checked = True
        return request

    return build


@pytest.fixture
def io(monkeypatch):
    iam = Mock()
    iam.is_allowed.return_value = True
    iam.get_apply_url.return_value = (True, "", "https://iam.invalid/log-apply")
    catalog = Mock(
        return_value=[
            {
                "index_set_id": 123,
                "index_set_name": "synthetic",
                "bk_biz_id": 2,
                "space_uid": "bkcc__2",
                "is_platform_index": False,
                "is_group": False,
            }
        ]
    )
    monitor = Mock()
    # Permission.is_allowed_by_biz masks some SDK errors as False; the new path must not call it.
    monitor.is_allowed_by_biz.return_value = False
    monitor.filter_space_list_by_action.return_value = [{"bk_biz_id": 2}]
    monitor.iam_client.is_allowed.side_effect = lambda query: not query.action.id.startswith("using_")
    monitor.iam_client.get_apply_url.return_value = (True, "", "https://iam.invalid/monitor-apply")
    monitor.make_request.side_effect = lambda action, resources: Request(
        "bk_monitorv3", Subject("user", "alice"), Action(action), resources, None
    )
    monitor.get_apply_url.return_value = "https://iam.invalid/monitor-apply"
    monkeypatch.setattr(
        auth, "_business_resource", lambda biz: Resource("bk_monitorv3", "space", str(biz), {"name": str(biz)})
    )
    real_target_scope = auth._validate_alert_target
    target_scope = Mock()
    monkeypatch.setattr(auth, "_validate_alert_target", target_scope)
    monkeypatch.setattr(auth, "_log_iam", lambda user: iam)
    monkeypatch.setattr(auth, "log_index_sets", catalog)
    monkeypatch.setattr(auth, "_monitor_permission", lambda user: monitor)
    dispatcher = ModuleType("kernel_api.unified_mcp.dispatcher")
    dispatcher.dispatch_tool = Mock(return_value={"ok": True})
    monkeypatch.setitem(sys.modules, dispatcher.__name__, dispatcher)
    return NS(
        iam=iam,
        catalog=catalog,
        monitor=monitor,
        dispatch=dispatcher.dispatch_tool,
        target_scope=target_scope,
        real_target_scope=real_target_scope,
    )


@pytest.fixture
def native_http(monkeypatch, request_factory):
    for module_name, class_name in [
        ("bkmonitor.views.renderers", "MonitorJSONRenderer"),
        ("kernel_api.adapters", "ApiRenderer"),
    ]:
        module = ModuleType(module_name)
        setattr(module, class_name, lambda: NS(render=lambda data, **kwargs: json.dumps(data).encode()))
        monkeypatch.setitem(sys.modules, module_name, module)
    handle = source_method(
        "kernel_api/middlewares/authentication.py",
        "AuthenticationMiddleware._handle_native_mcp",
        log_mcp_event=auth.log_mcp_event,
        logging=logging,
        HttpResponse=HttpResponse,
        JsonResponse=JsonResponse,
    )

    def call(tool, args, unified):
        request = (
            request_factory(body={"tool_name": tool.name, "tool_args": args})
            if unified
            else request_factory(tool.backend_path, args, tool.backend_method)
        )
        if not unified and request.method == "GET":
            args = request.GET.dict()
        return handle(NS(_report_mcp_metric=Mock()), request, tool, args, unified=unified), request

    return call


def log_args(**extra):
    return {"bk_biz_id": "2", "index_set_id": 123, "start_time": "1", "end_time": "2", **extra}


def test_catalog_defaults_and_opt_in_change_version(monkeypatch):
    native = registry.get_tool_registry()
    tool = native.get("search_logs")
    assert len(native) == 89
    assert sum(bool(tool.native_permission) for tool in native.list()) == 88
    assert {tool.name for tool in native.list() if not tool.permission_exempt} == set(registry.NATIVE_PERMISSIONS)
    assert native.get_by_backend("POST", "/api/v4/log_search/search_log/") is tool
    assert native.get_by_backend("GET", "/api/v4/log_search/search_log/") is None
    assert native.get_by_backend("POST", "/api/v4/log_search/search_log.json/") is tool
    assert native.get_by_backend("HEAD", "/api/v4/log_search/get_index_set_list/").name == "list_index_sets"
    assert tool.permission_payload()["system_id"] == "bk_log_search"
    assert tool.permission_payload()["resource_arg"] == "index_set_id"
    assert tool.input_schema["properties"]["target_type"]["enum"] == ["index_set", "scene"]
    assert "table_id_conditions" in tool.input_schema["properties"]
    assert tool.resolve_native_permission({"target_type": "scene"})["action_id"] == "view_business_v2"
    monkeypatch.setattr(settings, "MCP_NATIVE_PERMISSION_TOOLS", [])
    legacy = registry.get_tool_registry()
    assert legacy.catalog_version != native.catalog_version
    assert legacy.get("search_logs").permission_payload() == {
        "action_id": "using_log_mcp",
        "resource_type": "space",
        "resource_arg": "bk_biz_id",
    }
    assert all(not item.native_permission for item in legacy.list())


def test_all_non_exempt_public_tools_have_reviewed_native_permissions():
    catalog = registry.get_tool_registry()
    expected = {}

    def add(names, action, system="bk_monitorv3", resource_type="space", resource_arg="bk_biz_id"):
        for name in names:
            expected[name] = (system, action, resource_type, resource_arg)

    add(
        (
            "list_time_series_groups",
            "list_time_series_metrics",
            "execute_range_query",
            "execute_sql_query",
            "find_relations",
            "find_relations_range",
        ),
        "explore_metric_v2",
    )
    add(
        (
            "get_index_set_fields",
            "search_logs",
            "search_index_set_context",
            "analyze_field",
            "search_log_clustering_pattern",
        ),
        "search_log_v2",
        "bk_log_search",
        "indices",
        "index_set_id",
    )
    add(
        ("list_index_sets", "list_log_scenes", "list_scene_dimension_values", "get_scene_log_fields"),
        "view_business_v2",
        "bk_log_search",
    )
    alert_tools = {tool.name for tool in catalog.list(category="alert")}
    add(alert_tools - {"get_strategy_detail"}, "view_event_v2")
    add(("get_strategy_detail",), "view_rule_v2")
    add(("list_events", "get_event_view_config", "search_event_log"), "explore_metric_v2")
    add(("list_apm_applications", "get_profile_application_service"), "view_business_v2")
    add(
        {tool.name for tool in catalog.list(category="apm")}
        - {"list_apm_applications", "get_profile_application_service"},
        "view_apm_application_v2",
        resource_type="apm_application",
        resource_arg="app_name",
    )
    add(("get_dashboard_tree_list",), "view_dashboard_v2")
    add(
        ("get_dashboard_detail_by_uid",),
        "view_single_dashboard",
        resource_type="grafana_dashboard",
        resource_arg="dashboard_uid",
    )
    add(
        (
            "search_alarm_strategies",
            "get_alarm_strategy",
            "search_alarm_action_configs",
            "get_alarm_action_config",
            "search_alarm_assign_groups",
        ),
        "view_rule_v2",
    )
    add(("search_alarm_shields", "get_alarm_shield"), "view_downtime_v2")
    add(("search_alarm_notice_groups",), "view_notify_team_v2")
    add(
        (
            "list_log_collectors",
            "get_log_collector",
            "get_log_index_set",
            "list_third_party_es_clusters",
            "list_result_tables",
            "list_log_index_set_groups",
        ),
        "view_business_v2",
    )
    add(("preview_log_etl", "get_log_collector_status"), "view_collection_v2")
    add(
        (
            "list_log_extract_topology",
            "search_log_extract_hosts",
            "list_log_extract_allowed_paths",
            "get_log_extract_task",
        ),
        "view_business_v2",
        "bk_log_search",
    )
    add(("list_bcs_clusters",), "view_business_v2")
    add(
        (
            "create_alarm_strategy",
            "update_alarm_strategy",
            "update_alarm_action_config",
            "save_alarm_assign_group",
            "delete_alarm_assign_group",
        ),
        "manage_rule_v2",
    )
    add(("create_alarm_shield", "update_alarm_shield", "disable_alarm_shield"), "manage_downtime_v2")
    add(("create_alarm_notice_group", "update_alarm_notice_group"), "manage_notify_team_v2")
    add(("create_dashboard", "update_dashboard"), "manage_dashboard_v2")
    add(
        (
            "update_log_collector_clean_config",
            "fast_create_log_collector",
            "create_custom_report",
            "create_bkdata_index_set",
            "create_third_party_es",
            "update_custom_report",
            "update_third_party_es",
            "update_bkdata_index_set",
            "fast_update_log_collector",
        ),
        "manage_collection_v2",
    )
    add(("search_log_extract_files",), "view_business_v2", "bk_log_search")
    add(("create_log_extract_task",), "create_client_log_task", "bk_log_search")
    add(("get_log_extract_download_url",), "download_client_log", "bk_log_search")

    protected_tools = {tool.name for tool in catalog.list() if not tool.permission_exempt}
    assert set(expected) == protected_tools == set(registry.NATIVE_PERMISSIONS)
    assert {
        name: tuple(
            registry.NATIVE_PERMISSIONS[name][field]
            for field in (
                "system_id",
                "action_id",
                "resource_type",
                "resource_arg",
            )
        )
        for name in expected
    } == expected


@pytest.mark.parametrize("tool_name", sorted(registry.NATIVE_PERMISSIONS))
@pytest.mark.parametrize(
    "native_result,legacy_allowed",
    [(True, False), (False, True), (False, False), ("error", True)],
)
def test_every_native_tool_uses_strict_native_then_legacy(
    monkeypatch, request_factory, io, tool_name, native_result, legacy_allowed
):
    tool = registry.get_tool_registry().get(tool_name)
    context = {}
    spec = tool.resolve_native_permission(context)
    if spec["resource_type"] == "indices":
        context["index_set_id"] = 123
    elif spec["resource_type"] == "apm_application":
        context["app_name"] = "demo"
        monkeypatch.setattr(
            auth,
            "_apm_application_resource",
            lambda *_args: Resource("bk_monitorv3", "apm_application", "1001", {"name": "demo"}),
        )
    elif spec["resource_type"] == "grafana_dashboard":
        context["dashboard_uid"] = "dash-1"
        monkeypatch.setattr(
            auth,
            "_dashboard_resource",
            lambda *_args: Resource("bk_monitorv3", "grafana_dashboard", "dash-1", {"name": "Demo"}),
        )
    monkeypatch.setattr(auth, "_validate_native_target", Mock())

    def native_decision():
        if native_result == "error":
            raise RuntimeError("private IAM failure")
        return native_result

    io.iam.is_allowed.side_effect = lambda _query: native_decision()
    io.monitor.iam_client.is_allowed.side_effect = lambda query: (
        legacy_allowed if query.action.id == tool.iam_action else native_decision()
    )

    if native_result == "error":
        with pytest.raises(auth.AuthorizationUnavailable):
            auth.permission_state(tool, request_factory(), 2, context)
        assert tool.iam_action not in [
            call.args[0].action.id for call in io.monitor.iam_client.is_allowed.call_args_list
        ]
        return

    result = auth.permission_state(tool, request_factory(), 2, context)
    expected_source = "native" if native_result else "legacy" if legacy_allowed else "none"
    assert result["authorized"] is bool(native_result or legacy_allowed)
    assert result["authorization_source"] == expected_source
    assert result["native_authorized"] is native_result
    assert result["legacy_authorized"] is (None if native_result else legacy_allowed)


def test_conditional_native_permissions_follow_the_actual_query_branch():
    catalog = registry.get_tool_registry()
    log = catalog.get("search_logs")
    event = catalog.get("search_event_log")

    assert log.resolve_native_permission({"target_type": "index_set"})["action_id"] == "search_log_v2"
    assert log.resolve_native_permission({"target_type": "scene"}) == {
        "system_id": "bk_log_search",
        "action_id": "view_business_v2",
        "resource_type": "space",
        "resource_arg": "bk_biz_id",
    }
    assert event.resolve_native_permission({"app_name": "demo", "service_name": "api"}) == {
        "system_id": "bk_monitorv3",
        "action_id": "view_apm_application_v2",
        "resource_type": "apm_application",
        "resource_arg": "app_name",
    }
    assert event.resolve_native_permission({"app_name": "demo"})["action_id"] == "explore_metric_v2"


def test_scene_search_uses_log_business_permission_and_keeps_dynamic_route(request_factory, io):
    tool = registry.get_tool_registry().get("search_logs")
    args = {
        "target_type": "scene",
        "bk_biz_id": "2",
        "table_id_conditions": [[{"field_name": "scene", "value": ["k8s"], "op": "eq"}]],
        "start_time": "1",
        "end_time": "2",
    }

    assert auth.execute_native_tool(tool, args, request_factory()) == {"ok": True}

    query = io.iam.is_allowed.call_args.args[0]
    assert (query.system, query.action.id) == ("bk_log_search", "view_business_v2")
    assert (query.resources[0].system, query.resources[0].type, query.resources[0].id) == (
        "bk_monitorv3",
        "space",
        "2",
    )
    io.catalog.assert_not_called()
    io.dispatch.assert_called_once_with("search_logs", args)


def test_apm_event_branch_uses_application_instance(monkeypatch, request_factory, io):
    resource = Resource(
        "bk_monitorv3",
        "apm_application",
        "1001",
        {"name": "demo", "_bk_iam_path_": "/space,2/"},
    )
    resolve = Mock(return_value=resource)
    monkeypatch.setattr(auth, "_apm_application_resource", resolve)
    tool = registry.get_tool_registry().get("search_event_log")
    args = {
        "bk_biz_id": "2",
        "data_source_label": "custom",
        "data_type_label": "event",
        "table": "demo.event",
        "start_time": "1",
        "end_time": "2",
        "app_name": "demo",
        "service_name": "api",
    }

    assert auth.execute_native_tool(tool, args, request_factory()) == {"ok": True}

    resolve.assert_called_once_with(2, args)
    query = io.monitor.iam_client.is_allowed.call_args.args[0]
    assert (query.action.id, query.resources[0].type, query.resources[0].id) == (
        "view_apm_application_v2",
        "apm_application",
        "1001",
    )


def test_apm_dispatcher_skips_duplicate_check_only_for_matching_native_scope(monkeypatch):
    application_query = NS(values_list=lambda *_args, **_kwargs: NS(first=lambda: 1001))
    permission = Mock()
    check = source_method(
        "kernel_api/unified_mcp/dispatcher.py",
        "_ensure_apm_application_permission",
        Application=NS(objects=NS(filter=lambda **_kwargs: application_query)),
        get_request=lambda **_kwargs: NS(native_mcp_tool="search_spans", mcp_permission_source="legacy"),
        Permission=lambda: permission,
        ActionEnum=NS(VIEW_APM_APPLICATION="view_apm_application_v2"),
        ResourceEnum=NS(APM_APPLICATION=NS(create_simple_instance=lambda value: value)),
        ValidationError=ValidationError,
    )
    native_tool = NS(resolve_native_permission=lambda _args: {"resource_type": "apm_application"})
    monkeypatch.setattr(registry, "get_tool_registry", lambda: NS(get=lambda _name: native_tool))

    check({"bk_biz_id": 2, "app_name": "demo"})
    permission.is_allowed.assert_not_called()

    native_tool.resolve_native_permission = lambda _args: {"resource_type": "space"}
    check({"bk_biz_id": 2, "app_name": "demo"})
    permission.is_allowed.assert_called_once()


def test_instance_native_permissions_remain_unresolved_without_the_instance(request_factory, io):
    catalog = registry.get_tool_registry()
    for name in ("get_apm_filter_fields", "get_dashboard_detail_by_uid"):
        result = auth.permission_state(catalog.get(name), request_factory(), 2)
        assert result["state"] == "requires_resource" and result["authorized"] is False
    io.monitor.iam_client.is_allowed.assert_not_called()


def test_sql_scope_is_validated_before_iam(monkeypatch, request_factory, io):
    scope = Mock(side_effect=ValidationError({"table_id": "foreign table"}))
    metrics_module = ModuleType("kernel_api.resource.metrics")
    metrics_module.ensure_time_series_table_belongs_to_biz = scope
    metrics_module.ensure_sql_reads_declared_table = Mock()
    monkeypatch.setitem(sys.modules, metrics_module.__name__, metrics_module)
    args = {
        "bk_biz_id": "2",
        "table_id": "other.table",
        "sql": "SELECT * FROM other.table",
        "start_time": "1",
        "end_time": "2",
    }

    with pytest.raises(ValidationError, match="foreign table"):
        auth.execute_native_tool(registry.get_tool_registry().get("execute_sql_query"), args, request_factory())

    scope.assert_called_once_with(2, "other.table", allow_platform=False)
    io.monitor.iam_client.is_allowed.assert_not_called()
    io.dispatch.assert_not_called()


def test_sql_query_only_reads_the_declared_single_table():
    import sqlparse
    from sqlparse import sql as sql_nodes
    from sqlparse import tokens as sql_tokens

    validate = source_method(
        "kernel_api/resource/metrics.py",
        "ensure_sql_reads_declared_table",
        sqlparse=sqlparse,
        sql_nodes=sql_nodes,
        sql_tokens=sql_tokens,
        serializers=serializers,
    )
    for statement in (
        "SELECT * FROM db.table",
        "SELECT value FROM `db`.`table` AS source WHERE value > 0",
        "SELECT count(*) FROM db.table LIMIT 10",
    ):
        validate(statement, "db.table")

    for statement in (
        "SELECT * FROM other.table",
        "SELECT * FROM db.table JOIN other.table AS other ON 1=1",
        "SELECT * FROM db.table LEFT JOIN other.table AS other ON 1=1",
        "SELECT * FROM db.table UNION SELECT * FROM other.table",
        "SELECT * FROM (SELECT * FROM db.table) AS source",
        "SELECT * FROM db.table; SELECT * FROM other.table",
        "SELECT * FROM db.table -- hidden source",
        "UPDATE db.table SET value = 1",
    ):
        with pytest.raises(ValidationError):
            validate(statement, "db.table")


def test_apm_and_dashboard_resources_are_resolved_inside_the_requested_business(monkeypatch):
    class APMQuery:
        def values(self, *_fields):
            return self

        def first(self):
            return {"application_id": 1001, "app_name": "demo", "bk_biz_id": 2}

    apm_filter = Mock(return_value=APMQuery())
    apm_models = ModuleType("apm_web.models")
    apm_models.Application = NS(objects=NS(filter=apm_filter))
    monkeypatch.setitem(sys.modules, "apm_web.models", apm_models)

    app = auth._apm_application_resource(2, {"app_name": "demo"})
    assert (app.system, app.type, app.id, app.attribute["_bk_iam_path_"]) == (
        "bk_monitorv3",
        "apm_application",
        "1001",
        "/space,2/",
    )
    apm_filter.assert_called_once_with(bk_biz_id=2, app_name="demo")

    class OrgQuery:
        def values_list(self, *_fields, **_kwargs):
            return [7]

    class DashboardQuery:
        def values(self, *_fields):
            return [{"uid": "dash-1", "title": "Demo"}]

    org_filter = Mock(return_value=OrgQuery())
    dashboard_filter = Mock(return_value=DashboardQuery())
    dashboard_models = ModuleType("bk_dataview.models")
    dashboard_models.Org = NS(objects=NS(filter=org_filter))
    dashboard_models.Dashboard = NS(objects=NS(filter=dashboard_filter))
    monkeypatch.setitem(sys.modules, "bk_dataview.models", dashboard_models)

    dashboard = auth._dashboard_resource(2, {"dashboard_uid": "dash-1"})
    assert (dashboard.system, dashboard.type, dashboard.id, dashboard.attribute["_bk_iam_path_"]) == (
        "bk_monitorv3",
        "grafana_dashboard",
        "dash-1",
        "/space,2/",
    )
    org_filter.assert_called_once_with(name="2")
    dashboard_filter.assert_called_once_with(org_id=7, uid="dash-1", is_folder=0)


def test_sql_native_scope_rejects_platform_tables(monkeypatch):
    group = NS(bk_biz_id=9, bk_data_id=1001)
    groups = NS(objects=NS(filter=lambda **_kwargs: NS(first=lambda: group)))
    platform = Mock(return_value=True)
    data_sources = NS(objects=NS(filter=lambda **_kwargs: NS(exists=platform)))
    validate = source_method(
        "kernel_api/resource/metrics.py",
        "ensure_time_series_table_belongs_to_biz",
        get_request_tenant_id=lambda: "system",
        TimeSeriesGroup=groups,
        DataSource=data_sources,
        serializers=serializers,
    )

    validate(2, "demo.table", allow_platform=True)
    with pytest.raises(ValidationError, match="does not belong"):
        validate(2, "demo.table", allow_platform=False)
    platform.assert_called_once_with()


def test_lookup_metadata_reuses_native_bcs_permission(request_factory):
    request = request_factory()
    tool = NS(native_permission={"action_id": "view_business_v2"})
    execute = Mock(return_value=[{"cluster_id": "demo"}])
    perform = source_method(
        "kernel_api/resource/unified_mcp.py",
        "LookupMetadataResource.perform_request",
        get_tool_registry=lambda: NS(get=lambda name: tool),
        execute_native_tool=execute,
        get_request=lambda: request,
    )

    result = perform(NS(), {"metadata_type": "bcs_clusters", "bk_biz_id": 2})

    assert result == {"metadata_type": "bcs_clusters", "bcs_clusters": [{"cluster_id": "demo"}]}
    execute.assert_called_once_with(tool, {"bk_biz_id": "2"}, request)


def test_public_tools_publish_executable_permission_and_confirmation_contracts():
    catalog = registry.get_tool_registry()
    dashboard = catalog.get("create_dashboard")
    export = catalog.get("create_log_extract_task")

    assert dashboard.risk == "mutation"
    assert dashboard.permission_payload() == {
        "system_id": "bk_monitorv3",
        "action_id": "manage_dashboard_v2",
        "resource_type": "space",
        "resource_arg": "bk_biz_id",
        "mode": "native_then_legacy",
        "fallback_system_id": "bk_monitorv3",
        "fallback_action_id": "using_dashboard_mcp",
        "fallback_resource_type": "space",
        "fallback_resource_arg": "bk_biz_id",
        "fallback_on": "explicit_denial_only",
    }
    assert dashboard.requires_confirmation is True and dashboard.forwards_confirmation is False
    assert dashboard.input_schema["properties"]["configs"]["type"] == "object"
    assert dashboard.input_schema["properties"]["configs"]["additionalProperties"] == {"type": "string"}
    assert export.risk == "data_export"
    assert export.permission_payload()["system_id"] == "bk_log_search"
    assert export.permission_payload()["action_id"] == "create_client_log_task"
    assert export.permission_payload()["fallback_action_id"] == "using_log_extract_mcp"
    assert export.requires_confirmation is True and export.forwards_confirmation is False
    schema = dashboard.schema_payload(catalog.catalog_version)
    assert schema["execution"] == {
        "status": "executable",
        "requires_confirmation": True,
        "reason": "",
    }
    assert schema["input_schema"]["properties"]["confirm"]["enum"] == [True]
    assert "confirm" in schema["input_schema"]["required"]
    assert "用户明确确认" in schema["guidelines"][0]


def test_public_schema_converts_openapi_nullable_to_json_schema_null():
    catalog = registry.get_tool_registry()
    strategy_schema = catalog.get("update_alarm_strategy").input_schema["properties"]
    third_party_schema = catalog.get("update_third_party_es").input_schema["properties"]

    for schema in (strategy_schema["priority"], strategy_schema["issue_config"], third_party_schema["time_field_unit"]):
        assert "nullable" not in schema
        Draft7Validator(schema).validate(None)
    assert None in third_party_schema["time_field_unit"]["enum"]


def test_catalog_version_tracks_schema_normalization_version(monkeypatch):
    source_root = BASE / "support-files/apigw/resources/internal/user"
    original_version = registry.load_tool_registry(source_root).catalog_version

    monkeypatch.setattr(registry, "SCHEMA_NORMALIZATION_VERSION", registry.SCHEMA_NORMALIZATION_VERSION + 1)

    assert registry.load_tool_registry(source_root).catalog_version != original_version


def test_standard_tools_reuse_original_mcp_and_route_permissions():
    catalog = registry.get_tool_registry()
    log_collection = catalog.get("list_log_collectors")
    metadata_discovery = catalog.get("search_spaces")

    assert log_collection.legacy_action_ids == ("using_log_collection_mcp", "view_business_v2")
    assert log_collection.permission_payload() == {
        "system_id": "bk_monitorv3",
        "action_id": "view_business_v2",
        "resource_type": "space",
        "resource_arg": "bk_biz_id",
        "mode": "native_then_legacy",
        "fallback_system_id": "bk_monitorv3",
        "fallback_action_id": "using_log_collection_mcp",
        "fallback_resource_type": "space",
        "fallback_resource_arg": "bk_biz_id",
        "fallback_on": "explicit_denial_only",
    }
    assert metadata_discovery.permission_exempt is True
    assert metadata_discovery.permission_payload() == {
        "mode": "exempt",
        "reason": "platform-visible metadata discovery",
    }


def test_registry_rejects_unreviewed_mcp_source_file(tmp_path):
    source_root = BASE / "support-files/apigw/resources/internal/user"
    for filenames in registry.SOURCE_FILES.values():
        for filename in filenames:
            (tmp_path / filename).symlink_to(source_root / filename)
    (tmp_path / "future_mcp.yaml").write_text("paths: {}")

    with pytest.raises(RuntimeError, match="source-file drift"):
        registry.load_tool_registry(tmp_path)


def test_private_mcp_sources_are_not_part_of_tool_search():
    catalog = registry.get_tool_registry()
    assert registry.IGNORED_SOURCE_FILES == {
        "openclaw_recovering_mcp.yaml",
        "operation_mcp.yaml",
        "ops_mcp.yaml",
    }
    assert "operation" not in registry.CATEGORIES
    from constants.mcp import get_mcp_permission_action_by_server_name

    assert get_mcp_permission_action_by_server_name("bk-monitor-prod-operation") == "using_operation_mcp"
    for tool_name in (
        "search_openclaw_spans",
        "get_openclaw_trace_detail",
        "search_openclaw_logs",
        "query_datalink_metadata",
        "query_data_link_info",
        "diagnose_metadata_datalink",
        "get_data_link_metadata",
        "list_operation_metrics",
        "get_operation_metric",
        "get_operation_overview",
    ):
        with pytest.raises(KeyError):
            catalog.get(tool_name)


def test_unified_openapi_filters_cover_the_full_catalog_taxonomy():
    document = yaml.safe_load((BASE / "support-files/apigw/resources/internal/user/unified_mcp.yaml").read_text())
    paths = document["paths"]
    tool_properties = paths["/mcp/lookup_tool/"]["post"]["requestBody"]["content"]["application/json"]["schema"][
        "properties"
    ]
    permission_properties = paths["/mcp/lookup_permissions/"]["post"]["requestBody"]["content"]["application/json"][
        "schema"
    ]["properties"]

    assert tool_properties["category"]["enum"] == list(registry.CATEGORIES)
    assert permission_properties["category"]["enum"] == list(registry.CATEGORIES)
    assert set(tool_properties["capability"]["enum"]) == {
        capability for capabilities in registry.CAPABILITIES.values() for capability in capabilities
    }


def test_unified_facade_descriptions_publish_agent_workflow():
    document = yaml.safe_load((BASE / "support-files/apigw/resources/internal/user/unified_mcp.yaml").read_text())

    def description(tool_name):
        return document["paths"][f"/mcp/{tool_name}/"]["post"]["description"]

    lookup = description("lookup_tool")
    assert "tool_name only accepts an exact registered ID" in lookup
    assert "call lookup_tool_schema before execute_tool" in lookup
    assert "required_context and prerequisites" in lookup

    schema = description("lookup_tool_schema")
    assert "current catalog_version" in schema
    assert "use lookup_metadata for spaces/BCS clusters" in schema
    assert "mutation or data-export tools" in schema

    metadata = description("lookup_metadata")
    assert "never invent or infer a business ID" in metadata
    assert "prerequisite tools returned by lookup_tool_schema" in metadata

    permissions = description("lookup_permissions")
    assert "Do not call it before every ordinary read-only query" in permissions
    assert "requires_resource means unresolved, not granted" in permissions
    assert "Never open or submit an application automatically" in permissions

    execute = description("execute_tool")
    assert "never guess IDs or permission actions" in execute
    assert "explicit user confirmation and confirm=true" in execute
    assert "verify both the transport envelope and the business result" in execute


def test_dispatcher_contains_every_public_catalog_tool():
    tree = ast.parse((BASE / "kernel_api/unified_mcp/dispatcher.py").read_text())
    assignment = next(
        node
        for node in tree.body
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", None) == "TOOL_EXECUTORS"
    )
    dispatcher_names = {ast.literal_eval(key) for key in assignment.value.keys}

    assert dispatcher_names == registry.EXECUTABLE_TOOL_NAMES


def test_dispatcher_emits_bounded_tool_flow_without_payload(caplog):
    caplog.set_level(logging.INFO, logger=auth.__name__)
    executor = Mock(return_value={"ok": True})
    dispatch = source_method(
        "kernel_api/unified_mcp/dispatcher.py",
        "dispatch_tool",
        TOOL_EXECUTORS={"search_logs": executor},
        time=time,
        logging=logging,
    )

    result = dispatch("search_logs", {"query_string": "private-query"})

    assert result == {"ok": True}
    records = [row.getMessage() for row in caplog.records if row.getMessage().startswith("MCP_TOOL:")]
    assert [record.split(" ", 2)[1] for record in records] == [
        "event=dispatch_started",
        "event=dispatch_finished",
    ]
    assert '"decision": "succeeded"' in records[-1]
    assert "private-query" not in "\n".join(records)


def test_dispatcher_logs_failure_type_without_exception_text(caplog):
    caplog.set_level(logging.INFO, logger=auth.__name__)
    dispatch = source_method(
        "kernel_api/unified_mcp/dispatcher.py",
        "dispatch_tool",
        TOOL_EXECUTORS={"search_logs": Mock(side_effect=ValueError("private-error"))},
        time=time,
        logging=logging,
    )

    with pytest.raises(ValueError, match="private-error"):
        dispatch("search_logs", {})

    record = [row.getMessage() for row in caplog.records if "event=dispatch_finished " in row.getMessage()][-1]
    assert record.startswith("MCP_TOOL: event=dispatch_finished ")
    assert '"decision": "failed"' in record and '"error_type": "ValueError"' in record
    assert "private-error" not in record


@pytest.mark.parametrize(
    "names",
    [
        ["search_spaces"],
        ["get_operation_metric"],
        ["typo"],
        "search_logs",
        [True],
        None,
        "",
        0,
    ],
)
def test_invalid_opt_in_does_not_silently_fall_back(monkeypatch, names):
    monkeypatch.setattr(settings, "MCP_NATIVE_PERMISSION_TOOLS", names)
    with pytest.raises(ImproperlyConfigured):
        registry.get_tool_registry()


@pytest.mark.parametrize("redis_enabled", [False, True])
def test_dynamic_configuration_round_trip_rebuilds_catalog(monkeypatch, redis_enabled):
    # Evaluate only the two real registrations, without unrelated project settings.
    tree = ast.parse((BASE / "bkmonitor/define/global_config.py").read_text())
    defaults = {"MCP_NATIVE_PERMISSION_TOOLS": [], "MCP_LOG_IAM_PROFILE": {}}
    fields = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Tuple) and len(node.elts) == 2:
            key = node.elts[0]
            if isinstance(key, ast.Constant) and key.value in defaults:
                fields[key.value] = eval(
                    compile(ast.Expression(node.elts[1]), "global_config.py", "eval"), {"slz": serializers}
                )
    assert set(fields) == set(defaults)
    for name, field in fields.items():
        assert field.default == defaults[name]
        # init_or_update_global_config persists these kwargs into GlobalConfig.options.
        assert json.loads(json.dumps(field._kwargs))["default"] == defaults[name]
    static_tree = ast.parse((BASE / "config/default.py").read_text())
    for node in static_tree.body:
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", None) in defaults:
            assert ast.literal_eval(node.value) == defaults[node.target.id]

    module = ModuleType("bkmonitor.define.global_config")
    module.GLOBAL_CONFIGS = list(fields)
    monkeypatch.setitem(sys.modules, module.__name__, module)
    import bkmonitor.define

    monkeypatch.setattr(bkmonitor.define, "global_config", module, raising=False)
    locmem = LocMemCache("mcp-dynamic-test", {})
    redis = LocMemCache("mcp-dynamic-redis-test", {}) if redis_enabled else None
    locmem.clear()
    if redis is not None:
        redis.clear()
    dynamic_class = source_method(
        "bkmonitor/utils/dynamic_settings.py",
        "DynamicSettings",
        locmem_cache=locmem,
        redis_cache=redis,
        json=json,
        logger=logging.getLogger("test"),
    )
    db = {}
    model = NS(get=lambda key, default, **kwargs: db.get(key, default), set=lambda key, value: db.update({key: value}))
    wrapped = NS(**defaults, BASE_DIR=str(BASE), BK_IAM_SYSTEM_ID="bk_monitorv3")
    dynamic = dynamic_class(wrapped, model)
    monkeypatch.setattr(registry, "settings", dynamic)

    legacy = registry.get_tool_registry()
    enabled = ["execute_range_query", "search_logs", "search_index_set_context"]
    dynamic.MCP_NATIVE_PERMISSION_TOOLS = enabled
    assert db["MCP_NATIVE_PERMISSION_TOOLS"] == enabled
    assert locmem.get("MCP_NATIVE_PERMISSION_TOOLS") is None
    if redis is not None:
        assert redis.get("MCP_NATIVE_PERMISSION_TOOLS") is None
    native = registry.get_tool_registry()
    if redis is not None:
        assert json.loads(redis.get("MCP_NATIVE_PERMISSION_TOOLS")) == enabled
        locmem.clear()
        assert dynamic.MCP_NATIVE_PERMISSION_TOOLS == enabled
    assert native.catalog_version != legacy.catalog_version
    for name in enabled:
        assert native.get(name).permission_payload()["mode"] == "native_then_legacy"
    assert native.get("search_logs").input_schema["properties"]["target_type"]["enum"] == ["index_set", "scene"]
    assert native.get("execute_sql_query").native_permission is None

    profile = {"mode": "v3-current", "gateway_url": "https://iam.invalid/"}
    dynamic.MCP_LOG_IAM_PROFILE = profile
    assert dynamic.MCP_LOG_IAM_PROFILE == db["MCP_LOG_IAM_PROFILE"] == profile
    dynamic.MCP_NATIVE_PERMISSION_TOOLS = []
    rollback = registry.get_tool_registry()
    assert rollback.catalog_version == legacy.catalog_version
    assert all(not tool.native_permission for tool in rollback.list())
    assert "scene" in rollback.get("search_logs").input_schema["properties"]["target_type"]["enum"]


@pytest.fixture
def permission_lookup(request_factory, io):
    request = request_factory()
    mixed = source_method(
        "kernel_api/resource/unified_mcp.py",
        "_mixed_permission_scopes",
        get_request=lambda: request,
        _permission_state_by_action=source_method("kernel_api/resource/unified_mcp.py", "_permission_state_by_action"),
        permission_state=auth.permission_state,
        get_action_by_id=lambda action: NS(name=action),
        ResourceEnum=NS(BUSINESS=NS(create_simple_instance=auth._business_resource)),
    )
    cls = source_method(
        "kernel_api/resource/unified_mcp.py",
        "LookupPermissionsResource",
        Resource=object,
        serializers=serializers,
        CATEGORIES=registry.CATEGORIES,
        CATEGORY_ACTIONS=registry.CATEGORY_ACTIONS,
        get_tool_registry=registry.get_tool_registry,
        ValidationError=ValidationError,
        get_permission_client=lambda: io.monitor,
        _mixed_permission_scopes=mixed,
        get_action_by_id=lambda action: NS(name=action),
        ResourceEnum=NS(BUSINESS=NS(create_simple_instance=auth._business_resource)),
    )

    def lookup(**params):
        serializer = cls.RequestSerializer(data=params)
        serializer.is_valid(raise_exception=True)
        return cls().perform_request(serializer.validated_data)

    return lookup


def test_permission_lookup_preserves_exempt_space_discovery(permission_lookup, io):
    result = permission_lookup(tool_name="search_spaces")

    assert result["authorized"] is True
    assert result["scopes"] == [
        {
            "category": "metadata",
            "tool_name": "search_spaces",
            "state": "exempt",
            "authorized": True,
        }
    ]
    io.monitor.is_allowed_by_biz.assert_not_called()
    io.monitor.filter_space_list_by_action.assert_not_called()


def test_permission_lookup_reuses_original_route_action_with_legacy_fallback(permission_lookup, io):
    io.monitor.iam_client.is_allowed.side_effect = lambda query: query.action.id == "using_log_collection_mcp"

    result = permission_lookup(bk_biz_id=2, tool_name="list_log_collectors")

    scope = result["scopes"][0]
    assert result["authorized"] is True
    assert scope["action_id"] == "view_business_v2"
    assert scope["native_authorized"] is False
    assert scope["legacy_authorized"] is True
    assert scope["authorization_source"] == "legacy"


@pytest.mark.parametrize("tool_name", ["search_logs", "search_index_set_context"])
def test_permission_context_explains_disabled_native_mode(monkeypatch, permission_lookup, io, tool_name):
    monkeypatch.setattr(settings, "MCP_NATIVE_PERMISSION_TOOLS", [])
    with pytest.raises(ValidationError) as error:
        permission_lookup(bk_biz_id=2, tool_name=tool_name, resource_context={"index_set_id": 123})
    assert "MCP_NATIVE_PERMISSION_TOOLS" in str(error.value.detail)
    assert "using_log_mcp" in str(error.value.detail)
    io.iam.is_allowed.assert_not_called()
    io.monitor.is_allowed_by_biz.assert_not_called()
    # Omitting instance context remains a legacy permission probe, not a native grant.
    io.monitor.is_allowed_by_biz.return_value = True
    result = permission_lookup(bk_biz_id=2, tool_name=tool_name)
    assert result["authorized"] is True
    assert result["scopes"][0]["action_id"] == "using_log_mcp"


@pytest.mark.parametrize("tool_name", ["search_logs", "search_index_set_context"])
@pytest.mark.parametrize("native_allowed,legacy_allowed", [(True, False), (False, True), (False, False)])
def test_permission_context_reports_source_and_apply_links(
    permission_lookup, io, tool_name, native_allowed, legacy_allowed
):
    io.iam.is_allowed.return_value = native_allowed
    io.monitor.iam_client.is_allowed.side_effect = lambda query: legacy_allowed
    result = permission_lookup(
        bk_biz_id=2,
        tool_name=tool_name,
        resource_context={"target_type": "index_set", "index_set_id": 123},
        include_apply_guide=True,
    )
    scope = result["scopes"][0]
    assert scope["resource"] == {"bk_biz_id": "2", "index_set_id": "123"}
    assert scope["authorization_source"] == ("native" if native_allowed else "legacy" if legacy_allowed else "none")
    assert result["authorized"] == (native_allowed or legacy_allowed)
    assert bool(result["missing_permissions"]) == (not result["authorized"])
    if not result["authorized"]:
        assert scope["action_id"] == "search_log_v2"
        assert scope["apply_url"] == "https://iam.invalid/log-apply"
        assert scope["legacy_permission"]["apply_url"] == "https://iam.invalid/monitor-apply"
    else:
        assert "apply_url" not in scope
    if native_allowed:
        io.monitor.iam_client.is_allowed.assert_not_called()


def test_permission_context_rejects_mismatch_and_keeps_missing_instance_unresolved(permission_lookup, io):
    with pytest.raises(ValidationError, match="does not match"):
        permission_lookup(bk_biz_id=2, tool_name="search_logs", resource_context={"alert_id": "123"})
    result = permission_lookup(bk_biz_id=2, tool_name="search_logs")
    assert result["authorized"] is False
    assert result["scopes"][0]["state"] == "requires_resource"
    io.iam.is_allowed.assert_not_called()
    io.monitor.iam_client.is_allowed.assert_not_called()


@pytest.mark.parametrize("begin", [-10, 0, 10])
def test_log_context_preserves_position_and_checks_space_before_backend(begin):
    params = {
        "bk_biz_id": "2",
        "index_set_id": 123,
        "zero": True,
        "begin": str(begin),
        "size": "10",
        "dtEventTimeStamp": "1788783672000",
        "serverIp": "localhost",
        "gseIndex": "12",
        "iterationIndex": "1",
        "path": "/logs/app.log",
    }
    backend = Mock(return_value={"list": []})
    resource = source_method(
        "kernel_api/resource/log_search.py",
        "SearchIndexSetContextResource",
        Resource=object,
        serializers=serializers,
        logger=logging.getLogger("test"),
        call_log_api=backend,
    )
    serializer = resource.RequestSerializer(data=params)
    serializer.is_valid(raise_exception=True)
    catalog = Mock(return_value=[{"index_set_id": 123}])
    ensure_scope = source_method(
        "kernel_api/unified_mcp/dispatcher.py",
        "_ensure_index_set_belongs_to_biz",
        GetIndexSetListResource=lambda: NS(request=catalog),
        ValidationError=ValidationError,
        _index_set_ids=source_method("kernel_api/unified_mcp/dispatcher.py", "_index_set_ids"),
    )
    dispatch = source_method(
        "kernel_api/unified_mcp/dispatcher.py",
        "_log_resource_executor",
        _ensure_index_set_belongs_to_biz=ensure_scope,
    )(lambda: NS(request=lambda **kwargs: resource().perform_request(kwargs)))
    assert dispatch(serializer.validated_data) == {"list": []}
    backend.assert_called_once_with("search_index_set_context", **serializer.validated_data)
    assert backend.call_args.kwargs["begin"] == begin
    assert backend.call_args.kwargs["gseIndex"] == "12"
    backend.reset_mock()
    catalog.return_value = []
    with pytest.raises(ValidationError, match="does not belong"):
        dispatch(serializer.validated_data)
    backend.assert_not_called()


def test_log_uses_native_system_subject_instance_and_path(request_factory, io):
    request = request_factory()
    result = auth.execute_native_tool(registry.get_tool_registry().get("search_logs"), log_args(), request)
    assert result == {"ok": True}
    query = io.iam.is_allowed.call_args.args[0]
    assert (query.system, query.subject.id, query.action.id) == ("bk_log_search", "alice", "search_log_v2")
    assert (query.resources[0].system, query.resources[0].type, query.resources[0].id) == (
        "bk_log_search",
        "indices",
        "123",
    )
    assert query.resources[0].attribute["_bk_iam_path_"] == "/space,2/"
    assert request.skip_check is False
    assert request.native_mcp_tool is None
    io.monitor.is_allowed_by_biz.assert_not_called()
    io.dispatch.assert_called_once_with("search_logs", log_args())


def test_native_denial_is_not_bypassed_by_old_checked_flag(request_factory, io):
    io.iam.is_allowed.return_value = False
    request = request_factory()
    with pytest.raises(PermissionDenied) as error:
        auth.execute_native_tool(registry.get_tool_registry().get("search_logs"), log_args(), request)
    assert error.value.detail["action_id"] == "search_log_v2"
    assert error.value.detail["permission"]["system_id"] == "bk_log_search"
    assert error.value.detail["apply_url"] == "https://iam.invalid/log-apply"
    assert error.value.detail["native_authorized"] is False
    assert error.value.detail["legacy_authorized"] is False
    assert error.value.detail["authorized"] is False
    io.dispatch.assert_not_called()


@pytest.mark.parametrize(
    "case",
    [
        "unverified",
        "other_user",
        "anonymous",
        "missing_tenant",
        "missing_jwt",
        "wrong_tenant",
        "wrong_business",
        "no_space",
    ],
)
def test_identity_and_tenant_fail_closed(monkeypatch, request_factory, io, case):
    request = request_factory()
    if case == "unverified":
        request.jwt.user["verified"] = False
    if case == "other_user":
        request.jwt.user["username"] = "bob"
    if case == "anonymous":
        request.user.is_authenticated = False
    if case == "missing_tenant":
        request.user.tenant_id = ""
    if case == "missing_jwt":
        request.jwt = None
    if case == "wrong_tenant":
        monkeypatch.setattr(settings, "ENABLE_MULTI_TENANT_MODE", True)
        request.META["HTTP_X_BK_TENANT_ID"] = "other"
    if case == "wrong_business":
        monkeypatch.setattr(tenant, "is_biz_in_tenant", lambda *args: False)
    if case == "no_space":
        monkeypatch.setattr("bkm_space.utils.bk_biz_id_to_space_uid", lambda *args: None)
    with pytest.raises(PermissionDenied):
        auth.execute_native_tool(registry.get_tool_registry().get("search_logs"), log_args(), request)
    io.catalog.assert_not_called()
    io.dispatch.assert_not_called()


@pytest.mark.parametrize(
    "change",
    [
        {"is_platform_index": True},
        {"is_platform_index": None},
        {"is_group": True},
        {"platform_index_owner_space_uid": "bkcc__9"},
        {"bk_biz_id": 9},
        {"space_uid": "bkcc__9"},
        {"index_set_id": 456},
    ],
)
@pytest.mark.parametrize("standalone", [False, True])
def test_unsupported_or_foreign_indices_do_not_query(native_http, io, change, standalone):
    io.monitor.iam_client.is_allowed.side_effect = lambda query: True
    io.catalog.return_value[0].update(change)
    args = log_args(index_set_id="123" if standalone else 123)
    response, _ = native_http(registry.get_tool_registry().get("search_logs"), args, unified=not standalone)
    assert response.status_code in {400, 403}
    io.catalog.assert_called_once()
    io.iam.is_allowed.assert_not_called()
    io.monitor.iam_client.is_allowed.assert_not_called()
    io.dispatch.assert_not_called()


def test_duplicate_catalog_match_is_rejected(request_factory, io):
    io.catalog.return_value *= 2
    with pytest.raises(PermissionDenied):
        auth.execute_native_tool(registry.get_tool_registry().get("search_logs"), log_args(), request_factory())
    io.dispatch.assert_not_called()


@pytest.mark.parametrize(
    "extra",
    [
        {"skip_check": True},
        {"bk_username": "bob"},
        {"bk_tenant_id": "other"},
        {"target_type": "scene"},
        {"table_id_conditions": []},
        {"index_set_id": True},
        {"bk_biz_id": "0"},
    ],
)
def test_bad_or_server_owned_parameters_are_rejected(request_factory, io, extra):
    with pytest.raises(ValidationError):
        auth.execute_native_tool(registry.get_tool_registry().get("search_logs"), log_args(**extra), request_factory())
    io.dispatch.assert_not_called()


@pytest.mark.parametrize("case", ["async", "query_conflict", "form", "head"])
def test_transport_cannot_bypass_authorization(request_factory, io, case):
    request = request_factory()
    if case == "async":
        request.META["HTTP_X_ASYNC_TASK"] = "0"
    if case == "query_conflict":
        request.GET = request.GET.copy()
        request.GET["bk_biz_id"] = "9"
    if case == "form":
        request.content_type = "application/x-www-form-urlencoded"
    if case == "head":
        request.method = "HEAD"
    with pytest.raises(ValidationError):
        auth.execute_native_tool(registry.get_tool_registry().get("search_logs"), log_args(), request)
    io.iam.is_allowed.assert_not_called()
    io.dispatch.assert_not_called()


def test_get_and_aggregate_share_normalized_log_arguments(native_http, io):
    tool = registry.get_tool_registry().get("get_index_set_fields")
    response, request = native_http(tool, {"bk_biz_id": "2", "index_set_id": "123"}, unified=False)
    assert request.method == "GET"
    assert response.status_code == 200
    assert request.mcp_usage_tool == "get_index_set_fields"
    io.dispatch.assert_called_once_with(tool.name, {"bk_biz_id": "2", "index_set_id": 123})


@pytest.mark.parametrize("value", [None, "false", 1])
def test_non_boolean_iam_result_is_not_permission(request_factory, io, value):
    io.iam.is_allowed.return_value = value
    with pytest.raises(auth.AuthorizationUnavailable):
        auth.execute_native_tool(registry.get_tool_registry().get("search_logs"), log_args(), request_factory())
    io.dispatch.assert_not_called()


def test_iam_failure_is_unavailable_without_legacy_fallback(request_factory, io):
    io.iam.is_allowed.side_effect = RuntimeError("private upstream details")
    with pytest.raises(auth.AuthorizationUnavailable) as error:
        auth.execute_native_tool(registry.get_tool_registry().get("search_logs"), log_args(), request_factory())
    assert "private upstream" not in str(error.value)
    io.dispatch.assert_not_called()


def test_metrics_use_original_monitor_action(request_factory, io):
    tool = registry.get_tool_registry().get("list_time_series_groups")
    assert auth.execute_native_tool(tool, {"bk_biz_id": "2"}, request_factory()) == {"ok": True}
    query = io.monitor.iam_client.is_allowed.call_args.args[0]
    assert (query.system, query.action.id, query.resources[0].id) == ("bk_monitorv3", "explore_metric_v2", "2")
    io.monitor.is_allowed_by_biz.assert_not_called()
    io.iam.is_allowed.assert_not_called()


def test_log_directory_checks_log_action_with_external_space(request_factory, io, caplog):
    caplog.set_level(logging.INFO, logger=auth.__name__)
    tool = registry.get_tool_registry().get("list_index_sets")
    auth.execute_native_tool(tool, {"bk_biz_id": "2"}, request_factory())
    query = io.iam.is_allowed.call_args.args[0]
    assert query.system == "bk_log_search" and query.action.id == "view_business_v2"
    assert query.resources[0].system == "bk_monitorv3" and query.resources[0].type == "space"
    check = next(row for row in audit_records(caplog) if row["phase"] == "native")
    assert check["system_id"] == "bk_log_search" and check["resource_system"] == "bk_monitorv3"


@pytest.mark.parametrize(
    "profile", [{}, {"mode": "v4"}, {"mode": "union"}, {"mode": "v3-current", "gateway_url": "file:///etc/config"}]
)
def test_log_model_must_be_explicit(monkeypatch, request_factory, profile):
    monkeypatch.setattr(settings, "MCP_LOG_IAM_PROFILE", profile)
    with pytest.raises(ImproperlyConfigured):
        auth._log_iam(request_factory().user)


@pytest.mark.parametrize(
    "system,kind,resource_id",
    [("bk_monitorv3", "space", "9"), ("other", "space", "2"), ("bk_monitorv3", "indices", "2")],
)
def test_business_resource_cannot_change_authorized_identity(monkeypatch, system, kind, resource_id):
    module = ModuleType("bkmonitor.iam")
    module.ResourceEnum = NS(BUSINESS=NS(create_simple_instance=lambda biz: Resource(system, kind, resource_id, {})))
    monkeypatch.setitem(sys.modules, module.__name__, module)
    with pytest.raises(auth.AuthorizationUnavailable):
        auth._business_resource(2)


def test_log_client_uses_monitor_credentials_not_log_secret(request_factory):
    client = auth._log_iam(request_factory().user)
    assert client._client._app_code == "monitor-saas"
    assert client._client._bk_tenant_id == "system"
    assert settings.BK_IAM_SYSTEM_ID == "bk_monitorv3"


def test_missing_business_never_claims_unscoped_native_metric_access(request_factory, io):
    result = auth.permission_state(registry.get_tool_registry().get("execute_range_query"), request_factory())
    assert result["state"] == "requires_resource" and result["authorized"] is False
    io.monitor.is_allowed_by_biz.assert_not_called()
    io.monitor.filter_space_list_by_action.assert_not_called()


def test_missing_instance_is_discoverable_but_not_authorized(request_factory, io):
    result = auth.permission_state(registry.get_tool_registry().get("search_logs"), request_factory(), 2)
    assert result["state"] == "requires_resource" and result["authorized"] is False
    io.iam.is_allowed.assert_not_called()
    io.catalog.assert_not_called()


def test_execution_marker_is_restored_after_failure(request_factory, io):
    request = request_factory()
    io.dispatch.side_effect = RuntimeError("query failed")
    with pytest.raises(RuntimeError):
        auth.execute_native_tool(registry.get_tool_registry().get("search_logs"), log_args(), request)
    assert request.native_mcp_tool is None


@pytest.mark.parametrize("suffix", ["/", ".json/"])
@pytest.mark.parametrize(
    "tool_name,args",
    [
        ("search_logs", log_args()),
        ("execute_range_query", {"bk_biz_id": "2", "start_time": "1", "end_time": "2", "promql": "test_metric"}),
        ("list_alerts", {"bk_biz_id": "2", "start_time": "1", "end_time": "2"}),
    ],
)
def test_standalone_and_unified_middleware_route_from_same_catalog(
    monkeypatch, request_factory, io, suffix, tool_name, args
):
    for name in ("bkmonitor.iam", "bkmonitor.iam.action", "bkmonitor.iam.drf"):
        monkeypatch.setitem(sys.modules, name, ModuleType(name))
    legacy = Mock(side_effect=AssertionError("legacy permission must not be called"))
    sys.modules["bkmonitor.iam.action"].get_action_by_id = legacy
    sys.modules["bkmonitor.iam.drf"].MCPPermission = legacy
    handle = source_method(
        "kernel_api/middlewares/authentication.py",
        "AuthenticationMiddleware._handle_mcp_auth",
        logger=logging.getLogger("test"),
        json=json,
        settings=settings,
        time=time,
        secrets=secrets,
        log_mcp_event=auth.log_mcp_event,
        log_mcp_tool_event=auth.log_mcp_tool_event,
        HttpResponseForbidden=HttpResponseForbidden,
    )
    delegate = Mock(
        side_effect=lambda request, tool, args, unified=False: auth.execute_native_tool(
            tool, args if unified else tool.normalize_standalone_args(args), request
        )
    )
    extract = source_method(
        "kernel_api/middlewares/authentication.py", "AuthenticationMiddleware.extract_tool_name_from_path"
    )
    middleware = NS(extract_tool_name_from_path=extract, _handle_native_mcp=delegate)
    tool = registry.get_tool_registry().get(tool_name)
    standalone_args = dict(args)
    if "index_set_id" in standalone_args:
        standalone_args["index_set_id"] = str(standalone_args["index_set_id"])
    if tool.backend_derived_fields:
        standalone_args["bk_biz_ids"] = [args["bk_biz_id"]]
    standalone = request_factory(tool.backend_path.rstrip("/") + suffix, standalone_args)
    standalone.META["HTTP_X_BKAPI_PERMISSION_ACTION"] = "using_dashboard_mcp"
    aggregate = request_factory(
        "/api/v4/unified_mcp/execute_tool" + suffix, body={"tool_name": tool_name, "tool_args": args}
    )
    assert handle(middleware, standalone, "alice") == {"ok": True}
    assert handle(middleware, aggregate, "alice") == {"ok": True}
    assert [call.args[1].name for call in delegate.call_args_list] == [tool_name, tool_name]
    assert delegate.call_args_list[1].kwargs["unified"] is True
    assert io.iam.is_allowed.call_count + io.monitor.iam_client.is_allowed.call_count == 2
    assert all(call.args == (tool_name, args) for call in io.dispatch.call_args_list)
    legacy.assert_not_called()


def test_middleware_preserves_exempt_space_discovery(monkeypatch, request_factory):
    for name in ("bkmonitor.iam", "bkmonitor.iam.action", "bkmonitor.iam.drf"):
        monkeypatch.setitem(sys.modules, name, ModuleType(name))
    legacy = Mock(side_effect=AssertionError("exempt tool must not query permissions"))
    sys.modules["bkmonitor.iam.action"].get_action_by_id = legacy
    sys.modules["bkmonitor.iam.drf"].MCPPermission = legacy
    handle = source_method(
        "kernel_api/middlewares/authentication.py",
        "AuthenticationMiddleware._handle_mcp_auth",
        logger=logging.getLogger("test"),
        logging=logging,
        json=json,
        settings=settings,
        time=time,
        secrets=secrets,
        log_mcp_event=auth.log_mcp_event,
        log_mcp_tool_event=auth.log_mcp_tool_event,
        HttpResponseForbidden=HttpResponseForbidden,
    )
    extract = source_method(
        "kernel_api/middlewares/authentication.py", "AuthenticationMiddleware.extract_tool_name_from_path"
    )
    report = Mock()
    request = request_factory(
        "/api/v4/unified_mcp/execute_tool/",
        body={"tool_name": "search_spaces", "tool_args": {"space_name": "demo"}},
    )

    response = handle(NS(extract_tool_name_from_path=extract, _report_mcp_metric=report), request, "alice")

    assert response is None
    assert request.unified_mcp_permission_checked is True
    assert len(request.mcp_usage_event_id) == 32
    assert request.mcp_usage_tool == "search_spaces"
    assert request.mcp_usage_target_tool == ""
    report.assert_called_once()
    legacy.assert_not_called()


def test_middleware_keeps_facade_and_target_tool_separate(monkeypatch, request_factory):
    for name in ("bkmonitor.iam", "bkmonitor.iam.action", "bkmonitor.iam.drf"):
        monkeypatch.setitem(sys.modules, name, ModuleType(name))
    legacy = Mock(side_effect=AssertionError("facade tool must not query permissions"))
    sys.modules["bkmonitor.iam.action"].get_action_by_id = legacy
    sys.modules["bkmonitor.iam.drf"].MCPPermission = legacy
    handle = source_method(
        "kernel_api/middlewares/authentication.py",
        "AuthenticationMiddleware._handle_mcp_auth",
        logger=logging.getLogger("test"),
        logging=logging,
        json=json,
        settings=settings,
        time=time,
        secrets=secrets,
        log_mcp_event=auth.log_mcp_event,
        log_mcp_tool_event=auth.log_mcp_tool_event,
        HttpResponseForbidden=HttpResponseForbidden,
    )
    extract = source_method(
        "kernel_api/middlewares/authentication.py", "AuthenticationMiddleware.extract_tool_name_from_path"
    )
    request = request_factory(
        "/api/v4/unified_mcp/lookup_tool_schema/",
        body={"tool_name": "search_logs"},
    )

    response = handle(NS(extract_tool_name_from_path=extract, _report_mcp_metric=Mock()), request, "alice")

    assert response is None
    assert request.mcp_usage_operation == request.mcp_usage_tool == "lookup_tool_schema"
    assert request.mcp_usage_target_tool == "search_logs"
    assert request.mcp_permission_source == "exempt"
    legacy.assert_not_called()


def test_middleware_closes_unified_tool_trace_with_http_status(request_factory, caplog):
    caplog.set_level(logging.INFO, logger=auth.__name__)
    process_response = source_method(
        "kernel_api/middlewares/authentication.py",
        "AuthenticationMiddleware.process_response",
        time=time,
        logging=logging,
        log_mcp_tool_event=auth.log_mcp_tool_event,
    )
    request = request_factory()
    request.unified_mcp_operation = "execute_tool"
    request.unified_mcp_tool = "search_logs"
    request.unified_mcp_started_at = time.monotonic() - 0.01
    response = HttpResponse(status=403)

    assert process_response(NS(), request, response) is response
    record = caplog.records[-1].getMessage()
    assert record.startswith("MCP_TOOL: event=response_finished ")
    fields = json.loads(record.split(" ", 2)[2])
    assert fields["operation"] == "execute_tool" and fields["tool"] == "search_logs"
    assert fields["decision"] == "failed" and fields["status_code"] == 403
    assert fields["duration_ms"] >= 0


def test_middleware_emits_one_complete_usage_record(request_factory, caplog):
    caplog.set_level(logging.INFO, logger=auth.__name__)
    process_response = source_method(
        "kernel_api/middlewares/authentication.py",
        "AuthenticationMiddleware.process_response",
        time=time,
        logging=logging,
        MCP_USAGE_SCHEMA_VERSION=1,
        log_mcp_tool_event=auth.log_mcp_tool_event,
        log_mcp_usage_event=auth.log_mcp_usage_event,
    )
    request = request_factory()
    request.META.update(
        HTTP_X_BK_REQUEST_FROM="knot",
        HTTP_X_BK_REQUEST_SOURCE="bkm-mcp-client",
        HTTP_X_REQUEST_ID="request-id-1",
    )
    request.mcp_usage_started_at = time.monotonic() - 0.01
    request.mcp_usage_event_id = "event-id-1"
    request.mcp_usage_app_code = "knot-app"
    request.mcp_usage_entry_point = "unified"
    request.mcp_usage_operation = "execute_tool"
    request.mcp_usage_tool = "search_logs"
    request.mcp_usage_target_tool = ""
    request.unified_mcp_tool = "search_logs"
    request.mcp_permission_action = "search_log_v2"
    request.mcp_permission_source = "native"
    request.biz_id = 2

    response = HttpResponse(status=200)
    assert process_response(NS(), request, response) is response

    records = [row.getMessage() for row in caplog.records if row.getMessage().startswith("MCP_USAGE:")]
    assert len(records) == 1
    fields = json.loads(records[0].split(" ", 2)[2])
    assert fields == {
        "action_id": "search_log_v2",
        "app_code": "knot-app",
        "authorization_source": "native",
        "bk_biz_id": "2",
        "checked_action_id": "search_log_v2",
        "decision": "succeeded",
        "duration_ms": fields["duration_ms"],
        "entry_point": "unified",
        "mcp_server_name": "bk-monitor-prod-unified",
        "method": "POST",
        "operation": "execute_tool",
        "path": "/api/v4/unified_mcp/execute_tool/",
        "request_event_id": "event-id-1",
        "request_from": "knot",
        "request_source": "bkm-mcp-client",
        "status_code": 200,
        "target_tool": "",
        "tenant_id": "system",
        "tool": "search_logs",
        "trace_id": request.mcp_trace_id,
        "usage_schema_version": 1,
        "username": "alice",
        "x_request_id": "request-id-1",
    }
    assert fields["duration_ms"] >= 0


def test_usage_record_does_not_report_denied_action_as_effective(request_factory, caplog):
    caplog.set_level(logging.INFO, logger=auth.__name__)
    process_response = source_method(
        "kernel_api/middlewares/authentication.py",
        "AuthenticationMiddleware.process_response",
        time=time,
        logging=logging,
        MCP_USAGE_SCHEMA_VERSION=1,
        log_mcp_tool_event=auth.log_mcp_tool_event,
        log_mcp_usage_event=auth.log_mcp_usage_event,
    )
    request = request_factory()
    request.mcp_usage_started_at = time.monotonic()
    request.mcp_permission_action = "using_log_mcp"
    request.mcp_permission_source = "none"

    process_response(NS(), request, HttpResponse(status=403))

    record = next(row.getMessage() for row in caplog.records if row.getMessage().startswith("MCP_USAGE:"))
    fields = json.loads(record.split(" ", 2)[2])
    assert fields["action_id"] == ""
    assert fields["checked_action_id"] == "using_log_mcp"
    assert fields["authorization_source"] == "none"
    assert fields["decision"] == "failed"


def test_usage_record_clears_internal_permission_probe_from_exempt_facade(request_factory, caplog):
    caplog.set_level(logging.INFO, logger=auth.__name__)
    process_response = source_method(
        "kernel_api/middlewares/authentication.py",
        "AuthenticationMiddleware.process_response",
        time=time,
        logging=logging,
        MCP_USAGE_SCHEMA_VERSION=1,
        log_mcp_tool_event=auth.log_mcp_tool_event,
        log_mcp_usage_event=auth.log_mcp_usage_event,
    )
    request = request_factory("/api/v4/unified_mcp/lookup_permissions/")
    request.mcp_usage_started_at = time.monotonic()
    request.mcp_usage_operation = "lookup_permissions"
    request.mcp_usage_tool = "lookup_permissions"
    request.mcp_usage_target_tool = "search_logs"
    request.mcp_permission_action = "search_log_v2"
    request.mcp_permission_source = "exempt"

    process_response(NS(), request, HttpResponse(status=200))

    record = next(row.getMessage() for row in caplog.records if row.getMessage().startswith("MCP_USAGE:"))
    fields = json.loads(record.split(" ", 2)[2])
    assert fields["operation"] == fields["tool"] == "lookup_permissions"
    assert fields["target_tool"] == "search_logs"
    assert fields["action_id"] == fields["checked_action_id"] == ""
    assert fields["authorization_source"] == "exempt"


def test_middleware_marks_wrapped_application_error_as_failed(request_factory, caplog):
    caplog.set_level(logging.INFO, logger=auth.__name__)
    process_response = source_method(
        "kernel_api/middlewares/authentication.py",
        "AuthenticationMiddleware.process_response",
        time=time,
        logging=logging,
        log_mcp_tool_event=auth.log_mcp_tool_event,
    )
    request = request_factory()
    request.unified_mcp_operation = "execute_tool"
    request.unified_mcp_tool = "update_dashboard"
    request.unified_mcp_started_at = time.monotonic() - 0.01
    request.unified_mcp_response_failed = True
    request.unified_mcp_result_code = 400
    response = NS(status_code=200, data=None)

    assert process_response(NS(), request, response) is response
    record = caplog.records[-1].getMessage()
    fields = json.loads(record.split(" ", 2)[2])
    assert fields["decision"] == "failed"
    assert fields["status_code"] == 200
    assert fields["result_code"] == 400
    assert "data" not in fields


def test_strategy_update_preflight_rejects_late_issue_validation():
    events = []

    class CandidateStrategy:
        def __init__(self, **_kwargs):
            events.append("build")

        def convert(self):
            events.append("convert")

    class InvalidIssueConfig:
        def __init__(self, **_kwargs):
            pass

        def validate(self, _strategy):
            events.append("validate")
            raise ValidationError("invalid issue config")

    preflight = source_method(
        "kernel_api/resource/alert.py",
        "_validate_strategy_before_write",
        Strategy=CandidateStrategy,
        IssueConfig=InvalidIssueConfig,
    )

    with pytest.raises(ValidationError, match="invalid issue config"):
        preflight({"issue_config": {}})
    assert events == ["build", "convert", "validate"]


def test_native_discovery_keeps_unresolved_tool_without_old_grant(request_factory, io):
    request = request_factory()
    legacy = Mock()
    legacy.is_allowed_by_biz.return_value = False
    legacy.filter_space_list_by_action.return_value = []
    states = source_method("kernel_api/resource/unified_mcp.py", "_permission_state_by_action")
    lookup = source_method(
        "kernel_api/resource/unified_mcp.py",
        "LookupToolResource.perform_request",
        get_tool_registry=registry.get_tool_registry,
        get_permission_client=lambda: legacy,
        _permission_state_by_action=states,
        permission_state=auth.permission_state,
        get_request=lambda: request,
        ValidationError=ValidationError,
    )
    result = lookup(
        NS(), {"tool_name": "search_logs", "bk_biz_id": 2, "available_only": True, "page": 1, "page_size": 50}
    )
    assert [(tool["name"], tool["permission_state"]) for tool in result["tools"]] == [
        ("search_logs", "requires_resource")
    ]
    legacy.is_allowed_by_biz.assert_not_called()
    io.iam.is_allowed.assert_not_called()


def test_tool_lookup_requires_actions_on_the_same_space(monkeypatch, request_factory):
    monkeypatch.setattr(settings, "MCP_NATIVE_PERMISSION_TOOLS", [])
    request = request_factory()
    permission = Mock()
    permission.filter_space_list_by_action.side_effect = lambda action: [
        {"bk_biz_id": 2 if action == "using_log_collection_mcp" else 3}
    ]
    states = source_method("kernel_api/resource/unified_mcp.py", "_permission_state_by_action")
    lookup = source_method(
        "kernel_api/resource/unified_mcp.py",
        "LookupToolResource.perform_request",
        get_tool_registry=registry.get_tool_registry,
        get_permission_client=lambda: permission,
        _permission_state_by_action=states,
        _legacy_tool_state=source_method("kernel_api/resource/unified_mcp.py", "_legacy_tool_state"),
        permission_state=auth.permission_state,
        get_request=lambda: request,
        ValidationError=ValidationError,
    )

    result = lookup(
        NS(),
        {
            "tool_name": "list_log_collectors",
            "available_only": True,
            "page": 1,
            "page_size": 50,
        },
    )

    assert result["tools"] == []


def test_lookup_permission_uses_native_instance_and_apply_guide(request_factory, io):
    request = request_factory()
    io.iam.is_allowed.return_value = False
    legacy = Mock(side_effect=AssertionError("legacy must not be evaluated"))
    states = source_method("kernel_api/resource/unified_mcp.py", "_permission_state_by_action")
    lookup = source_method(
        "kernel_api/resource/unified_mcp.py",
        "_mixed_permission_scopes",
        get_request=lambda: request,
        _permission_state_by_action=states,
        permission_state=auth.permission_state,
    )
    result = lookup(
        [registry.get_tool_registry().get("search_logs")],
        {
            "bk_biz_id": 2,
            "resource_context": {"index_set_id": 123},
            "include_apply_guide": True,
        },
        legacy,
    )
    assert result["authorized"] is False
    assert result["missing_permissions"][0]["system_id"] == "bk_log_search"
    assert result["missing_permissions"][0]["resource"]["index_set_id"] == "123"
    assert result["missing_permissions"][0]["apply_url"] == "https://iam.invalid/log-apply"


@pytest.mark.parametrize(
    "api_name,tool_name",
    [
        ("log_search_index_set", "get_index_set_fields"),
        ("search_index_set_context", "search_index_set_context"),
        ("scene_fields", "get_scene_log_fields"),
    ],
)
def test_native_log_api_uses_new_instance_and_current_identity(monkeypatch, request_factory, api_name, tool_name):
    from bkmonitor.utils import request as request_utils

    instances = []

    class FakeAPI:
        def __init__(self):
            self.request = Mock()
            self.request.cacheless = Mock(return_value={"ok": True})
            self.legacy = Mock(return_value={"legacy": True})
            instances.append(self)

        def __call__(self, **kwargs):
            return self.legacy(**kwargs)

    pooled = FakeAPI()
    module = ModuleType("core.drf_resource")
    module.api = NS(log_search=NS(**{api_name: pooled}))
    monkeypatch.setitem(sys.modules, module.__name__, module)
    request = request_factory()
    monkeypatch.setattr(request_utils, "get_request", lambda **kwargs: request)
    assert auth.call_log_api(api_name, index_set_id=123) == {"legacy": True}
    assert len(instances) == 1
    request.native_mcp_tool = tool_name
    assert auth.call_log_api(api_name, index_set_id=123) == {"ok": True}
    instances[-1].request.cacheless.assert_called_once_with(
        index_set_id=123, bk_username="alice", bk_tenant_id="system"
    )
    assert len(instances) == 2
    pooled.request.assert_not_called()


def audit_records(caplog):
    prefix = "MCP_AUTH: event=permission_check "
    return [
        json.loads(record.getMessage()[len(prefix) :])
        for record in caplog.records
        if record.name == auth.__name__ and record.getMessage().startswith(prefix)
    ]


@pytest.mark.parametrize(
    "tool_name,args,native_action,legacy_action",
    [
        ("search_logs", log_args(), "search_log_v2", "using_log_mcp"),
        (
            "search_index_set_context",
            {
                "bk_biz_id": "2",
                "index_set_id": 123,
                "zero": True,
                "begin": "-10",
                "size": "10",
                "dtEventTimeStamp": "1788783672000",
                "serverIp": "localhost",
                "gseIndex": "12",
                "iterationIndex": "1",
            },
            "search_log_v2",
            "using_log_mcp",
        ),
        (
            "execute_range_query",
            {"bk_biz_id": "2", "start_time": "1", "end_time": "2", "promql": "test_metric"},
            "explore_metric_v2",
            "using_metrics_mcp",
        ),
        ("list_time_series_groups", {"bk_biz_id": "2"}, "explore_metric_v2", "using_metrics_mcp"),
        ("list_alerts", {"bk_biz_id": "2", "start_time": "1", "end_time": "2"}, "view_event_v2", "using_alarm_mcp"),
    ],
)
@pytest.mark.parametrize("native_allowed,legacy_allowed", [(True, True), (True, False), (False, True), (False, False)])
def test_native_first_fallback_matrix_and_english_logs(
    request_factory, io, caplog, tool_name, args, native_action, legacy_action, native_allowed, legacy_allowed
):
    caplog.set_level(logging.INFO, logger=auth.__name__)
    io.iam.is_allowed.return_value = native_allowed
    io.monitor.iam_client.is_allowed.side_effect = (
        lambda query: legacy_allowed if query.action.id.startswith("using_") else native_allowed
    )
    request = request_factory()
    request.META["HTTP_X_BKAPI_PERMISSION_ACTION"] = "using_dashboard_mcp"
    tool = registry.get_tool_registry().get(tool_name)
    if native_allowed or legacy_allowed:
        assert auth.execute_native_tool(tool, args, request) == {"ok": True}
        io.dispatch.assert_called_once_with(tool_name, args)
    else:
        with pytest.raises(PermissionDenied):
            auth.execute_native_tool(tool, args, request)
        io.dispatch.assert_not_called()
    source = "native" if native_allowed else "legacy" if legacy_allowed else "none"
    assert request.mcp_permission_source == source
    assert request.mcp_permission_action == (native_action if native_allowed else legacy_action)
    checks = [record for record in audit_records(caplog) if record["decision"] == "checking"]
    assert [(row["phase"], row["action_id"]) for row in checks] == (
        [("native", native_action)] + ([] if native_allowed else [("legacy", legacy_action)])
    )
    assert all(row["bk_biz_id"] == "2" and row["username"] == "alice" for row in checks)
    assert len({row["trace_id"] for row in checks}) == 1 and checks[0]["trace_id"]
    assert any(row["phase"] == "final" and row["authorization_source"] == source for row in audit_records(caplog))
    assert all(record.getMessage().isascii() for record in caplog.records if record.name == auth.__name__)
    rows = audit_records(caplog)
    assert (rows[0]["phase"], rows[0]["decision"]) == ("route", "resolved")
    assert all(row["backend_path"] == tool.backend_path for row in rows)
    assert [(row["phase"], row["decision"]) for row in rows if row["phase"] == "execution"] == (
        [("execution", "started"), ("execution", "succeeded")]
        if native_allowed or legacy_allowed
        else [("execution", "aborted")]
    )
    assert next(i for i, row in enumerate(rows) if row["phase"] == "scope" and row["decision"] == "resolved") < next(
        i for i, row in enumerate(rows) if row["phase"] == "native"
    )
    io.monitor.is_allowed_by_biz.assert_not_called()


@pytest.mark.parametrize("phase", ["native", "legacy"])
def test_monitor_iam_error_is_not_a_denial_or_fallback_grant(request_factory, io, caplog, phase):
    caplog.set_level(logging.INFO, logger=auth.__name__)
    calls = []

    def check(query):
        calls.append(query.action.id)
        if phase == "native" or query.action.id.startswith("using_"):
            raise RuntimeError("private upstream response")
        return False

    io.monitor.iam_client.is_allowed.side_effect = check
    # This older wrapper would mask the error as False. It must not be used.
    io.monitor.is_allowed_by_biz.return_value = False
    with pytest.raises(auth.AuthorizationUnavailable):
        auth.execute_native_tool(
            registry.get_tool_registry().get("list_alerts"),
            {"bk_biz_id": "2", "start_time": "1", "end_time": "2"},
            request_factory(),
        )
    assert calls == ["view_event_v2"] + (["using_alarm_mcp"] if phase == "legacy" else [])
    assert any(row["phase"] == phase and row["decision"] == "error" for row in audit_records(caplog))
    assert "private upstream response" not in caplog.text
    io.dispatch.assert_not_called()
    io.monitor.is_allowed_by_biz.assert_not_called()


@pytest.mark.parametrize(
    "tool_name",
    [name for name in registry.NATIVE_PERMISSIONS if name.startswith("get_alert_")]
    + ["list_alerts", "get_strategy_snapshot", "get_strategy_detail"],
)
def test_alert_queries_have_explicit_native_and_legacy_actions(request_factory, io, tool_name):
    tool = registry.get_tool_registry().get(tool_name)
    assert tool.category == "alert"
    action = "view_rule_v2" if tool_name == "get_strategy_detail" else "view_event_v2"
    assert tool.native_permission["action_id"] == action
    assert tool.permission_payload()["fallback_action_id"] == "using_alarm_mcp"
    assert tool.permission_payload()["mode"] == "native_then_legacy"
    values = {
        "bk_biz_id": "2",
        "id": "123",
        "alert_id": "123",
        "start_time": "1",
        "end_time": "2",
        "fields": ["severity"],
    }
    args = {key: values[key] for key in tool.input_schema["required"]}
    auth.execute_native_tool(tool, args, request_factory())
    query = io.monitor.iam_client.is_allowed.call_args.args[0]
    assert query.action.id == action and query.resources[0].id == "2"
    if tool.native_permission.get("target_arg"):
        io.target_scope.assert_called_once_with(tool.native_permission, 2, args)
    else:
        io.target_scope.assert_not_called()
    io.dispatch.assert_called_once_with(tool_name, args)


@pytest.mark.parametrize(
    "tool_name", ["get_alert_info", "get_strategy_snapshot", "get_strategy_detail", "get_alert_events"]
)
def test_foreign_alert_or_strategy_cannot_use_legacy_fallback(monkeypatch, request_factory, io, caplog, tool_name):
    caplog.set_level(logging.INFO, logger=auth.__name__)
    monkeypatch.setattr(auth, "_validate_alert_target", io.real_target_scope)
    module = ModuleType("kernel_api.resource.alert")
    module.ensure_alert_belongs_to_biz = source_method(
        "kernel_api/resource/alert.py",
        "ensure_alert_belongs_to_biz",
        AlertDocument=NS(get=lambda value: NS(event=NS(bk_biz_id=9))),
        ValidationError=ValidationError,
    )
    module.ensure_strategy_ids_belong_to_biz = source_method(
        "kernel_api/resource/alert.py",
        "ensure_strategy_ids_belong_to_biz",
        StrategyModel=NS(objects=NS(filter=lambda **kwargs: NS(values_list=lambda *args, **kwargs: []))),
        ValidationError=ValidationError,
    )
    monkeypatch.setitem(sys.modules, module.__name__, module)
    io.monitor.iam_client.is_allowed.side_effect = lambda query: True
    tool = registry.get_tool_registry().get(tool_name)
    args = {"bk_biz_id": "2", tool.native_permission["target_arg"]: "123"}
    with pytest.raises(ValidationError):
        auth.execute_native_tool(tool, args, request_factory())
    io.monitor.iam_client.is_allowed.assert_not_called()
    io.dispatch.assert_not_called()
    assert not any(row["phase"] == "legacy" for row in audit_records(caplog))


@pytest.mark.parametrize("values", [[], ["9"], ["2", "9"], ["2", "2"], "2"])
def test_alert_business_array_cannot_expand_scope(request_factory, io, values):
    io.monitor.iam_client.is_allowed.side_effect = lambda query: True
    with pytest.raises(ValidationError):
        auth.execute_native_tool(
            registry.get_tool_registry().get("list_alerts"),
            {"bk_biz_id": "2", "bk_biz_ids": values, "start_time": "1", "end_time": "2"},
            request_factory(),
        )
    io.monitor.iam_client.is_allowed.assert_not_called()
    io.dispatch.assert_not_called()


@pytest.mark.parametrize(
    "function,resource_name", [("_list_alerts", "ListAlertResource"), ("_alert_top_n", "ListAlertTopNResource")]
)
def test_alert_dispatcher_derives_only_authorized_business(function, resource_name):
    backend = Mock(return_value={"ok": True})
    execute = source_method(
        "kernel_api/unified_mcp/dispatcher.py", function, **{resource_name: lambda: NS(request=backend)}
    )
    execute({"bk_biz_id": "2", "bk_biz_ids": ["9"]})
    assert backend.call_args.kwargs["bk_biz_ids"] == ["2"]


def test_alert_all_business_sentinel_is_not_a_single_space_permission(request_factory, io):
    with pytest.raises(ValidationError):
        auth.execute_native_tool(
            registry.get_tool_registry().get("list_alerts"),
            {"bk_biz_id": "-1", "start_time": "1", "end_time": "2"},
            request_factory(),
        )
    io.monitor.iam_client.is_allowed.assert_not_called()
    io.dispatch.assert_not_called()


def test_permission_probe_reports_legacy_success_without_missing_permissions(request_factory, io):
    io.iam.is_allowed.return_value = False
    io.monitor.iam_client.is_allowed.side_effect = lambda query: True
    result = auth.permission_state(
        registry.get_tool_registry().get("search_logs"), request_factory(), 2, {"index_set_id": 123}, True
    )
    assert result["authorized"] is True and result["state"] == "granted"
    assert result["native_authorized"] is False and result["legacy_authorized"] is True
    assert result["authorization_source"] == "legacy" and result["matched_action_id"] == "using_log_mcp"
    assert "apply_url" not in result
    io.iam.get_apply_url.assert_not_called()


@pytest.mark.parametrize(
    "mode", ["success", "denied", "iam_error", "legacy_iam_error", "query_error", "render_error", "invalid_args"]
)
def test_http_response_logs_match_execution_and_last_attempted_action(monkeypatch, request_factory, io, caplog, mode):
    caplog.set_level(logging.INFO, logger=auth.__name__)
    render = Mock(return_value=b'{"result":true}')
    for module_name, class_name in [
        ("bkmonitor.views.renderers", "MonitorJSONRenderer"),
        ("kernel_api.adapters", "ApiRenderer"),
    ]:
        module = ModuleType(module_name)
        setattr(module, class_name, lambda: NS(render=render))
        monkeypatch.setitem(sys.modules, module_name, module)
    tool = registry.get_tool_registry().get("search_logs")
    args = log_args(query_string="private-query")
    expected_code = {"success": 200, "denied": 403, "invalid_args": 400}.get(mode, 503)
    if mode in {"denied", "legacy_iam_error"}:
        io.iam.is_allowed.return_value = False
    if mode == "iam_error":
        io.iam.is_allowed.side_effect = RuntimeError("private-upstream")
    if mode == "legacy_iam_error":
        io.monitor.iam_client.is_allowed.side_effect = RuntimeError("private-upstream")
    if mode == "query_error":
        io.dispatch.side_effect = RuntimeError("private-upstream")
    if mode == "render_error":
        render.side_effect = RuntimeError("private-upstream")
    if mode == "invalid_args":
        args["token"] = "private-token"
    handle = source_method(
        "kernel_api/middlewares/authentication.py",
        "AuthenticationMiddleware._handle_native_mcp",
        log_mcp_event=auth.log_mcp_event,
        logging=logging,
        HttpResponse=HttpResponse,
        JsonResponse=JsonResponse,
    )
    request, metric = request_factory(), Mock()
    response = handle(NS(_report_mcp_metric=metric), request, tool, args, unified=True)
    assert response.status_code == expected_code
    record = next(r for r in caplog.records if r.getMessage().startswith("MCP_AUTH: event=response_finished "))
    fields = json.loads(record.getMessage().split(" ", 2)[2])
    assert fields["status_code"] == expected_code and fields["entry_point"] == "unified"
    assert fields["trace_id"] == request.mcp_trace_id
    assert bool(fields["error_type"]) == (mode != "success")
    if mode == "legacy_iam_error":
        assert fields["action_id"] == metric.call_args.args[4] == "using_log_mcp"
    execution = [r["decision"] for r in audit_records(caplog) if r["phase"] == "execution"]
    assert ("succeeded" in execution) == (mode in {"success", "render_error"})
    assert ("started" in execution) == (mode in {"success", "render_error", "query_error"})
    assert not any(secret in caplog.text for secret in ("private-query", "private-token", "private-upstream"))


@pytest.mark.parametrize("method", ["GET", "POST", "FORM"])
def test_ingress_logs_do_not_dump_headers_or_parameters(request_factory, caplog, method):
    caplog.set_level(logging.INFO, logger=auth.__name__)
    args = {"query_string": "private-query", "bk_app_secret": "private-secret"}
    request = request_factory(body=args, method=method)
    if method == "FORM":
        request = RequestFactory().post(request.path, args)
    user = NS(username="alice", tenant_id="system")
    request.META["HTTP_X_BKAPI_JWT"] = "private-jwt"
    jwt = NS(app=NS(app_code="monitor"), user=NS(username="alice"), validate=lambda: (True, ""))
    process = source_method(
        "kernel_api/middlewares/authentication.py",
        "AuthenticationMiddleware.process_view",
        settings=settings,
        secrets=secrets,
        BkJWTClient=lambda *args: jwt,
        auth=NS(authenticate=lambda **kwargs: user),
        DEFAULT_TENANT_ID="system",
        log_mcp_event=auth.log_mcp_event,
    )
    middleware = NS(
        use_apigw_auth=lambda request: True,
        get_apigw_public_keys=lambda: {},
        use_mcp_auth=lambda *args: True,
        _handle_mcp_auth=lambda *args, **kwargs: "handled",
    )
    assert process(middleware, request, NS()) == "handled"
    record = next(row.getMessage() for row in caplog.records if "event=request_received " in row.getMessage())
    fields = json.loads(record.split(" ", 2)[2])
    assert len(request.mcp_usage_event_id) == 32
    assert fields["request_event_id"] == request.mcp_usage_event_id
    assert not any(
        s in caplog.text for s in ("private-query", "private-secret", "private-jwt", "get_params", "post_params")
    )


@pytest.mark.parametrize("reason", ["invalid_jwt", "missing_tenant"])
def test_gateway_rejection_is_logged_without_token_or_exception_text(monkeypatch, request_factory, caplog, reason):
    caplog.set_level(logging.INFO, logger=auth.__name__)
    monkeypatch.setattr(settings, "ENABLE_MULTI_TENANT_MODE", True)
    request = request_factory()
    jwt = NS(
        app=NS(app_code="monitor"),
        user=NS(username="alice"),
        validate=lambda: (reason != "invalid_jwt", "private-jwt-error"),
    )
    process = source_method(
        "kernel_api/middlewares/authentication.py",
        "AuthenticationMiddleware.process_view",
        settings=settings,
        BkJWTClient=lambda *args: jwt,
        log_mcp_event=auth.log_mcp_event,
        logging=logging,
        HttpResponseForbidden=HttpResponseForbidden,
    )
    middleware = NS(
        use_apigw_auth=lambda request: True, get_apigw_public_keys=lambda: {}, use_mcp_auth=lambda *args: True
    )
    assert process(middleware, request, NS()).status_code == 403
    assert "event=gateway_auth_denied " in caplog.text and reason in caplog.text
    assert "private-jwt-error" not in caplog.text


@pytest.mark.parametrize("path", ["/api/v4/log_search/search_log/", "/api/v4/unified_mcp/execute_tool/"])
def test_routing_configuration_errors_are_logged_without_legacy_fallback(
    monkeypatch, request_factory, io, caplog, path
):
    caplog.set_level(logging.INFO, logger=auth.__name__)
    monkeypatch.setattr(settings, "MCP_NATIVE_PERMISSION_TOOLS", ["unsupported"])
    for name, attr in [("bkmonitor.iam.action", "get_action_by_id"), ("bkmonitor.iam.drf", "MCPPermission")]:
        module = ModuleType(name)
        setattr(module, attr, Mock(side_effect=AssertionError("legacy must not be called")))
        monkeypatch.setitem(sys.modules, name, module)
    handle = source_method(
        "kernel_api/middlewares/authentication.py",
        "AuthenticationMiddleware._handle_mcp_auth",
        settings=settings,
        time=time,
        secrets=secrets,
        json=json,
        log_mcp_event=auth.log_mcp_event,
        log_mcp_tool_event=auth.log_mcp_tool_event,
        logging=logging,
        JsonResponse=JsonResponse,
        HttpResponseForbidden=HttpResponseForbidden,
    )
    extract = source_method(
        "kernel_api/middlewares/authentication.py", "AuthenticationMiddleware.extract_tool_name_from_path"
    )
    request = request_factory(path, {"tool_name": "search_logs", "tool_args": log_args()})
    assert handle(NS(extract_tool_name_from_path=extract), request, "alice").status_code == 503
    assert "event=routing_failed " in caplog.text and "ImproperlyConfigured" in caplog.text
    io.iam.is_allowed.assert_not_called()
    io.monitor.iam_client.is_allowed.assert_not_called()
    io.dispatch.assert_not_called()


@pytest.mark.parametrize("failure", ["exception", "invalid_response"])
def test_apply_guide_failure_is_logged_but_does_not_change_denial(request_factory, io, caplog, failure):
    caplog.set_level(logging.INFO, logger=auth.__name__)
    io.iam.is_allowed.return_value = False
    if failure == "exception":
        io.iam.get_apply_url.side_effect = RuntimeError("private-apply-response")
    else:
        io.iam.get_apply_url.return_value = (False, "private-apply-response", "")
    request = request_factory()
    state = auth.permission_state(
        registry.get_tool_registry().get("search_logs"), request, 2, {"index_set_id": 123}, True
    )
    assert not state["authorized"] and "apply_url" not in state
    assert "event=apply_guide_unavailable " in caplog.text and request.mcp_trace_id in caplog.text
    assert "private-apply-response" not in caplog.text


def test_log_format_is_ascii_single_line_and_bounded(request_factory, caplog):
    caplog.set_level(logging.INFO, logger=auth.__name__)
    request = request_factory()
    request.user.username = "用户\nforged entry"
    auth.log_mcp_event("auth_begin", request, tool="x" * 300)
    record = caplog.records[-1].getMessage()
    assert record.startswith("MCP_AUTH: event=auth_begin ") and record.isascii() and "\n" not in record
    fields = json.loads(record.split(" ", 2)[2])
    assert len(fields["tool"]) == 256 and fields["username"] == request.user.username
    assert fields["trace_id"] == request.mcp_trace_id


def test_usage_log_uses_separate_prefix_and_same_trace(request_factory, caplog):
    caplog.set_level(logging.INFO, logger=auth.__name__)
    request = request_factory()

    auth.log_mcp_usage_event("request_finished", request, request_from="knot", action_id="search_log_v2")

    record = caplog.records[-1].getMessage()
    assert record.startswith("MCP_USAGE: event=request_finished ") and record.isascii() and "\n" not in record
    fields = json.loads(record.split(" ", 2)[2])
    assert fields["request_from"] == "knot" and fields["action_id"] == "search_log_v2"
    assert fields["trace_id"] == request.mcp_trace_id


def test_tool_log_uses_separate_prefix_and_same_trace(request_factory, caplog):
    caplog.set_level(logging.INFO, logger=auth.__name__)
    request = request_factory()

    auth.log_mcp_tool_event("request_received", request, operation="execute_tool", tool="search_logs")

    record = caplog.records[-1].getMessage()
    assert record.startswith("MCP_TOOL: event=request_received ") and record.isascii() and "\n" not in record
    fields = json.loads(record.split(" ", 2)[2])
    assert fields["operation"] == "execute_tool" and fields["tool"] == "search_logs"
    assert fields["trace_id"] == request.mcp_trace_id


@pytest.mark.parametrize(
    "tool_name,args",
    [
        ("get_index_set_fields", {"bk_biz_id": "2", "index_set_id": "123"}),
        ("search_logs", log_args(index_set_id="123", limit=1)),
        (
            "search_index_set_context",
            {
                "bk_biz_id": "2",
                "index_set_id": "123",
                "zero": "true",
                "begin": "0",
                "size": "2",
                "dtEventTimeStamp": "1000",
                "serverIp": "localhost",
                "gseIndex": "5",
                "iterationIndex": "1",
            },
        ),
        (
            "analyze_field",
            log_args(
                index_set_id="123",
                field_name="log",
                group_by="false",
                limit="20",
                conditions={
                    "field_list": [{"field_name": "log", "op": "eq", "value": ["False"]}],
                    "condition_list": [],
                },
            ),
        ),
        (
            "search_log_clustering_pattern",
            log_args(
                index_set_id="123",
                pattern_level="05",
                show_new_pattern="false",
                size=2,
            ),
        ),
    ],
)
@pytest.mark.parametrize("native_allowed,legacy_allowed", [(True, False), (False, True), (False, False)])
def test_standalone_log_wire_formats_use_same_permission_route(
    native_http, io, tool_name, args, native_allowed, legacy_allowed
):
    io.iam.is_allowed.return_value = native_allowed
    io.monitor.iam_client.is_allowed.side_effect = lambda query: legacy_allowed
    tool = registry.get_tool_registry().get(tool_name)
    original = json.loads(json.dumps(args))
    response, request = native_http(tool, args, unified=False)
    assert args == original  # The adapter must not rewrite caller-owned dictionaries.
    assert io.iam.is_allowed.call_args.args[0].resources[0].id == "123"
    assert request.mcp_permission_source == ("native" if native_allowed else "legacy" if legacy_allowed else "none")
    if native_allowed or legacy_allowed:
        assert response.status_code == 200
        normalized = io.dispatch.call_args.args[1]
        assert normalized["index_set_id"] == 123
        assert type(normalized["index_set_id"]) is int
        if tool_name == "analyze_field":
            assert normalized["group_by"] is False
            assert normalized["conditions"]["field_list"][0]["value"] == ["False"]
        if tool_name == "search_index_set_context":
            assert normalized["zero"] is True
        if tool_name == "search_log_clustering_pattern":
            assert normalized["show_new_pattern"] is False
    else:
        assert response.status_code == 403
        data = json.loads(response.content)["data"]
        assert data["native_authorized"] is False and data["legacy_authorized"] is False
        assert data["authorized"] is False
        assert data["resource"]["index_set_id"] == "123"
        assert data["apply_url"] == "https://iam.invalid/log-apply"
        io.dispatch.assert_not_called()
    if native_allowed:
        io.monitor.iam_client.is_allowed.assert_not_called()


@pytest.mark.parametrize(
    "value",
    [True, False, 1.5, 123.0, "123.0", "1e2", "0", "-1", "", "null", [], {}, pytest.param("9" * 5000, id="oversized")],
)
@pytest.mark.parametrize("unified", [False, True])
def test_invalid_log_identifier_never_reaches_iam(native_http, io, value, unified):
    response, _ = native_http(registry.get_tool_registry().get("search_logs"), log_args(index_set_id=value), unified)
    assert response.status_code == 400
    io.catalog.assert_not_called()
    io.iam.is_allowed.assert_not_called()
    io.monitor.iam_client.is_allowed.assert_not_called()
    io.dispatch.assert_not_called()


def test_standalone_adapter_uses_schema_not_tool_or_field_names():
    tool = replace(
        registry.get_tool_registry().get("search_logs"),
        name="unrelated_tool",
        category="other",
        input_schema={
            "properties": {
                "count": {"type": "integer"},
                "enabled": {"type": "boolean"},
                "criteria": {"type": "object"},
                "group_by": {"type": "array"},
                "label": {"type": "string"},
            }
        },
    )
    args = {
        "count": " +003 ",
        "enabled": "False",
        "criteria": "{}",
        "group_by": "false",
        "label": "123",
        "unknown": "true",
    }
    original = dict(args)
    normalized = tool.normalize_standalone_args(args)
    assert normalized == {**args, "count": 3, "enabled": False}
    assert args == original
    assert normalized is not args


@pytest.mark.parametrize(
    "field_type,value",
    [
        ("integer", "123.0"),
        ("integer", "1e2"),
        ("integer", 123.0),
        ("integer", True),
        ("boolean", "1"),
        ("boolean", "0"),
        ("boolean", "yes"),
        ("boolean", "on"),
        ("boolean", 1),
        ("boolean", 0),
    ],
)
def test_standalone_adapter_does_not_expose_broad_serializer_coercion(field_type, value):
    tool = replace(
        registry.get_tool_registry().get("search_logs"), input_schema={"properties": {"value": {"type": field_type}}}
    )
    result = tool.normalize_standalone_args({"value": value})
    assert result["value"] == value
    assert type(result["value"]) is type(value)


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_executor_requires_normalized_ids_regardless_of_transport(request_factory, io, method):
    tool = registry.get_tool_registry().get("get_index_set_fields")
    args = {"bk_biz_id": "2", "index_set_id": "123"}
    request = request_factory(tool.backend_path, args, method)
    with pytest.raises(ValidationError):
        auth.execute_native_tool(tool, args, request)
    io.catalog.assert_not_called()
    io.iam.is_allowed.assert_not_called()
    io.dispatch.assert_not_called()


@pytest.mark.parametrize("value", [False, "false", "False", "true"])
def test_standalone_metric_boolean_conversion_keeps_resource_restrictions(native_http, io, value):
    tool = registry.get_tool_registry().get("list_time_series_groups")
    response, request = native_http(tool, {"bk_biz_id": "2", "is_platform": value}, unified=False)
    assert request.method == "POST"
    if value == "true":
        assert response.status_code == 400
        io.monitor.iam_client.is_allowed.assert_not_called()
        io.dispatch.assert_not_called()
    else:
        assert response.status_code == 200
        assert io.dispatch.call_args.args[1]["is_platform"] is False


def test_unified_does_not_inherit_standalone_string_adaptation(native_http, io):
    response, _ = native_http(registry.get_tool_registry().get("search_logs"), log_args(index_set_id="123"), True)
    assert response.status_code == 400
    io.iam.is_allowed.assert_not_called()
    io.dispatch.assert_not_called()


@pytest.mark.parametrize("conditions", ["invalid-json", "{}", "[]", "null", '"nested-json"', {"bk_biz_id": "9"}])
@pytest.mark.parametrize("unified", [False, True])
def test_filter_requires_schema_object_without_json_string_decoding(native_http, io, conditions, unified):
    response, _ = native_http(
        registry.get_tool_registry().get("analyze_field"),
        log_args(index_set_id=123 if unified else "123", field_name="log", conditions=conditions),
        unified,
    )
    assert response.status_code == 400
    io.catalog.assert_not_called()
    io.iam.is_allowed.assert_not_called()
    io.dispatch.assert_not_called()


@pytest.mark.parametrize(
    "tool_name",
    [
        name
        for name in registry.NATIVE_PERMISSIONS
        if name.startswith("get_alert_") or name in {"list_alerts", "get_strategy_snapshot", "get_strategy_detail"}
    ],
)
@pytest.mark.parametrize("unified", [False, True])
@pytest.mark.parametrize("native_allowed,legacy_allowed", [(True, False), (False, True), (False, False)])
def test_alert_pilot_http_permission_matrix(
    native_http, io, caplog, tool_name, unified, native_allowed, legacy_allowed
):
    caplog.set_level(logging.INFO, logger=auth.__name__)
    io.monitor.iam_client.is_allowed.side_effect = lambda query: (
        legacy_allowed if query.action.id == "using_alarm_mcp" else native_allowed
    )
    tool = registry.get_tool_registry().get(tool_name)
    values = {
        "bk_biz_id": "2",
        "id": "123",
        "alert_id": "123",
        "fields": ["severity"],
        "start_time": "1",
        "end_time": "2",
    }
    args = {key: values[key] for key in tool.input_schema["required"]}
    if not unified and tool.backend_derived_fields:
        args["bk_biz_ids"] = ["2"]
    response, request = native_http(tool, args, unified)
    native_action = "view_rule_v2" if tool_name == "get_strategy_detail" else "view_event_v2"
    queries = [call.args[0] for call in io.monitor.iam_client.is_allowed.call_args_list]
    assert [query.action.id for query in queries] == [native_action] + ([] if native_allowed else ["using_alarm_mcp"])
    assert all(query.resources[0].id == "2" for query in queries)
    if tool.native_permission.get("target_arg"):
        io.target_scope.assert_called_once()
    else:
        io.target_scope.assert_not_called()
    source = "native" if native_allowed else "legacy" if legacy_allowed else "none"
    assert request.mcp_permission_source == source
    assert response.status_code == (200 if native_allowed or legacy_allowed else 403)
    if response.status_code == 403:
        data = json.loads(response.content)["data"]
        assert data["native_authorized"] is False and data["legacy_authorized"] is False
        assert data["apply_url"] == data["legacy_permission"]["apply_url"] == "https://iam.invalid/monitor-apply"
        io.dispatch.assert_not_called()
    else:
        assert "bk_biz_ids" not in io.dispatch.call_args.args[1]
    message = next(row.getMessage() for row in caplog.records if "event=response_finished " in row.getMessage())
    fields = json.loads(message.split(" ", 2)[2])
    assert fields["entry_point"] == ("unified" if unified else "standalone")
    assert fields["authorization_source"] == source


@pytest.mark.parametrize("unified", [False, True])
def test_http_permission_state_preserves_null_and_message_strings(monkeypatch, native_http, io, unified):
    state = {
        "state": "requires_resource",
        "authorized": False,
        "native_authorized": None,
        "legacy_authorized": None,
        "authorization_source": "none",
        "label": "False",
        "count": 0,
    }
    monkeypatch.setattr(auth, "permission_state", lambda *args, **kwargs: state)
    response, _ = native_http(registry.get_tool_registry().get("search_logs"), log_args(), unified)
    assert response.status_code == 403
    assert json.loads(response.content)["data"] == state
    io.dispatch.assert_not_called()


def test_permission_denied_keeps_drf_error_introspection():
    state = {"authorized": False, "native_authorized": None, "count": 0, "reasons": [{"label": "False"}]}
    denial = auth.MCPPermissionDenied(state)
    standard = PermissionDenied(state)
    assert denial.status_code == 403
    assert denial.get_codes() == standard.get_codes()
    assert denial.get_full_details() == standard.get_full_details()
    assert json.loads(json.dumps(denial.detail)) == state


@pytest.mark.parametrize("handler_kind", ["resource", "api"])
def test_global_exception_handlers_preserve_permission_state(handler_kind):
    import six
    from rest_framework.exceptions import APIException
    from rest_framework.response import Response

    from core.errors import Error, ErrorDetails
    from core.errors.common import DrfApiError

    state = {"state": "denied", "authorized": False, "native_authorized": None, "label": "False", "count": 0}
    denial = auth.MCPPermissionDenied(state)
    if handler_kind == "resource":
        handler = source_method(
            "core/drf_resource/exceptions.py",
            "custom_exception_handler",
            Error=Error,
            APIException=APIException,
            DrfApiError=DrfApiError,
            ErrorDetails=ErrorDetails,
            Response=Response,
        )
        response = handler(denial, {})
        assert response.status_code == 403
        assert response.data["data"] == state
        assert response.exception_instance is denial
    else:
        handler = source_method(
            "kernel_api/exceptions.py",
            "api_exception_handler",
            IGNORE_EXCEPTIONS=(ValidationError,),
            logger=Mock(),
            six=six,
            failed=source_method("bkmonitor/utils/common_utils.py", "failed", ErrorDetails=ErrorDetails),
            Response=Response,
        )
        response = handler(denial, {})
        # Preserve the API role's existing business-code envelope, not a new status convention.
        assert response.data["code"] == 403
        assert response.data["detail"] == state


def test_api_exception_handler_marks_unified_failure_on_request():
    import six
    from rest_framework.response import Response

    from core.errors import ErrorDetails

    handler = source_method(
        "kernel_api/exceptions.py",
        "api_exception_handler",
        IGNORE_EXCEPTIONS=(ValidationError,),
        logger=Mock(),
        six=six,
        failed=source_method("bkmonitor/utils/common_utils.py", "failed", ErrorDetails=ErrorDetails),
        Response=Response,
    )
    request = NS(unified_mcp_operation="execute_tool")
    drf_request = NS(_request=request)

    response = handler(ValidationError("must not be copied"), {"request": drf_request})

    assert response.data["code"] == 400
    assert request.unified_mcp_response_failed is True
    assert request.unified_mcp_result_code == 400
    assert "must not be copied" not in vars(request).values()
    assert not hasattr(drf_request, "unified_mcp_response_failed")


def test_log_context_zero_false_begin_zero_does_not_query():
    fetch = Mock(return_value=Mock())
    search_context = source_method(
        "../bklog/apps/log_search/handlers/search/search_handlers_esquery.py",
        "SearchHandler.search_context",
        Scenario=NS(ES="es"),
        IndicesOptimizerContextTail=lambda *args, **kwargs: NS(index=[]),
        StorageClusterRecord=NS(objects=NS(none=lambda: None)),
    )
    result = search_context(
        NS(
            scenario_id="log",
            indices=[],
            dtEventTimeStamp=None,
            zero=False,
            start=0,
            fetch_esquery_method=fetch,
        )
    )
    assert result == {"list": []}
    fetch.return_value.assert_not_called()


def test_log_context_schema_describes_per_direction_window():
    tool = registry.get_tool_registry().get("search_index_set_context")
    assert "2*size" in tool.description
    assert "2*size" in tool.input_schema["properties"]["size"]["description"]
    assert "zero=false" in tool.input_schema["properties"]["begin"]["description"]
    for name in ("zero", "begin"):
        assert "begin=0 returns an empty list" in tool.input_schema["properties"][name]["description"]


@pytest.mark.parametrize("filename", ["log_mcp.yaml", "metrics_mcp.yaml", "alert_mcp.yaml"])
def test_source_schema_defaults_match_declared_types(filename):
    document = yaml.safe_load((registry._catalog_root() / filename).read_text())

    def check(schema):
        if "default" in schema:
            assert not list(Draft7Validator(schema).iter_errors(schema["default"])), schema
        for value in schema.get("properties", {}).values():
            check(value)
        if isinstance(schema.get("items"), dict):
            check(schema["items"])

    for path_item in document["paths"].values():
        for operation in path_item.values():
            if isinstance(operation, dict) and "operationId" in operation:
                check(registry._extract_input_schema(operation))


def test_unified_resource_reuses_original_route_permission_native_first(request_factory, io):
    request = request_factory()
    perform = source_method(
        "kernel_api/resource/unified_mcp.py",
        "ExecuteToolResource.perform_request",
        get_tool_registry=registry.get_tool_registry,
        get_request=lambda **kwargs: request,
        execute_native_tool=auth.execute_native_tool,
    )

    result = perform(NS(), {"tool_name": "list_log_collectors", "tool_args": {"bk_biz_id": "2"}})

    assert result["data"] == {"ok": True}
    query = io.monitor.iam_client.is_allowed.call_args.args[0]
    assert query.action.id == "view_business_v2"
    io.dispatch.assert_called_once_with("list_log_collectors", {"bk_biz_id": "2"})

    io.monitor.iam_client.is_allowed.side_effect = lambda query: query.action.id == "using_log_collection_mcp"
    io.dispatch.reset_mock()
    result = perform(NS(), {"tool_name": "list_log_collectors", "tool_args": {"bk_biz_id": "2"}})
    assert result["data"] == {"ok": True}
    assert [call.args[0].action.id for call in io.monitor.iam_client.is_allowed.call_args_list[-2:]] == [
        "view_business_v2",
        "using_log_collection_mcp",
    ]


def test_unified_resource_requires_and_routes_explicit_confirmation(request_factory, io):
    request = request_factory()
    perform = source_method(
        "kernel_api/resource/unified_mcp.py",
        "ExecuteToolResource.perform_request",
        get_tool_registry=registry.get_tool_registry,
        get_request=lambda **kwargs: request,
        Draft7Validator=Draft7Validator,
        ValidationError=ValidationError,
        get_permission_client=lambda: Mock(),
        execute_native_tool=auth.execute_native_tool,
        dispatch_tool=io.dispatch,
    )
    dashboard_args = {"bk_biz_id": "2", "configs": {"grafana/demo.json": "{}"}}

    with pytest.raises(ValidationError, match="confirm"):
        perform(NS(), {"tool_name": "create_dashboard", "tool_args": dashboard_args})
    io.dispatch.assert_not_called()

    perform(NS(), {"tool_name": "create_dashboard", "tool_args": {**dashboard_args, "confirm": True}})
    io.dispatch.assert_called_once_with("create_dashboard", dashboard_args)

    io.dispatch.reset_mock()
    shield_args = {"bk_biz_id": "2", "id": ["1"], "confirm": True}
    perform(NS(), {"tool_name": "disable_alarm_shield", "tool_args": shield_args})
    io.dispatch.assert_called_once_with("disable_alarm_shield", shield_args)


def test_unified_resource_preserves_exempt_space_discovery(request_factory):
    request = request_factory()
    dispatch = Mock(return_value={"ok": True})
    perform = source_method(
        "kernel_api/resource/unified_mcp.py",
        "ExecuteToolResource.perform_request",
        get_tool_registry=registry.get_tool_registry,
        get_request=lambda **kwargs: request,
        Draft7Validator=Draft7Validator,
        ValidationError=ValidationError,
        get_permission_client=lambda: (_ for _ in ()).throw(AssertionError("permission must not be queried")),
        execute_native_tool=auth.execute_native_tool,
        dispatch_tool=dispatch,
    )

    result = perform(NS(), {"tool_name": "search_spaces", "tool_args": {"space_name": "demo"}})

    assert result["data"] == {"ok": True}
    dispatch.assert_called_once_with("search_spaces", {"space_name": "demo"})


def test_unified_resource_rejects_private_mcp_tool_as_unknown():
    perform = source_method(
        "kernel_api/resource/unified_mcp.py",
        "ExecuteToolResource.perform_request",
        get_tool_registry=registry.get_tool_registry,
        ValidationError=ValidationError,
    )

    with pytest.raises(ValidationError, match="unknown unified MCP tool"):
        perform(NS(), {"tool_name": "search_openclaw_spans", "tool_args": {}})


def test_unified_resource_cannot_reuse_legacy_checked_flag(request_factory, io):
    request = request_factory()
    io.iam.is_allowed.return_value = False
    legacy = Mock(side_effect=AssertionError("legacy permission must not be called"))
    perform = source_method(
        "kernel_api/resource/unified_mcp.py",
        "ExecuteToolResource.perform_request",
        get_tool_registry=registry.get_tool_registry,
        Draft7Validator=Draft7Validator,
        ValidationError=ValidationError,
        get_request=lambda **kwargs: request,
        get_permission_client=legacy,
        execute_native_tool=auth.execute_native_tool,
    )
    with pytest.raises(PermissionDenied):
        perform(NS(), {"tool_name": "search_logs", "tool_args": log_args()})
    legacy.assert_not_called()
    io.dispatch.assert_not_called()
