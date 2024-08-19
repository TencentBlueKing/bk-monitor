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
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from apm import constants, types
from apm.core.handlers.query.base import (
    QueryConfigBuilder,
    UnifyQueryBuilder,
    UnifyQuerySet,
)
from apm.models import TraceDataSource
from bkmonitor.utils.thread_backend import InheritParentThread, run_threads
from constants.apm import OtlpKey

logger = logging.getLogger("apm")


class SpanQuery(UnifyQueryBuilder):

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
    ) -> Tuple[List[Dict[str, Any]], int]:

        logger.info("[SpanQuery] list: es_dsl -> %s", es_dsl)

        page_data: Dict[str, Union[int, List[Dict[str, Any]]]] = {}
        all_fields: Set[str] = {field_info["field_name"] for field_info in TraceDataSource.TRACE_FIELD_LIST}
        select_fields: List[str] = list(all_fields - set(exclude_fields or ["attributes", "links", "events"]))
        q: QueryConfigBuilder = (
            self.q.filter(self.build_filters(filters))
            .query_string(*self.parse_query_string_from_dsl(es_dsl))
            .order_by(*(self.parse_ordering_from_dsl(es_dsl) or [f"{self.DEFAULT_TIME_FIELD} desc"]))
        )
        queryset: UnifyQuerySet = self.time_range_queryset(start_time, end_time)

        def _fill_total():
            _q: QueryConfigBuilder = q.metric(field=OtlpKey.SPAN_ID, method="count", alias="total")
            page_data["total"] = queryset.add_query(_q)[0]["total"]

        def _fill_data():
            _q: QueryConfigBuilder = q.values(*select_fields)
            page_data["data"] = list(queryset.add_query(_q).offset(offset).limit(limit))

        run_threads([InheritParentThread(target=_fill_total), InheritParentThread(target=_fill_data)])

        return page_data["data"], page_data["total"]

    def query_option_values(
        self, start_time: Optional[int], end_time: Optional[int], fields: List[str]
    ) -> Dict[str, List[str]]:
        q: QueryConfigBuilder = self.q.order_by(f"{self.DEFAULT_TIME_FIELD} desc")
        return self._query_option_values(q, fields, start_time, end_time)

    def query_by_trace_id(self, trace_id: str) -> List[Dict[str, Any]]:
        q: QueryConfigBuilder = (
            self.q.time_field(OtlpKey.START_TIME)
            .order_by(OtlpKey.START_TIME)
            .filter(**{f"{OtlpKey.TRACE_ID}__eq": trace_id})
        )
        return list(self.time_range_queryset().add_query(q).limit(constants.DISCOVER_BATCH_SIZE))

    def query_by_span_id(self, span_id) -> Optional[Dict[str, Any]]:
        q: QueryConfigBuilder = (
            self.q.time_field(OtlpKey.START_TIME)
            .order_by(f"{OtlpKey.START_TIME} desc")
            .filter(**{f"{OtlpKey.SPAN_ID}__eq": span_id})
        )
        return self.time_range_queryset().add_query(q).first()
