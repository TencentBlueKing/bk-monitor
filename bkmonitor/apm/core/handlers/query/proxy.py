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

from django.utils.functional import cached_property

from apm.core.discover.precalculation.storage import PrecalculateStorage
from apm.core.handlers.ebpf.base import EbpfHandler
from apm.core.handlers.query.base import FakeQuery
from apm.core.handlers.query.define import QueryMode, TraceInfoList
from apm.core.handlers.query.ebpf_query import DeepFlowQuery, EbpfQuery
from apm.core.handlers.query.origin_trace_query import OriginTraceQuery
from apm.core.handlers.query.span_query import SpanQuery
from apm.core.handlers.query.statistics_query import StatisticsQuery
from apm.core.handlers.query.trace_query import TraceQuery
from apm.models import ApmApplication, EbpfApplicationConfig
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

    @cached_property
    def span_query(self):
        return SpanQuery(self.application.trace_datasource.es_client, self.application.trace_datasource.result_table_id)

    @cached_property
    def origin_trace_query(self):
        return OriginTraceQuery(
            self.bk_biz_id,
            self.app_name,
            self.application.trace_datasource.es_client,
            self.application.trace_datasource.result_table_id,
        )

    @cached_property
    def trace_query(self):
        precalculate = PrecalculateStorage(self.bk_biz_id, self.app_name)
        if not precalculate.is_valid:
            logger.info(f"[QueryProxy] {self.bk_biz_id} - {self.app_name} use fake trace query")
            trace_query = FakeQuery()
        else:
            trace_query = TraceQuery(self.bk_biz_id, self.app_name, precalculate.client, precalculate.search_index_name)

        return trace_query

    @cached_property
    def statistics_query(self):
        return StatisticsQuery(self.trace_query, self.span_query)

    @cached_property
    def ebpf_query(self):
        config = EbpfApplicationConfig.objects.filter(bk_biz_id=self.bk_biz_id).first()
        if not config:
            return FakeQuery()

        app = ApmApplication.objects.filter(id=config.application_id).first()
        if not app:
            return FakeQuery()

        if EbpfHandler.is_ebpf_application(self.application):
            return FakeQuery()

        return EbpfQuery(app.trace_datasource.es_client, app.trace_datasource.result_table_id)

    @cached_property
    def is_trace_query_valid(self):
        return isinstance(self.trace_query, TraceQuery)

    def query_list(
        self, query_mode, start_time, end_time, limit, offset, filters=None, es_dsl=None, exclude_field=None
    ):
        """查询列表"""
        data, size = self.query_mode[query_mode].list(
            start_time, end_time, offset, limit, filters, es_dsl, exclude_field
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
            relation_app = ApmApplication.objects.filter(
                bk_biz_id=trace_relation["biz_id"], app_name=trace_relation["app_name"]
            ).first()
            if relation_app:
                span_query = SpanQuery(
                    relation_app.trace_datasource.es_client, relation_app.trace_datasource.result_table_id
                )
                relation_spans = span_query.query_by_trace_id(trace_id)
                client = Permission()
                permission = client.is_allowed(
                    ActionEnum.VIEW_APM_APPLICATION,
                    resources=[ResourceEnum.APM_APPLICATION.create_instance(relation_app.id)],
                )
                relation_mapping = {
                    i[OtlpKey.PARENT_SPAN_ID]: {
                        "bk_biz_id": trace_relation["biz_id"],
                        "app_name": trace_relation["app_name"],
                        "bk_biz_name": trace_relation["biz_name"],
                        "app_id": trace_relation["app_id"],
                        "trace_id": trace_id,
                        "permission": permission,
                    }
                    for i in relation_spans
                }

        return spans, relation_mapping

    def query_span_detail(self, span_id):
        return self.span_query.query_by_span_id(span_id)

    def query_option_values(self, query_mode, start_time, end_time, fields):
        """获取候选值"""
        return self.query_mode[query_mode].query_option_values(start_time, end_time, fields)

    def query_statistics(self, query_mode, start_time, end_time, limit, offset, filters=None, es_dsl=None):
        return self.statistics_query.query_statistics(query_mode, start_time, end_time, limit, offset, filters, es_dsl)

    def _get_trace_relation(self, trace_id):
        """获取trace_id的跨应用关联"""
        # 获取基准trace_id的时间范围
        latest_trace_info = self.trace_query.query_latest(trace_id)
        if latest_trace_info:
            start_time = latest_trace_info["min_start_time"]
            end_time = latest_trace_info["max_end_time"]
        else:
            start_time, end_time = None, None
            logger.warning(f"[QueryProxy] {self.bk_biz_id}:{self.app_name} trace: {trace_id} not in pre_recalculation!")

        # 遍历寻找关联
        client_mapping = PrecalculateStorage.get_search_mapping(self.bk_biz_id)

        for index_name, client in client_mapping.items():
            trace_query = TraceQuery(self.bk_biz_id, self.app_name, client, index_name)
            relation = trace_query.query_relation_by_trace_id(trace_id, start_time, end_time)
            if relation:
                logger.info(f"[QueryProxy] find relation on {trace_id}({relation['biz_id']}:{relation['app_name']})")
                return relation

        return None

    @classmethod
    def query_trace_by_ids(cls, bk_biz_id, trace_ids, start_time, end_time):
        """不指定APP_NAME下 根据TraceId查询Trace"""

        # 遍历寻找
        client_mapping = PrecalculateStorage.get_search_mapping(bk_biz_id)

        res = {}
        for index_name, client in client_mapping.items():
            trace_infos = TraceQuery.query_by_trace_ids(client, index_name, trace_ids, start_time, end_time)

            for item in trace_infos:
                res[item["trace_id"]] = item

        return res

    def query_simple_info(self, start_time, end_time, offset, limit):
        trace_infos, total = self.trace_query.query_simple_info(start_time, end_time, offset, limit)

        res = {}
        for item in trace_infos:
            res[item["trace_id"][0]] = item

        return res, total
