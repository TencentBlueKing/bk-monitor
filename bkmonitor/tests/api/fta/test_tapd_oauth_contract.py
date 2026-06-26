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

    def test_user_oauth_state_is_session_bound(self):
        utils_module = _parse("bkmonitor/packages/fta_web/issue/utils/tapd.py")
        generate_auth_url = _function(utils_module, "generate_auth_url")
        callback = _function(_parse("bkmonitor/packages/fta_web/issue/resources.py"), "tapd_user_oauth_callback")
        utils_source = ast.get_source_segment(
            _read("bkmonitor/packages/fta_web/issue/utils/tapd.py"), generate_auth_url
        )
        callback_source = ast.get_source_segment(_read("bkmonitor/packages/fta_web/issue/resources.py"), callback)

        self.assertIn("request.session", utils_source)
        self.assertIn("tapd_oauth_state_", utils_source)
        self.assertNotIn("generate_signed_state(payload)", utils_source)
        self.assertIn("request.session.get(session_key)", callback_source)
        self.assertNotIn("verify_signed_state(state", callback_source)
        self.assertIn("redirect_uri=backend_callback.rstrip", callback_source)

    def test_app_install_callback_still_uses_signed_state(self):
        callback = _function(_parse("bkmonitor/packages/fta_web/issue/resources.py"), "tapd_app_install_callback")
        self.assertIn("verify_signed_state", _call_names(callback))


if __name__ == "__main__":
    unittest.main()
