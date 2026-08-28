from collections import defaultdict
from typing import Any

from opentelemetry.semconv.resource import ResourceAttributes
from rest_framework import serializers

from apm.core.handlers.query.proxy import QueryProxy
from apm.serializers import FilterSerializer
from constants.apm import OtlpKey
from constants.otel_query import OperatorEnum
from core.drf_resource import Resource, api

from apm_web.llm.adapter import adapt_spans


class ListTracesResource(Resource):
    """按指定字段折叠查询 Agent Trace。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        app_name = serializers.CharField(required=True, label="应用名称")
        start_time = serializers.IntegerField(required=True, label="开始时间")
        end_time = serializers.IntegerField(required=True, label="结束时间")
        group_field = serializers.CharField(required=False, default=OtlpKey.TRACE_ID, label="分组字段")
        filters = serializers.ListSerializer(child=FilterSerializer(), required=False, default=[], label="查询条件")
        service_name = serializers.CharField(required=False, allow_blank=True, default="", label="服务名称")
        offset = serializers.IntegerField(required=False, min_value=0, default=0, label="分页偏移")
        limit = serializers.IntegerField(required=False, min_value=1, default=20, label="分页大小")

        def validate(self, attrs):
            if attrs["start_time"] > attrs["end_time"]:
                raise serializers.ValidationError("start_time 不能大于 end_time")
            return attrs

    @staticmethod
    def _span_field_value(span: dict[str, Any], field: str) -> str:
        section, separator, name = field.partition(".")
        if separator and section in {OtlpKey.ATTRIBUTES, OtlpKey.RESOURCE}:
            values = span.get(section)
            value = values.get(name, "") if isinstance(values, dict) else ""
        else:
            value = span.get(field, "")
        if isinstance(value, list):
            return value[0] if value else ""
        return value

    @staticmethod
    def _message_text(spans: list[dict[str, Any]], attribute: str) -> str:
        for span in spans:
            attributes = span.get(OtlpKey.ATTRIBUTES)
            messages = attributes.get(attribute) if isinstance(attributes, dict) else None
            if not isinstance(messages, list):
                continue
            for message in reversed(messages):
                if not isinstance(message, dict):
                    continue
                parts = message.get("parts")
                if not isinstance(parts, list):
                    continue
                texts = [
                    content
                    for part in parts
                    if isinstance(part, dict)
                    and part.get("type") == "text"
                    and isinstance((content := part.get("content", part.get("text"))), str)
                    and content.strip()
                ]
                if texts:
                    return " ".join(texts)
        return ""

    @classmethod
    def _trace_item(cls, trace_id: str, raw_spans: list[dict[str, Any]]) -> dict[str, Any]:
        converted_spans = adapt_spans(raw_spans)
        converted_attributes = [
            attributes for span in converted_spans if isinstance((attributes := span.get(OtlpKey.ATTRIBUTES)), dict)
        ]
        root_span = next((span for span in raw_spans if not span.get(OtlpKey.PARENT_SPAN_ID)), {})
        start_time = root_span.get(OtlpKey.START_TIME, 0)
        end_time = root_span.get(OtlpKey.END_TIME, start_time)

        def attribute_values(attribute: str) -> list[Any]:
            return [attributes[attribute] for attributes in converted_attributes if attribute in attributes]

        def token_total(attribute: str) -> int:
            return sum(
                value for value in attribute_values(attribute) if isinstance(value, int) and not isinstance(value, bool)
            )

        user_id = next(
            (str(value) for value in attribute_values("user.id") if value not in (None, "")),
            "",
        )
        return {
            "group_id": trace_id,
            "group_field": OtlpKey.TRACE_ID,
            "trace_id": trace_id,
            "input": cls._message_text(converted_spans, "gen_ai.input.messages"),
            "output": cls._message_text(converted_spans[::-1], "gen_ai.output.messages"),
            "input_tokens": token_total("gen_ai.usage.input_tokens"),
            "output_tokens": token_total("gen_ai.usage.output_tokens"),
            "cache_read_input_tokens": token_total("gen_ai.usage.cache_read.input_tokens"),
            "cache_creation_input_tokens": token_total("gen_ai.usage.cache_creation.input_tokens"),
            "start_time": start_time,
            "elapsed_time": max(0, end_time - start_time),
            "user_id": user_id,
        }

    @classmethod
    def _group_spans(
        cls,
        group_field: str,
        group_ids: list[str],
        raw_spans: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        spans_by_group: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
        for span in raw_spans:
            group_id = cls._span_field_value(span, group_field)
            trace_id = cls._span_field_value(span, OtlpKey.TRACE_ID)
            if group_id and trace_id:
                spans_by_group[group_id][trace_id].append(span)

        items: list[dict[str, Any]] = []
        for group_id in group_ids:
            childs = [cls._trace_item(trace_id, spans) for trace_id, spans in spans_by_group[group_id].items()]
            if not childs:
                continue
            childs.sort(key=lambda child: child["start_time"])
            start_time = childs[0]["start_time"]
            end_time = max(child["start_time"] + child["elapsed_time"] for child in childs)
            items.append(
                {
                    "group_id": group_id,
                    "group_field": group_field,
                    "input": "",
                    "output": "",
                    "input_tokens": sum(child["input_tokens"] for child in childs),
                    "output_tokens": sum(child["output_tokens"] for child in childs),
                    "cache_read_input_tokens": sum(child["cache_read_input_tokens"] for child in childs),
                    "cache_creation_input_tokens": sum(child["cache_creation_input_tokens"] for child in childs),
                    "start_time": start_time,
                    "elapsed_time": max(0, end_time - start_time),
                    "user_id": next((child["user_id"] for child in childs if child["user_id"]), ""),
                    "childs": childs,
                }
            )

        if group_field == OtlpKey.TRACE_ID:
            for item in items:
                item.update(item.pop("childs")[0])
        return items

    def perform_request(self, validated_request_data):
        filters = list(validated_request_data["filters"])
        if service_name := validated_request_data["service_name"]:
            filters.append(
                {
                    "key": OtlpKey.get_resource_key(ResourceAttributes.SERVICE_NAME),
                    "operator": OperatorEnum.EQUAL["operator"],
                    "value": [service_name],
                }
            )

        span_query = QueryProxy(
            validated_request_data["bk_biz_id"],
            validated_request_data["app_name"],
        ).span_query
        group_ids = span_query.query_group_list(
            start_time=validated_request_data["start_time"],
            end_time=validated_request_data["end_time"],
            group_field=validated_request_data["group_field"],
            offset=validated_request_data["offset"],
            limit=validated_request_data["limit"],
            filters=filters,
        )
        result = {
            "offset": validated_request_data["offset"],
            "limit": validated_request_data["limit"],
            "items": [],
        }
        if not group_ids:
            return result

        spans = span_query.query_by_group_ids(
            group_field=validated_request_data["group_field"],
            group_ids=group_ids,
        )
        result["items"] = self._group_spans(
            validated_request_data["group_field"],
            group_ids,
            spans,
        )
        return result


class ListSpansResource(Resource):
    """查询指定 Trace 的 Span 列表。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        app_name = serializers.CharField(required=True, label="应用名称")
        trace_id = serializers.CharField(required=True, label="trace_id")

    def perform_request(self, validated_request_data):
        params = {
            "bk_biz_id": validated_request_data["bk_biz_id"],
            "app_name": validated_request_data["app_name"],
            "filters": [
                {
                    "key": OtlpKey.TRACE_ID,
                    "operator": OperatorEnum.EQUAL["operator"],
                    "value": [validated_request_data["trace_id"]],
                }
            ],
            "limit": 10000,
            "exclude_field": ["bk_app_code"],
        }
        response = api.apm_api.query_span_list(params)
        raw_spans = response["data"]
        spans = adapt_spans(raw_spans)
        return {
            "trace_id": validated_request_data["trace_id"],
            "total": len(spans),
            "spans": spans,
        }
