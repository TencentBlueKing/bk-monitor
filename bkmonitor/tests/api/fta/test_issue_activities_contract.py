from __future__ import annotations

"""
Backend contract tests for Issue activity list repair.

These tests use AST/source inspection so they can run without the full Django
service stack. They guard the resolved-only read-repair contract for missing
IssueActivityDocument records.
"""

import ast
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[4]
RESOURCE_PATH = "bkmonitor/packages/fta_web/issue/resources.py"


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def _parse(path: str) -> ast.Module:
    return ast.parse(_read(path))


def _class(module: ast.Module, name: str) -> ast.ClassDef:
    for node in module.body:
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


def _calls(function: ast.FunctionDef) -> list[str]:
    return [_call_name(node.func) for node in ast.walk(function) if isinstance(node, ast.Call)]


def _source(node: ast.AST) -> str:
    return ast.get_source_segment(_read(RESOURCE_PATH), node) or ""


class TestIssueActivitiesResolvedRepairContract(unittest.TestCase):
    def _resource(self) -> ast.ClassDef:
        return _class(_parse(RESOURCE_PATH), "ListIssueActivitiesResource")

    def test_list_activities_validates_issue_and_invokes_repair(self):
        perform_request = _method(self._resource(), "perform_request")
        calls = _calls(perform_request)
        source = _source(perform_request)

        self.assertIn("IssueDocument.get_issue_or_raise", calls)
        self.assertIn("self._repair_missing_resolved_activity", calls)
        self.assertIn("repair_activity = self._repair_missing_resolved_activity(issue, hits)", source)
        self.assertIn("hits.insert(0, repair_activity)", source)

    def test_repair_is_resolved_only_and_uses_resolved_time(self):
        repair_method = _method(self._resource(), "_repair_missing_resolved_activity")
        source = _source(repair_method)

        self.assertIn("issue.status != IssueStatus.RESOLVED", source)
        self.assertIn('not getattr(issue, "resolved_time", None)', source)
        self.assertIn("now = int(issue.resolved_time)", source)
        self.assertIn("to_value=IssueStatus.RESOLVED", source)

    def test_repair_skips_existing_resolved_status_activity(self):
        repair_method = _method(self._resource(), "_repair_missing_resolved_activity")
        source = _source(repair_method)

        self.assertIn("hit.activity_type == IssueActivityType.STATUS_CHANGE", source)
        self.assertIn('getattr(hit, "to_value", None) == IssueStatus.RESOLVED', source)
        self.assertIn("return None", source)

    def test_repair_writes_best_effort_activity_with_source_marker(self):
        repair_method = _method(self._resource(), "_repair_missing_resolved_activity")
        calls = _calls(repair_method)
        source = _source(repair_method)

        self.assertIn("IssueActivityDocument.bulk_create", calls)
        self.assertIn('"repair_source": "list_issue_activities"', source)
        self.assertIn("logger.warning", calls)
        self.assertIn("return activity", source)


if __name__ == "__main__":
    unittest.main()
