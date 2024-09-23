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
import itertools
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

from bkmonitor.data_source import load_data_source
from bkmonitor.data_source.backends.base.compiler import SQLCompiler
from bkmonitor.data_source.backends.base.connection import BaseDatabaseConnection
from bkmonitor.data_source.backends.base.operations import BaseDatabaseOperations
from bkmonitor.data_source.data_source import DataSource, q_to_dict
from bkmonitor.data_source.models.query import (
    BaseDataQuery,
    DslMixin,
    IterMixin,
    QueryMixin,
)
from bkmonitor.data_source.models.sql import Query
from bkmonitor.data_source.models.sql.query import get_limit_range
from bkmonitor.data_source.models.sql.where import WhereNode
from bkmonitor.data_source.unify_query.query import UnifyQuery

logger = logging.getLogger("apm")


"""
做了什么：复用已有 datasource 模块，支持使用类 ORM 模式进行 UnifyQuery 查询

背景：
- 监控统一查询结构目前主要供前端数据检索/告警配置使用，由【前端拼接参数】，后台负责解析查询
- APM 存在预计算路由，服务接口统计等复杂查询场景，可能需要对多结果表进行聚合查询，所以在后台有一个模块提供查询功能

解决了什么问题？
- 在切换到 UnifyQuery 的背景下，后台查询模块也需要和前端一样，拼接通用查询参数，查询 ES or UnifyQuery
- 在过程中发现每个场景的查询都在进行相似的数据结构拼装，过于重复冗长，基于 unify[query_configs] 场景进行类 ORM 的封装
- 后台逻辑实现从 dict 构造转为基于查询条件编写 ORM 语句，提升可维护和可读性

不稳定阶段先放到 apm 下踩坑完善，验证完成后可以考虑往 datasource 下沉，供其他模块使用
"""


class QueryConfig(Query):
    def __init__(self, using: Tuple[str, str], where: Type[WhereNode] = WhereNode):
        super().__init__(using, where)

        self.reference_name: str = ""
        self.metrics: List[Dict[str, Any]] = []
        self.dimension_fields: List[str] = []

    def clone(self) -> "QueryConfig":
        obj: "QueryConfig" = super().clone()
        obj.reference_name = self.reference_name
        obj.metrics = self.metrics[:]
        obj.dimension_fields = self.dimension_fields[:]
        return obj

    def set_reference_name(self, reference_name: Optional[str]):
        if reference_name:
            self.reference_name = reference_name

    def add_metric(self, field: str, method: str, alias: Optional[str] = ""):
        self.metrics.append({"field": field, "alias": alias or method, "method": method})

    def add_dimension_fields(self, field: str):
        if field not in self.dimension_fields:
            self.dimension_fields.append(field)


class QueryConfigBuilder(BaseDataQuery, QueryMixin, DslMixin):
    QUERY_CLASS = QueryConfig

    def alias(self, alias: Optional[str]) -> "QueryConfigBuilder":
        clone = self._clone()
        clone.query.set_reference_name(alias)
        return clone

    def metric(self, field: str, method: str, alias: Optional[str] = "") -> "QueryConfigBuilder":
        clone = self._clone()
        clone.query.add_metric(field, method, alias)
        return clone

    def tag_values(self, *fields) -> "QueryConfigBuilder":
        clone = self._clone()
        for field in fields:
            clone.query.add_dimension_fields(field)
        return clone

    """以下只是显示声明支持方法，同时供 IDE 补全"""

    def table(self, table_name: str) -> "QueryConfigBuilder":
        return super().table(table_name)

    def values(self, *fields) -> "QueryConfigBuilder":
        return super().values(*fields)

    def filter(self, *args, **kwargs) -> "QueryConfigBuilder":
        return super().filter(*args, **kwargs)

    def group_by(self, *fields) -> "QueryConfigBuilder":
        return super().group_by(*fields)

    def order_by(self, *fields) -> "QueryConfigBuilder":
        return super().order_by(*fields)

    def time_field(self, field: str) -> "QueryConfigBuilder":
        return super().time_field(field)

    def query_string(self, query_string: str, nested_paths: Optional[Dict[str, str]] = None) -> "QueryConfigBuilder":
        return super().dsl_raw_query_string(query_string, nested_paths)


class QueryHelper:
    @classmethod
    def _query_log(cls, unify_query: UnifyQuery, query_body: Dict[str, Any]) -> List[Dict[str, Any]]:
        data, __ = unify_query.query_log(
            start_time=query_body["start_time"],
            end_time=query_body["end_time"],
            limit=query_body["limit"],
            offset=query_body["offset"],
            search_after_key=query_body["search_after_key"],
        )
        return data

    @classmethod
    def _query_data(cls, unify_query: UnifyQuery, query_body: Dict[str, Any]) -> List[Dict[str, Any]]:
        data = unify_query.query_data(
            start_time=query_body["start_time"],
            end_time=query_body["end_time"],
            limit=query_body["limit"],
            offset=query_body["offset"],
            search_after_key=query_body["search_after_key"],
        )
        return data

    @classmethod
    def _query_dimensions(cls, unify_query: UnifyQuery, query_body: Dict[str, Any]) -> List[Dict[str, Any]]:
        dimension_fields: List[str] = query_body["dimension_fields"]
        data = unify_query.query_dimensions(
            dimension_field=dimension_fields,
            start_time=query_body["start_time"],
            end_time=query_body["end_time"],
            limit=query_body["limit"],
        )

        values_list: List[List[str]] = []
        dimension_field_values_mapping: Dict[str] = data.get("values") or {}
        for dimension_field in dimension_fields:
            values_list.append(dimension_field_values_mapping.get(dimension_field) or [])

        # ["a", "b", "c"] + [["a1", "b2", "b3"]] -> [{"a": "a1", "b": "b1", "c": "c1"}]
        dimensions: List[Dict[str, Any]] = []
        for dimension_values in itertools.product(*values_list):
            # refer: https://stackoverflow.com/questions/209840
            dimensions.append(dict(zip(dimension_fields, dimension_values)))
        return dimensions

    @classmethod
    def _get_query_func(
        cls, query_body: Dict[str, Any]
    ) -> Callable[[UnifyQuery, Dict[str, Any]], List[Dict[str, Any]]]:
        # 1. Dimensions
        if query_body.get("dimension_fields"):
            return cls._query_dimensions

        # 2. Data
        for query_config in query_body.get("query_configs") or []:
            if query_config.get("metrics"):
                return cls._query_data

        # 3. Log
        return cls._query_log

    @classmethod
    def query(cls, table_id: str, query_body: Dict[str, Any]) -> List[Dict[str, Any]]:

        logger.info("[QueryHelper] table_id -> %s query_body -> %s", table_id, query_body)

        data_sources: List[DataSource] = []
        for query_config in query_body["query_configs"]:
            data_source_class = load_data_source(query_config["data_source_label"], query_config["data_type_label"])
            data_source = data_source_class(
                bk_biz_id=query_body["bk_biz_id"], use_full_index_names=True, **query_config
            )
            data_sources.append(data_source)

        unify_query: UnifyQuery = UnifyQuery(
            bk_biz_id=query_body["bk_biz_id"],
            data_sources=data_sources,
            expression=query_body["expression"],
            functions=query_body["functions"],
        )

        return cls._get_query_func(query_body)(unify_query, query_body)


class UnifyQueryCompiler(SQLCompiler):
    def as_sql(self) -> Tuple[str, Dict[str, Any]]:
        query_configs: List[Dict[str, Any]] = []
        for query_config_obj in self.query.query_configs:
            query_config = {
                "data_type_label": query_config_obj.using[0],
                "data_source_label": query_config_obj.using[1],
                "reference_name": query_config_obj.reference_name or "a",
                "table": query_config_obj.table_name,
                "time_field": query_config_obj.time_field,
                "select": query_config_obj.select,
                "distinct": query_config_obj.distinct,
                "where": [],
                "metrics": query_config_obj.metrics,
                "group_by": query_config_obj.group_by,
                "dimension_fields": query_config_obj.dimension_fields or [],
                "filter_dict": q_to_dict(query_config_obj.where),
                "query_string": query_config_obj.raw_query_string or "*",
                "nested_paths": query_config_obj.nested_paths,
                "order_by": query_config_obj.order_by,
            }
            query_configs.append(query_config)

        return "unifyquery", {
            "bk_biz_id": None,
            "query_configs": query_configs,
            "dimension_fields": query_configs[0]["dimension_fields"],
            "functions": self.query.functions,
            "expression": self.query.expression or query_configs[0]["reference_name"],
            "limit": self.query.get_limit(),
            "offset": self.query.offset,
            "start_time": self.query.start_time,
            "end_time": self.query.end_time,
            "search_after_key": self.query.search_after_key,
        }


class DatabaseOperations(BaseDatabaseOperations):
    compiler_module = "apm.core.handlers.query.builder"


class DatabaseConnection(BaseDatabaseConnection):
    vendor = "unifyquery"
    prefer_storage = "unifyquery"

    def __init__(self, query_func):
        self.query_func = query_func
        self.ops = DatabaseOperations(self)

    def execute(self, table_id: str, query_body: Dict[str, Any]):
        return self.query_func(table_id=table_id, query_body=query_body)


class UnifyQueryConfig:

    compiler = "UnifyQueryCompiler"

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

    def clone(self) -> "UnifyQueryConfig":
        obj: "UnifyQueryConfig" = self.__class__()
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
        self.low_mark, self.high_mark = get_limit_range(low, high, self.low_mark, self.high_mark)

    def get_limit(self) -> int:
        return (self.high_mark - self.low_mark, 0)[self.high_mark is None]

    def get_compiler(self, using: Optional[Tuple[str, str]] = None) -> SQLCompiler:
        connection: DatabaseConnection = DatabaseConnection(QueryHelper.query)
        return connection.ops.compiler(self.compiler)(self, connection, using)


class UnifyQuerySet(IterMixin):
    def __init__(self, query: UnifyQueryConfig = None):
        self.using = None
        self._result_cache = None
        self.query = query or UnifyQueryConfig()

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
        clone.query.add_q(q.query)
        return clone

    def start_time(self, start_time: int):
        clone = self._clone()
        clone.query.set_start_time(start_time)
        return clone

    def end_time(self, end_time: int):
        clone = self._clone()
        clone.query.set_end_time(end_time)
        return clone
