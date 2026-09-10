"""日志采集接入 MCP 资源。"""

import json
from collections.abc import Mapping
from typing import Any

from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from bkm_space.utils import bk_biz_id_to_space_uid
from core.drf_resource import Resource, api
from kernel_api.resource.log_collection_common import normalize_json_list, normalize_json_object

ENVIRONMENT_LINUX = "linux"
ENVIRONMENT_WINDOWS = "windows"
ENVIRONMENT_CONTAINER = "container"
ENVIRONMENT_UNKNOWN = "unknown"
VALID_ENVIRONMENTS = {
    ENVIRONMENT_LINUX,
    ENVIRONMENT_WINDOWS,
    ENVIRONMENT_CONTAINER,
}
WINDOWS_COLLECTOR_SCENARIO = "wineventlog"
LINUX_COLLECTOR_SCENARIOS = {"row", "section"}
CUSTOM_COLLECTOR_SCENARIO = "custom"
CUSTOM_CONTAINER_TYPE = "log"
# 与 bklog/apps/log_databus/constants.py 的 LOG_COLLECTOR_ORDERING_CHOICES 保持同步；
# MCP 故意排除高耗时的 daily_usage / total_usage 排序。
LOG_COLLECTOR_ORDERING_CHOICES = (
    "name",
    "-name",
    "retention",
    "-retention",
    "updated_at",
    "-updated_at",
    "created_at",
    "-created_at",
)
# 与 bklog/apps/log_search/constants.py 的 LogAccessTypeEnum 保持同步。
LOG_ACCESS_TYPE_CHOICES = (
    "linux",
    "winevent",
    "container_file",
    "container_stdout",
    "bkdata",
    "es",
    "custom_report",
)
# 与 bklog/apps/log_databus/handlers/collector_handler/log.py::get_log_collectors 保持同步。
LOG_COLLECTOR_CONDITION_CHOICES = (
    "scenario_id",
    "name",
    "bk_data_name",
    "name_en",
    "bk_data_id",
    "collector_scenario_id",
    "created_by",
    "updated_by",
    "status",
    "storage_display_name",
    "log_access_type",
    "tags",
    "collector_source",
    "query",
)
SENSITIVE_KEYWORDS = (
    "password",
    "passwd",
    "secret",
    "token",
    "credential",
    "authorization",
    "api_key",
    "access_key",
    "private_key",
    "cookie",
)
CONTAINER_CONFIG_FIELDS = {
    "id",
    "collector_type",
    "namespaces",
    "namespaces_exclude",
    "any_namespace",
    "workload_type",
    "workload_name",
    "container_name",
    "container_name_exclude",
    "match_labels",
    "match_expressions",
    "match_annotations",
    "all_container",
    "data_encoding",
    "params",
    "status",
    "status_detail",
}


class JSONListField(serializers.JSONField):
    """接受 GET 查询参数中的 JSON 数组，也兼容资源内部传入的原生数组。"""

    def to_internal_value(self, data):
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                raise serializers.ValidationError("必须是合法的 JSON 数组。")
        return super().to_internal_value(data)


def normalize_environment(collector: dict[str, Any]) -> str:
    """兼容存量采集项 environment 为空的情况。"""
    collector_scenario_id = collector.get("collector_scenario_id")
    if collector_scenario_id == CUSTOM_COLLECTOR_SCENARIO and collector.get("custom_type") == CUSTOM_CONTAINER_TYPE:
        return ENVIRONMENT_CONTAINER

    environment = collector.get("environment")
    if environment in VALID_ENVIRONMENTS:
        return environment

    if collector_scenario_id == WINDOWS_COLLECTOR_SCENARIO:
        return ENVIRONMENT_WINDOWS
    if collector_scenario_id in LINUX_COLLECTOR_SCENARIOS:
        return ENVIRONMENT_LINUX
    return ENVIRONMENT_UNKNOWN


def mask_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "******"
            if any(keyword in str(key).lower() for keyword in SENSITIVE_KEYWORDS)
            else mask_sensitive(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [mask_sensitive(item) for item in value]
    return value


def normalize_collection_params(value: Any) -> dict[str, Any]:
    params = normalize_json_object(value)
    if "kafka_ssl_params" in params:
        params = params.copy()
        params["kafka_ssl_params"] = normalize_json_object(params["kafka_ssl_params"])
    return mask_sensitive(params)


def normalize_container_configs(value: Any) -> list[dict[str, Any]]:
    configs = []
    for config in normalize_json_list(value):
        if not isinstance(config, dict):
            continue
        normalized = {key: config[key] for key in CONTAINER_CONFIG_FIELDS if key in config}
        if "params" in normalized:
            normalized["params"] = normalize_collection_params(normalized["params"])
        configs.append(mask_sensitive(normalized))
    return configs


def normalize_index_set(collector: dict[str, Any]) -> dict[str, Any]:
    is_search = collector.get("is_search")
    return {
        "index_set_id": collector.get("index_set_id"),
        "table_id_prefix": collector.get("table_id_prefix") or "",
        "table_id": collector.get("table_id") or "",
        # 列表接口会补齐精确可检索状态，详情原始接口未补齐时返回 unknown，
        # 避免把“未返回”误报为不可检索。
        "is_searchable": bool(is_search) if is_search is not None else None,
        "bkdata_index_set_ids": normalize_json_list(collector.get("bkdata_index_set_ids")),
    }


def get_log_access_type(collector: dict[str, Any]) -> str:
    """返回新版采集列表中的统一接入类型，兼容旧版字段。"""
    log_access_type = collector.get("log_access_type")
    if log_access_type:
        return log_access_type
    if collector.get("scenario_id") in {"bkdata", "es"}:
        return collector["scenario_id"]
    if collector.get("environment") == ENVIRONMENT_CONTAINER:
        if collector.get("container_collector_type") in {"container_log_config", "node_log_config"}:
            return "container_file"
        if collector.get("container_collector_type") == "std_log_config":
            return "container_stdout"
    collector_scenario_id = collector.get("collector_scenario_id")
    if collector_scenario_id == CUSTOM_COLLECTOR_SCENARIO:
        return "custom_report"
    if collector_scenario_id in LINUX_COLLECTOR_SCENARIOS:
        return "linux"
    if collector_scenario_id == WINDOWS_COLLECTOR_SCENARIO:
        return "winevent"
    return ""


def normalize_collector_detail(collector: dict[str, Any]) -> dict[str, Any]:
    is_active = bool(collector.get("is_active"))
    collector_scenario_id = collector.get("collector_scenario_id") or collector.get("scenario_id") or ""
    collector_scenario_name = collector.get("collector_scenario_name") or collector.get("scenario_name") or ""
    parent_index_sets = collector.get("parent_index_sets") or []
    result = {
        "collector_config_id": collector.get("collector_config_id") or None,
        "collector_config_name": collector.get("collector_config_name")
        or collector.get("name")
        or collector.get("index_set_name")
        or "",
        "bk_biz_id": collector.get("bk_biz_id"),
        "environment": normalize_environment(collector),
        "collector_scenario": {
            "id": collector_scenario_id,
            "name": collector_scenario_name,
        },
        "status": "enabled" if is_active else "disabled",
        "is_active": is_active,
        "bk_data_id": collector.get("bk_data_id"),
        "subscription_id": collector.get("subscription_id"),
        "index_set": normalize_index_set(collector),
        "log_access_type": get_log_access_type(collector),
        "parent_index_sets": parent_index_sets,
        "created_at": collector.get("created_at"),
        "updated_at": collector.get("updated_at"),
    }
    result.update(
        {
            "description": collector.get("description") or "",
            "log_access_type": get_log_access_type(collector),
            "category": {
                "id": collector.get("category_id") or "",
                "name": collector.get("category_name") or "",
            },
            "target": {
                "object_type": collector.get("target_object_type") or "",
                "node_type": collector.get("target_node_type") or "",
                "nodes": normalize_json_list(collector.get("target_nodes")),
                "bcs_cluster_id": collector.get("bcs_cluster_id"),
            },
            "collection_config": {
                "data_encoding": collector.get("data_encoding") or "",
                "params": normalize_collection_params(collector.get("params")),
                "configs": normalize_container_configs(collector.get("configs")),
            },
            "clean_config": {
                "etl_config": collector.get("etl_config") or "",
                "etl_params": normalize_json_object(collector.get("etl_params")),
                "fields": normalize_json_list(collector.get("fields")),
            },
            "storage": {
                "cluster_id": collector.get("storage_cluster_id"),
                "cluster_name": collector.get("storage_cluster_name") or "",
                "display_name": collector.get("storage_display_name") or "",
                "cluster_type": collector.get("storage_cluster_type") or "",
                "retention": collector.get("retention"),
                "allocation_min_days": collector.get("allocation_min_days"),
                "storage_replies": collector.get("storage_replies"),
                "es_shards": collector.get("storage_shards_nums"),
            },
        }
    )
    return result


class ListLogCollectorsResource(Resource):
    """分页查询指定业务的日志采集项。"""

    class RequestSerializer(serializers.Serializer):
        class ConditionSerializer(serializers.Serializer):
            key = serializers.ChoiceField(required=True, choices=LOG_COLLECTOR_CONDITION_CHOICES, label="过滤字段")
            value = serializers.ListField(required=True, allow_empty=False, label="过滤值列表")

        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        page = serializers.IntegerField(required=False, default=1, min_value=1, label="页码")
        page_size = serializers.IntegerField(required=False, default=20, min_value=1, max_value=100, label="每页数量")
        keyword = serializers.CharField(
            required=False, default="", allow_blank=True, allow_null=True, label="搜索关键字"
        )
        collector_scenario_id = serializers.CharField(required=False, label="采集场景")
        log_access_type = serializers.ListField(
            child=serializers.ChoiceField(choices=LOG_ACCESS_TYPE_CHOICES),
            required=False,
            allow_empty=False,
            label="日志接入类型",
        )
        ordering = serializers.ChoiceField(
            required=False,
            default="-updated_at",
            choices=LOG_COLLECTOR_ORDERING_CHOICES,
            label="排序方式",
        )
        conditions = JSONListField(required=False, label="高级过滤条件")

        def validate_conditions(self, value):
            if not isinstance(value, list):
                raise serializers.ValidationError("conditions 必须是由 {key, value} 组成的列表。")
            serializer = self.ConditionSerializer(data=value, many=True)
            serializer.is_valid(raise_exception=True)
            return serializer.validated_data

        def validate(self, attrs):
            condition_keys = {condition["key"] for condition in attrs.get("conditions", [])}
            shortcut_condition_keys = {
                "collector_scenario_id": "collector_scenario_id",
                "log_access_type": "log_access_type",
            }
            conflict_keys = {
                shortcut
                for shortcut, condition_key in shortcut_condition_keys.items()
                if shortcut in attrs and condition_key in condition_keys
            }
            if conflict_keys:
                raise serializers.ValidationError(
                    {"conditions": f"请勿同时通过 conditions 和快捷参数过滤 {', '.join(sorted(conflict_keys))}。"}
                )
            return attrs

    def perform_request(self, validated_request_data):
        conditions = list(validated_request_data.get("conditions", []))
        if "collector_scenario_id" in validated_request_data:
            conditions.append(
                {"key": "collector_scenario_id", "value": [validated_request_data["collector_scenario_id"]]}
            )
        if validated_request_data.get("log_access_type"):
            conditions.append({"key": "log_access_type", "value": validated_request_data["log_access_type"]})
        params = {
            "space_uid": bk_biz_id_to_space_uid(validated_request_data["bk_biz_id"]),
            "page": validated_request_data["page"],
            "pagesize": validated_request_data["page_size"],
            "keyword": validated_request_data.get("keyword") or "",
            "ordering": validated_request_data.get("ordering", "-updated_at"),
            "conditions": conditions,
        }
        # 新版接口已完成混合采集项/索引集的字段整合和实例权限计算；不得再次裁剪。
        return api.log_search.log_access_collector(**params)


class GetLogCollectorResource(Resource):
    """查询指定业务中的日志采集项详情。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        collector_config_id = serializers.IntegerField(required=True, min_value=1, label="采集项ID")

    def perform_request(self, validated_request_data):
        collector = api.log_search.data_bus_collectors(
            collector_config_id=validated_request_data["collector_config_id"],
            enforce_permission=True,
        )
        if str(collector.get("bk_biz_id")) != str(validated_request_data["bk_biz_id"]):
            raise PermissionDenied("Collector config does not belong to the requested business.")
        return normalize_collector_detail(collector)


class GetLogIndexSetResource(Resource):
    """查询指定业务中的独立索引集详情。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        index_set_id = serializers.IntegerField(required=True, min_value=1, label="索引集ID")

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        index_set_id = validated_request_data["index_set_id"]

        # 详情接口只按 index_set_id 查询，使用新版详情返回的 space_uid 校验业务归属，
        # 同时保持返回结果不做字段裁剪，避免丢失更新所需的完整 indexes 等字段。
        result = api.log_search.get_index_set(index_set_id=index_set_id)
        detail = result
        if isinstance(detail, Mapping) and isinstance(detail.get("data"), Mapping):
            detail = detail["data"]
        expected_space_uid = bk_biz_id_to_space_uid(bk_biz_id)
        if not isinstance(detail, Mapping) or detail.get("space_uid") != expected_space_uid:
            raise PermissionDenied("Index set does not belong to the requested business.")
        return detail
