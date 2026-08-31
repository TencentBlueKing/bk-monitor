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

from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder, UnifyQuerySet
from bkmonitor.data_source.utils import types
from bkmonitor.data_source.utils.apm import APMQueryFilterMixin, TraceDatasourceTarget, TraceQueryGuard
from constants.apm import OtlpKey

from apm_web.handlers.query.span import SpanQuery


class LLMQuery(APMQueryFilterMixin, SpanQuery):
    """查询 LLM Trace 与会话。"""

    DEFAULT_TIME_FIELD = OtlpKey.END_TIME
    KEY_REPLACE_FIELDS = {"duration": "elapsed_time"}

    def get_qs(
        self,
        start_time: int | None = None,
        end_time: int | None = None,
        using_scope: bool = True,
    ) -> UnifyQuerySet:
        queryset = super().get_qs(start_time, end_time)
        if not using_scope:
            return queryset

        bk_biz_ids = {data_source.app.bk_biz_id for data_source in self.data_sources}
        if len(bk_biz_ids) != 1:
            return queryset
        return queryset.scope(bk_biz_ids.pop())

    def build_queries(
        self,
        filters: list[types.Filter] | None = None,
        query_string: str | None = "",
        time_field: str | None = None,
    ) -> list[QueryConfigBuilder]:
        return [
            TraceQueryGuard.get_q([data_source])
            .time_field(time_field or self.DEFAULT_TIME_FIELD)
            .filter(self._build_filters(filters))
            .query_string(query_string or "")
            for data_source in self.data_sources
        ]

    def query_group_list(
        self,
        start_time: int | None,
        end_time: int | None,
        group_field: str,
        offset: int,
        limit: int,
        filters: list[types.Filter] | None = None,
        query_string: str | None = None,
    ) -> list[str]:
        queries = [
            query.distinct(group_field).values(group_field).order_by(f"{self.DEFAULT_TIME_FIELD} desc")
            for query in self.build_queries(filters, query_string)
        ]
        records = self._query_list(queries, start_time, end_time, offset, limit)
        return [record[group_field] for record in records]

    def query_by_group_ids(
        self,
        group_field: str,
        group_ids: list[str],
        start_time: int | None = None,
        end_time: int | None = None,
        limit: int = SpanQuery.QUERY_MAX_LIMIT,
    ) -> list[dict[str, Any]]:
        queries = [
            query.order_by(OtlpKey.START_TIME).filter(**{f"{group_field}__eq": group_ids})
            for query in self.build_queries(time_field=OtlpKey.START_TIME)
        ]
        return self._query_list(queries, start_time, end_time, 0, limit)

    @classmethod
    def _add_logic_filter(cls, q: Q, field: str, value: types.FilterValue) -> Q:
        if field == "keyword":
            return q & (
                Q(**{f"{OtlpKey.TRACE_ID}__eq": value})
                | Q(**{f"{OtlpKey.SPAN_ID}__eq": value})
                | Q(**{f"{OtlpKey.get_attributes_key('user.id')}__include": value})
                | Q(**{f"{OtlpKey.get_attributes_key('gen_ai.conversation.id')}__include": value})
            )
        return q


def get_query(data_sources: list[TraceDatasourceTarget]) -> LLMQuery:
    """根据数据源构造 LLM 查询对象。"""

    return LLMQuery(data_sources)
