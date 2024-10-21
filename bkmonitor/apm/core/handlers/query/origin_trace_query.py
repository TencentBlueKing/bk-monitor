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
from typing import Any, Dict, List, Optional, Union

from django.db.models import Q
from opentelemetry.semconv.trace import SpanAttributes
from opentelemetry.trace import StatusCode

from apm import constants, types
from apm.core.discover.precalculation.processor import PrecalculateProcessor
from apm.core.handlers.query.base import BaseQuery, QueryConfigBuilder, UnifyQuerySet
from bkmonitor.utils.thread_backend import ThreadPool
from constants.apm import OtlpKey


class OriginTraceQuery(BaseQuery):
    DEFAULT_TIME_FIELD = "end_time"

    KEY_REPLACE_FIELDS = {"duration": "elapsed_time"}

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
        page_data: Dict[str, Union[int, List[str]]] = {"total": 0}
        queryset: UnifyQuerySet = self.time_range_queryset(start_time, end_time)
        q: QueryConfigBuilder = self.q.filter(self._build_filters(filters))
        q = self._add_filters_from_dsl(q, es_dsl)

        def _fill_data():
            _trace_ids: List[str] = []
            _q: QueryConfigBuilder = q.distinct(OtlpKey.TRACE_ID)
            for _info in queryset.add_query(_q).offset(offset).limit(limit):
                _trace_id: Union[str, List[str]] = _info[OtlpKey.TRACE_ID]
                if isinstance(_trace_id, list):
                    _trace_id = _trace_id[0]
                _trace_ids.append(_trace_id)
            page_data["data"] = _trace_ids

        _fill_data()

        pool = ThreadPool()
        processor = PrecalculateProcessor(None, self.bk_biz_id, self.app_name)
        params_list = [(processor, trace_id) for trace_id in page_data["data"]]
        results = pool.map_ignore_exception(self._query_trace_info, params_list)
        res = []
        for result in results:
            if not result:
                continue
            res.append(result)

        return res, page_data["total"]

    def _query_trace_info(self, processor, trace_id: str) -> Dict[str, Any]:
        q: QueryConfigBuilder = (
            self.q.time_field(OtlpKey.START_TIME)
            .order_by(OtlpKey.START_TIME)
            .filter(**{f"{OtlpKey.TRACE_ID}__eq": trace_id})
        )
        span_infos: List[Dict[str, Any]] = list(
            self.time_range_queryset().add_query(q).limit(constants.DISCOVER_BATCH_SIZE)
        )

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
