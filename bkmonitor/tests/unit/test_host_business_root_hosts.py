"""Run actual CMDB host consumers against a stale topology and current host data."""

import abc
import ast
import copy
import typing
from collections import Counter, defaultdict
from collections.abc import Iterable
from functools import cached_property
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.conf import settings
from rest_framework.exceptions import NotFound, ParseError, PermissionDenied

ROOT = Path(__file__).resolve().parents[2]


def load(path, name, namespace, methods=None):
    node = next(n for n in ast.parse((ROOT / path).read_text()).body if getattr(n, "name", None) == name)
    if isinstance(node, ast.FunctionDef):
        node.decorator_list = []
    elif methods is not None:
        node.body = [n for n in node.body if getattr(n, "name", None) in methods]
        if name != "CMDBBaseResource":
            node.bases = []
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(ROOT / path), "exec"), namespace)
    return namespace[name]


@pytest.fixture
def cmdb():
    namespace = dict(
        abc=abc,
        copy=copy,
        typing=typing,
        Iterable=Iterable,
        Counter=Counter,
        defaultdict=defaultdict,
        cached_property=cached_property,
        settings=SimpleNamespace(
            HOST_DYNAMIC_FIELDS=[],
            HOST_DISPLAY_FIELDS=[],
            HOST_DISABLE_MONITOR_STATES=[],
            HOST_DISABLE_NOTICE_STATES=[],
            BK_SUPPLIER_ACCOUNT="0",
        ),
        _=lambda value: value,
        DEFAULT_TENANT_ID="system",
        get_backend_username=lambda **_kwargs: "operator",
        bk_biz_id_to_space_uid=lambda scope: f"example__{scope}",
        SpaceTypeEnum=SimpleNamespace(BKCC=SimpleNamespace(value="bkcc")),
        SpaceApi=SimpleNamespace(
            get_related_space=lambda uid, _kind: SimpleNamespace(bk_biz_id=2) if uid == "example__-100" else None
        ),
    )
    load("bkm_space/errors.py", "NoRelatedResourceError", namespace)
    load("bkm_space/validate.py", "validate_bk_biz_id", namespace)
    for name in ("_split_member_list", "BaseNode", "TopoNode", "TopoTree", "Host", "ServiceInstance"):
        load("api/cmdb/define.py", name, namespace)
    path = "api/cmdb/default.py"
    for name in (
        "split_inner_host",
        "_host_from_raw",
        "_host_full_cloud",
        "_trans_topo_node_to_module_ids",
        "get_host_dict_by_biz",
    ):
        load(path, name, namespace)
    # The baseline does not have this helper; its actual consumer methods still run.
    if "def _is_biz_root_scope(" in (ROOT / path).read_text():
        load(path, "_is_biz_root_scope", namespace)
    for name in ("GetHostByTopoNode", "GetHostPage", "GetHostIdentities"):
        load(path, name, namespace, {"perform_request"})

    class APIResource:
        def full_request_data(self, params):
            return copy.deepcopy(params)

    namespace["APIResource"] = APIResource
    transport = load("api/cmdb/client.py", "CMDBBaseResource", namespace, {"full_request_data"})()
    transport.page_sort = ""
    transport.bk_tenant_id = "system"
    tree = {
        "bk_obj_id": "biz",
        "bk_inst_id": 2,
        "child": [
            {"bk_obj_id": "set", "bk_inst_id": 3, "child": [{"bk_obj_id": "module", "bk_inst_id": 8, "child": []}]}
        ],
    }
    namespace["_get_topo_tree"] = lambda _scope: copy.deepcopy(tree)
    records = [
        {
            "host": {"bk_host_id": host, "bk_host_innerip": address, "bk_cloud_id": 0},
            "topo": [{"bk_set_id": 3, "module": [{"bk_module_id": module}]}],
        }
        for host, address, module in [(101, "192.0.2.1", 8), (102, "192.0.2.2", 9)]
    ]
    calls = []

    def matches(rule, host):
        if "condition" in rule:
            values = [matches(child, host) for child in rule["rules"]]
            return all(values) if rule["condition"] == "AND" else any(values)
        if rule["operator"] == "contains":
            return bool(host.get(rule["field"]))
        if rule["operator"] == "equal":
            return host.get(rule["field"]) == rule["value"]
        return host.get(rule["field"]) in rule["value"]

    def query(params):
        params = transport.full_request_data(params)
        calls.append(copy.deepcopy(params))
        assert params["bk_biz_id"] == 2
        selected = copy.deepcopy(records)
        if "module_property_filter" in params:
            modules = set(params["module_property_filter"]["rules"][0]["value"])
            selected = [row for row in selected if row["topo"][0]["module"][0]["bk_module_id"] in modules]
        if "host_property_filter" in params:
            selected = [row for row in selected if matches(params["host_property_filter"], row["host"])]
        page = params.get("page", {"start": 0, "limit": 500})
        return {"count": len(selected), "info": selected[page["start"] : page["start"] + page["limit"]]}

    namespace.update(
        client=SimpleNamespace(list_biz_hosts_topo=query),
        batch_request=lambda client, params: client(params)["info"],
        mem_cache=SimpleNamespace(clear=lambda: None),
        api=SimpleNamespace(cmdb=SimpleNamespace(search_cloud_area=lambda: [])),
    )

    def request(kind, scope, nodes, **kwargs):
        params = {"bk_biz_id": scope, "topo_nodes": nodes, "fields": namespace["Host"].Fields, **kwargs}
        resource = namespace[kind]()
        if kind == "GetHostPage":
            result = resource.perform_request({"page": 1, "page_size": 500, **params})
            return [host.bk_host_id for host in result["items"]]
        result = resource.perform_request(params)
        if kind == "GetHostIdentities":
            return [host["bk_host_id"] for host in result]
        return [host.bk_host_id for host in result]

    return SimpleNamespace(request=request, calls=calls, tree=tree, namespace=namespace)


CONSUMERS = ["GetHostByTopoNode", "GetHostPage", "GetHostIdentities"]


@pytest.mark.parametrize("kind", CONSUMERS)
@pytest.mark.parametrize("scope, root", [(2, 2), (-100, -100), (-100, 2), (-100, "2"), (2, "2")])
def test_current_business_root_keeps_hosts_in_new_modules(cmdb, kind, scope, root):
    nodes = {"biz": [root]}
    before = copy.deepcopy(nodes)
    tree_before = copy.deepcopy(cmdb.tree)
    assert cmdb.request(kind, scope, nodes) == [101, 102]
    assert nodes == before and cmdb.tree == tree_before
    assert all("module_property_filter" not in call for call in cmdb.calls)


@pytest.mark.parametrize("kind", CONSUMERS)
@pytest.mark.parametrize(
    "nodes, expected", [({"biz": [999]}, []), ({"set": [3]}, [101]), ({"module": [8]}, [101]), ({"module": [9]}, [102])]
)
def test_foreign_root_and_child_scopes_keep_topology_filter(cmdb, kind, nodes, expected):
    assert cmdb.request(kind, -100, nodes) == expected


@pytest.mark.parametrize("kind", CONSUMERS)
def test_root_dominates_mixed_union_without_stale_module_filter(cmdb, kind):
    assert cmdb.request(kind, -100, {"biz": [-100], "module": [8]}) == [101, 102]


@pytest.mark.parametrize("kind", ["GetHostPage", "GetHostIdentities"])
def test_explicit_host_filter_is_preserved_under_root(cmdb, kind):
    assert cmdb.request(kind, -100, {"biz": [-100]}, bk_host_id=102) == [102]


def test_unrelated_space_is_not_a_business_root(cmdb):
    assert not cmdb.namespace["_is_biz_root_scope"](-200, {"biz": [-200]})


@pytest.mark.parametrize("kind", CONSUMERS)
def test_unscoped_business_hosts_do_not_require_topology(cmdb, kind):
    def unexpected(_scope):
        raise AssertionError("unscoped host query must not load the topology")

    cmdb.namespace["_get_topo_tree"] = unexpected
    assert cmdb.request(kind, -100, {}) == [101, 102]


@pytest.fixture
def frontend_topology(cmdb):
    if not settings.configured:
        settings.configure(USE_I18N=False, REST_FRAMEWORK={})
    namespace = cmdb.namespace
    namespace.update(NotFound=NotFound, ParseError=ParseError, PermissionDenied=PermissionDenied)
    load("bkm_space/serializers.py", "resolve_cmdb_biz_id", namespace)
    load("packages/monitor_web/commons/cc/utils/topo_tree_tools.py", "foreach_topo_tree", namespace)
    for node in [cmdb.tree, cmdb.tree["child"][0], cmdb.tree["child"][0]["child"][0]]:
        node["bk_inst_name"] = node["bk_obj_id"]
    tree_request = Mock(side_effect=lambda _params: copy.deepcopy(cmdb.tree))
    namespace.update(
        resource=SimpleNamespace(commons=SimpleNamespace(cc_topo_tree=tree_request)),
        get_host_view_display_fields=lambda _scope: ("bk_host_innerip", "bk_host_name"),
    )
    resource = load(
        "packages/monitor_web/commons/cc/resources/frontend_resources.py",
        "GetTopoTree",
        namespace,
        {"filter_scope_node", "handle_node", "remove_empty_nodes", "perform_request"},
    )()
    return SimpleNamespace(request=resource.perform_request, tree_request=tree_request)


@pytest.mark.parametrize("scope, root", [(2, 2), (-100, -100), (-100, 2)])
def test_scoped_frontend_tree_accepts_root_alias_and_preserves_space(frontend_topology, scope, root):
    params = {"bk_biz_id": scope, "bk_obj_id": "biz", "bk_inst_id": root}
    before = params.copy()
    result = frontend_topology.request(params)
    assert result[0]["id"] == "biz|2"
    assert result[0]["bk_biz_id"] == scope
    assert result[0]["children"][0]["bk_biz_id"] == scope
    frontend_topology.tree_request.assert_called_once_with(before)
    assert params == before


@pytest.mark.parametrize("scope, root, error", [(-100, 999, PermissionDenied), (-200, -200, NotFound)])
def test_scoped_frontend_tree_rejects_foreign_or_unrelated_root(frontend_topology, scope, root, error):
    with pytest.raises(error):
        frontend_topology.request({"bk_biz_id": scope, "bk_obj_id": "biz", "bk_inst_id": root})


@pytest.mark.parametrize("obj, node", [("set", 3), ("module", 8)])
def test_child_scope_frontend_tree_remains_restricted(frontend_topology, obj, node):
    result = frontend_topology.request({"bk_biz_id": -100, "bk_obj_id": obj, "bk_inst_id": node})
    assert result[0]["id"] == "biz|2"
    assert len(result[0]["children"]) == 1
    assert result[0]["children"][0]["id"] == "set|3"
