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

from apm import types
from apm.core.handlers.ebpf.base import EbpfHandler
from apm.core.handlers.query.base import BaseQuery
from apm.core.handlers.query.builder import QueryConfigBuilder, UnifyQuerySet
from apm.models import ApmApplication
from constants.apm import OtlpKey, PrecalculateStorageConfig

logger = logging.getLogger("apm")


class TraceQuery(BaseQuery):
    LEVEL_NAME = "trace"
    DEFAULT_TIME_FIELD = "min_start_time"

    KEY_PREFIX_TRANSLATE_FIELDS = {
        f"{OtlpKey.ATTRIBUTES}.": "collections",
        f"{OtlpKey.RESOURCE}.": "collections",
        OtlpKey.KIND: "collections",
        OtlpKey.SPAN_NAME: "collections",
    }

    KEY_REPLACE_FIELDS = {"duration": "trace_duration"}

    @classmethod
    def _get_select_fields(cls, exclude_fields: list[str] | None) -> list[str]:
        all_fields: set[str] = {field_info["field_name"] for field_info in PrecalculateStorageConfig.TABLE_SCHEMA}
        select_fields: list[str] = list(
            all_fields - set(exclude_fields or ["collections", "bk_app_code", "biz_name", "root_span_id"])
        )
        return select_fields

    def build_app_filter(self) -> Q:
        return Q(biz_id__eq=self.bk_biz_id, app_name__eq=self.app_name)

    def build_queries(
        self,
        filters: list[types.Filter] | None = None,
        query_string: str | None = "",
        time_field: str | None = None,
    ) -> list[QueryConfigBuilder]:
        table_ids: list[str] = [
            table_id
            for data_source in self.data_sources
            for table_id in data_source.get_level_table_ids(self.LEVEL_NAME)
        ]
        queries: list[QueryConfigBuilder] = [
            QueryConfigBuilder(self.USING).table(table_id).time_field(time_field or self.DEFAULT_TIME_FIELD)
            for table_id in table_ids
        ]
        return [
            q.filter(self._build_filters(filters)).query_string(query_string or "").filter(self.build_app_filter())
            for q in queries
        ]

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

    def _get_ebpf_application(self) -> ApmApplication | None:
        return EbpfHandler.get_ebpf_application(self.bk_biz_id)

    def query_relation_by_trace_id(
        self, trace_id: str, start_time: int | None, end_time: int | None
    ) -> dict[str, Any] | None:
        """查询此traceId是否有跨应用关联（需要排除此业务下的EBPF应用）"""
        exclude_app_names: list[str] = [self.app_name]
        ebpf_application: ApmApplication | None = self._get_ebpf_application()
        if ebpf_application:
            exclude_app_names.append(ebpf_application.app_name)

        table_ids: list[str] = [
            table_id
            for data_source in self.data_sources
            for table_id in data_source.get_level_table_ids(self.LEVEL_NAME)
        ]
        if not table_ids:
            raise ValueError("TraceQuery 缺少 trace 层级结果表")
        queries: list[QueryConfigBuilder] = [
            QueryConfigBuilder(self.USING)
            .table(table_id)
            .time_field(self.DEFAULT_TIME_FIELD)
            .order_by("time desc")
            .filter(**{f"{OtlpKey.TRACE_ID}__eq": trace_id})
            .filter(Q(app_name__neq=exclude_app_names) | Q(biz_id__neq=self.bk_biz_id))
            for table_id in table_ids
        ]

        # 以此TraceId 开始-结束时间为范围 在此时间范围内才为跨应用
        # <start_time -- <min_start_time --- ... --- max_end_time> -- end_time>
        if start_time:
            queries = [q.filter(min_start_time__gte=start_time) for q in queries]
        if end_time:
            queries = [q.filter(max_end_time__lte=end_time) for q in queries]

        # using_scope=False：跨应用检索，需要全局查询。
        return self._add_query(self.get_qs(using_scope=False), queries).first()

    def query_latest(self, trace_id: str) -> dict[str, Any] | None:
        queries: list[QueryConfigBuilder] = [
            q.filter(**{f"{OtlpKey.TRACE_ID}__eq": trace_id}).order_by("time desc") for q in self.build_queries()
        ]
        return self._add_query(self.get_qs(), queries).first()

    @classmethod
    def _translate_field(cls, field: str) -> str:
        for prefix, translated_prefix in cls.KEY_PREFIX_TRANSLATE_FIELDS.items():
            # OtlpKey.KIND 和 OtlpKey.SPAN_NAME 没有下级，字段名必须相等才加上 translated_prefix
            if prefix in {OtlpKey.KIND, OtlpKey.SPAN_NAME}:
                if field == prefix:
                    return f"{translated_prefix}.{field}"
                continue

            if field.startswith(prefix):
                return f"{translated_prefix}.{field}"

        return super()._translate_field(field)

    @classmethod
    def _add_logic_filter(cls, q: Q, field: str, value: types.FilterValue) -> Q:
        if field == "error":
            return q & Q(error_count__neq=0)
        return q

    @classmethod
    def query_by_trace_ids(
        cls,
        result_table_ids: list[str],
        trace_ids: list[str],
        retention: int,
        start_time: int | None,
        end_time: int | None,
    ) -> list[dict[str, Any]]:
        base_q: QueryConfigBuilder = (
            QueryConfigBuilder(cls.USING)
            .alias("a")
            .filter(trace_id__eq=trace_ids)
            .values("trace_id", "app_name", "error", "trace_duration", "root_service_category", "root_span_id")
            .time_field(cls.DEFAULT_TIME_FIELD)
            .order_by(f"{cls.DEFAULT_TIME_FIELD} desc")
        )

        start_time, end_time = cls.get_retention_time_range(retention, start_time, end_time)
        queries: list[QueryConfigBuilder] = [base_q.table(result_table_id) for result_table_id in result_table_ids]
        queryset = cls._add_query(
            UnifyQuerySet().start_time(start_time).end_time(end_time).time_align(False).is_es_batch(), queries
        )

        # 查询多表数据，合并返回，不同查询模式下均能支持：
        # ES - 并发查询后合并。
        # UnifyQuery - 多 Table 且 alias 相同的情况下，会自动聚合多表查询结果。
        return list(queryset.expression("a").limit(len(trace_ids)))

    def query_simple_info(
        self, start_time: int | None, end_time: int | None, offset: int, limit: int
    ) -> list[dict[str, Any]]:
        """查询App下的简单Trace信息"""
        select_fields: list[str] = ["trace_id", "app_name", "error", "trace_duration", "root_service_category"]
        queries: list[QueryConfigBuilder] = [
            q.order_by(f"{self.DEFAULT_TIME_FIELD} desc").values(*select_fields) for q in self.build_queries()
        ]
        return self._query_list(queries, start_time, end_time, offset, limit)
