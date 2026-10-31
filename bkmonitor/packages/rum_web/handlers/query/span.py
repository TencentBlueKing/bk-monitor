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

from bkmonitor.data_source.format import flatten_dict_data
from rum_web.handlers.query.base import BaseRumQuery
from rum_web.handlers.query.session import SessionQuery
from rum_web.handlers.query.view import ViewQuery
from semconv.rum.constants import RumSpanType


class SpanQuery(BaseRumQuery):
    """原始 Span 查询。"""

    def query_detail(self, record_id: str) -> dict[str, Any]:
        span = super().query_detail(record_id)
        flat: dict[str, Any] = flatten_dict_data(span)
        query_class = {
            RumSpanType.VIEW.value: ViewQuery,
            RumSpanType.SESSION.value: SessionQuery,
        }.get(flat.get("attributes.span_type") or "")
        if query_class is not None:
            business_id = flat.get(query_class.RECORD_ID_FIELD)
            if isinstance(business_id, str) and business_id:
                return query_class(self.data_sources).query_detail(business_id)
        return span
