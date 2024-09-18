# -*- coding: utf-8 -*-
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
from typing import Any, Dict, List, Optional, Set, Tuple

from django.db.models import Q

from apm import types
from apm.core.discover.precalculation.storage import PrecalculateStorage
from apm.core.handlers.ebpf.base import EbpfHandler
from apm.core.handlers.query.base import BaseQuery
from apm.core.handlers.query.builder import QueryConfigBuilder, UnifyQuerySet
from apm.models import ApmApplication
from constants.apm import OtlpKey

logger = logging.getLogger("apm")


class TraceQuery(BaseQuery):

    DEFAULT_TIME_FIELD = "min_start_time"

    KEY_PREFIX_TRANSLATE_FIELDS = {
        f"{OtlpKey.ATTRIBUTES}.": "collections",
        f"{OtlpKey.RESOURCE}.": "collections",
        OtlpKey.KIND: "collections",
        OtlpKey.SPAN_NAME: "collections",
    }

    KEY_REPLACE_FIELDS = {"duration": "trace_duration"}

    @classmethod
    def _get_select_fields(cls, exclude_fields: Optional[List[str]]) -> List[str]:
        all_fields: Set[str] = {field_info["field_name"] for field_info in PrecalculateStorage.TABLE_SCHEMA}
        select_fields: List[str] = list(
            all_fields - set(exclude_fields or ["collections", "bk_app_code", "biz_name", "root_span_id"])
        )
        return select_fields

    def build_app_filter(self) -> Q:
        return Q(biz_id__eq=self.bk_biz_id, app_name__eq=self.app_name)

    def _get_ebpf_application(self) -> Optional[ApmApplication]:
        return EbpfHandler.get_ebpf_application(self.bk_biz_id)

    def list(
        self,
        start_time: Optional[int],
        end_time: Optional[int],
        offset: int,
        limit: int,
        filters: Optional[List[types.Filter]] = None,
        es_dsl: Optional[Dict[str, Any]] = None,
        exclude_fields: Optional[List[str]] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        select_fields: List[str] = self._get_select_fields(exclude_fields)
        queryset: UnifyQuerySet = self.time_range_queryset(start_time, end_time)
        q: QueryConfigBuilder = self.q.filter(self._build_filters(filters) & self.build_app_filter()).order_by(
            *(self._parse_ordering_from_dsl(es_dsl) or [f"{self.DEFAULT_TIME_FIELD} desc"])
        )
        q = self._add_filters_from_dsl(q, es_dsl)
        page_data: types.Page = self._get_data_page(q, queryset, select_fields, OtlpKey.TRACE_ID, offset, limit)
        return page_data["data"], page_data["total"]

    def query_relation_by_trace_id(
        self, trace_id: str, start_time: Optional[int], end_time: Optional[int]
    ) -> Optional[Dict[str, Any]]:
        """查询此traceId是否有跨应用关联（需要排除此业务下的EBPF应用）"""
        exclude_app_names: List[str] = [self.app_name]
        ebpf_application: Optional[ApmApplication] = self._get_ebpf_application()
        if ebpf_application:
            exclude_app_names.append(ebpf_application.app_name)

        q: QueryConfigBuilder = (
            self.q.order_by("time desc")
            .filter(**{f"{OtlpKey.TRACE_ID}__eq": trace_id})
            .filter(Q(app_name__neq=exclude_app_names) | Q(biz_id__neq=self.bk_biz_id))
        )

        # 以此TraceId 开始-结束时间为范围 在此时间范围内才为跨应用
        # <start_time -- <min_start_time --- ... --- max_end_time> -- end_time>
        if start_time:
            q = q.filter(min_start_time__gte=start_time)
        if end_time:
            q = q.filter(max_end_time__lte=end_time)

        return self.time_range_queryset().add_query(q).first()

    def query_latest(self, trace_id: str) -> Optional[Dict[str, Any]]:
        q: QueryConfigBuilder = (
            self.q.filter(self.build_app_filter()).filter(**{f"{OtlpKey.TRACE_ID}__eq": trace_id}).order_by("time desc")
        )
        return self.time_range_queryset().add_query(q).first()

    def query_option_values(
        self, datasource_type: str, start_time: Optional[int], end_time: Optional[int], fields: List[str]
    ) -> Dict[str, List[str]]:
        q: QueryConfigBuilder = self.q.filter(self.build_app_filter()).order_by(f"{self.DEFAULT_TIME_FIELD} desc")
        return self._query_option_values(q, fields, start_time, end_time)

    @classmethod
    def _translate_field(cls, field: str) -> str:
        for prefix, translated_prefix in cls.KEY_PREFIX_TRANSLATE_FIELDS.items():
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
        result_table_ids: List[str],
        trace_ids: List[str],
        retention: int,
        start_time: Optional[int],
        end_time: Optional[int],
    ) -> List[Dict[str, Any]]:
        base_q: QueryConfigBuilder = (
            QueryConfigBuilder(cls.USING_LOG)
            .filter(trace_id__eq=trace_ids)
            .values("trace_id", "app_name", "error", "trace_duration", "root_service_category", "root_span_id")
            .time_field(cls.DEFAULT_TIME_FIELD)
            .order_by(f"{cls.DEFAULT_TIME_FIELD} desc")
        )

        aliases: List[str] = []
        start_time, end_time = cls._get_time_range(retention, start_time, end_time)
        queryset: UnifyQuerySet = UnifyQuerySet().start_time(start_time).end_time(end_time)
        for idx, result_table_id in enumerate(result_table_ids):
            alias: str = chr(ord("a") + idx)
            q: QueryConfigBuilder = base_q.table(result_table_id).alias(alias)
            queryset: UnifyQuerySet = queryset.add_query(q)
            aliases.append(alias)

        # TODO 这里大概率后面对接 UnifyQuery 还需要微调和扩展
        return list(queryset.expression(" or ".join(aliases)).limit(len(trace_ids)))

    def query_simple_info(
        self, start_time: Optional[int], end_time: Optional[int], offset: int, limit: int
    ) -> Tuple[List[Dict[str, Any]], int]:
        """查询App下的简单Trace信息"""
        select_fields: List[str] = ["trace_id", "app_name", "error", "trace_duration", "root_service_category"]
        queryset: UnifyQuerySet = self.time_range_queryset(start_time, end_time)
        q: QueryConfigBuilder = self.q.filter(self.build_app_filter()).order_by(f"{self.DEFAULT_TIME_FIELD} desc")
        page_data: types.Page = self._get_data_page(q, queryset, select_fields, OtlpKey.TRACE_ID, offset, limit)
        return page_data["data"], page_data["total"]
