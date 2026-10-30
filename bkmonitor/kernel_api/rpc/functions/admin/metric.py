"""AI 指标发现：复用监控指标选择器和 UQ 维度查询。"""

from rest_framework import serializers

from api.unify_query.default import GetPromqlLabelValuesResource
from bkmonitor.models.metric_list_cache import MetricListCache
from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.common import build_response
from monitor_web.strategies.resources.v2 import GetMetricListV2Resource


class MetricLabelValuesResource(GetPromqlLabelValuesResource):
    """只在 Admin RPC 内补齐显式租户，复用原 Resource 的路由与请求。"""

    class RequestSerializer(GetPromqlLabelValuesResource.RequestSerializer):
        bk_tenant_id = serializers.CharField()


class ScopeSerializer(serializers.Serializer):
    bk_tenant_id = serializers.CharField(max_length=128)
    bk_biz_id = serializers.IntegerField(min_value=1)

    def validate_bk_tenant_id(self, value):
        if value == "__all__":
            raise serializers.ValidationError("请选择具体租户")
        return value


class SearchSerializer(ScopeSerializer):
    query = serializers.CharField(required=False, allow_blank=True, default="", max_length=512)
    data_source_label = serializers.ListField(child=serializers.CharField(), default=list)
    page = serializers.IntegerField(min_value=1, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, default=20)


class DetailSerializer(ScopeSerializer):
    metric_id = serializers.CharField(max_length=1024)


class DimensionValuesSerializer(ScopeSerializer):
    match = serializers.ListField(child=serializers.CharField(max_length=65536), min_length=1, max_length=20)
    label = serializers.CharField(max_length=256)
    start = serializers.IntegerField(min_value=0)
    end = serializers.IntegerField(min_value=0)
    page = serializers.IntegerField(min_value=1, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, default=20)

    def validate(self, attrs):
        if attrs["end"] < attrs["start"]:
            raise serializers.ValidationError("结束时间不能早于开始时间")
        return attrs


SCOPE = {
    "bk_tenant_id": {"type": "string", "minLength": 1},
    "bk_biz_id": {"type": "integer", "minimum": 1},
}
PAGING = {
    "page": {"type": "integer", "minimum": 1, "default": 1},
    "page_size": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
}
EXAMPLE_SCOPE = {"bk_tenant_id": "system", "bk_biz_id": 2}


def _validated(serializer_class, params):
    serializer = serializer_class(data=params)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def _response(operation, params, data):
    return build_response(
        operation=operation,
        func_name=f"admin.{operation}",
        bk_tenant_id=params["bk_tenant_id"],
        data={"source": {key: params[key] for key in SCOPE}, **data},
    )


def _metrics(params, conditions, page, page_size):
    # 显式租户范围，复用选择器的过滤、排序、分页和 PromQL 名称生成；不触发缓存刷新。
    selector = GetMetricListV2Resource
    query = selector().validate_request_data(
        {
            "bk_biz_id": params["bk_biz_id"],
            "data_type_label": "time_series",
            "data_source_label": params.get("data_source_label", []),
            "conditions": conditions,
            "page": page,
            "page_size": page_size,
        }
    )
    metrics = MetricListCache.objects.filter(
        bk_tenant_id=params["bk_tenant_id"], bk_biz_id__in=[0, params["bk_biz_id"]]
    )
    metrics = selector.filter_by_conditions(metrics, query)
    metrics = selector.data_type_filter(metrics, query)
    metrics = selector.data_source_filter(metrics, query)
    metrics, total = selector.page_filter(metrics, query)
    return selector.get_metric_list(params["bk_biz_id"], metrics), total


@KernelRPCRegistry.register(
    "admin.metric.search",
    summary="分页检索业务可见时序指标",
    description="复用监控指标选择器，返回指标标识、PromQL 名称、单位及维度；缓存命中不代表当前有数据。",
    params_schema={
        "type": "object",
        "required": list(SCOPE),
        "additionalProperties": False,
        "properties": {
            **SCOPE,
            **PAGING,
            "query": {"type": "string"},
            "data_source_label": {"type": "array", "items": {"type": "string"}},
        },
    },
    example_params={**EXAMPLE_SCOPE, "query": "cpu", "page": 1, "page_size": 20},
)
def search(params):
    params = _validated(SearchSerializer, params)
    conditions = [{"key": "query", "value": [params["query"]]}] if params["query"] else []
    items, total = _metrics(params, conditions, params["page"], params["page_size"])
    return _response(
        "metric.search",
        params,
        {
            "items": items,
            "total": total,
            "page": params["page"],
            "page_size": params["page_size"],
        },
    )


@KernelRPCRegistry.register(
    "admin.metric.detail",
    summary="读取指标查询方式和维度",
    description="使用 search 返回的 metric_id；保留默认条件，返回基础 PromQL 查询模板，不猜测不支持的查询语法。",
    params_schema={
        "type": "object",
        "required": [*SCOPE, "metric_id"],
        "additionalProperties": False,
        "properties": {**SCOPE, "metric_id": {"type": "string"}},
    },
    example_params={**EXAMPLE_SCOPE, "metric_id": "bk_monitor.system.cpu.usage"},
)
def detail(params):
    params = _validated(DetailSerializer, params)
    items, _ = _metrics(params, [{"key": "metric_id", "value": [params["metric_id"]]}], 1, 1)
    if not items:
        raise CustomException(message="当前租户和业务下未找到指标", data={"code": "METRIC_NOT_FOUND"})
    metric = items[0]
    promql = metric.get("promql_metric")
    return _response(
        "metric.detail",
        params,
        {
            "metric": metric,
            "query_template": {
                "operation": "unify_query.query",
                "params": {**{key: params[key] for key in SCOPE}, "promql": promql, "step": 60, "parse_only": True},
                "required_params": ["start", "end"],
                "notes": "补充 Unix 秒时间范围；此为基础指标选择器，按 default_condition 和维度值添加筛选。预览后设置 parse_only=false 执行。",
            }
            if promql
            else None,
            "dimension_values_template": {
                "operation": "metric.dimension_values",
                "params": {**{key: params[key] for key in SCOPE}, "match": [promql], "page": 1, "page_size": 20},
                "required_params": ["label", "start", "end"],
            }
            if promql
            else None,
        },
    )


@KernelRPCRegistry.register(
    "admin.metric.dimension_values",
    summary="查询指标维度值",
    description="复用 UQ label values，显式时间范围；上游无分页，Admin 对返回值分页，total 仅为上游返回数量。异常不转为空值。",
    params_schema={
        "type": "object",
        "required": [*SCOPE, "match", "label", "start", "end"],
        "additionalProperties": False,
        "properties": {
            **SCOPE,
            **PAGING,
            "match": {"type": "array", "minItems": 1, "maxItems": 20, "items": {"type": "string"}},
            "label": {"type": "string"},
            "start": {"type": "integer", "minimum": 0},
            "end": {"type": "integer", "minimum": 0},
        },
    },
    example_params={
        **EXAMPLE_SCOPE,
        "match": ["bkmonitor:system:cpu:usage"],
        "label": "bk_target_ip",
        "start": 1790100000,
        "end": 1790103600,
        "page": 1,
        "page_size": 20,
    },
)
def dimension_values(params):
    params = _validated(DimensionValuesSerializer, params)
    result = MetricLabelValuesResource()(
        bk_tenant_id=params["bk_tenant_id"],
        bk_biz_ids=[params["bk_biz_id"]],
        match=params["match"],
        label=params["label"],
        start=str(params["start"]),
        end=str(params["end"]),
    )
    values = result["values"].get(params["label"], [])
    offset = (params["page"] - 1) * params["page_size"]
    return _response(
        "metric.dimension_values",
        params,
        {
            "items": values[offset : offset + params["page_size"]],
            "total": len(values),
            "page": params["page"],
            "page_size": params["page_size"],
            "trace_id": result.get("trace_id"),
        },
    )
