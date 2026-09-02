"""日志采集接入 MCP 资源。"""

import math
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
    if collector.get("collector_scenario_id") == CUSTOM_COLLECTOR_SCENARIO:
        return "custom_report"
    return ""


def normalize_collector_summary(collector: dict[str, Any], default_bk_biz_id: int | None = None) -> dict[str, Any]:
    is_active = bool(collector.get("is_active"))
    collector_scenario_id = collector.get("collector_scenario_id") or collector.get("scenario_id") or ""
    collector_scenario_name = collector.get("collector_scenario_name") or collector.get("scenario_name") or ""
    parent_index_sets = collector.get("parent_index_sets") or []
    return {
        "collector_config_id": collector.get("collector_config_id") or None,
        "collector_config_name": collector.get("collector_config_name")
        or collector.get("name")
        or collector.get("index_set_name")
        or "",
        "bk_biz_id": collector.get("bk_biz_id") or default_bk_biz_id,
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


def normalize_collector_detail(collector: dict[str, Any]) -> dict[str, Any]:
    result = normalize_collector_summary(collector)
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
            },
        }
    )
    return result


class ListLogCollectorsResource(Resource):
    """分页查询指定业务的日志采集项。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        page = serializers.IntegerField(required=False, default=1, min_value=1, label="页码")
        page_size = serializers.IntegerField(required=False, default=20, min_value=1, max_value=100, label="每页数量")
        keyword = serializers.CharField(
            required=False, default="", allow_blank=True, allow_null=True, label="搜索关键字"
        )
        collector_scenario_id = serializers.CharField(required=False, label="采集场景")
        log_access_type = serializers.ListField(
            child=serializers.ChoiceField(
                choices=["linux", "winevent", "container_file", "container_stdout", "bkdata", "es", "custom_report"]
            ),
            required=False,
            allow_empty=False,
            label="日志接入类型",
        )

    def perform_request(self, validated_request_data):
        conditions = []
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
            "ordering": "-updated_at",
            "conditions": conditions,
        }
        response = api.log_search.log_access_collector(**params)
        total = int(response.get("total") or 0)
        items = response.get("list") or []

        page_size = validated_request_data["page_size"]
        return {
            "page": validated_request_data["page"],
            "page_size": page_size,
            "total": total,
            "total_pages": math.ceil(total / page_size) if total else 0,
            "items": [
                normalize_collector_summary(item, default_bk_biz_id=validated_request_data["bk_biz_id"])
                for item in items
            ],
        }


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
        return result
