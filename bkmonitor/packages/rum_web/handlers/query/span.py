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
from bkmonitor.data_source.utils import types
from bkmonitor.data_source.utils.apm import FilterOperator
from rum_web.handlers.builder.utils import get_safe_number
from rum_web.handlers.query.base import BaseRumQuery
from rum_web.handlers.query.session import SessionQuery
from rum_web.handlers.query.view import ViewQuery
from semconv.rum.constants import RumSpanType, SessionPhase


class SpanQuery(BaseRumQuery):
    """原始 Span 查询。"""

    def query_session_time_range(self, session_id: str) -> dict[str, int | float | None]:
        """独立查询会话时间边界，不受时间线节点条数上限影响。"""
        filters: list[types.Filter] = [
            {"key": "attributes.session.id", "value": [session_id], "operator": FilterOperator.EQUAL}
        ]
        lifecycle_filters: list[types.Filter] = [
            *filters,
            {"key": "attributes.span_type", "value": [RumSpanType.SESSION.value], "operator": FilterOperator.EQUAL},
        ]
        boundaries: tuple[tuple[str, str, list[types.Filter], str], ...] = (
            (
                "start_time",
                "start_time",
                [
                    *lifecycle_filters,
                    {
                        "key": "attributes.session.phase",
                        "value": [SessionPhase.START.value, SessionPhase.ROTATE.value],
                        "operator": FilterOperator.EQUAL,
                    },
                ],
                "start_time",
            ),
            (
                "end_time",
                "end_time",
                [
                    *lifecycle_filters,
                    {
                        "key": "attributes.session.phase",
                        "value": [SessionPhase.END.value],
                        "operator": FilterOperator.EQUAL,
                    },
                ],
                "-end_time",
            ),
            ("observed_start", "start_time", filters, "start_time"),
            ("observed_end", "end_time", filters, "-end_time"),
        )
        result: dict[str, int | float | None] = {}
        for name, field, conditions, order in boundaries:
            records: list[dict[str, Any]] = self.query_list(
                start_time=None,
                end_time=None,
                offset=0,
                limit=1,
                filters=[*conditions, {"key": field, "value": [""], "operator": FilterOperator.EXISTS}],
                sort=[order, "span_id"],
            )
            result[name] = get_safe_number(records[0].get(field), None) if records else None
        return result

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
