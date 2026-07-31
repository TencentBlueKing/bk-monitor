"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any

from django.db.models import Q

from bkmonitor.data_source.utils import types
from bkmonitor.data_source.utils.query import BaseQuery
from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder, UnifyQuerySet
from bkmonitor.data_source.utils.apm import TraceDatasourceTarget, FilterOperator, LogicSupportOperator
from constants.data_source import DataSourceLabel, DataTypeLabel


class SpanQuery(BaseQuery):
    USING_LOG: tuple[str, str] = (DataTypeLabel.LOG, DataSourceLabel.BK_APM)

    def __init__(self, data_sources: list[TraceDatasourceTarget]):
        self.data_sources = data_sources

    @classmethod
    def _add_logic_filter(cls, q: Q, field: str, value: types.FilterValue) -> Q:
        return q

    @classmethod
    def _build_filters(cls, filters: list[types.Filter] | None) -> Q:
        if not filters:
            return Q()

        q: Q = Q()
        for f in filters:
            operator = f["operator"]
            key = cls._translate_field(f["key"])
            # 更新 q，叠加查询条件
            if operator == LogicSupportOperator.LOGIC:
                q = cls._add_logic_filter(q, key, f["value"])
            else:
                q = FilterOperator.get_handler(operator)(q, operator, key, f["value"], f.get("options", {}))
        return q

    @classmethod
    def build_query_q(cls, q: QueryConfigBuilder, filters: list[types.Filter] | None, query_string: str = ""):
        return q.filter(cls._build_filters(filters)).query_string(query_string)

    def get_queries(
        self, filters: list[types.Filter] | None = None, query_string: str = ""
    ) -> list[QueryConfigBuilder]:
        return [
            self.build_query_q(
                QueryConfigBuilder(self.USING_LOG).table(ds.table_id).time_field(self.DEFAULT_TIME_FIELD),
                filters,
                query_string,
            )
            for ds in self.data_sources
        ]

    def time_range_queryset(self, start_time: int, end_time: int, using_scope: bool = True) -> UnifyQuerySet:
        qs = super().time_range_queryset(start_time, end_time)
        if not using_scope:
            return qs

        bk_biz_ids = {ds.app.bk_biz_id for ds in self.data_sources}
        if len(bk_biz_ids) != 1:
            return qs
        return qs.scope(bk_biz_ids.pop())

    def query_list(
        self,
        start_time: int,
        end_time: int,
        offset: int,
        limit: int,
        filters: list[types.Filter] | None = None,
        query_string: str = "",
        sort: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        queries = [
            q.order_by(*self.process_sort_fields(sort or self.DEFAULT_SORT))
            for q in self.get_queries(filters, query_string)
        ]
        return super()._query_list(queries, start_time, end_time, offset, limit)

    def query_total(
        self,
        start_time: int,
        end_time: int,
        filters: list[types.Filter] | None = None,
        query_string: str = "",
    ) -> int:
        return super()._query_total(self.get_queries(filters, query_string), start_time, end_time)

    def query_field_topk(
        self,
        start_time: int,
        end_time: int,
        field: str,
        limit: int = 5,
        filters: list[types.Filter] | None = None,
        query_string: str = "",
        need_empty: bool = False,
    ):
        return super()._query_field_topk(
            self.get_queries(filters, query_string), start_time, end_time, field, limit, need_empty
        )
