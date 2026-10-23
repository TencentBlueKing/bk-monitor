"""业务场景存储查询的内部批量接口。资源引用由已鉴权的 SaaS 生成。"""

from rest_framework import serializers

from bkmonitor.utils.serializers import TenantIdField
from bkmonitor.views.resource_storage import QueryResourceStorageSerializer, SCENE_DATA_TYPES
from core.drf_resource import Resource
from metadata.service.resource_storage import ResourceStorageQuery


class ResourceStorageReferenceSerializer(serializers.Serializer):
    scene = serializers.ChoiceField(choices=tuple(SCENE_DATA_TYPES))
    resource_id = serializers.CharField()
    resource_name = serializers.CharField(allow_blank=True)
    resource_status = serializers.CharField(allow_blank=True)
    data_type = serializers.CharField()
    bk_data_id = serializers.IntegerField(min_value=1, allow_null=True, required=False)
    data_name = serializers.CharField(allow_blank=True, required=False)
    table_id = serializers.CharField(allow_blank=True, required=False)
    expand_tables = serializers.BooleanField(default=False)
    is_builtin = serializers.BooleanField(default=False)
    error = serializers.CharField(required=False)


class QueryResourceStorageResource(Resource):
    """批量查询业务资源引用对应的结果表及存储关联。"""

    class RequestSerializer(QueryResourceStorageSerializer):
        bk_tenant_id = TenantIdField()
        resources = ResourceStorageReferenceSerializer(many=True, default=list)

    def perform_request(self, validated_request_data):
        return ResourceStorageQuery(validated_request_data["bk_tenant_id"], validated_request_data["bk_biz_id"]).query(
            **validated_request_data
        )
