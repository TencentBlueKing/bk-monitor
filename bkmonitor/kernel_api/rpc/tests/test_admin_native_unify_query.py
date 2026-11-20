"""Exercise registered RPC entrypoints against a local UQ HTTP server."""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest
from django.db import connection
from rest_framework.exceptions import ValidationError

from bkmonitor.define.global_config import ADVANCED_OPTIONS
from bkmonitor.models import GlobalConfig
from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin import native_unify_query as native


def test_target_config_registration_round_trip():
    field = ADVANCED_OPTIONS["ADMIN_UNIFY_QUERY_TARGETS"]
    options_column = GlobalConfig._meta.get_field("options")
    stored = options_column.get_db_prep_save(field._kwargs, connection)
    config = GlobalConfig(data_type="Dict", options=options_column.from_db_value(stored, None, connection))
    targets = {"test": "http://uq-test.example:10205"}
    assert config.get_serializer().run_validation(targets) == targets


@pytest.fixture
def backend(monkeypatch, settings):
    calls = []
    raw = {"trace_id": "upstream", "data": [], "is_partial": True, "result_table_options": {"rt": {"from": 5}}}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            calls.append((self.path, dict(self.headers), body))
            if self.path.endswith("/promql_to_struct"):
                source = "bkdata" if body["promql"] == "outside" else "bkmonitor"
                self.reply({"data": {"query_list": [{"data_source": source}]}})
            elif body.get("timezone") == "error":
                self.reply({"error": "Doris failed", "trace_id": "failed"}, 503)
            else:
                self.reply(raw)

        def do_GET(self):
            calls.append((self.path, dict(self.headers), None))
            self.reply({"values": {"host": ["host-1"]}})

        def reply(self, data, status=200):
            self.send_response(status)
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())

        def log_message(self, *args):
            pass

    listener = HTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=listener.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{listener.server_port}"
    settings.ADMIN_UNIFY_QUERY_TARGETS = {"test": origin + "/test/"}
    monkeypatch.setattr(native, "get_unify_query_url", lambda space_uid: origin + "/default")
    spaces = Mock()
    spaces.filter.return_value.filter.return_value.first.return_value = Mock(space_uid="bkcc__2", is_global=True)
    spaces.filter.return_value.filter.return_value.exclude.return_value.first.return_value = Mock(space_uid="bkci__p")
    monkeypatch.setattr(native.Space, "objects", spaces)
    try:
        yield calls, raw, spaces
    finally:
        listener.shutdown()
        thread.join()
        listener.server_close()


def invoke(name, **updates):
    func_name = "admin.unify_query." + name
    example = KernelRPCRegistry.get_function_detail(func_name)["example_params"]
    return KernelRPCRegistry.execute(func_name, {**example, **updates})


@pytest.mark.parametrize("name", native.ENDPOINTS)
def test_native_endpoints(backend, name):
    calls, raw, spaces = backend
    result = invoke(name, uq_target="test", doris_direct_query=False)
    url, headers, payload = calls[-1]
    assert headers["X-Bk-Scope-Space-Uid"] == "bkcc__2"
    assert "X-Bk-Scope-Skip-Space" not in headers
    assert headers["X-Bk-Tenant-Id"] == "system"
    assert json.loads(headers["X-Bk-Query-Flags"]) == {"doris_direct_query": False}
    spaces.filter.assert_called_once_with(bk_tenant_id="system")
    if name == "label_values":
        assert urlsplit(url).path == "/test/query/ts/label/bk_target_ip/values"
        assert parse_qs(urlsplit(url).query)["match[]"] == [native.PROM_EXAMPLE["promql"]]
        assert result["data"] == {"values": {"host": ["host-1"]}}
    else:
        assert url == "/test/" + native.ENDPOINTS[name][0]
        assert payload == native.ENDPOINTS[name][4]
        assert result["data"] == raw


def test_default_and_negative_space(backend):
    calls, _, spaces = backend
    invoke("raw", bk_biz_id=-42, space_uid="bkci__p")
    path, headers, payload = calls[-1]
    spaces.filter.return_value.filter.assert_called_once_with(id=42)
    spaces.filter.return_value.filter.return_value.exclude.assert_called_once_with(space_type_id="bkcc")
    assert path == "/default/query/ts/raw"
    assert headers["X-Bk-Scope-Space-Uid"] == "bkci__p"
    assert "X-Bk-Query-Flags" not in headers
    assert payload == native.RAW_EXAMPLE


@pytest.mark.parametrize(
    "changes",
    [
        {"tsdb_map": {}},
        {"TsDB_Map": {}},
        {"bk_tenant_id": "__all__"},
        {"space_uid": "bkcc__3"},
        {"bk_biz_id": 0},
        {"uq_target": "absent"},
        {"query_list": [{"Data_Source": "bkdata"}]},
        {"query_list": [{"data_source": "bk_data"}]},
        {"result_table_options": {"rt": {"scroll_id": "some-id"}}},
    ],
)
def test_scope_guard_before_forwarding(backend, changes):
    with pytest.raises(ValidationError):
        invoke("raw", **changes)
    assert not backend[0]


def test_not_found_and_named_output_scope(backend):
    calls, _, spaces = backend
    with pytest.raises(ValidationError):
        invoke("promql", output_list=[{"reference_name": "b", "expression": "outside"}])
    assert all(path.endswith("promql_to_struct") for path, _, _ in calls)
    spaces.filter.return_value.filter.return_value.first.return_value = None
    with pytest.raises(ValidationError):
        invoke("raw", bk_tenant_id="other")


def test_preserve_search_after_and_upstream_failure(backend):
    calls, _, _ = backend
    options = {"rt": {"query_backend": "doris", "search_after": [2**53 + 1, "k"]}}
    invoke("raw", is_search_after=True, result_table_options=options, doris_direct_query=True)
    assert calls[-1][2]["result_table_options"] == options
    assert json.loads(calls[-1][1]["X-Bk-Query-Flags"]) == {"doris_direct_query": True}
    with pytest.raises(CustomException, match="503"):
        invoke("raw", uq_target="test", timezone="error")
    assert len(calls) == 2


def test_promql_explicit_business_filter(backend):
    calls, _, _ = backend
    with pytest.raises(ValidationError):
        invoke("promql", bk_biz_ids=["3"])
    assert not calls
    invoke("promql", bk_biz_ids=["2"])
    assert calls[-1][2]["bk_biz_ids"] == ["2"]
