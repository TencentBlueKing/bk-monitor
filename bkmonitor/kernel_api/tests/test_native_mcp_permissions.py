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
import socket
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace as NS
from unittest.mock import Mock

import django
import pytest
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


def log_args(**extra):
    return {"bk_biz_id": "2", "index_set_id": 123, "start_time": "1", "end_time": "2", **extra}


def test_catalog_defaults_and_opt_in_change_version(monkeypatch):
    native = registry.get_tool_registry()
    tool = native.get("search_logs")
    assert len(native) == 43
    assert sum(bool(tool.native_permission) for tool in native.list()) == 21
    assert native.get_by_backend("POST", "/api/v4/log_search/search_log/") is tool
    assert native.get_by_backend("GET", "/api/v4/log_search/search_log/") is None
    assert native.get_by_backend("POST", "/api/v4/log_search/search_log.json/") is tool
    assert native.get_by_backend("HEAD", "/api/v4/log_search/get_index_set_list/").name == "list_index_sets"
    assert tool.permission_payload()["system_id"] == "bk_log_search"
    assert tool.permission_payload()["resource_arg"] == "index_set_id"
    assert tool.input_schema["properties"]["target_type"]["enum"] == ["index_set"]
    assert "index_set_id" in tool.input_schema["required"]
    assert "table_id_conditions" not in tool.input_schema["properties"]
    monkeypatch.setattr(settings, "MCP_NATIVE_PERMISSION_TOOLS", [])
    legacy = registry.get_tool_registry()
    assert legacy.catalog_version != native.catalog_version
    assert legacy.get("search_logs").permission_payload() == {
        "action_id": "using_log_mcp",
        "resource_type": "space",
        "resource_arg": "bk_biz_id",
    }
    assert all(not item.native_permission for item in legacy.list())


@pytest.mark.parametrize(
    "names", [["search_event_log"], ["execute_sql_query"], ["typo"], "search_logs", [True], None, "", 0]
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
    assert native.get("search_logs").input_schema["properties"]["target_type"]["enum"] == ["index_set"]
    assert not native.get("execute_sql_query").native_permission

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
    )
    cls = source_method(
        "kernel_api/resource/unified_mcp.py",
        "LookupPermissionsResource",
        Resource=object,
        serializers=serializers,
        CATEGORIES=tuple(registry.CATEGORY_ACTIONS),
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
def test_unsupported_or_foreign_indices_do_not_query(request_factory, io, change):
    io.monitor.iam_client.is_allowed.side_effect = lambda query: True
    io.catalog.return_value[0].update(change)
    with pytest.raises((PermissionDenied, ValidationError)):
        auth.execute_native_tool(registry.get_tool_registry().get("search_logs"), log_args(), request_factory())
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


def test_get_and_aggregate_share_normalized_log_arguments(request_factory, io):
    tool = registry.get_tool_registry().get("get_index_set_fields")
    request = request_factory(tool.backend_path, {"bk_biz_id": "2", "index_set_id": "123"}, "GET")
    assert auth.execute_native_tool(tool, request.GET.dict(), request) == {"ok": True}
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
        log_mcp_event=auth.log_mcp_event,
        HttpResponseForbidden=HttpResponseForbidden,
    )
    delegate = Mock(
        side_effect=lambda request, tool, args, unified=False: auth.execute_native_tool(tool, args, request)
    )
    extract = source_method(
        "kernel_api/middlewares/authentication.py", "AuthenticationMiddleware.extract_tool_name_from_path"
    )
    middleware = NS(extract_tool_name_from_path=extract, _handle_native_mcp=delegate)
    tool = registry.get_tool_registry().get(tool_name)
    standalone_args = dict(args)
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
    [("log_search_index_set", "get_index_set_fields"), ("search_index_set_context", "search_index_set_context")],
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
    io.target_scope.assert_called_once_with(tool.native_permission, 2, args)
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
    assert "event=request_received " in caplog.text
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
        json=json,
        log_mcp_event=auth.log_mcp_event,
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
