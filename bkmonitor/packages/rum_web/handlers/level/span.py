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

from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError

from bkmonitor.data_source.utils import types
from bkmonitor.data_source.utils.apm import FilterOperator, TraceDatasourceTarget
from bkmonitor.data_source.format import flatten_dict_data
from semconv.rum.constants import RumSpanType, SPAN_TYPE_COMMON_DISPLAY_FIELDS, ViewPhase
from rum_web.handlers.level.base import BaseRumLevelHandler
from rum_web.handlers.query.span import SpanQuery
from rum_web.handlers.builder.timeline import build as build_timeline
from rum_web.handlers.builder.utils import get_safe_number


class SpanLevelHandler(BaseRumLevelHandler):
    """Span 层级处理器

    以 SpanQuery 作为主查询，实现 BaseRumLevelHandler 的全部接口能力。
    """

    query: SpanQuery

    DISPLAY_FIELDS = [
        *SPAN_TYPE_COMMON_DISPLAY_FIELDS,
        "attributes.view.url_template",
        "elapsed_time",
        "resource.user_agent.name",
        "attributes.user.id",
    ]

    #: 常驻筛选字段，前端置顶展示并默认带出的筛选维度
    RESIDENT_FIELDS = [
        "attributes.session.id",
        "trace_id",
        "span_name",
        "resource.deployment.environment.name",
        "resource.user_agent.name",
        "attributes.view.url_template",
        "attributes.outcome.type",
        "attributes.user.id",
        "elapsed_time",
    ]

    def __init__(self, data_sources: list[TraceDatasourceTarget]):
        super().__init__(data_sources)
        self.query = SpanQuery(data_sources)

    def view_config(
        self,
        start_time: int | None,
        end_time: int | None,
        extra_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        config = super().view_config(start_time, end_time, extra_config)
        config["span_type_resident_fields"] = {kind.value: list(kind.resident_fields) for kind in RumSpanType}
        config["span_type_display_fields"] = {kind.value: kind.display_fields for kind in RumSpanType}
        return config

    def timeline(self, session_id: str | None = None, view_id: str | None = None) -> dict[str, Any]:
        """查询会话或单个 View 的时间线，单次最多读取 10000 条原始 Span，不分页。"""
        record_id = session_id or view_id
        if not record_id:
            raise ValidationError(_("session_id 和 view_id 至少提供一个"))

        filters: list[types.Filter] = [
            {
                "key": "attributes.session.id" if session_id else "attributes.view.id",
                "value": [record_id],
                "operator": FilterOperator.EQUAL,
            }
        ]
        if view_id:
            filters.append(
                {
                    "key": "attributes.span_type",
                    "value": [RumSpanType.SESSION.value],
                    "operator": FilterOperator.NOT_EQUAL,
                }
            )
        spans = self.query.query_list(
            start_time=None,
            end_time=None,
            offset=0,
            limit=10000,
            filters=filters,
            sort=["start_time", "span_id"],
        )
        timeline = build_timeline(spans)
        if view_id:
            timeline["start_time"], timeline["end_time"] = self._view_time_range(spans)
        return timeline

    @staticmethod
    def _view_time_range(spans: list[dict[str, Any]]) -> tuple[int | None, int | None]:
        """开始取最早导航时间（ms → us），结束取结束快照的最晚退出时间。"""
        start_times: list[int | float] = []
        end_times: list[int | float] = []
        for span in spans:
            view = flatten_dict_data(span)
            if view.get("attributes.span_type") != RumSpanType.VIEW.value:
                continue
            if (started_at := get_safe_number(view.get("attributes.view.started_at"), None)) is not None:
                start_times.append(started_at)
            if view.get("attributes.view.phase") == ViewPhase.END.value:
                if (end_time := get_safe_number(view.get("end_time"), None)) is not None:
                    end_times.append(end_time)
        return (
            int(min(start_times) * 1000) if start_times else None,
            int(max(end_times)) if end_times else None,
        )
