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
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from typing import Any

from django.utils.translation import gettext_lazy as _


from apm.utils.ui_optimizations import HistogramNiceNumberGenerator
from bkmonitor.data_source.utils import types
from bkmonitor.utils.elasticsearch.handler import QueryStringGenerator
from constants.apm import OperatorGroupRelation
from constants.otel_query import (
    EnabledStatisticsDimension,
    OperatorEnum,
    StatisticsProperty,
)
from bkmonitor.data_source.utils.apm import FilterOperator, TraceDatasourceTarget
from bkmonitor.utils.common_utils import format_percent
from bkmonitor.utils.thread_backend import ThreadPool
from core.drf_resource import resource
from semconv.rum.constants import RumSpanType
from rum_web.handlers.level.base import BaseRumLevelHandler
from rum_web.handlers.query.span import SpanQuery
from rum_web.constants import RUM_SEARCH_PAGE_GROUPS


class SpanLevelHandler(BaseRumLevelHandler):
    """Span 层级处理器

    以 SpanQuery 作为主查询，实现 BaseRumLevelHandler 的全部接口能力。
    """

    DISPLAY_FIELDS = [
        "span_name",
        "attributes.span_type",
        "end_time",
        "elapsed_time",
        "status.code",
        "attributes.view.url_template",
        "attributes.user.id",
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
            "span_type_display_fields": {span_type.value: span_type.display_fields for span_type in RumSpanType},
        }

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
        return self.query.query_option_values(start_time, end_time, fields, limit, filters or [], query_string)

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
            topk_list.append({"value": bucket.get(field), "count": count, "proportions": proportions})

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
            exclude_empty_operator = (
                FilterOperator.EXISTS
                if EnabledStatisticsDimension.from_value(field["field_type"]).is_numeric()
                else FilterOperator.NOT_EQUAL
            )
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
            return resource.grafana.graph_unify_query(config)

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

    # ---------------- 内部工具方法 ----------------

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
