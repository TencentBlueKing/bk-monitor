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
from elasticsearch_dsl import A, Q
from opentelemetry.semconv.trace import SpanAttributes
from opentelemetry.trace import StatusCode

from apm import constants
from apm.core.discover.precalculation.processor import PrecalculateProcessor
from apm.core.handlers.query.base import EsQueryBuilderMixin
from apm.utils.es_search import EsSearch
from bkmonitor.utils.thread_backend import ThreadPool
from constants.apm import OtlpKey


class OriginTraceQuery(EsQueryBuilderMixin):
    DEFAULT_SORT_FIELD = "end_time"

    KEY_REPLACE_FIELDS = {"duration": "elapsed_time"}

    def __init__(self, bk_biz_id, app_name, es_client, index_name):
        self.client = es_client
        self.index_name = index_name
        self.bk_biz_id = bk_biz_id
        self.app_name = app_name

    @property
    def search(self):
        return EsSearch(using=self.client, index=self.index_name)

    def list(self, start_time, end_time, offset, limit, filter_params=None, es_dsl=None, exclude_field=None):
        query = self.search
        if es_dsl:
            query = query.update_from_dict(es_dsl)

        query = self.add_time(query, start_time, end_time)
        query = self.add_sort(query, "-start_time")

        if filter_params:
            query = self.add_filter_params(query, filter_params)

        query = query[offset : offset + limit]
        query = (
            query.extra(collapse={"field": OtlpKey.TRACE_ID}).extra(track_total_hits=True).source([OtlpKey.TRACE_ID])
        )
        query.aggs.bucket("total_size", A("cardinality", field=OtlpKey.TRACE_ID))
        response = query.execute()

        total_size = response.aggregations.total_size.value

        processor = PrecalculateProcessor(None, self.bk_biz_id, self.app_name)

        pool = ThreadPool()
        trace_id_list = [(processor, getattr(trace, OtlpKey.TRACE_ID)[0]) for trace in response.hits]
        results = pool.map_ignore_exception(self._query_trace_info, trace_id_list)
        res = []
        for result in results:
            if not result:
                continue
            res.append(result)

        return res, total_size

    def _query_trace_info(self, processor, trace_id: str):
        query = self.search
        query = query.query("bool", filter=[Q("term", **{OtlpKey.TRACE_ID: trace_id})]).extra(
            size=constants.DISCOVER_BATCH_SIZE
        )
        spans = []

        for span in query.execute():
            spans.append(span.to_dict())

        trace_info = processor.get_trace_info(trace_id, spans)
        trace_info.pop("collections", None)
        trace_info.pop("biz_name", None)
        trace_info.pop("root_span_id", None)

        return trace_info

    @classmethod
    def _translate_key(cls, key):
        if key in cls.KEY_REPLACE_FIELDS:
            return cls.KEY_REPLACE_FIELDS[key]

        return key

    @classmethod
    def _add_logic_filter(cls, query, key, value):
        if key == "status_code":
            # 表头状态码特殊查询
            query = query.query(
                "bool",
                should=[
                    Q("terms", **{OtlpKey.get_attributes_key(SpanAttributes.HTTP_STATUS_CODE): value}),
                    Q("terms", **{OtlpKey.get_attributes_key(SpanAttributes.RPC_GRPC_STATUS_CODE): value}),
                ],
            )

        if key == "error":
            # 查询错误
            query = query.query("bool", should=[Q("term", **{OtlpKey.STATUS_CODE: StatusCode.ERROR.value})])
        return query
