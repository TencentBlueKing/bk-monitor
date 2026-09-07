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
from bkmonitor.data_source.utils.apm import TraceDatasourceTarget
from constants.apm import OtlpKey

from apm_web.handlers.query.span import SpanQuery


class LLMQuery(SpanQuery):
    """查询 LLM Trace 与会话。"""

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

    def query_group_trace_list(
        self,
        group_field: str,
        group_ids: list[str],
        limit: int = SpanQuery.QUERY_MAX_LIMIT,
    ) -> list[dict[str, Any]]:
        fields = [group_field]
        if group_field != OtlpKey.TRACE_ID:
            fields.append(OtlpKey.TRACE_ID)
        queries = [
            query.filter(**{f"{group_field}__eq": group_ids}).distinct(OtlpKey.TRACE_ID).values(*fields)
            for query in self.build_queries()
        ]
        return self._query_list(queries, None, None, 0, limit)

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
