"""受 Kubernetes 遮罩范围约束的 Pod 日志及 Monitor 指标单次读取。"""

from kubernetes.client.rest import ApiException
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from urllib3 import Timeout

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.kubernetes import (
    SEGMENT,
    UNMASK_RULE_SCHEMA,
    ClusterSerializer,
    UnmaskRuleSerializer,
    _context,
    _get,
    _matching_rules,
    _response,
)

MAX_TEXT_BYTES = 5 * 1024 * 1024


class PodSerializer(ClusterSerializer):
    namespace = serializers.RegexField(SEGMENT, max_length=253)
    name = serializers.RegexField(SEGMENT, max_length=253)
    unmask_rules = UnmaskRuleSerializer(many=True, required=False)


class PodLogsSerializer(PodSerializer):
    container = serializers.RegexField(SEGMENT, max_length=253, required=False)
    tail_lines = serializers.IntegerField(min_value=1, max_value=10000, default=200)
    since_seconds = serializers.IntegerField(min_value=1, required=False)
    previous = serializers.BooleanField(default=False)
    timestamps = serializers.BooleanField(default=False)
    limit_bytes = serializers.IntegerField(min_value=1, max_value=MAX_TEXT_BYTES, default=1024 * 1024)


class PodMetricsSerializer(PodSerializer):
    monitor_kind = serializers.ChoiceField(choices=("ServiceMonitor", "PodMonitor"))
    monitor_namespace = serializers.RegexField(SEGMENT, max_length=253)
    monitor_name = serializers.RegexField(SEGMENT, max_length=253)
    endpoint_index = serializers.IntegerField(min_value=0, default=0)
    service_name = serializers.RegexField(SEGMENT, max_length=253, required=False)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs["monitor_kind"] == "ServiceMonitor" and not attrs.get("service_name"):
            raise serializers.ValidationError({"service_name": "ServiceMonitor 必须指定 Service 名称"})
        if attrs["monitor_kind"] == "PodMonitor" and attrs.get("service_name"):
            raise serializers.ValidationError({"service_name": "PodMonitor 不接受 Service 名称"})
        return attrs


def _pod_context(params, serializer):
    values, client, _prefix = _context(params, serializer)
    scope = {**values, "api_version": "v1", "resource": "pods"}
    if values["namespace"] not in values["_default_unmask_namespaces"] and not _matching_rules(scope):
        raise PermissionDenied("Pod 不在 Kubernetes 遮罩放行范围内")
    return values, client


def _get_text(client, path, query=(), *, limit=MAX_TEXT_BYTES, truncate=False):
    # SDK call_api 不提供逐请求 redirect 开关；复用 BCS 客户端的认证和 TLS 连接池。
    headers = {**client.default_headers, "Accept": "text/plain, application/openmetrics-text"}
    query = list(query)
    client.update_params_for_auth(headers, query, ["BearerToken"])
    response = client.rest_client.pool_manager.request(
        "GET",
        client.configuration.host + path,
        fields=query,
        headers=headers,
        preload_content=False,
        redirect=False,
        retries=False,
        timeout=Timeout(connect=5, read=30),
    )
    try:
        if not 200 <= response.status < 300:
            # 保留上游状态供定位，正文不进入异常日志。
            raise ApiException(status=response.status, reason="Kubernetes 文本查询失败（不跟随重定向）")
        content = response.read(limit + 1)
        exceeded = len(content) > limit
        if exceeded and not truncate:
            raise serializers.ValidationError(f"指标响应超过 {limit} bytes 上限")
        return content[:limit].decode("utf-8", errors="replace"), len(content) >= limit if truncate else exceeded
    finally:
        response.close()
        response.release_conn()


def _pod_response(operation, values, data):
    return _response(
        operation,
        values,
        {
            "namespace": values["namespace"],
            "name": values["name"],
            "unmasked_resources": [{"namespace": values["namespace"], "name": values["name"]}],
            "unmasked_count": 1,
            **data,
        },
    )


POD_PROPERTIES = {
    "bk_tenant_id": {"type": "string", "minLength": 1, "maxLength": 128},
    "cluster_id": {"type": "string", "minLength": 1, "maxLength": 253},
    "namespace": {"type": "string", "pattern": SEGMENT},
    "name": {"type": "string", "pattern": SEGMENT},
    "unmask_rules": {"type": "array", "description": "仅由受信 Admin 服务按环境配置注入", "items": UNMASK_RULE_SCHEMA},
}
POD_REQUIRED = ["bk_tenant_id", "cluster_id", "namespace", "name"]
POD_EXAMPLE = {
    "bk_tenant_id": "system",
    "cluster_id": "BCS-K8S-00000",
    "namespace": "bkmonitor-operator",
    "name": "example-pod",
}


@KernelRPCRegistry.register(
    "admin.kubernetes.pod_logs",
    summary="读取放行范围内 Pod 的容器日志",
    description="inspect 单次 GET；Pod 必须在集群默认 namespace 或环境 pods 例外内，不提供日志跟随。",
    params_schema={
        "type": "object",
        "additionalProperties": False,
        "required": POD_REQUIRED,
        "properties": {
            **POD_PROPERTIES,
            "container": {"type": "string", "pattern": SEGMENT},
            "tail_lines": {"type": "integer", "minimum": 1, "maximum": 10000, "default": 200},
            "since_seconds": {"type": "integer", "minimum": 1},
            "previous": {"type": "boolean", "default": False},
            "timestamps": {"type": "boolean", "default": False},
            "limit_bytes": {"type": "integer", "minimum": 1, "maximum": MAX_TEXT_BYTES, "default": 1024 * 1024},
        },
    },
    example_params=POD_EXAMPLE,
)
def pod_logs(params):
    values, client = _pod_context(params, PodLogsSerializer)
    query = [("follow", False)]
    for source, target in (
        ("container", "container"),
        ("tail_lines", "tailLines"),
        ("since_seconds", "sinceSeconds"),
        ("previous", "previous"),
        ("timestamps", "timestamps"),
        ("limit_bytes", "limitBytes"),
    ):
        if source in values:
            query.append((target, values[source]))
    text, truncated = _get_text(
        client,
        f"/api/v1/namespaces/{values['namespace']}/pods/{values['name']}/log",
        query,
        limit=values["limit_bytes"],
        truncate=True,
    )
    response = _pod_response(
        "kubernetes.pod_logs",
        values,
        {
            "text": text,
            "truncated": truncated,
            **({"container": values["container"]} if "container" in values else {}),
        },
    )
    if truncated:
        response["warnings"].append("日志达到 limit_bytes 上限，正文已截断")
    return response


def _matches_labels(selector, labels):
    if not all(labels.get(key) == value for key, value in selector.get("matchLabels", {}).items()):
        return False
    for expression in selector.get("matchExpressions", []):
        key, operator = expression["key"], expression["operator"]
        values = expression.get("values", [])
        if operator == "In":
            matches = key in labels and labels[key] in values
        elif operator == "NotIn":
            matches = key not in labels or labels[key] not in values
        elif operator == "Exists":
            matches = key in labels
        elif operator == "DoesNotExist":
            matches = key not in labels
        else:
            raise serializers.ValidationError(f"不支持的标签选择操作: {operator}")
        if not matches:
            return False
    return True


def _matches_namespace(selector, monitor_namespace, namespace):
    return bool(selector.get("any")) or namespace in (selector.get("matchNames") or [monitor_namespace])


def _pod_port(pod, value):
    ports = {
        port["containerPort"]
        for container in pod.get("spec", {}).get("containers", [])
        for port in container.get("ports", [])
        if port.get("protocol", "TCP") == "TCP"
        and (port.get("name") == value if isinstance(value, str) else port["containerPort"] == value)
    }
    if len(ports) != 1:
        raise serializers.ValidationError("Monitor 端口无法唯一解析到 Pod 的 TCP containerPort")
    return ports.pop()


def _metrics_port(endpoint, pod, service):
    if service is None:
        return _pod_port(pod, endpoint.get("port") or endpoint.get("portNumber") or endpoint.get("targetPort"))
    if endpoint.get("port"):
        ports = [
            port
            for port in service["spec"].get("ports", [])
            if port.get("name") == endpoint["port"] and port.get("protocol", "TCP") == "TCP"
        ]
        if len(ports) != 1:
            raise serializers.ValidationError("Monitor port 未匹配唯一的 Service TCP 端口")
        target = ports[0].get("targetPort", ports[0]["port"])
        return _pod_port(pod, target) if isinstance(target, str) else target
    return _pod_port(pod, endpoint.get("targetPort"))


def _endpoint_request(endpoint, monitor):
    unsupported = (
        "authorization",
        "basicAuth",
        "bearerTokenSecret",
        "bearerTokenFile",
        "oauth2",
        "tlsConfig",
        "proxyUrl",
        "proxyURL",
        "noProxy",
        "proxyFromEnvironment",
        "proxyConnectHeader",
        "httpHeaders",
    )
    if any(endpoint.get(field) for field in unsupported) or monitor["spec"].get("scrapeClass"):
        raise CustomException(
            code="KUBERNETES_METRICS_UNSUPPORTED", message="不支持需要认证、自定义 TLS、代理或 scrapeClass 的指标端点"
        )
    for relabel in endpoint.get("relabelings", []):
        target = relabel.get("targetLabel", "")
        if (
            relabel.get("action") == "labelmap"
            or target in {"__address__", "__scheme__", "__metrics_path__"}
            or target.startswith("__param_")
        ):
            raise CustomException(code="KUBERNETES_METRICS_UNSUPPORTED", message="不支持改写抓取目标的 relabelings")
    scheme, path = endpoint.get("scheme") or "http", endpoint.get("path") or "/metrics"
    if scheme not in {"http", "https"}:
        raise serializers.ValidationError("指标端点仅支持 HTTP(S)")
    if (
        not path.startswith("/")
        or path.startswith("//")
        or ".." in path.split("/")
        or any(char in path for char in ("?", "#", "\\", "%"))
    ):
        raise serializers.ValidationError("指标端点 path 必须是普通绝对路径，不接受 URL 或路径跳转")
    return scheme, path, [(key, value) for key, values in endpoint.get("params", {}).items() for value in values]


@KernelRPCRegistry.register(
    "admin.kubernetes.pod_metrics",
    summary="按指定 ServiceMonitor/PodMonitor 抓取放行 Pod 的指标",
    description="inspect 单次 GET；同时受 pods 放行范围和 Monitor 选择关系限制，端口/路径/参数来自 Monitor。",
    params_schema={
        "type": "object",
        "additionalProperties": False,
        "required": [*POD_REQUIRED, "monitor_kind", "monitor_namespace", "monitor_name"],
        "properties": {
            **POD_PROPERTIES,
            "monitor_kind": {"type": "string", "enum": ["ServiceMonitor", "PodMonitor"]},
            "monitor_namespace": {"type": "string", "pattern": SEGMENT},
            "monitor_name": {"type": "string", "pattern": SEGMENT},
            "endpoint_index": {"type": "integer", "minimum": 0, "default": 0},
            "service_name": {
                "type": "string",
                "pattern": SEGMENT,
                "description": "ServiceMonitor 必填，PodMonitor 不传",
            },
        },
    },
    example_params={
        **POD_EXAMPLE,
        "monitor_kind": "PodMonitor",
        "monitor_namespace": "bkmonitor-operator",
        "monitor_name": "example-monitor",
        "endpoint_index": 0,
    },
)
def pod_metrics(params):
    values, client = _pod_context(params, PodMetricsSerializer)
    namespace = values["namespace"]
    pod = _get(client, f"/api/v1/namespaces/{namespace}/pods/{values['name']}")
    service_monitor = values["monitor_kind"] == "ServiceMonitor"
    plural = "servicemonitors" if service_monitor else "podmonitors"
    monitor = _get(
        client,
        f"/apis/monitoring.coreos.com/v1/namespaces/{values['monitor_namespace']}/{plural}/{values['monitor_name']}",
    )
    spec = monitor["spec"]
    if not _matches_namespace(spec.get("namespaceSelector", {}), values["monitor_namespace"], namespace):
        raise PermissionDenied("目标 Pod namespace 未被 Monitor 选中")
    service = None
    if service_monitor:
        service = _get(client, f"/api/v1/namespaces/{namespace}/services/{values['service_name']}")
        if not _matches_labels(spec["selector"], service.get("metadata", {}).get("labels", {})):
            raise PermissionDenied("Service 未被 ServiceMonitor 选中")
        selector = service["spec"].get("selector")
        if not selector:
            raise CustomException(code="KUBERNETES_METRICS_UNSUPPORTED", message="不支持没有 selector 的 Service")
        if not _matches_labels({"matchLabels": selector}, pod.get("metadata", {}).get("labels", {})):
            raise PermissionDenied("目标 Pod 未被 Service selector 选中")
    elif not _matches_labels(spec["selector"], pod.get("metadata", {}).get("labels", {})):
        raise PermissionDenied("目标 Pod 未被 PodMonitor 选中")
    endpoints = spec.get("endpoints" if service_monitor else "podMetricsEndpoints", [])
    if values["endpoint_index"] >= len(endpoints):
        raise serializers.ValidationError("endpoint_index 超出 Monitor 端点范围")
    endpoint = endpoints[values["endpoint_index"]]
    scheme, path, query = _endpoint_request(endpoint, monitor)
    port = _metrics_port(endpoint, pod, service)
    text, _truncated = _get_text(
        client, f"/api/v1/namespaces/{namespace}/pods/{scheme}:{values['name']}:{port}/proxy{path}", query
    )
    return _pod_response(
        "kubernetes.pod_metrics",
        values,
        {
            "text": text,
            "monitor": {
                "kind": values["monitor_kind"],
                "namespace": values["monitor_namespace"],
                "name": values["monitor_name"],
                "endpoint_index": values["endpoint_index"],
                **({"service_name": values["service_name"]} if service_monitor else {}),
            },
            "endpoint": {"scheme": scheme, "port": port, "path": path},
        },
    )
