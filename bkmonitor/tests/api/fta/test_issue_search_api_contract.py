from __future__ import annotations

"""Issue 查询 Resource 与前端生成接口的轻量契约测试。"""

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


class TestIssueSearchAPIContract(unittest.TestCase):
    def test_resource_name_generates_existing_frontend_api_contract(self):
        resources = _parse("bkmonitor/packages/fta_web/issue/resources.py")
        _class(resources, "IssueSearchResource")

        views = _read("bkmonitor/packages/fta_web/issue/views.py")
        self.assertIn(
            'ResourceRoute("POST", resource.issue.issue_search, endpoint="issue/search")',
            views,
        )

        api_module = _read("bkmonitor/webpack/src/monitor-api/modules/issue.js")
        self.assertIn(
            "export const issueSearch = request('POST', 'fta/issue/issue/search/');",
            api_module,
        )
        self.assertIn("  issueSearch,", api_module)
        self.assertNotIn("export const searchIssue", api_module)


if __name__ == "__main__":
    unittest.main()
