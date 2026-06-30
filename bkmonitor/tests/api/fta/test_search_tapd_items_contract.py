from __future__ import annotations

"""
Backend contract tests for searching existing TAPD items from Issue APIs.

These tests use AST/source inspection so they can run without the full Django
service stack, matching the lightweight contract coverage used by nearby TAPD
tests.
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


def _method(class_node: ast.ClassDef, name: str) -> ast.FunctionDef:
    for node in class_node.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"method {name} not found")


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def _string_constants(node: ast.AST) -> set[str]:
    return {child.value for child in ast.walk(node) if isinstance(child, ast.Constant) and isinstance(child.value, str)}


def _class_assignment(class_node: ast.ClassDef, name: str) -> ast.Assign:
    for node in class_node.body:
        if isinstance(node, ast.Assign) and any(getattr(target, "id", None) == name for target in node.targets):
            return node
    raise AssertionError(f"assignment {name} not found")


def _has_item_status_subscript(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if not isinstance(child, ast.Subscript):
            continue
        if not isinstance(child.value, ast.Name) or child.value.id != "item":
            continue
        if isinstance(child.slice, ast.Constant) and child.slice.value == "status":
            return True
    return False


class TestSearchTapdItemsContract(unittest.TestCase):
    def test_resource_queries_stories_and_bugs_with_bug_field_mapping(self):
        resource = _class(_parse("bkmonitor/packages/fta_web/issue/resources.py"), "SearchTAPDItemsResource")
        query_method = _method(resource, "_query_tapd_items")
        call_names = {_call_name(node.func) for node in ast.walk(query_method) if isinstance(node, ast.Call)}

        self.assertIn("api.tapd.get_stories", call_names)
        self.assertIn("api.tapd.get_bugs", call_names)
        self.assertIn(
            "BUG_FIELD_MAPPING", {node.attr for node in ast.walk(resource) if isinstance(node, ast.Attribute)}
        )

    def test_status_display_name_tolerates_items_without_status(self):
        resource = _class(_parse("bkmonitor/packages/fta_web/issue/resources.py"), "SearchTAPDItemsResource")
        query_method = _method(resource, "_query_tapd_items")

        self.assertFalse(_has_item_status_subscript(query_method))

    def test_search_endpoint_is_read_only_and_registered(self):
        viewset = _class(_parse("bkmonitor/packages/fta_web/issue/views.py"), "IssueViewSet")
        read_only_endpoints = _string_constants(_class_assignment(viewset, "READ_ONLY_ENDPOINTS"))
        routes = _string_constants(_class_assignment(viewset, "resource_routes"))

        self.assertIn("issue/search_tapd_items", read_only_endpoints)
        self.assertIn("issue/search_tapd_items", routes)
        self.assertIn("issue/create_tapd", routes)

    def test_monitor_api_exports_search_and_create_tapd(self):
        source = _read("bkmonitor/webpack/src/monitor-api/modules/issue.js")

        self.assertIn("export const searchTAPDItems", source)
        self.assertIn("export const createTapd", source)
        self.assertIn("searchTAPDItems,", source)
        self.assertIn("createTapd,", source)


if __name__ == "__main__":
    unittest.main()
