"""Admin 统一查询只读入口；复用平台 Resource 的业务路由和租户上下文。"""

from django.conf import settings
from rest_framework import serializers

from core.drf_resource import api
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.common import build_response

FUNC_QUERY = "admin.unify_query.query"


class QuerySerializer(serializers.Serializer):
    bk_tenant_id = serializers.CharField(max_length=128)
    bk_biz_id = serializers.IntegerField(min_value=1, default=lambda: settings.DEFAULT_BK_BIZ_ID)
    promql = serializers.CharField(max_length=65536)
    start = serializers.IntegerField(min_value=0)
    end = serializers.IntegerField(min_value=0)
    step = serializers.IntegerField(min_value=1)

    def validate(self, attrs):
        if attrs["bk_tenant_id"] == "__all__":
            raise serializers.ValidationError("请选择具体租户")
        if attrs["end"] < attrs["start"]:
            raise serializers.ValidationError("结束时间不能早于开始时间")
        return attrs


@KernelRPCRegistry.register(
    FUNC_QUERY,
    summary="Admin unify-query PromQL 范围查询",
    description="只读查询；缺省业务使用目标环境 DEFAULT_BK_BIZ_ID，复用统一查询 Resource，不接受 URL 或 Header。",
    params_schema={
        "type": "object",
        "required": ["bk_tenant_id", "promql", "start", "end", "step"],
        "properties": {
            "bk_tenant_id": {"type": "string", "minLength": 1},
            "bk_biz_id": {"type": "integer", "minimum": 1, "description": "缺省使用 DEFAULT_BK_BIZ_ID"},
            "promql": {"type": "string", "minLength": 1, "maxLength": 65536},
            "start": {"type": "integer", "minimum": 0, "description": "Unix 秒"},
            "end": {"type": "integer", "minimum": 0, "description": "Unix 秒"},
            "step": {"type": "integer", "minimum": 1, "description": "采样步长，秒"},
        },
        "additionalProperties": False,
    },
    example_params={
        "bk_tenant_id": "system",
        "bk_biz_id": 2,
        "promql": 'sum(rate(bkmonitor:transfer_pipeline_frontend_handled_total{id="50010"}[5m]))',
        "start": 1790100000,
        "end": 1790103600,
        "step": 60,
    },
)
def query(params):
    serializer = QuerySerializer(data=params)
    serializer.is_valid(raise_exception=True)
    validated = serializer.validated_data
    result = api.unify_query.query_data_by_promql(
        bk_tenant_id=validated["bk_tenant_id"],
        bk_biz_ids=[str(validated["bk_biz_id"])],
        promql=validated["promql"],
        start=str(validated["start"]),
        end=str(validated["end"]),
        step=f"{validated['step']}s",
    )
    return build_response(
        operation="unify_query.query",
        func_name=FUNC_QUERY,
        bk_tenant_id=validated["bk_tenant_id"],
        data={
            "source": {
                "bk_tenant_id": validated["bk_tenant_id"],
                "bk_biz_id": validated["bk_biz_id"],
            },
            "result": result,
        },
    )
