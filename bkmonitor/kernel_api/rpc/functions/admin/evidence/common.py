from functools import wraps

from rest_framework import serializers
from rest_framework.schemas.openapi import AutoSchema

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.common import build_response, paginate_queryset
from kernel_api.rpc.functions.admin.space import _apply_space_bk_biz_id_filter


class TenantPage(serializers.Serializer):
    bk_tenant_id = serializers.CharField()
    page = serializers.IntegerField(min_value=1, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, default=20)

    def validate_bk_tenant_id(self, value):
        if value == "__all__":
            raise serializers.ValidationError("请选择具体租户")
        return value


class BusinessPage(TenantPage):
    bk_biz_id = serializers.IntegerField()


def business_scope(p):
    from metadata.models import Space

    if not _apply_space_bk_biz_id_filter(Space.objects.filter(bk_tenant_id=p["bk_tenant_id"]), p["bk_biz_id"]).exists():
        raise CustomException(message="指定业务不属于当前租户")


def query(name, title, params_class, example=None, *, safety="read"):
    """将同一个参数定义用于 RPC 发现和请求解析。处理函数返回本页记录、匹配总数。"""

    def register(handler):
        @wraps(handler)
        def call(params):
            serializer = params_class(data=params)
            unknown = params.keys() - serializer.fields.keys()
            if unknown:
                raise CustomException(message="不支持的查询参数：" + ", ".join(sorted(unknown)))
            serializer.is_valid(raise_exception=True)
            p = serializer.validated_data
            items, total = handler(p)
            return build_response(
                operation=name,
                func_name="admin." + name,
                safety_level=safety,
                bk_tenant_id=p["bk_tenant_id"],
                data={"items": items, "total": total, "page": p["page"], "page_size": p["page_size"]},
            )

        fields = params_class()
        sample = {"bk_tenant_id": "system", "page": 1, "page_size": 20}
        if "bk_biz_id" in fields.fields:
            sample["bk_biz_id"] = 2
        KernelRPCRegistry.register_function(
            func_name="admin." + name,
            handler=call,
            summary=title,
            description=title,
            params_schema={**AutoSchema().map_serializer(fields), "additionalProperties": False},
            example_params={**sample, **(example or {})},
        )
        return call

    return register


def db_page(rows, p):
    return paginate_queryset(rows, page=p["page"], page_size=p["page_size"])


def list_page(rows, p):
    start = (p["page"] - 1) * p["page_size"]
    return rows[start : start + p["page_size"]], len(rows)
