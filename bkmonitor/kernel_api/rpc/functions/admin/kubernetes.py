"""通过 BCSClusterInfo 的认证客户端查询 Kubernetes；仅开放资源 GET。"""

from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.bcs_cluster import _get_bcs_cluster_or_raise
from kernel_api.rpc.functions.admin.common import build_response
from kernel_api.rpc.functions.admin.consul import _is_sensitive_key, _redact_sensitive_value

SEGMENT = r"^[a-z0-9][a-z0-9.-]*$"
UNMASK_RULE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["bk_tenant_id", "cluster_id", "namespace", "api_group", "resource"],
    "properties": {
        "bk_tenant_id": {"type": "string", "minLength": 1},
        "cluster_id": {"type": "string", "minLength": 1},
        "namespace": {"type": "string", "pattern": SEGMENT},
        "api_group": {"type": "string"},
        "resource": {"type": "string", "pattern": SEGMENT},
        "resource_names": {"type": "array", "items": {"type": "string", "pattern": SEGMENT}},
    },
}


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


class UnmaskRuleSerializer(serializers.Serializer):
    bk_tenant_id = serializers.CharField(max_length=128)
    cluster_id = serializers.CharField(max_length=253)
    namespace = serializers.RegexField(SEGMENT, max_length=253)
    api_group = serializers.CharField(allow_blank=True, max_length=253)
    resource = serializers.RegexField(SEGMENT, max_length=253)
    resource_names = serializers.ListField(child=serializers.RegexField(SEGMENT, max_length=253), required=False)


class ResourceSerializer(ScopeSerializer):
    resource = serializers.RegexField(SEGMENT, max_length=253)
    namespace = serializers.RegexField(SEGMENT, max_length=253, required=False)
    include_sensitive = serializers.BooleanField(default=False)
    unmask_rules = UnmaskRuleSerializer(many=True, required=False)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs["include_sensitive"]:
            if not attrs.get("namespace"):
                raise serializers.ValidationError("原文查询必须指定 namespace")
            if not _matching_rules(attrs):
                raise PermissionDenied("没有适用的 Kubernetes 遮罩例外规则")
        return attrs


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


def _matching_rules(params, name=None):
    group = params["api_version"].split("/")[0] if "/" in params["api_version"] else ""
    name = name if name is not None else params.get("name")
    return [
        rule
        for rule in params.get("unmask_rules", [])
        if rule["bk_tenant_id"] == params["bk_tenant_id"]
        and rule["cluster_id"] == params["cluster_id"]
        and rule["namespace"] == params.get("namespace")
        and rule["api_group"] == group
        and rule["resource"] == params["resource"]
        and (name is None or not rule.get("resource_names") or name in rule["resource_names"])
    ]


def _resource_context(client, prefix, params, verb):
    # Discovery 决定资源作用域，并排除 proxy/exec/log 等子资源。
    resources = _get(client, prefix)["resources"]
    resource = next((item for item in resources if item["name"] == params["resource"]), None)
    if resource is None or verb not in resource.get("verbs", []):
        raise serializers.ValidationError("资源不存在或不支持此只读操作")
    if params.get("include_sensitive") and (resource["kind"] == "Secret" or not resource["namespaced"]):
        raise PermissionDenied("Secret 和集群级资源不能解除遮罩")
    namespace = params.get("namespace")
    if not resource["namespaced"] and namespace:
        raise serializers.ValidationError("集群级资源不能指定 namespace")
    if resource["namespaced"] and verb == "get" and not namespace:
        raise serializers.ValidationError("查询命名空间资源详情必须指定 namespace")
    path = prefix + (f"/namespaces/{namespace}" if namespace else "") + f"/{params['resource']}"
    return path, resource["kind"]


def _redact(value, kind=None, allow_unmask=False, revealed=None):
    if isinstance(value, list):
        return [_redact(item, allow_unmask=allow_unmask, revealed=revealed) for item in value]
    if not isinstance(value, dict):
        return _redact_sensitive_value(value)
    # 列表项可能省略 kind；根资源类型使用本次 discovery 的结果。
    kind = kind or value.get("kind")
    if kind == "Secret":
        allow_unmask = False
    result = {}
    for key, item in value.items():
        if key in {"secretKeyRef", "configMapKeyRef", "secretRef", "configMapRef"} and isinstance(item, dict):
            # 引用只含定位信息，不读取引用目标；保留 key 名称而非配置值。
            result[key] = {field: item[field] for field in ("name", "key", "optional") if field in item}
        elif _is_sensitive_key(key) and not isinstance(item, bool):
            result[key] = "[REDACTED]"
        else:
            result[key] = _redact(item, allow_unmask=allow_unmask, revealed=revealed)
    if kind == "Secret":
        result.pop("data", None)
        result.pop("stringData", None)
        result["metadata"] = {k: v for k, v in result.get("metadata", {}).items() if k != "annotations"}
    if kind == "ConfigMap":
        for key in ("data", "binaryData"):
            if isinstance(result.get(key), dict):
                result[key] = dict(value[key]) if allow_unmask else {name: "[REDACTED]" for name in result[key]}
                if allow_unmask and result[key] and revealed is not None:
                    revealed.append(key)
    # 遍历 Pod spec 和所有工作负载模板，覆盖普通、初始化及临时容器。
    if isinstance(result.get("env"), list):
        result["env"] = [
            {**entry, "value": value["env"][index]["value"] if allow_unmask else "[REDACTED]"}
            if isinstance(entry, dict) and "value" in entry
            else entry
            for index, entry in enumerate(result["env"])
        ]
        if (
            allow_unmask
            and revealed is not None
            and any(isinstance(entry, dict) and "value" in entry for entry in result["env"])
        ):
            revealed.append("env")
    if isinstance(result.get("annotations"), dict):
        result["annotations"] = {
            key: item for key, item in result["annotations"].items() if not key.endswith("last-applied-configuration")
        }
    return result


def _redact_resource(resource, kind, params, unmasked_resources):
    metadata = resource.get("metadata", {})
    allowed = bool(
        params.get("include_sensitive")
        and metadata.get("namespace") == params.get("namespace")
        and _matching_rules(params, metadata.get("name"))
    )
    revealed = []
    result = _redact(resource, kind=kind, allow_unmask=allowed, revealed=revealed)
    if revealed:
        unmasked_resources.append({"namespace": metadata["namespace"], "name": metadata["name"]})
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
            "include_sensitive": {"type": "boolean", "default": False},
            "unmask_rules": {
                "type": "array",
                "description": "仅由受信 Admin 服务按环境配置注入的例外规则",
                "items": UNMASK_RULE_SCHEMA,
            },
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
    path, kind = _resource_context(client, prefix, values, "list")
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
    unmasked_resources = []
    items = [_redact_resource(item, kind, values, unmasked_resources) for item in result["items"]]
    return _response(
        "kubernetes.list",
        values,
        {
            "items": items,
            **(
                {"unmasked_resources": unmasked_resources, "unmasked_count": len(unmasked_resources)}
                if values["include_sensitive"]
                else {}
            ),
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
            "include_sensitive": {"type": "boolean", "default": False},
            "unmask_rules": {
                "type": "array",
                "description": "仅由受信 Admin 服务按环境配置注入的例外规则",
                "items": UNMASK_RULE_SCHEMA,
            },
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
    path, kind = _resource_context(client, prefix, values, "get")
    resource = _get(client, path + f"/{values['name']}")
    unmasked_resources = []
    resource = _redact_resource(resource, kind, values, unmasked_resources)
    return _response(
        "kubernetes.get",
        values,
        {
            "resource": resource,
            **(
                {"unmasked_resources": unmasked_resources, "unmasked_count": len(unmasked_resources)}
                if values["include_sensitive"]
                else {}
            ),
        },
    )
