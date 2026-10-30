"""Exercise production host scopes without application or database bootstrap."""

import ast
import copy
import inspect
import os
import re
import subprocess
import typing
from collections.abc import Iterable
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.conf import settings
from rest_framework import serializers
from rest_framework.exceptions import NotFound, ParseError, PermissionDenied, ValidationError


ROOT = Path(__file__).resolve().parents[2]
REVISION = os.environ.get("HOST_ROOT_REVISION")
PERFORMANCE = "packages/monitor_web/performance/resources.py"
HANDLER = "bkmonitor/share/handler.py"


def load(path, name, namespace, methods=None, current=False):
    source = ROOT / path
    content = (
        subprocess.check_output(["git", "show", f"{REVISION}:bkmonitor/{path}"], cwd=ROOT, text=True)
        if REVISION and not current
        else source.read_text()
    )
    node = next(node for node in ast.parse(content).body if getattr(node, "name", None) == name)
    if methods is not None:
        node.bases = []
        node.body = [method for method in node.body if getattr(method, "name", None) in methods]
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"), namespace)
    return namespace[name]


@pytest.fixture
def production():
    if not settings.configured:
        settings.configure(USE_I18N=False, REST_FRAMEWORK={})
    no_related = type("NoRelatedResourceError", (Exception,), {})
    invalid = type("InvalidParamsError", (Exception,), {})
    denied = type("ParamsPermissionDeniedError", (Exception,), {})
    token_invalid = type("TokenValidatedError", (Exception,), {})

    def related_business(space_id):
        if int(space_id) in (2, -100):
            return 2
        if int(space_id) == -200:
            raise no_related("No related business")
        return int(space_id)

    namespace = dict(
        serializers=serializers,
        NotFound=NotFound,
        ParseError=ParseError,
        PermissionDenied=PermissionDenied,
        ValidationError=ValidationError,
        NoRelatedResourceError=no_related,
        validate_bk_biz_id=related_business,
        InvalidParamsError=invalid,
        ParamsPermissionDeniedError=denied,
        TokenValidatedError=token_invalid,
        SearchLockedError=type("SearchLockedError", (Exception,), {}),
        _=lambda value: value,
        copy=copy,
        typing=typing,
        Iterable=Iterable,
        re=re,
        ApiAuthToken=object,
        HOST_SCOPE_VERSION=1,
        HOST_DYNAMIC_TIME_PATTERN=re.compile(r"^now.*$"),
        scene_params_mapping={},
        is_ipv6_biz=lambda _space: False,
        Host=SimpleNamespace,
        ApiAuthResource=object,
        HOST_STATS_METRICS={"cpu": None, "mem": None, "disk": None},
    )
    # Keep the new shared validator available when replaying old callers.
    load("bkm_space/serializers.py", "resolve_cmdb_biz_id", namespace, current=True)
    load("bkm_space/serializers.py", "CMDBScopeSerializer", namespace, current=True)
    for name in ("TopoNode", "TopoTree"):
        load("api/cmdb/define.py", name, namespace)
    raw_tree = {
        "bk_obj_id": "biz",
        "bk_inst_id": 2,
        "bk_inst_name": "business",
        "child": [
            {
                "bk_obj_id": "set",
                "bk_inst_id": 3,
                "bk_inst_name": "set",
                "child": [{"bk_obj_id": "module", "bk_inst_id": 4, "bk_inst_name": "module", "child": []}],
            },
            {
                "bk_obj_id": "custom",
                "bk_inst_id": 7,
                "bk_inst_name": "custom",
                "child": [{"bk_obj_id": "module", "bk_inst_id": "5", "bk_inst_name": "module", "child": []}],
            },
        ],
    }
    namespace["_get_topo_tree"] = lambda _space: raw_tree
    resolve_modules = load("api/cmdb/default.py", "_trans_topo_node_to_module_ids", namespace)
    hosts = [
        SimpleNamespace(bk_host_id=101, bk_module_ids=[4], ip="192.0.2.1", bk_host_innerip="192.0.2.1", bk_cloud_id=0),
        SimpleNamespace(bk_host_id=102, bk_module_ids=[5], ip="192.0.2.2", bk_host_innerip="192.0.2.2", bk_cloud_id=0),
    ]
    for host in hosts:
        host.__dict__.update(
            display_name=host.ip,
            bk_biz_id=2,
            bk_cloud_name="default",
            bk_host_outerip="",
            bk_os_type="1",
            bk_os_name="Linux",
            bk_province_name="",
            bk_host_name=f"host-{host.bk_host_id}",
            ignore_monitoring=False,
            is_shielding=False,
        )

    def get_hosts(bk_biz_id, topo_nodes=None, bk_host_ids=None, bk_host_id=None):
        result = hosts
        if topo_nodes:
            modules = resolve_modules(bk_biz_id, copy.deepcopy(topo_nodes))
            result = [host for host in result if set(host.bk_module_ids) & modules]
        if bk_host_ids is not None:
            result = [host for host in result if host.bk_host_id in bk_host_ids]
        if bk_host_id is not None:
            result = [host for host in result if host.bk_host_id == bk_host_id]
        return result

    def get_page(page, page_size, **params):
        result = get_hosts(**params)
        return {"items": result[(page - 1) * page_size : page * page_size], "total": len(result)}

    def get_topo_tree(bk_biz_id, raw=False):
        return raw_tree if raw else namespace["TopoTree"](copy.deepcopy(raw_tree))

    cmdb = SimpleNamespace(
        get_host_by_topo_node=Mock(side_effect=get_hosts),
        get_host_by_id=Mock(side_effect=get_hosts),
        get_host_page=Mock(side_effect=get_page),
        get_topo_tree=Mock(side_effect=get_topo_tree),
        get_host_identities=Mock(side_effect=lambda **params: [vars(host) for host in get_hosts(**params)]),
    )
    namespace["api"] = SimpleNamespace(cmdb=cmdb)

    class Pool:
        def __init__(self, *_args):
            pass

        def apply_async(self, function, args=(), kwds=None):
            result = function(*args, **(kwds or {}))
            return SimpleNamespace(get=lambda: result)

        def close(self):
            pass

        def join(self):
            pass

    namespace.update(
        ThreadPool=Pool,
        query_business_host_metric_stats=Mock(return_value={"value": 2, "complete": True}),
        query_host_metric_stats=Mock(
            side_effect=lambda _biz, _category, selected, *_args: {"value": len(selected), "complete": True}
        ),
    )
    info = load(
        PERFORMANCE, "SearchHostInfoResource", namespace, {"RequestSerializer", "get_module_info", "perform_request"}
    )
    metric = load(
        PERFORMANCE,
        "SearchHostMetricResource",
        namespace,
        {"RequestSerializer", "_resolve_hosts", "validate_scope_host_ids"},
    )
    stats = load(PERFORMANCE, "SearchHostMetricStatsResource", namespace)
    namespace["Resource"] = object
    namespace["get_request"] = lambda **_kwargs: SimpleNamespace(method="POST", resolver_match=None)
    load(HANDLER, "validate_host_share_scope", namespace)
    load(HANDLER, "BaseApiAuthChecker", namespace)
    checker = load(HANDLER, "HostApiAuthChecker", namespace)
    namespace["AuthType"] = SimpleNamespace(Host="host")
    validate_share = load("packages/monitor_web/share/resources.py", "validate_host_share_target", namespace)
    graph_node = ast.parse((ROOT / "packages/monitor_web/grafana/resources/unify_query.py").read_text())
    if REVISION:
        graph_node = ast.parse(
            subprocess.check_output(
                ["git", "show", f"{REVISION}:bkmonitor/packages/monitor_web/grafana/resources/unify_query.py"],
                cwd=ROOT,
                text=True,
            )
        )
    graph = next(node for node in graph_node.body if getattr(node, "name", None) == "UnifyQueryRawResource")
    serializer = next(node for node in graph.body if getattr(node, "name", None) == "RequestSerializer")
    process = next(node for node in serializer.body if getattr(node, "name", None) == "process_filter_dict")
    exec(compile(ast.Module(body=[process], type_ignores=[]), "graph-filter", "exec"), namespace)
    return SimpleNamespace(
        namespace=namespace,
        info=info,
        metric=metric,
        stats=stats,
        cmdb=cmdb,
        raw_tree=raw_tree,
        resolve_modules=resolve_modules,
        checker=checker,
        validate_share=validate_share,
        process_filter=namespace["process_filter_dict"],
        invalid=invalid,
        denied=denied,
    )


def validated(resource, data):
    serializer = resource.RequestSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


@pytest.mark.parametrize("space, root", [(2, 2), (-100, -100), (-100, 2)])
@pytest.mark.parametrize("resource_name", ["info", "metric", "stats"])
def test_host_serializers_normalize_only_current_business_root(production, space, root, resource_name):
    resource = getattr(production, resource_name)
    params = {"bk_biz_id": space, "bk_obj_id": "biz", "bk_inst_id": root}
    if resource_name == "info":
        params.update(page=1, page_size=1)
    elif resource_name == "stats":
        params["category"] = "cpu"
    result = validated(resource, params)
    assert (result["bk_biz_id"], result["bk_inst_id"]) == (2, 2)
    assert params["bk_biz_id"] == space


@pytest.mark.parametrize("resource_name", ["info", "metric", "stats"])
def test_missing_related_business_is_explicit_not_found(production, resource_name):
    params = {"bk_biz_id": -200, "category": "cpu"}
    with pytest.raises(NotFound):
        validated(getattr(production, resource_name), params)
    production.cmdb.get_host_by_topo_node.assert_not_called()


@pytest.mark.parametrize("resource_name", ["info", "metric", "stats"])
def test_foreign_business_root_is_rejected(production, resource_name):
    with pytest.raises(PermissionDenied):
        validated(
            getattr(production, resource_name),
            {"bk_biz_id": -100, "bk_obj_id": "biz", "bk_inst_id": 9, "category": "cpu"},
        )


@pytest.mark.parametrize(
    "space, target, expected",
    [
        (-100, {"biz": [-100]}, {4, 5}),
        (-100, {"biz": [2]}, {4, 5}),
        (2, {"biz": [2]}, {4, 5}),
        (-100, {"biz": [9]}, set()),
        (-100, {"set": [3]}, {4}),
        (-100, {"custom": [7]}, {5}),
        (-100, {"module": [4]}, {4}),
        (-100, {"set": [3], "module": [5]}, {4, 5}),
        (-100, {"set": [999]}, set()),
    ],
)
def test_cmdb_root_and_descendants_preserve_input_and_shared_tree(production, space, target, expected):
    original_target, original_tree = copy.deepcopy(target), copy.deepcopy(production.raw_tree)
    assert production.resolve_modules(space, target) == expected
    assert target == original_target
    assert production.raw_tree == original_tree


@pytest.mark.parametrize("space, root", [(2, 2), (-100, -100), (-100, 2)])
def test_same_root_scope_agrees_in_page_full_metric_and_stats(production, space, root):
    target = {"bk_biz_id": space, "bk_obj_id": "biz", "bk_inst_id": root}
    full = production.info().perform_request(validated(production.info, target))
    page = production.info().perform_request(validated(production.info, {**target, "page": 1, "page_size": 1}))
    metric_params = validated(production.metric, target)
    push_target, metric_hosts, _ = production.metric()._resolve_hosts(metric_params)
    assert push_target is False
    stats = production.stats().perform_request(validated(production.stats, {**target, "category": "cpu"}))
    assert [host["bk_host_id"] for host in full] == [101, 102]
    assert page["total"] == 2
    assert [host["bk_host_id"] for host in page["items"]] == [101]
    assert [host.bk_host_id for host in metric_hosts] == [101, 102]
    assert stats == {"value": 2, "complete": True}


@pytest.mark.parametrize("obj, node, expected_id", [("set", 3, 101), ("module", 4, 101), ("custom", 7, 102)])
def test_subtree_scope_does_not_widen(production, obj, node, expected_id):
    target = {"bk_biz_id": -100, "bk_obj_id": obj, "bk_inst_id": node}
    result = production.info().perform_request(validated(production.info, target))
    assert [host["bk_host_id"] for host in result] == [expected_id]
    stats = production.stats().perform_request(validated(production.stats, {**target, "category": "cpu"}))
    assert stats["value"] == 1
    params = validated(production.metric, {**target, "bk_host_ids": [102 if expected_id == 101 else 101]})
    with pytest.raises(production.denied):
        production.metric.validate_scope_host_ids(params)


@pytest.mark.parametrize("node", ["-100", "2", ["-100"], ["2"]])
def test_graph_normalizes_root_and_retains_space_and_extra_filters(production, node):
    params = {
        "bk_biz_id": -100,
        "filter_dict": {
            "targets": [{"bk_obj_id": "biz", "bk_inst_id": node, "device_name": "cpu0"}],
            "display_name": "worker",
        },
    }
    result = production.process_filter(None, params["bk_biz_id"], params["filter_dict"])
    assert params["bk_biz_id"] == -100
    assert result["targets"][0] == {
        "bk_obj_id": "biz",
        "bk_inst_id": ["2"] if isinstance(node, list) else "2",
        "device_name": "cpu0",
    }
    assert result["display_name"] == "worker"


@pytest.mark.parametrize("node", ["9", ["-100", "9"]])
def test_graph_rejects_foreign_roots_including_mixed_lists(production, node):
    with pytest.raises(PermissionDenied):
        production.process_filter(None, -100, {"targets": [{"bk_obj_id": "biz", "bk_inst_id": node}]})


def make_token(root, space=-100, obj="biz"):
    return SimpleNamespace(
        bk_tenant_id="system",
        namespaces=[f"biz#{space}"],
        params={
            "lock_search": False,
            "default_time_range": [],
            "start_time": 100,
            "end_time": 200,
            "data": {"scope": {"version": 1, "target_type": "topo", "bk_obj_id": obj, "bk_inst_id": root}},
        },
    )


@pytest.mark.parametrize("space, root", [(2, 2), (-100, -100), (-100, 2)])
def test_root_share_create_and_access_accept_same_business_aliases(production, space, root):
    token = make_token(root, space)
    original = copy.deepcopy(token.params)
    assert production.validate_share("host", space, token.params["data"])["bk_inst_id"] == root
    checker = production.checker(token)
    for node in {space, 2}:
        checker.params_check({"bk_obj_id": "biz", "bk_inst_id": node})
        checker.query_target_check({"bk_obj_id": "biz", "bk_inst_id": str(node)}, "targets.0")
    with pytest.raises(production.denied):
        checker.params_check({"bk_obj_id": "biz", "bk_inst_id": 9})
    assert token.params == original
    assert token.namespaces == [f"biz#{space}"]


@pytest.mark.parametrize("obj, node", [("set", 3), ("module", 4), ("custom", 7)])
def test_subtree_share_cannot_become_a_business_root(production, obj, node):
    checker = production.checker(make_token(node, obj=obj))
    for root in (-100, 2):
        with pytest.raises(production.denied):
            checker.params_check({"bk_obj_id": "biz", "bk_inst_id": root})
        with pytest.raises(production.denied):
            checker.query_target_check({"bk_obj_id": "biz", "bk_inst_id": root}, "targets.0")


def test_host_share_cannot_become_a_business_root(production):
    token = make_token(-100)
    token.params["data"]["scope"] = {"version": 1, "target_type": "host", "bk_host_id": 101}
    checker = production.checker(token)
    with pytest.raises(production.denied):
        checker.params_check({"bk_obj_id": "biz", "bk_inst_id": -100})


@pytest.mark.parametrize("obj", ["biz", ["biz"]])
@pytest.mark.parametrize("node", ["-100", "2", ["-100"], ["2"], ["-100", "2"]])
def test_graph_serialized_root_passes_same_share_scope(production, obj, node):
    token = make_token(-100)
    checker = production.checker(token)
    target = production.process_filter(None, -100, {"targets": [{"bk_obj_id": obj, "bk_inst_id": node}]})["targets"][0]
    checker.query_target_check(target, "targets.0")
    with pytest.raises(production.denied):
        checker.query_target_check({"bk_obj_id": "biz", "bk_inst_id": ["2", "9"]}, "targets.0")


@pytest.mark.parametrize("node", [-100, 2, [-100], [2]])
@pytest.mark.parametrize("reverse", [False, True])
def test_mixed_host_identity_and_business_root_keep_original_scope(production, node, reverse):
    production.namespace["is_ipv6_biz"] = lambda business: business == 2
    host = {"bk_host_id": "101", "bk_target_ip": "192.0.2.1", "bk_target_cloud_id": "0"}
    root = {"bk_obj_id": "biz", "bk_inst_id": node}
    targets = [root, host] if reverse else [host, root]
    # The identity-mode fix is independently releasable; exercise it when present.
    kwargs = (
        {"is_host_query": True} if "is_host_query" in inspect.signature(production.process_filter).parameters else {}
    )
    result = production.process_filter(None, -100, {"targets": copy.deepcopy(targets)}, **kwargs)
    actual = next(target for target in result["targets"] if target.get("bk_obj_id") == "biz")
    assert actual["bk_inst_id"] == (["2"] if isinstance(node, list) else "2")
    production.checker(make_token(-100)).query_target_check(actual, "targets.0")


@pytest.mark.parametrize("node", [-200, 999, [-200], [999]])
@pytest.mark.parametrize("reverse", [False, True])
def test_unrelated_space_mixed_host_and_root_still_validates_business(production, node, reverse):
    host = {"bk_host_id": "101", "bk_target_ip": "192.0.2.1", "bk_target_cloud_id": "0"}
    root = {"bk_obj_id": "biz", "bk_inst_id": node}
    targets = [root, host] if reverse else [host, root]
    kwargs = (
        {"is_host_query": True} if "is_host_query" in inspect.signature(production.process_filter).parameters else {}
    )
    with pytest.raises(NotFound):
        production.process_filter(None, -200, {"targets": copy.deepcopy(targets)}, **kwargs)


def set_list_route(production, name):
    view_class = type(name, (), {})
    view_class.__module__ = "monitor_web.performance.views"
    production.namespace["get_request"] = lambda **_kwargs: SimpleNamespace(
        method="POST", resolver_match=SimpleNamespace(func=SimpleNamespace(cls=view_class, actions={"post": "create"}))
    )


@pytest.mark.parametrize("route", ["SearchHostInfoViewSet", "SearchHostMetricStatsViewSet"])
def test_root_share_list_routes_allow_only_authorized_descendants_and_hosts(production, route):
    set_list_route(production, route)
    checker = production.checker(make_token(-100))
    production.cmdb.get_host_page.assert_called_once_with(bk_biz_id=-100, page=1, page_size=1, topo_nodes={"biz": [2]})
    for obj, node in [("biz", -100), ("biz", 2), ("set", 3), ("module", 4), ("custom", 7)]:
        checker.check({"bk_obj_id": obj, "bk_inst_id": node, "page": 1})
    checker.check({"bk_host_id": 101, "page": 1})
    for target in [
        {"bk_obj_id": "biz", "bk_inst_id": 9},
        {"bk_obj_id": "module", "bk_inst_id": 999},
        {"bk_host_id": 999},
    ]:
        with pytest.raises(production.denied):
            checker.check({**target, "page": 1})


@pytest.mark.parametrize("route", ["SearchHostInfoViewSet", "SearchHostMetricStatsViewSet"])
def test_set_share_list_routes_cannot_expand_to_sibling_or_root(production, route):
    set_list_route(production, route)
    checker = production.checker(make_token(3, obj="set"))
    checker.check({"bk_obj_id": "module", "bk_inst_id": 4, "page": 1})
    for obj, node in [("module", 5), ("custom", 7), ("biz", 2), ("biz", -100)]:
        with pytest.raises(production.denied):
            checker.check({"bk_obj_id": obj, "bk_inst_id": node, "page": 1})
