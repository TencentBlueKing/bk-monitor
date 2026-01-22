"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import abc
import copy
import logging
import threading
from collections import defaultdict
from threading import Lock
from typing import Any

from django.db.models import Q
from django.utils.translation import gettext_lazy as _


from bkmonitor.data_source.data_source import dict_to_q, q_to_dict
from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder, UnifyQuerySet
from bkmonitor.models import MetricListCache
from bkmonitor.utils.common_utils import format_percent
from bkmonitor.utils.elasticsearch.handler import QueryStringGenerator
from bkmonitor.utils.request import get_request_tenant_id
from bkmonitor.utils.thread_backend import InheritParentThread, run_threads
from core.drf_resource import FaultTolerantResource, resource

from . import serializers
from .constants import (
    BK_BIZ_ID,
    BK_BIZ_ID_DEFAULT_DATA_LABEL,
    BK_BIZ_ID_DEFAULT_TABLE_ID,
    CATEGORY_WEIGHTS,
    DEFAULT_DIMENSION_FIELDS,
    DIMENSION_DISTINCT_VALUE,
    DISPLAY_FIELDS,
    ENTITIES,
    INNER_FIELD_TYPE_MAPPINGS,
    QUERY_MAX_LIMIT,
    TYPE_OPERATION_MAPPINGS,
    Operation,
    CategoryWeight,
    EventCategory,
    EventDimensionTypeEnum,
    EventType,
    EVENT_ORIGIN_MAPPING,
    DEFAULT_EVENT_ORIGIN,
    SYSTEM_EVENT_TRANSLATIONS,
    EventDomain,
    K8S_EVENT_TRANSLATIONS,
    CicdEventName,
    EventSource,
)
from .core.processors import (
    BaseEventProcessor,
    CicdEventProcessor,
    HostEventProcessor,
    OriginEventProcessor,
)
from .core.processors.context import (
    BcsClusterContext,
    CicdPipelineContext,
    SystemClusterContext,
)
from .core.processors.k8s import K8sEventProcessor
from .utils import (
    get_data_labels_map,
    get_field_alias,
    get_q_from_query_config,
    get_qs_from_req_data,
    is_dimensions,
    format_field,
    sort_fields,
)

logger = logging.getLogger(__name__)


class EventBaseResource(FaultTolerantResource, abc.ABC):
    @classmethod
    def is_return_default_early(cls, validated_request_data: dict[str, Any]) -> bool:
        """判断是否提前返回默认数据"""
        return not validated_request_data.get("query_configs")


class EventTimeSeriesResource(EventBaseResource):
    DEFAULT_RESPONSE_DATA = {}
    RequestSerializer = serializers.EventTimeSeriesRequestSerializer

    def perform_request(self, validated_request_data: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = resource.grafana.graph_unify_query(validated_request_data)
        for series in result["series"]:
            dimensions = series["dimensions"]
            if "type" in dimensions and not dimensions["type"].strip():
                dimensions["type"] = EventType.Default.value
        result["query_config"] = validated_request_data
        return result


class EventLogsResource(EventBaseResource):
    DEFAULT_SORT = ["-time"]
    DEFAULT_RESPONSE_DATA = {"list": []}
    RequestSerializer = serializers.EventLogsRequestSerializer

    def perform_request(self, validated_request_data: dict[str, Any]) -> dict[str, Any]:
        # 构建统一查询集
        queryset = (
            get_qs_from_req_data(validated_request_data)
            .time_agg(False)
            .instant()
            .limit(validated_request_data["limit"])
            .offset(validated_request_data["offset"])
        )
        # Q：为什么不在序列化器增加默认值？
        # A：EventLogsResource 存在内部调用场景。
        processed_sort_fields = self.process_sort_fields(validated_request_data.get("sort") or self.DEFAULT_SORT)

        # 添加查询到查询集中
        for query in [
            get_q_from_query_config(query_config) for query_config in validated_request_data["query_configs"]
        ]:
            queryset = queryset.add_query(query.order_by(*processed_sort_fields))

        events: list[dict[str, Any]] = list(queryset)
        processors: list[BaseEventProcessor] = [
            OriginEventProcessor(),
            K8sEventProcessor(BcsClusterContext()),
            HostEventProcessor(SystemClusterContext()),
            CicdEventProcessor(CicdPipelineContext()),
        ]
        for processor in processors:
            events = processor.process(events)

        return {
            "list": sort_fields(events, processed_sort_fields, extractor=lambda item: item.get("origin_data")),
            # 返回查询配置，用于检索跳转。
            "query_config": validated_request_data,
        }

    @classmethod
    def process_sort_fields(cls, fields):
        """
        预处理排序字段列表，为字段添加前缀，并调整字段排序格式

        :param fields: 原始排序字段列表，如 ["-time", "name"]
        :return: 处理后的排序字段列表，如 ["time desc", "dimensions.name"]
        """
        processed_fields = []
        for field in fields:
            # 提取字段名（去掉可能的 "-" 前缀）
            is_descending = field.startswith("-")
            field = field[1:] if is_descending else field
            # 是否是内置字段,不是添加 dimensions. 前缀
            field = format_field(field)

            # 保留原始排序方向
            if is_descending:
                processed_fields.append(f"{field} desc")
            else:
                processed_fields.append(field)
        return processed_fields


class EventViewConfigResource(EventBaseResource):
    DEFAULT_RESPONSE_DATA = {"display_fields": [], "entities": [], "field": []}
    RequestSerializer = serializers.EventViewConfigRequestSerializer

    @classmethod
    def is_return_default_early(cls, validated_request_data: dict[str, Any]) -> bool:
        return not validated_request_data.get("data_sources")

    def perform_request(self, validated_request_data: dict[str, Any]) -> dict[str, Any]:
        tables = [data_source["table"] for data_source in validated_request_data["data_sources"]]
        dimension_metadata_map = self.get_dimension_metadata_map(validated_request_data["bk_biz_id"], tables)
        fields = self.sort_fields(dimension_metadata_map)
        return {"display_fields": DISPLAY_FIELDS, "entities": ENTITIES, "field": fields}

    @classmethod
    def get_dimension_metadata_map(cls, bk_biz_id: int, tables):
        # 维度元数据集
        data_labels_map = get_data_labels_map(bk_biz_id, tuple(sorted(tables)))
        dimensions_queryset = MetricListCache.objects.filter(
            result_table_id__in=data_labels_map.keys(),
            bk_tenant_id=get_request_tenant_id(),
        ).values("dimensions", "result_table_id")
        dimension_metadata_map = {
            default_dimension_field: {"table_ids": set(), "data_labels": set()}
            for default_dimension_field in DEFAULT_DIMENSION_FIELDS
        }
        dimension_metadata_map.setdefault(BK_BIZ_ID, {}).setdefault("table_ids", set()).add(BK_BIZ_ID_DEFAULT_TABLE_ID)
        dimension_metadata_map.setdefault(BK_BIZ_ID, {}).setdefault("data_labels", set()).add(
            BK_BIZ_ID_DEFAULT_DATA_LABEL
        )

        # 遍历查询集并聚合数据
        for dimension_entry in dimensions_queryset:
            dimensions = dimension_entry["dimensions"]
            table_id = dimension_entry["result_table_id"]
            # 如果维度查询的 table_id 在 result_table 中查询不到，默认设置该 table_id 对应的维度的事件类型为 UNKNOWN_EVENT
            data_label = data_labels_map.get(table_id, EventCategory.UNKNOWN_EVENT.value)

            for dimension in dimensions:
                dimension_metadata_map.setdefault(dimension["id"], {}).setdefault("table_ids", set()).add(table_id)
                dimension_metadata_map[dimension["id"]].setdefault("data_labels", set()).add(data_label)
        return dimension_metadata_map

    @classmethod
    def sort_fields(cls, dimension_metadata_map) -> list[dict[str, Any]]:
        fields = []
        for name, dimension_metadata in dimension_metadata_map.items():
            field_type = cls.get_field_type(name)
            data_labels = list(dimension_metadata["data_labels"])
            if data_labels:
                alias, field_category, index = get_field_alias(name, data_labels[0])
            else:
                # 内置字段，没有 data_labels，这里直接传 common
                alias, field_category, index = get_field_alias(name, EventCategory.COMMON.value)
            is_option_enabled = cls.is_option_enabled(field_type)
            supported_operations = cls.get_supported_operations(field_type)
            fields.append(
                {
                    "name": name,
                    "alias": alias,
                    "type": field_type,
                    "is_option_enabled": is_option_enabled,
                    "is_dimensions": is_dimensions(name),
                    "supported_operations": supported_operations,
                    "index": index,
                    "category": field_category,
                }
            )

        # 使用 category_weights 对 fields 进行排序
        fields.sort(
            key=lambda _f: CATEGORY_WEIGHTS.get(_f["category"], CategoryWeight.UNKNOWN.value) * 100 + _f["index"]
        )

        # 排序后除去权重字段
        for field in fields:
            del field["index"]
            del field["category"]
        return fields

    @classmethod
    def get_field_type(cls, field) -> str:
        """ "
        获取字段类型
        """
        # 自定义字段统一返回 keyword
        return INNER_FIELD_TYPE_MAPPINGS.get(field, EventDimensionTypeEnum.KEYWORD.value)

    @classmethod
    def is_option_enabled(cls, field_type) -> bool:
        return field_type in {EventDimensionTypeEnum.KEYWORD.value, EventDimensionTypeEnum.INTEGER.value}

    @classmethod
    def get_supported_operations(cls, field_type) -> list[dict[str, Any]]:
        return TYPE_OPERATION_MAPPINGS[field_type]


class EventTopKResource(EventBaseResource):
    DEFAULT_RESPONSE_DATA = []
    RequestSerializer = serializers.EventTopKRequestSerializer

    def perform_request(self, validated_request_data: dict[str, Any]) -> list[dict[str, Any]]:
        lock = threading.Lock()
        fields = validated_request_data["fields"]
        # 计算事件总数
        total = EventTotalResource().perform_request(validated_request_data)["total"]
        if total == 0:
            return [{"total": total, "field": field, "distinct_count": 0, "list": []} for field in fields]

        queryset = get_qs_from_req_data(validated_request_data).time_agg(False).instant()
        need_empty: bool = validated_request_data.get("need_empty") or False
        limit = validated_request_data["limit"]
        query_configs = validated_request_data["query_configs"]
        tables = [query_config["table"] for query_config in query_configs]
        dimension_metadata_map = EventViewConfigResource().get_dimension_metadata_map(
            validated_request_data["bk_biz_id"], tables
        )
        field_topk_map = defaultdict(lambda: defaultdict(int))
        # 字段和对应的去重数字典
        field_distinct_map = {}
        # 用于存储不存在的字段
        missing_fields = []
        # 用于存储有效字段
        valid_fields = []
        # 存在的字段字典
        topk_field_map = {}
        for field in fields:
            if field not in dimension_metadata_map:
                missing_fields.append({"field": field, "distinct_count": 0, "list": []})
            else:
                # 只保留有效字段
                valid_fields.append(field)

        # 计算去重数量
        run_threads(
            [
                InheritParentThread(
                    target=self.calculate_field_distinct_count,
                    args=(
                        lock,
                        queryset,
                        query_configs,
                        field,
                        dimension_metadata_map,
                        field_distinct_map,
                        field_topk_map,
                        need_empty,
                    ),
                )
                for field in valid_fields
            ]
        )
        # 只计算维度的去重数量，不需要 topk 值
        if limit == DIMENSION_DISTINCT_VALUE:
            for field in valid_fields:
                topk_field_map[field] = {
                    "field": field,
                    "distinct_count": field_distinct_map.get(field, 0),
                    "list": [],
                }

            # 合并不存在的字段
            return list(topk_field_map.values()) + missing_fields

        # 计算 topk，因为已经计算了多事件源 topk 值，此处只需计算单事件源的字段
        single_query_fields = [field for field in valid_fields if field not in field_topk_map]
        thread_list = []
        for field in single_query_fields:
            match_configs = self.get_match_query_configs(field, query_configs, dimension_metadata_map)
            # 检查是否非空
            if not match_configs:
                continue
            thread_list.append(
                InheritParentThread(
                    target=self.calculate_topk,
                    args=(lock, queryset, [match_configs[0]], field, limit, field_topk_map, need_empty),
                )
            )
        run_threads(thread_list)

        for field, field_values in field_topk_map.items():
            sorted_fields = sorted(field_values.items(), key=lambda item: item[1], reverse=True)[:limit]
            topk_field_map[field] = {
                "field": field,
                "total": total,
                "distinct_count": field_distinct_map[field],
                "list": [
                    {
                        "value": field_value or "",
                        "alias": "--" if not field_value else field_value,
                        "count": field_count,
                        "proportions": format_percent(
                            100 * (field_count / total) if total > 0 else 0,
                            precision=3,
                            sig_fig_cnt=3,
                            readable_precision=3,
                        ),
                    }
                    for field_value, field_count in sorted_fields
                ],
            }
        return list(topk_field_map.values()) + missing_fields

    @classmethod
    def get_q(cls, query_config) -> QueryConfigBuilder:
        # 基于 query_config 生成 QueryConfigBuilder
        return (
            QueryConfigBuilder((query_config["data_type_label"], query_config["data_source_label"]))
            .time_field("time")
            .table(query_config["table"])
            .conditions(query_config["where"])
        )

    @classmethod
    def query_topk(
        cls, queryset: UnifyQuerySet, qs: list[QueryConfigBuilder], field: str, limit: int = 0, need_empty: bool = False
    ):
        alias: str = "a"
        for q in qs:
            queryset = queryset.add_query(
                q.metric(field="_index" if need_empty else field, method="COUNT", alias=alias)
                .group_by(field)
                .order_by("_value desc")
            )

        queryset.expression(alias)
        return list(queryset.limit(limit))

    @classmethod
    def query_distinct(cls, queryset: UnifyQuerySet, qs: list[QueryConfigBuilder], field: str):
        alias: str = "a"
        for q in qs:
            queryset = queryset.add_query(q.metric(field=field, method="distinct", alias=alias)).limit(1)

        queryset.expression(alias)
        return list(queryset)

    @classmethod
    def get_match_query_configs(
        cls, field: str, query_configs: list[dict[str, Any]], dimension_metadata_map: dict[str, dict[str, set[str]]]
    ):
        """
        获取字段匹配的查询条件
        """
        if field in INNER_FIELD_TYPE_MAPPINGS:
            return query_configs
        return [
            query_config
            for query_config in query_configs
            if query_config["table"] in dimension_metadata_map[field]["table_ids"]
            or query_config["table"] in dimension_metadata_map[field]["data_labels"]
        ]

    @classmethod
    def calculate_topk(
        cls,
        lock: Lock,
        queryset: UnifyQuerySet,
        query_configs: list[dict[str, Any]],
        field: str,
        limit: int,
        field_topk_map: dict[str, dict[str, int]],
        need_empty: bool = False,
    ):
        """
        计算事件源 topk 查询
        """
        field_value_count_dict_list = cls.query_topk(
            queryset, [get_q_from_query_config(qc) for qc in query_configs], field, limit, need_empty
        )
        for field_value_count_dict in field_value_count_dict_list:
            try:
                # 剔除 count=0 的空数据
                if field_value_count_dict["_result_"] == 0:
                    continue
                # 加锁，防止多线程下非原子操作时 topk 值计算错误
                with lock:
                    field_topk_map[field][field_value_count_dict[field]] += field_value_count_dict["_result_"]
            except (IndexError, KeyError) as exc:
                logger.warning("[EventTopkResource] failed to get field topk, err -> %s", exc)
                raise ValueError(_("获取字段的 topk 失败"))

    @classmethod
    def calculate_distinct_count_for_table(
        cls, queryset: UnifyQuerySet, query_config: dict[str, Any], field: str, field_distinct_map: dict[str, int]
    ):
        """
        计算数据源的维度去重数量
        """
        q: QueryConfigBuilder = get_q_from_query_config(query_config)
        try:
            field_distinct_map[field] = cls.query_distinct(queryset, [q], field)[0]["_result_"]
        except (IndexError, KeyError) as exc:
            logger.warning("[EventTopkResource] failed to get field distinct_count, err -> %s", exc)
            raise ValueError(_("获取字段的去重数量失败"))

    @classmethod
    def calculate_field_distinct_count(
        cls,
        lock: Lock,
        queryset: UnifyQuerySet,
        query_configs: list[dict[str, Any]],
        field: str,
        dimension_metadata_map: dict[str, dict[str, set[str]]],
        field_distinct_map: dict[str, int],
        field_topk_map: dict[str, dict[str, int]],
        need_empty: bool = False,
    ):
        """
        计算维度去重数量
        """
        matching_configs = cls.get_match_query_configs(field, query_configs, dimension_metadata_map)
        matching_configs_length = len(matching_configs)
        if matching_configs_length == 0:
            return
        if matching_configs_length > 1:
            # 多事件源直接求所有枚举值
            cls.calculate_topk(lock, queryset, matching_configs, field, QUERY_MAX_LIMIT, field_topk_map, need_empty)
            field_distinct_map[field] = len(field_topk_map.get(field, []))
        else:
            cls.calculate_distinct_count_for_table(queryset, matching_configs[0], field, field_distinct_map)


class EventTotalResource(EventBaseResource):
    DEFAULT_RESPONSE_DATA = {"total": 0}
    RequestSerializer = serializers.EventTotalRequestSerializer

    def perform_request(self, validated_request_data: dict[str, Any]) -> dict[str, Any]:
        alias: str = "a"
        # 构建查询列表
        queries = [
            get_q_from_query_config(query_config).alias(alias).metric(field="_index", method="COUNT", alias=alias)
            for query_config in validated_request_data["query_configs"]
        ]

        # 构建统一查询集
        query_set = get_qs_from_req_data(validated_request_data).expression(alias).time_agg(False).instant().limit(1)

        # 添加查询到查询集中
        for query in queries:
            query_set = query_set.add_query(query)

        return {"total": list(query_set)[0]["_result_"]}


class EventStatisticsGraphResource(EventBaseResource):
    DEFAULT_RESPONSE_DATA = {"series": [{"datapoints": []}]}
    RequestSerializer = serializers.EventStatisticsGraphRequestSerializer

    def perform_request(self, validated_request_data: dict[str, Any]) -> dict[str, Any]:
        """
        param:field[values]:list
                1）当字段类型为 integer 时，包含字段的最小值、最大值、枚举数量和区间数量。具体结构如下：
                    1. 第0个元素: 最小值
                    2. 第1个元素: 最大值
                    3. 第2个元素: 枚举数量
                    4. 第3个元素: 区间数量
                2）当字段类型为 keyword 时，值为占比前5的值
        """
        field = validated_request_data["field"]
        # keyword 类型，返回时序图
        field_name = field["field_name"]
        values = field["values"]
        if field["field_type"] == EventDimensionTypeEnum.KEYWORD.value:
            for query_config in validated_request_data["query_configs"]:
                query_config["filter_dict"] = q_to_dict(
                    (dict_to_q(query_config["filter_dict"]) or Q()) & Q(**{f"{field_name}__eq": values})
                )
            return EventTimeSeriesResource().perform_request(validated_request_data)

        # integer 类型，返回直方图
        queryset = get_qs_from_req_data(validated_request_data).time_agg(False).instant()
        queries = []
        for query_config in validated_request_data["query_configs"]:
            for metric in query_config["metrics"]:
                q = get_q_from_query_config(query_config).metric(
                    field=metric["field"], method=metric["method"], alias=metric["alias"]
                )
                queries.append(q)

        # 字段枚举数量小于等于区间数量或者区间的最大数量小于等于区间数，直接查询枚举值返回
        min_value, max_value, distinct_count, interval_num = values[:4]
        if distinct_count <= interval_num or (max_value - min_value + 1) <= interval_num:
            for q in queries:
                queryset = queryset.add_query(q.group_by(field_name))
            return self.process_graph_info(
                [
                    [datapoint["_result_"], datapoint[field_name]]
                    for datapoint in sorted(queryset.limit(distinct_count), key=lambda x: int(x[field_name]))
                ]
            )
        # 划分区间计算
        return self.process_graph_info(
            self.calculate_interval_buckets(
                queryset, queries, field_name, self.calculate_intervals(min_value, max_value, interval_num)
            )
        )

    @classmethod
    def calculate_intervals(cls, min_value, max_value, interval_num):
        """
        计算区间
        :param min_value: int
            区间的最小值。
        :param max_value: int
            区间的最大值。
        :param interval_num: int
            区间数量。
        :return: List[Tuple[int, int]]
            返回各区间的元组列表，每个元组包含闭合区间 (最小值, 最大值)
        """
        intervals = []
        current_min = min_value
        for i in range(interval_num):
            # 闭区间，加上区间数后要 -1
            current_max = current_min + (max_value - min_value + 1) // interval_num - 1
            # 确保最后一个区间覆盖到 max_value
            if i == interval_num - 1:
                current_max = max_value
            intervals.append((current_min, current_max))
            current_min = current_max + 1
        return intervals

    @classmethod
    def calculate_interval_buckets(cls, queryset, queries, field, intervals) -> list:
        """
        统计各区间计数
        """
        buckets = []
        run_threads(
            [
                InheritParentThread(
                    target=cls.collect_interval_buckets,
                    args=(
                        queryset,
                        [cls._get_q_by_interval(query, field, interval) for query in queries],
                        buckets,
                        interval,
                    ),
                )
                for interval in intervals
            ]
        )
        return sorted(buckets, key=lambda x: int(x[1].split("-")[0]))

    @classmethod
    def _get_q_by_interval(cls, query, field, interval):
        """
        处理区间条件
        :param interval:tuple
            - interval[0]: 最小值
            - interval[1]: 最大值
        """
        return query.filter(**{f"{field}__gte": interval[0], f"{field}__lte": interval[1]})

    @classmethod
    def process_graph_info(cls, buckets):
        """
        处理数值趋势图格式，和时序趋势图保持一致
        """
        return {"series": [{"datapoints": buckets}]}

    @classmethod
    def collect_interval_buckets(cls, queryset, queries, bucket, interval: tuple[int, int]):
        for query in queries:
            queryset = queryset.add_query(query)
        try:
            bucket.append([queryset.original_data[0]["_result_"], f"{interval[0]}-{interval[1]}"])
        except (IndexError, KeyError) as exc:
            logger.warning("[EventStatisticsGraphResource] failed to get field interval_buckets, err -> %s", exc)
            raise ValueError(_("获取数值类型区间统计数量失败"))


class EventStatisticsInfoResource(EventBaseResource):
    DEFAULT_RESPONSE_DATA = {
        "total_count": 0,
        "field_count": 0,
        "distinct_count": 0,
        "field_percent": 0,
        "value_analysis": {},
    }
    RequestSerializer = serializers.EventStatisticsInfoRequestSerializer

    def perform_request(self, validated_request_data: dict[str, Any]) -> dict[str, Any]:
        queries = [
            get_q_from_query_config(query_config).alias("a") for query_config in validated_request_data["query_configs"]
        ]
        field = validated_request_data["field"]
        statistics_property_method_map = {
            "total_count": "count",
            "field_count": "count",
            "distinct_count": "distinct",
        }
        if field["field_type"] == EventDimensionTypeEnum.INTEGER.value:
            # 数值类型，支持更多统计方法
            statistics_property_method_map.update({"max": "max", "min": "min", "median": "cp50", "avg": "avg"})

        statistics_info = {}
        run_threads(
            [
                InheritParentThread(
                    target=self.get_statistics_info,
                    args=(
                        get_qs_from_req_data(validated_request_data).time_agg(False).limit(1).instant(),
                        queries,
                        field["field_name"],
                        statistics_property,
                        method,
                        statistics_info,
                    ),
                )
                for statistics_property, method in statistics_property_method_map.items()
            ]
        )
        # 格式化统计信息
        return self.process_statistics_info(statistics_info)

    @classmethod
    def process_statistics_info(cls, statistics_info: dict[str, Any]) -> dict[str, Any]:
        processed_statistics_info = {}
        # 分类并处理结果
        for statistics_property, value in statistics_info.items():
            # 平均值取两位小数
            if statistics_property == "avg":
                value = format_percent(value, precision=3, sig_fig_cnt=3, readable_precision=3)
            if statistics_property in ["max", "min", "median", "avg"]:
                processed_statistics_info.setdefault("value_analysis", {})[statistics_property] = value
                continue
            processed_statistics_info[statistics_property] = value

        # 计算百分比
        processed_statistics_info["field_percent"] = format_percent(
            (statistics_info["field_count"] / statistics_info["total_count"]) * 100
            if statistics_info["total_count"] > 0
            else 0,
            precision=3,
            sig_fig_cnt=3,
            readable_precision=3,
        )
        return processed_statistics_info

    @classmethod
    def get_statistics_info(cls, queryset, queries, field, statistics_property, method, statistics_info) -> None:
        for query in queries:
            queryset = queryset.add_query(
                cls.get_q_by_statistics_property(query, field, statistics_property).metric(
                    field=field, method=method, alias="a"
                )
            )
        queryset = cls.set_qs_expression_by_method(queryset, method)
        try:
            statistics_info[statistics_property] = queryset.original_data[0]["_result_"]
        except (IndexError, KeyError) as exc:
            logger.warning("[EventStatisticsInfoResource] failed to get statistics info, err -> %s", exc)
            raise ValueError(_(f"获取字段统计信息失败，查询函数：{method}"))

    @classmethod
    def get_q_by_statistics_property(cls, query, field, statistics_property):
        """
        根据统计属性设置过滤条件
        """
        return query.filter(**{f"{field}__neq": ""}) if statistics_property == "field_count" else query

    @classmethod
    def set_qs_expression_by_method(cls, queryset, method):
        """
        根据查询函数适配表达式
        """
        return queryset.expression(f"{method}(a)") if method in {"max", "min"} else queryset.expression("a")


class EventGenerateQueryStringResource(EventBaseResource):
    DEFAULT_RESPONSE_DATA = ""
    RequestSerializer = serializers.EventGenerateQueryStringRequestSerializer

    @classmethod
    def is_return_default_early(cls, validated_request_data: dict[str, Any]) -> bool:
        return False

    def perform_request(self, data):
        generator = QueryStringGenerator(Operation.QueryStringOperatorMapping)
        for f in data["where"]:
            generator.add_filter(
                format_field(f["key"]),
                f["method"],
                f["value"],
                is_wildcard=f.get("options", {}).get("is_wildcard", False),
            )
        return generator.to_query_string()


class EventTagDetailResource(EventBaseResource):
    DEFAULT_RESPONSE_DATA = {"total": 0, "list": []}
    RequestSerializer = serializers.EventTagDetailRequestSerializer

    def perform_request(self, validated_request_data: dict[str, Any]) -> dict[str, Any]:
        def _collect(_key: str, _req_data: dict[str, Any]):
            result[_key] = self.get_tag_detail(_req_data)
            pass

        result: dict[str, dict[str, Any]] = {}
        req_data_with_warn: dict[str, Any] = copy.deepcopy(validated_request_data)
        for qc in req_data_with_warn["query_configs"]:
            qc.setdefault("where", []).append(
                {"key": "type", "method": "eq", "value": [EventType.Warning.value], "condition": "and"}
            )

        run_threads(
            [
                InheritParentThread(target=_collect, args=(EventType.Warning.value, req_data_with_warn)),
                InheritParentThread(target=_collect, args=("All", validated_request_data)),
            ]
        )
        return result

    @classmethod
    def get_event_origin_req_data_map(
        cls,
        validated_request_data: dict[str, Any],
        data_labels_map: dict[str, str],
        exclude_origins: list[tuple[str, str]] | None = None,
    ) -> dict[tuple[str, str], Any]:
        exclude_origins = exclude_origins or []
        event_origin_req_data_map: dict[tuple[str, str], dict[str, Any]] = {}
        for query_config in validated_request_data["query_configs"]:
            event_origin: tuple[str, str] = EVENT_ORIGIN_MAPPING.get(
                data_labels_map.get(query_config["table"]), DEFAULT_EVENT_ORIGIN
            )
            if event_origin in exclude_origins:
                continue

            if event_origin not in event_origin_req_data_map:
                event_origin_req_data_map[event_origin] = copy.deepcopy(validated_request_data)
                event_origin_req_data_map[event_origin]["query_configs"] = []
            event_origin_req_data_map[event_origin]["query_configs"].append(query_config)
        return event_origin_req_data_map

    @classmethod
    def get_tag_detail(cls, validated_request_data: dict[str, Any]) -> dict[str, Any]:
        # 获取 total
        tag_detail: dict[str, Any] = {"time": validated_request_data["start_time"], "total": 0}
        try:
            total: int = EventTotalResource().perform_request(validated_request_data).get("total") or 0
        except Exception:  # pylint: disable=broad-except
            return {**tag_detail, "total": 0, "list": []}

        if total == 0:
            tag_detail["list"] = []
            return tag_detail

        if total > 20:
            topk: list[dict[str, Any]] = cls.fetch_topk(validated_request_data)
            for item in topk:
                item["proportions"] = format_percent((item["count"] / total) * 100, 3, 3, 3)
            tag_detail["topk"] = sorted(topk, key=lambda _t: -_t["count"])[: validated_request_data["limit"]]
        else:
            tag_detail["list"] = cls.fetch_logs(validated_request_data)

        tag_detail["total"] = total
        return tag_detail

    @classmethod
    def fetch_topk(cls, validated_request_data: dict[str, Any]) -> list[dict[str, Any]]:
        data_labels_map: dict[str, str] = get_data_labels_map(
            validated_request_data["bk_biz_id"],
            [query_config["table"] for query_config in validated_request_data["query_configs"]],
        )
        validated_request_data: dict[str, Any] = copy.deepcopy(validated_request_data)
        validated_request_data["fields"] = ["event_name"]
        origin_req_data_map: dict[tuple[str, str], dict[str, Any]] = cls.get_event_origin_req_data_map(
            validated_request_data, data_labels_map
        )
        event_origin_topk_map: dict[tuple[str, str], list[dict[str, Any]]] = {}
        run_threads(
            [
                InheritParentThread(target=cls.query_topk, args=(event_origin, req_data, event_origin_topk_map))
                for event_origin, req_data in origin_req_data_map.items()
            ]
        )

        event_tuple_count_map: dict[tuple[str, str, str], int] = defaultdict(int)
        for event_origin, topk in event_origin_topk_map.items():
            domain, source = event_origin
            for item in topk:
                event_tuple_count_map[(domain, source, item["value"])] += item["count"]

        event_name_translations: dict[str, dict[str, str]] = {
            EventDomain.SYSTEM.value: SYSTEM_EVENT_TRANSLATIONS,
            EventDomain.CICD.value: {
                CicdEventName.PIPELINE_STATUS_INFO.value: CicdEventName.PIPELINE_STATUS_INFO.label
            },
        }
        for k8s_event_name_translations in K8S_EVENT_TRANSLATIONS.values():
            event_name_translations.setdefault(EventDomain.K8S.value, {}).update(k8s_event_name_translations)

        processed_topk: list[dict[str, Any]] = []
        for event_tuple, count in event_tuple_count_map.items():
            domain, source, event_name = event_tuple
            processed_topk.append(
                {
                    "domain": {"value": domain, "alias": EventDomain.from_value(domain).label},
                    "source": {"value": source, "alias": EventSource.from_value(source).label},
                    "event_name": {
                        "value": event_name,
                        "alias": _("{alias}（{name}）").format(
                            alias=event_name_translations.get(domain, {}).get(event_name, event_name), name=event_name
                        ),
                    },
                    "count": count,
                }
            )
        return processed_topk

    @classmethod
    def query_topk(
        cls,
        event_origin: tuple[str, str],
        req_data: dict[str, Any],
        event_origin_topk_map: dict[tuple[str, str], list[dict[str, Any]]],
    ):
        event_origin_topk_map[event_origin] = EventTopKResource().perform_request(req_data)[0].get("list") or []

    @classmethod
    def fetch_logs(cls, validated_request_data: dict[str, Any], limit: int = 10) -> list[dict[str, Any]]:
        validated_request_data: dict[str, Any] = copy.deepcopy(validated_request_data)
        validated_request_data["offset"] = 0
        return EventLogsResource().perform_request(validated_request_data).get("list") or []
