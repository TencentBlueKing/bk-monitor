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

from bkmonitor.data_source.utils import types
from bkmonitor.data_source.utils.base import sort_fields
from bkmonitor.data_source.utils.query import BaseQuery
from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder, UnifyQuerySet
from bkmonitor.data_source.utils.apm import TraceDatasourceTarget, APMQueryFilterMixin
from bkm_space.utils import bk_biz_id_to_space_uid
from constants.data_source import DataSourceLabel, DataTypeLabel
from constants.otel_query import FIELD_OPERATIONS, OTEL_SPAN_COMMON_FIELD_ALIAS

from rum_web.constants import RUM_FIELD_ALIAS, RumSpanType, RumSpanKind, RumSpanStatusCode, RumDeviceType


class SpanQuery(APMQueryFilterMixin, BaseQuery):
    USING: tuple[str, str] = (DataTypeLabel.LOG, DataSourceLabel.BK_RUM)
    DEFAULT_TIME_FIELD = "end_time"
    DEFAULT_SORT = ["-end_time"]
    FIELD_ALIAS_MAP_LIST = [OTEL_SPAN_COMMON_FIELD_ALIAS, RUM_FIELD_ALIAS]
    FIELD_OPERATIONS = FIELD_OPERATIONS
    FIELD_UNITS = {
        "elapsed_time": "us",
    }
    ENUM_FIELD_OPTION_VALUES = {
        field_name: [{"value": value, "alias": alias} for value, alias in enum_class.choices()]
        for field_name, enum_class in [
            ("attributes.span_type", RumSpanType),
            ("kind", RumSpanKind),
            ("status.code", RumSpanStatusCode),
            ("resource.device.type", RumDeviceType),
        ]
    }

    def __init__(self, data_sources: list[TraceDatasourceTarget]):
        self.data_sources = data_sources

    @property
    def retention(self) -> int:
        """数据保留天数（天），取所有数据源保留期的最小值以保证查询在有效窗口内。"""
        retention: int | None = self.data_sources[0].retention
        if retention is None:
            raise ValueError("RUM 查询数据源必须设置 retention")
        return retention

    @classmethod
    def build_query_q(cls, q: QueryConfigBuilder, filters: list[types.Filter] | None, query_string: str = ""):
        return q.filter(cls._build_filters(filters)).query_string(query_string)

    def get_queries(
        self, filters: list[types.Filter] | None = None, query_string: str = ""
    ) -> list[QueryConfigBuilder]:
        return [
            self.build_query_q(
                self._get_q().table(ds.table_id),
                filters,
                query_string,
            )
            for ds in self.data_sources
        ]

    def get_qs(self, start_time: int, end_time: int, using_scope: bool = True) -> UnifyQuerySet:
        qs = super().get_qs(start_time, end_time)
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
        processed_sort_fields = self.process_sort_fields(sort or self.DEFAULT_SORT)
        queries = [q.order_by(*processed_sort_fields) for q in self.get_queries(filters, query_string)]
        return sort_fields(super()._query_list(queries, start_time, end_time, offset, limit), processed_sort_fields)

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

    def query_option_values(
        self,
        start_time: int,
        end_time: int,
        fields: list[str],
        limit: int,
        filters: list[types.Filter],
        query_string: str,
    ):
        return super()._query_option_values(
            self.get_queries(filters, query_string), start_time, end_time, fields, limit
        )

    def query_fields(self, start_time: int | None, end_time: int | None) -> dict[str, dict[str, Any]]:
        return super()._query_fields(
            [(target.table_id, bk_biz_id_to_space_uid(target.app.bk_biz_id)) for target in self.data_sources],
            start_time,
            end_time,
        )
