"""PromQL 直查必须在 kernel_rpc 内解析租户内集群身份。"""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

import pytest
import requests

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc.functions.admin import vm_query

PARAMS = {
    "bk_tenant_id": "tenant-a",
    "storage": "storage-a",
    "config": {"host": "vm-a", "port": 80},
    "query": 'sum(rate(http_requests_total{job="app"}[5m]))',
    "mode": "range",
    "start": 1000,
    "end": 1600,
    "step": 60,
}
SUCCESS = {
    "status": "success",
    "data": {
        "resultType": "matrix",
        "result": [{"metric": {"job": "app"}, "values": [[1000, "1"], [1060, "NaN"], [1120, "+Inf"]]}],
    },
}


@pytest.fixture
def cluster(mocker):
    resource = {
        "metadata": {"name": "storage-a"},
        "status": {"phase": "Ok"},
        "spec": {
            "selectHost": "vm-a",
            "commonSelectHost": "vm-a",
            "historySelectHost": "vm-history",
            "selectPort": 80,
            "insertHost": "write-only",
            "password": "not-for-discovery",
        },
    }

    def get_resource(**kwargs):
        return (
            resource
            if kwargs
            == {"bk_tenant_id": "tenant-a", "namespace": "bkmonitor", "kind": "vmstorages", "name": "storage-a"}
            else None
        )

    mocker.patch.object(vm_query.api.bkdata, "get_data_link", side_effect=get_resource)
    return resource


def test_config_discovery_is_live_paginated_and_projected(cluster, mocker):
    other = {**cluster, "metadata": {"name": "another"}}
    retired = {**cluster, "status": {"phase": "Terminated"}}
    listing = mocker.patch.object(vm_query.api.bkdata, "list_data_link", return_value=[other, cluster, retired])
    result = vm_query.storage_config_list({"bk_tenant_id": "tenant-a", "page": 2, "page_size": 1})["data"]
    listing.assert_called_once_with(bk_tenant_id="tenant-a", namespace="bkmonitor", kind="vmstorages")
    assert result == {
        "total": 2,
        "page": 2,
        "page_size": 1,
        "items": [
            {
                "name": "storage-a",
                "selectHost": "vm-a",
                "commonSelectHost": "vm-a",
                "historySelectHost": "vm-history",
                "strategySelectHost": None,
                "selectPort": 80,
            }
        ],
    }


@pytest.fixture
def http(mocker):
    factory = mocker.patch.object(vm_query.requests, "Session")
    session = factory.return_value.__enter__.return_value
    response = session.post.return_value.__enter__.return_value
    response.status_code = 200
    response.iter_content.return_value = [json.dumps(SUCCESS).encode()]
    return factory, session, response


def test_only_current_endpoints_are_queried(cluster, http):
    result = vm_query.query_by_config(PARAMS)
    assert result["data"]["config"] == PARAMS["config"]
    assert result["data"]["response"] == SUCCESS
    _, session, _ = http
    assert session.post.call_args.args == ("http://vm-a:80/select/0/prometheus/api/v1/query_range",)
    assert session.trust_env is False
    assert session.post.call_args.kwargs["allow_redirects"] is False
    cluster["spec"].update(selectHost="new-host", commonSelectHost="new-host")
    with pytest.raises(CustomException) as err:
        vm_query.query_by_config(PARAMS)
    assert err.value.data["code"] == "TARGET_REMOVED"
    assert session.post.call_count == 1


def test_real_http_post_uses_only_the_stored_endpoint(cluster):
    received = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            received["path"] = self.path
            received["auth"] = self.headers.get("Authorization")
            received["body"] = parse_qs(self.rfile.read(int(self.headers["Content-Length"])).decode())
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(SUCCESS).encode())

        def log_message(self, *args):
            pass

    with HTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            cluster["spec"].update(selectHost="127.0.0.1", selectPort=server.server_port)
            expression = 'sum(rate(requests_total{label="a&b + 中文"}[5m]))'
            result = vm_query.query_by_config(
                {**PARAMS, "query": expression, "config": {"host": "127.0.0.1", "port": server.server_port}}
            )
            assert result["data"]["response"] == SUCCESS
            assert received["path"] == "/select/0/prometheus/api/v1/query_range"
            assert received["auth"] is None
            assert received["body"]["query"] == [expression]
            assert received["body"]["step"] == ["60"]
        finally:
            server.shutdown()
            thread.join(timeout=2)


def test_instant_and_updated_domain_are_resolved_each_time(cluster, http):
    _, session, response = http
    cluster["spec"].update(historySelectHost="query.example.com", selectPort=9443)
    response.iter_content.return_value = [
        json.dumps({"status": "success", "data": {"resultType": "scalar", "result": [1000, "1"]}}).encode()
    ]
    params = {k: v for k, v in PARAMS.items() if k not in {"start", "end", "step"}}
    result = vm_query.query_by_config(
        {**params, "mode": "instant", "time": 1000, "config": {"host": "query.example.com", "port": 9443}}
    )
    assert result["data"]["response"]["data"]["resultType"] == "scalar"
    assert session.post.call_args.args[0] == "http://query.example.com:9443/select/0/prometheus/api/v1/query"
    assert session.post.call_args.kwargs["data"]["time"] == 1000


@pytest.mark.parametrize(
    "changes",
    [
        {"bk_tenant_id": "other"},
        {"namespace": "other"},
        {"storage": "missing"},
        {"config": {"host": "write-only", "port": 80}},
        {"config": {"host": "vm-a", "port": 81}},
        {"bk_tenant_id": "__all__"},
        {"bk_tenant_id": ""},
        {"query": " "},
        {"query": "x" * 65537},
        {"url": "http://attacker"},
        {"cluster_domain": "attacker"},
        {"path": "/delete"},
        {"headers": {}},
        {"mode": "delete"},
        {"mode": "instant", "time": 1000},
        {"step": 0},
        {"step": True},
        {"step": float("nan")},
        {"end": float("inf")},
        {"start": -1},
        {"end": 999},
        {"end": 1000 + 32 * 86400},
        {"step": 0.001},
        {"time": 1000},
    ],
)
def test_invalid_or_out_of_scope_requests_never_connect(cluster, http, changes):
    with pytest.raises(CustomException):
        vm_query.query_by_config({**PARAMS, **changes})
    http[0].assert_not_called()


def test_terminated_cluster_does_not_connect(cluster, http):
    cluster["status"]["phase"] = "Terminated"
    with pytest.raises(CustomException) as error:
        vm_query.query_by_config(PARAMS)
    assert error.value.data["code"] == "TARGET_REMOVED"
    http[0].assert_not_called()


@pytest.mark.parametrize(
    "domain",
    [
        "",
        "file:///etc/passwd",
        "http://user:password@host",
        "http://host/path",
        "host?path=query",
        "host#fragment",
        "host:bad",
        "host\\path",
        "host\n",
    ],
)
def test_invalid_stored_endpoints_are_rejected(cluster, http, domain):
    cluster["spec"]["selectHost"] = domain
    with pytest.raises(CustomException):
        vm_query.query_by_config({**PARAMS, "config": {"host": domain, "port": 80}})
    http[0].assert_not_called()


@pytest.mark.parametrize(
    "status,payload,code",
    [
        (302, b"", "UPSTREAM_ERROR"),
        (500, b"<html>error</html>", "UPSTREAM_ERROR"),
        (200, b'{"status":"error","error":"parse error","errorType":"bad_data"}', "QUERY_FAILED"),
        (422, b'{"status":"error","error":"parse error"}', "QUERY_FAILED"),
        (200, b'{"status":"success","data":{"resultType":"unknown","result":[]}}', "UPSTREAM_ERROR"),
        (
            200,
            b'{"status":"success","data":{"resultType":"vector","result":[{"metric":{},"value":null}]}}',
            "UPSTREAM_ERROR",
        ),
    ],
)
def test_upstream_errors_are_explicit(cluster, http, status, payload, code):
    http[2].status_code = status
    http[2].iter_content.return_value = [payload]
    with pytest.raises(CustomException) as error:
        vm_query.query_by_config(PARAMS)
    assert error.value.data["code"] == code


def test_response_limit_and_timeout(cluster, http, monkeypatch):
    monkeypatch.setattr(vm_query, "MAX_RESPONSE_BYTES", 5)
    with pytest.raises(CustomException) as error:
        vm_query.query_by_config(PARAMS)
    assert error.value.data["code"] == "RESULT_TOO_LARGE"
    http[1].post.side_effect = requests.Timeout()
    with pytest.raises(CustomException) as error:
        vm_query.query_by_config(PARAMS)
    assert error.value.data["code"] == "UPSTREAM_TIMEOUT"


def test_total_series_and_point_limits(cluster, http, monkeypatch):
    monkeypatch.setattr(vm_query, "MAX_SERIES", 0)
    with pytest.raises(CustomException) as error:
        vm_query.query_by_config(PARAMS)
    assert error.value.data["code"] == "RESULT_TOO_LARGE"
    monkeypatch.setattr(vm_query, "MAX_SERIES", 1000)
    monkeypatch.setattr(vm_query, "MAX_POINTS", 2)
    with pytest.raises(CustomException) as error:
        vm_query.query_by_config(PARAMS)
    assert error.value.data["code"] == "RESULT_TOO_LARGE"


@pytest.mark.parametrize("mode", ["range", "instant"])
def test_forwards_optional_lookback_and_cache_controls(cluster, http, mode):
    params = {**PARAMS, "max_lookback": 30, "nocache": True}
    if mode == "instant":
        for key in ("start", "end", "step"):
            params.pop(key)
        params.update(mode="instant", time=1000)
    vm_query.query_by_config(params)
    data = http[1].post.call_args.kwargs["data"]
    assert data["max_lookback"] == 30
    assert data["nocache"] == "1"


def test_removed_storage_or_bkbase_failure_never_dispatches(mocker, http):
    read = mocker.patch.object(vm_query.api.bkdata, "get_data_link", return_value=None)
    with pytest.raises(CustomException) as missing:
        vm_query.query_by_config(PARAMS)
    assert missing.value.data["code"] == "TARGET_REMOVED"
    read.side_effect = vm_query.BKAPIError(result="unavailable")
    with pytest.raises(CustomException) as upstream:
        vm_query.query_by_config(PARAMS)
    assert upstream.value.data["code"] == "STORAGE_CONFIG_UNAVAILABLE"
    http[0].assert_not_called()
