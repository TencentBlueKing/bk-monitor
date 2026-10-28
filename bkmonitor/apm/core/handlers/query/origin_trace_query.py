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

from typing import Any

from django.db.models import Q
from opentelemetry.semconv.trace import SpanAttributes
from opentelemetry.trace import StatusCode

from apm import constants, types
from apm.core.discover.precalculation.processor import PrecalculateProcessor
from apm.core.handlers.query.base import BaseQuery
from apm.core.handlers.query.builder import QueryConfigBuilder, UnifyQuerySet
from bkmonitor.utils.thread_backend import ThreadPool
from constants.apm import OtlpKey


class OriginTraceQuery(BaseQuery):
    DEFAULT_TIME_FIELD = "end_time"

    KEY_REPLACE_FIELDS = {"duration": "elapsed_time"}

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
        queries: list[QueryConfigBuilder] = [
            q.distinct(OtlpKey.TRACE_ID).values(OtlpKey.TRACE_ID) for q in self.build_queries(filters, query_string)
        ]

        trace_ids: list[str] = []
        trace_records: list[dict[str, Any]] = self._query_list(queries, start_time, end_time, offset, limit)
        for trace_record in trace_records:
            trace_id: str | list[str] = trace_record[OtlpKey.TRACE_ID]
            if isinstance(trace_id, list):
                trace_id = trace_id[0]
            trace_ids.append(trace_id)

        pool = ThreadPool()
        processor = PrecalculateProcessor(None, self.bk_biz_id, self.app_name)
        params_list = [(processor, trace_id) for trace_id in trace_ids]
        results = pool.map_ignore_exception(self._query_trace_info, params_list)
        res: list[dict[str, Any]] = []
        for result in results:
            if not result:
                continue
            res.append(result)

        return res

    def _query_trace_info(self, processor, trace_id: str) -> dict[str, Any]:
        queries: list[QueryConfigBuilder] = [
            q.order_by(OtlpKey.START_TIME).filter(**{f"{OtlpKey.TRACE_ID}__eq": trace_id})
            for q in self.build_queries(time_field=OtlpKey.START_TIME)
        ]
        queryset: UnifyQuerySet = self.get_qs().limit(constants.DISCOVER_BATCH_SIZE)
        span_infos: list[dict[str, Any]] = list(self._add_query(queryset, queries))

        trace_info = processor.get_trace_info(trace_id, span_infos)
        trace_info.pop("collections", None)
        trace_info.pop("biz_name", None)
        trace_info.pop("root_span_id", None)
        return trace_info

    @classmethod
    def _add_logic_filter(cls, q: Q, field: str, value: types.FilterValue) -> Q:
        if field == "status_code":
            # 表头状态码特殊查询
            return q & (
                Q(**{OtlpKey.get_attributes_key(SpanAttributes.HTTP_STATUS_CODE): value})
                | Q(**{OtlpKey.get_attributes_key(SpanAttributes.RPC_GRPC_STATUS_CODE): value})
            )

        if field == "error":
            # 查询错误
            return q & Q(**{OtlpKey.STATUS_CODE: StatusCode.ERROR.value})
        return q
