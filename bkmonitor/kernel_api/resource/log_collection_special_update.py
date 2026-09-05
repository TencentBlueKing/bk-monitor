"""日志采集相关的自定义上报、第三方 ES 和 bkdata 更新资源。"""

from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError

from bkm_space.utils import bk_biz_id_to_space_uid
from core.drf_resource import Resource, api
from kernel_api.resource.log_collection import get_log_access_type
from kernel_api.resource.log_collection_common import StrictMCPSerializer
from kernel_api.resource.log_collection_discovery import ensure_storage_clusters_visible
from kernel_api.resource.log_collection_special_create import (
    BkDataIndexSerializer,
    ThirdPartyESIndexSerializer,
    fill_index_business_ids,
)


class StrictUpdateSerializer(StrictMCPSerializer):
    unsupported_api_name = "MCP update API"


def ensure_collector_belongs_to_biz(collector: dict, bk_biz_id: int) -> None:
    if str(collector.get("bk_biz_id")) != str(bk_biz_id):
        raise PermissionDenied("Collector config does not belong to the requested business.")


def ensure_custom_report(collector: dict) -> None:
    if get_log_access_type(collector) != "custom_report":
        raise ValidationError("The collector config is not a custom-report collector.")


def get_index_set_for_business(index_set_id: int, bk_biz_id: int) -> dict:
    """从无缓存详情接口读取索引集，并校验其空间归属。"""
    index_set = api.log_search.get_index_set(index_set_id=index_set_id)
    if index_set.get("space_uid") != bk_biz_id_to_space_uid(bk_biz_id):
        raise PermissionDenied("Index set does not belong to the requested business.")
    return index_set


class UpdateCustomReportResource(Resource):
    """更新自定义上报采集项。"""

    class RequestSerializer(StrictUpdateSerializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        collector_config_id = serializers.IntegerField(required=True, min_value=1, label="采集项ID")
        collector_config_name = serializers.CharField(required=True, max_length=50, label="采集项名称")
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
        is_display = serializers.BooleanField(required=False, label="是否展示")
        owners = serializers.ListField(child=serializers.CharField(max_length=64), required=False, label="授权用户列表")
        sort_fields = serializers.ListField(required=False, allow_empty=True, label="排序字段")
        target_fields = serializers.ListField(required=False, allow_empty=True, label="定位字段")
        parent_index_set_ids = serializers.ListField(
            child=serializers.IntegerField(min_value=1),
            required=False,
            allow_null=True,
            label="归属索引组ID列表",
        )
        confirm = serializers.BooleanField(required=True, label="确认执行更新")

        def validate_confirm(self, value: bool) -> bool:
            if not value:
                raise serializers.ValidationError("写操作必须由用户确认，请设置 confirm=true")
            return value

    def perform_request(self, validated_request_data):
        request_data = dict(validated_request_data)
        request_data.pop("confirm")
        bk_biz_id = request_data.pop("bk_biz_id")
        collector_config_id = request_data.pop("collector_config_id")

        collector = api.log_search.data_bus_collectors(
            collector_config_id=collector_config_id,
            enforce_permission=True,
        )
        ensure_collector_belongs_to_biz(collector, bk_biz_id)
        ensure_custom_report(collector)

        result = api.log_search.update_custom_report(
            collector_config_id=collector_config_id,
            enforce_permission=True,
            **request_data,
        )
        return {
            "collector_config_id": collector_config_id,
            "updated": result if isinstance(result, bool) else True,
        }


class UpdateThirdPartyESResource(Resource):
    """更新第三方 ES 索引集。"""

    class RequestSerializer(StrictUpdateSerializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        index_set_id = serializers.IntegerField(required=True, min_value=1, label="索引集ID")
        index_set_name = serializers.CharField(required=True, max_length=64, label="索引集名称")
        storage_cluster_id = serializers.IntegerField(required=True, min_value=1, label="存储集群ID")
        indexes = serializers.ListField(
            child=ThirdPartyESIndexSerializer(), required=True, allow_empty=False, label="第三方索引列表"
        )
        time_field = serializers.CharField(required=True, allow_blank=False, label="时间字段")
        time_field_type = serializers.ChoiceField(required=True, choices=["date", "long"], label="时间字段类型")
        time_field_unit = serializers.ChoiceField(
            required=True, allow_null=True, choices=["second", "millisecond", "microsecond"], label="时间字段单位"
        )
        category_id = serializers.CharField(required=True, max_length=64, label="分类ID")
        is_trace_log = serializers.BooleanField(required=True, label="是否 Trace 日志")
        target_fields = serializers.ListField(required=True, allow_empty=True, label="定位字段")
        sort_fields = serializers.ListField(required=True, allow_empty=True, label="排序字段")
        parent_index_set_ids = serializers.ListField(
            child=serializers.IntegerField(min_value=1),
            required=False,
            allow_null=True,
            label="归属索引组ID列表",
        )
        confirm = serializers.BooleanField(required=True, label="确认执行更新")

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
        bk_biz_id = request_data.pop("bk_biz_id")
        index_set_id = request_data.pop("index_set_id")

        index_set = get_index_set_for_business(index_set_id, bk_biz_id)
        if get_log_access_type(index_set) != "es":
            raise ValidationError("The index set is not a third-party ES index set.")

        ensure_storage_clusters_visible(
            bk_biz_id,
            {request_data["storage_cluster_id"]}
            | {index["storage_cluster_id"] for index in request_data["indexes"] if index.get("storage_cluster_id")},
        )
        request_data["indexes"] = fill_index_business_ids(request_data["indexes"], bk_biz_id)
        request_data.update(
            {
                "space_uid": bk_biz_id_to_space_uid(bk_biz_id),
                "scenario_id": "es",
            }
        )
        return api.log_search.update_index_set(index_set_id=index_set_id, enforce_permission=True, **request_data)


class UpdateBkDataResource(Resource):
    """更新计算平台 bkdata 索引集。"""

    class RequestSerializer(StrictUpdateSerializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        index_set_id = serializers.IntegerField(required=True, min_value=1, label="索引集ID")
        index_set_name = serializers.CharField(required=True, max_length=64, label="索引集名称")
        indexes = serializers.ListField(
            child=BkDataIndexSerializer(), required=True, allow_empty=False, label="数据平台结果表列表"
        )
        time_field = serializers.CharField(required=True, allow_blank=False, label="时间字段")
        time_field_type = serializers.ChoiceField(required=True, choices=["date", "long"], label="时间字段类型")
        time_field_unit = serializers.ChoiceField(
            required=True, allow_null=True, choices=["second", "millisecond", "microsecond"], label="时间字段单位"
        )
        category_id = serializers.CharField(required=True, max_length=64, label="分类ID")
        is_trace_log = serializers.BooleanField(required=True, label="是否 Trace 日志")
        target_fields = serializers.ListField(required=True, allow_empty=True, label="定位字段")
        sort_fields = serializers.ListField(required=True, allow_empty=True, label="排序字段")
        parent_index_set_ids = serializers.ListField(
            child=serializers.IntegerField(min_value=1),
            required=False,
            allow_null=True,
            label="归属索引组ID列表",
        )
        confirm = serializers.BooleanField(required=True, label="确认执行更新")

        def validate_confirm(self, value: bool) -> bool:
            if not value:
                raise serializers.ValidationError("写操作必须由用户确认，请设置 confirm=true")
            return value

        def validate(self, attrs):
            bk_biz_id = attrs["bk_biz_id"]
            invalid_biz_ids = {
                index["bk_biz_id"]
                for index in attrs["indexes"]
                if index.get("bk_biz_id") is not None and index["bk_biz_id"] != bk_biz_id
            }
            if invalid_biz_ids:
                raise serializers.ValidationError(
                    {"indexes": f"bkdata 索引所属业务必须与 bk_biz_id={bk_biz_id} 一致。"}
                )
            return attrs

    def perform_request(self, validated_request_data):
        request_data = dict(validated_request_data)
        request_data.pop("confirm")
        bk_biz_id = request_data.pop("bk_biz_id")
        index_set_id = request_data.pop("index_set_id")

        index_set = get_index_set_for_business(index_set_id, bk_biz_id)
        if get_log_access_type(index_set) != "bkdata":
            raise ValidationError("The index set is not a bkdata index set.")

        request_data["indexes"] = fill_index_business_ids(request_data["indexes"], bk_biz_id)
        request_data.update(
            {
                "space_uid": bk_biz_id_to_space_uid(bk_biz_id),
                "scenario_id": "bkdata",
            }
        )
        return api.log_search.update_index_set(index_set_id=index_set_id, enforce_permission=True, **request_data)
