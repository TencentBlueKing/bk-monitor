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

import logging
from typing import Any

from apm import constants, types
from apm.core.handlers.query.base import BaseQuery
from apm.core.handlers.query.builder import QueryConfigBuilder, UnifyQuerySet
from apm.models import TraceDataSource
from constants.apm import OtlpKey

logger = logging.getLogger("apm")


class SpanQuery(BaseQuery):
    KEY_REPLACE_FIELDS = {"duration": "elapsed_time"}

    @classmethod
    def _get_select_fields(cls, exclude_fields: list[str] | None) -> list[str]:
        all_fields: set[str] = {field_info["field_name"] for field_info in TraceDataSource.TRACE_FIELD_LIST}
        select_fields: list[str] = list(all_fields - set(exclude_fields or ["attributes", "links", "events"]))
        return select_fields

    def query_list(
        self,
        start_time: int | None,
        end_time: int | None,
        offset: int,
        limit: int,
        filters: list[types.Filter] | None = None,
        es_dsl: dict[str, Any] | None = None,
        exclude_fields: list[str] | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        select_fields: list[str] = self._get_select_fields(exclude_fields)
        queryset: UnifyQuerySet = self.time_range_queryset(start_time, end_time)
        q: QueryConfigBuilder = self.q.filter(self._build_filters(filters)).order_by(
            *(self._parse_ordering_from_dsl(es_dsl) or [f"{self.DEFAULT_TIME_FIELD} desc"])
        )
        q = self._add_filters_from_dsl(q, es_dsl)
        page_data: types.Page = self._get_data_page(q, queryset, select_fields, OtlpKey.SPAN_ID, offset, limit)
        return page_data["data"], page_data["total"]

    def query_option_values(
        self, datasource_type: str, start_time: int | None, end_time: int | None, fields: list[str]
    ) -> dict[str, list[str]]:
        q: QueryConfigBuilder = self._get_q(datasource_type)
        return self._query_option_values(q, fields, start_time, end_time)

    def query_by_trace_id(self, trace_id: str) -> list[dict[str, Any]]:
        q: QueryConfigBuilder = (
            self.q.time_field(OtlpKey.START_TIME)
            .order_by(OtlpKey.START_TIME)
            .filter(**{f"{OtlpKey.TRACE_ID}__eq": trace_id})
        )
        return list(self.time_range_queryset().add_query(q).limit(constants.DISCOVER_BATCH_SIZE))

    def query_by_span_id(self, span_id) -> dict[str, Any] | None:
        q: QueryConfigBuilder = (
            self.q.time_field(OtlpKey.START_TIME)
            .order_by(f"{OtlpKey.START_TIME} desc")
            .filter(**{f"{OtlpKey.SPAN_ID}__eq": span_id})
        )
        return self.time_range_queryset().add_query(q).first()

    def query_field_topk(
        self,
        start_time: int | None,
        end_time: int | None,
        field: str,
        limit: int,
        filters: list[types.Filter] | None = None,
        query_string: str | None = None,
    ):
        return self._query_field_topk(start_time, end_time, field, limit, filters, query_string)

    def query_total(
        self,
        start_time: int | None,
        end_time: int | None,
        filters: list[types.Filter] | None = None,
        query_string: str | None = None,
    ):
        return self._query_total(start_time, end_time, filters, query_string)

    def query_field_aggregated_value(
        self,
        start_time: int | None,
        end_time: int | None,
        field: str,
        method: str,
        filters: list[types.Filter] | None = None,
        query_string: str | None = None,
        need_empty: bool = True,
    ):
        q: QueryConfigBuilder = self.get_q_from_filters_and_query_string(filters, query_string)
        if not need_empty:
            q = q.filter(**{f"{field}__ne": ""})
        return self._query_field_aggregated_value(start_time, end_time, field, method, q)
