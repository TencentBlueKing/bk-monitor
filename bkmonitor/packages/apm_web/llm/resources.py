from collections import defaultdict
from math import ceil, pi, sin
from typing import Any

from opentelemetry.semconv.resource import ResourceAttributes
from rest_framework import serializers

from constants.apm import OtlpKey
from constants.otel_query import OperatorEnum
from core.drf_resource import Resource, api

from apm_web.llm.adapter import adapt_spans
from apm_web.llm.query import get_query
from apm_web.metric.resources import CalculateByRangeResource as MetricCalculateByRangeResource
from apm_web.models import Application
from apm_web.strategy.dispatch.entity import EntitySet
from bkmonitor.utils.time_tools import parse_time_compare_abbreviation

AGENT_CANDIDATE_QUERY = (
    "_exists_:attributes.gen_ai.span.kind "
    "OR _exists_:attributes.gen_ai.operation.name "
    "OR _exists_:attributes.agent.info.id "
    "OR _exists_:attributes.agent.info.name "
    "OR _exists_:attributes.langfuse.observation.type"
)

MOCK_TIME_SERIES_GROUP_BY_FIELDS = {"gen_ai.operation.name", "gen_ai.response.model"}
MOCK_TIME_SERIES_MAX_POINTS = 60
MOCK_TIME_SERIES_MODELS = ["hunyuan-turbo", "deepseek-r1", "qwen3-32b"]
MOCK_TIME_SERIES_OPERATIONS = ["invoke_agent", "chat", "execute_tool", "retrieval"]
MOCK_TIME_SERIES_CAL_TYPES = (
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "cache_tokens",
    "request_count",
    "model_call_count",
    "duration",
    "operation_count",
)


class ListTracesResource(Resource):
    """按指定字段折叠查询 Agent Trace。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        app_name = serializers.CharField(required=True, label="应用名称")
        start_time = serializers.IntegerField(required=True, label="开始时间")
        end_time = serializers.IntegerField(required=True, label="结束时间")
        group_field = serializers.CharField(required=False, default=OtlpKey.TRACE_ID, label="分组字段")
        service_name = serializers.CharField(required=False, allow_blank=True, default="", label="服务名称")
        keyword = serializers.CharField(required=False, allow_blank=True, default="", label="关键词")
        offset = serializers.IntegerField(required=False, min_value=0, default=0, label="分页偏移")
        limit = serializers.IntegerField(required=False, min_value=1, max_value=100, default=20, label="分页大小")

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
    def _preview_root(spans: list[dict[str, Any]]) -> dict[str, Any]:
        for span in spans:
            attributes = span.get(OtlpKey.ATTRIBUTES)
            operation = attributes.get("gen_ai.operation.name") if isinstance(attributes, dict) else None
            if isinstance(operation, str) and operation.lower() in {"invoke_agent", "invoke_workflow"}:
                return span

        span_ids = {span_id for span in spans if (span_id := span.get(OtlpKey.SPAN_ID))}
        return next(
            (
                span
                for span in spans
                if not (parent_span_id := span.get(OtlpKey.PARENT_SPAN_ID)) or parent_span_id not in span_ids
            ),
            {},
        )

    @staticmethod
    def _last_message_text(span: dict[str, Any], attribute: str, expected_role: str) -> str:
        attributes = span.get(OtlpKey.ATTRIBUTES)
        messages = attributes.get(attribute) if isinstance(attributes, dict) else None
        if not isinstance(messages, list):
            return ""

        for message in reversed(messages):
            if not isinstance(message, dict) or message.get("role") != expected_role:
                continue
            parts = message.get("parts")
            if not isinstance(parts, list):
                return ""
            texts = [
                content
                for part in parts
                if isinstance(part, dict)
                and part.get("type") == "text"
                and isinstance((content := part.get("content", part.get("text"))), str)
                and content.strip()
            ]
            return " ".join(texts)
        return ""

    @classmethod
    def _trace_item(cls, trace_id: str, raw_spans: list[dict[str, Any]], entity_set: EntitySet) -> dict[str, Any]:
        converted_spans = adapt_spans(raw_spans, entity_set)
        converted_attributes = [
            attributes for span in converted_spans if isinstance((attributes := span.get(OtlpKey.ATTRIBUTES)), dict)
        ]
        preview_root = cls._preview_root(converted_spans)
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
            "input": cls._last_message_text(preview_root, "gen_ai.input.messages", "user"),
            "output": cls._last_message_text(preview_root, "gen_ai.output.messages", "assistant"),
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
        trace_group_map: dict[str, str],
        raw_spans: list[dict[str, Any]],
        entity_set: EntitySet,
    ) -> list[dict[str, Any]]:
        spans_by_group: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
        for span in raw_spans:
            trace_id = cls._span_field_value(span, OtlpKey.TRACE_ID)
            group_id = trace_group_map.get(trace_id, "")
            if group_id and trace_id:
                spans_by_group[group_id][trace_id].append(span)

        items: list[dict[str, Any]] = []
        for group_id in group_ids:
            childs = [
                cls._trace_item(trace_id, spans, entity_set) for trace_id, spans in spans_by_group[group_id].items()
            ]
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
        filters = []
        if service_name := validated_request_data["service_name"]:
            filters.append(
                {
                    "key": OtlpKey.get_resource_key(ResourceAttributes.SERVICE_NAME),
                    "operator": OperatorEnum.EQUAL["operator"],
                    "value": [service_name],
                }
            )
        if keyword := validated_request_data["keyword"]:
            filters.append({"key": "keyword", "operator": "logic", "value": [keyword]})

        application = Application.objects.get(
            bk_biz_id=validated_request_data["bk_biz_id"],
            app_name=validated_request_data["app_name"],
        )
        span_query = get_query(application.build_data_sources())
        group_ids = span_query.query_group_list(
            start_time=validated_request_data["start_time"],
            end_time=validated_request_data["end_time"],
            group_field=validated_request_data["group_field"],
            offset=validated_request_data["offset"],
            limit=validated_request_data["limit"],
            filters=filters,
            query_string=AGENT_CANDIDATE_QUERY,
        )
        result = {
            "offset": validated_request_data["offset"],
            "limit": validated_request_data["limit"],
            "items": [],
        }
        if not group_ids:
            return result

        group_trace_records = span_query.query_group_trace_list(
            group_field=validated_request_data["group_field"],
            group_ids=group_ids,
        )
        trace_group_map = {
            record[OtlpKey.TRACE_ID]: record[validated_request_data["group_field"]] for record in group_trace_records
        }
        if not trace_group_map:
            return result

        spans = span_query.query_by_group_ids(
            group_field=OtlpKey.TRACE_ID,
            group_ids=list(trace_group_map),
        )
        entity_set: EntitySet = EntitySet(
            bk_biz_id=validated_request_data["bk_biz_id"],
            app_name=validated_request_data["app_name"],
        )
        result["items"] = self._group_spans(
            validated_request_data["group_field"],
            group_ids,
            trace_group_map,
            spans,
            entity_set,
        )
        return result


class ListSpansResource(Resource):
    """根据 Trace ID 或 Span ID 查询 Span 列表。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        app_name = serializers.CharField(required=True, label="应用名称")
        trace_id = serializers.CharField(required=False, allow_blank=True, default="", label="trace_id")
        span_id = serializers.CharField(required=False, allow_blank=True, default="", label="span_id")

        def validate(self, attrs):
            if not attrs["trace_id"] and not attrs["span_id"]:
                raise serializers.ValidationError("trace_id 和 span_id 至少传一个")
            return attrs

    def perform_request(self, validated_request_data):
        trace_id = validated_request_data["trace_id"]
        span_id = validated_request_data["span_id"]
        filters = []
        if trace_id:
            filters.append(
                {
                    "key": OtlpKey.TRACE_ID,
                    "operator": OperatorEnum.EQUAL["operator"],
                    "value": [trace_id],
                }
            )
        if span_id:
            filters.append(
                {
                    "key": OtlpKey.SPAN_ID,
                    "operator": OperatorEnum.EQUAL["operator"],
                    "value": [span_id],
                }
            )
        params = {
            "bk_biz_id": validated_request_data["bk_biz_id"],
            "app_name": validated_request_data["app_name"],
            "filters": filters,
            "limit": 10000,
            "exclude_field": ["bk_app_code"],
        }
        response = api.apm_api.query_span_list(params)
        raw_spans = response["data"]
        entity_set: EntitySet = EntitySet(
            bk_biz_id=validated_request_data["bk_biz_id"],
            app_name=validated_request_data["app_name"],
        )
        spans = adapt_spans(raw_spans, entity_set)
        return {
            "trace_id": trace_id or (raw_spans[0].get(OtlpKey.TRACE_ID, "") if raw_spans else ""),
            "total": len(spans),
            "spans": spans,
        }


class ListFlowsResource(Resource):
    """按会话或 Trace 查询层级 Span。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        app_name = serializers.CharField(required=True, label="应用名称")
        group_field = serializers.CharField(required=True, label="分组字段")
        group_id = serializers.CharField(required=True, label="分组值")

    @staticmethod
    def _build_flow(
        raw_spans: list[dict[str, Any]],
        spans: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        nodes = [{**span, "childs": []} for span in spans]
        nodes_by_span_id = {node[OtlpKey.SPAN_ID]: node for node in nodes if node.get(OtlpKey.SPAN_ID)}
        raw_spans_by_span_id = {span[OtlpKey.SPAN_ID]: span for span in raw_spans if span.get(OtlpKey.SPAN_ID)}
        raw_children_by_parent_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
        raw_roots = []
        for span in raw_spans:
            span_id = span.get(OtlpKey.SPAN_ID)
            parent_span_id = span.get(OtlpKey.PARENT_SPAN_ID)
            if parent_span_id and parent_span_id in raw_spans_by_span_id and parent_span_id != span_id:
                raw_children_by_parent_id[parent_span_id].append(span)
            else:
                raw_roots.append(span)

        roots = []

        def project(span: dict[str, Any], parent: dict[str, Any] | None) -> None:
            node = nodes_by_span_id.get(span.get(OtlpKey.SPAN_ID))
            if node is not None:
                if parent is None:
                    roots.append(node)
                else:
                    parent["childs"].append(node)
                parent = node

            for child in raw_children_by_parent_id.get(span.get(OtlpKey.SPAN_ID), []):
                project(child, parent)

        for raw_root in raw_roots:
            project(raw_root, None)

        return roots

    def perform_request(self, validated_request_data):
        application = Application.objects.get(
            bk_biz_id=validated_request_data["bk_biz_id"],
            app_name=validated_request_data["app_name"],
        )
        span_query = get_query(application.build_data_sources())
        group_field = validated_request_data["group_field"]
        group_id = validated_request_data["group_id"]
        group_trace_records = span_query.query_group_trace_list(
            group_field=group_field,
            group_ids=[group_id],
        )
        trace_ids = list(
            dict.fromkeys(record[OtlpKey.TRACE_ID] for record in group_trace_records if record.get(OtlpKey.TRACE_ID))
        )
        result = {
            "group_field": group_field,
            "group_id": group_id,
            "traces": [],
        }
        if not trace_ids:
            return result

        spans = span_query.query_by_group_ids(
            group_field=OtlpKey.TRACE_ID,
            group_ids=trace_ids,
        )
        spans_by_trace: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for span in spans:
            if trace_id := span.get(OtlpKey.TRACE_ID):
                spans_by_trace[trace_id].append(span)

        for trace_id in trace_ids:
            raw_trace_spans = spans_by_trace[trace_id]
            result["traces"].append(
                {
                    "trace_id": trace_id,
                    "flow": self._build_flow(raw_trace_spans, adapt_spans(raw_trace_spans)),
                }
            )
        return result


class TimeSeriesResource(Resource):
    """临时 LLM 指标时序 mock 接口。

    只按传入时域生成稳定的假数据，用于前端先行联调；后续会替换为基于 LLMQuery 的真实查询。
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        app_name = serializers.CharField(required=True, label="应用名称")
        service_name = serializers.CharField(required=False, allow_blank=True, default="", label="服务名称")
        start_time = serializers.IntegerField(required=True, label="开始时间")
        end_time = serializers.IntegerField(required=True, label="结束时间")
        cal_type = serializers.ChoiceField(
            required=True,
            choices=MOCK_TIME_SERIES_CAL_TYPES,
            label="指标类型",
        )
        group_by = serializers.ListField(
            required=False,
            default=list,
            child=serializers.CharField(),
            label="聚合字段",
        )

        def validate(self, attrs):
            if attrs["start_time"] >= attrs["end_time"]:
                raise serializers.ValidationError("start_time 必须小于 end_time")

            if len(attrs["group_by"]) > 1:
                raise serializers.ValidationError("暂不支持多字段聚合")

            unsupported_group_by = set(attrs["group_by"]) - MOCK_TIME_SERIES_GROUP_BY_FIELDS
            if unsupported_group_by:
                raise serializers.ValidationError(f"暂不支持按 {sorted(unsupported_group_by)} 聚合")
            return attrs

    @staticmethod
    def _auto_interval(start_time: int, end_time: int) -> int:
        raw_interval = max(60, ceil((end_time - start_time) / 30))
        for interval in (60, 300, 600, 1800, 3600, 21600, 86400):
            if raw_interval <= interval:
                return interval
        return 86400

    @staticmethod
    def _mock_value(cal_type: str, point_index: int, series_index: int, point_count: int) -> int:
        progress = point_index / max(1, point_count - 1)
        wave = sin(progress * pi)
        ripple = sin(progress * pi * 3 + series_index * 0.7) * 0.16

        if cal_type == "input_tokens":
            return max(0, int(2600 + series_index * 760 + wave * 2500 + ripple * 800))
        if cal_type == "output_tokens":
            return max(0, int(980 + series_index * 280 + wave * 980 + ripple * 320))
        if cal_type == "total_tokens":
            return TimeSeriesResource._mock_value("input_tokens", point_index, series_index, point_count) + (
                TimeSeriesResource._mock_value("output_tokens", point_index, series_index, point_count)
            )
        if cal_type == "cache_tokens":
            return max(0, int(420 + series_index * 120 + wave * 520 + ripple * 150))
        if cal_type == "request_count":
            return max(0, int(36 + series_index * 9 + wave * 42 + ripple * 12))
        if cal_type == "model_call_count":
            return max(0, int(110 + series_index * 28 + wave * 125 + ripple * 38))
        if cal_type == "operation_count":
            return max(0, int(140 + series_index * 35 + wave * 160 + ripple * 45))
        return max(0, int(820000 + series_index * 210000 + wave * 520000 + ripple * 130000))

    @staticmethod
    def _dimensions(group_by: list[str]) -> list[dict[str, str]]:
        if not group_by:
            return [{}]
        if group_by == ["gen_ai.response.model"]:
            return [{"gen_ai.response.model": model} for model in MOCK_TIME_SERIES_MODELS]
        if group_by == ["gen_ai.operation.name"]:
            return [{"gen_ai.operation.name": operation} for operation in MOCK_TIME_SERIES_OPERATIONS]
        return [{}]

    def perform_request(self, validated_request_data):
        start_time = validated_request_data["start_time"]
        end_time = validated_request_data["end_time"]
        interval = max(
            self._auto_interval(start_time, end_time),
            ceil((end_time - start_time) / (MOCK_TIME_SERIES_MAX_POINTS - 1)),
        )
        timestamps = list(range(start_time, end_time + 1, interval))
        if timestamps[-1] != end_time:
            timestamps.append(end_time)

        cal_type = validated_request_data["cal_type"]
        series = []
        point_count = len(timestamps)
        for series_index, dimensions in enumerate(self._dimensions(validated_request_data["group_by"])):
            datapoints = [
                [self._mock_value(cal_type, point_index, series_index, point_count), timestamp * 1000]
                for point_index, timestamp in enumerate(timestamps)
            ]
            series_item = {"datapoints": datapoints}
            if dimensions:
                series_item["target"] = next(iter(dimensions.values()))
                series_item["dimensions"] = dimensions
            series.append(series_item)

        return {
            "series": series,
            "mock": True,
        }


class CalculateByRangeResource(MetricCalculateByRangeResource):
    """临时 LLM 指标区间聚合 mock 接口。"""

    class RequestSerializer(serializers.Serializer):
        ZERO_TIME_SHIFT = "0s"

        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        app_name = serializers.CharField(required=True, label="应用名称")
        service_name = serializers.CharField(required=False, allow_blank=True, default="", label="服务名称")
        start_time = serializers.IntegerField(required=True, label="开始时间")
        end_time = serializers.IntegerField(required=True, label="结束时间")
        cal_type = serializers.ChoiceField(
            required=True,
            choices=MOCK_TIME_SERIES_CAL_TYPES,
            label="指标类型",
        )
        group_by = serializers.ListField(
            required=False,
            default=list,
            child=serializers.CharField(),
            label="聚合字段",
        )
        baseline = serializers.CharField(required=False, default=ZERO_TIME_SHIFT, label="对比基准")
        time_shifts = serializers.ListField(
            required=False,
            default=list,
            child=serializers.CharField(),
            label="时间偏移",
        )

        def validate(self, attrs):
            if attrs["start_time"] >= attrs["end_time"]:
                raise serializers.ValidationError("start_time 必须小于 end_time")

            if len(attrs["group_by"]) > 1:
                raise serializers.ValidationError("暂不支持多字段聚合")

            unsupported_group_by = set(attrs["group_by"]) - MOCK_TIME_SERIES_GROUP_BY_FIELDS
            if unsupported_group_by:
                raise serializers.ValidationError(f"暂不支持按 {sorted(unsupported_group_by)} 聚合")

            attrs["time_shifts"] = list(dict.fromkeys([*attrs["time_shifts"], self.ZERO_TIME_SHIFT]))
            if len(attrs["time_shifts"]) > 3:
                raise serializers.ValidationError("最多支持两次时间对比")
            if attrs["baseline"] not in attrs["time_shifts"]:
                raise serializers.ValidationError("baseline 必须包含在 time_shifts 中")
            return attrs

    @staticmethod
    def _range_value(cal_type: str, start_time: int, end_time: int, series_index: int) -> int:
        minutes = max(1, ceil((end_time - start_time) / 60))

        if cal_type == "input_tokens":
            base = minutes * (1180 + series_index * 360) + (start_time // 60 % 17) * 95
            return int(base)
        if cal_type == "output_tokens":
            base = minutes * (430 + series_index * 130) + (start_time // 60 % 11) * 42
            return int(base)
        if cal_type == "total_tokens":
            return CalculateByRangeResource._range_value(
                "input_tokens", start_time, end_time, series_index
            ) + CalculateByRangeResource._range_value("output_tokens", start_time, end_time, series_index)
        if cal_type == "cache_tokens":
            base = minutes * (160 + series_index * 48) + (start_time // 60 % 7) * 21
            return int(base)
        if cal_type == "request_count":
            base = minutes * (17 + series_index * 4) + (start_time // 60 % 23)
            return int(base)
        if cal_type == "model_call_count":
            base = minutes * (34 + series_index * 8) + (start_time // 60 % 7) * 2
            return int(base)
        if cal_type == "operation_count":
            base = minutes * (43 + series_index * 13) + (start_time // 60 % 29) * 3
            return int(base)

        base = 830000 + series_index * 230000 + min(minutes, 180) * 1600 + (start_time // 60 % 13) * 4200
        return int(base)

    def perform_request(self, validated_request_data):
        cal_type = validated_request_data["cal_type"]
        group_by = validated_request_data["group_by"]
        aliases = validated_request_data["time_shifts"]

        records: list[dict[str, Any]] = []
        for series_index, dimensions in enumerate(TimeSeriesResource._dimensions(group_by)):
            record: dict[str, Any] = {"dimensions": dimensions}
            for alias in aliases:
                time_offset = parse_time_compare_abbreviation(alias)
                record[alias] = self._range_value(
                    cal_type,
                    validated_request_data["start_time"] + time_offset,
                    validated_request_data["end_time"] + time_offset,
                    series_index,
                )
            records.append(record)

        self._process_growth_rates(validated_request_data["baseline"], aliases, records)

        return {"total": len(records), "data": records}
