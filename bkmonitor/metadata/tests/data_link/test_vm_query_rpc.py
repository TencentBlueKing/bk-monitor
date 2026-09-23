"""PromQL 直查必须在 kernel_rpc 内解析租户内集群身份。"""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

import pytest
import requests

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc.functions.admin import vm_query
from metadata.models.data_link.vm_query_cluster import VmQueryClusterConfig

pytestmark = pytest.mark.django_db(databases="__all__")

PARAMS = {
    "bk_tenant_id": "tenant-a",
    "namespace": "bkmonitor",
    "name": "query-a",
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
def cluster():
    return VmQueryClusterConfig.objects.create(
        bk_tenant_id="tenant-a",
        namespace="bkmonitor",
        name="query-a",
        cluster_name="logical-a",
        cluster_domain="vm-a.svc.cluster.local",
        num_replicas=3,
        monitor_storage_clusters=["storage-a"],
        status="Ok",
        k8s_cluster="cluster-a",
        k8s_namespace="vm",
        version="1.0",
        origin_config={},
    )


@pytest.fixture
def http(mocker):
    factory = mocker.patch.object(vm_query.requests, "Session")
    session = factory.return_value.__enter__.return_value
    response = session.post.return_value.__enter__.return_value
    response.status_code = 200
    response.iter_content.return_value = [json.dumps(SUCCESS).encode()]
    return factory, session, response


def test_resolves_stored_domain_and_posts_unmodified_promql(cluster, http):
    _, session, _ = http
    result = vm_query.query(PARAMS)
    assert result["meta"]["safety_level"] == "read"
    assert result["data"]["cluster"] == {key: PARAMS[key] for key in ("bk_tenant_id", "namespace", "name")}
    assert result["data"]["response"] == SUCCESS
    assert session.trust_env is False
    args, kwargs = session.post.call_args
    assert args[0] == "http://vm-a.svc.cluster.local:8481/select/0/prometheus/api/v1/query_range"
    assert kwargs["data"] == {"query": PARAMS["query"], "start": 1000, "end": 1600, "step": 60, "timeout": "30s"}
    assert kwargs["allow_redirects"] is False
    assert kwargs["stream"] is True
    assert kwargs["headers"] == {"Accept": "application/json"}
    assert "auth" not in kwargs


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
            cluster.cluster_domain = f"127.0.0.1:{server.server_port}"
            cluster.save()
            expression = 'sum(rate(requests_total{label="a&b + 中文"}[5m]))'
            result = vm_query.query({**PARAMS, "query": expression})
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
    cluster.cluster_domain = "https://query.example.com:9443"
    cluster.save()
    response.iter_content.return_value = [
        json.dumps({"status": "success", "data": {"resultType": "scalar", "result": [1000, "1"]}}).encode()
    ]
    params = {k: v for k, v in PARAMS.items() if k not in {"start", "end", "step"}}
    result = vm_query.query({**params, "mode": "instant", "time": 1000})
    assert result["data"]["response"]["data"]["resultType"] == "scalar"
    assert session.post.call_args.args[0] == "https://query.example.com:9443/select/0/prometheus/api/v1/query"
    assert session.post.call_args.kwargs["data"]["time"] == 1000


@pytest.mark.parametrize(
    "changes",
    [
        {"bk_tenant_id": "other"},
        {"namespace": "other"},
        {"name": "missing"},
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
        vm_query.query({**PARAMS, **changes})
    http[0].assert_not_called()


def test_terminated_cluster_does_not_connect(cluster, http):
    cluster.status = "Terminated"
    cluster.save()
    with pytest.raises(CustomException) as error:
        vm_query.query(PARAMS)
    assert error.value.data["code"] == "CLUSTER_TERMINATED"
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
    cluster.cluster_domain = domain
    cluster.save()
    with pytest.raises(CustomException):
        vm_query.query(PARAMS)
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
        vm_query.query(PARAMS)
    assert error.value.data["code"] == code


def test_response_limit_and_timeout(cluster, http, monkeypatch):
    monkeypatch.setattr(vm_query, "MAX_RESPONSE_BYTES", 5)
    with pytest.raises(CustomException) as error:
        vm_query.query(PARAMS)
    assert error.value.data["code"] == "RESULT_TOO_LARGE"
    http[1].post.side_effect = requests.Timeout()
    with pytest.raises(CustomException) as error:
        vm_query.query(PARAMS)
    assert error.value.data["code"] == "UPSTREAM_TIMEOUT"


def test_total_series_and_point_limits(cluster, http, monkeypatch):
    monkeypatch.setattr(vm_query, "MAX_SERIES", 0)
    with pytest.raises(CustomException) as error:
        vm_query.query(PARAMS)
    assert error.value.data["code"] == "RESULT_TOO_LARGE"
    monkeypatch.setattr(vm_query, "MAX_SERIES", 1000)
    monkeypatch.setattr(vm_query, "MAX_POINTS", 2)
    with pytest.raises(CustomException) as error:
        vm_query.query(PARAMS)
    assert error.value.data["code"] == "RESULT_TOO_LARGE"
