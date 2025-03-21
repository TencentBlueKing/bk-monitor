# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import logging
import threading
from collections import defaultdict
from threading import Lock
from typing import Any, Dict, List, Set

from django.utils.translation import gettext_lazy as _

from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder, UnifyQuerySet
from bkmonitor.models import MetricListCache
from bkmonitor.utils.thread_backend import InheritParentThread, run_threads
from core.drf_resource import Resource, resource

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
    CategoryWeight,
    EventCategory,
    EventDimensionTypeEnum,
    EventType,
)
from .core.processors import (
    BaseEventProcessor,
    HostEventProcessor,
    OriginEventProcessor,
)
from .core.processors.context import BcsClusterContext, SystemClusterContext
from .core.processors.k8s import K8sEventProcessor
from .mock_data import (
    API_LOGS_RESPONSE,
    API_TIME_SERIES_RESPONSE,
    API_TOPK_RESPONSE,
    API_TOTAL_RESPONSE,
    API_VIEW_CONFIG_RESPONSE,
)
from .utils import get_data_labels_map, get_field_alias, get_q_from_query_config

logger = logging.getLogger(__name__)


class EventTimeSeriesResource(Resource):
    RequestSerializer = serializers.EventTimeSeriesRequestSerializer

    def perform_request(self, validated_request_data: Dict[str, Any]) -> Dict[str, Any]:
        if validated_request_data["is_mock"]:
            return API_TIME_SERIES_RESPONSE

        try:
            result: Dict[str, Any] = resource.grafana.graph_unify_query(validated_request_data)
        except Exception as exc:
            logger.warning("[EventTimeSeriesResource] failed to get series, err -> %s", exc)
            return {}

        for series in result["series"]:
            dimensions = series["dimensions"]
            if "type" in dimensions and not dimensions["type"].strip():
                dimensions["type"] = EventType.Default.value
        result["query_config"] = validated_request_data
        return result


class EventLogsResource(Resource):
    RequestSerializer = serializers.EventLogsRequestSerializer

    def perform_request(self, validated_request_data: Dict[str, Any]) -> Dict[str, Any]:
        if validated_request_data.get("is_mock"):
            return API_LOGS_RESPONSE

        # 构建统一查询集
        queryset = (
            UnifyQuerySet()
            .scope(bk_biz_id=validated_request_data["bk_biz_id"])
            .start_time(1000 * validated_request_data["start_time"])
            .end_time(1000 * validated_request_data["end_time"])
            .time_agg(False)
            .instant()
            .limit(validated_request_data["limit"])
            .offset(validated_request_data["offset"])
        )

        # 添加查询到查询集中
        for query in [
            get_q_from_query_config(query_config) for query_config in validated_request_data["query_configs"]
        ]:
            queryset = queryset.add_query(query.order_by("-time"))
        try:
            # unify-query 查询失败
            events: List[Dict[str, Any]] = list(queryset)
        except Exception as exc:
            logger.warning("[EventLogsResource] failed to get logs, err -> %s", exc)
            return {"list": []}

        processors: List[BaseEventProcessor] = [
            OriginEventProcessor(),
            K8sEventProcessor(BcsClusterContext()),
            HostEventProcessor(SystemClusterContext()),
        ]
        for processor in processors:
            events = processor.process(events)

        return {"list": events}


class EventViewConfigResource(Resource):
    RequestSerializer = serializers.EventViewConfigRequestSerializer

    def perform_request(self, validated_request_data: Dict[str, Any]) -> Dict[str, Any]:
        if validated_request_data.get("is_mock"):
            return API_VIEW_CONFIG_RESPONSE

        data_sources = validated_request_data["data_sources"]
        tables = [data_source["table"] for data_source in data_sources]
        dimension_metadata_map = self.get_dimension_metadata_map(validated_request_data["bk_biz_id"], tables)
        fields = self.sort_fields(dimension_metadata_map)
        return {"display_fields": DISPLAY_FIELDS, "entities": ENTITIES, "field": fields}

    @classmethod
    def get_dimension_metadata_map(cls, bk_biz_id: int, tables):
        # 维度元数据集
        data_labels_map = get_data_labels_map(bk_biz_id, tables)
        dimensions_queryset = MetricListCache.objects.filter(result_table_id__in=data_labels_map.keys()).values(
            "dimensions", "result_table_id"
        )
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
    def sort_fields(cls, dimension_metadata_map) -> List[Dict[str, Any]]:
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
            is_dimensions = cls.is_dimensions(name)
            supported_operations = cls.get_supported_operations(field_type)
            fields.append(
                {
                    "name": name,
                    "alias": alias,
                    "type": field_type,
                    "is_option_enabled": is_option_enabled,
                    "is_dimensions": is_dimensions,
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
    def is_dimensions(cls, name) -> bool:
        # 如果是内置字段，不需要补充 dimensions.
        return name not in INNER_FIELD_TYPE_MAPPINGS

    @classmethod
    def get_field_type(cls, field) -> str:
        """ "
        获取字段类型
        """
        # 自定义字段统一返回 keyword
        return INNER_FIELD_TYPE_MAPPINGS.get(field, EventDimensionTypeEnum.KEYWORD.value)

    @classmethod
    def is_option_enabled(cls, field_type) -> bool:
        return field_type in {EventDimensionTypeEnum.KEYWORD.value}

    @classmethod
    def get_supported_operations(cls, field_type) -> List[Dict[str, Any]]:
        return TYPE_OPERATION_MAPPINGS[field_type]


class EventTopKResource(Resource):
    RequestSerializer = serializers.EventTopKRequestSerializer

    def perform_request(self, validated_request_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        lock = threading.Lock()
        if validated_request_data["is_mock"]:
            return API_TOPK_RESPONSE

        fields = validated_request_data["fields"]
        # 计算事件总数
        total = EventTotalResource().perform_request(validated_request_data)["total"]
        if total == 0:
            return [{"total": total, "field": field, "distinct_count": 0, "list": []} for field in fields]

        queryset = (
            UnifyQuerySet()
            .scope(bk_biz_id=validated_request_data["bk_biz_id"])
            .start_time(1000 * validated_request_data["start_time"])
            .end_time(1000 * validated_request_data["end_time"])
            .time_agg(False)
            .instant()
        )
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
                # 对多线程获取失败的进行补偿
                if field not in field_distinct_map:
                    logger.warning(
                        "[EventTopKResource] distinct_count not found, try to compensate: field -> %s", field
                    )
                    self.calculate_field_distinct_count(
                        lock,
                        queryset,
                        query_configs,
                        field,
                        dimension_metadata_map,
                        field_distinct_map,
                        field_topk_map,
                        need_empty,
                    )

                topk_field_map[field] = {
                    "field": field,
                    "distinct_count": field_distinct_map[field],
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
                        # TODO unifyquery 处理完空值问题会退这段代码
                        "value": "" if not field_value or field_value == " " else field_value,
                        "alias": "--" if not field_value or field_value == " " else field_value,
                        "count": field_count,
                        "proportions": round(100 * (field_count / total), 2),
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
        cls, queryset: UnifyQuerySet, qs: List[QueryConfigBuilder], field: str, limit: int = 0, need_empty: bool = False
    ):
        alias: str = "a"
        for q in qs:
            queryset = queryset.add_query(
                q.metric(field="_index" if need_empty else field, method="COUNT", alias=alias)
                .group_by(field)
                .order_by("-_value")
            )

        queryset.expression(alias)
        return list(queryset.limit(limit))

    @classmethod
    def query_distinct(cls, queryset: UnifyQuerySet, qs: List[QueryConfigBuilder], field: str):
        alias: str = "a"
        for q in qs:
            queryset = queryset.add_query(q.metric(field=field, method="cardinality", alias=alias))

        queryset.expression(alias)
        return list(queryset)

    @classmethod
    def get_match_query_configs(
        cls, field: str, query_configs: List[Dict[str, Any]], dimension_metadata_map: Dict[str, Dict[str, Set[str]]]
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
        query_configs: List[Dict[str, Any]],
        field: str,
        limit: int,
        field_topk_map: Dict[str, Dict[str, int]],
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
        cls, queryset: UnifyQuerySet, query_config: Dict[str, Any], field: str, field_distinct_map: Dict[str, int]
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
        query_configs: List[Dict[str, Any]],
        field: str,
        dimension_metadata_map: Dict[str, Dict[str, Set[str]]],
        field_distinct_map: Dict[str, int],
        field_topk_map: Dict[str, Dict[str, int]],
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


class EventTotalResource(Resource):
    RequestSerializer = serializers.EventTotalRequestSerializer

    def perform_request(self, validated_request_data: Dict[str, Any]) -> Dict[str, Any]:
        if validated_request_data.get("is_mock"):
            return API_TOTAL_RESPONSE

        alias: str = "a"
        # 构建查询列表
        queries = [
            get_q_from_query_config(query_config).alias(alias).metric(field="_index", method="COUNT", alias=alias)
            for query_config in validated_request_data["query_configs"]
        ]

        # 构建统一查询集
        query_set = (
            UnifyQuerySet()
            .scope(bk_biz_id=validated_request_data["bk_biz_id"])
            .start_time(1000 * validated_request_data["start_time"])
            .end_time(1000 * validated_request_data["end_time"])
            .expression(alias)
            .time_agg(False)
            .instant()
        )

        # 添加查询到查询集中
        for query in queries:
            query_set = query_set.add_query(query)

        try:
            return {"total": query_set.original_data[0]["_result_"]}
        except Exception as exc:
            logger.warning("[EventTotalResource] failed to get total, err -> %s", exc)
            return {"total": 0}
