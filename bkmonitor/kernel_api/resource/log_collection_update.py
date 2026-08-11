"""日志采集 Fast Update MCP 资源。"""

from typing import Any

from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from core.drf_resource import Resource, api

COMMON_UPDATE_FIELDS = {
    "collector_config_name",
    "description",
}
HOST_UPDATE_FIELDS = COMMON_UPDATE_FIELDS | {
    "target_object_type",
    "target_node_type",
    "target_nodes",
    "params",
    "data_encoding",
}
CONTAINER_UPDATE_FIELDS = COMMON_UPDATE_FIELDS | {
    "collector_scenario_id",
    "configs",
    "add_pod_label",
    "add_pod_annotation",
    "extra_labels",
    "yaml_config_enabled",
    "yaml_config",
}
REQUEST_SCOPE_FIELDS = {"bk_biz_id", "collector_config_id"}


def normalize_task_ids(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        values = value.split(",")
    elif isinstance(value, (list, tuple, set)):
        values = value
    else:
        values = [value]
    return [str(item).strip() for item in values if str(item).strip()]


class StrictFastUpdateSerializer(serializers.Serializer):
    """拒绝未声明字段，避免 MCP 静默忽略环境、清洗或存储参数。"""

    def to_internal_value(self, data):
        unknown_fields = set(data.keys()) - set(self.fields)
        if unknown_fields:
            raise serializers.ValidationError(
                {field: ["This field is not supported by Fast Update MCP."] for field in sorted(unknown_fields)}
            )
        return super().to_internal_value(data)


class FastUpdateLogCollectorResource(Resource):
    """只更新采集配置，不修改清洗、字段和存储配置。"""

    class RequestSerializer(StrictFastUpdateSerializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        collector_config_id = serializers.IntegerField(required=True, label="采集项ID")
        collector_config_name = serializers.CharField(required=False, max_length=50, label="采集项名称")
        description = serializers.CharField(
            required=False, allow_blank=True, allow_null=True, max_length=100, label="描述"
        )
        target_object_type = serializers.CharField(required=False, label="目标类型")
        target_node_type = serializers.CharField(required=False, label="节点类型")
        target_nodes = serializers.ListField(child=serializers.DictField(), required=False, label="目标节点")
        params = serializers.DictField(required=False, label="主机采集参数")
        data_encoding = serializers.CharField(required=False, label="日志字符集")
        collector_scenario_id = serializers.CharField(required=False, label="容器日志类型")
        configs = serializers.ListField(
            child=serializers.DictField(), required=False, allow_empty=False, label="完整容器日志配置"
        )
        add_pod_label = serializers.BooleanField(required=False, label="是否添加 Pod 标签")
        add_pod_annotation = serializers.BooleanField(required=False, label="是否添加 Pod 注解")
        extra_labels = serializers.ListField(child=serializers.DictField(), required=False, label="额外标签")
        yaml_config_enabled = serializers.BooleanField(required=False, label="是否使用 YAML 配置")
        yaml_config = serializers.CharField(required=False, allow_blank=True, label="YAML 配置内容")

        def validate(self, attrs):
            attrs = super().validate(attrs)
            if not set(attrs) - REQUEST_SCOPE_FIELDS:
                raise serializers.ValidationError("At least one collection field must be provided.")
            return attrs

    def perform_request(self, validated_request_data):
        request_data = validated_request_data.copy()
        bk_biz_id = request_data.pop("bk_biz_id")
        collector_config_id = request_data.pop("collector_config_id")

        collector = api.log_search.data_bus_collectors(collector_config_id=collector_config_id)
        if str(collector.get("bk_biz_id")) != str(bk_biz_id):
            raise PermissionDenied("Collector config does not belong to the requested business.")

        environment = str(collector.get("environment") or "").lower()
        if environment == "container":
            allowed_fields = CONTAINER_UPDATE_FIELDS
        else:
            if environment not in {"linux", "windows"}:
                environment = "windows" if collector.get("collector_scenario_id") == "wineventlog" else "linux"
            allowed_fields = HOST_UPDATE_FIELDS

        invalid_fields = set(request_data) - allowed_fields
        if invalid_fields:
            raise serializers.ValidationError(
                {
                    field: [f"This field cannot be updated for a {environment} collector."]
                    for field in sorted(invalid_fields)
                }
            )
        if environment in {"linux", "windows"} and len(request_data.get("description") or "") > 64:
            raise serializers.ValidationError({"description": "Host collector description cannot exceed 64 characters."})
        if environment == "container" and "description" in request_data and request_data["description"] is None:
            raise serializers.ValidationError({"description": "Container collector description cannot be null."})

        update_result = (
            api.log_search.fast_update_log_collector(
                collector_config_id=collector_config_id,
                update_clean_config=False,
                **request_data,
            )
            or {}
        )

        if "subscription_id" not in update_result or "task_id_list" not in update_result:
            latest_collector = api.log_search.data_bus_collectors(collector_config_id=collector_config_id)
        else:
            latest_collector = {}

        subscription_id = update_result.get("subscription_id", latest_collector.get("subscription_id"))
        task_id_list = update_result.get("task_id_list", latest_collector.get("task_id_list"))
        return {
            "collector_config_id": collector_config_id,
            "environment": environment,
            "subscription_id": subscription_id,
            "task_ids": normalize_task_ids(task_id_list),
            "updated_fields": sorted(request_data),
            "clean_config_updated": False,
        }
