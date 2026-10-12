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

from bkm_space.utils import bk_biz_id_to_space_uid
from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder, UnifyQuerySet
from bkmonitor.data_source.utils import types
from bkmonitor.data_source.utils.apm import APMQueryFilterMixin, TraceQueryGuard
from constants.apm import OtlpKey
from constants.otel_query import FIELD_OPERATIONS, OTEL_SPAN_COMMON_FIELD_ALIAS

from apm_web.handlers.query.base import BaseQuery
from apm_web.trace.constants import TRACE_FIELD_ALIAS


class SpanQuery(APMQueryFilterMixin, BaseQuery):
    """通过 unify-query 查询 APM Span。"""

    DEFAULT_TIME_FIELD = OtlpKey.END_TIME
    KEY_REPLACE_FIELDS = {"duration": "elapsed_time"}
    FIELD_ALIAS_MAP_LIST: list[dict[str, Any]] = [OTEL_SPAN_COMMON_FIELD_ALIAS, TRACE_FIELD_ALIAS]
    FIELD_OPERATIONS = FIELD_OPERATIONS

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

    def query_fields(self, start_time: int | None, end_time: int | None) -> dict[str, dict[str, Any]]:
        """查询 Span 字段，缺省时间范围由 Target 的数据保留期补齐。"""

        return super()._query_fields(
            [
                (data_source.table_id, bk_biz_id_to_space_uid(data_source.app.bk_biz_id))
                for data_source in self.data_sources
            ],
            start_time,
            end_time,
        )
