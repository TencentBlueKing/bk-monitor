"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from rum_web.handlers.builder.span.timing.base import Phase, TimingLayout
from rum_web.handlers.builder.utils import get_safe_number
from semconv.rum.constants import ViewLoadingTimeSource


class ViewTimingLayout(TimingLayout):
    TIMING_PREFIX = "attributes.timing."

    def matches(self) -> bool:
        start = self.point("start_time")
        return start is not None and start >= 0

    def stable_end(self) -> int | float | None:
        if self.flatten_data.get("attributes.view.loading_time_source") != ViewLoadingTimeSource.AUTO.value:
            return None
        load_start = self.point("load_event_start") or 0
        load_end = self.point("load_event_end") or 0
        loading_time = get_safe_number(self.flatten_data.get("attributes.view.loading_time"))
        if load_start <= 0 or load_end < load_start or loading_time <= 0:
            return None
        end = max(load_end, loading_time)
        return end if end > load_start else None

    def _connection_phases(
        self, connect_start: int | float, connect_end: int | float, *, reused: bool
    ) -> list[Phase | None]:
        if reused:
            offset = connect_end - (self.point("start_time") or 0)
            # 前端将三条零耗时阶段合并为连接复用提示。
            return [(key, offset, 0) for key in ("dns", "connect", "tls")] if offset >= 0 else []

        tls = self.point("secure_connection_start") or 0
        if not connect_start <= tls <= connect_end:
            tls = 0
        return [
            self.span("dns", self.point("domain_lookup_start"), self.point("domain_lookup_end")),
            self.span("connect", connect_start, tls or connect_end),
            self.span("tls", tls, connect_end) if tls else None,
        ]

    def phases(self) -> list[Phase | None]:
        connect_start = self.point("connect_start") or 0
        connect_end = self.point("connect_end") or 0
        reused = (
            connect_end != 0
            and self.point("domain_lookup_start") == self.point("domain_lookup_end") == connect_start == connect_end
        )
        connected = reused or (connect_start > 0 and connect_end > 0)
        connection = self._connection_phases(connect_start, connect_end, reused=reused) if connected else []
        redirect_end = self.point("redirect_end")
        fetch_start = self.point("fetch_start")
        response_start = self.point("response_start") or 0
        response_end = self.point("response_end") or None
        # 过渡期 SDK 仍可从 view.dom_interactive 提供 DOM 解析终点。
        interactive = self.point("dom_interactive") or get_safe_number(
            self.flatten_data.get("attributes.view.dom_interactive"), None
        )
        load_start = self.point("load_event_start")
        return [
            self.span("redirect", self.point("redirect_start"), redirect_end),
            self.span("prepare", redirect_end or self.point("start_time"), fetch_start),
            *connection,
            self.span("first_byte", connect_end, response_start) if connect_end > 0 else None,
            self.span("download", response_start, response_end) if response_start > 0 else None,
            self.span("dom_parsing", response_end, interactive),
            self.span("resource_load", interactive or None, load_start),
            self.span("page_stable", load_start, self.stable_end()),
        ]
