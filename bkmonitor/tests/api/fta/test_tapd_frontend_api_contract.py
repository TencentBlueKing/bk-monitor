from __future__ import annotations

"""TAPD Resource 命名与前端生成接口的兼容性契约。"""

import ast
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[4]


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def _class_names(path: str) -> set[str]:
    module = ast.parse(_read(path))
    return {node.name for node in ast.iter_child_nodes(module) if isinstance(node, ast.ClassDef)}


class TestTapdFrontendAPIContract(unittest.TestCase):
    EXPECTED_APIS = {
        "GetUserWorkspaceResource": (
            "get_user_workspace",
            "getUserWorkspace",
            "tapd/user_workspace",
        ),
        "UnbindWorkspaceResource": (
            "unbind_workspace",
            "unbindWorkspace",
            "tapd/unbind_workspace",
        ),
        "RebindWorkspaceResource": (
            "rebind_workspace",
            "rebindWorkspace",
            "tapd/rebind_workspace",
        ),
        "RevokeAuthResource": (
            "revoke_auth",
            "revokeAuth",
            "tapd/revoke_auth",
        ),
    }

    def test_resource_names_preserve_generated_frontend_contract(self):
        resource_names = _class_names("bkmonitor/packages/fta_web/issue/resources.py")
        views = _read("bkmonitor/packages/fta_web/issue/views.py")
        api_module = _read("bkmonitor/webpack/src/monitor-api/modules/issue.js")

        for resource_name, (resource_attribute, function_name, endpoint) in self.EXPECTED_APIS.items():
            with self.subTest(function_name=function_name):
                self.assertIn(resource_name, resource_names)
                self.assertIn(
                    f'resource.issue.{resource_attribute}, endpoint="{endpoint}"',
                    views,
                )
                self.assertIn(f"export const {function_name} = request(", api_module)
                self.assertIn(f"  {function_name},", api_module)


if __name__ == "__main__":
    unittest.main()
