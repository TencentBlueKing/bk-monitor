"""日志采集清洗配置修改 MCP 资源。"""

import json
from collections.abc import Mapping
from typing import Any

from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError

from bkmonitor.utils.request import get_request_username
from core.drf_resource import Resource, api

SUPPORTED_ETL_CONFIGS = (
    "bk_log_text",
    "bk_log_json",
    "bk_log_delimiter",
    "bk_log_regexp",
)


class StrictSerializer(serializers.Serializer):
    """拒绝未声明字段，避免 MCP 把模板或其它配置静默传入底层。"""

    def to_internal_value(self, data):
        if isinstance(data, Mapping):
            unknown_fields = set(data) - set(self.fields)
            if unknown_fields:
                raise serializers.ValidationError(
                    {field: ["This field is not supported by clean config MCP."] for field in sorted(unknown_fields)}
                )
        return super().to_internal_value(data)


class CleanMetadataSerializer(StrictSerializer):
    field_name = serializers.CharField(required=True, label="元数据字段名")
    value = serializers.CharField(required=True, allow_blank=True, allow_null=True, label="元数据字段值")
    metadata_type = serializers.ChoiceField(required=True, choices=["path"], label="元数据类型")


class ExtJsonConfigSerializer(StrictSerializer):
    expand_depth = serializers.ChoiceField(required=False, allow_null=True, choices=[1, 2, 3], label="动态解析层级")


class CleanEtlParamsSerializer(StrictSerializer):
    separator_regexp = serializers.CharField(required=False, allow_blank=True, allow_null=True, label="正则表达式")
    is_grok = serializers.BooleanField(required=False, label="是否使用 Grok")
    separator = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        trim_whitespace=False,
        label="分隔符",
    )
    retain_original_text = serializers.BooleanField(required=False, label="是否保留原文")
    original_text_is_case_sensitive = serializers.BooleanField(required=False, label="原文是否大小写敏感")
    original_text_tokenize_on_chars = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        trim_whitespace=False,
        label="原文自定义分词符",
    )
    retain_extra_json = serializers.BooleanField(required=False, label="是否保留未定义 JSON 字段")
    ext_json_config = ExtJsonConfigSerializer(required=False, label="未定义 JSON 字段解析配置")
    enable_retain_content = serializers.BooleanField(required=False, label="是否保留清洗失败日志")
    record_parse_failure = serializers.BooleanField(required=False, label="是否记录清洗失败标记")
    path_regexp = serializers.CharField(required=False, allow_blank=True, allow_null=True, label="路径分割正则")
    metadata_fields = CleanMetadataSerializer(many=True, required=False, label="元数据字段")


class CleanFieldSerializer(StrictSerializer):
    field_index = serializers.IntegerField(required=False, allow_null=True, label="字段顺序")
    field_name = serializers.CharField(required=False, allow_blank=True, allow_null=True, label="字段名")
    alias_name = serializers.CharField(required=False, allow_blank=True, allow_null=True, label="字段别名")
    field_type = serializers.CharField(required=False, allow_blank=True, allow_null=True, label="字段类型")
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True, label="字段说明")
    is_analyzed = serializers.BooleanField(required=False, label="是否分词")
    is_dimension = serializers.BooleanField(required=False, label="是否维度")
    is_time = serializers.BooleanField(required=False, label="是否时间字段")
    is_delete = serializers.BooleanField(required=True, label="是否删除")
    is_built_in = serializers.BooleanField(required=False, label="是否内置字段")
    option = serializers.DictField(required=False, label="字段选项")
    is_case_sensitive = serializers.BooleanField(required=False, label="是否大小写敏感")
    tokenize_on_chars = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        trim_whitespace=False,
        label="自定义分词符",
    )
    value = serializers.JSONField(required=False, allow_null=True, label="字段样例值")


def normalize_json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def normalize_json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def build_clean_config_readback(collector: dict[str, Any]) -> dict[str, Any]:
    return {
        "collector_config_id": collector.get("collector_config_id"),
        "bk_biz_id": collector.get("bk_biz_id"),
        "clean_config": {
            "etl_config": collector.get("etl_config") or "",
            "etl_params": normalize_json_object(collector.get("etl_params")),
            "fields": normalize_json_list(collector.get("fields")),
        },
        "storage": {
            "storage_cluster_id": collector.get("storage_cluster_id"),
            "storage_cluster_name": collector.get("storage_cluster_name") or "",
            "storage_display_name": collector.get("storage_display_name") or "",
            "storage_cluster_type": collector.get("storage_cluster_type") or "",
            "retention": collector.get("retention"),
            "allocation_min_days": collector.get("allocation_min_days"),
            "storage_replies": collector.get("storage_replies"),
            "es_shards": collector.get("storage_shards_nums"),
        },
        "index_set": {
            "index_set_id": collector.get("index_set_id"),
            "table_id_prefix": collector.get("table_id_prefix") or "",
            "table_id": collector.get("table_id") or "",
            "sort_fields": normalize_json_list(collector.get("sort_fields")),
            "target_fields": normalize_json_list(collector.get("target_fields")),
        },
    }


class UpdateLogCollectorCleanConfigResource(Resource):
    """完整更新单个采集项的清洗、存储与索引集配置。"""

    class RequestSerializer(StrictSerializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        collector_config_id = serializers.IntegerField(required=True, min_value=1, label="采集项ID")
        table_id = serializers.CharField(required=True, allow_blank=False, max_length=128, label="结果表ID")
        etl_config = serializers.ChoiceField(required=True, choices=SUPPORTED_ETL_CONFIGS, label="清洗类型")
        etl_params = CleanEtlParamsSerializer(required=True, label="清洗参数")
        fields = CleanFieldSerializer(many=True, required=True, allow_empty=True, label="清洗字段完整列表")
        storage_cluster_id = serializers.IntegerField(required=True, min_value=1, label="存储集群ID")
        retention = serializers.IntegerField(required=True, min_value=1, label="保留天数")
        allocation_min_days = serializers.IntegerField(required=True, min_value=0, label="冷热数据生效天数")
        storage_replies = serializers.IntegerField(required=True, min_value=0, label="ES副本数量")
        es_shards = serializers.IntegerField(required=True, min_value=1, label="ES分片数量")
        confirm = serializers.BooleanField(required=True, label="确认执行高风险写操作")

        def validate_confirm(self, value: bool) -> bool:
            if not value:
                raise serializers.ValidationError("Clean config write requires explicit confirm=true.")
            return value

    @staticmethod
    def ensure_collector_belongs_to_biz(collector: dict[str, Any], bk_biz_id: int) -> None:
        if str(collector.get("bk_biz_id")) != str(bk_biz_id):
            raise PermissionDenied("Collector config does not belong to the requested business.")

    @staticmethod
    def ensure_table_id_matches_collector(collector: dict[str, Any], table_id: str) -> None:
        expected_table_id = collector.get("table_id") or collector.get("collector_config_name_en")
        if expected_table_id and str(expected_table_id) != table_id:
            raise ValidationError(
                {"table_id": "table_id must match the collector result table; this tool cannot rename it."}
            )

    def perform_request(self, validated_request_data):
        request_data = dict(validated_request_data)
        request_data.pop("confirm")
        bk_biz_id = request_data.pop("bk_biz_id")
        collector_config_id = request_data.pop("collector_config_id")

        username = get_request_username()
        if not username:
            raise PermissionDenied("Cannot resolve request username.")

        collector = api.log_search.data_bus_collectors(
            collector_config_id=collector_config_id,
            enforce_permission=True,
            bk_username=username,
        )
        self.ensure_collector_belongs_to_biz(collector, bk_biz_id)
        self.ensure_table_id_matches_collector(collector, request_data["table_id"])

        write_result = (
            api.log_search.update_log_collector_clean_config(
                collector_config_id=collector_config_id,
                enforce_permission=True,
                bk_username=username,
                **request_data,
            )
            or {}
        )
        latest_collector = api.log_search.data_bus_collectors(
            collector_config_id=collector_config_id,
            enforce_permission=True,
            bk_username=username,
        )
        self.ensure_collector_belongs_to_biz(latest_collector, bk_biz_id)

        return {
            "collector_config_id": collector_config_id,
            "bk_biz_id": bk_biz_id,
            "requested_by": username,
            "write_result": {
                key: write_result.get(key)
                for key in (
                    "etl_config",
                    "index_set_id",
                    "scenario_id",
                    "storage_cluster_id",
                    "retention",
                    "es_shards",
                )
                if key in write_result
            },
            "readback": build_clean_config_readback(latest_collector),
            "status_query": {
                "tool": "get_log_collector",
                "arguments": {
                    "bk_biz_id": bk_biz_id,
                    "collector_config_id": collector_config_id,
                },
                "retry_after_seconds": 5,
            },
        }
