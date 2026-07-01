from __future__ import annotations

"""
Backend contract tests for Issue TAPD OAuth and workspace binding.

These tests use AST/source inspection to keep the deploy-time authorization
contracts covered without importing the full Django service stack.
"""

import ast
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[4]


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def _parse(path: str) -> ast.Module:
    return ast.parse(_read(path))


def _class(module: ast.AST, name: str) -> ast.ClassDef:
    for node in ast.iter_child_nodes(module):
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    raise AssertionError(f"class {name} not found")


def _function(module: ast.AST, name: str) -> ast.FunctionDef:
    for node in ast.iter_child_nodes(module):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"function {name} not found")


def _method(class_node: ast.ClassDef, name: str) -> ast.FunctionDef:
    for node in class_node.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"method {name} not found")


def _class_assignment(class_node: ast.ClassDef, name: str) -> ast.Assign:
    for node in class_node.body:
        if isinstance(node, ast.Assign) and any(getattr(target, "id", None) == name for target in node.targets):
            return node
    raise AssertionError(f"assignment {name} not found")


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def _call_names(node: ast.AST) -> set[str]:
    return {_call_name(child.func) for child in ast.walk(node) if isinstance(child, ast.Call)}


def _string_constants(node: ast.AST) -> set[str]:
    return {child.value for child in ast.walk(node) if isinstance(child, ast.Constant) and isinstance(child.value, str)}


def _serializer_field(class_node: ast.ClassDef, name: str) -> ast.Call:
    for node in ast.walk(class_node):
        if not isinstance(node, ast.Assign):
            continue
        if not any(getattr(target, "id", None) == name for target in node.targets):
            continue
        if isinstance(node.value, ast.Call):
            return node.value
    raise AssertionError(f"serializer field {name} not found")


class TestTapdOauthContract(unittest.TestCase):
    def test_workspace_binding_migration_follows_issue_tapd_relation(self):
        migration_path = REPO_ROOT / "bkmonitor/bkmonitor/migrations/0199_tapd_workspace_binding.py"
        self.assertTrue(migration_path.exists())
        self.assertFalse((REPO_ROOT / "bkmonitor/bkmonitor/migrations/0198_tapd_workspace_binding.py").exists())

        source = migration_path.read_text(encoding="utf-8")
        self.assertIn('("bkmonitor", "0198_add_issue_tapd_relation")', source)

    def test_user_workspace_requires_manage_event_and_keeps_tapd_auth_permission(self):
        viewset = _class(_parse("bkmonitor/packages/fta_web/issue/views.py"), "IssueViewSet")
        read_only_endpoints = _string_constants(_class_assignment(viewset, "READ_ONLY_ENDPOINTS"))
        routes = _string_constants(_class_assignment(viewset, "resource_routes"))
        get_permissions = _method(viewset, "get_permissions")

        self.assertNotIn("tapd/user_workspace", read_only_endpoints)
        self.assertIn("tapd/user_workspace", routes)
        self.assertIn("self.TAPDAuthPermission", _call_names(get_permissions))

    def test_user_workspace_error_url_is_optional_and_falls_back_to_success_url(self):
        resource = _class(_parse("bkmonitor/packages/fta_web/issue/resources.py"), "ListUserTapdWorkspaceResource")
        request_serializer = _class(resource, "RequestSerializer")
        error_url_field = _serializer_field(request_serializer, "error_url")

        required = {
            keyword.arg: keyword.value.value
            for keyword in error_url_field.keywords
            if isinstance(keyword.value, ast.Constant)
        }
        self.assertIs(required.get("required"), False)

        source = _read("bkmonitor/packages/fta_web/issue/resources.py")
        self.assertIn('validated_request_data.get("error_url") or success_url', source)

    def test_user_oauth_state_is_signed_and_session_free(self):
        utils_module = _parse("bkmonitor/packages/fta_web/issue/utils/tapd.py")
        generate_auth_url = _function(utils_module, "generate_auth_url")
        callback = _function(_parse("bkmonitor/packages/fta_web/issue/resources.py"), "tapd_user_oauth_callback")
        utils_source = ast.get_source_segment(
            _read("bkmonitor/packages/fta_web/issue/utils/tapd.py"), generate_auth_url
        )
        callback_source = ast.get_source_segment(_read("bkmonitor/packages/fta_web/issue/resources.py"), callback)

        self.assertIn("generate_signed_state(payload)", utils_source)
        self.assertIn("secrets.token_urlsafe", utils_source)
        self.assertNotIn("request.session", utils_source)
        self.assertIn("verify_signed_state", _call_names(callback))
        self.assertNotIn("request.session.get", callback_source)
        self.assertIn("redirect_uri=backend_callback.rstrip", callback_source)

    def test_user_oauth_callback_binds_token_to_current_bk_user(self):
        callback = _function(_parse("bkmonitor/packages/fta_web/issue/resources.py"), "tapd_user_oauth_callback")
        callback_source = ast.get_source_segment(_read("bkmonitor/packages/fta_web/issue/resources.py"), callback)

        identity_guard_index = callback_source.index("callback_username != username")
        token_exchange_index = callback_source.index("api.tapd.user_oauth_token")
        save_token_index = callback_source.index("save_tapd_token")

        self.assertIn("callback_username = get_request_username()", callback_source)
        self.assertLess(identity_guard_index, token_exchange_index)
        self.assertLess(identity_guard_index, save_token_index)

    def test_tapd_api_access_token_is_request_scoped(self):
        source = _read("bkmonitor/api/tapd/default.py")
        module = _parse("bkmonitor/api/tapd/default.py")
        tapd_api_resource = _class(module, "TapdAPIResource")
        perform_request = _method(tapd_api_resource, "perform_request")
        get_headers = _method(tapd_api_resource, "get_headers")
        get_granted_serializer = _class(_class(module, "GetGrantedWorkspacesResource"), "RequestSerializer")
        get_workspace_serializer = _class(_class(module, "GetWorkspaceInfoResource"), "RequestSerializer")

        self.assertIn("contextvars.ContextVar", source)
        self.assertNotIn("self.access_token", source)
        self.assertIn("tapd_access_token.set", _call_names(perform_request))
        self.assertIn("tapd_access_token.reset", _call_names(perform_request))
        self.assertIn("tapd_access_token.get", _call_names(get_headers))
        self.assertIsNotNone(_serializer_field(get_granted_serializer, "access_token"))
        self.assertIsNotNone(_serializer_field(get_workspace_serializer, "access_token"))

    def test_app_install_callback_still_uses_signed_state(self):
        callback = _function(_parse("bkmonitor/packages/fta_web/issue/resources.py"), "tapd_app_install_callback")
        self.assertIn("verify_signed_state", _call_names(callback))

    def test_redirect_urls_are_restricted_to_allowed_hosts(self):
        source = _read("bkmonitor/packages/fta_web/issue/utils/tapd.py")
        normalize_redirect_url = _function(
            _parse("bkmonitor/packages/fta_web/issue/utils/tapd.py"), "normalize_redirect_url"
        )

        self.assertIn("url_has_allowed_host_and_scheme", source)
        self.assertIn("DisallowedHost", source)
        self.assertIn("url_has_allowed_host_and_scheme", _call_names(normalize_redirect_url))

    def test_signed_state_decode_errors_are_validation_errors(self):
        verify_signed_state = _function(_parse("bkmonitor/packages/fta_web/issue/utils/tapd.py"), "verify_signed_state")
        source = ast.get_source_segment(_read("bkmonitor/packages/fta_web/issue/utils/tapd.py"), verify_signed_state)

        self.assertIn("except Exception as e", source)
        self.assertIn('ValidationError("invalid_signed_state")', source)
        self.assertIn("isinstance(payload, dict)", source)

    def test_app_install_callback_validates_resource_shape_and_canonical_workspace_id(self):
        callback = _function(_parse("bkmonitor/packages/fta_web/issue/resources.py"), "tapd_app_install_callback")
        source = ast.get_source_segment(_read("bkmonitor/packages/fta_web/issue/resources.py"), callback)

        self.assertIn("isinstance(resource, dict)", source)
        self.assertIn("raw_workspace_id", source)
        self.assertIn("workspace_id = str(int(raw_workspace_id))", source)

    def test_oauth_token_exchange_logs_without_exception_payload(self):
        callback = _function(_parse("bkmonitor/packages/fta_web/issue/resources.py"), "tapd_user_oauth_callback")
        source = ast.get_source_segment(_read("bkmonitor/packages/fta_web/issue/resources.py"), callback)

        self.assertIn('logger.exception("exchange token failed")', source)
        self.assertIn('logger.exception("exchange token unexpected error")', source)
        self.assertNotIn('logger.exception(f"exchange token failed: {e}")', source)
        self.assertNotIn('logger.exception(f"exchange token unexpected error: {e}")', source)

    def test_rebind_requires_app_granted_workspace_before_creating_binding(self):
        resource = _class(_parse("bkmonitor/packages/fta_web/issue/resources.py"), "RebindTapdWorkspaceResource")
        perform_request = _method(resource, "perform_request")
        source = ast.get_source_segment(_read("bkmonitor/packages/fta_web/issue/resources.py"), perform_request)

        self.assertIn("ListUserTapdWorkspaceResource._fetch_app_granted_ids", source)
        app_grant_index = source.index("ListUserTapdWorkspaceResource._fetch_app_granted_ids")
        create_binding_index = source.index("TapdWorkspaceBinding.objects.get_or_create")

        self.assertLess(app_grant_index, create_binding_index)
        self.assertIn("workspace_id not in app_granted_ids", source)
        self.assertIn("TAPD 项目未完成应用授权", source)

    def test_trace_tapd_frontend_rebinds_manually_unbound_workspace(self):
        service_source = _read(
            "bkmonitor/webpack/src/trace/pages/alarm-center/alarm-issues/issues-tapd/services/tapd.ts"
        )
        auth_source = _read(
            "bkmonitor/webpack/src/trace/pages/alarm-center/alarm-issues/issues-tapd/composables/use-tapd-auth.ts"
        )
        constants_source = _read("bkmonitor/webpack/src/trace/pages/alarm-center/alarm-issues/constant.ts")

        self.assertIn("MANUALLY_UNBOUND: 'manually_unbound'", constants_source)
        self.assertIn("export const rebindWorkspace", service_source)
        self.assertIn("export const unbindWorkspace", service_source)
        self.assertIn("export const revokeAuth", service_source)
        self.assertIn("item.is_bound === 'manually_unbound'", auth_source)
        self.assertIn("await rebindWorkspace", auth_source)
        self.assertIn("await getAuth()", auth_source)
        self.assertIn("installUrl.value.replace", auth_source)


if __name__ == "__main__":
    unittest.main()
