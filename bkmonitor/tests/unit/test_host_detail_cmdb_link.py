"""Exercise host detail links without application or database bootstrap."""

import ast
import copy
from collections.abc import Iterable
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.parse import urljoin

import pytest


ROOT = Path(__file__).resolve().parents[2]


def load_class(path, name, namespace, methods=None):
    """Execute production definitions, omitting unrelated resource/bootstrap code."""
    source = ROOT / path
    node = next(node for node in ast.parse(source.read_text()).body if getattr(node, "name", None) == name)
    if methods is not None:
        node.bases = []
        node.body = [method for method in node.body if getattr(method, "name", None) in methods]
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"), namespace)
    return namespace[name]


@pytest.fixture
def host_detail():
    namespace = {"copy": copy, "Iterable": Iterable}
    load_class("api/cmdb/define.py", "TopoNode", namespace)
    topo_tree_class = load_class("api/cmdb/define.py", "TopoTree", namespace)
    cmdb = SimpleNamespace(get_host_by_id=Mock(), get_topo_tree=Mock())
    get_agent_status = Mock(return_value={101: "on"})
    namespace.update(
        {
            "api": SimpleNamespace(cmdb=cmdb),
            "resource": SimpleNamespace(cc=SimpleNamespace(get_agent_status=get_agent_status)),
            "settings": SimpleNamespace(BK_CC_URL="https://cmdb.example.test/", OS_TYPE_NAME_DICT={}),
            "AGENT_STATUS": SimpleNamespace(ON="on", NOT_EXIST="not_exist", NO_DATA="no_data", UNKNOWN="unknown"),
            "_": lambda value: value,
            "urljoin": urljoin,
        }
    )
    detail = load_class(
        "packages/monitor_web/scene_view/resources/host.py",
        "GetHostOrTopoNodeDetailResource",
        namespace,
        {"get_host_info"},
    )
    return SimpleNamespace(detail=detail, cmdb=cmdb, get_agent_status=get_agent_status, topo_tree_class=topo_tree_class)


def build_host(request_biz_id, module_ids):
    # The CMDB adapter retains the caller's space identity in Host.bk_biz_id.
    return SimpleNamespace(
        bk_biz_id=request_biz_id,
        bk_host_id=101,
        bk_module_ids=module_ids,
        bk_state="running",
        is_shielding=False,
        ignore_monitoring=False,
        bk_host_name="host.example.test",
        bk_host_innerip="192.0.2.1",
        bk_host_innerip_v6="",
        bk_host_outerip="",
        bk_host_outerip_v6="",
    )


def build_topo_tree(topo_tree_class):
    return topo_tree_class(
        {
            "bk_obj_id": "biz",
            "bk_inst_id": 2,
            "bk_inst_name": "business",
            "child": [
                {
                    "bk_obj_id": "set",
                    "bk_inst_id": 3,
                    "bk_inst_name": "set-3",
                    "child": [
                        {"bk_obj_id": "module", "bk_inst_id": 4, "bk_inst_name": "module-4", "child": []},
                        {"bk_obj_id": "module", "bk_inst_id": 5, "bk_inst_name": "module-5", "child": []},
                    ],
                }
            ],
        }
    )


def result_value(result, name):
    return next(item["value"] for item in result if item["name"] == name)


@pytest.mark.parametrize("request_biz_id", [2, -100])
@pytest.mark.parametrize("module_ids", [[4], []])
def test_host_link_uses_cmdb_topology_business_and_preserves_request_space(host_detail, request_biz_id, module_ids):
    host = build_host(request_biz_id, module_ids)
    host_detail.cmdb.get_host_by_id.return_value = [host]
    host_detail.cmdb.get_topo_tree.return_value = build_topo_tree(host_detail.topo_tree_class)

    result = host_detail.detail.get_host_info(request_biz_id, host.bk_host_id)

    assert result_value(result, "内网IP") == {
        "url": "https://cmdb.example.test/#/resource/host/2/101",
        "value": "192.0.2.1",
    }
    assert result_value(result, "所属模块") == (["set-3 / module-4"] if module_ids else [])
    host_detail.cmdb.get_host_by_id.assert_called_once_with(bk_biz_id=request_biz_id, bk_host_ids=[101])
    host_detail.cmdb.get_topo_tree.assert_called_once_with(bk_biz_id=request_biz_id)
    host_detail.get_agent_status.assert_called_once_with(bk_biz_id=request_biz_id, hosts=[host])
    assert host.bk_biz_id == request_biz_id


@pytest.mark.parametrize("request_biz_id", [2, -100])
def test_missing_host_returns_empty_without_topology_or_agent_queries(host_detail, request_biz_id):
    host_detail.cmdb.get_host_by_id.return_value = []

    assert host_detail.detail.get_host_info(request_biz_id, 101) == {}

    host_detail.cmdb.get_host_by_id.assert_called_once_with(bk_biz_id=request_biz_id, bk_host_ids=[101])
    host_detail.cmdb.get_topo_tree.assert_not_called()
    host_detail.get_agent_status.assert_not_called()
