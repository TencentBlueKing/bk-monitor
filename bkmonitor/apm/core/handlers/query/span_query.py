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

from django.conf import settings

from apm import constants, types
from apm.core.handlers.query.base import BaseQuery
from apm.core.handlers.query.builder import QueryConfigBuilder, UnifyQuerySet
from apm.models.meta import TraceScopeIndexSet
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
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

    def _query_by_trace_id(self, trace_id: str, limit: int = constants.DISCOVER_BATCH_SIZE) -> list[dict[str, Any]]:
        queries: list[QueryConfigBuilder] = [
            q.order_by(OtlpKey.START_TIME).filter(**{f"{OtlpKey.TRACE_ID}__eq": trace_id})
            for q in self.build_queries(time_field=OtlpKey.START_TIME)
        ]
        return list(self._add_query(self.get_qs().limit(limit), queries))

    def _build_cross_queries(self, trace_id: str, trace_scope_table: str) -> list[QueryConfigBuilder]:
        return [
            QueryConfigBuilder(self.USING)
            .table(trace_scope_table)
            .order_by(OtlpKey.START_TIME)
            .filter(**{f"{OtlpKey.TRACE_ID}__eq": trace_id})
        ]

    def _cross_query_by_trace_id(self, trace_id: str) -> list[dict[str, Any]]:
        bk_tenant_id: str = bk_biz_id_to_bk_tenant_id(self.bk_biz_id)
        trace_scope_table: str | None = TraceScopeIndexSet.get_table(self.bk_biz_id, bk_tenant_id)
        if trace_scope_table is None:
            logger.warning(
                "[SpanQuery] trace_scope_table not found, fallback to application datasource: "
                "bk_tenant_id=%s, bk_biz_id=%s",
                bk_tenant_id,
                self.bk_biz_id,
            )
            return self._query_by_trace_id(trace_id)

        qs: UnifyQuerySet = self.get_qs().is_es_batch().limit(constants.DISCOVER_BATCH_SIZE)
        spans: list[dict[str, Any]] = list(self._add_query(qs, self._build_cross_queries(trace_id, trace_scope_table)))

        seen: set[str] = set()
        deduped_spans: list[dict[str, Any]] = []
        for span in spans:
            span_id: str = span.get(OtlpKey.SPAN_ID, "")
            if span_id not in seen:
                seen.add(span_id)
                deduped_spans.append(span)
        return deduped_spans

    def query_by_trace_id(self, trace_id: str, use_trace_scope: bool = True) -> list[dict[str, Any]]:
        if use_trace_scope and self.bk_biz_id in settings.APM_CROSS_APP_TRACE_SEARCH_SCOPE_WHITE_LIST:
            return self._cross_query_by_trace_id(trace_id)
        return self._query_by_trace_id(trace_id)

    def query_by_span_id(self, span_id: str) -> dict[str, Any] | None:
        queries: list[QueryConfigBuilder] = [
            q.order_by(f"{OtlpKey.START_TIME} desc").filter(**{f"{OtlpKey.SPAN_ID}__eq": span_id})
            for q in self.build_queries(time_field=OtlpKey.START_TIME)
        ]
        return self._add_query(self.get_qs(), queries).first()
