import json
from collections import defaultdict
from typing import Any

from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.trace import StatusCode
from rest_framework import serializers

from constants.apm import LLMProduct, OtlpKey
from constants.otel_query import OperatorEnum
from core.drf_resource import Resource, api

from apm_web.handlers.metric_group import GroupEnum, MetricGroupRegistry
from apm_web.handlers.trace_handler.query import QueryHandler, QueryStringBuilder, SpanQueryTransformer
from apm_web.llm.adapter import adapt_spans
from apm_web.llm.adapter.fields import AGENT_CANDIDATE_Q, resolve_product, resolve_query_field
from apm_web.llm.constants import CalculationType
from apm_web.llm.metric_group import LLMMetricGroup
from apm_web.llm.query import LLMQuery, get_query
from apm_web.metric.resources import CalculateByRangeResource as MetricCalculateByRangeResource
from apm_web.models import Application
from apm_web.strategy.dispatch.entity import EntitySet
from bkmonitor.data_source import get_auto_interval
from bkmonitor.utils.thread_backend import InheritParentThread, run_threads


class ListTracesResource(Resource):
    """按指定字段折叠查询 Agent Trace。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        app_name = serializers.CharField(required=True, label="应用名称")
        start_time = serializers.IntegerField(required=True, label="开始时间")
        end_time = serializers.IntegerField(required=True, label="结束时间")
        group_field = serializers.CharField(required=False, default=OtlpKey.TRACE_ID, label="分组字段")
        service_name = serializers.CharField(required=True, label="服务名称")
        keyword = serializers.CharField(required=False, allow_blank=True, default="", label="关键词")
        offset = serializers.IntegerField(required=False, min_value=0, default=0, label="分页偏移")
        limit = serializers.IntegerField(required=False, min_value=1, max_value=100, default=20, label="分页大小")

        def validate(self, attrs):
            if attrs["start_time"] > attrs["end_time"]:
                raise serializers.ValidationError("start_time 不能大于 end_time")
            return attrs

    _TEXT_PART_TYPES = {"", "text", "input_text", "output_text"}
    _OUTPUT_PREVIEW_KEYS = ("text", "reasoning", "tool_call", "tool_result")

    @staticmethod
    def _build_keyword_query(product: str, bk_biz_id: int, app_name: str, keyword: str) -> str:
        """构造关键词查询，避免 hex32 会话 ID 被误判为仅查询 Trace ID。"""
        if ":" not in keyword and (hex32 := QueryStringBuilder.extract_trace_id(keyword)):
            conversation_field = resolve_query_field(product, "attributes.gen_ai.conversation.id")
            fields = dict.fromkeys((OtlpKey.TRACE_ID, conversation_field))
            return " OR ".join(f'{field}: "{hex32}"' for field in fields)

        return QueryHandler.process_query_string(SpanQueryTransformer(bk_biz_id, app_name), keyword)

    @staticmethod
    def _span_field_value(span: dict[str, Any], field: str) -> Any:
        value = LLMQuery._get_field_value(span, field)
        if isinstance(value, list):
            return value[0] if value else ""
        return value

    @staticmethod
    def _preview_text(value: Any) -> str:
        if isinstance(value, str):
            return value.strip()
        if value in (None, "", [], {}):
            return ""
        try:
            return json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(value).strip()

    @classmethod
    def _part_preview(cls, part: dict[str, Any], expected: str) -> str:
        part_type = str(part.get("type") or "")
        if expected == "text" and part_type in cls._TEXT_PART_TYPES:
            return cls._preview_text(part.get("content", part.get("text")))
        if expected == "reasoning" and part_type in {"reasoning", "thinking"}:
            return cls._preview_text(part.get("content", part.get("text", part.get("thinking"))))
        if expected == "tool_call" and part_type == "tool_call":
            name = cls._preview_text(part.get("name"))
            arguments = cls._preview_text(part.get("arguments"))
            return " ".join(item for item in (name, arguments) if item)
        if expected == "tool_result" and part_type in {"tool_call_response", "tool_result"}:
            return cls._preview_text(part.get("response", part.get("content", part.get("result"))))
        return ""

    @classmethod
    def _message_previews(cls, messages: Any, expected: str, *, roles: set[str]) -> list[str]:
        if not isinstance(messages, list):
            return []
        previews: list[str] = []
        for message in messages:
            if not isinstance(message, dict) or message.get("role") not in roles:
                continue
            parts = message.get("parts")
            if not isinstance(parts, list):
                continue
            for part in parts:
                if isinstance(part, dict) and (preview := cls._part_preview(part, expected)):
                    previews.append(preview)
        return previews

    @classmethod
    def _trace_previews(cls, spans: list[dict[str, Any]]) -> tuple[str, str]:
        """输入取最早的用户文本；输出按 模型文本 → 推理 → 规划工具调用 → 工具返回 取最新一条。"""
        user_inputs: list[tuple[int, int, str]] = []
        tool_inputs: list[tuple[int, int, str]] = []
        output_buckets: dict[str, list[tuple[int, int, str]]] = {key: [] for key in cls._OUTPUT_PREVIEW_KEYS}

        for index, span in enumerate(spans):
            attributes = span.get(OtlpKey.ATTRIBUTES)
            if not isinstance(attributes, dict):
                continue
            start_time = span.get(OtlpKey.START_TIME) or 0
            end_time = span.get(OtlpKey.END_TIME) or start_time
            user_texts = cls._message_previews(attributes.get("gen_ai.input.messages"), "text", roles={"user"})
            if user_texts:
                user_inputs.append((start_time, index, user_texts[-1]))
            elif arguments := cls._preview_text(attributes.get("gen_ai.tool.call.arguments")):
                tool_inputs.append((start_time, index, arguments))

            for key in cls._OUTPUT_PREVIEW_KEYS:
                roles = {"assistant", "tool"} if key == "tool_result" else {"assistant"}
                previews = cls._message_previews(attributes.get("gen_ai.output.messages"), key, roles=roles)
                if key == "tool_result":
                    if result := cls._preview_text(attributes.get("gen_ai.tool.call.result")):
                        previews.append(result)
                if previews:
                    output_buckets[key].append((end_time, index, previews[-1]))

        input_text = min(user_inputs)[2] if user_inputs else (min(tool_inputs)[2] if tool_inputs else "")
        for key in cls._OUTPUT_PREVIEW_KEYS:
            if candidates := output_buckets[key]:
                return input_text, max(candidates)[2]
        return input_text, ""

    @classmethod
    def _trace_item(
        cls,
        trace_id: str,
        raw_spans: list[dict[str, Any]],
        entity_set: EntitySet,
    ) -> dict[str, Any]:
        # 在 Adapter 过滤前判定，避免漏掉未被保留的失败 Span。
        has_error = any(span["status"]["code"] == StatusCode.ERROR.value for span in raw_spans)
        # converted 只服务于本函数的 token / preview；调用方在拿到 compact item 后应丢掉 raw_spans。
        converted_spans = adapt_spans(raw_spans, entity_set)
        converted_attributes = [
            attributes for span in converted_spans if isinstance((attributes := span.get(OtlpKey.ATTRIBUTES)), dict)
        ]
        input_text, output_text = cls._trace_previews(converted_spans)
        root_span = next((span for span in raw_spans if not span.get(OtlpKey.PARENT_SPAN_ID)), {})
        start_time = (
            root_span.get(OtlpKey.START_TIME, 0)
            if root_span
            else min((span.get(OtlpKey.START_TIME, 0) for span in raw_spans), default=0)
        )
        end_time = max((span.get(OtlpKey.END_TIME, start_time) for span in raw_spans), default=start_time)

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
        conversation_id = next(
            (str(value) for value in attribute_values("gen_ai.conversation.id") if value not in (None, "")),
            "",
        )
        return {
            "group_id": trace_id,
            "group_field": OtlpKey.TRACE_ID,
            "trace_id": trace_id,
            "conversation_id": conversation_id,
            "status": "error" if has_error else "success",
            "input": input_text,
            "output": output_text,
            "input_tokens": token_total("gen_ai.usage.input_tokens"),
            "output_tokens": token_total("gen_ai.usage.output_tokens"),
            "cache_read_input_tokens": token_total("gen_ai.usage.cache_read.input_tokens"),
            "cache_write_input_tokens": token_total("gen_ai.usage.cache_write.input_tokens"),
            "start_time": start_time,
            "end_time": end_time,
            "elapsed_time": max(0, end_time - start_time),
            "user_id": user_id,
        }

    @classmethod
    def _consume_span_batch(
        cls,
        raw_spans: list[dict[str, Any]],
        trace_group_map: dict[str, Any],
        entity_set: EntitySet,
        childs_by_group: dict[Any, list[dict[str, Any]]],
    ) -> None:
        """把一批 raw Span 转成 compact child，并立刻丢掉这批原始文档。

        按 trace_id 分片查询时，同一 Trace 的 Span 落在同一批，这里就可以
        `_trace_item`。会话折叠只累加 child，等全部批次结束后再拼 group item。
        `raw_spans` 会被清空，调用方不要再持有这批 `_source`。
        """
        spans_by_group: dict[Any, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
        for span in raw_spans:
            trace_id = cls._span_field_value(span, OtlpKey.TRACE_ID)
            group_id = trace_group_map.get(trace_id, "")
            if group_id is not None and group_id != "" and trace_id:
                spans_by_group[group_id][trace_id].append(span)
        # 分组表已握住同一批 dict，断开 batch list 的引用，避免和 spans_by_group 叠一份指针数组。
        raw_spans.clear()

        for group_id, traces in spans_by_group.items():
            for trace_id in list(traces):
                child = cls._trace_item(trace_id, traces[trace_id], entity_set)
                childs_by_group.setdefault(group_id, []).append(child)
                # compact item 已拷走 input/output/token，raw 可以释放。
                del traces[trace_id]

    @classmethod
    def _assemble_group_items(
        cls,
        group_field: str,
        group_ids: list[Any],
        childs_by_group: dict[Any, list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        """用已经算好的 compact child 拼分页顺序的 group item，不再碰 raw Span。"""
        items: list[dict[str, Any]] = []
        for group_id in group_ids:
            childs = childs_by_group.get(group_id)
            if not childs:
                # Trace 视角没有 child 就组不出行；会话视角保留缺省行，避免短页掐掉下拉加载。
                if group_field == OtlpKey.TRACE_ID:
                    continue
                items.append(cls._empty_group_item(group_field, group_id))
                continue
            childs.sort(key=lambda child: child["end_time"], reverse=True)
            start_time = min(child["start_time"] for child in childs)
            end_time = max(child["end_time"] for child in childs)
            first_input = min(
                (child for child in childs if child["input"]), key=lambda child: child["start_time"], default=None
            )
            last_output = max(
                (child for child in childs if child["output"]), key=lambda child: child["end_time"], default=None
            )
            items.append(
                {
                    "group_id": group_id,
                    "group_field": group_field,
                    "status": "error" if any(child["status"] == "error" for child in childs) else "success",
                    "input": first_input["input"] if first_input else "",
                    "output": last_output["output"] if last_output else "",
                    "input_tokens": sum(child["input_tokens"] for child in childs),
                    "output_tokens": sum(child["output_tokens"] for child in childs),
                    "cache_read_input_tokens": sum(child["cache_read_input_tokens"] for child in childs),
                    "cache_write_input_tokens": sum(child["cache_write_input_tokens"] for child in childs),
                    "start_time": start_time,
                    "end_time": end_time,
                    "elapsed_time": max(0, end_time - start_time),
                    "user_id": next((child["user_id"] for child in childs if child["user_id"]), ""),
                    "childs": childs,
                }
            )

        if group_field == OtlpKey.TRACE_ID:
            for item in items:
                item.update(item.pop("childs")[0])
        return items

    @classmethod
    def _empty_group_item(cls, group_field: str, group_id: Any) -> dict[str, Any]:
        return {
            "group_id": group_id,
            "group_field": group_field,
            "status": "",
            "input": "",
            "output": "",
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_input_tokens": 0,
            "cache_write_input_tokens": 0,
            "start_time": 0,
            "end_time": 0,
            "elapsed_time": 0,
            "user_id": "",
            "childs": [],
        }

    @classmethod
    def _group_spans(
        cls,
        group_field: str,
        group_ids: list[Any],
        trace_group_map: dict[str, Any],
        raw_spans: list[dict[str, Any]],
        entity_set: EntitySet,
    ) -> list[dict[str, Any]]:
        childs_by_group: dict[Any, list[dict[str, Any]]] = defaultdict(list)
        cls._consume_span_batch(raw_spans, trace_group_map, entity_set, childs_by_group)
        return cls._assemble_group_items(group_field, group_ids, childs_by_group)

    def perform_request(self, validated_request_data):
        group_field = validated_request_data["group_field"]

        bk_biz_id = validated_request_data["bk_biz_id"]
        app_name = validated_request_data["app_name"]
        service_name = validated_request_data["service_name"]
        application = Application.objects.get(
            bk_biz_id=bk_biz_id,
            app_name=app_name,
        )
        entity_set: EntitySet = EntitySet(
            bk_biz_id=bk_biz_id,
            app_name=app_name,
            service_names=[service_name],
        )
        product = resolve_product(entity_set, service_name)
        is_aidev = product == LLMProduct.AIDEV.value
        if is_aidev:
            entity_set = EntitySet(bk_biz_id=bk_biz_id, app_name=app_name)
            filters = []
        else:
            filters = [
                {
                    "key": OtlpKey.get_resource_key(ResourceAttributes.SERVICE_NAME),
                    "operator": OperatorEnum.EQUAL["operator"],
                    "value": [service_name],
                }
            ]
        query_group_field = resolve_query_field(product, group_field)
        query_string = self._build_keyword_query(
            product,
            bk_biz_id,
            app_name,
            validated_request_data["keyword"],
        )
        span_query = get_query(application.build_data_sources())
        group_ids = span_query.query_group_list(
            start_time=validated_request_data["start_time"],
            end_time=validated_request_data["end_time"],
            group_field=query_group_field,
            offset=validated_request_data["offset"],
            limit=validated_request_data["limit"],
            filters=filters,
            query_string=query_string,
            extra_filter=AGENT_CANDIDATE_Q if group_field == OtlpKey.TRACE_ID else None,
        )
        result = {
            "offset": validated_request_data["offset"],
            "limit": validated_request_data["limit"],
            "items": [],
        }
        if not group_ids:
            return result

        group_trace_records = span_query.query_group_trace_list(
            group_field=query_group_field,
            group_ids=group_ids,
        )
        trace_group_map: dict[str, Any] = {}
        for record in group_trace_records:
            trace_id = record.get(OtlpKey.TRACE_ID, "")
            if not trace_id:
                continue

            group_id = LLMQuery._get_field_value(record, query_group_field)
            if group_id is not None and group_id != "" and trace_id not in trace_group_map:
                trace_group_map[trace_id] = group_id

        # 按批拉取 → 立刻转 compact child → 丢掉该批 raw，避免先拼出全量 `_source`。
        # 没有 Trace 的会话仍走 assemble，补缺省行，避免短页。
        childs_by_group: dict[Any, list[dict[str, Any]]] = defaultdict(list)
        if trace_group_map:
            for batch in span_query.iter_by_group_ids(
                group_field=OtlpKey.TRACE_ID,
                group_ids=list(trace_group_map),
            ):
                self._consume_span_batch(batch, trace_group_map, entity_set, childs_by_group)
        result["items"] = self._assemble_group_items(group_field, group_ids, childs_by_group)
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
        entity_set = EntitySet(
            bk_biz_id=validated_request_data["bk_biz_id"],
            app_name=validated_request_data["app_name"],
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
                    "flow": self._build_flow(raw_trace_spans, adapt_spans(raw_trace_spans, entity_set)),
                }
            )
        return result


class LLMMetricRequestSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
    app_name = serializers.CharField(required=True, label="应用名称")
    service_name = serializers.CharField(required=False, allow_blank=True, default="", label="服务名称")
    start_time = serializers.IntegerField(required=True, label="开始时间")
    end_time = serializers.IntegerField(required=True, label="结束时间")
    cal_type = serializers.ChoiceField(required=True, choices=sorted(LLMMetricGroup.AGGREGATIONS), label="指标类型")
    group_by = serializers.ListField(required=False, default=list, child=serializers.CharField(), label="聚合字段")


class LLMMetricGroupMixin:
    """解析服务对应的产品，构造 LLM 指标组。"""

    @staticmethod
    def _get_group(validated_request_data: dict[str, Any], time_shift: str | None = None) -> LLMMetricGroup:
        bk_biz_id: int = validated_request_data["bk_biz_id"]
        app_name: str = validated_request_data["app_name"]
        service_name: str = validated_request_data["service_name"]
        entity_set = EntitySet(
            bk_biz_id=bk_biz_id,
            app_name=app_name,
            service_names=[service_name] if service_name else None,
        )
        # 不指定服务时取应用下任一 LLM 服务的产品，否则字段映射会错落到标准名上
        service_names: list[str] = [service_name] if service_name else entity_set.service_names
        return MetricGroupRegistry.get(
            GroupEnum.LLM.value,
            bk_biz_id,
            app_name,
            group_by=validated_request_data["group_by"],
            time_shift=time_shift,
            product=next(filter(None, (resolve_product(entity_set, name) for name in service_names)), ""),
            service_name=service_name,
        )


class TimeSeriesResource(LLMMetricGroupMixin, Resource):
    """LLM 指标时序查询。"""

    class RequestSerializer(LLMMetricRequestSerializer):
        # 放大期望聚合周期，避免时间范围拉长后数据点过密，与事件时序图保持一致
        INTERVAL_FACTOR = 10

        interval = serializers.IntegerField(required=False, label="聚合周期")

        def validate(self, attrs):
            attrs = super().validate(attrs)
            if not attrs.get("interval"):
                attrs["interval"] = get_auto_interval(
                    LLMMetricGroup.COLLECT_INTERVAL,
                    attrs["start_time"],
                    attrs["end_time"],
                    factor=self.INTERVAL_FACTOR,
                )
            return attrs

    def perform_request(self, validated_request_data):
        return self._get_group(validated_request_data).time_series(
            validated_request_data["cal_type"],
            validated_request_data["interval"],
            start_time=validated_request_data["start_time"],
            end_time=validated_request_data["end_time"],
        )


class CalculateByRangeResource(LLMMetricGroupMixin, MetricCalculateByRangeResource):
    """LLM 指标区间聚合，返回结构与调用分析的 CalculateByRangeResource 保持一致。"""

    class RequestSerializer(LLMMetricRequestSerializer):
        ZERO_TIME_SHIFT = "0s"

        baseline = serializers.CharField(required=False, default=ZERO_TIME_SHIFT, label="对比基准")
        time_shifts = serializers.ListField(
            required=False,
            default=list,
            child=serializers.CharField(),
            label="时间偏移",
        )

        def validate(self, attrs):
            attrs = super().validate(attrs)
            attrs["time_shifts"] = list(dict.fromkeys([*attrs["time_shifts"], self.ZERO_TIME_SHIFT]))
            if len(attrs["time_shifts"]) > 3:
                raise serializers.ValidationError("最多支持两次时间对比")
            if attrs["baseline"] not in attrs["time_shifts"]:
                raise serializers.ValidationError("baseline 必须包含在 time_shifts 中")
            return attrs

    @classmethod
    def format_value(cls, metric_cal_type: str, value: Any) -> float:
        """计数类算子取整：基类只认调用分析的 request_total，LLM 的计数算子用的是自己的取值名。"""
        formatted: float = super().format_value(metric_cal_type, value)
        if metric_cal_type in {
            CalculationType.REQUEST_COUNT.value,
            CalculationType.MODEL_CALL_COUNT.value,
            CalculationType.OPERATION_COUNT.value,
        }:
            return int(formatted)
        return formatted

    def perform_request(self, validated_request_data):
        def _collect(_alias: str, **_kwargs):
            alias_aggregated_records_map[_alias] = self._get_group(validated_request_data, _alias).handle(
                cal_type, **_kwargs
            )

        baseline: str = validated_request_data["baseline"]
        cal_type: str = validated_request_data["cal_type"]
        group_fields: list[str] = validated_request_data["group_by"]
        alias_aggregated_records_map: dict[str, list[dict[str, Any]]] = {}

        run_threads(
            [
                InheritParentThread(
                    target=_collect,
                    args=(time_shift,),
                    kwargs={
                        "start_time": validated_request_data["start_time"],
                        "end_time": validated_request_data["end_time"],
                    },
                )
                for time_shift in validated_request_data["time_shifts"]
            ]
        )

        merged_records: list[dict[str, Any]] = self._merge(cal_type, group_fields, alias_aggregated_records_map)
        aliases: list[str] = list(alias_aggregated_records_map.keys())
        # 分组结果按基准列降序，概览页的 TopK 卡片直接取前 N 条
        merged_records.sort(key=lambda record: record.get(baseline) or 0, reverse=True)
        self._process_growth_rates(baseline, aliases, merged_records)

        return {"total": len(merged_records), "data": self._process_sorted(merged_records)}
