"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from collections import defaultdict
from collections.abc import Iterator, Sequence
from typing import Any

from django.db.models import Q
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.trace import StatusCode
from rest_framework import serializers

from constants.apm import LLMProduct, OtlpKey
from constants.otel_query import OperatorEnum
from core.drf_resource import Resource, api

from apm_web.handlers.metric_group import GroupEnum, MetricGroupRegistry
from apm_web.handlers.trace_handler.query import QueryHandler, QueryStringBuilder, SpanQueryTransformer
from apm_web.llm.adapter import adapt_spans
from apm_web.llm.adapter.fields import (
    AGENT_CANDIDATE_Q,
    SPAN_TYPES,
    operation_query,
    resolve_product,
    resolve_query_field,
    resolve_query_fields,
)
from apm_web.llm.builders.flow import TOKEN_FIELDS, FlowBuilder
from apm_web.llm.builders.summary import TraceSummary
from apm_web.llm.constants import CalculationType, SpanType
from apm_web.llm.metric_group import LLMMetricGroup
from apm_web.llm.query import LLMQuery, get_query
from apm_web.metric.resources import CalculateByRangeResource as MetricCalculateByRangeResource
from apm_web.models import Application
from apm_web.strategy.dispatch.entity import EntitySet
from bkmonitor.data_source import get_auto_interval
from bkmonitor.utils.thread_backend import InheritParentThread, ThreadPool, run_threads


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

    @staticmethod
    def _build_keyword_query(product: str, bk_biz_id: int, app_name: str, keyword: str) -> str:
        """构造关键词查询，避免 hex32 会话 ID 被误判为仅查询 Trace ID。"""
        if ":" not in keyword and (hex32 := QueryStringBuilder.extract_trace_id(keyword)):
            conversation_field = resolve_query_field(product, "attributes.gen_ai.conversation.id")
            fields = dict.fromkeys((OtlpKey.TRACE_ID, conversation_field))
            return " OR ".join(f'{field}: "{hex32}"' for field in fields)

        return QueryHandler.process_query_string(SpanQueryTransformer(bk_biz_id, app_name), keyword) or ""

    @staticmethod
    def iter_trace_items(
        *,
        bk_biz_id: int,
        app_name: str,
        span_query: LLMQuery,
        entity_set: EntitySet,
        trace_ids: list[str],
        product: str,
        cal_types: Sequence[CalculationType] = (CalculationType.INPUT_TOKENS, CalculationType.OUTPUT_TOKENS),
    ) -> Iterator[dict[str, Any]]:
        """按 Trace 折叠查询预览及统计，不加载完整调用链。"""
        if not trace_ids:
            return

        metric_group = LLMMetricGroup(
            bk_biz_id,
            app_name,
            group_by=[OtlpKey.TRACE_ID],
            filter_dict={"trace_id__eq": trace_ids},
            product=product,
            query=span_query,
        )
        operations: list[str] = [
            name for name, span_type in SPAN_TYPES.items() if span_type in {SpanType.AGENT, SpanType.LLM}
        ]
        extra_filter: Q = operation_query(product, operations)
        # 统计按需查询并去重；get() 传播异常，不能把失败伪装成空预览或零 Token。
        cal_types = tuple(dict.fromkeys(cal_types))
        with ThreadPool(processes=3 + len(cal_types)) as pool:
            input_preview = pool.apply_async(
                span_query.query_trace_preview,
                (trace_ids,),
                {"extra_filter": extra_filter, "sort": ["start_time asc"]},
            )
            output_preview = pool.apply_async(
                span_query.query_trace_preview,
                (trace_ids,),
                {
                    # agent.execution 恒无输出；UQ 不保留 ~Q 的取反标记，排除条件必须用 __neq。
                    "extra_filter": extra_filter & Q(span_name__neq=["agent.execution"])
                    if product == LLMProduct.AIDEV.value
                    else extra_filter,
                    "sort": ["end_time desc"],
                },
            )
            token_queries = {
                cal_type.value: pool.apply_async(metric_group.handle, (cal_type.value,)) for cal_type in cal_types
            }
            errors = pool.apply_async(span_query.query_trace_errors, (trace_ids,))
            previews = [*input_preview.get(), *output_preview.get()]
            token_results: dict[str, list[dict[str, Any]]] = {
                name: query.get() for name, query in token_queries.items()
            }
            error_trace_ids: set[str] = {record[OtlpKey.TRACE_ID] for record in errors.get()}

        spans_by_trace: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
        for span in previews:
            trace_id = span[OtlpKey.TRACE_ID]
            if trace_id not in trace_ids:
                continue
            spans_by_trace[trace_id][span[OtlpKey.SPAN_ID]] = span

        tokens_by_trace: dict[str, dict[str, float]] = defaultdict(dict)
        for name, records in token_results.items():
            for record in records:
                tokens_by_trace[record[OtlpKey.TRACE_ID]][name] = record["_result_"]

        for trace_id in trace_ids:
            spans: dict[str, dict[str, Any]] = spans_by_trace.get(trace_id, {})
            if not spans:
                continue
            raw_spans: list[dict[str, Any]] = list(spans.values())
            yield TraceSummary.build(
                trace_id,
                raw_spans,
                adapt_spans(raw_spans, entity_set),
                {name: tokens_by_trace[trace_id].get(name, 0) for name in token_results},
                has_error=trace_id in error_trace_ids,
            )

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
            childs: list[dict[str, Any]] | None = childs_by_group.get(group_id)
            if not childs:
                # 会话视角保留缺省行，避免短页掐掉下拉加载。
                if group_field != OtlpKey.TRACE_ID:
                    items.append(cls._empty_group_item(group_field, group_id))
                continue

            if group_field == OtlpKey.TRACE_ID:
                latest_child: dict[str, Any] = max(childs, key=lambda child: child["end_time"])
                items.append(latest_child.copy())
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
                    "start_time": start_time,
                    "end_time": end_time,
                    "elapsed_time": max(0, end_time - start_time),
                    "user_id": next((child["user_id"] for child in childs if child["user_id"]), ""),
                    "childs": childs,
                }
            )

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
            "start_time": 0,
            "end_time": 0,
            "elapsed_time": 0,
            "user_id": "",
            "childs": [],
        }

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

            group_id = LLMQuery.get_field_value(record, query_group_field)
            if group_id is not None and group_id != "" and trace_id not in trace_group_map:
                trace_group_map[trace_id] = group_id

        childs_by_group: dict[Any, list[dict[str, Any]]] = defaultdict(list)
        for child in self.iter_trace_items(
            bk_biz_id=bk_biz_id,
            app_name=app_name,
            span_query=span_query,
            entity_set=entity_set,
            trace_ids=list(trace_group_map),
            product=product,
        ):
            childs_by_group[trace_group_map[child["trace_id"]]].append(child)
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
    """会话查询只返回 Trace 概览，按 Trace ID 查询完整执行线。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        app_name = serializers.CharField(required=True, label="应用名称")
        group_field = serializers.CharField(required=True, label="分组字段")
        group_id = serializers.CharField(required=True, label="分组值")

    @staticmethod
    def build_trace_flow(bk_biz_id: int, app_name: str, trace_id: str) -> FlowBuilder | None:
        """仅加载单个 Trace 的完整 Span，执行线与 Agent Token 统计共用一次构造。"""
        application = Application.objects.get(bk_biz_id=bk_biz_id, app_name=app_name)
        raw_spans: list[dict[str, Any]] = get_query(application.build_data_sources()).query_by_group_ids(
            group_field=OtlpKey.TRACE_ID,
            group_ids=[trace_id],
        )
        if not raw_spans:
            return None
        entity_set = EntitySet(bk_biz_id=bk_biz_id, app_name=app_name)
        builder = FlowBuilder(raw_spans, adapt_spans(raw_spans, entity_set))
        builder.build()
        return builder

    @staticmethod
    def list_session_traces(validated_request_data: dict[str, Any]) -> list[dict[str, Any]]:
        bk_biz_id: int = validated_request_data["bk_biz_id"]
        app_name: str = validated_request_data["app_name"]
        group_field: str = validated_request_data["group_field"]
        application = Application.objects.get(bk_biz_id=bk_biz_id, app_name=app_name)
        span_query = get_query(application.build_data_sources())
        service_field: str = OtlpKey.get_resource_key(ResourceAttributes.SERVICE_NAME)
        # 会话可能使用产品别名；附带服务名以确定每条 Trace 的统计口径。
        records: list[dict[str, Any]] = span_query.query_group_trace_list(
            group_field=group_field,
            group_ids=[validated_request_data["group_id"]],
            possible_group_fields=resolve_query_fields(group_field),
            extra_fields=[service_field],
        )
        if not records:
            return []

        trace_products: dict[str, str] = {}
        entity_set = EntitySet(bk_biz_id=bk_biz_id, app_name=app_name)
        for record in records:
            trace_id: str = record.get(OtlpKey.TRACE_ID, "")
            if trace_id and trace_id not in trace_products:
                service_name: str = LLMQuery.get_field_value(record, service_field)
                trace_products[trace_id] = resolve_product(entity_set, service_name) or LLMProduct.DEFAULT.value

        traces_by_product: dict[str, list[str]] = defaultdict(list)
        for trace_id, product in trace_products.items():
            traces_by_product[product].append(trace_id)

        items: dict[str, dict[str, Any]] = {}
        for product, trace_ids in traces_by_product.items():
            for item in ListTracesResource.iter_trace_items(
                bk_biz_id=bk_biz_id,
                app_name=app_name,
                span_query=span_query,
                entity_set=entity_set,
                trace_ids=trace_ids,
                product=product,
                cal_types=tuple(CalculationType(name) for name in TOKEN_FIELDS),
            ):
                items[item["trace_id"]] = {**item, "flow": []}

        return [items[trace_id] for trace_id in trace_products if trace_id in items]

    def perform_request(self, validated_request_data):
        traces: list[dict[str, Any]] = []
        if validated_request_data["group_field"] != OtlpKey.TRACE_ID:
            traces = self.list_session_traces(validated_request_data)
        else:
            trace_id: str = validated_request_data["group_id"]
            builder = self.build_trace_flow(
                validated_request_data["bk_biz_id"], validated_request_data["app_name"], trace_id
            )
            if builder is not None:
                item: dict[str, Any] = TraceSummary.build(
                    trace_id,
                    builder.raw_spans,
                    builder.spans,
                    builder.tokens,
                    has_error=any(
                        (span.get(OtlpKey.STATUS) or {}).get("code") == StatusCode.ERROR.value
                        for span in builder.raw_spans
                    ),
                )
                item["flow"] = builder.flow
                traces.append(item)
        tokens: dict[str, float] = {name: sum(trace[name] for trace in traces) for name in TOKEN_FIELDS}
        tokens["total_tokens"] = tokens["input_tokens"] + tokens["output_tokens"]
        for trace in traces:
            trace["total_tokens"] = trace["input_tokens"] + trace["output_tokens"]
        start_time: int = min((trace["start_time"] for trace in traces), default=0)
        end_time: int = max((trace["end_time"] for trace in traces), default=0)
        return {
            "group_field": validated_request_data["group_field"],
            "group_id": validated_request_data["group_id"],
            **tokens,
            "start_time": start_time,
            "end_time": end_time,
            "elapsed_time": max(0, end_time - start_time),
            "traces": traces,
        }


class TokenStatisticsResource(Resource):
    """统计 Trace 内所有 Agent Span 子树的模型 Token。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        app_name = serializers.CharField(required=True, label="应用名称")
        trace_id = serializers.CharField(required=True, label="Trace ID")

    def perform_request(self, validated_request_data):
        trace_id = validated_request_data["trace_id"]
        builder = ListFlowsResource.build_trace_flow(
            validated_request_data["bk_biz_id"], validated_request_data["app_name"], trace_id
        )
        return {"trace_id": trace_id, "statistics": builder.statistics if builder else {}}


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
