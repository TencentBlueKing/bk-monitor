# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - Resource SDK (BlueKing - Resource SDK) available.
Copyright (C) 2022 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import datetime
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from django.db.models import Q
from django.utils.functional import classproperty
from django.utils.translation import ugettext_lazy as _

from apm import types
from apm.core.handlers.query.builder import QueryConfigBuilder, UnifyQuerySet
from apm.utils.base import normalize_rt_id
from bkmonitor.utils.thread_backend import InheritParentThread, ThreadPool, run_threads

logger = logging.getLogger("apm")


class FilterOperator:
    # 走ES查询可以使用的操作符
    EXISTS = "exists"
    NOT_EXISTS = "not exists"
    EQUAL = "equal"
    NOT_EQUAL = "not_equal"
    BETWEEN = "between"
    LIKE = "like"


class LogicSupportOperator:
    # 走特殊逻辑可以使用的操作符
    LOGIC = "logic"


class BaseQuery:

    # datasource 类型
    USING: Tuple[str, str] = ("log", "bk_monitor")

    # 时间填充，单位 s
    TIME_PADDING = 5

    # 时间字段精度，用于时间字段查询时做乘法
    TIME_FIELD_ACCURACY = 1000

    # 默认时间字段
    DEFAULT_TIME_FIELD = "end_time"

    # 字段候选值最多获取500个
    OPTION_VALUES_MAX_SIZE = 500

    # 查询字段映射
    KEY_REPLACE_FIELDS: Dict[str, str] = {}

    def __init__(self, bk_biz_id: int, result_table_id: str, retention: int):
        self.bk_biz_id: int = bk_biz_id
        self.result_table_id: str = normalize_rt_id(result_table_id)
        self.retention: int = retention

    @classproperty
    def operator_mapping(self) -> Dict[str, Callable[[QueryConfigBuilder, str, types.FilterValue], Q]]:
        return {
            FilterOperator.EXISTS: lambda q, field, value: q & Q(**{f"{field}__exists": value}),
            FilterOperator.NOT_EXISTS: lambda q, field, value: q & Q(**{f"{field}__nexists": value}),
            FilterOperator.EQUAL: lambda q, field, value: q & q & Q(**{f"{field}__eq": value}),
            FilterOperator.NOT_EQUAL: lambda q, field, value: q & Q(**{f"{field}__neq": value}),
            FilterOperator.BETWEEN: lambda q, field, value: q
            & Q(**{f"{field}__gte": value[0], f"{field}__lte": value[1]}),
            FilterOperator.LIKE: lambda q, field, value: q & Q(**{f"{field}__include": value[0]}),
            LogicSupportOperator.LOGIC: lambda q, field, value: self._add_logic_filter(q, field, value),
        }

    @property
    def q(self) -> QueryConfigBuilder:
        return QueryConfigBuilder(self.USING).table(self.result_table_id).time_field(self.DEFAULT_TIME_FIELD)

    def time_range_queryset(self, start_time: Optional[int] = None, end_time: Optional[int] = None) -> UnifyQuerySet:
        start_time, end_time = self.get_time_range(self.retention, start_time, end_time)
        return UnifyQuerySet().start_time(start_time).end_time(end_time)

    def _query_option_values(
        self, q: QueryConfigBuilder, fields: List[str], start_time: Optional[int] = None, end_time: Optional[int] = None
    ) -> Dict[str, List[str]]:

        queryset: UnifyQuerySet = self.time_range_queryset(start_time, end_time).limit(self.OPTION_VALUES_MAX_SIZE)

        # 为什么这里使用多线程，而不是构造多个 aggs？
        # 在性能差距不大的情况下，尽可能构造通用查询，便于后续屏蔽存储差异
        option_values: Dict[str, List[str]] = {}
        ThreadPool().map_ignore_exception(
            self._collect_option_values, [(q, queryset, field, option_values) for field in fields]
        )
        return option_values

    @classmethod
    def _collect_option_values(
        cls, q: QueryConfigBuilder, queryset: UnifyQuerySet, field: str, option_values: Dict[str, List[str]]
    ):
        q = q.metric(field=field, method="count").group_by(field)
        for bucket in queryset.add_query(q):
            option_values.setdefault(field, []).append(bucket[field])

    @classmethod
    def _get_data_page(
        cls,
        q: QueryConfigBuilder,
        queryset: UnifyQuerySet,
        select_fields: List[str],
        count_field: str,
        offset: int,
        limit: int,
    ) -> types.Page:
        def _fill_total():
            _q: QueryConfigBuilder = q.metric(field=count_field, method="count", alias="total")
            page_data["total"] = queryset.add_query(_q)[0]["total"]

        def _fill_data():
            _q: QueryConfigBuilder = q.values(*select_fields)
            page_data["data"] = list(queryset.add_query(_q).offset(offset).limit(limit))

        # 为什么要分开获取数据和总数？
        # 并不是所有的 DB 都能在一次查询里，同时返回数据和命中总数，此处对查询场景进行原子逻辑拆分，同时并发加速
        page_data: Dict[str, Union[int, List[Dict[str, Any]]]] = {}
        run_threads([InheritParentThread(target=_fill_total), InheritParentThread(target=_fill_data)])

        return page_data

    @classmethod
    def _translate_field(cls, field: str) -> str:
        return cls.KEY_REPLACE_FIELDS.get(field) or field

    @classmethod
    def build_filters(cls, filters: Optional[List[types.Filter]]) -> Q:
        if not filters:
            return Q()

        q: Q = Q()
        for f in filters:
            if f["operator"] not in cls.operator_mapping:
                raise ValueError(_("不支持的查询操作符: %s") % (f['operator']))

            key = cls._translate_field(f["key"])
            return cls.operator_mapping[f["operator"]](q, key, f["value"])

        return q

    @classmethod
    def _add_logic_filter(cls, q: Q, field: str, value: types.FilterValue) -> Q:
        return q

    @classmethod
    def get_time_range(
        cls, retention: int, start_time: Optional[int] = None, end_time: Optional[int] = None
    ) -> Tuple[int, int]:
        now: int = int(datetime.datetime.now().timestamp())
        # 最早可查询时间
        earliest_start_time: int = now - int(datetime.timedelta(days=retention).total_seconds())

        # 开始时间不能小于 earliest_start_time
        start_time = max(earliest_start_time, start_time or earliest_start_time)
        # 结束时间不能大于 now
        end_time = min(now, end_time or now)

        # 通常我们会在页面拿到 TraceID 后便进行查询，「查询请求时间」可能 Trace 还未完成，前后补一个填充时间
        start_time = (start_time - cls.TIME_PADDING) * cls.TIME_FIELD_ACCURACY
        end_time = (end_time + cls.TIME_PADDING) * cls.TIME_FIELD_ACCURACY

        return start_time, end_time

    @classmethod
    def parse_query_string_from_dsl(cls, dsl: Dict[str, Any]) -> Tuple[str, List[str]]:
        """
        【待废弃】在 dsl 中提取检索关键字，保留该逻辑主要是兼容前端的 lucene 查询，后续兼容不同 DB，该逻辑大概率会下掉
        :param dsl:
        :return:
        """
        try:
            return dsl["query"]["query_string"]["query"], []
        except KeyError:
            pass

        try:
            should_list: List[Dict[str, Any]] = dsl["query"]["bool"]["should"]
        except KeyError:
            return "*", []

        query_string: str = "*"
        nested_paths: List[str] = []
        for should in should_list:
            try:
                nested_paths.append(should["nested"]["path"])
                query_string = should["nested"]["query"]["query_string"]["query"]
            except KeyError:
                continue

        return query_string, nested_paths

    @classmethod
    def parse_ordering_from_dsl(cls, dsl: Dict[str, Any]) -> List[str]:
        """
        【待废弃】在 dsl 中提取字段排序信息
        :param dsl:
        :return:
        """

        ordering: List[str] = []
        try:
            for sort_item in dsl["sort"]:
                if isinstance(sort_item, str):
                    # handle case: 'start_time'
                    ordering.append(sort_item)

                elif isinstance(sort_item, dict):
                    for field, option in sort_item.items():
                        if isinstance(option, str):
                            # handle case: {'end_time': 'desc'}
                            ordering.append(f"{field} {option}")
                        elif isinstance(option, dict):
                            # handle case: {'hierarchy_count': {'order': 'desc'}}
                            ordering.append(f"{field} {option['order']}")
        except (KeyError, TypeError, IndexError):
            pass

        return ordering


class FakeQuery:
    def list(self, *args, **kwargs):
        return [], 0

    def __getattr__(self, item):
        return lambda *args, **kwargs: None
