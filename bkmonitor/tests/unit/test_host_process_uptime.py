"""Exercise the production uptime resource without application/database bootstrap."""

import ast
import copy
import logging
import re
from collections import defaultdict
from functools import cached_property
from itertools import chain, product
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest


ROOT = Path(__file__).resolve().parents[2]


def load_function(path, name, namespace, class_name=None):
    source = ast.parse((ROOT / path).read_text())
    for owner in class_name if isinstance(class_name, tuple) else (class_name,):
        if owner:
            source = next(node for node in source.body if getattr(node, "name", None) == owner)
    function = next(node for node in source.body if getattr(node, "name", None) == name)
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), "exec"), namespace)
    return namespace[name]


@pytest.fixture
def scope_namespace():
    space_api = SimpleNamespace(
        gen_space_uid=lambda kind, scope: f"{kind}__{scope}",
        get_space_detail=Mock(return_value=SimpleNamespace(space_uid="bkci__example")),
        get_related_space=Mock(return_value=SimpleNamespace(bk_biz_id=2)),
    )
    namespace = {
        "Host": SimpleNamespace,
        "defaultdict": defaultdict,
        "settings": SimpleNamespace(IPV6_SUPPORT_BIZ_LIST=[], IS_ACCESS_BK_DATA=False),
        "time": SimpleNamespace(time=lambda: 1_700_003_600),
        "SpaceApi": space_api,
        "SpaceTypeEnum": SimpleNamespace(BKCC=SimpleNamespace(value="bkcc")),
        "api": SimpleNamespace(SpaceApi=space_api),
    }
    load_function("bkm_space/errors.py", "NoRelatedResourceError", namespace)
    load_function("bkm_space/utils.py", "bk_biz_id_to_space_uid", namespace)
    load_function("bkm_space/validate.py", "validate_bk_biz_id", namespace)
    load_function("bkmonitor/commons/tools.py", "is_ipv6_biz", namespace)
    load_function("packages/monitor_web/cc/resources/cmdb.py", "_build_host_target_filter", namespace)
    return namespace


@pytest.fixture
def uptime_resource(scope_namespace):
    namespace = scope_namespace
    get_host = Mock()
    load_data_source = Mock(return_value=lambda **kwargs: SimpleNamespace(**kwargs))
    query_data = Mock()
    query = Mock(return_value=SimpleNamespace(query_data=query_data))
    namespace.update(
        api=SimpleNamespace(cmdb=SimpleNamespace(get_host_by_id=get_host), SpaceApi=namespace["SpaceApi"]),
        load_data_source=load_data_source,
        UnifyQuery=query,
        DataSourceLabel=SimpleNamespace(BK_MONITOR_COLLECTOR="bk_monitor"),
        DataTypeLabel=SimpleNamespace(TIME_SERIES="time_series"),
    )
    perform_request = load_function(
        "packages/monitor_web/scene_view/resources/host.py",
        "perform_request",
        namespace,
        class_name="GetHostProcessUptimeResource",
    )
    return SimpleNamespace(
        request=lambda params: perform_request(None, params),
        get_host=get_host,
        load_data_source=load_data_source,
        query=query,
        query_data=query_data,
        settings=namespace["settings"],
        space_api=namespace["SpaceApi"],
    )


def make_host(ip="192.0.2.10", cloud_id=7):
    return SimpleNamespace(bk_host_id=101, bk_host_innerip=ip, bk_host_innerip_v6="2001:db8::10", bk_cloud_id=cloud_id)


def request_params(scope=2, **kwargs):
    return {
        "bk_biz_id": scope,
        "bk_host_id": 101,
        "display_name": "nginx",
        "start_time": 1_700_003_540,
        "end_time": 1_700_003_600,
        **kwargs,
    }


def configure_rows(resource, host):
    """Apply the emitted target conditions to rows with colliding process names."""
    resource.get_host.return_value = [host]
    rows = [
        {
            "bk_host_id": 101,
            "bk_target_ip": host.bk_host_innerip,
            "bk_target_cloud_id": 7,
            "display_name": "nginx",
            "_result_": 7200,
        },
        {
            "bk_host_id": 102,
            "bk_target_ip": host.bk_host_innerip,
            "bk_target_cloud_id": 8,
            "display_name": "nginx",
            "_result_": 300,
        },
        {
            "bk_host_id": 101,
            "bk_target_ip": host.bk_host_innerip,
            "bk_target_cloud_id": 7,
            "display_name": "other",
            "_result_": 60,
        },
    ]
    if not host.bk_host_innerip:
        # IPv6 rows carry the host ID rather than an IPv4 target label.
        for row in rows:
            row.pop("bk_target_ip")

    def matches(row, conditions):
        return all(
            key in row and str(row[key]) in [str(value) for value in values if value is not None]
            for key, value in conditions.items()
            for values in [value if isinstance(value, list) else [value]]
        )

    def query_rows(**_kwargs):
        data_source = resource.query.call_args.kwargs["data_sources"][0]
        conditions = data_source.filter_dict
        targets = conditions.get("targets", [{}])
        common = {key: value for key, value in conditions.items() if key != "targets"}
        return [row for row in rows if matches(row, common) and any(matches(row, target) for target in targets)]

    resource.query_data.side_effect = query_rows


@pytest.mark.parametrize("scope", [2, -2])
def test_ipv4_uptime_keeps_ip_cloud_and_process_filter(uptime_resource, scope):
    host = make_host()
    configure_rows(uptime_resource, host)

    assert uptime_resource.request(request_params(scope)) == {"value": 7200, "unit": "s"}
    uptime_resource.get_host.assert_called_once_with(bk_biz_id=scope, bk_host_ids=[101])
    assert uptime_resource.query.call_args.kwargs["bk_biz_id"] == scope
    source = uptime_resource.query.call_args.kwargs["data_sources"][0]
    assert source.group_by == ["bk_target_ip", "bk_target_cloud_id", "display_name"]
    assert source.table == "system.proc"
    assert source.metrics == [{"field": "uptime", "method": "MAX", "alias": "A"}]


@pytest.mark.parametrize("scope, ipv6_scopes", [(2, [2]), (-2, [-2]), (-2, [2])])
def test_ipv6_uptime_targets_selected_host_even_when_scope_has_no_ipv6_flag(uptime_resource, scope, ipv6_scopes):
    uptime_resource.settings.IPV6_SUPPORT_BIZ_LIST = ipv6_scopes
    configure_rows(uptime_resource, make_host(ip=""))

    assert uptime_resource.request(request_params(scope)) == {"value": 7200, "unit": "s"}
    query = uptime_resource.query.call_args.kwargs
    assert query["bk_biz_id"] == scope
    assert query["data_sources"][0].filter_dict == {"targets": [{"bk_host_id": ["101"]}], "display_name": "nginx"}


def test_ipv6_enabled_scope_uses_host_identity_for_dual_stack_host(uptime_resource):
    uptime_resource.settings.IPV6_SUPPORT_BIZ_LIST = [2]
    configure_rows(uptime_resource, make_host())

    assert uptime_resource.request(request_params()) == {"value": 7200, "unit": "s"}
    assert uptime_resource.query.call_args.kwargs["data_sources"][0].filter_dict == {
        "targets": [{"bk_host_id": ["101"]}],
        "display_name": "nginx",
    }


@pytest.mark.parametrize(
    "times, expected_start",
    [
        ({"start_time": 1_700_000_000, "end_time": 1_700_003_600}, 1_700_003_420_000),
        ({"start_time": 1_700_003_540, "end_time": 1_700_003_600}, 1_700_003_540_000),
        ({}, 1_700_003_420_000),
    ],
)
def test_uptime_keeps_selected_snapshot_window_in_milliseconds(uptime_resource, times, expected_start):
    uptime_resource.get_host.return_value = [make_host()]
    uptime_resource.query_data.return_value = [{"_result_": 0}]
    params = {key: value for key, value in request_params().items() if key not in {"start_time", "end_time"}}

    assert uptime_resource.request({**params, **times}) == {"value": 0, "unit": "s"}
    uptime_resource.query_data.assert_called_once_with(
        start_time=expected_start, end_time=1_700_003_600_000, instant=True
    )


def test_missing_host_skips_uptime_query(uptime_resource):
    uptime_resource.get_host.return_value = []

    assert uptime_resource.request(request_params()) == []
    uptime_resource.load_data_source.assert_not_called()
    uptime_resource.query.assert_not_called()


def test_missing_uptime_keeps_empty_value_and_unit(uptime_resource):
    uptime_resource.get_host.return_value = [make_host()]
    uptime_resource.query_data.return_value = []

    assert uptime_resource.request(request_params()) == {"value": "", "unit": "s"}


@pytest.fixture
def compiled_query(scope_namespace):
    """Keep production scope resolution and UQ compilation; replace remote I/O only."""
    namespace = scope_namespace
    namespace.update(
        copy=copy,
        re=re,
        product=product,
        chain=chain,
        Any=Any,
        cached_property=cached_property,
        DataSource=object,
        PrometheusTimeSeriesDataSource=type("UnusedPrometheusDataSource", (), {}),
        DataSourceLabel=SimpleNamespace(BK_DATA="bk_data", BK_MONITOR_COLLECTOR="bk_monitor"),
        DataTypeLabel=SimpleNamespace(TIME_SERIES="time_series"),
        APM_METRIC_DATA_LABEL="apm",
        AGG_METHOD_REAL_TIME="REAL_TIME",
        CpAggMethods={},
        AggMethods={},
        add_expression_functions=lambda expression, _functions: expression,
        bk_biz_id_to_bk_tenant_id=lambda _scope: "tenant",
        DEFAULT_TENANT_ID="tenant",
        logger=logging.getLogger(__name__),
        time_interval_align=lambda value, step: value // step * step,
    )
    load_function("bkmonitor/data_source/data_source/__init__.py", "_filter_dict_to_conditions", namespace)
    load_function("bkmonitor/data_source/unify_query/functions.py", "normalize_metric_method", namespace)
    compiler = load_function(
        "bkmonitor/data_source/data_source/__init__.py",
        "to_unify_query_config",
        namespace,
        class_name="TimeSeriesDataSource",
    )

    class Source(SimpleNamespace):
        to_unify_query_config = compiler

        def _parse_function_params(self):
            return {}, []

        def set_bk_tenant_id(self, tenant):
            self.bk_tenant_id = tenant

    def source(**kwargs):
        return Source(
            **{
                "table": "system.proc",
                "metrics": [{"field": "uptime", "method": "MAX", "alias": "A"}],
                "filter_dict": {},
                "group_by": ["display_name"],
                "interval": 60,
                **kwargs,
            },
            data_source_label="bk_monitor",
            where=[],
            data_label="",
            time_field="time",
            time_shift=False,
            time_offset=0,
        )

    query_path = "bkmonitor/data_source/unify_query/query.py"
    for name in ("__init__", "space_uid", "get_unify_query_params"):
        load_function(query_path, name, namespace, class_name="UnifyQuery")

    class Query:
        __init__ = namespace["__init__"]
        space_uid = namespace["space_uid"]
        get_unify_query_params = namespace["get_unify_query_params"]

    namespace["UnifyQueryRawResource"] = SimpleNamespace(re_down_sample=re.compile(r"^\d+[mshdw]$"))
    for name in ("process_filter_dict", "to_str", "validate"):
        load_function(
            "packages/monitor_web/grafana/resources/unify_query.py",
            name,
            namespace,
            class_name=("UnifyQueryRawResource", "RequestSerializer"),
        )

    class Serializer:
        process_filter_dict = namespace["process_filter_dict"]
        to_str = namespace["to_str"]
        validate = namespace["validate"]

    def process(scope, filters, **config):
        attrs = Serializer().validate(
            {
                "bk_biz_id": scope,
                "down_sample_range": "",
                "query_configs": [
                    {
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "table": "system.proc",
                        "interval": 60,
                        "filter_dict": filters,
                        **config,
                    }
                ],
            }
        )
        assert attrs["bk_biz_id"] == scope
        return attrs["query_configs"][0]["filter_dict"]

    return SimpleNamespace(
        namespace=namespace,
        source=source,
        query=Query,
        process=process,
    )


def query_conditions(params):
    conditions = params["query_list"][0]["conditions"]
    assert set(conditions["condition_list"]) <= {"and"}
    return {field["field_name"]: field["value"] for field in conditions["field_list"]}


@pytest.mark.parametrize("scope", [2, -101])
@pytest.mark.parametrize("ipv6_scopes, ipv6_enabled", [([], False), ([2], True), ([-101], False)])
@pytest.mark.parametrize("identity", ["host_only", "dual", "pure_ipv6"])
def test_graph_compiler_uses_related_identity_mode_and_original_space(
    compiled_query, scope, ipv6_scopes, ipv6_enabled, identity
):
    compiled_query.namespace["settings"].IPV6_SUPPORT_BIZ_LIST = ipv6_scopes
    target = {"bk_host_id": "101"}
    if identity != "host_only":
        target.update(bk_target_ip="" if identity == "pure_ipv6" else "192.0.2.10", bk_target_cloud_id="7")
    filters = compiled_query.process(scope, {"targets": [target], "display_name": "nginx"})
    query = compiled_query.query(
        bk_biz_id=scope, data_sources=[compiled_query.source(filter_dict=filters)], expression="A"
    )
    params = query.get_unify_query_params(1_700_003_540_000, 1_700_003_600_000)

    expected = {"display_name": ["nginx"]}
    if ipv6_enabled:
        expected["bk_host_id"] = ["101"]
    elif identity != "host_only":
        expected.update(bk_target_ip=[target["bk_target_ip"]], bk_target_cloud_id=["7"])
    assert query_conditions(params) == expected
    assert query.bk_biz_id == scope
    assert params["space_uid"] == ("bkcc__2" if scope > 0 else "bkci__example")
    assert params["query_list"][0]["field_name"] == "uptime"


@pytest.mark.parametrize("scope", [2, -101])
@pytest.mark.parametrize("host_ip", ["192.0.2.10", ""])
def test_uptime_compiler_selects_host_across_address_reuse(compiled_query, scope, host_ip):
    namespace = compiled_query.namespace
    namespace["settings"].IPV6_SUPPORT_BIZ_LIST = [2]
    get_host = Mock(return_value=[make_host(ip=host_ip)])
    namespace["api"].cmdb = SimpleNamespace(get_host_by_id=get_host)
    rows = [
        {"bk_host_id": "101", "bk_target_ip": "192.0.2.20", "display_name": "nginx", "_result_": 7200},
        {"bk_host_id": "102", "bk_target_ip": "192.0.2.10", "display_name": "nginx", "_result_": 300},
        {"bk_host_id": "101", "bk_target_ip": "192.0.2.20", "display_name": "other", "_result_": 60},
    ]
    for row in rows:
        row["bk_target_cloud_id"] = "7"
        if not host_ip:
            row.pop("bk_target_ip")

    queries = []

    def query_factory(**kwargs):
        query = compiled_query.query(**kwargs)

        def query_data(**times):
            params = query.get_unify_query_params(times["start_time"], times["end_time"])
            queries.append(params)
            conditions = query_conditions(params)
            return [row for row in rows if all(str(row.get(key)) in values for key, values in conditions.items())]

        query.query_data = query_data
        return query

    namespace.update(UnifyQuery=query_factory, load_data_source=lambda *_args: compiled_query.source)
    perform_request = load_function(
        "packages/monitor_web/scene_view/resources/host.py",
        "perform_request",
        namespace,
        class_name="GetHostProcessUptimeResource",
    )

    assert perform_request(None, request_params(scope)) == {"value": 7200, "unit": "s"}
    get_host.assert_called_once_with(bk_biz_id=scope, bk_host_ids=[101])
    assert queries[0]["space_uid"] == ("bkcc__2" if scope > 0 else "bkci__example")
    assert query_conditions(queries[0]) == {"display_name": ["nginx"], "bk_host_id": ["101"]}


def test_unrelated_space_cannot_drop_graph_host_identity(compiled_query):
    namespace = compiled_query.namespace
    namespace["SpaceApi"].get_related_space.return_value = None
    filters = {"targets": [{"bk_host_id": "101", "bk_target_ip": "192.0.2.10", "bk_target_cloud_id": "7"}]}

    processed = compiled_query.process(-101, filters)
    assert processed == filters
    query = compiled_query.query(
        bk_biz_id=-101, data_sources=[compiled_query.source(filter_dict=processed)], expression="A"
    )
    params = query.get_unify_query_params()
    assert params["space_uid"] == "bkci__example"
    assert query_conditions(params) == {
        "bk_host_id": ["101"],
        "bk_target_ip": ["192.0.2.10"],
        "bk_target_cloud_id": ["7"],
    }


def test_unrelated_space_cannot_start_uptime_query(uptime_resource, scope_namespace):
    uptime_resource.space_api.get_related_space.return_value = None
    uptime_resource.get_host.return_value = [make_host()]
    uptime_resource.query_data.return_value = []

    with pytest.raises(scope_namespace["NoRelatedResourceError"]):
        uptime_resource.request(request_params(-101))
    uptime_resource.get_host.assert_called_once_with(bk_biz_id=-101, bk_host_ids=[101])
    uptime_resource.query.assert_not_called()


@pytest.mark.parametrize("node_type", ["biz", "set", "module"])
def test_graph_topology_target_keeps_original_space_without_identity_resolution(compiled_query, node_type):
    namespace = compiled_query.namespace
    namespace["SpaceApi"].get_related_space.return_value = None
    target = {"bk_obj_id": node_type, "bk_inst_id": "3"}
    filters = {"target": [target], "display_name": "nginx", "optional": "undefined"}
    processed = compiled_query.process(-101, filters)
    query = compiled_query.query(
        bk_biz_id=-101, data_sources=[compiled_query.source(filter_dict=processed)], expression="A"
    )

    assert processed == {"target": [target], "display_name": "nginx"}
    assert query.get_unify_query_params()["space_uid"] == "bkci__example"
    namespace["SpaceApi"].get_related_space.assert_not_called()


def test_graph_non_host_targets_do_not_resolve_related_resources(compiled_query):
    target = {"pod_name": "example"}
    assert compiled_query.process(-101, {"targets": [target]}) == {"targets": [target]}
    compiled_query.namespace["SpaceApi"].get_related_space.assert_not_called()


@pytest.mark.parametrize(
    "config",
    [
        {"data_source_label": "custom"},
        {"data_type_label": "event"},
        {"table": "apm.example"},
        {"data_label": "example"},
    ],
)
def test_graph_generic_queries_keep_original_target_mode_without_related_resource(compiled_query, config):
    namespace = compiled_query.namespace
    namespace["settings"].IPV6_SUPPORT_BIZ_LIST = [2]
    namespace["SpaceApi"].get_related_space.return_value = None
    filters = {"targets": [{"bk_host_id": "101", "bk_target_ip": "192.0.2.10", "bk_target_cloud_id": "7"}]}

    assert compiled_query.process(-101, filters, **config) == {
        "targets": [{"bk_target_ip": "192.0.2.10", "bk_target_cloud_id": "7"}]
    }
    namespace["SpaceApi"].get_related_space.assert_not_called()
