"""日志采集相关的自定义上报和第三方 ES 创建资源。"""

from collections.abc import Mapping

from rest_framework import serializers

from bkm_space.utils import bk_biz_id_to_space_uid
from core.drf_resource import Resource, api


class StrictCreateSerializer(serializers.Serializer):
    """拒绝未声明字段，避免 MCP 创建接口静默丢弃参数。"""

    def to_internal_value(self, data):
        if isinstance(data, Mapping):
            unknown_fields = set(data) - set(self.fields)
            if unknown_fields:
                raise serializers.ValidationError(
                    {field: ["This field is not supported by this MCP create API."] for field in sorted(unknown_fields)}
                )
        return super().to_internal_value(data)


class CreateCustomReportResource(Resource):
    """创建自定义上报采集项，并可将新索引集加入指定索引组。"""

    class RequestSerializer(StrictCreateSerializer):
        bk_biz_id = serializers.IntegerField(required=True, min_value=1, label="业务ID")
        collector_config_name = serializers.CharField(required=True, max_length=50, label="采集项名称")
        collector_config_name_en = serializers.RegexField(
            required=True, min_length=5, max_length=50, regex=r"^[A-Za-z0-9_]+$", label="采集项英文名"
        )
        custom_type = serializers.ChoiceField(
            required=True, choices=["log", "otlp_trace", "otlp_log"], label="自定义上报类型"
        )
        data_link_id = serializers.CharField(required=False, allow_blank=True, allow_null=True, label="数据链路ID")
        category_id = serializers.CharField(required=False, max_length=64, label="分类ID")
        description = serializers.CharField(
            required=False, allow_blank=True, allow_null=True, max_length=64, label="描述"
        )
        etl_config = serializers.CharField(required=False, label="清洗类型")
        etl_params = serializers.DictField(required=False, label="清洗参数")
        fields = serializers.ListField(child=serializers.DictField(), required=False, label="清洗字段")
        storage_cluster_id = serializers.IntegerField(required=False, min_value=1, label="存储集群ID")
        storage_cluster_type = serializers.CharField(required=False, label="存储集群类型")
        retention = serializers.IntegerField(required=False, min_value=1, label="保留天数")
        allocation_min_days = serializers.IntegerField(required=False, min_value=0, label="冷热数据生效天数")
        storage_replies = serializers.IntegerField(required=False, min_value=0, label="ES副本数")
        es_shards = serializers.IntegerField(required=False, min_value=1, label="ES分片数")
        is_display = serializers.BooleanField(required=False, default=True, label="是否展示")
        owners = serializers.ListField(
            child=serializers.CharField(max_length=64), required=False, default=list, label="授权用户列表"
        )
        sort_fields = serializers.ListField(required=False, default=list, label="排序字段")
        target_fields = serializers.ListField(required=False, default=list, label="定位字段")
        ignore_exists = serializers.BooleanField(required=False, default=False, label="是否忽略已存在")
        parent_index_set_ids = serializers.ListField(
            child=serializers.IntegerField(min_value=1),
            required=False,
            allow_null=True,
            label="归属索引组ID列表",
        )
        confirm = serializers.BooleanField(required=True, label="确认执行创建")

        def validate_confirm(self, value: bool) -> bool:
            if not value:
                raise serializers.ValidationError("写操作必须由用户确认，请设置 confirm=true")
            return value

    def perform_request(self, validated_request_data):
        request_data = dict(validated_request_data)
        request_data.pop("confirm")
        result = api.log_search.create_custom_report(enforce_permission=True, **request_data) or {}
        return {
            "collector_config_id": result.get("collector_config_id"),
            "index_set_id": result.get("index_set_id"),
            "bk_data_id": result.get("bk_data_id"),
            "bk_data_token": result.get("bk_data_token"),
            "created": result.get("created", True),
            "parent_index_set_ids": request_data.get("parent_index_set_ids"),
        }


class ThirdPartyESIndexSerializer(serializers.Serializer):
    result_table_id = serializers.CharField(required=True, max_length=255, label="第三方索引名")
    bk_biz_id = serializers.IntegerField(required=False, allow_null=True, default=None, label="索引所属业务ID")
    time_field = serializers.CharField(required=False, allow_blank=False, label="时间字段")
    time_field_type = serializers.ChoiceField(required=False, choices=["date", "long"], label="时间字段类型")
    time_field_unit = serializers.ChoiceField(
        required=False, allow_null=True, choices=["second", "millisecond", "microsecond"], label="时间字段单位"
    )
    storage_cluster_id = serializers.IntegerField(required=False, min_value=1, label="索引存储集群ID")


class CreateThirdPartyESResource(Resource):
    """创建第三方 ES 索引集，并可将其加入指定索引组。"""

    class RequestSerializer(StrictCreateSerializer):
        bk_biz_id = serializers.IntegerField(required=True, min_value=1, label="业务ID")
        index_set_name = serializers.CharField(required=True, max_length=64, label="索引集名称")
        storage_cluster_id = serializers.IntegerField(required=True, min_value=1, label="存储集群ID")
        indexes = ThirdPartyESIndexSerializer(many=True, required=True, allow_empty=False, label="第三方索引列表")
        time_field = serializers.CharField(required=True, allow_blank=False, label="时间字段")
        time_field_type = serializers.ChoiceField(
            required=False, default="date", choices=["date", "long"], label="时间字段类型"
        )
        time_field_unit = serializers.ChoiceField(
            required=False, allow_null=True, choices=["second", "millisecond", "microsecond"], label="时间字段单位"
        )
        category_id = serializers.CharField(required=False, max_length=64, label="分类ID")
        is_trace_log = serializers.BooleanField(required=False, default=False, label="是否 Trace 日志")
        is_editable = serializers.BooleanField(required=False, default=True, label="是否可编辑")
        target_fields = serializers.ListField(required=False, default=list, label="定位字段")
        sort_fields = serializers.ListField(required=False, default=list, label="排序字段")
        parent_index_set_ids = serializers.ListField(
            child=serializers.IntegerField(min_value=1),
            required=False,
            allow_null=True,
            label="归属索引组ID列表",
        )
        confirm = serializers.BooleanField(required=True, label="确认执行创建")

        def validate_confirm(self, value: bool) -> bool:
            if not value:
                raise serializers.ValidationError("写操作必须由用户确认，请设置 confirm=true")
            return value

        def validate(self, attrs):
            if attrs.get("time_field_type") == "long" and not attrs.get("time_field_unit"):
                raise serializers.ValidationError({"time_field_unit": "long 类型必须指定时间单位。"})
            return attrs

    def perform_request(self, validated_request_data):
        request_data = dict(validated_request_data)
        request_data.pop("confirm")
        request_data.update(
            {
                "space_uid": bk_biz_id_to_space_uid(request_data.pop("bk_biz_id")),
                "scenario_id": "es",
                "enforce_permission": True,
            }
        )
        result = api.log_search.create_index_set(**request_data) or {}
        return {
            "index_set_id": result.get("index_set_id"),
            "index_set_name": result.get("index_set_name") or validated_request_data["index_set_name"],
            "scenario_id": result.get("scenario_id") or "es",
            "space_uid": result.get("space_uid") or request_data["space_uid"],
            "storage_cluster_id": result.get("storage_cluster_id") or validated_request_data["storage_cluster_id"],
            "parent_index_set_ids": request_data.get("parent_index_set_ids"),
        }
