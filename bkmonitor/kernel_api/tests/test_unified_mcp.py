"""Unit coverage for the unified MCP facade."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from django.test import RequestFactory
from rest_framework.exceptions import ValidationError

from kernel_api.middlewares.authentication import AuthenticationMiddleware
from kernel_api.resource import unified_mcp
from kernel_api.unified_mcp import dispatcher
from kernel_api.unified_mcp.registry import load_tool_registry


class FakePermission:
    def __init__(self, *, allowed_actions=(), allowed_biz=()):
        self.allowed_actions = set(allowed_actions)
        self.allowed_biz = set(allowed_biz)
        self.checked = []

    def filter_space_list_by_action(self, action):
        action_id = getattr(action, "id", action)
        if action_id not in self.allowed_actions:
            return []
        return [{"bk_biz_id": 789, "display_name": "demo"}]

    def is_allowed_by_biz(self, bk_biz_id, action_id, raise_exception=False):
        self.checked.append((int(bk_biz_id), action_id, raise_exception))
        return (int(bk_biz_id), action_id) in self.allowed_biz

    def get_apply_url(self, action_ids, resources):
        return "https://iam.example.test/apply"


def test_registry_loads_exact_phase_one_catalog():
    root = Path(__file__).resolve().parents[2] / "support-files" / "apigw" / "resources" / "internal" / "user"
    registry = load_tool_registry(root)

    assert len(registry) == 25
    assert len(registry.list(category="metrics")) == 4
    assert len(registry.list(category="log")) == 9
    assert len(registry.list(category="alert")) == 12
    assert registry.get("search_logs").prerequisites == ("list_index_sets", "get_index_set_fields")


def test_registry_rejects_source_tool_without_product_metadata(tmp_path):
    source_root = Path(__file__).resolve().parents[2] / "support-files" / "apigw" / "resources" / "internal" / "user"
    for filename in ("metrics_mcp.yaml", "log_mcp.yaml", "alert_mcp.yaml"):
        shutil.copy2(source_root / filename, tmp_path / filename)
    log_path = tmp_path / "log_mcp.yaml"
    document = yaml.safe_load(log_path.read_text())
    document["paths"]["/mcp/new_query/"] = {
        "get": {
            "operationId": "new_query",
            "description": "Synthetic registry drift test tool.",
            "tags": ["log_mcp"],
        }
    }
    log_path.write_text(yaml.safe_dump(document, sort_keys=False))

    with pytest.raises(RuntimeError, match="missing_metadata"):
        load_tool_registry(tmp_path)


def test_registry_hides_backend_derived_alert_fields():
    registry = load_tool_registry(
        Path(__file__).resolve().parents[2] / "support-files" / "apigw" / "resources" / "internal" / "user"
    )
    schema = registry.get("list_alerts").input_schema

    assert "bk_biz_ids" not in schema["properties"]
    assert "bk_biz_ids" not in schema["required"]
    assert "bk_biz_id" in schema["required"]


def test_every_registered_tool_has_an_executor():
    registry = load_tool_registry(
        Path(__file__).resolve().parents[2] / "support-files" / "apigw" / "resources" / "internal" / "user"
    )

    assert set(dispatcher.TOOL_EXECUTORS) == set(registry.names)


def test_alert_dispatcher_derives_backend_biz_array(monkeypatch):
    captured = {}

    def fake_request(_self, **kwargs):
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(dispatcher.ListAlertResource, "request", fake_request)

    result = dispatcher.dispatch_tool(
        "list_alerts",
        {"bk_biz_id": "789", "start_time": "1", "end_time": "2"},
    )

    assert result == {"ok": True}
    assert captured["bk_biz_id"] == "789"
    assert captured["bk_biz_ids"] == ["789"]


def test_lookup_tool_is_deterministic_and_permission_filtered(monkeypatch):
    permission = FakePermission(allowed_actions={"using_log_mcp"})
    monkeypatch.setattr(unified_mcp, "get_permission_client", lambda: permission)

    result = unified_mcp.LookupToolResource().request(
        category="log",
        capability="query",
        available_only=True,
    )

    assert [tool["name"] for tool in result["tools"]] == ["search_logs"]
    assert result["tools"][0]["permission_state"] == "granted"
    assert "recommended_tool" not in result


def test_lookup_tool_filters_permission_for_target_space(monkeypatch):
    permission = FakePermission(
        allowed_actions={"using_log_mcp"},
        allowed_biz={(789, "using_log_mcp")},
    )
    monkeypatch.setattr(unified_mcp, "get_permission_client", lambda: permission)

    allowed = unified_mcp.LookupToolResource().request(
        category="log",
        capability="query",
        bk_biz_id=789,
        available_only=True,
    )
    denied = unified_mcp.LookupToolResource().request(
        category="log",
        capability="query",
        bk_biz_id=790,
        available_only=True,
    )

    assert [tool["name"] for tool in allowed["tools"]] == ["search_logs"]
    assert denied["tools"] == []


def test_lookup_tool_rejects_unknown_exact_name(monkeypatch):
    monkeypatch.setattr(unified_mcp, "get_permission_client", lambda: FakePermission())

    with pytest.raises(ValidationError):
        unified_mcp.LookupToolResource().request(tool_name="query_logs")


def test_lookup_tool_schema_returns_permission_and_prerequisites():
    result = unified_mcp.LookupToolSchemaResource().request(tool_name="search_logs")

    assert result["permission"] == {
        "action_id": "using_log_mcp",
        "resource_type": "space",
        "resource_arg": "bk_biz_id",
    }
    assert [item["tool"] for item in result["prerequisites"]] == [
        "list_index_sets",
        "get_index_set_fields",
    ]
    assert result["limits"]["max_results"] == 10000


def test_lookup_permissions_lists_current_user_scope(monkeypatch):
    permission = FakePermission(allowed_actions={"using_log_mcp"})
    monkeypatch.setattr(unified_mcp, "get_permission_client", lambda: permission)

    result = unified_mcp.LookupPermissionsResource().request(category="log")

    assert result["authorized"] is True
    assert result["scopes"] == [
        {
            "category": "log",
            "tool_name": None,
            "action_id": "using_log_mcp",
            "resource": {"bk_biz_id": "789", "space_name": "demo"},
            "authorized": True,
        }
    ]
    assert result["missing_permissions"] == []


def test_lookup_permissions_returns_apply_guide_for_missing_scope(monkeypatch):
    permission = FakePermission()
    monkeypatch.setattr(unified_mcp, "get_permission_client", lambda: permission)

    result = unified_mcp.LookupPermissionsResource().request(
        bk_biz_id=789,
        tool_name="search_logs",
        include_apply_guide=True,
    )

    assert result["authorized"] is False
    assert result["missing_permissions"][0]["action_id"] == "using_log_mcp"
    assert result["missing_permissions"][0]["apply_url"] == "https://iam.example.test/apply"
    assert permission.checked == [(789, "using_log_mcp", False)]


def test_lookup_metadata_formats_platform_visible_spaces(monkeypatch):
    monkeypatch.setattr(
        unified_mcp.ListSpacesResource,
        "request",
        lambda _self, **_kwargs: {
            "count": 2,
            "list": [
                {"id": 1, "space_uid": "bkcc__789", "space_type_id": "bkcc", "space_name": "demo"},
                {"id": 15, "space_uid": "bkci__project", "space_type_id": "bkci", "space_name": "project"},
            ],
        },
    )

    result = unified_mcp.LookupMetadataResource().request(metadata_type="spaces", space_name="demo")

    assert result["spaces"] == [
        {"space_name": "demo", "space_type": "bkcc", "bk_biz_id": "789"},
        {"space_name": "project", "space_type": "bkci", "bk_biz_id": "-15"},
    ]


def test_log_dispatcher_rejects_cross_space_index_set(monkeypatch):
    monkeypatch.setattr(
        dispatcher.GetIndexSetListResource,
        "request",
        lambda _self, **_kwargs: [{"index_set_id": 10001}],
    )
    monkeypatch.setattr(dispatcher.SearchLogResource, "request", lambda _self, **_kwargs: {"ok": True})

    with pytest.raises(ValidationError):
        dispatcher.dispatch_tool(
            "search_logs",
            {"bk_biz_id": "789", "index_set_id": 10002, "start_time": "1", "end_time": "2"},
        )

    assert dispatcher.dispatch_tool(
        "search_logs",
        {"bk_biz_id": "789", "index_set_id": 10001, "start_time": "1", "end_time": "2"},
    ) == {"ok": True}


def test_time_series_table_rejects_cross_space_reference(monkeypatch):
    group = SimpleNamespace(bk_biz_id=999, bk_data_id=1)
    group_query = SimpleNamespace(first=lambda: group)
    data_source_query = SimpleNamespace(exists=lambda: False)
    monkeypatch.setattr(dispatcher.TimeSeriesGroup.objects, "filter", lambda **_kwargs: group_query)
    monkeypatch.setattr(dispatcher.DataSource.objects, "filter", lambda **_kwargs: data_source_query)
    monkeypatch.setattr(dispatcher, "get_request_tenant_id", lambda: "default")

    with pytest.raises(ValidationError):
        dispatcher._ensure_time_series_table_belongs_to_biz({"bk_biz_id": "789", "table_id": "other.table"})


def test_execute_tool_checks_permission_and_dispatches(monkeypatch):
    permission = FakePermission(allowed_biz={(789, "using_log_mcp")})
    monkeypatch.setattr(unified_mcp, "get_permission_client", lambda: permission)
    monkeypatch.setattr(
        unified_mcp,
        "dispatch_tool",
        lambda tool_name, tool_args: {"called": tool_name, "args": tool_args},
    )

    result = unified_mcp.ExecuteToolResource().request(
        tool_name="list_index_sets",
        tool_args={"bk_biz_id": "789"},
    )

    assert result["status"] == "success"
    assert result["data"]["called"] == "list_index_sets"
    assert permission.checked == [(789, "using_log_mcp", True)]


def test_execute_tool_requires_space_context(monkeypatch):
    monkeypatch.setattr(unified_mcp, "get_permission_client", lambda: FakePermission())

    with pytest.raises(ValidationError):
        unified_mcp.ExecuteToolResource().request(tool_name="list_index_sets", tool_args={})


def test_execute_tool_rejects_invalid_business_id(monkeypatch):
    monkeypatch.setattr(unified_mcp, "get_permission_client", lambda: FakePermission())

    with pytest.raises(ValidationError):
        unified_mcp.ExecuteToolResource().request(
            tool_name="list_index_sets",
            tool_args={"bk_biz_id": "not-an-id"},
        )


def test_middleware_exempts_only_unified_facade_lookup_path(monkeypatch):
    monkeypatch.setattr(AuthenticationMiddleware, "_report_mcp_metric", lambda *_args, **_kwargs: None)
    middleware = AuthenticationMiddleware(lambda _request: None)

    unified_request = RequestFactory().post(
        "/api/v4/unified_mcp/lookup_tool/",
        data=json.dumps({"category": "log"}),
        content_type="application/json",
        HTTP_X_BKAPI_MCP_SERVER_NAME="bk-monitor-prod-unified",
    )
    other_request = RequestFactory().post(
        "/api/v4/other/lookup_tool/",
        data=json.dumps({"category": "log"}),
        content_type="application/json",
        HTTP_X_BKAPI_MCP_SERVER_NAME="bk-monitor-prod-unified",
    )

    assert middleware._handle_mcp_auth(unified_request, username="test-user") is None
    denied = middleware._handle_mcp_auth(other_request, username="test-user")
    assert denied.status_code == 403
    assert denied.content == b"Missing bk_biz_id in request parameters"


def test_middleware_routes_unified_execute_permission_from_inner_tool(monkeypatch):
    captured = {}

    class FakeMCPPermission:
        def __init__(self, action):
            captured["action"] = action.id

        def has_permission(self, request, _view):
            captured["bk_biz_id"] = request.biz_id
            return True

    monkeypatch.setattr("bkmonitor.iam.action.get_action_by_id", lambda action_id: SimpleNamespace(id=action_id))
    monkeypatch.setattr("bkmonitor.iam.drf.MCPPermission", FakeMCPPermission)
    monkeypatch.setattr(AuthenticationMiddleware, "_report_mcp_metric", lambda *_args, **_kwargs: None)

    request = RequestFactory().post(
        "/api/v4/unified_mcp/execute_tool/",
        data=json.dumps({"tool_name": "search_logs", "tool_args": {"bk_biz_id": "789"}}),
        content_type="application/json",
        HTTP_X_BKAPI_MCP_SERVER_NAME="bk-monitor-prod-unified",
    )
    request.user = SimpleNamespace(username="test-user", tenant_id="default")

    response = AuthenticationMiddleware(lambda _request: None)._handle_mcp_auth(request, username="test-user")

    assert response is None
    assert captured == {"action": "using_log_mcp", "bk_biz_id": 789}
    assert request.unified_mcp_permission_checked is True


def test_middleware_rejects_unknown_unified_inner_tool(monkeypatch):
    monkeypatch.setattr(AuthenticationMiddleware, "_report_mcp_metric", lambda *_args, **_kwargs: None)
    request = RequestFactory().post(
        "/api/v4/unified_mcp/execute_tool/",
        data=json.dumps({"tool_name": "unknown_tool", "tool_args": {"bk_biz_id": "789"}}),
        content_type="application/json",
        HTTP_X_BKAPI_MCP_SERVER_NAME="bk-monitor-prod-unified",
    )

    response = AuthenticationMiddleware(lambda _request: None)._handle_mcp_auth(request, username="test-user")

    assert response.status_code == 403
    assert response.content == b"Invalid unified MCP tool"


def test_middleware_rejects_non_object_unified_tool_args(monkeypatch):
    monkeypatch.setattr(AuthenticationMiddleware, "_report_mcp_metric", lambda *_args, **_kwargs: None)
    request = RequestFactory().post(
        "/api/v4/unified_mcp/execute_tool/",
        data=json.dumps({"tool_name": "search_logs", "tool_args": ["invalid"]}),
        content_type="application/json",
        HTTP_X_BKAPI_MCP_SERVER_NAME="bk-monitor-prod-unified",
    )

    response = AuthenticationMiddleware(lambda _request: None)._handle_mcp_auth(request, username="test-user")

    assert response.status_code == 403
    assert response.content == b"Invalid unified MCP tool_args"
