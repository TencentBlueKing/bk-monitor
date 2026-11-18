"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import functools
import json
import logging
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from django.db.models import Q
from opentelemetry.semconv.resource import ResourceAttributes

from bkmonitor.data_source import get_auto_interval
from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder
from bkmonitor.utils.time_tools import parse_time_compare_abbreviation, time_interval_align
from constants.apm import LLMProduct, OtlpKey
from core.drf_resource import resource

from apm_web.handlers.metric_group import base, define
from apm_web.llm.adapter.fields import operation_query, resolve_operation_name, resolve_query_field
from apm_web.llm.constants import CalculationType
from apm_web.llm.query import LLMQuery, get_query
from apm_web.models import Application

logger = logging.getLogger(__name__)

# Span 的 start_time / elapsed_time 都是微秒
MICROSECONDS_PER_SECOND = 1_000_000

MILLISECONDS_PER_SECOND = 1_000

SERVICE_NAME_FIELD: str = OtlpKey.get_resource_key(ResourceAttributes.SERVICE_NAME)

OPERATION_NAME_FIELD: str = "gen_ai.operation.name"


class Layer:
    """Span 的语义层级。"""

    AGENT = "agent"
    MODEL = "model"


@dataclass(frozen=True)
class Aggregation:
    """一个算子的取数声明：在哪一层取数、聚合什么、怎么聚合。

    slots 走 TOKEN_FIELDS 做产品换算，field 是各产品同名的固有字段，两者互斥。
    多个 slots 的聚合值由存储侧相加。
    """

    layer: str | None
    method: str
    slots: tuple[str, ...] = ()
    field: str = ""


class LLMMetricGroup(base.BaseMetricGroup):
    # Span 是明细数据，没有采集周期，取平台趋势图的最小聚合周期
    COLLECT_INTERVAL: int = 60
    # 放大期望聚合周期，避免时间范围拉长后数据点过密，与事件时序图保持一致
    INTERVAL_FACTOR: int = 10

    # 层级谓词：各产品对「哪些 Span 算模型调用 / Agent 调用」的埋点方式不同。
    # default 就是标准 OT 语义，未单独登记的产品都落到它，因此声明表只需要记录特例。
    LAYER_QUERIES: dict[str, dict[str, Q]] = {
        Layer.MODEL: {
            LLMProduct.DEFAULT.value: Q(
                **{"attributes.gen_ai.operation.name": ["chat", "generate_content", "text_completion", "embeddings"]}
            ),
            # operation.name 取值为大写的 CHAT，统一用 span.kind 判定
            LLMProduct.AGENTLENS.value: Q(**{"attributes.gen_ai.span.kind": "LLM"}),
            LLMProduct.LANGFUSE.value: Q(**{"attributes.langfuse.observation.type": "generation"}),
            # 同时支持标准 GenAI 与旧埋点，旧模式只取业务模型 Span，避免包装层重复计数。
            LLMProduct.AIDEV.value: operation_query(
                LLMProduct.AIDEV.value, ["chat", "generate_content", "text_completion", "embeddings"]
            ),
        },
        Layer.AGENT: {
            LLMProduct.DEFAULT.value: Q(**{"attributes.gen_ai.operation.name": ["invoke_agent", "invoke_workflow"]}),
            LLMProduct.AGENTLENS.value: Q(**{"attributes.gen_ai.span.kind": "AGENT"}),
            LLMProduct.LANGFUSE.value: Q(**{"attributes.langfuse.internal.is_app_root": "true"}),
            LLMProduct.AIDEV.value: operation_query(LLMProduct.AIDEV.value, ["invoke_agent", "invoke_workflow"]),
        },
    }

    # 语义槽位 -> 产品 -> 字段，登记多个字段时由存储侧相加。
    # default 只登记标准名；多字段是产品特例，同一 Span 上这些拼写互斥，相加才不漏数。
    TOKEN_FIELDS: dict[str, dict[str, tuple[str, ...]]] = {
        "input_tokens": {
            LLMProduct.DEFAULT.value: ("attributes.gen_ai.usage.input_tokens",),
            # 新版 GenAI 与旧版 traceloop 使用不同的 Token 字段。
            LLMProduct.AIDEV.value: (
                "attributes.gen_ai.usage.input_tokens",
                "attributes.gen_ai.usage.prompt_tokens",
            ),
        },
        "output_tokens": {
            LLMProduct.DEFAULT.value: ("attributes.gen_ai.usage.output_tokens",),
            LLMProduct.AIDEV.value: (
                "attributes.gen_ai.usage.output_tokens",
                "attributes.gen_ai.usage.completion_tokens",
            ),
        },
        "cache_read": {
            LLMProduct.DEFAULT.value: ("attributes.gen_ai.usage.cache_read.input_tokens",),
            # 该产品自己就有三种拼写：样本环境用下划线形态，生产用 cached，
            # 且标准名在生产上条条有值却恒为 0，只认标准名会把真实缓存量静默算成 0
            LLMProduct.GALILEO.value: (
                "attributes.gen_ai.usage.cache_read.input_tokens",
                "attributes.gen_ai.usage.cache_read_input_tokens",
                "attributes.gen_ai.usage.cached.input_tokens",
            ),
        },
        "cache_write": {
            LLMProduct.DEFAULT.value: ("attributes.gen_ai.usage.cache_write.input_tokens",),
            # GenAI 语义约定独立成库时把 cache_creation 改名为 cache_write，该产品仍是改名前的形态
            LLMProduct.GALILEO.value: (
                "attributes.gen_ai.usage.cache_creation.input_tokens",
                "attributes.gen_ai.usage.cache_creation_input_tokens",
            ),
        },
    }

    # usage_details 是 keyword 类型的 JSON 串，存储侧无法 SUM，只能取回原始值本地聚合。
    LANGFUSE_USAGE_FIELD: str = "attributes.langfuse.observation.usage_details"
    LANGFUSE_USAGE_KEYS: dict[str, tuple[str, ...]] = {
        # 该产品的 input 恒为 0，实测真实输入量需要把缓存部分加回来，才与其他产品的计费口径一致
        "input_tokens": ("input", "cache_read_input_tokens", "cache_creation_input_tokens"),
        "output_tokens": ("output",),
        "cache_read": ("cache_read_input_tokens",),
        "cache_write": ("cache_creation_input_tokens",),
    }

    AGGREGATIONS: dict[str, Aggregation] = {
        CalculationType.INPUT_TOKENS.value: Aggregation(Layer.MODEL, "SUM", slots=("input_tokens",)),
        CalculationType.OUTPUT_TOKENS.value: Aggregation(Layer.MODEL, "SUM", slots=("output_tokens",)),
        CalculationType.TOTAL_TOKENS.value: Aggregation(Layer.MODEL, "SUM", slots=("input_tokens", "output_tokens")),
        CalculationType.CACHE_TOKENS.value: Aggregation(Layer.MODEL, "SUM", slots=("cache_read", "cache_write")),
        CalculationType.CACHE_READ_INPUT_TOKENS.value: Aggregation(Layer.MODEL, "SUM", slots=("cache_read",)),
        CalculationType.CACHE_WRITE_INPUT_TOKENS.value: Aggregation(Layer.MODEL, "SUM", slots=("cache_write",)),
        CalculationType.MODEL_CALL_COUNT.value: Aggregation(Layer.MODEL, "COUNT", field="_index"),
        # 操作次数按调用方的查询范围直接计数，不额外限定 Span 层级。
        CalculationType.OPERATION_COUNT.value: Aggregation(None, "COUNT", field="_index"),
        CalculationType.DURATION.value: Aggregation(Layer.MODEL, "AVG", field=OtlpKey.ELAPSED_TIME),
        # Agent Span 数会被双层埋点和子 Agent 放大，按 trace 去重才收敛到真实请求数
        CalculationType.REQUEST_COUNT.value: Aggregation(Layer.AGENT, "DISTINCT", field=OtlpKey.TRACE_ID),
    }

    def __init__(
        self,
        bk_biz_id: int,
        app_name: str,
        group_by: list[str] | None = None,
        filter_dict: dict[str, Any] | None = None,
        product: str | None = None,
        service_name: str | None = None,
        query: LLMQuery | None = None,
        **kwargs,
    ):
        super().__init__(bk_biz_id, app_name, group_by, filter_dict, **kwargs)
        self.product: str = product or LLMProduct.DEFAULT.value
        self.time_shift: str | None = kwargs.get("time_shift")
        self.query: LLMQuery = query or get_query(
            Application.objects.get(bk_biz_id=bk_biz_id, app_name=app_name).build_data_sources()
        )
        # 分组字段按产品换算成存储中的原始字段，聚合结果再回填成调用方传入的标准名
        self.group_fields: list[str] = [self._resolve_group_field(self.product, field) for field in self.group_by]
        self.dimension_fields: list[tuple[str, str]] = [
            (storage_field, standard_field)
            for storage_field, standard_field in zip(self.group_fields, self.group_by)
            if standard_field != LLMQuery.TIME_BUCKET_FIELD
        ]
        # 该产品把一个 Agent 拆成多个上报服务，带 Token 的模型 Span 落在兄弟服务 {svc}-default 上，
        # 按服务过滤必然漏数，改为不加过滤，由应用维度兜住全部上报名。
        if service_name and self.product != LLMProduct.AIDEV.value:
            self.filter_dict.setdefault(f"{SERVICE_NAME_FIELD}__eq", [service_name])

    class Meta:
        name = define.GroupEnum.LLM.value

    def handle(self, calculation_type: str, **kwargs) -> list[dict[str, Any]]:
        return self.get_calculation_method(calculation_type)(**kwargs)

    def get_calculation_method(self, calculation_type: str) -> Callable[..., list[dict[str, Any]]]:
        return functools.partial(self._aggregate, self._get_aggregation(calculation_type))

    def time_series(
        self, calculation_type: str, interval: int, start_time: int | None = None, end_time: int | None = None
    ) -> dict[str, Any]:
        """时序数据：默认下推到存储侧出图，存储侧聚合不了的产品本地聚合。"""
        aggregation: Aggregation = self._get_aggregation(calculation_type)
        start_time, end_time = self._shift(start_time, end_time)
        # 回传聚合周期，前端按「数据步长」展示
        query_config: dict[str, Any] = {"interval": interval}
        if self._is_local_aggregation(aggregation):
            return {
                "metrics": [],
                "series": self._local_series(aggregation, start_time, end_time, interval),
                "query_config": query_config,
            }

        response: dict[str, Any] = resource.grafana.graph_unify_query(
            self.query.query_field_graph_config(
                self._queries(aggregation.layer),
                start_time,
                end_time,
                self._fields(aggregation),
                aggregation.method,
                interval,
                self.group_fields,
            )
        )
        return {
            **response,
            "series": self._standardize_series_list(response.get("series") or []),
            "query_config": query_config,
        }

    def _get_aggregation(self, calculation_type: str) -> Aggregation:
        if calculation_type not in self.AGGREGATIONS:
            raise ValueError(f"Unsupported calculation type -> {calculation_type}")
        return self.AGGREGATIONS[calculation_type]

    def _declared(self, table: dict[str, dict[str, Any]], key: str) -> Any:
        """取当前产品在声明表中的登记项，未登记的产品按标准 OT 语义取 default 那份。"""
        entry: dict[str, Any] = table[key]
        return entry.get(self.product, entry[LLMProduct.DEFAULT.value])

    def _fields(self, aggregation: Aggregation) -> list[str]:
        """展开算子在当前产品下要聚合的字段，多个字段的聚合值由存储侧相加。"""
        if not aggregation.slots:
            return [aggregation.field]
        return [field for slot in aggregation.slots for field in self._declared(self.TOKEN_FIELDS, slot)]

    def _shift(self, start_time: int | None, end_time: int | None) -> tuple[int | None, int | None]:
        """Trace 原始表没有 promql 的 time_shift 算子，改为整体平移查询窗口。"""
        if not self.time_shift or start_time is None or end_time is None:
            return start_time, end_time
        offset: int = parse_time_compare_abbreviation(self.time_shift)
        return start_time + offset, end_time + offset

    def _queries(self, layer: str | None) -> list[QueryConfigBuilder]:
        """按产品的层级谓词构造查询，应用配置了多个 Trace 结果表时各出一个。"""
        layer_q: Q = self._declared(self.LAYER_QUERIES, layer) if layer is not None else Q()
        return [query.filter(layer_q).filter(self._filter_dict_to_q()) for query in self.query.build_queries()]

    @staticmethod
    def _resolve_group_field(product: str, field: str) -> str:
        if field in {OtlpKey.TRACE_ID, LLMQuery.TIME_BUCKET_FIELD}:
            return field
        if field in {"service_name", ResourceAttributes.SERVICE_NAME}:
            return SERVICE_NAME_FIELD
        if field.startswith(f"{OtlpKey.RESOURCE}."):
            return field
        attr_field: str = field if field.startswith(f"{OtlpKey.ATTRIBUTES}.") else OtlpKey.get_attributes_key(field)
        return resolve_query_field(product, attr_field)

    @staticmethod
    def _is_operation_dimension(field: str) -> bool:
        return field in {OPERATION_NAME_FIELD, OtlpKey.get_attributes_key(OPERATION_NAME_FIELD)}

    def _dimension_key(self, record: dict[str, Any]) -> tuple:
        values: list[Any] = []
        for storage_field, standard_field in self.dimension_fields:
            value = record.get(storage_field) or ""
            if self._is_operation_dimension(standard_field):
                value = resolve_operation_name(self.product, value)
            values.append(value)
        return tuple(values)

    def _should_drop_operation_dimension(self, key: tuple) -> bool:
        return any(
            self._is_operation_dimension(field) and value == "" for (_, field), value in zip(self.dimension_fields, key)
        )

    def _dimensions(self, key: tuple) -> dict[str, Any]:
        """维度回填成调用方传入的标准字段名，不暴露各产品存储中的原始字段名。"""
        return {field: value for (_, field), value in zip(self.dimension_fields, key)}

    def _standardize_series(self, series: dict[str, Any]) -> dict[str, Any]:
        """维度与图例都按标准字段名回填，与本地聚合出的 series 结构保持一致。

        grafana 的图例取自查询表达式，多字段求和时会展开成一长串「方法(字段)」，既不可读也与
        本地聚合路径不一致，统一改由维度决定：无分组时留空，交给前端用图表标题兜底。
        """
        key: tuple = self._dimension_key(series.get("dimensions") or {})
        return {**series, "dimensions": self._dimensions(key), "target": next(iter(key), "")}

    def _standardize_series_list(self, series_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """操作名映射后可能多条曲线落到同一标准名，按维度合并并丢掉空操作名。"""
        merged: dict[tuple, dict[str, Any]] = {}
        for item in series_list:
            key: tuple = self._dimension_key(item.get("dimensions") or {})
            if self._should_drop_operation_dimension(key):
                continue
            standardized: dict[str, Any] = self._standardize_series(item)
            existing: dict[str, Any] | None = merged.get(key)
            if existing is None:
                merged[key] = standardized
                continue
            existing["datapoints"] = self._merge_datapoints(
                existing.get("datapoints") or [], standardized.get("datapoints") or []
            )
        return list(merged.values())

    @staticmethod
    def _merge_datapoints(left: list[list[Any]], right: list[list[Any]]) -> list[list[Any]]:
        points: dict[Any, float] = {timestamp: value for value, timestamp in left}
        for value, timestamp in right:
            points[timestamp] = (points.get(timestamp) or 0) + value
        return [[value, timestamp] for timestamp, value in sorted(points.items())]

    def _merge_storage_records(
        self,
        records: list[dict[str, Any]],
        *,
        is_time_bucketed: bool,
        bucket_delta_ms: int,
    ) -> dict[tuple, tuple[float, int, tuple, int | None]]:
        """按标准维度（及对齐后的桶时间）合并存储侧返回的聚合记录。"""
        merged: dict[tuple, tuple[float, int, tuple, int | None]] = {}
        for record in records:
            key: tuple = self._dimension_key(record)
            if self._should_drop_operation_dimension(key):
                continue
            value: float = record.get("_result_") or 0
            raw_time: int | None = record.get("_time_")
            time_: int | None = (
                (raw_time - bucket_delta_ms if raw_time is not None else None) if is_time_bucketed else raw_time
            )
            merge_key: tuple = (*key, time_) if is_time_bucketed else key
            if merge_key in merged:
                prev_value, prev_count, _, prev_time = merged[merge_key]
                merged[merge_key] = (
                    prev_value + value,
                    prev_count + 1,
                    key,
                    time_ if time_ is not None else prev_time,
                )
            else:
                merged[merge_key] = (value, 1, key, time_)
        return merged

    def _aggregate(
        self,
        aggregation: Aggregation,
        start_time: int | None = None,
        end_time: int | None = None,
        interval: int | None = None,
    ) -> list[dict[str, Any]]:
        """聚合出区间标量或按时间分桶的序列，每个有样本的维度（及时间桶）一条记录。"""
        shifted_start, shifted_end = self._shift(start_time, end_time)
        is_time_bucketed: bool = LLMQuery.TIME_BUCKET_FIELD in self.group_by
        resolved_interval: int | None = None
        bucket_delta_ms: int = 0
        if is_time_bucketed:
            resolved_interval = interval or get_auto_interval(
                self.COLLECT_INTERVAL,
                start_time or 0,
                end_time or 0,
                factor=self.INTERVAL_FACTOR,
            )
            if self.time_shift and start_time is not None and shifted_start is not None:
                bucket_delta_ms = (
                    time_interval_align(shifted_start, resolved_interval)
                    - time_interval_align(start_time, resolved_interval)
                ) * MILLISECONDS_PER_SECOND

        if self._is_local_aggregation(aggregation):
            if is_time_bucketed and resolved_interval is not None:
                bucket_totals: dict[tuple[tuple, int], float] = defaultdict(float)
                for record in self._usage_records(aggregation.layer, shifted_start, shifted_end, (OtlpKey.START_TIME,)):
                    key: tuple = self._dimension_key(record)
                    if self._should_drop_operation_dimension(key):
                        continue
                    seconds: int = (record.get(OtlpKey.START_TIME) or 0) // MICROSECONDS_PER_SECOND
                    bucket_ms: int = (
                        time_interval_align(seconds, resolved_interval) * MILLISECONDS_PER_SECOND - bucket_delta_ms
                    )
                    bucket_totals[(key, bucket_ms)] += self._usage_value(record, aggregation)
                return [
                    self._record(key, value, shifted_end, bucket_ms)
                    for (key, bucket_ms), value in sorted(bucket_totals.items(), key=lambda item: item[0][1])
                ]

            totals: dict[tuple, float] = defaultdict(float)
            for record in self._usage_records(aggregation.layer, shifted_start, shifted_end):
                key = self._dimension_key(record)
                if self._should_drop_operation_dimension(key):
                    continue
                totals[key] += self._usage_value(record, aggregation)
            return [self._record(key, value, shifted_end) for key, value in totals.items()]

        queries: list[QueryConfigBuilder] = self._queries(aggregation.layer)
        fields: list[str] = self._fields(aggregation)
        query_kwargs: dict[str, Any] = {"interval": resolved_interval} if resolved_interval is not None else {}

        if is_time_bucketed and aggregation.method in {"SUM", "AVG"}:
            # ES date_histogram 会为无样本桶补 0；按同层样本数 COUNT > 0 区分真实零值桶与无样本空桶
            val_merged = self._merge_storage_records(
                self.query.query_field_aggregated_group(
                    queries, shifted_start, shifted_end, fields, aggregation.method, self.group_fields, **query_kwargs
                ),
                is_time_bucketed=True,
                bucket_delta_ms=bucket_delta_ms,
            )
            count_fields: list[str] = ["_index"] if aggregation.method == "SUM" else fields
            count_merged = self._merge_storage_records(
                self.query.query_field_aggregated_group(
                    queries, shifted_start, shifted_end, count_fields, "COUNT", self.group_fields, **query_kwargs
                ),
                is_time_bucketed=True,
                bucket_delta_ms=bucket_delta_ms,
            )
            return [
                self._record(
                    key,
                    (
                        val_merged[merge_key][0] / val_merged[merge_key][1]
                        if aggregation.method == "AVG"
                        else val_merged[merge_key][0]
                    )
                    if merge_key in val_merged
                    else 0.0,
                    shifted_end,
                    time_,
                )
                for merge_key, (sample_count, _, key, time_) in count_merged.items()
                if sample_count > 0
            ]

        # COUNT / DISTINCT 分桶下值为 0 即无匹配样本
        merged = self._merge_storage_records(
            self.query.query_field_aggregated_group(
                queries, shifted_start, shifted_end, fields, aggregation.method, self.group_fields, **query_kwargs
            ),
            is_time_bucketed=is_time_bucketed,
            bucket_delta_ms=bucket_delta_ms,
        )
        return [
            self._record(key, value / count if aggregation.method == "AVG" else value, shifted_end, time_)
            for value, count, key, time_ in merged.values()
            if not is_time_bucketed or value > 0
        ]

    def _record(self, key: tuple, value: float, end_time: int | None, time_: int | None = None) -> dict[str, Any]:
        """区间聚合出的点统一戳在窗口右端，调用方按维度取值，不依赖该时间。"""
        return {
            "_time_": time_ if time_ is not None else (end_time or 0) * self.query.TIME_FIELD_ACCURACY,
            "_result_": value,
            **self._dimensions(key),
        }

    def _build_series(self, points: dict[tuple, dict[int, float]]) -> list[dict[str, Any]]:
        return [
            {
                "datapoints": [[value, timestamp] for timestamp, value in sorted(timestamps.items())],
                "dimensions": self._dimensions(key),
                "target": next(iter(key), ""),
            }
            for key, timestamps in points.items()
        ]

    def _local_series(
        self, aggregation: Aggregation, start_time: int | None, end_time: int | None, interval: int
    ) -> list[dict[str, Any]]:
        """本地按 interval 分桶，空桶补零，与存储侧出图的点位保持一致。

        只保留有数据的桶会让曲线退化成零星几个点，存储侧出图时由 null_as_zero 补齐，这里同样补。
        """
        empty: dict[int, float] = {
            bucket * MILLISECONDS_PER_SECOND: 0.0
            for bucket in range((start_time or 0) // interval * interval, end_time or 0, interval)
        }
        points: dict[tuple, dict[int, float]] = defaultdict(lambda: defaultdict(float, empty))
        for record in self._usage_records(aggregation.layer, start_time, end_time, (OtlpKey.START_TIME,)):
            key: tuple = self._dimension_key(record)
            if self._should_drop_operation_dimension(key):
                continue
            seconds: int = (record.get(OtlpKey.START_TIME) or 0) // MICROSECONDS_PER_SECOND
            bucket: int = seconds // interval * interval * MILLISECONDS_PER_SECOND
            points[key][bucket] += self._usage_value(record, aggregation)
        return self._build_series(points)

    def _is_local_aggregation(self, aggregation: Aggregation) -> bool:
        """Langfuse 的 Token 存在 JSON 串里，存储侧聚合不了，只能取回原始值本地算。"""
        return self.product == LLMProduct.LANGFUSE.value and bool(aggregation.slots)

    def _usage_records(
        self, layer: str | None, start_time: int | None, end_time: int | None, extra_fields: tuple[str, ...] = ()
    ) -> list[dict[str, Any]]:
        group_fields: list[str] = [field for field, _ in self.dimension_fields]
        fields: list[str] = [self.LANGFUSE_USAGE_FIELD, *group_fields, *extra_fields]
        queries: list[QueryConfigBuilder] = self._queries(layer)
        trace_ids: list[str] = self.filter_dict.get("trace_id__eq") or []
        if not trace_ids:
            return self.query.query_field_values(queries, start_time, end_time, fields, self.query.QUERY_MAX_LIMIT)
        # JSON 用量仍是一条模型 Span 一行，沿用原始查询的 ID 批次，避免多会话共用一页上限。
        records: list[dict[str, Any]] = []
        for index in range(0, len(trace_ids), self.query.GROUP_ID_BATCH_SIZE):
            chunk: list[str] = trace_ids[index : index + self.query.GROUP_ID_BATCH_SIZE]
            records.extend(
                self.query.query_field_values(
                    [query.filter(trace_id__eq=chunk) for query in queries],
                    start_time,
                    end_time,
                    fields,
                    self.query.QUERY_MAX_LIMIT,
                )
            )
        return records

    def _usage_value(self, record: dict[str, Any], aggregation: Aggregation) -> float:
        usage: dict[str, Any] = self._parse_usage(record.get(self.LANGFUSE_USAGE_FIELD))
        return sum(usage.get(key) or 0 for slot in aggregation.slots for key in self.LANGFUSE_USAGE_KEYS[slot])

    @staticmethod
    def _parse_usage(raw: Any) -> dict[str, Any]:
        if not isinstance(raw, str) or not raw:
            return {}
        try:
            usage = json.loads(raw)
        except ValueError:
            logger.warning("[LLM] 无法解析 Langfuse usage_details: %s", raw[:128])
            return {}
        return usage if isinstance(usage, dict) else {}
