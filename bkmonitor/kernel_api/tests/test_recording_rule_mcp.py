"""RecordingRule MCP 的网关契约、用户权限和业务隔离。"""

import copy
import json
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from django.urls import include, path, resolve
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIRequestFactory

from bkmonitor.iam import ActionEnum
from bkmonitor.iam.action import canonicalize_action_id
from bkmonitor.iam.definitions import Roles, actions
from constants.mcp import get_mcp_permission_action_by_server_name
from core.drf_resource.routers import ResourceRouter
from kernel_api.resource import recording_rule, recording_rule_mcp, unified_mcp
from kernel_api.unified_mcp import dispatcher
from kernel_api.unified_mcp.registry import get_tool_registry
from kernel_api.views.v4 import recording_rule_mcp as mcp_views

ROOT = Path(__file__).resolve().parents[2]
VIEW = "view_recording_rule_v2"
MANAGE = "manage_recording_rule_v2"
TOOLS = [
    ("preview_recording_rule", "PreviewConfigResource", "preview_config"),
    ("create_recording_rule", "CreateConfigResource", "create_config"),
    ("update_recording_rule", "UpdateConfigResource", "update_config"),
    ("delete_recording_rule", "DeleteConfigResource", "delete_config"),
    ("get_recording_rule", "GetConfigResource", "get_config"),
    ("apply_recording_rule", "ApplyConfigResource", "apply_config"),
    ("list_recording_rules", "ListConfigsResource", "list_configs"),
]
CONFIG = {"name": "cpu", "rules": [{"record": "cpu_avg", "expr": "avg(system_cpu_usage)"}]}


@pytest.fixture
def authenticated(mocker, settings):
    settings.ENABLE_MULTI_TENANT_MODE = True
    request = SimpleNamespace(
        user=SimpleNamespace(username="alice", tenant_id="tenant-a", is_authenticated=True),
        jwt=SimpleNamespace(is_valid=True, user={"username": "alice", "verified": True}),
        META={"HTTP_X_BK_TENANT_ID": "tenant-a"},
        skip_check=True,
        unified_mcp_permission_checked=True,
    )
    mocker.patch.object(recording_rule_mcp, "get_request", return_value=request)
    mocker.patch.object(unified_mcp, "get_request", return_value=request)
    tenant_check = mocker.patch("bkmonitor.utils.tenant.is_biz_in_tenant", return_value=True)
    mocker.patch("bkm_space.utils.bk_biz_id_to_space_uid", return_value="bkcc__2")
    permission = mocker.patch.object(recording_rule_mcp, "Permission")
    return request, permission, tenant_check


def params_for(cls):
    params = {"bk_biz_id": "2"}
    fields = cls.RequestSerializer().fields
    if "config" in fields:
        params["config"] = copy.deepcopy(CONFIG)
    if "id" in fields:
        params["id"] = 42
    if cls.requires_confirmation:
        params["confirm"] = True
    return params


@pytest.mark.parametrize("tool_name,class_name,endpoint", TOOLS)
def test_all_tools_use_guarded_resources_and_real_routes(authenticated, mocker, tool_name, class_name, endpoint):
    request, permission, tenant_check = authenticated
    cls = getattr(recording_rule_mcp, class_name)
    perform = mocker.patch.object(getattr(recording_rule, class_name), "perform_request", return_value={"ok": True})
    params = params_for(cls)
    assert dispatcher.dispatch_tool(tool_name, params) == {"ok": True}
    permission.assert_called_once_with("alice", bk_tenant_id="tenant-a")
    assert permission.return_value.skip_check is False
    permission.return_value.is_allowed_by_biz.assert_called_once_with(
        2, MANAGE if cls.requires_confirmation else VIEW, raise_exception=True
    )
    tenant_check.assert_called_once_with(2, "tenant-a")
    assert perform.call_count == 1

    router = ResourceRouter()
    router.register_module(mcp_views)
    backend_path = f"/api/v4/recording_rule_mcp/{endpoint}/"
    match = resolve(backend_path, urlconf=(path("api/v4/", include(router.urls)),))
    response = match.func(APIRequestFactory().post(backend_path, params, format="json"), **match.kwargs)
    assert response.status_code == 200
    assert perform.call_count == 2


@pytest.mark.parametrize("missing", ["user", "authenticated", "jwt", "verified", "username", "tenant"])
def test_mcp_rejects_unverified_users_before_execution(authenticated, mocker, missing):
    request, permission, _ = authenticated
    if missing == "user":
        request.user = None
    elif missing == "authenticated":
        request.user.is_authenticated = False
    elif missing == "jwt":
        request.jwt.is_valid = False
    elif missing == "verified":
        request.jwt.user["verified"] = False
    elif missing == "username":
        request.jwt.user["username"] = "another-user"
    elif missing == "tenant":
        request.META["HTTP_X_BK_TENANT_ID"] = "another-tenant"
    perform = mocker.patch.object(recording_rule.ListConfigsResource, "perform_request")
    with pytest.raises(PermissionDenied):
        recording_rule_mcp.ListConfigsResource().request(bk_biz_id=2)
    permission.assert_not_called()
    perform.assert_not_called()


def test_mcp_rejects_business_outside_user_tenant(authenticated, mocker):
    _, permission, tenant_check = authenticated
    tenant_check.return_value = False
    perform = mocker.patch.object(recording_rule.ListConfigsResource, "perform_request")
    with pytest.raises(PermissionDenied, match="tenant"):
        recording_rule_mcp.ListConfigsResource().request(bk_biz_id=99)
    permission.assert_not_called()
    perform.assert_not_called()


@pytest.mark.parametrize("tool_name,class_name,endpoint", TOOLS)
def test_unified_checked_marker_cannot_bypass_recording_rule_permission(
    authenticated, mocker, tool_name, class_name, endpoint
):
    _, permission, _ = authenticated
    permission.return_value.is_allowed_by_biz.side_effect = PermissionDenied("business permission denied")
    perform = mocker.patch.object(getattr(recording_rule, class_name), "perform_request")
    with pytest.raises(PermissionDenied, match="business permission denied"):
        unified_mcp.ExecuteToolResource().request(
            tool_name=tool_name, tool_args=params_for(getattr(recording_rule_mcp, class_name))
        )
    cls = getattr(recording_rule_mcp, class_name)
    permission.return_value.is_allowed_by_biz.assert_called_once_with(
        2, MANAGE if cls.requires_confirmation else VIEW, raise_exception=True
    )
    perform.assert_not_called()


@pytest.mark.parametrize(
    "class_name", ["CreateConfigResource", "UpdateConfigResource", "DeleteConfigResource", "ApplyConfigResource"]
)
def test_standalone_mutations_require_confirmation(authenticated, mocker, class_name):
    cls = getattr(recording_rule_mcp, class_name)
    params = params_for(cls)
    params.pop("confirm")
    perform = mocker.patch.object(getattr(recording_rule, class_name), "perform_request")
    with pytest.raises(ValidationError, match="confirm"):
        cls().request(params)
    perform.assert_not_called()


def test_mcp_requires_explicit_business(authenticated):
    with pytest.raises(ValidationError):
        recording_rule_mcp.ListConfigsResource().request(space_uid="bkcc__2")


def test_app_api_does_not_require_mcp_user(authenticated, mocker):
    request, permission, _ = authenticated
    request.user = None
    request.jwt = None
    mocker.patch.object(recording_rule.ListConfigsResource, "perform_request", return_value={"list": []})
    assert recording_rule.ListConfigsResource().request(bk_biz_id=2) == {"list": []}
    permission.assert_not_called()


def test_mcp_contract_requires_users_and_matches_registry():
    document = yaml.safe_load(
        (ROOT / "support-files/apigw/resources/internal/user/recording_rule_mcp.yaml").read_text()
    )
    registry = get_tool_registry()
    for tool_name, _, endpoint in TOOLS:
        operation = document["paths"][f"/mcp/{tool_name}/"]["post"]
        auth = operation["x-bk-apigateway-resource"]["authConfig"]
        assert auth == {"appVerifiedRequired": False, "userVerifiedRequired": True, "resourcePermissionRequired": True}
        tool = registry.get(tool_name)
        assert tool.iam_action == (MANAGE if tool.risk == "mutation" else VIEW)
        assert tool.backend_method == "POST"
        assert tool.backend_path == f"/api/v4/recording_rule_mcp/{endpoint}/"
        assert "bk_biz_id" in tool.input_schema["required"]
        if tool.risk == "mutation":
            assert tool.requires_confirmation and tool.forwards_confirmation
    assert get_mcp_permission_action_by_server_name("bk-monitor-prod-recording-rule") == VIEW


def test_iam_registration_preserves_groups_and_adds_business_management_permission(mocker):
    iam_dir = ROOT / "support-files/iam"
    previous = json.loads((iam_dir / "0016_correct_action_groups.json").read_text())
    current = json.loads((iam_dir / "0017_recording_rule_mcp.json").read_text())
    view, manage, groups = current["operations"]
    assert view["data"]["id"] == VIEW == ActionEnum.VIEW_RECORDING_RULE.id
    assert manage["data"]["id"] == MANAGE == ActionEnum.MANAGE_RECORDING_RULE.id
    assert view["data"]["type"] == "view"
    assert manage["data"]["type"] == "manage"
    assert view["data"]["related_resource_types"][0]["id"] == "space"
    assert manage["data"]["related_resource_types"][0]["id"] == "space"
    assert manage["data"]["related_actions"] == [ActionEnum.VIEW_BUSINESS.id, VIEW]
    expected = copy.deepcopy(previous["operations"][0])
    next(group for group in expected["data"] if group["name_en"] == "Metric")["sub_groups"].append(
        {"name": "预计算规则", "name_en": "RecordingRule", "actions": [{"id": VIEW}, {"id": MANAGE}]}
    )
    assert groups == expected
    view_id, manage_id = canonicalize_action_id(VIEW), canonicalize_action_id(MANAGE)
    assert actions[view_id].resource_type == actions[manage_id].resource_type == "space"
    for role in (Roles.SPACE_OPERATOR, Roles.SPACE_ADMIN):
        for action_id in (view_id, manage_id):
            assert any(binding.action_id == action_id and binding.resource_type == "space" for binding in role.actions)
    assert any(binding.action_id == view_id for binding in Roles.SPACE_VIEWER.actions)
    assert all(binding.action_id != manage_id for binding in Roles.SPACE_VIEWER.actions)
    migration = import_module("bkmonitor.iam.migrations.0017_recording_rule_mcp")
    migrator = mocker.patch.object(migration, "IAMMigrator")
    assert migration.Migration.dependencies == ["0016_correct_action_groups"]
    migration.Migration.operations[0]()
    migrator.assert_called_once_with("0017_recording_rule_mcp.json")
    migrator.return_value.migrate.assert_called_once()


@pytest.mark.parametrize("tool_name,class_name,endpoint", TOOLS)
def test_standalone_middleware_selects_read_or_manage_action(mocker, tool_name, class_name, endpoint):
    from bkmonitor.iam.drf import MCPPermission
    from kernel_api.middlewares.authentication import AuthenticationMiddleware

    cls = getattr(recording_rule_mcp, class_name)
    request = APIRequestFactory().post(
        f"/api/v4/recording_rule_mcp/{endpoint}/",
        params_for(cls),
        format="json",
        HTTP_X_BKAPI_MCP_SERVER_NAME="bk-monitor-prod-recording-rule",
        HTTP_X_BKAPI_PERMISSION_ACTION="using_dashboard_mcp",
    )
    request.user = SimpleNamespace(username="alice", tenant_id="tenant-a")
    checked = []
    mocker.patch.object(
        MCPPermission, "has_permission", lambda self, request, view: checked.append(self.actions[0].id) or True
    )
    middleware = AuthenticationMiddleware(lambda request: None)
    mocker.patch.object(middleware, "_report_mcp_metric")
    assert middleware._handle_mcp_auth(request, username="alice") is None
    assert checked == [MANAGE if cls.requires_confirmation else VIEW]


@pytest.mark.parametrize("tool_name,class_name,endpoint", TOOLS)
def test_read_permission_does_not_authorize_writes_or_other_businesses(
    authenticated, mocker, tool_name, class_name, endpoint
):
    _, permission, _ = authenticated
    cls = getattr(recording_rule_mcp, class_name)
    params = params_for(cls)
    perform = mocker.patch.object(getattr(recording_rule, class_name), "perform_request", return_value={"ok": True})

    def authorize(bk_biz_id, action, raise_exception):
        if bk_biz_id == 2 and action == VIEW:
            return True
        raise PermissionDenied("business permission denied")

    permission.return_value.is_allowed_by_biz.side_effect = authorize
    if cls.requires_confirmation:
        with pytest.raises(PermissionDenied):
            cls().request(params)
        perform.assert_not_called()
    else:
        assert cls().request(params) == {"ok": True}
    perform.reset_mock()
    params["bk_biz_id"] = "3"
    with pytest.raises(PermissionDenied):
        cls().request(params)
    perform.assert_not_called()


def test_tool_discovery_and_permission_lookup_split_read_and_manage(authenticated, mocker):
    permission = mocker.Mock()
    permission.is_allowed_by_biz.side_effect = lambda biz, action: biz == 2 and action == VIEW
    mocker.patch.object(unified_mcp, "get_permission_client", return_value=permission)
    result = unified_mcp.LookupToolResource().request(category="recording_rule", bk_biz_id=2)
    assert {tool["name"] for tool in result["tools"]} == {
        "preview_recording_rule",
        "get_recording_rule",
        "list_recording_rules",
    }
    result = unified_mcp.LookupPermissionsResource().request(category="recording_rule", bk_biz_id=2)
    assert {scope["action_id"]: scope["authorized"] for scope in result["scopes"]} == {VIEW: True, MANAGE: False}
