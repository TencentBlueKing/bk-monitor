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

import abc
import datetime
import logging
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from django.db.models import Q
from django.db.models.sql import AND
from django.utils.functional import classproperty
from django.utils.translation import ugettext_lazy as _
from elasticsearch_dsl import A
from elasticsearch_dsl import Q as ESQ

from apm import types
from apm.utils.base import normalize_rt_id
from bkmonitor.data_source import load_data_source
from bkmonitor.data_source.data_source import DataSource, q_to_dict
from bkmonitor.data_source.models.query import DataQueryIterMixin
from bkmonitor.data_source.models.sql.where import WhereNode
from bkmonitor.data_source.unify_query.query import UnifyQuery
from bkmonitor.utils.thread_backend import ThreadPool

logger = logging.getLogger("apm")

"""
UnifyQuerySet 在 APM 验证完成后，可以考虑往 datasource 下沉，供其他模块使用

做了什么？复用原有 datasource 模块，支持使用类 ORM 模式进行查询

解决了什么问题？
- 监控统一查询结构目前主要供前端数据检索/告警配置使用，由前端拼接参数，后台负责解析查询
- APM 存在预计算路由，服务接口统计等复杂查询场景，可能需要对多结果表进行聚合查询，所以在后台有一个模块提供查询功能
- 在切换到 UnifyQuery 的背景下，后台查询模块也需要和前端一样，拼接通用查询参数，查询 ES or UnifyQuery
- 在过程中发现每个场景的查询都在进行相似的数据结构拼装，过于重复冗长，基于 unify[query_configs] 场景进行类 ORM 的封装
- 后台逻辑实现从 dict 构造转为基于查询条件编写 ORM 语句，提升可维护和可读性

监控的 datasource 也有类似 queryset 的封装，和这里有什么区别？
- 在 unify query 之前，datasource 确实可以承接单指标查询的类 orm 查询的需求，但现在 datasource 只是 unify 下的一个 query config
- 在 unify query 之后，由于查询方式的改变，之前 queryset 基本是静态引用，代码入口也不支持传入 queryset（主要还是没需求，这个事情是前端做的）
- unify 支持配置多个 datasource 进行聚合计算，在之前 datasource 的基础上，需要对 unify 也进行相应的封装，这是目前没有的

这里会不会新增了很多代码？ 不会，基本还是复用 datasource，新增 200+ 左右的代码，用于把 unify[query_configs] 部分查询 ORM 化

其他模块可不可以复用？可以，不稳定阶段先放到 apm 下踩坑完善

查询结构的 dict 构造，相比于 queryset 有什么劣势？
- 从复用度来讲，无论哪种方式都需要进行一定的抽象封装，才能达到相似查询代码复用的目的
- 从代码量上说，两者差不多，但后者的收益更高，因为抽象的内容具有被其他模块复用的可能
"""


class QueryConfig:
    def __init__(self, using: Tuple[str, str]):
        self.table: str = ""
        self.reference_name: str = ""
        self.time_field: str = ""
        self.distinct: str = ""
        self.select: List[str] = []
        self.where: WhereNode = WhereNode()
        self.metrics: List[Dict[str, Any]] = []
        self.order_by: List[str] = []
        self.group_by: List[str] = []
        self.using: Tuple[str, str] = using

        # to be deprecation
        self.query_string: str = "*"
        self.nested_paths: List[str] = []

    def clone(self) -> "QueryConfig":
        obj: "QueryConfig" = self.__class__(using=self.using)
        obj.table = self.table
        obj.reference_name = self.reference_name
        obj.time_field = self.time_field
        obj.distinct = self.distinct
        obj.select = self.select[:]
        obj.where = self.where.clone()
        obj.metrics = self.metrics[:]
        obj.order_by = self.order_by[:]
        obj.group_by = self.group_by[:]
        obj.query_string = self.query_string
        obj.nested_paths = self.nested_paths[:]
        return obj

    def set_table(self, table: Optional[str]):
        if table:
            self.table = table

    def set_reference_name(self, reference_name: Optional[str]):
        if reference_name:
            self.reference_name = reference_name

    def set_time_field(self, time_field: Optional[str]):
        if time_field:
            self.time_field = time_field

    def set_distinct(self, field: Optional[str]):
        if field:
            self.select = [field]
            self.distinct = field

    def set_query_string(self, query_string: Optional[str], nested_paths: Optional[List[str]] = None):
        if query_string:
            self.query_string = query_string
            if nested_paths:
                self.nested_paths = nested_paths

    def add_q(self, q_object: Q):
        self.where.add(q_object, AND)

    def add_metrics(self, field: str, method: str, alias: Optional[str] = ""):
        self.metrics.append({"field": field, "alias": alias or method, "method": method})

    def add_select(self, col: Optional[str]):
        if col and col.strip():
            self.select.append(col.strip())

    def add_grouping(self, *field_names):
        if field_names:
            self.group_by.extend([field for field in field_names if field and field.strip()])

    def add_ordering(self, *field_names):
        if field_names:
            self.order_by.extend([field for field in field_names if field and field.strip()])


class QueryConfigBuilder:
    def __init__(self, using: Tuple[str, str], query_config: Optional[QueryConfig] = None):
        self.query_config = query_config or QueryConfig(using=using)

    def clone(self) -> "QueryConfigBuilder":
        query_config: QueryConfig = self.query_config.clone()
        obj: "QueryConfigBuilder" = self.__class__(using=self.query_config.using, query_config=query_config)
        return obj

    def table(self, table: Optional[str]):
        clone = self.clone()
        clone.query_config.set_table(table)
        return clone

    def alias(self, alias: Optional[str]):
        clone = self.clone()
        clone.query_config.set_reference_name(alias)
        return clone

    def time_field(self, time_field: str):
        clone = self.clone()
        clone.query_config.set_time_field(time_field)
        return clone

    def values(self, *fields):
        clone = self.clone()
        for col in fields:
            clone.query_config.add_select(col)
        return clone

    def distinct(self, field: Optional[str]):
        clone = self.clone()
        clone.query_config.set_distinct(field)
        return clone

    def filter(self, *args, **kwargs):
        clone = self.clone()
        clone.query_config.add_q(Q(*args, **kwargs))
        return clone

    def metric(self, field: str, method: str, alias: Optional[str] = ""):
        clone = self.clone()
        clone.query_config.add_metrics(field, method, alias)
        return clone

    def order_by(self, *field_names):
        clone = self.clone()
        clone.query_config.add_ordering(*field_names)
        return clone

    def group_by(self, *field_names):
        clone = self.clone()
        clone.query_config.add_grouping(*field_names)
        return clone

    def query_string(self, query_string: Optional[str], nested_paths: Optional[List[str]] = None):
        clone = self.clone()
        clone.query_config.set_query_string(query_string, nested_paths)
        return clone


class BaseCompiler(abc.ABC):
    def __init__(self, query: "Query"):
        self.query: "Query" = query

    @abc.abstractmethod
    def execute(self) -> List[Dict[str, Any]]:
        raise NotImplementedError

    @abc.abstractmethod
    def as_params(self) -> Dict[str, Any]:
        raise NotImplementedError


class UnifyQueryCompiler(BaseCompiler):
    @classmethod
    def query_log(cls, unify_query: UnifyQuery, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        data, __ = unify_query.query_log(
            start_time=params["start_time"],
            end_time=params["end_time"],
            limit=params["limit"],
            offset=params["offset"],
            search_after_key=params["search_after_key"],
        )
        return data

    @classmethod
    def query_data(cls, unify_query: UnifyQuery, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        data = unify_query.query_data(
            start_time=params["start_time"],
            end_time=params["end_time"],
            limit=params["limit"],
            offset=params["offset"],
            search_after_key=params["search_after_key"],
        )
        return data

    def execute(self) -> List[Dict[str, Any]]:

        params: Dict[str, Any] = self.as_params()
        logger.info("[UnifyQueryCompiler] params -> %s", params)

        is_metric: bool = False
        data_sources: List[DataSource] = []
        for query_config in params["query_configs"]:
            if query_config["metrics"]:
                is_metric = True

            data_source_class = load_data_source(query_config["data_source_label"], query_config["data_type_label"])
            data_source = data_source_class(
                bk_biz_id=params["bk_biz_id"],
                use_full_index_names=True,
                enable_dimension_completion=False,
                enable_builtin_dimension_expansion=False,
                **query_config,
            )
            data_sources.append(data_source)

        unify_query: UnifyQuery = UnifyQuery(
            bk_biz_id=params["bk_biz_id"],
            data_sources=data_sources,
            expression=params["expression"],
            functions=params["functions"],
        )

        if is_metric:
            return self.query_data(unify_query, params)
        else:
            return self.query_log(unify_query, params)

    def as_params(self) -> Dict[str, Any]:
        query_configs: List[Dict[str, Any]] = []
        for query_config_obj in self.query.query_configs:
            query_config = {
                "data_type_label": query_config_obj.using[0],
                "data_source_label": query_config_obj.using[1],
                "reference_name": query_config_obj.reference_name or "a",
                "table": query_config_obj.table,
                "time_field": query_config_obj.time_field,
                "distinct": query_config_obj.distinct,
                "where": [],
                "metrics": query_config_obj.metrics,
                "group_by": query_config_obj.group_by,
                "filter_dict": q_to_dict(query_config_obj.where),
                "query_string": query_config_obj.query_string or "*",
                "nested_paths": query_config_obj.nested_paths,
                "order_by": query_config_obj.order_by,
            }
            if query_config_obj.select:
                query_config["keep_columns"] = query_config_obj.select
            query_configs.append(query_config)

        return {
            "bk_biz_id": 0,
            "query_configs": query_configs,
            "functions": self.query.functions,
            "expression": self.query.expression or query_configs[0]["reference_name"],
            "limit": self.query.get_limit(),
            "offset": self.query.offset,
            "start_time": self.query.start_time * 1000,
            "end_time": self.query.end_time * 1000,
            "search_after_key": self.query.search_after_key,
        }


class Query:
    def __init__(self):
        self.expression: str = ""
        self.functions: List[Dict[str, Any]] = []
        self.query_configs: List[QueryConfig] = []
        self.start_time: int = 0
        self.end_time: int = 0
        self.offset: int = 0
        self.low_mark: int = 0
        self.high_mark: Optional[int] = None

        # to be deprecation
        self.search_after_key: Optional[Dict[str, Any]] = None

    def clone(self) -> "Query":
        obj: "Query" = self.__class__()
        obj.expression = self.expression
        obj.functions = self.functions[:]
        obj.query_configs = self.query_configs[:]
        obj.start_time = self.start_time
        obj.end_time = self.end_time
        obj.offset = self.offset
        obj.low_mark = self.low_mark
        obj.high_mark = self.high_mark

        if self.search_after_key is not None:
            obj.search_after_key = self.search_after_key.copy()

        return obj

    def set_search_after_key(self, search_after_key: Optional[Dict[str, Any]]):
        # None 表示重置
        self.search_after_key = search_after_key

    def set_expression(self, expression: Optional[str]):
        if expression:
            self.expression = expression

    def add_f(self, func: Optional[Dict[str, Any]]):
        if func:
            self.functions.append(func)

    def add_q(self, query_config: Optional[QueryConfig]):
        if query_config:
            self.query_configs.append(query_config)

    def set_start_time(self, start_time: Optional[int]):
        if start_time:
            self.start_time = start_time

    def set_end_time(self, end_time: Optional[int]):
        if end_time:
            self.end_time = end_time

    def set_offset(self, offset: Optional[int]):
        if offset:
            self.offset = offset

    def set_limits(self, low: Optional[int] = None, high: Optional[int] = None):
        if high is not None:
            high = self.low_mark + high
            if self.high_mark is None:
                self.high_mark = high
            else:
                self.high_mark = min(high, self.high_mark)
        if low is not None:
            low = self.low_mark + low
            if self.high_mark is None:
                self.low_mark = low
            else:
                self.low_mark = min(self.high_mark, low)

    def get_limit(self) -> int:
        return (self.high_mark - self.low_mark, 0)[self.high_mark is None]

    def get_compiler(self) -> BaseCompiler:
        return UnifyQueryCompiler(self)


class UnifyQuerySet(DataQueryIterMixin):
    def __init__(self, query: Query = None):
        self.query = query or Query()
        self._result_cache = None

    def _clone(self):
        query = self.query.clone()
        clone = self.__class__(query=query)
        return clone

    def after(self, after_key: Optional[Dict[str, Any]] = None):
        clone = self._clone()
        clone.query.set_search_after_key(after_key)
        return clone

    def function(self, **kwargs):
        clone = self._clone()
        clone.query.add_f(kwargs)
        return clone

    def expression(self, expression: Optional[str]):
        clone = self._clone()
        clone.query.set_expression(expression)
        return clone

    def add_query(self, q: QueryConfigBuilder):
        clone = self._clone()
        clone.query.add_q(q.query_config)
        return clone

    def start_time(self, start_time: int):
        clone = self._clone()
        clone.query.set_start_time(start_time)
        return clone

    def end_time(self, end_time: int):
        clone = self._clone()
        clone.query.set_end_time(end_time)
        return clone

    def iterator(self) -> Iterable[Dict[str, Any]]:
        compiler: BaseCompiler = self.query.get_compiler()
        for row in compiler.execute():
            yield row

    def first(self) -> Optional[Dict[str, Any]]:
        clone = self._clone().limit(1)
        if len(clone):
            return clone[0]
        return None


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


class UnifyQueryBuilder:

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


class EsQueryBuilderMixin:
    DEFAULT_SORT_FIELD = None

    # 字段候选值最多获取500个
    OPTION_VALUES_MAX_SIZE = 500

    # 时间字段精 用于时间字段查询时做乘法
    TIME_FIELD_ACCURACY = 1000000

    @classproperty
    def operator_mapping(self):
        return {
            FilterOperator.EXISTS: lambda q, k, v: q.query("bool", filter=[ESQ("exists", field=k)]),
            FilterOperator.NOT_EXISTS: lambda q, k, v: q.query("bool", must_not=[ESQ("exists", field=k)]),
            FilterOperator.EQUAL: lambda q, k, v: q.query("bool", filter=[ESQ("terms", **{k: v})]),
            FilterOperator.NOT_EQUAL: lambda q, k, v: q.query("bool", must_not=[ESQ("terms", **{k: v})]),
            FilterOperator.BETWEEN: lambda q, k, v: q.query(
                "bool", filter=[ESQ("range", **{k: {"gte": v[0], "lte": v[1]}})]
            ),
            FilterOperator.LIKE: lambda q, k, v: q.query("bool", filter=[ESQ("wildcard", **{k: f'*{v[0]}*'})]),
            LogicSupportOperator.LOGIC: lambda q, k, v: self._add_logic_filter(q, k, v),
        }

    @classmethod
    def add_time(cls, query, start_time=None, end_time=None, time_field=None):
        if not start_time and not end_time:
            return query

        time_query = {}
        if start_time:
            time_query["gt"] = start_time * cls.TIME_FIELD_ACCURACY
        if end_time:
            time_query["lte"] = end_time * cls.TIME_FIELD_ACCURACY

        if not time_field:
            time_field = cls.DEFAULT_SORT_FIELD

        return query.filter("range", **{time_field: time_query})

    @classmethod
    def add_sort(cls, query, sort_field=None):

        if "sort" in query.to_dict():
            return query

        if not sort_field:
            return query.sort(f"-{cls.DEFAULT_SORT_FIELD}")

        return query.sort(sort_field)

    @classmethod
    def add_filter_params(cls, query, filter_params):

        for i in filter_params:
            query = cls.add_filter_param(query, i)

        return query

    @classmethod
    def add_filter_param(cls, query, filter_param):

        if filter_param["operator"] not in cls.operator_mapping:
            raise ValueError(_("不支持的查询操作符: %s") % (filter_param['operator']))

        key = cls._translate_key(filter_param["key"])
        return cls.operator_mapping[filter_param["operator"]](query, key, filter_param["value"])

    @classmethod
    def _add_logic_filter(cls, query, key, value):
        """生成特殊处理的Filters参数"""
        return query

    @classmethod
    def _translate_key(cls, key):
        return key

    @classmethod
    def distinct_fields(cls, query, field):

        query = query.extra(collapse={"field": field}, track_total_hits=True)
        cls.add_total_size(query, field)
        return query

    @classmethod
    def add_total_size(cls, query, field):
        query.aggs.bucket("total_size", A("cardinality", field=field))

    @classmethod
    def add_filter(cls, query, key, value):
        return query.query("bool", filter=[ESQ("term", **{key: value})])

    @classmethod
    def _query_option_values(cls, query, fields):

        for i in fields:
            query.aggs.bucket(f"{i}_values", A("terms", field=i, size=cls.OPTION_VALUES_MAX_SIZE))

        # 不返回文档，只返回聚合结果
        query = query.extra(size=0)
        print(f"[{cls.__name__}] query_option_values: {query.to_dict()}")
        response = query.execute()

        res = {}
        for field in fields:
            values = getattr(response.aggregations, f"{field}_values")
            res[field] = [i["key"] for i in values.buckets]

        return res


class FakeQuery:
    def list(self, *args, **kwargs):
        return [], 0

    def __getattr__(self, item):
        return lambda *args, **kwargs: None
