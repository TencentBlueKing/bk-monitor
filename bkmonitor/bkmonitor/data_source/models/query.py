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
from typing import Any, Dict, List, Optional, Tuple

from django.db.models import Q

from bkmonitor.data_source.models import sql
from bkmonitor.data_source.models.data_structure import DataPoint


class IterMixin:
    """数据遍历相关"""

    def __getitem__(self, k):
        """
        Retrieves an item or slice from the set of results.
        """
        if not isinstance(k, (slice, int)):
            raise TypeError

        if self._result_cache is not None:
            return self._result_cache[k]

        if isinstance(k, slice):
            if k.start is not None:
                start = int(k.start)
            else:
                start = None
            if k.stop is not None:
                stop = int(k.stop)
            else:
                stop = None
            self.query.set_limits(start, stop)
            return list(self)[:: k.step] if k.step else self

        self.query.set_limits(k, k + 1)
        return list(self)[0]

    def __len__(self):
        self._fetch_all()
        return len(self._result_cache)

    def __iter__(self):
        self._fetch_all()
        return iter(self._result_cache)

    def __bool__(self):
        self._fetch_all()
        return bool(self._result_cache)

    def all(self):
        return self.data

    def limit(self, k):
        clone = self._clone()
        clone.query.set_limits(high=k)
        return clone

    def slimit(self, s):
        return self._clone()

    def offset(self, o):
        clone = self._clone()
        clone.query.set_offset(o)
        return clone

    def _fetch_all(self):
        if self._result_cache is None:
            self._result_cache = list(self.iterator())

    @property
    def raw_data(self):
        self._fetch_all()
        return self._result_cache

    @property
    def data(self):
        self._fetch_all()
        data = []
        for row in self._result_cache:
            data.append(DataPoint(row))
        return data

    def iterator(self):
        compiler = self.query.get_compiler(using=self.using)
        results = compiler.execute_sql()
        for row in results:
            yield row

    @property
    def original_data(self):
        compiler = self.query.get_compiler(using=self.using)
        original_sql, params = compiler.as_sql()
        return compiler.connection.execute(original_sql, params)

    def first(self) -> Optional[Dict[str, Any]]:
        clone = self._clone().limit(1)
        if len(clone):
            return clone[0]
        return None


class QueryMixin:
    """数据查询相关"""

    def table(self, table_name: str):
        clone = self._clone()
        clone.query.table_name = table_name
        return clone

    from_ = db = table

    def values(self, *fields):
        clone = self._clone()
        for field in fields:
            clone.query.add_select(field)
        return clone

    select = values

    def time_field(self, field: str):
        clone = self._clone()
        clone.query.set_time_field(field)
        return clone

    def filter(self, *args, **kwargs):
        clone = self._clone()
        clone.query.add_q(Q(*args, **kwargs))
        return clone

    where = filter

    def group_by(self, *fields):
        clone = self._clone()
        clone.query.add_grouping(*fields)
        return clone

    def order_by(self, *fields):
        clone = self._clone()
        clone.query.add_ordering(*fields)
        return clone

    def distinct(self, field: Optional[str]):
        clone = self._clone()
        if field:
            clone.query.distinct = field
        return clone


class DslMixin:
    """ES DSL 相关"""

    def use_full_index_names(self, use_full_index_names: Optional[bool]):
        clone = self._clone()
        if use_full_index_names is not None:
            clone.query.use_full_index_names = use_full_index_names
        return clone

    def dsl_raw_query_string(self, query_string: str, nested_paths: Optional[Dict[str, str]] = None):
        clone = self._clone()
        clone.query.raw_query_string = query_string
        if nested_paths:
            clone.query.nested_paths = nested_paths
        return clone

    def dsl_index_set_id(self, index_set_id: int):
        clone = self._clone()
        clone.query.index_set_id = index_set_id
        return clone

    def dsl_group_hits(self, size: int = 1):
        clone = self._clone()
        clone.query.group_hits_size = size
        return clone

    def dsl_search_after(self, search_after_key: Optional[Dict[str, Any]]):
        clone = self._clone()
        if search_after_key is not None:
            clone.query.search_after_key = search_after_key
        return clone

    def dsl_date_histogram(self, enable: bool):
        clone = self._clone()
        clone.query.enable_date_histogram = enable
        return clone


class BaseDataQuery:

    TYPE = "base"
    QUERY_CLASS = sql.Query

    def __init__(self, using: Tuple[str, str], query=None):
        self.using: Tuple[str, str] = using
        self.query = query or self.QUERY_CLASS(self.using)
        self._result_cache: Optional[List[Any]] = None

    def _clone(self):
        query = self.query.clone()
        clone = self.__class__(using=self.using, query=query)
        return clone


class DataQuery(BaseDataQuery, IterMixin, QueryMixin, DslMixin):
    def target_type(self, target_type):
        clone = self._clone()
        clone.query.set_target_type(target_type)
        return clone

    def raw(self, raw_query, params=None):
        return sql.RawQuery(raw_query, using=self.using, params=params).execute_query()

    def metrics(self, metrics: List[Dict]):
        clone = self._clone()
        for metric in metrics:
            alias = metric.get("alias")
            if metric.get("method"):
                select_str = f"{metric['method']}({metric['field']})"
                alias = alias or metric["field"]
            else:
                select_str = metric["field"]

            if alias:
                select_str += f" as {alias}"
            clone.query.add_select(select_str)
        return clone

    def agg_condition(self, agg_condition):
        clone = self._clone()
        clone.query.set_agg_condition(agg_condition)
        return clone
