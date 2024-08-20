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

import abc
import logging
from typing import Any, Dict, Iterable, List, Optional, Tuple

from django.db.models import Q
from django.db.models.sql import AND

from bkmonitor.data_source import load_data_source
from bkmonitor.data_source.data_source import DataSource, q_to_dict
from bkmonitor.data_source.models.query import DataQueryIterMixin
from bkmonitor.data_source.models.sql.where import WhereNode
from bkmonitor.data_source.unify_query.query import UnifyQuery

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
- unify 支持配置多个 datasource 进行聚合计算，在之前 datasource 的基础上，需要对 unify query 也进行相应的封装，这是【目前没有】的

这里会不会新增了很多代码？ 【不会】，基本还是复用 datasource，新增 200+ 左右的代码，用于把 unify[query_configs] 部分查询 ORM 化

其他模块可不可以复用？【可以】，不稳定阶段先放到 apm 下踩坑完善

查询结构的 dict 构造，相比于 queryset 有什么劣势？
- 从复用度来讲，无论哪种方式【都需要进行一定的抽象封装】，才能达到相似查询代码复用的目的
- 从实现代码量上说，【两者差不多】，但后者的收益更高，因为抽象的内容具有被其他模块复用的可能
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
