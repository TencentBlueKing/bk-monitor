"""通过 BCSClusterInfo 的认证客户端查询 Kubernetes；仅开放资源 GET。"""

from rest_framework import serializers

from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.bcs_cluster import _get_bcs_cluster_or_raise
from kernel_api.rpc.functions.admin.common import build_response
from kernel_api.rpc.functions.admin.consul import _is_sensitive_key, _redact_sensitive_value

SEGMENT = r"^[a-z0-9][a-z0-9.-]*$"


class ScopeSerializer(serializers.Serializer):
    bk_tenant_id = serializers.CharField(max_length=128)
    cluster_id = serializers.CharField(max_length=253)
    api_version = serializers.RegexField(r"^[a-z0-9][a-z0-9.-]*(/[a-z0-9][a-z0-9.-]*)?$", default="v1")

    def validate(self, attrs):
        if attrs["bk_tenant_id"] == "__all__":
            raise serializers.ValidationError("请选择具体租户")
        unknown = set(self.initial_data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError(f"不支持的参数: {', '.join(sorted(unknown))}")
        return attrs


class DiscoverySerializer(ScopeSerializer):
    page = serializers.IntegerField(min_value=1, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, default=20)


class ResourceSerializer(ScopeSerializer):
    resource = serializers.RegexField(SEGMENT, max_length=253)
    namespace = serializers.RegexField(SEGMENT, max_length=253, required=False)


class ListSerializer(ResourceSerializer):
    page_size = serializers.IntegerField(min_value=1, max_value=100, default=20)
    label_selector = serializers.CharField(max_length=4096, required=False, allow_blank=True)
    field_selector = serializers.CharField(max_length=4096, required=False, allow_blank=True)

    # continue 是 Python 关键字，保留 Kubernetes 原生游标字段名。
    locals()["continue"] = serializers.CharField(max_length=8192, required=False, allow_blank=True)


class GetSerializer(ResourceSerializer):
    name = serializers.RegexField(SEGMENT, max_length=253)


def _context(params, serializer_class):
    serializer = serializer_class(data=params)
    serializer.is_valid(raise_exception=True)
    values = serializer.validated_data
    cluster = _get_bcs_cluster_or_raise(values["bk_tenant_id"], values["cluster_id"])
    version = values["api_version"]
    prefix = f"/apis/{version}" if "/" in version else f"/api/{version}"
    return values, cluster.api_client, prefix


def _get(client, path, query=()):
    return client.call_api(
        path,
        "GET",
        query_params=list(query),
        header_params={"Accept": "application/json"},
        response_type="object",
        auth_settings=["BearerToken"],
        _return_http_data_only=True,
        _request_timeout=(5, 30),
    )


def _resource_path(client, prefix, params, verb):
    # Discovery 决定资源作用域，并排除 proxy/exec/log 等子资源。
    resources = _get(client, prefix)["resources"]
    resource = next((item for item in resources if item["name"] == params["resource"]), None)
    if resource is None or verb not in resource.get("verbs", []):
        raise serializers.ValidationError("资源不存在或不支持此只读操作")
    namespace = params.get("namespace")
    if not resource["namespaced"] and namespace:
        raise serializers.ValidationError("集群级资源不能指定 namespace")
    if resource["namespaced"] and verb == "get" and not namespace:
        raise serializers.ValidationError("查询命名空间资源详情必须指定 namespace")
    path = prefix + (f"/namespaces/{namespace}" if namespace else "") + f"/{params['resource']}"
    return path


def _redact(value):
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if not isinstance(value, dict):
        return _redact_sensitive_value(value)
    result = {}
    for key, item in value.items():
        if key in {"secretKeyRef", "configMapKeyRef", "secretRef", "configMapRef"} and isinstance(item, dict):
            # 引用只含定位信息，不读取引用目标；保留 key 名称而非配置值。
            result[key] = {field: item[field] for field in ("name", "key", "optional") if field in item}
        elif _is_sensitive_key(key) and not isinstance(item, bool):
            result[key] = "[REDACTED]"
        else:
            result[key] = _redact(item)
    if result.get("kind") == "Secret":
        result.pop("data", None)
        result.pop("stringData", None)
        result["metadata"] = {k: v for k, v in result.get("metadata", {}).items() if k != "annotations"}
    if result.get("kind") == "ConfigMap":
        for key in ("data", "binaryData"):
            if isinstance(result.get(key), dict):
                result[key] = {name: "[REDACTED]" for name in result[key]}
    # 遍历 Pod spec 和所有工作负载模板，覆盖普通、初始化及临时容器。
    if isinstance(result.get("env"), list):
        result["env"] = [
            {**entry, "value": "[REDACTED]"} if isinstance(entry, dict) and "value" in entry else entry
            for entry in result["env"]
        ]
    if isinstance(result.get("annotations"), dict):
        result["annotations"] = {
            key: item for key, item in result["annotations"].items() if not key.endswith("last-applied-configuration")
        }
    return result


def _response(operation, params, data):
    return build_response(
        operation=operation,
        func_name=f"admin.{operation}",
        bk_tenant_id=params["bk_tenant_id"],
        data=data,
        safety_level="inspect",
    )


@KernelRPCRegistry.register(
    "admin.kubernetes.api_resources",
    summary="分页发现指定 API version 的资源类型",
    description="inspect 只读查询，复用 BCSClusterInfo.api_client；Secret 正文不返回，不支持子资源。",
    params_schema={
        "additionalProperties": False,
        "properties": {
            "api_version": {
                "default": "v1",
                "pattern": "^[a-z0-9][a-z0-9.-]*(\\/[a-z0-9][a-z0-9.-]*)?$",
                "type": "string",
            },
            "bk_tenant_id": {"maxLength": 128, "minLength": 1, "type": "string"},
            "cluster_id": {"maxLength": 253, "minLength": 1, "type": "string"},
            "page": {"default": 1, "minimum": 1, "type": "integer"},
            "page_size": {"default": 20, "maximum": 100, "minimum": 1, "type": "integer"},
        },
        "required": ["bk_tenant_id", "cluster_id"],
        "type": "object",
    },
    example_params={"bk_tenant_id": "system", "cluster_id": "BCS-K8S-00000", "api_version": "v1"},
)
def api_resources(params):
    values, client, prefix = _context(params, DiscoverySerializer)
    resources = [
        r
        for r in _get(client, prefix)["resources"]
        if "/" not in r["name"] and ({"get", "list"} & set(r.get("verbs", [])))
    ]
    start = (values["page"] - 1) * values["page_size"]
    return _response(
        "kubernetes.api_resources",
        values,
        {
            "items": resources[start : start + values["page_size"]],
            "total": len(resources),
            "page": values["page"],
            "page_size": values["page_size"],
        },
    )


@KernelRPCRegistry.register(
    "admin.kubernetes.list",
    summary="分页查询 Kubernetes 资源（原生 continue 游标）",
    description="inspect 只读查询，复用 BCSClusterInfo.api_client；Secret 正文不返回，不支持子资源。",
    params_schema={
        "additionalProperties": False,
        "properties": {
            "api_version": {
                "default": "v1",
                "pattern": "^[a-z0-9][a-z0-9.-]*(\\/[a-z0-9][a-z0-9.-]*)?$",
                "type": "string",
            },
            "bk_tenant_id": {"maxLength": 128, "minLength": 1, "type": "string"},
            "cluster_id": {"maxLength": 253, "minLength": 1, "type": "string"},
            "continue": {"maxLength": 8192, "type": "string"},
            "field_selector": {"maxLength": 4096, "type": "string"},
            "label_selector": {"maxLength": 4096, "type": "string"},
            "namespace": {"maxLength": 253, "pattern": "^[a-z0-9][a-z0-9.-]*$", "type": "string"},
            "page_size": {"default": 20, "maximum": 100, "minimum": 1, "type": "integer"},
            "resource": {"maxLength": 253, "pattern": "^[a-z0-9][a-z0-9.-]*$", "type": "string"},
        },
        "required": ["bk_tenant_id", "cluster_id", "resource"],
        "type": "object",
    },
    example_params={
        "bk_tenant_id": "system",
        "cluster_id": "BCS-K8S-00000",
        "api_version": "v1",
        "resource": "pods",
        "namespace": "default",
    },
)
def list_resources(params):
    values, client, prefix = _context(params, ListSerializer)
    path = _resource_path(client, prefix, values, "list")
    query = [("limit", values["page_size"])]
    for source, target in (
        ("continue", "continue"),
        ("label_selector", "labelSelector"),
        ("field_selector", "fieldSelector"),
    ):
        if values.get(source):
            query.append((target, values[source]))
    result = _get(client, path, query)
    metadata = result.get("metadata", {})
    cursor = metadata.get("continue", "")
    return _response(
        "kubernetes.list",
        values,
        {
            "items": [_redact(item) for item in result["items"]],
            "continue": cursor,
            "resource_version": metadata.get("resourceVersion", ""),
            "has_more": bool(cursor),
        },
    )


@KernelRPCRegistry.register(
    "admin.kubernetes.get",
    summary="查询 Kubernetes 单资源详情",
    description="inspect 只读查询，复用 BCSClusterInfo.api_client；Secret 正文不返回，不支持子资源。",
    params_schema={
        "additionalProperties": False,
        "properties": {
            "api_version": {
                "default": "v1",
                "pattern": "^[a-z0-9][a-z0-9.-]*(\\/[a-z0-9][a-z0-9.-]*)?$",
                "type": "string",
            },
            "bk_tenant_id": {"maxLength": 128, "minLength": 1, "type": "string"},
            "cluster_id": {"maxLength": 253, "minLength": 1, "type": "string"},
            "name": {"maxLength": 253, "pattern": "^[a-z0-9][a-z0-9.-]*$", "type": "string"},
            "namespace": {"maxLength": 253, "pattern": "^[a-z0-9][a-z0-9.-]*$", "type": "string"},
            "resource": {"maxLength": 253, "pattern": "^[a-z0-9][a-z0-9.-]*$", "type": "string"},
        },
        "required": ["bk_tenant_id", "cluster_id", "resource", "name"],
        "type": "object",
    },
    example_params={
        "bk_tenant_id": "system",
        "cluster_id": "BCS-K8S-00000",
        "api_version": "v1",
        "resource": "pods",
        "namespace": "default",
        "name": "example-pod",
    },
)
def get_resource(params):
    values, client, prefix = _context(params, GetSerializer)
    path = _resource_path(client, prefix, values, "get") + f"/{values['name']}"
    return _response("kubernetes.get", values, {"resource": _redact(_get(client, path))})
