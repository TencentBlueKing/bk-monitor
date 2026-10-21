"""Scoped MCP facade checks, runnable without databases or project services.

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=.:bkmonitor bkmonitor/.venv/bin/python -m pytest \
  -c /dev/null -p no:cacheprovider bkmonitor/kernel_api/tests/test_mcp_response_limits.py

Resource / query methods are loaded from their actual AST with model adapters
replaced. DynamicSettings, JSON encoding, requests and gzip decoding are real.
"""

import ast
import copy
import gzip
import http.client
import io
import json
import logging
import sys
import tracemalloc
from pathlib import Path
from types import ModuleType, SimpleNamespace as NS
from unittest.mock import Mock
from urllib.parse import urljoin

import django
import pytest
import requests
from django.conf import settings
from django.http import HttpResponse, StreamingHttpResponse
from django.utils.functional import empty
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from urllib3.response import HTTPResponse

BASE = Path(__file__).resolve().parents[2]
if not settings.configured:
    settings.configure(
        SECRET_KEY="offline",
        INSTALLED_APPS=[],
        DATABASES={},
        USE_I18N=False,
        BASE_DIR=str(BASE),
        APP_CODE="monitor",
        BKAPP_DEPLOY_PLATFORM="bkte",
        RSA_PRIVATE_KEY="",
        TRANSLATE_SNMP_TRAP_DIMENSIONS=False,
    )
    django.setup()


def source(path, name, **namespace):
    node = ast.parse((BASE / path).read_text())
    for part in name.split("."):
        node = next(child for child in node.body if getattr(child, "name", None) == part)
    node.decorator_list = []
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(BASE / path), "exec"), namespace)
    return namespace[node.name]


def http_response(body, status=200, headers=None):
    response = requests.Response()
    response.status_code = status
    response.headers.update(headers or {})
    response.raw = HTTPResponse(body=io.BytesIO(body), headers=headers or {}, preload_content=False)
    return response


@pytest.fixture
def limits(monkeypatch):
    from bkmonitor.utils.common_utils import DatetimeEncoder

    class Resource:
        def validate_response_data(self, value):
            return value

    # Load the real module except the model-heavy Resource import.
    tree = ast.parse((BASE / "kernel_api/resource/mcp_response.py").read_text())
    tree.body = [n for n in tree.body if not (isinstance(n, ast.ImportFrom) and n.module == "core.drf_resource")]
    namespace = {"Resource": Resource, "__name__": "scoped_mcp_limits"}
    exec(compile(tree, "mcp_response.py", "exec"), namespace)
    namespace["get_request"] = Mock(return_value=None)
    namespace["settings"] = NS(MCP_MAX_RESPONSE_BYTES=1000)
    module = ModuleType("kernel_api.adapters")

    class Renderer:
        def get_result(self, data, renderer_context=None):
            return {"result": True, "code": 200, "message": "OK", "data": data}

    module.ApiRenderer = Renderer
    monkeypatch.setitem(sys.modules, module.__name__, module)
    namespace["DatetimeEncoder"] = DatetimeEncoder
    return NS(**namespace, namespace=namespace)


@pytest.mark.parametrize(
    "req",
    [
        NS(META={"HTTP_X_BKAPI_MCP_SERVER_NAME": "metrics"}),
        NS(META={"HTTP_X_BK_REQUEST_SOURCE": "bkm-mcp-client"}),
        NS(META={}, native_mcp_tool="search_logs"),
        NS(META={}, mcp_usage_tool="execute_tool"),
        NS(META={}, mcp_usage_event_id="legacy-authenticated-mcp"),
    ],
)
def test_mcp_markers_are_recognized(limits, req):
    limits.get_request.return_value = req
    assert limits.is_mcp_request()


@pytest.mark.parametrize("req", [None, NS(META={}), NS(META={"HTTP_X_BK_REQUEST_SOURCE": "other"})])
def test_non_mcp_result_and_validation_are_unchanged(limits, req):
    limits.get_request.return_value = req
    limits.settings.MCP_MAX_RESPONSE_BYTES = 0  # must not even consult MCP config
    data = {"large": "x" * 10000}
    assert limits.MCPResource().validate_response_data(data) is data


@pytest.mark.parametrize("header_value", [None, ""])
def test_empty_mcp_header_config_does_not_classify_normal_requests(limits, header_value):
    limits.settings.AIDEV_AGENT_MCP_REQUEST_HEADER_VALUE = header_value
    limits.get_request.return_value = NS(META={})
    assert not limits.is_mcp_request()


@pytest.mark.parametrize("data", [{"logs": "x" * 2000}, {"series": ["x"] * 1000}, ["x" * 2000]])
def test_generic_guard_rejects_different_tool_results(limits, data):
    limits.get_request.return_value = NS(META={}, native_mcp_tool="query")
    with pytest.raises(ValidationError, match="result_too_large"):
        limits.MCPResource().validate_response_data(data)


def test_success_result_and_parameters_are_not_rewritten(limits):
    limits.get_request.return_value = NS(META={}, native_mcp_tool="query")
    result = {"series": [{"datapoints": [[1, 1000]], "dimensions": {"pod": "demo"}}]}
    original = copy.deepcopy(result)
    assert limits.MCPResource().validate_response_data(result) is result
    assert result == original


def test_renderer_probe_cannot_mutate_already_wrapped_result(limits):
    class MutatingRenderer:
        def get_result(self, value, renderer_context):
            value.setdefault("trace_id", "trace")
            return value

    sys.modules["kernel_api.adapters"].ApiRenderer = MutatingRenderer
    limits.get_request.return_value = NS(META={}, native_mcp_tool="query")
    result = {"result": True, "data": {"rows": []}}
    assert limits.MCPResource().validate_response_data(result) is result
    assert "trace_id" not in result


def test_raw_http_and_streaming_results_are_preserved(limits):
    limits.get_request.return_value = NS(META={}, native_mcp_tool="export")
    for response in (HttpResponse(b"x" * 2000), StreamingHttpResponse(iter([b"large stream"]))):
        assert limits.MCPResource().validate_response_data(response) is response


@pytest.mark.parametrize("value", [0, -1, True, "100", None])
def test_invalid_config_cannot_disable_limit(limits, value):
    limits.settings.MCP_MAX_RESPONSE_BYTES = value
    with pytest.raises(ValueError):
        limits.get_max_response_bytes()


def test_exact_json_limit_includes_ascii_escaping(limits):
    data = {"label": '中文\n"\u2028', "values": [1, 2]}
    size = len(json.dumps(data, ensure_ascii=True).encode())
    limits.check_json_size(data, size)
    with pytest.raises(ValidationError):
        limits.check_json_size(data, size - 1)


def test_envelope_is_counted_without_changing_renderer(limits):
    limits.get_request.return_value = NS(META={}, native_mcp_tool="query")
    limits.settings.MCP_MAX_RESPONSE_BYTES = 100
    data = {"text": "x" * 80}
    assert len(json.dumps(data).encode()) < 100
    with pytest.raises(ValidationError):
        limits.MCPResource().validate_response_data(data)


def test_native_unified_envelope_is_counted_before_original_middleware_adds_it(limits):
    request = NS(META={}, native_mcp_tool="execute_range_query")
    limits.get_request.return_value = request
    limits.settings.MCP_MAX_RESPONSE_BYTES = 180
    data = {"text": "x" * 80}
    assert limits.MCPResource().validate_response_data(data) is data
    request.unified_mcp_operation = "execute_tool"
    with pytest.raises(ValidationError):
        limits.MCPResource().validate_response_data(data)
    assert data == {"text": "x" * 80}


@pytest.mark.parametrize("header", [{}, {"Content-Length": "bad"}, {"Content-Length": "1"}])
def test_reader_rejects_before_json_decode_without_trusting_length(limits, header):
    response = Mock(headers=header, status_code=200)
    response.raw.read.side_effect = [b"x" * 100] * 10
    decoder = Mock(side_effect=AssertionError("must not parse oversized JSON"))
    limits.namespace["json"] = NS(loads=decoder)
    with pytest.raises(ValidationError):
        limits.read_bounded_json(response, 200)
    assert response.raw.read.call_count == 3
    decoder.assert_not_called()


def test_large_content_length_does_not_read(limits):
    response = Mock(headers={"Content-Length": "10001"})
    with pytest.raises(ValidationError):
        limits.read_bounded_json(response, 10000)
    response.raw.read.assert_not_called()


def test_reader_exact_utf8_limit_and_small_error(limits):
    body = '{"value":"中文"}'.encode()
    assert limits.read_bounded_json(http_response(body), len(body)) == ({"value": "中文"}, None)
    assert limits.read_bounded_json(http_response(b"failed", 503), 100) == (None, "failed")


@pytest.mark.parametrize("status", [200, 500, 302])
def test_error_and_success_bodies_share_the_same_limit(limits, status):
    with pytest.raises(ValidationError):
        limits.read_bounded_json(http_response(b"x" * 1001, status), 1000)


def test_bounded_gzip_and_concatenated_members(limits):
    small = gzip.compress(b'{"ok":') + gzip.compress(b"true}")
    assert limits.read_bounded_json(http_response(small, headers={"Content-Encoding": "gzip"}), 100) == (
        {"ok": True},
        None,
    )
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb") as writer:
        for _ in range(60):
            writer.write(b"x" * (1024 * 1024))
    response = http_response(buffer.getvalue(), headers={"Content-Encoding": "gzip"})
    tracemalloc.start()
    try:
        with pytest.raises(ValidationError):
            limits.read_bounded_json(response, 256 * 1024)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < 2 * 1024 * 1024


def test_range_query_non_mcp_still_calls_original_api(limits):
    original = Mock(return_value={"original": True})
    perform = source(
        "kernel_api/resource/metrics.py",
        "ExecuteRangeQueryResource.perform_request",
        is_mcp_request=lambda: False,
        resource=NS(grafana=NS(graph_promql_query=original)),
    )
    params = {"promql": "up", "start_time": 1, "end_time": 2, "step": "1m"}
    assert perform(None, params) == {"original": True}
    original.assert_called_once_with(**params)


@pytest.fixture
def graph_pair(monkeypatch):
    import re
    from bkmonitor.utils.time_tools import hms_string, parse_time_compare_abbreviation, time_interval_align

    monkeypatch.setattr(settings, "USE_TZ", True)

    class Resource:
        def validate_request_data(self, data):
            serializer = self.RequestSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            return serializer.validated_data

    raw = [{"group_keys": ["pod"], "group_values": ["demo"], "values": [[60000, 1], [120000, 2]]}]
    provider = Mock(side_effect=lambda **kwargs: {"series": copy.deepcopy(raw)})
    bounded = Mock(side_effect=lambda params, max_bytes: {"series": copy.deepcopy(raw)})
    processor = NS(process_formatted_data=lambda params, series: series)
    namespace = dict(
        Resource=Resource,
        serializers=serializers,
        re=re,
        get_auto_interval=lambda *args: 60,
        hms_string=hms_string,
        parse_time_compare_abbreviation=parse_time_compare_abbreviation,
        time_interval_align=time_interval_align,
        get_cookies_filter=lambda: {"scope": "cookie"},
        PrometheusTimeSeriesDataSource=NS(filter_dict_to_promql_match=lambda value: 'scope="cookie"'),
        timezone=NS(get_current_timezone_name=lambda: "UTC"),
        api=NS(unify_query=NS(query_data_by_promql=provider)),
        HeatMapProcessor=processor,
        QueryTypeProcessor=processor,
        AddNullDataProcessor=processor,
        GraphUnifyQueryResource=NS(translate_dimensions=lambda params, series: series),
        query_promql=bounded,
        get_max_response_bytes=lambda: 1000,
        ValidationError=ValidationError,
    )
    cls = source("packages/monitor_web/grafana/resources/unify_query.py", "GraphPromqlQueryResource", **namespace)
    namespace["GraphPromqlQueryResource"] = cls
    new = source("kernel_api/resource/mcp_metrics_query.py", "execute_range_query", **namespace)
    return cls, new, provider, bounded


@pytest.mark.parametrize(
    "overrides",
    [
        {},
        {"step": "auto"},
        {"step": "60"},
        {"type": "instant"},
        {"time_alignment": False},
        {"format": "table"},
        {"down_sample_range": "5m"},
        {"promql": ""},
        {"promql": 'up{pod="__BKMONITOR_ALL__",node="demo"}'},
    ],
)
def test_mcp_graph_validation_query_and_success_shape_match_original(graph_pair, overrides):
    graph_cls, new, provider, bounded = graph_pair
    params = {"bk_biz_id": "2", "promql": "up", "start_time": "61", "end_time": "180", **overrides}
    original_input = copy.deepcopy(params)
    old = graph_cls()
    expected = old.perform_request(old.validate_request_data(dict(params)))
    assert new(params) == expected
    assert params == original_input
    if params["promql"]:
        assert bounded.call_args.args[0] == provider.call_args.kwargs
        assert bounded.call_args.args[1] == 1000
    else:
        bounded.assert_not_called()


@pytest.fixture
def uq_pair(limits):
    request = NS(user=NS(username="user"), biz_id=7)
    transport = Mock()

    class Client:
        method = "POST"
        path = "/query/ts/promql"
        v1beta3_path = ""

        def validate_request_data(self, data):
            return dict(data)

    namespace = dict(
        QueryDataByPromqlResource=Client,
        get_request=lambda **kwargs: request,
        SpaceApi=NS(get_space_detail=lambda **kwargs: NS(is_global=False)),
        bk_biz_id_to_space_uid=lambda bid: f"bkcc__{bid}",
        space_uid_to_bk_tenant_id=lambda uid: "derived",
        get_request_tenant_id=lambda **kwargs: "fallback",
        get_unify_query_url=lambda uid: "http://uq.invalid/",
        local=NS(),
        settings=NS(APP_CODE="monitor"),
        urljoin=urljoin,
        requests=NS(request=transport),
        read_bounded_json=limits.read_bounded_json,
        BKAPIError=lambda **kwargs: RuntimeError(kwargs["result"]),
        resolve_relation_query_path=lambda path, *args: path,
    )
    old = source("api/unify_query/default.py", "UnifyQueryAPIResource.perform_request", **namespace)
    bounded_uq = source(
        "kernel_api/resource/mcp_uq.py",
        "query_uq",
        UQ_OPERATIONS={"query_data_by_promql": Client},
        get_max_response_bytes=limits.get_max_response_bytes,
        **namespace,
    )
    new = source("kernel_api/resource/mcp_metrics_query.py", "query_promql", query_uq=bounded_uq)
    return Client, old, new, namespace, transport


@pytest.mark.parametrize("variant", ["business", "global", "no_space", "username", "strategy", "tenant_fallback"])
def test_mcp_uq_adapter_preserves_original_scope_routing_and_payload(uq_pair, variant):
    client, old, new, namespace, transport = uq_pair
    params = {"bk_biz_ids": [2], "promql": "up", "start": 1, "end": 2, "step": "1m"}
    if variant == "global":
        namespace["SpaceApi"].get_space_detail = lambda **kwargs: NS(is_global=True)
    if variant == "no_space":
        params = {**params, "space_uid": None}
    if variant == "strategy":
        namespace["get_request"] = lambda **kwargs: None
        namespace["local"].strategy_id = 12
        old.__globals__["get_request"] = new.__globals__["query_uq"].__globals__["get_request"] = namespace[
            "get_request"
        ]
    if variant == "tenant_fallback":

        def no_tenant(uid):
            raise ValueError("no derived tenant")

        old.__globals__["space_uid_to_bk_tenant_id"] = new.__globals__["query_uq"].__globals__[
            "space_uid_to_bk_tenant_id"
        ] = no_tenant
    body = b'{"series":[]}'
    transport.return_value = http_response(body)
    assert old(client(), copy.deepcopy(params)) == {"series": []}
    old_kwargs = copy.deepcopy(transport.call_args.kwargs)
    transport.return_value = http_response(body)
    assert new(copy.deepcopy(params), 1000) == {"series": []}
    new_kwargs = copy.deepcopy(transport.call_args.kwargs)
    assert new_kwargs.pop("stream") is True
    assert new_kwargs.pop("allow_redirects") is False
    assert new_kwargs["headers"].pop("Accept-Encoding") == "gzip, identity"
    assert new_kwargs == old_kwargs
    assert transport.return_value.raw.closed


@pytest.mark.parametrize(
    "body,status,error", [(b"x" * 1001, 200, ValidationError), (b"{", 200, ValueError), (b"failed", 503, RuntimeError)]
)
def test_mcp_uq_adapter_closes_connections_on_all_failures(uq_pair, body, status, error):
    _, _, call, _, transport = uq_pair
    response = http_response(body, status)
    transport.return_value = response
    with pytest.raises(error):
        call({"bk_biz_ids": [2]}, 1000)
    assert response.raw.closed


class TTLCache:
    def __init__(self, clock):
        self.clock, self.data = clock, {}

    def has_key(self, key):
        return key in self.data and self.data[key][1] > self.clock[0]

    def get(self, key):
        return self.data[key][0] if self.has_key(key) else None

    def set(self, key, value, timeout):
        self.data[key] = (value, self.clock[0] + timeout)

    def delete(self, key):
        self.data.pop(key, None)


@pytest.fixture
def dynamic():
    # Use the real registration catalog and DynamicSettings methods. Only DB and
    # cache transport are simulated; clocks advance without sleeping.
    from bkmonitor.define import global_config
    from django.conf import LazySettings

    field = global_config.ADVANCED_OPTIONS["MCP_MAX_RESPONSE_BYTES"]
    assert field.default == 5 * 1024 * 1024 and field.min_value == 1
    assert "MCP_MAX_RESPONSE_BYTES" in global_config.GLOBAL_CONFIGS
    clock, store = [0], {"MCP_MAX_RESPONSE_BYTES": 100}
    db = NS(get=Mock(side_effect=lambda key, default, **kwargs: store.get(key, default)))
    db.set = lambda key, value: store.update({key: value})
    redis = TTLCache(clock)
    reader = source("bkmonitor/utils/dynamic_settings.py", "lazy__getattr__", empty=empty)

    class Lazy(LazySettings):
        __getattr__ = reader

    def worker():
        cls = source(
            "bkmonitor/utils/dynamic_settings.py",
            "DynamicSettings",
            json=json,
            logger=logging.getLogger(__name__),
            locmem_cache=TTLCache(clock),
            redis_cache=redis,
        )
        proxy = Lazy()
        proxy._wrapped = cls(NS(MCP_MAX_RESPONSE_BYTES=5 * 1024 * 1024), db)
        return proxy

    return NS(clock=clock, store=store, db=db, worker=worker, field=field)


def test_global_settings_update_takes_effect_after_real_cache_expiry(dynamic, limits):
    proxy = dynamic.worker()
    limits.namespace["settings"] = proxy
    assert limits.get_max_response_bytes() == 100
    assert "MCP_MAX_RESPONSE_BYTES" not in proxy.__dict__
    dynamic.store["MCP_MAX_RESPONSE_BYTES"] = 200
    assert limits.get_max_response_bytes() == 100  # no false promise of immediate DB-write visibility
    dynamic.clock[0] = 181
    assert limits.get_max_response_bytes() == 200


def test_dynamic_settings_assignment_invalidates_writer_caches(dynamic, limits):
    proxy = dynamic.worker()
    limits.namespace["settings"] = proxy
    assert limits.get_max_response_bytes() == 100
    proxy.MCP_MAX_RESPONSE_BYTES = 300
    assert limits.get_max_response_bytes() == 300


def test_two_worker_cache_refill_can_extend_direct_db_update_delay(dynamic):
    first = dynamic.worker()
    assert first.MCP_MAX_RESPONSE_BYTES == 100
    dynamic.clock[0] = 1
    dynamic.store["MCP_MAX_RESPONSE_BYTES"] = 200
    dynamic.clock[0] = 179
    second = dynamic.worker()
    assert second.MCP_MAX_RESPONSE_BYTES == 100
    dynamic.clock[0] = 181
    assert first.MCP_MAX_RESPONSE_BYTES == 200
    assert second.MCP_MAX_RESPONSE_BYTES == 100
    dynamic.clock[0] = 360
    assert second.MCP_MAX_RESPONSE_BYTES == 200


def test_config_change_changes_actual_response_acceptance(dynamic, limits):
    proxy = dynamic.worker()
    limits.namespace["settings"] = proxy
    limits.get_request.return_value = NS(META={}, native_mcp_tool="query")
    result = {"text": "x" * 80}
    with pytest.raises(ValidationError):
        limits.MCPResource().validate_response_data(result)
    proxy.MCP_MAX_RESPONSE_BYTES = 500
    assert limits.MCPResource().validate_response_data(result) is result


def test_static_default_matches_dynamic_registration(dynamic):
    tree = ast.parse((BASE / "config/default.py").read_text())
    assignment = next(
        n
        for n in tree.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "MCP_MAX_RESPONSE_BYTES" for t in n.targets)
    )
    namespace = {}
    exec(compile(ast.Module(body=[assignment], type_ignores=[]), "static_config", "exec"), namespace)
    assert namespace["MCP_MAX_RESPONSE_BYTES"] == dynamic.field.default


@pytest.fixture
def all_uq(limits):
    """Real original API classes / serializers, with only model and I/O adapters replaced."""

    class Resource:
        def validate_request_data(self, params):
            serializer = self.RequestSerializer(data=params)
            serializer.is_valid(raise_exception=True)
            return serializer.validated_data

    routing_tree = ast.parse((BASE / "api/unify_query/relation_routing.py").read_text())
    constants = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in routing_tree.body
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
    }
    rollout = [False]
    resolver = Mock(
        side_effect=source(
            "api/unify_query/relation_routing.py",
            "resolve_relation_query_path",
            is_graph_relation_v4_enabled=lambda bid: rollout[0],
        )
    )
    transport = Mock()
    request = NS(user=NS(username="caller"), biz_id=7)
    space = NS(is_global=False, bk_biz_id=-9)
    namespace = dict(
        Resource=Resource,
        serializers=serializers,
        json=json,
        logger=logging.getLogger(__name__),
        get_request=lambda **kwargs: request,
        SpaceApi=NS(get_space_detail=lambda **kwargs: space),
        bk_biz_id_to_space_uid=lambda bid: f"bkcc__{bid}",
        space_uid_to_bk_tenant_id=lambda uid: "derived",
        get_request_tenant_id=lambda **kwargs: "fallback",
        local=NS(),
        settings=NS(APP_CODE="monitor"),
        get_unify_query_url=lambda uid: "http://uq.invalid/root/",
        urljoin=urljoin,
        resolve_relation_query_path=resolver,
        requests=NS(request=transport),
        read_bounded_json=limits.read_bounded_json,
        get_max_response_bytes=limits.get_max_response_bytes,
        BKAPIError=lambda **kwargs: RuntimeError(kwargs["result"]),
        **constants,
    )
    root = source("api/unify_query/default.py", "UnifyQueryAPIResource", **namespace)
    namespace["UnifyQueryAPIResource"] = root
    for name in (
        "QueryDataByPromqlResource",
        "QueryRawResource",
        "QueryReferenceResource",
        "QueryMultiResource",
        "QueryMultiResourceRange",
    ):
        namespace[name] = source("api/unify_query/default.py", name, **namespace)
    mapping = next(
        node.value
        for node in ast.parse((BASE / "kernel_api/resource/mcp_uq.py").read_text()).body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "UQ_OPERATIONS" for target in node.targets)
    )
    operations = eval(compile(ast.Expression(mapping), "MCP_UQ_OPERATIONS", "eval"), namespace)
    call = source("kernel_api/resource/mcp_uq.py", "query_uq", UQ_OPERATIONS=operations, **namespace)
    return NS(
        call=call,
        operations=operations,
        transport=transport,
        rollout=rollout,
        resolver=resolver,
        space=space,
        request=request,
    )


def uq_params(operation):
    if operation == "query_data_by_promql":
        return {
            "promql": "up",
            "start": "1",
            "end": "2",
            "step": "60s",
            "bk_biz_ids": [-9],
            "response_contract": "named_outputs/v1",
            "legacy_output_ref": "a",
            "output_list": [],
        }
    if operation in ("query_multi", "query_multi_resource_range"):
        timing = (
            {"timestamp": "2"}
            if operation == "query_multi"
            else {
                "start_time": "1",
                "end_time": "2",
                "step": "60s",
            }
        )
        return {
            "bk_biz_ids": [-9],
            "query_list": [
                {**timing, "source_info": {"pod": "demo"}, "target_type": "system", "target_info_show": False}
            ],
        }
    return {
        "query_list": [{"table_id": "test", "keep_columns": ["log"]}],
        "metric_merge": "a",
        "start_time": "1",
        "end_time": "2",
        "step": "auto",
        "space_uid": "bkcc__-9",
        "_from": 7,
        "limit": 2,
        "order_by": ["-time"],
    }


@pytest.mark.parametrize(
    "operation",
    [
        "query_data_by_promql",
        "query_raw",
        "query_reference",
        "query_multi",
        "query_multi_resource_range",
    ],
)
@pytest.mark.parametrize("mode", ["legacy", "v1beta3", "global", "tenant_fallback"])
def test_all_uq_operations_match_original_validators_body_headers_and_route(all_uq, operation, mode):
    params = {**uq_params(operation), "ignored_extra": "not forwarded"}
    original_input = copy.deepcopy(params)
    if mode == "v1beta3":
        all_uq.rollout[0] = True
    if mode == "global":
        all_uq.space.is_global = True
    if mode == "tenant_fallback":

        def no_tenant(uid):
            raise ValueError("missing derived tenant")

        all_uq.call.__globals__["space_uid_to_bk_tenant_id"] = no_tenant
        root = all_uq.operations[operation].__mro__[1]
        root.perform_request.__globals__["space_uid_to_bk_tenant_id"] = no_tenant
    body = json.dumps({"list": [{"value": "中文", "points": [1, 2]}]}, ensure_ascii=False).encode()
    all_uq.transport.return_value = http_response(body)
    old = all_uq.operations[operation]()
    expected = old.perform_request(old.validate_request_data(copy.deepcopy(params)))
    old_kwargs = copy.deepcopy(all_uq.transport.call_args.kwargs)
    all_uq.transport.return_value = http_response(body)
    assert all_uq.call(operation, params) == expected
    new_kwargs = copy.deepcopy(all_uq.transport.call_args.kwargs)
    assert new_kwargs.pop("stream") is True
    assert new_kwargs.pop("allow_redirects") is False
    assert new_kwargs["headers"].pop("Accept-Encoding") == "gzip, identity"
    assert new_kwargs == old_kwargs
    assert "ignored_extra" not in new_kwargs["json"]
    assert params == original_input
    assert all_uq.transport.return_value.raw.closed
    if operation == "query_raw":
        assert new_kwargs["json"]["from"] == 7 and "_from" not in new_kwargs["json"]
    if mode == "v1beta3" and operation.startswith("query_multi"):
        assert "/v1beta3/" in new_kwargs["url"]
    if mode == "legacy" and operation.startswith("query_multi"):
        assert "/v1beta3/" not in new_kwargs["url"]
    if mode == "global":
        assert new_kwargs["headers"]["X-Bk-Scope-Skip-Space"] == "monitor"
    if mode == "tenant_fallback":
        assert new_kwargs["headers"]["X-Bk-Tenant-Id"] == "fallback"


@pytest.mark.parametrize("operation", ["query_raw", "query_reference"])
def test_explicit_null_space_and_space_derived_routing_match_original(all_uq, operation):
    for space_uid in (None, "bkcc__-9"):
        params = {**uq_params(operation), "space_uid": space_uid}
        all_uq.transport.return_value = http_response(b'{"list":[]}')
        all_uq.call(operation, params)
        headers = all_uq.transport.call_args.kwargs["headers"]
        if space_uid is None:
            assert headers["X-Bk-Scope-Skip-Space"] == "monitor"
        else:
            assert all_uq.resolver.call_args.args[2] == -9
            assert headers["X-Bk-Scope-Space-Uid"] == "bkcc__-9"


@pytest.mark.parametrize(
    "operation",
    [
        "query_data_by_promql",
        "query_raw",
        "query_reference",
        "query_multi",
        "query_multi_resource_range",
    ],
)
def test_every_uq_operation_rejects_oversized_body_before_json_and_closes(all_uq, operation, limits):
    response = http_response(b"x" * 1001)
    all_uq.transport.return_value = response
    parser = Mock(side_effect=AssertionError("oversized data must never be parsed"))
    limits.namespace["json"] = NS(loads=parser)
    with pytest.raises(ValidationError, match="result_too_large"):
        all_uq.call(operation, uq_params(operation))
    parser.assert_not_called()
    assert response.raw.closed


def test_uq_default_budget_observes_dynamic_settings_updates(all_uq, limits, dynamic):
    proxy = dynamic.worker()
    limits.namespace["settings"] = proxy
    body = json.dumps({"list": ["x" * 120]}).encode()
    all_uq.transport.return_value = http_response(body)
    with pytest.raises(ValidationError):
        all_uq.call("query_raw", uq_params("query_raw"))
    proxy.MCP_MAX_RESPONSE_BYTES = 500
    all_uq.transport.return_value = http_response(body)
    assert all_uq.call("query_raw", uq_params("query_raw")) == json.loads(body)


def test_uq_rejects_unknown_operation_and_invalid_parameters_before_network(all_uq):
    with pytest.raises(ValueError, match="Unsupported MCP UQ operation"):
        all_uq.call("arbitrary_url", {})
    with pytest.raises(ValidationError):
        all_uq.call("query_raw", {})
    all_uq.transport.assert_not_called()


def test_uq_error_message_is_short_and_connection_is_closed(all_uq):
    response = http_response(b"x" * 900, status=503)
    all_uq.transport.return_value = response
    with pytest.raises(RuntimeError) as exc:
        all_uq.call("query_raw", uq_params("query_raw"))
    assert len(str(exc.value)) < 600
    assert str(exc.value).endswith("[truncated]")
    assert response.raw.closed


@pytest.mark.parametrize("compressed,oversized", [(False, False), (True, False), (False, True), (True, True)])
def test_uq_reads_real_chunked_http_framing_without_network(all_uq, compressed, oversized):
    payload = {"list": [{"message": "x" * 2000 if oversized else "中文"}]}
    body = json.dumps(payload, ensure_ascii=False).encode()
    if compressed:
        body = gzip.compress(body)
    headers = b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n"
    if compressed:
        headers += b"Content-Encoding: gzip\r\n"
    framed = headers + b"\r\n"
    for offset in range(0, len(body), 13):
        chunk = body[offset : offset + 13]
        framed += f"{len(chunk):x}\r\n".encode() + chunk + b"\r\n"
    framed += b"0\r\n\r\n"

    class WireSocket:
        def makefile(self, *args, **kwargs):
            return io.BytesIO(framed)

    wire = http.client.HTTPResponse(WireSocket())
    wire.begin()
    response = requests.Response()
    response.status_code = wire.status
    response.headers.update(dict(wire.getheaders()))
    response.raw = HTTPResponse(
        body=wire,
        headers=dict(wire.getheaders()),
        original_response=wire,
        preload_content=False,
        decode_content=False,
    )
    all_uq.transport.return_value = response
    if oversized:
        with pytest.raises(ValidationError):
            all_uq.call("query_raw", uq_params("query_raw"))
    else:
        assert all_uq.call("query_raw", uq_params("query_raw")) == payload
    assert response.raw.closed


def test_uq_closes_response_when_body_read_times_out(all_uq):
    response = http_response(b'{"list":[]}')
    response.raw.read = Mock(side_effect=requests.exceptions.ReadTimeout("body read timeout"))
    all_uq.transport.return_value = response
    with pytest.raises(requests.exceptions.ReadTimeout):
        all_uq.call("query_raw", uq_params("query_raw"))
    assert response.raw.closed


@pytest.mark.parametrize("point", ["sql", "index_logs", "field", "relation", "relation_range"])
def test_five_resource_points_keep_normal_call_and_only_opt_in_mcp(point, monkeypatch):
    from typing import Any

    original = Mock(return_value={"preserved": [1, 2]})
    bounded = Mock(return_value=original.return_value)
    module = ModuleType("kernel_api.resource.mcp_uq")
    module.query_uq = bounded
    monkeypatch.setitem(sys.modules, module.__name__, module)
    mcp = [False]
    namespace = dict(
        is_mcp_request=lambda: mcp[0],
        logger=logging.getLogger(__name__),
        serializers=serializers,
        Any=Any,
        bk_biz_id_to_space_uid=lambda bid: f"bkcc__{bid}",
        get_log_unify_query_table=lambda *args: "bklog_index_set_3",
        api=NS(
            unify_query=NS(
                query_raw=original, query_reference=original, query_multi=original, query_multi_resource_range=original
            )
        ),
    )
    if point == "sql":
        method = source("kernel_api/resource/metrics.py", "ExecuteSQLQueryResource.perform_request", **namespace)
        params = {
            "bk_biz_id": 2,
            "table_id": "test",
            "sql": "select * from test",
            "start_time": "1",
            "end_time": "2",
            "step": "5m",
            "limit": 10,
        }
        invoke, operation = lambda: method(None, params), "query_raw"
    elif point == "index_logs":
        method = source("kernel_api/resource/log_search.py", "SearchLogResource._search_by_index_set", **namespace)
        params = {
            "bk_biz_id": 2,
            "index_set_id": 3,
            "start_time": "1",
            "end_time": "2",
            "offset": 7,
            "limit": 10,
            "keep_columns": ["log"],
            "order_by": ["-time"],
            "conditions": {"field_list": []},
        }
        invoke, operation = lambda: method(params), "query_raw"
    elif point == "field":
        path = "kernel_api/resource/log_search.py"
        aggregation = source(path, "FieldAnalyzeResource._build_aggregation_function", **namespace)
        build_item = source(path, "FieldAnalyzeResource._build_query_item", **namespace)
        method = source(path, "FieldAnalyzeResource.perform_request", **namespace)
        instance = NS(ORDER_BY_MAPPING={"time": ["-dtEventTimeStamp", "-gseIndex", "-iterationIndex"]})
        instance._build_aggregation_function = lambda *args: aggregation(instance, *args)
        instance._build_query_item = lambda *args: build_item(instance, *args)
        params = {"bk_biz_id": 2, "index_set_id": 3, "field_name": "log", "start_time": "1", "end_time": "2"}
        invoke, operation = lambda: method(instance, params), "query_reference"
    else:
        cls = "QueryMultiResourceRelationResource" if point == "relation" else "QueryMultiResourceRelationRangeResource"
        method = source("kernel_api/resource/relation.py", cls + ".perform_request", **namespace)
        params = {"bk_biz_id": -9, "query_list": [{"source_info": {"pod": "demo"}}]}
        operation = "query_multi" if point == "relation" else "query_multi_resource_range"

        def invoke():
            return method(None, params)

    snapshot = copy.deepcopy(params)
    assert invoke() is original.return_value
    original_kwargs = copy.deepcopy(original.call_args.kwargs)
    bounded.assert_not_called()
    original.reset_mock()
    mcp[0] = True
    assert invoke() is bounded.return_value
    bounded.assert_called_once_with(operation, original_kwargs)
    original.assert_not_called()
    assert params == snapshot
    bounded.side_effect = ValidationError("result_too_large")
    with pytest.raises(ValidationError):
        invoke()
    original.assert_not_called()  # no unbounded fallback or retry on rejection
