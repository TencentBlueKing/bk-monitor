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
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from django.utils.functional import cached_property

from apm import types
from apm.core.discover.precalculation.storage import PrecalculateStorage
from apm.core.handlers.query.base import FakeQuery
from apm.core.handlers.query.define import QueryMode, TraceInfoList
from apm.core.handlers.query.ebpf_query import DeepFlowQuery
from apm.core.handlers.query.origin_trace_query import OriginTraceQuery
from apm.core.handlers.query.span_query import SpanQuery
from apm.core.handlers.query.statistics_query import StatisticsQuery
from apm.core.handlers.query.trace_query import TraceQuery
from apm.models import ApmApplication, ApmDataSourceConfigBase
from bkmonitor.iam import ActionEnum, Permission, ResourceEnum
from constants.apm import OtlpKey, TraceWaterFallDisplayKey

logger = logging.getLogger("apm")


class QueryProxy:
    def __init__(self, bk_biz_id, app_name):
        self.bk_biz_id = bk_biz_id
        self.app_name = app_name
        self.application = ApmApplication.get_application(self.bk_biz_id, self.app_name)
        self.query_mode = {
            QueryMode.TRACE: self.trace_query,
            QueryMode.ORIGIN_TRACE: self.origin_trace_query,
            QueryMode.SPAN: self.span_query,
        }

    def _get_trace_query(self, result_table_id: str) -> TraceQuery:
        return TraceQuery(
            self.bk_biz_id,
            self.app_name,
            self.application.trace_datasource.retention,
            overwrite_datasource_configs={
                ApmDataSourceConfigBase.TRACE_DATASOURCE: {"get_table_id_func": lambda *args, **kwargs: result_table_id}
            },
        )

    @cached_property
    def span_query(self):
        return SpanQuery(
            self.bk_biz_id,
            self.app_name,
            self.application.trace_datasource.retention,
            overwrite_datasource_configs={
                ApmDataSourceConfigBase.TRACE_DATASOURCE: {
                    "get_table_id_func": lambda *args, **kwargs: self.application.trace_datasource.result_table_id
                },
                ApmDataSourceConfigBase.METRIC_DATASOURCE: {
                    "get_table_id_func": lambda *args, **kwargs: self.application.metric_datasource.result_table_id
                },
            },
        )

    @cached_property
    def origin_trace_query(self):
        return OriginTraceQuery(
            self.bk_biz_id,
            self.app_name,
            self.application.trace_datasource.retention,
            overwrite_datasource_configs={
                ApmDataSourceConfigBase.TRACE_DATASOURCE: {
                    "get_table_id_func": lambda *args, **kwargs: self.application.trace_datasource.result_table_id
                },
                ApmDataSourceConfigBase.METRIC_DATASOURCE: {
                    "get_table_id_func": lambda *args, **kwargs: self.application.metric_datasource.result_table_id
                },
            },
        )

    @cached_property
    def trace_query(self):
        precalculate = PrecalculateStorage(self.bk_biz_id, self.app_name, need_client=False)
        if not precalculate.is_valid:
            logger.info(f"[QueryProxy] {self.bk_biz_id} - {self.app_name} use fake trace query")
            trace_query = FakeQuery()
        else:
            trace_query = self._get_trace_query(result_table_id=precalculate.result_table_id)

        return trace_query

    @cached_property
    def statistics_query(self):
        return StatisticsQuery(self.trace_query, self.span_query)

    @cached_property
    def is_trace_query_valid(self):
        return isinstance(self.trace_query, TraceQuery)

    def query_list(
        self,
        query_mode: str,
        start_time: int,
        end_time: int,
        limit: int,
        offset: int,
        filters: Optional[List[types.Filter]] = None,
        es_dsl: Optional[Dict[str, Any]] = None,
        exclude_fields: Optional[List[str]] = None,
    ):
        """查询列表"""
        data, size = self.query_mode[query_mode].list(
            start_time, end_time, offset, limit, filters, es_dsl, exclude_fields
        )
        return asdict(TraceInfoList(total=size, data=data))

    def query_trace_detail(self, trace_id, displays, bk_biz_id=None, query_trace_relation_app: bool = False):
        """Trace详情"""
        # query otel data
        spans = self.span_query.query_by_trace_id(trace_id)

        # query ebpf data
        if TraceWaterFallDisplayKey.SOURCE_CATEGORY_EBPF in displays:
            ebpf_spans = DeepFlowQuery.get_ebpf(trace_id, bk_biz_id)
            if ebpf_spans:
                spans += ebpf_spans

        relation_mapping = {}
        if not self.is_trace_query_valid:
            return spans, relation_mapping

        if not query_trace_relation_app:
            return spans, relation_mapping

        trace_relation = self._get_trace_relation(trace_id)
        if trace_relation:
            relation_app: ApmApplication = ApmApplication.objects.filter(
                bk_biz_id=trace_relation["bk_biz_id"], app_name=trace_relation["app_name"]
            ).first()
            if relation_app:
                span_query = SpanQuery(
                    relation_app.bk_biz_id,
                    relation_app.app_name,
                    relation_app.trace_datasource.retention,
                )
                relation_spans = span_query.query_by_trace_id(trace_id)
                client = Permission()
                permission = client.is_allowed(
                    ActionEnum.VIEW_APM_APPLICATION,
                    resources=[ResourceEnum.APM_APPLICATION.create_instance(relation_app.id)],
                )
                relation_mapping = {
                    i[OtlpKey.PARENT_SPAN_ID]: {
                        "bk_biz_id": trace_relation["bk_biz_id"],
                        "app_name": trace_relation["app_name"],
                        "bk_biz_name": trace_relation["biz_name"],
                        "app_id": trace_relation["bk_app_code"],
                        "trace_id": trace_id,
                        "permission": permission,
                    }
                    for i in relation_spans
                }

        return spans, relation_mapping

    def query_span_detail(self, span_id):
        return self.span_query.query_by_span_id(span_id)

    def query_option_values(self, query_mode, datasource_type: str, start_time, end_time, fields):
        """获取候选值"""
        return self.query_mode[query_mode].query_option_values(datasource_type, start_time, end_time, fields)

    def query_statistics(self, query_mode, start_time, end_time, limit, offset, filters=None, es_dsl=None):
        return self.statistics_query.query_statistics(query_mode, start_time, end_time, limit, offset, filters, es_dsl)

    def _get_trace_relation(self, trace_id: str):
        """获取 trace_id 的跨应用关联"""
        # 获取基准 trace_id 的时间范围
        latest_trace_info = self.trace_query.query_latest(trace_id)
        if latest_trace_info:
            start_time = latest_trace_info["min_start_time"]
            end_time = latest_trace_info["max_end_time"]
        else:
            start_time, end_time = None, None
            logger.warning(f"[QueryProxy] {self.bk_biz_id}:{self.app_name} trace: {trace_id} not in pre_recalculation!")

        for result_table_id in PrecalculateStorage.fetch_result_table_ids(self.bk_biz_id):
            trace_query = self._get_trace_query(result_table_id)
            relation = trace_query.query_relation_by_trace_id(trace_id, start_time, end_time)
            if relation:
                logger.info(f"[QueryProxy] find relation on {trace_id}({relation['bk_biz_id']}:{relation['app_name']})")
                return relation

        return None

    @classmethod
    def query_trace_by_ids(
        cls, bk_biz_id: int, trace_ids: List[str], start_time: Optional[int], end_time: Optional[int]
    ) -> Dict[str, Dict[str, Any]]:
        """不指定 APP_NAME 下根据 TraceId 查询 Trace"""
        trace_id__info_map: Dict[str, Dict[str, Any]] = {}
        result_table_ids: List[str] = PrecalculateStorage.fetch_result_table_ids(bk_biz_id)
        # 这里取哪一个业务的数据过期时间都不合适，但时间范围后续切换查询方式可能起到加速查询、跨集群检索的能力，先给个极值 30
        trace_infos: List[Dict[str, Any]] = TraceQuery.query_by_trace_ids(
            result_table_ids, trace_ids, 30, start_time, end_time
        )
        for trace_info in trace_infos:
            trace_id__info_map[trace_info["trace_id"]] = trace_info
        return trace_id__info_map

    def query_simple_info(self, start_time, end_time, offset, limit):
        trace_id__info_map: Dict[str, Dict[str, Any]] = {}
        trace_infos, total = self.trace_query.query_simple_info(start_time, end_time, offset, limit)
        for trace_info in trace_infos:
            trace_id__info_map[trace_info["trace_id"]] = trace_info
        return trace_id__info_map, total
