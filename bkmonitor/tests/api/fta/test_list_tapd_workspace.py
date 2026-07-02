import ast
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from rest_framework import serializers


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _load_list_tapd_workspace_resource(tapd_api):
    source = (PROJECT_ROOT / "packages/fta_web/issue/resources.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    class_node = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "ListTapdWorkspaceResource"
    )
    class_source = ast.get_source_segment(source, class_node)

    namespace = {
        "Resource": object,
        "serializers": serializers,
        "ThreadPoolExecutor": ThreadPoolExecutor,
        "as_completed": as_completed,
        "api": SimpleNamespace(tapd=tapd_api),
        "logger": mock.Mock(),
    }
    exec(class_source, namespace)
    return namespace["ListTapdWorkspaceResource"], namespace["logger"]


def test_list_tapd_workspace_invalid_item_falls_back_without_crashing():
    tapd_api = SimpleNamespace(
        get_granted_workspaces=mock.Mock(return_value={"list": [{"OpenOrganizationApp": {"created": "2026-06-09"}}]}),
        get_workspace_info=mock.Mock(side_effect=KeyError("Workspace")),
    )
    resource_cls, logger = _load_list_tapd_workspace_resource(tapd_api)

    result = resource_cls().perform_request({"bk_biz_id": 2, "limit": 30, "page": 1})

    assert result == [
        {
            "workspace_id": "",
            "workspace_name": "",
            "pretty_name": "",
            "created": "2026-06-09",
            "creator": "",
            "description": "",
            "status": "",
            "category": "",
        }
    ]
    logger.warning.assert_called_once()


def test_tapd_query_endpoints_use_read_permission():
    source = (PROJECT_ROOT / "packages/fta_web/issue/views.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    viewset = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "IssueViewSet")
    read_only_assignment = next(
        node
        for node in viewset.body
        if isinstance(node, ast.Assign)
        and any(getattr(target, "id", None) == "READ_ONLY_ENDPOINTS" for target in node.targets)
    )

    read_only_endpoints = ast.literal_eval(read_only_assignment.value)

    assert "tapd/workspace" in read_only_endpoints
    assert "issue/get_tapd_fields" in read_only_endpoints
