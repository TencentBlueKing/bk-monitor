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
from typing import Any, Dict, List, Optional, Set, Union

from django.db.models import Q

from apm import types
from apm.core.discover.precalculation.storage import PrecalculateStorage
from apm.core.handlers.ebpf.base import EbpfHandler
from apm.core.handlers.query.base import (
    QueryConfigBuilder,
    UnifyQueryBuilder,
    UnifyQuerySet,
)
from apm.models import ApmApplication
from bkmonitor.utils.thread_backend import InheritParentThread, run_threads
from constants.apm import OtlpKey

logger = logging.getLogger("apm")


class TraceQuery(UnifyQueryBuilder):

    DEFAULT_TIME_FIELD = "min_start_time"

    KEY_PREFIX_TRANSLATE_FIELDS = {
        f"{OtlpKey.ATTRIBUTES}.": "collections",
        f"{OtlpKey.RESOURCE}.": "collections",
        OtlpKey.KIND: "collections",
        OtlpKey.SPAN_NAME: "collections",
    }

    KEY_REPLACE_FIELDS = {"duration": "trace_duration"}

    def __init__(self, bk_biz_id: int, app_name: str, result_table_id: str, retention: int):
        self.app_name: str = app_name
        super().__init__(bk_biz_id, result_table_id, retention)

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
    ):
        logger.info("[TraceQuery] list: es_dsl -> %s", es_dsl)

        page_data: Dict[str, Union[int, List[Dict[str, Any]]]] = {}
        all_fields: Set[str] = {field_info["field_name"] for field_info in PrecalculateStorage.TABLE_SCHEMA}
        select_fields: List[str] = list(
            all_fields - set(exclude_fields or ["collections", "bk_app_code", "biz_name", "root_span_id"])
        )
        q: QueryConfigBuilder = (
            self.q.filter(self.build_filters(filters) & self.build_app_filter())
            .order_by(*(self.parse_ordering_from_dsl(es_dsl) or [f"{self.DEFAULT_TIME_FIELD} desc"]))
            .query_string(*self.parse_query_string_from_dsl(es_dsl))
        )
        queryset: UnifyQuerySet = self.time_range_queryset(start_time, end_time)

        def _fill_total():
            _q: QueryConfigBuilder = q.metric(field=OtlpKey.TRACE_ID, method="count", alias="total")
            page_data["total"] = queryset.add_query(_q)[0]["total"]

        def _fill_data():
            _q: QueryConfigBuilder = q.values(*select_fields)
            page_data["data"] = list(queryset.add_query(_q).offset(offset).limit(limit))

        run_threads([InheritParentThread(target=_fill_total), InheritParentThread(target=_fill_data)])

        return page_data["data"], page_data["total"]

    def query_relation_by_trace_id(self, trace_id: str, start_time: Optional[int], end_time: Optional[int]):
        """查询此traceId是否有跨应用关联（需要排除此业务下的EBPF应用）"""

        exclude_biz_id: int = self.bk_biz_id
        exclude_app_names: List[str] = [self.app_name]
        ebpf_application: Optional[ApmApplication] = self._get_ebpf_application()
        if ebpf_application:
            exclude_app_names.append(ebpf_application.app_name)

        q: QueryConfigBuilder = (
            self.q.order_by("time desc")
            .filter(**{f"{OtlpKey.TRACE_ID}__eq": trace_id})
            .filter(app_name__neq=exclude_app_names, bk_biz_id__neq=exclude_biz_id)
        )

        # 以此TraceId 开始-结束时间为范围 在此时间范围内才为跨应用
        # <start_time -- <min_start_time --- ... --- max_end_time> -- end_time>
        if start_time:
            q = q.filter(min_start_time__gte=start_time)
        if end_time:
            q = q.filter(max_end_time__lte=end_time)

        return self.time_range_queryset().add_query(q).first()

    def query_latest(self, trace_id):
        q: QueryConfigBuilder = (
            self.q.filter(self.build_app_filter()).filter(**{f"{OtlpKey.TRACE_ID}__eq": trace_id}).order_by("time desc")
        )
        return self.time_range_queryset().add_query(q).first()

    def query_option_values(self, start_time: Optional[int], end_time: Optional[int], fields: List[str]):
        q: QueryConfigBuilder = self.q.filter(self.build_app_filter()).order_by(f"{self.DEFAULT_TIME_FIELD} desc")
        return self._query_option_values(q, fields, start_time, end_time)

    @classmethod
    def _translate_field(cls, field: str) -> str:
        for i, prefix in cls.KEY_PREFIX_TRANSLATE_FIELDS.items():
            if field.startswith(i):
                return f"{prefix}.{field}"
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
    ):
        base_q: QueryConfigBuilder = (
            QueryConfigBuilder(cls.USING)
            .filter(trace_id__eq=trace_ids)
            .values("trace_id", "app_name", "error", "trace_duration", "root_service_category", "root_span_id")
            .time_field(cls.DEFAULT_TIME_FIELD)
            .order_by(f"{cls.DEFAULT_TIME_FIELD} desc")
        )

        aliases: List[str] = []
        start_time, end_time = cls.get_time_range(retention, start_time, end_time)
        queryset: UnifyQuerySet = UnifyQuerySet().start_time(start_time).end_time(end_time)
        for idx, result_table_id in enumerate(result_table_ids):
            alias: str = chr(ord("a") + idx)
            q: QueryConfigBuilder = base_q.table(result_table_id).alias(alias)
            queryset: UnifyQuerySet = queryset.add_query(q)
            aliases.append(alias)

        # TODO 这里大概率后面对接 UnifyQuery 还需要微调和扩展
        return list(queryset.expression(" or ".join(aliases)).limit(len(trace_ids)))

    def query_simple_info(self, start_time: Optional[int], end_time: Optional[int], offset: int, limit: int):
        """查询App下的简单Trace信息"""
        q: QueryConfigBuilder = (
            self.q.filter(self.build_app_filter())
            .values("trace_id", "app_name", "error", "trace_duration", "root_service_category")
            .order_by(f"{self.DEFAULT_TIME_FIELD} desc")
        )
        return list(self.time_range_queryset(start_time, end_time).add_query(q).offset(offset).limit(limit)), 0
