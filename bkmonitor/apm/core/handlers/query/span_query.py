"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - Resource SDK (BlueKing - Resource SDK) available.
Copyright (C) 2017-2025 Tencent,
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

import logging
from typing import Any

from django.db.models import Q

from apm import constants, types
from apm.core.handlers.query.base import BaseQuery
from apm.core.handlers.query.builder import QueryConfigBuilder, UnifyQuerySet
from constants.apm import OtlpKey, TraceDataSourceConfig

logger = logging.getLogger("apm")


class SpanQuery(BaseQuery):
    KEY_REPLACE_FIELDS = {"duration": "elapsed_time"}

    @classmethod
    def _get_select_fields(cls, exclude_fields: list[str] | None) -> list[str]:
        all_fields: set[str] = {field_info["field_name"] for field_info in TraceDataSourceConfig.TRACE_FIELD_LIST}
        # TraceDataSource.TRACE_FIELD_LIST 定义中缺失 time 字段的定义， time 属于平台内置字段，这里查询需要补充上
        all_fields.add("time")
        select_fields: list[str] = list(all_fields - set(exclude_fields or ["attributes", "links", "events"]))
        return select_fields

    def query_list(
        self,
        start_time: int | None,
        end_time: int | None,
        offset: int,
        limit: int,
        filters: list[types.Filter] | None = None,
        exclude_fields: list[str] | None = None,
        query_string: str | None = None,
        sort: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        select_fields: list[str] = self._get_select_fields(exclude_fields)
        queries: list[QueryConfigBuilder] = [
            q.order_by(*(sort or [f"{self.DEFAULT_TIME_FIELD} desc"])).values(*select_fields)
            for q in self.build_queries(filters, query_string)
        ]
        return self._query_list(queries, start_time, end_time, offset, limit)

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

        group_ids: list[str] = []
        for record in records:
            group_id: str | list[str] = record[group_field]
            if isinstance(group_id, list):
                group_id = group_id[0]
            group_ids.append(group_id)

        return group_ids

    def query_by_group_ids(
        self,
        group_field: str,
        group_ids: list[str],
        start_time: int | None = None,
        end_time: int | None = None,
        limit: int = constants.DISCOVER_BATCH_SIZE,
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
                Q(**{f"{OtlpKey.TRACE_ID}__include": value})
                | Q(**{f"{OtlpKey.SPAN_ID}__include": value})
                | Q(**{f"{OtlpKey.get_attributes_key('user.id')}__include": value})
                | Q(**{f"{OtlpKey.get_attributes_key('gen_ai.conversation.id')}__include": value})
            )
        return q

    def query_by_trace_id(
        self,
        trace_id: str,
        start_time: int | None = None,
        end_time: int | None = None,
        limit: int = constants.DISCOVER_BATCH_SIZE,
    ) -> list[dict[str, Any]]:
        queries: list[QueryConfigBuilder] = [
            q.order_by(OtlpKey.START_TIME).filter(**{f"{OtlpKey.TRACE_ID}__eq": trace_id})
            for q in self.build_queries(time_field=OtlpKey.START_TIME)
        ]
        # 跨业务目标无法收敛到同一空间，需要全局查询
        bk_biz_ids: set[int] = {data_source.app.bk_biz_id for data_source in self.data_sources}
        qs: UnifyQuerySet = self.get_qs(start_time, end_time, using_scope=len(bk_biz_ids) == 1).limit(limit)
        return list(self._add_query(qs, queries))

    def _cross_query_by_trace_id(
        self,
        table: str,
        trace_id: str,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> list[dict[str, Any]]:
        # 前缀模式不走 unify-query，时间范围由数据源自行拼装，只有时间字段非默认值才会把毫秒换算成微秒，
        # 因此统一指定微秒精度的时间字段，否则毫秒范围过滤微秒字段将查不到数据。
        qs: UnifyQuerySet = self.get_qs(start_time, end_time).is_es_batch().limit(constants.DISCOVER_BATCH_SIZE)
        data_sources: list[QueryConfigBuilder] = [
            QueryConfigBuilder(self.USING)
            .table(table)
            .time_field(OtlpKey.START_TIME)
            .order_by(OtlpKey.START_TIME)
            .filter(**{f"{OtlpKey.TRACE_ID}__eq": trace_id})
        ]

        spans: list[dict[str, Any]] = list(self._add_query(qs, data_sources))

        # 解决索引范围重叠导致的查询数据重复问题
        seen: set[str] = set()
        deduped_spans: list[dict[str, Any]] = []
        for span in spans:
            span_id: str = span.get(OtlpKey.SPAN_ID, "")
            if span_id not in seen:
                seen.add(span_id)
                deduped_spans.append(span)
        return deduped_spans

    def cross_query_by_trace_id(
        self,
        trace_id: str,
        trace_scope_table: str,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> list[dict[str, Any]]:
        """在 Trace 数据源域索引集中查询 Span"""
        return self._cross_query_by_trace_id(trace_scope_table, trace_id, start_time, end_time)

    def prefix_query_by_trace_id(
        self,
        trace_id: str,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> list[dict[str, Any]]:
        """前缀模式检索 Span"""
        prefix_table: str
        if self.bk_biz_id > 0:
            prefix_table = f"{self.bk_biz_id}_bkapm.trace_"
        else:
            prefix_table = f"space_{-self.bk_biz_id}_bkapm.trace_"

        return self._cross_query_by_trace_id(f"PREFIX#{prefix_table}", trace_id, start_time, end_time)

    def query_by_span_id(self, span_id: str) -> dict[str, Any] | None:
        queries: list[QueryConfigBuilder] = [
            q.order_by(f"{OtlpKey.START_TIME} desc").filter(**{f"{OtlpKey.SPAN_ID}__eq": span_id})
            for q in self.build_queries(time_field=OtlpKey.START_TIME)
        ]
        return self._add_query(self.get_qs(), queries).first()
