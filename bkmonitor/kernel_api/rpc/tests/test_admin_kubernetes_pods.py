from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from unittest.mock import Mock

import pytest
from kubernetes import client as k8s_client
from kubernetes.client.rest import ApiException
from rest_framework.exceptions import PermissionDenied, ValidationError

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc.functions.admin import kubernetes as resources
from kernel_api.rpc.functions.admin import kubernetes_pods as module


NS = "custom-operator"
SCOPE = {"bk_tenant_id": "tenant-a", "cluster_id": "BCS-K8S-1", "namespace": NS, "name": "collector"}
POD = {
    "metadata": {"labels": {"app": "collector"}},
    "spec": {
        "containers": [
            {
                "ports": [
                    {"name": "metrics", "containerPort": 9090},
                    {"name": "admin", "containerPort": 8080},
                ]
            }
        ]
    },
}
MONITOR = {"spec": {"selector": {"matchLabels": {"app": "collector"}}, "podMetricsEndpoints": [{"port": "metrics"}]}}
SERVICE = {
    "metadata": {"labels": {"app": "collector"}},
    "spec": {
        "selector": {"app": "collector"},
        "ports": [{"name": "http-metrics", "port": 80, "targetPort": "metrics"}],
    },
}


@pytest.fixture
def client(monkeypatch):
    client = Mock()
    cluster = Mock(api_client=client, operator_ns=NS, cluster_id=SCOPE["cluster_id"])
    lookup = Mock(return_value=cluster)
    monkeypatch.setattr(resources, "_get_bcs_cluster_or_raise", lookup)
    monkeypatch.setattr(resources, "_get_bcs_operator_configured_namespace", lambda _cluster: None)
    client.lookup = lookup
    return client


@pytest.fixture
def text(monkeypatch):
    text = Mock(return_value=("password=original\n", False))
    monkeypatch.setattr(module, "_get_text", text)
    return text


def metrics_params(**override):
    return {**SCOPE, "monitor_kind": "PodMonitor", "monitor_namespace": NS, "monitor_name": "collector", **override}


def test_logs_query_mapping_and_original_text(client, text):
    result = module.pod_logs(
        {**SCOPE, "container": "sidecar", "previous": True, "timestamps": True, "since_seconds": 60}
    )
    assert result["data"]["text"] == "password=original\n"
    assert result["data"]["container"] == "sidecar"
    assert result["data"]["unmasked_count"] == 1
    assert dict(text.call_args.args[2]) == {
        "follow": False,
        "container": "sidecar",
        "tailLines": 200,
        "sinceSeconds": 60,
        "previous": True,
        "timestamps": True,
        "limitBytes": 1024 * 1024,
    }
    assert text.call_args.args[1] == f"/api/v1/namespaces/{NS}/pods/collector/log"
    client.call_api.assert_not_called()
    client.lookup.assert_called_once_with("tenant-a", "BCS-K8S-1")


@pytest.mark.parametrize("body,truncated", [("", False), ("tail", True)])
def test_empty_and_truncated_logs(client, text, body, truncated):
    text.return_value = (body, truncated)
    result = module.pod_logs(SCOPE)
    assert result["data"]["text"] == body
    assert result["data"]["truncated"] is truncated
    assert bool(result["warnings"]) is truncated


@pytest.mark.parametrize(
    "override", [{"namespace": "other"}, {"bk_tenant_id": "other"}, {"name": "other"}, {"cluster_id": "other"}]
)
def test_explicit_pod_rules_remain_scope_bound(client, text, override):
    rule = {**SCOPE, "namespace": "extra", "api_group": "", "resource": "pods", "resource_names": ["collector"]}
    del rule["name"]
    with pytest.raises(PermissionDenied):
        module.pod_logs({**SCOPE, "namespace": "extra", "unmask_rules": [rule], **override})
    text.assert_not_called()


def test_explicit_pod_rule_and_configured_namespace(client, text, monkeypatch):
    rule = {
        "bk_tenant_id": "tenant-a",
        "cluster_id": "BCS-K8S-1",
        "namespace": "extra",
        "api_group": "",
        "resource": "pods",
        "resource_names": ["collector"],
    }
    module.pod_logs({**SCOPE, "namespace": "extra", "unmask_rules": [rule]})
    monkeypatch.setattr(resources, "_get_bcs_operator_configured_namespace", lambda _cluster: "configured")
    module.pod_logs({**SCOPE, "namespace": "configured"})
    assert text.call_count == 2


@pytest.mark.parametrize(
    "override",
    [
        {"follow": True},
        {"path": "/admin"},
        {"namespace": "../other"},
        {"tail_lines": 0},
        {"limit_bytes": module.MAX_TEXT_BYTES + 1},
        {"bk_tenant_id": "__all__"},
        {"api_version": "v1"},
    ],
)
def test_reject_invalid_log_inputs_before_lookup(client, text, override):
    with pytest.raises(ValidationError):
        module.pod_logs({**SCOPE, **override})
    client.lookup.assert_not_called()
    text.assert_not_called()


@pytest.mark.parametrize(
    "endpoint", [{"port": "metrics"}, {"portNumber": 9090}, {"targetPort": 9090}, {"targetPort": "metrics"}]
)
def test_podmonitor_resolves_only_declared_metrics_port(client, text, endpoint):
    monitor = deepcopy(MONITOR)
    monitor["spec"]["podMetricsEndpoints"] = [
        {**endpoint, "path": "/relation/metrics", "params": {"format": ["prometheus", "text"]}}
    ]
    client.call_api.side_effect = [POD, monitor]
    result = module.pod_metrics(metrics_params())
    assert result["data"]["endpoint"] == {"port": 9090, "path": "/relation/metrics", "scheme": "http"}
    assert text.call_args.args[1].endswith("/pods/http:collector:9090/proxy/relation/metrics")
    assert text.call_args.args[2] == [("format", "prometheus"), ("format", "text")]
    assert client.call_api.call_count == 2


@pytest.mark.parametrize(
    "endpoint,target",
    [
        ({"port": "http-metrics"}, "metrics"),
        ({"port": "http-metrics"}, 9090),
        ({"targetPort": "metrics"}, "metrics"),
        ({"targetPort": 9090}, "metrics"),
    ],
)
def test_servicemonitor_service_pod_port_mapping(client, text, endpoint, target):
    monitor, service = deepcopy(MONITOR), deepcopy(SERVICE)
    monitor["spec"]["endpoints"] = [endpoint]
    service["spec"]["ports"][0]["targetPort"] = target
    client.call_api.side_effect = [POD, monitor, service]
    result = module.pod_metrics(metrics_params(monitor_kind="ServiceMonitor", service_name="collector"))
    assert result["data"]["endpoint"]["port"] == 9090
    assert result["data"]["monitor"]["service_name"] == "collector"
    text.assert_called_once()


@pytest.mark.parametrize(
    "selector,labels,expected",
    [
        ({"matchExpressions": [{"key": "app", "operator": "In", "values": ["collector"]}]}, {"app": "collector"}, True),
        ({"matchExpressions": [{"key": "app", "operator": "NotIn", "values": ["collector"]}]}, {}, True),
        ({"matchExpressions": [{"key": "app", "operator": "Exists"}]}, {}, False),
        ({"matchExpressions": [{"key": "app", "operator": "DoesNotExist"}]}, {}, True),
    ],
)
def test_label_expressions(selector, labels, expected):
    assert module._matches_labels(selector, labels) is expected


@pytest.mark.parametrize(
    "selector,expected", [({}, False), ({"matchNames": [NS]}, True), ({"any": True, "matchNames": ["other"]}, True)]
)
def test_monitor_namespace_selector(client, text, selector, expected):
    monitor = deepcopy(MONITOR)
    monitor["spec"]["namespaceSelector"] = selector
    client.call_api.side_effect = [POD, monitor]
    if expected:
        module.pod_metrics(metrics_params(monitor_namespace="monitoring"))
        text.assert_called_once()
    else:
        with pytest.raises(PermissionDenied):
            module.pod_metrics(metrics_params(monitor_namespace="monitoring"))
        text.assert_not_called()


@pytest.mark.parametrize(
    "change", ["pod-label", "service-label", "service-selector", "no-selector", "port", "endpoint-index"]
)
def test_invalid_monitor_relationship_never_fetches_text(client, text, change):
    monitor, service, pod = deepcopy(MONITOR), deepcopy(SERVICE), deepcopy(POD)
    monitor["spec"]["endpoints"] = [{"port": "http-metrics"}]
    if change == "pod-label":
        pod["metadata"]["labels"] = {}
    if change == "service-label":
        service["metadata"]["labels"] = {}
    if change == "service-selector":
        service["spec"]["selector"] = {"app": "other"}
    if change == "no-selector":
        service["spec"]["selector"] = {}
    if change == "port":
        monitor["spec"]["endpoints"][0]["port"] = "admin"
    client.call_api.side_effect = [pod, monitor, service]
    with pytest.raises((PermissionDenied, ValidationError, CustomException)):
        module.pod_metrics(
            metrics_params(
                monitor_kind="ServiceMonitor",
                service_name="collector",
                endpoint_index=1 if change == "endpoint-index" else 0,
            )
        )
    text.assert_not_called()


@pytest.mark.parametrize(
    "change",
    [
        {"authorization": {"credentials": {"name": "secret"}}},
        {"tlsConfig": {"insecureSkipVerify": True}},
        {"proxyUrl": "http://proxy"},
        {"relabelings": [{"targetLabel": "__address__", "replacement": "other"}]},
        {"relabelings": [{"targetLabel": "__metrics_path__", "replacement": "/admin"}]},
        {"path": "/../admin"},
        {"path": "/%2e%2e/admin"},
        {"scheme": "ftp"},
        {"relabelings": [{"action": "labelmap", "regex": "(.+)", "replacement": "__address__"}]},
    ],
)
def test_unsupported_endpoint_never_fetches_text(client, text, change):
    monitor = deepcopy(MONITOR)
    monitor["spec"]["podMetricsEndpoints"][0].update(change)
    client.call_api.side_effect = [POD, monitor]
    with pytest.raises((ValidationError, CustomException)):
        module.pod_metrics(metrics_params())
    text.assert_not_called()


def test_metrics_denied_by_pod_scope_before_monitor_requests(client, text):
    with pytest.raises(PermissionDenied):
        module.pod_metrics(metrics_params(namespace="other"))
    client.call_api.assert_not_called()
    text.assert_not_called()


def test_raw_transport_no_redirect_bounds_and_connection_config():
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append((self.path, self.headers.get("authorization")))
            if self.path == "/redirect":
                self.send_response(302)
                self.send_header("Location", "/forbidden")
            else:
                self.send_response(200)
            self.end_headers()
            self.wfile.write(b"password=original\n")

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    config = k8s_client.Configuration(
        host=f"http://127.0.0.1:{server.server_port}",
        api_key={"authorization": "cluster-key"},
        api_key_prefix={"authorization": "Bearer"},
    )
    try:
        with k8s_client.ApiClient(configuration=config) as client:
            assert module._get_text(client, "/logs") == ("password=original\n", False)
            assert module._get_text(client, "/logs", limit=4, truncate=True) == ("pass", True)
            with pytest.raises(ValidationError):
                module._get_text(client, "/metrics", limit=4)
            with pytest.raises(ApiException) as error:
                module._get_text(client, "/redirect")
            assert error.value.status == 302
            assert "password=original" not in str(error.value)
            assert all(path != "/forbidden" for path, _auth in requests)
            assert all(auth == "Bearer cluster-key" for _path, auth in requests)
            assert client.configuration.retries is None
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_https_endpoint_and_default_path(client, text):
    monitor = deepcopy(MONITOR)
    monitor["spec"]["podMetricsEndpoints"][0]["scheme"] = "https"
    client.call_api.side_effect = [POD, monitor]
    result = module.pod_metrics(metrics_params())
    assert result["data"]["endpoint"] == {"scheme": "https", "port": 9090, "path": "/metrics"}
    assert text.call_args.args[1].endswith("/pods/https:collector:9090/proxy/metrics")


def test_ambiguous_port_is_not_implicitly_chosen(client, text):
    pod = deepcopy(POD)
    pod["spec"]["containers"].append({"ports": [{"name": "metrics", "containerPort": 9091}]})
    client.call_api.side_effect = [pod, MONITOR]
    with pytest.raises(ValidationError):
        module.pod_metrics(metrics_params())
    text.assert_not_called()
