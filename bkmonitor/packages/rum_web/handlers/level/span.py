"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy
import bisect
import datetime
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from typing import Any

from django.utils.translation import gettext_lazy as _


from apm.utils.ui_optimizations import HistogramNiceNumberGenerator
from bkmonitor.data_source.utils import types
from bkmonitor.utils.elasticsearch.handler import QueryStringGenerator
from bkmonitor.utils.time_tools import parse_time_compare_abbreviation
from constants.apm import OperatorGroupRelation
from constants.otel_query import (
    AggregatedMethod,
    EnabledStatisticsDimension,
    OperatorEnum,
    StatisticsProperty,
)
from bkmonitor.data_source.utils.apm import FilterOperator, TraceDatasourceTarget
from bkmonitor.utils.common_utils import format_percent
from bkmonitor.utils.thread_backend import ThreadPool
from core.drf_resource import resource
from semconv.rum.constants import RumSpanType, SPAN_TYPE_COMMON_DISPLAY_FIELDS
from semconv.rum.trace import SpanSpec
from constants.otel_query import FieldTypeEnum
from rum_web.handlers.level.base import BaseRumLevelHandler
from rum_web.handlers.query.span import SpanQuery
from rum_web.constants import RUM_SEARCH_PAGE_GROUPS


class SpanLevelHandler(BaseRumLevelHandler):
    """Span 层级处理器

    以 SpanQuery 作为主查询，实现 BaseRumLevelHandler 的全部接口能力。
    """

    DISPLAY_FIELDS = [
        *SPAN_TYPE_COMMON_DISPLAY_FIELDS,
        "attributes.view.url_template",
        "elapsed_time",
        "resource.user_agent.name",
        "attributes.user.id",
    ]

    #: 常驻筛选字段，前端置顶展示并默认带出的筛选维度
    RESIDENT_FIELDS = [
        "attributes.session.id",
        "trace_id",
        "span_name",
        "resource.deployment.environment.name",
        "resource.user_agent.name",
        "attributes.view.url_template",
        "attributes.outcome.type",
        "attributes.user.id",
        "elapsed_time",
    ]
    VIEW_CONFIG_IGNORE_KEYS = ["is_case_sensitive", "is_analyzed", "wildcard_case_insensitive", "tokenize_on_chars"]

    BASE_STATISTICS_PROPERTIES: set[str] = {
        StatisticsProperty.TOTAL_COUNT.value,
        StatisticsProperty.FIELD_COUNT.value,
        StatisticsProperty.DISTINCT_COUNT.value,
    }

    #: 数值型统计属性（用于归类到 value_analysis）
    NUMERIC_STATISTICS_PROPERTIES: set[str] = {
        StatisticsProperty.MAX.value,
        StatisticsProperty.MIN.value,
        StatisticsProperty.MEDIAN.value,
        StatisticsProperty.AVG.value,
    }

    BOOLEAN_VALUE_TRANSFORM_MAP = {
        "1": True,
        "0": False,
        1: True,
        0: False,
        "true": True,
        "false": False,
        "True": True,
        "False": False,
    }

    #: 分组维度里表示时间分桶的 key，由 interval 触发
    STATISTICS_TIME_BUCKET_KEY: str = "time"

    def __init__(self, data_sources: list[TraceDatasourceTarget]):
        super().__init__(data_sources)
        self.query = SpanQuery(data_sources)

    def list_records(
        self,
        start_time: int,
        end_time: int,
        offset: int = 0,
        limit: int = 10,
        filters: list[types.Filter] | None = None,
        query_string: str = "",
        sort: list[str] | None = None,
        extra_config: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        return self.query.query_list(start_time, end_time, offset, limit, filters, query_string, sort)

    def view_config(
        self,
        start_time: int | None,
        end_time: int | None,
        extra_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        field_map: dict[str, Any] = self.query.query_fields(start_time, end_time)

        # 丢弃查询层私有键，其余字段直接透传给接口层
        for field_name, field_dict in field_map.items():
            for key in self.VIEW_CONFIG_IGNORE_KEYS:
                field_dict.pop(key, None)

        return {
            "default_sort": list(self.query.DEFAULT_SORT),
            "fields": list(field_map.values()),
            "groups": [
                {
                    "name": group["name"],
                    "alias": group["alias"],
                    "supported_span_types": group["supported_span_types"],
                    "field_names": [name for name in group["field_names"] if name in field_map],
                }
                for group in RUM_SEARCH_PAGE_GROUPS.get("span", [])
            ],
            "display_fields": list(self.DISPLAY_FIELDS),
            "resident_fields": list(self.RESIDENT_FIELDS),
            "span_type_resident_fields": {
                span_type.value: list(span_type.resident_fields) for span_type in RumSpanType
            },
            "span_type_display_fields": {span_type.value: span_type.display_fields for span_type in RumSpanType},
        }

    @classmethod
    def _value_transform(cls, field: str, value: str):
        span_spec = SpanSpec.from_field(field)
        if span_spec.field_type == FieldTypeEnum.BOOLEAN.value:
            return cls.BOOLEAN_VALUE_TRANSFORM_MAP.get(value, bool(value))
        return value

    def get_fields_option_values(
        self,
        start_time: int,
        end_time: int,
        fields: list[str],
        limit: int = 10,
        filters: list[types.Filter] | None = None,
        query_string: str = "",
        extra_config: dict[str, Any] | None = None,
    ) -> dict[str, list[str]]:
        result: dict[str, list[str]] = self.query.query_option_values(
            start_time, end_time, fields, limit, filters or [], query_string
        )
        for field, values in result.items():
            result[field] = [self._value_transform(field, value) for value in values]
        return result

    def field_topk(
        self,
        start_time: int,
        end_time: int,
        field: str,
        limit: int = 5,
        filters: list[types.Filter] | None = None,
        query_string: str = "",
        extra_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """查询字段 Top-K 值。

        并发计算 total_count（用于比例）、distinct_count（去重数）与 Top-K 桶列表，
        按协议组装 {"field", "distinct_count", "list": [{"value", "count", "proportions"}]}。
        """
        filters = filters or []

        results: dict[str, Any] = {}

        def _query_total():
            results["total"] = self.query.query_field_aggregated_value(
                start_time, end_time, field, "count", filters, query_string
            )

        def _query_distinct():
            results["distinct"] = self.query.query_field_aggregated_value(
                start_time, end_time, field, "distinct", filters, query_string
            )

        def _query_topk():
            results["topk"] = self.query.query_field_topk(start_time, end_time, field, limit, filters, query_string)

        ThreadPool().map_ignore_exception(lambda fn: fn(), [_query_total, _query_distinct, _query_topk])

        total_count: int = int(results.get("total") or 0)
        distinct_count: int = int(results.get("distinct") or 0)
        topk_buckets: list[dict[str, Any]] = results.get("topk") or []

        topk_list: list[dict[str, Any]] = []
        for bucket in topk_buckets:
            count = bucket.get("_result_", 0)
            proportions = format_percent(
                100 * count / total_count if total_count > 0 else 0,
                precision=3,
                sig_fig_cnt=3,
                readable_precision=3,
            )
            topk_list.append(
                {"value": self._value_transform(field, bucket.get(field)), "count": count, "proportions": proportions}
            )

        return {"field": field, "distinct_count": distinct_count, "list": topk_list}

    def field_statistics_info(
        self,
        start_time: int,
        end_time: int,
        field: dict[str, Any],
        filters: list[types.Filter] | None = None,
        query_string: str = "",
        extra_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """查询字段统计信息。

        - keyword 类型：返回 total_count、field_count、distinct_count、field_percent
        - 数值类型：额外补充 value_analysis: {max, min, avg, median}
        - 支持通过 extra_config["exclude_property"] 排除部分统计属性
        """
        filters = filters or []
        extra_config = extra_config or {}
        exclude_property: list[str] = extra_config.get("exclude_property") or []

        # 基础统计属性
        statistics_properties: set[str] = (
            self.BASE_STATISTICS_PROPERTIES | self.NUMERIC_STATISTICS_PROPERTIES
            if EnabledStatisticsDimension.from_value(field["field_type"]).is_numeric()
            else self.BASE_STATISTICS_PROPERTIES
        )
        target_properties: set[str] = statistics_properties - set(exclude_property)

        statistics_info: dict[str, Any] = {}
        ThreadPool().map_ignore_exception(
            lambda property_name: self._query_statistics_info(
                start_time, end_time, field, filters, query_string, property_name, statistics_info
            ),
            list(target_properties),
        )
        return self._process_statistics_info(statistics_info)

    def _query_statistics_info(
        self,
        start_time: int,
        end_time: int,
        field: dict[str, Any],
        filters: list[types.Filter],
        query_string: str,
        property_name: str,
        statistics_info: dict[str, Any],
    ) -> None:
        method_mapping = StatisticsProperty.method_mapping()
        if property_name not in method_mapping:
            raise ValueError(_("未知的字段统计属性: {}").format(property_name))

        field_name: str = field["field_name"]
        query_filters: list[types.Filter] = copy.deepcopy(filters)
        # 字段计数：排除空值。数值类型使用 exists 判断，其他类型排除空字符串。
        if property_name == StatisticsProperty.FIELD_COUNT.value:
            use_exists = (
                EnabledStatisticsDimension.from_value(field["field_type"]).is_numeric()
                or field["field_type"] == EnabledStatisticsDimension.BOOLEAN.value
            )
            exclude_empty_operator = FilterOperator.EXISTS if use_exists else FilterOperator.NOT_EQUAL
            query_filters.append({"key": field_name, "value": [""], "operator": exclude_empty_operator})

        # TOTAL_COUNT 使用 _index 计数，确保分母包含所有 Span（含缺失该字段的记录）
        query_field = "_index" if property_name == StatisticsProperty.TOTAL_COUNT.value else field_name
        statistics_info[property_name] = self.query.query_field_aggregated_value(
            start_time,
            end_time,
            query_field,
            method_mapping[property_name],
            query_filters,
            query_string,
        )

    @classmethod
    def _process_statistics_info(cls, statistics_info: dict[str, Any]) -> dict[str, Any]:
        processed: dict[str, Any] = {}
        # 分类并处理结果
        for statistics_property, value in statistics_info.items():
            value = format_percent(value, 3, 3, 3)
            if statistics_property in cls.NUMERIC_STATISTICS_PROPERTIES:
                processed.setdefault("value_analysis", {})[statistics_property] = value
                continue
            processed[statistics_property] = value

        # 计算字段占比
        if (
            StatisticsProperty.FIELD_COUNT.value in statistics_info
            and StatisticsProperty.TOTAL_COUNT.value in statistics_info
        ):
            field_percent = 0
            total_count = statistics_info[StatisticsProperty.TOTAL_COUNT.value]
            if total_count > 0:
                field_percent = statistics_info[StatisticsProperty.FIELD_COUNT.value] / total_count * 100
            processed["field_percent"] = format_percent(field_percent, 3, 3, 3)
        return processed

    def field_statistics_graph(
        self,
        start_time: int,
        end_time: int,
        field: dict[str, Any],
        filters: list[types.Filter] | None = None,
        query_string: str = "",
        extra_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """查询字段统计图表。

        - keyword 类型：按取值分组构建时序图（走 grafana.graph_unify_query）
        - 数值类型：根据 min/max/distinct_count/interval_num 划分区间，并发统计各区间计数
        """
        filters = filters or []
        field_name: str = field["field_name"]
        values: list[Any] = field.get("values") or []

        field_type_enum = EnabledStatisticsDimension.from_value(field["field_type"])
        # 非数值类型（keyword）：按取值分组构建时序图
        if not field_type_enum.is_numeric():
            keyword_filters = filters + [{"key": field_name, "value": values, "operator": FilterOperator.EQUAL}]
            config = self.query.query_graph_config(start_time, end_time, field_name, keyword_filters, query_string)
            config.update(
                {
                    "time_alignment": False,
                    "query_method": "query_reference",
                    "null_as_zero": True,
                    "start_time": config["start_time"] // 1000,
                    "end_time": config["end_time"] // 1000,
                }
            )
            data: dict[str, Any] = resource.grafana.graph_unify_query(config)
            if field["field_type"] != EnabledStatisticsDimension.BOOLEAN.value:
                return data
            series: list[dict[str, Any]] = data.get("series", [])
            for s in series:
                s.setdefault("dimensions", {})[field_name] = self._value_transform(
                    field_name, s["dimensions"].get(field_name)
                )

            return data

        # 数值类型：values 至少 4 项 [min_value, max_value, distinct_count, interval_num]
        min_value, max_value, distinct_count, interval_num = values[:4]
        if min_value is None or max_value is None or interval_num is None:
            return self._process_graph_info([])

        # 字段枚举数量小于等于区间数量，或 INTEGER / LONG 类型的区间最大数量小于等于区间数，直接查询枚举值返回
        use_discrete_values = distinct_count is not None and distinct_count <= interval_num
        if field_type_enum.is_integer():
            use_discrete_values |= (max_value - min_value + 1) <= interval_num

        if use_discrete_values:
            topk_buckets = self.query.query_field_topk(
                start_time, end_time, field_name, distinct_count, filters, query_string
            )
            value_parser = float if field_type_enum.is_float() else int
            datapoints: list[list[int | float]] = [
                [bucket.get("_result_", 0), value_parser(bucket[field_name])] for bucket in topk_buckets
            ]
            datapoints.sort(key=lambda b: b[1])
            return self._process_graph_info(datapoints)

        intervals = self._calculate_intervals(min_value, max_value, interval_num, field["field_type"])
        return self._process_graph_info(
            self._calculate_interval_buckets(start_time, end_time, field_name, filters, query_string, intervals)
        )

    def record_detail(
        self,
        record_id: str,
        extra_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    def statistics(
        self,
        start_time: int | None,
        end_time: int | None,
        field: str,
        cal_type: str,
        baseline: str,
        time_shifts: list[str],
        group_by: list[str] | None = None,
        interval: int | None = None,
        filters: list[types.Filter] | None = None,
        query_string: str = "",
        extra_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """数据统计：多时间偏移聚合查询。

        - 传入 ``interval`` 走 ``query_fields_graph_config``（时间分桶）；否则走 ``query_fields_aggregated_group``。
        - 时间统一透传（可为 None，由查询层按保留期补齐），不再在此处解析/偏移时间窗口，
          多时间偏移对比交由统一查询层处理。
        - 按维度合并各时间偏移的结果，基于 baseline 计算 growth_rates。
        - cal_type=count 时按每个时间偏移维度的总量计算 proportions。
        """
        filters = filters or []
        group_by = group_by or []
        alias_records_map: dict[str, list[dict[str, Any]]] = {}
        use_time_bucket: bool = interval is not None
        now: int = int(datetime.datetime.now().timestamp())
        dimension_fields: list[str] = [
            field_name for field_name in group_by if field_name != self.STATISTICS_TIME_BUCKET_KEY
        ]

        def _collect(time_shift: str) -> None:
            offset_seconds: int = parse_time_compare_abbreviation(time_shift)
            shifted_start: int | None = start_time - offset_seconds if start_time else start_time
            shifted_end: int = end_time - offset_seconds if end_time else now - offset_seconds
            if use_time_bucket:
                alias_records_map[time_shift] = self._query_statistics_time_bucket(
                    shifted_start, shifted_end, field, cal_type, interval, dimension_fields, filters, query_string
                )
            else:
                alias_records_map[time_shift] = self.query.query_fields_aggregated_group(
                    shifted_start,
                    shifted_end,
                    [field],
                    cal_type,
                    group_by=dimension_fields,
                    filters=filters,
                    query_string=query_string,
                )

        ThreadPool().map_ignore_exception(_collect, list(time_shifts))

        merged_records: list[dict[str, Any]] = self._merge_statistics_records(
            dimension_fields,
            use_time_bucket,
            time_shifts,
            alias_records_map,
        )
        self._process_statistics_growth_rates(baseline, time_shifts, merged_records)
        if cal_type == AggregatedMethod.COUNT.value:
            self._process_statistics_proportions(time_shifts, merged_records)

        return {"total": len(merged_records), "data": merged_records}

    def _query_statistics_time_bucket(
        self,
        start_time: int | None,
        end_time: int | None,
        field: str,
        cal_type: str,
        interval: int,
        dimension_fields: list[str],
        filters: list[types.Filter],
        query_string: str,
    ) -> list[dict[str, Any]]:
        """时间分桶场景：基于 query_fields_graph_config 走 graph_unify_query 拉取时序，再按桶落点。

        graph_unify_query 的 series[*].datapoints 为 [[value, timestamp_ms], ...]，
        按维度聚合后按 interval 把每个点归入对应桶起点（秒级），最终输出与分组场景一致的结构。

        输入数据结构：
            start_time / end_time: 查询时间范围，Unix 秒级时间戳，允许为 None（由下游决定默认值）
            field: 聚合字段名，如 "duration"
            cal_type: 聚合方式，如 "count" / "avg" / "sum" 等
            interval: 分桶间隔，单位秒，如 60 表示按分钟分桶
            dimension_fields: 维度字段名列表，如 ["service_name", "span_name"]
            filters: 过滤条件列表，元素结构见 types.Filter
            query_string: 附加的 query_string 表达式

        中间数据结构（graph_unify_query 返回）：
            {
                "series": [
                    {
                        "dimensions": {
                            "<dim_field_1>": <value>,
                            "<dim_field_2>": <value>,
                            ...
                        },
                        "datapoints": [
                            [<value>, <timestamp_ms>],  # value 可能为 None，需过滤
                            ...
                        ],
                    },
                    ...
                ],
                ...
            }

        输出数据结构：
            list[dict]，每个 dict 形如
                {
                    "<dim_field_1>": <value>,
                    "<dim_field_2>": <value>,
                    "time": 1737532800000,   # 桶起点，单位 ms（STATISTICS_TIME_BUCKET_KEY）
                    "_result_": 123,          # 同一 (维度..., 桶起点) 下的累计聚合值
                }
            相同 (维度..., 桶起点) 的点会累加到同一条 record 上。
        """
        config = self.query.query_fields_graph_config(
            start_time,
            end_time,
            [field],
            cal_type,
            interval,
            group_by=dimension_fields,
            filters=filters,
            query_string=query_string,
        )
        data: dict[str, Any] = resource.grafana.graph_unify_query(config)

        # (维度字段, 桶起点) -> 累计 record，直接在最终结构上累加 _result_，省去二次展平
        bucket_records: dict[tuple[tuple, int], dict[str, Any]] = {}
        for series in data.get("series", []):
            dimension_kv: tuple[tuple[str, Any], ...] = tuple(
                (field_name, field_value)
                for field_name, field_value in (series.get("dimensions") or {}).items()
                if field_name in dimension_fields
            )
            for point_value, timestamp_ms in series.get("datapoints", []):
                if point_value is None:
                    continue
                bucket_start: int = timestamp_ms // 1000
                record = bucket_records.setdefault(
                    (dimension_kv, bucket_start),
                    {
                        **dict(dimension_kv),
                        self.STATISTICS_TIME_BUCKET_KEY: bucket_start * 1000,
                        "_result_": 0,
                    },
                )
                record["_result_"] += point_value
        return list(bucket_records.values())

    @classmethod
    def _merge_statistics_records(
        cls,
        dimension_fields: list[str],
        use_time_bucket: bool,
        time_shifts: list[str],
        alias_records_map: dict[str, list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        """按维度合并各时间偏移的聚合结果。

        时间分桶结果的桶起点写入 dimensions.time，unify_query 返回的 _time_ 单位为毫秒，
        统一转成 Unix 秒级时间戳后再作为维度合并键，避免各时间偏移间因毫秒漂移错位。

        输入数据结构：
            dimension_fields: 维度字段名列表，如 ["service_name", "span_name"]
            use_time_bucket: 是否为时间分桶场景，True 时按 (维度..., time) 合并，
                             False 时仅按维度合并
            time_shifts: 时间偏移别名列表，如 ["0s", "1d", "7d"]，同时作为
                         alias_records_map 的 key
            alias_records_map: 各时间偏移对应的聚合记录列表，形如
                {
                    "0s": [
                        {
                            "<dim_field_1>": <value>,
                            "<dim_field_2>": <value>,
                            "time": 1737532800000,   # 仅 use_time_bucket=True 时存在，单位 ms
                            "_result_": 123,          # 聚合值
                        },
                        ...
                    ],
                    "1d": [...],
                }

        输出数据结构：
            list[dict]，每个 dict 形如
                {
                    "dimensions": {
                        "<dim_field_1>": <value>,
                        "<dim_field_2>": <value>,
                        "time": 1737532800,          # 仅 use_time_bucket=True 时存在，单位 s
                    },
                    "0s": 123,                   # 各 time_shift 对应的聚合值，缺失为 None
                    "1d": 100,
                    "7d": None,
                }
        """
        group_key_record_map: dict[tuple, dict[str, Any]] = {}
        for time_shift, records in alias_records_map.items():
            for record in records:
                dimension_kv: list[tuple[str, Any]] = [
                    (field_name, record.get(field_name) or "") for field_name in dimension_fields
                ]
                if use_time_bucket:
                    dimension_kv.append(
                        (cls.STATISTICS_TIME_BUCKET_KEY, record[cls.STATISTICS_TIME_BUCKET_KEY] // 1000)
                    )
                group_key: tuple = tuple(dimension_kv)
                merged_record = group_key_record_map.setdefault(
                    group_key,
                    {"dimensions": dict(dimension_kv), **dict.fromkeys(time_shifts)},
                )
                merged_record[time_shift] = record.get("_result_")
        return list(group_key_record_map.values())

    @staticmethod
    def _process_statistics_growth_rates(baseline: str, time_shifts: list[str], records: list[dict[str, Any]]) -> None:
        """基于 baseline 计算各时间偏移的增长率（百分比数值）。

        - baseline 或对比点缺数据时（值为 None）无法计算，增长率记为 None
        - 两个都为 0 时增长率为 0
        - 一端为 0 且另一端非 0 时视作 100%（正负号取决于方向）
        - 其余按 (baseline - shift) / shift * 100 计算
        """
        for record in records:
            base_value = record.get(baseline)
            growth_rates: dict[str, float | None] = {}
            for time_shift in time_shifts:
                shift_value = record.get(time_shift)
                if base_value is None or shift_value is None:
                    growth_rates[time_shift] = None
                elif base_value == 0 and shift_value == 0:
                    growth_rates[time_shift] = 0
                elif shift_value == 0:
                    growth_rates[time_shift] = 100
                elif base_value == 0:
                    growth_rates[time_shift] = -100
                else:
                    growth_rates[time_shift] = format_percent(
                        (base_value - shift_value) / shift_value * 100,
                        precision=2,
                        sig_fig_cnt=1,
                        readable_precision=4,
                    )
            record["growth_rates"] = growth_rates

    @staticmethod
    def _process_statistics_proportions(time_shifts: list[str], records: list[dict[str, Any]]) -> None:
        """cal_type=count 时按每个时间偏移的总量计算 proportions（百分比数值）。"""
        totals: dict[str, float] = {time_shift: 0 for time_shift in time_shifts}
        for record in records:
            for time_shift in time_shifts:
                totals[time_shift] += record.get(time_shift) or 0

        for record in records:
            proportions: dict[str, float | None] = {}
            for time_shift in time_shifts:
                total = totals[time_shift]
                value = record.get(time_shift)
                if not total or value is None:
                    proportions[time_shift] = None
                    continue
                proportions[time_shift] = format_percent(
                    value / total * 100, precision=2, sig_fig_cnt=1, readable_precision=4
                )
            record["proportions"] = proportions

    @staticmethod
    def _process_graph_info(datapoints: list[list[Any]]) -> dict[str, Any]:
        """处理数值趋势图格式，和时序趋势图保持一致。

        如果只有一个 bucket，且数据为 0，则返回空数据。
        """
        if len(datapoints) == 1 and datapoints[0][0] == 0:
            datapoints = []
        return {"series": [{"datapoints": datapoints}]}

    @staticmethod
    def _calculate_intervals(
        min_value: int | float,
        max_value: int | float,
        interval_num: int,
        field_type: str = "",
    ) -> list[tuple[int | float, int | float]]:
        """计算区间列表，每个元素为 [左闭右开) 区间 (min, max)。

        - integer / long：使用整数 nice number 生成器。
        - double / float：使用 Decimal 计算支持小数的 nice bucket size，避免精度丢失。
        """
        if EnabledStatisticsDimension.from_value(field_type).is_integer():
            left_x, _right_x, bucket_size, num_buckets = HistogramNiceNumberGenerator.align_histogram_bounds(
                min_value, max_value, interval_num
            )
            return [(left_x + i * bucket_size, left_x + (i + 1) * bucket_size) for i in range(num_buckets)]

        d_min = Decimal(str(min_value))
        d_max = Decimal(str(max_value))
        raw_size = (d_max - d_min) / interval_num

        magnitude = (
            Decimal(10) ** raw_size.adjusted()
        )  # 对应 raw_size 的数量级, 比如 1.5 -> 0 -> 10 ** 0, 15 -> 1 -> 10 ** 1
        normalized_size = raw_size / magnitude  # 归一化到 10 的区间
        _NICE_FACTORS = [Decimal("1"), Decimal("2"), Decimal("2.5"), Decimal("4"), Decimal("5"), Decimal("10")]

        factor = _NICE_FACTORS[bisect.bisect_left(_NICE_FACTORS, normalized_size)]
        bucket_size = factor * magnitude

        left = (d_min / bucket_size).to_integral_value(rounding=ROUND_FLOOR) * bucket_size
        right = (d_max / bucket_size).to_integral_value(rounding=ROUND_CEILING) * bucket_size
        if right == d_max:
            right += bucket_size

        def _to_number(d: Decimal) -> int | float:
            """Decimal 转为 int 或 float，整数值返回 int 避免冗余小数点。"""
            return int(d) if d == d.to_integral_value() else float(d)

        bucket_count = int((right - left) / bucket_size)
        return [
            (_to_number(left + index * bucket_size), _to_number(left + (index + 1) * bucket_size))
            for index in range(bucket_count)
        ]

    def _calculate_interval_buckets(
        self,
        start_time: int,
        end_time: int,
        field_name: str,
        filters: list[types.Filter],
        query_string: str,
        intervals: list[tuple[int, int]],
    ) -> list[list[Any]]:
        """并发统计各区间计数，返回按区间起点升序排列的数据点列表。"""
        buckets: list[tuple[int, list[Any]]] = []

        def _collect(left: int, right: int):
            interval_filters = filters + [
                {"key": field_name, "value": [left, right], "operator": FilterOperator.BETWEEN}
            ]
            interval_count = self.query.query_field_aggregated_value(
                start_time, end_time, "_index", "count", interval_filters, query_string
            )
            buckets.append((left, [int(interval_count or 0), f"{left}-{right}"]))

        ThreadPool().map_ignore_exception(_collect, intervals)
        buckets.sort(key=lambda item: item[0])
        return [data_point for _start, data_point in buckets]

    def generate_query_string(
        self,
        filters: list[types.Filter],
        extra_config: dict[str, Any] | None = None,
    ) -> str:
        generator = QueryStringGenerator(OperatorEnum.QueryStringOperatorMapping)
        for f in filters:
            generator.add_filter(
                f["key"],
                f["operator"],
                f["value"],
                f.get("options", {}).get("is_wildcard", False),
                f.get("options", {}).get("group_relation", OperatorGroupRelation.OR),
            )
        return generator.to_query_string()
