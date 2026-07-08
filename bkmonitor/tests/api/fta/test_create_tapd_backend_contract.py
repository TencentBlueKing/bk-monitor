from __future__ import annotations

"""
Backend contract tests for Issue -> TAPD creation.

These tests intentionally use AST/source inspection like the existing TAPD
workspace tests, because importing the full fta_web resource graph requires the
runtime service stack. They guard the deployable API contract that frontend
integration depends on.
"""

import ast
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[4]


def _parse(path: str) -> ast.Module:
    return ast.parse((REPO_ROOT / path).read_text(encoding="utf-8"))


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


def _calls(function: ast.FunctionDef) -> list[tuple[str, int]]:
    result = []
    for node in ast.walk(function):
        if isinstance(node, ast.Call):
            result.append((_call_name(node.func), node.lineno))
    return result


def _contains_name(node: ast.AST, name: str) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and child.id == name:
            return True
        if isinstance(child, ast.Attribute) and child.attr == name:
            return True
        if isinstance(child, ast.Constant) and child.value == name:
            return True
    return False


def _source(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


class TestCreateTapdBackendContract(unittest.TestCase):
    def test_relation_model_and_migration_store_tapd_id_as_string(self):
        model = _class(_parse("bkmonitor/bkmonitor/models/issue.py"), "IssueTapdRelation")

        tapd_id_assign = None
        for node in model.body:
            if isinstance(node, ast.Assign) and any(
                getattr(target, "id", None) == "tapd_id" for target in node.targets
            ):
                tapd_id_assign = node
                break
        self.assertIsNotNone(tapd_id_assign)
        self.assertEqual(_call_name(tapd_id_assign.value.func), "models.CharField")
        max_length = next(
            keyword.value.value
            for keyword in tapd_id_assign.value.keywords
            if keyword.arg == "max_length" and isinstance(keyword.value, ast.Constant)
        )
        self.assertGreaterEqual(max_length, 64)

        migration = _parse("bkmonitor/bkmonitor/migrations/0198_add_issue_tapd_relation.py")
        tapd_id_field = None
        for node in ast.walk(migration):
            if (
                isinstance(node, ast.Tuple)
                and len(node.elts) >= 2
                and isinstance(node.elts[0], ast.Constant)
                and node.elts[0].value == "tapd_id"
            ):
                tapd_id_field = node.elts[1]
                break
        self.assertIsNotNone(tapd_id_field)
        self.assertEqual(_call_name(tapd_id_field.func), "models.CharField")

    def test_create_tapd_validates_issue_before_calling_external_api(self):
        resource = _class(_parse("bkmonitor/packages/fta_web/issue/resources.py"), "CreateTapdResource")
        perform_request = _method(resource, "perform_request")
        calls = _calls(perform_request)

        get_issue_lines = [line for name, line in calls if name == "IssueDocument.get_issue_or_raise"]
        create_tapd_lines = [line for name, line in calls if name == "self._create_tapd"]

        self.assertTrue(get_issue_lines, "CreateTapdResource must validate issue ownership before creating TAPD")
        self.assertTrue(create_tapd_lines)
        self.assertLess(min(get_issue_lines), min(create_tapd_lines))

    def test_create_tapd_persists_sync_status_after_sync_task_is_implemented(self):
        resource = _class(_parse("bkmonitor/packages/fta_web/issue/resources.py"), "CreateTapdResource")
        request_serializer = _class(resource, "RequestSerializer")
        validate = _method(request_serializer, "validate")
        perform_request = _method(resource, "perform_request")
        perform_source = ast.get_source_segment(
            _source("bkmonitor/packages/fta_web/issue/resources.py"), perform_request
        )

        has_sync_status_guard = False
        for node in ast.walk(validate):
            if isinstance(node, ast.If) and _contains_name(node.test, "sync_status"):
                has_sync_status_guard = any(
                    isinstance(child, ast.Raise) and _contains_name(child, "ValidationError")
                    for child in ast.walk(node)
                )
                break

        self.assertFalse(has_sync_status_guard)
        self.assertIn('sync_status = validated_request_data["sync_status"]', perform_source)
        self.assertIn('"sync_status": sync_status', perform_source)

    def test_issue_list_tapd_count_query_is_scoped_by_biz(self):
        source = (REPO_ROOT / "bkmonitor/packages/fta_web/issue/handlers/issue.py").read_text(encoding="utf-8")
        self.assertIn("page_tapd_biz_ids", source)
        self.assertIn("bk_biz_id__in=page_tapd_biz_ids", source)

    def test_link_tapd_updates_sync_status_after_sync_task_is_implemented(self):
        resource = _class(_parse("bkmonitor/packages/fta_web/issue/resources.py"), "LinkIssueToTapdResource")
        request_serializer = _class(resource, "RequestSerializer")
        validate = _method(request_serializer, "validate")
        perform_request = _method(resource, "perform_request")
        perform_source = ast.get_source_segment(
            _source("bkmonitor/packages/fta_web/issue/resources.py"), perform_request
        )

        has_sync_status_guard = False
        for node in ast.walk(validate):
            if isinstance(node, ast.If) and _contains_name(node.test, "sync_status"):
                has_sync_status_guard = any(
                    isinstance(child, ast.Raise) and _contains_name(child, "ValidationError")
                    for child in ast.walk(node)
                )
                break

        self.assertFalse(has_sync_status_guard)
        self.assertIn('sync_status = validated_request_data["sync_status"]', perform_source)
        self.assertIn("obj.sync_status = sync_status", perform_source)
        self.assertIn('IssueTapdRelation.objects.bulk_update(to_update, ["sync_status"])', perform_source)

    def test_sync_tapd_status_task_queries_enabled_relations_and_resolves_issue(self):
        tasks_source = _source("bkmonitor/packages/fta_web/tasks.py")
        tasks = _parse("bkmonitor/packages/fta_web/tasks.py")
        sync_func = next(
            node
            for node in tasks.body
            if isinstance(node, ast.FunctionDef) and node.name == "sync_issues_from_tapd_status"
        )
        query_func = next(
            node
            for node in tasks.body
            if isinstance(node, ast.FunctionDef) and node.name == "_query_and_check_tapd_status"
        )
        resolve_func = next(
            node
            for node in tasks.body
            if isinstance(node, ast.FunctionDef) and node.name == "_resolve_issue_by_tapd_sync"
        )
        sync_source = ast.get_source_segment(tasks_source, sync_func)
        query_source = ast.get_source_segment(tasks_source, query_func)
        resolve_source = ast.get_source_segment(tasks_source, resolve_func)

        self.assertIn("IssueTapdRelation.objects.filter(sync_status=True)", sync_source)
        self.assertIn("sync_relations = list(", sync_source)
        self.assertIn("IssueDocument.search(all_indices=True)", sync_source)
        self.assertIn('stats["skipped"] += total_skipped', sync_source)
        self.assertIn("SearchTAPDItemsResource._query_tapd_items", query_source)
        self.assertIn('fields="id,status"', query_source)
        self.assertIn("_is_tapd_status_completed", query_source)
        self.assertIn("api.issue.resolve", resolve_source)
        self.assertIn('operator="system"', resolve_source)

    def test_sync_tapd_status_task_is_scheduled_on_resource_queue(self):
        source = _source("bkmonitor/config/celery/config.py")

        self.assertIn('"fta_web.tasks.sync_tapd_issue_status"', source)
        self.assertIn('"schedule": crontab(minute="*/10")', source)
        self.assertIn('"options": {"queue": "celery_resource"}', source)

    def test_link_tapd_rejects_duplicate_tapd_ids_before_bulk_create(self):
        resource = _class(_parse("bkmonitor/packages/fta_web/issue/resources.py"), "LinkIssueToTapdResource")
        request_serializer = _class(resource, "RequestSerializer")
        validate_source = ast.get_source_segment(
            _source("bkmonitor/packages/fta_web/issue/resources.py"), _method(request_serializer, "validate")
        )

        self.assertIn("seen_tapd_ids", validate_source)
        self.assertIn("duplicate TAPD ID", validate_source)

    def test_link_tapd_validates_workspace_and_tapd_items_before_bulk_create(self):
        resource = _class(_parse("bkmonitor/packages/fta_web/issue/resources.py"), "LinkIssueToTapdResource")
        perform_request = _method(resource, "perform_request")
        calls = _calls(perform_request)

        validate_workspace_lines = [line for name, line in calls if name == "self._validate_workspace_binding"]
        validate_items_lines = [line for name, line in calls if name == "self._validate_tapd_items"]
        create_lines = [line for name, line in calls if name == "self._bulk_create_relations"]

        self.assertTrue(validate_workspace_lines)
        self.assertTrue(validate_items_lines)
        self.assertTrue(create_lines)
        self.assertLess(min(validate_workspace_lines), min(create_lines))
        self.assertLess(min(validate_items_lines), min(create_lines))

    def test_link_tapd_item_validation_uses_tapd_api_query(self):
        resource = _class(_parse("bkmonitor/packages/fta_web/issue/resources.py"), "LinkIssueToTapdResource")
        validate_items = _method(resource, "_validate_tapd_items")
        call_names = {name for name, _ in _calls(validate_items)}

        self.assertIn("SearchTAPDItemsResource._query_tapd_items", call_names)
        self.assertIn("serializers.ValidationError", call_names)

    def test_link_tapd_workspace_validation_checks_local_binding(self):
        resource = _class(_parse("bkmonitor/packages/fta_web/issue/resources.py"), "LinkIssueToTapdResource")
        validate_workspace = _method(resource, "_validate_workspace_binding")
        source = ast.get_source_segment(_source("bkmonitor/packages/fta_web/issue/resources.py"), validate_workspace)

        self.assertIn("TapdWorkspaceBinding.objects.filter", source)
        self.assertIn("space_uid_to_bk_tenant_id", source)
        self.assertIn("bk_biz_id_to_space_uid", source)


if __name__ == "__main__":
    unittest.main()
