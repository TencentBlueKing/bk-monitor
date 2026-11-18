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

from rum_web.handlers.builder.span.timing.base import Phase, TimingLayout
from rum_web.handlers.builder.utils import get_safe_number


CURRENT_TIMING_PREFIX = "attributes.timing."
OLD_TIMING_PREFIX = "attributes.resource.timing."


class ResourceTimingLayout(TimingLayout):
    def __init__(self, flatten_data: dict[str, Any], *, timing_prefix: str):
        super().__init__(flatten_data)
        self.TIMING_PREFIX = timing_prefix
        self.uses_old_fields = timing_prefix == OLD_TIMING_PREFIX

    def point(self, name: str) -> int | float | None:
        value = super().point(name)
        return 0 if self.uses_old_fields and value is None else value

    def body_size(self) -> int | float | None:
        field = "decoded_body_size" if self.uses_old_fields else "size"
        return get_safe_number(self.flatten_data.get(f"attributes.resource.{field}"), None)

    def span(self, key: str, start: int | float | None, end: int | float | None) -> Phase | None:
        if not self.uses_old_fields and end is not None and end > (self.point("response_end") or 0):
            return None
        return super().span(key, start, end)

    def _redirect_and_wait_spans(self, key: str, next_point: int | float | None) -> list[Phase | None]:
        redirect_end = self.point("redirect_end")
        return [
            self.span("redirect", self.point("redirect_start"), redirect_end),
            self.span(key, redirect_end or self.point("start_time"), next_point),
        ]


class CrossOriginLayout(ResourceTimingLayout):
    """A. 跨域明细不可见：只展示总耗时，也是未匹配任何类型时的兜底。"""

    def matches(self) -> bool:
        return self.point("request_start") == self.point("response_start") == self.body_size() == 0

    def phases(self) -> list[Phase | None]:
        return [self.span("total", self.point("start_time"), self.point("response_end"))]


class ServiceWorkerLayout(ResourceTimingLayout):
    """B. Service Worker 响应：网络耗时在 SW 内部请求上，主请求看不到 DNS 与建连。"""

    def matches(self) -> bool:
        if not self.uses_old_fields:
            return self.flatten_data.get("attributes.resource.delivery_type") == "service_worker"
        return (
            (self.point("worker_start") or 0) > 0
            and self.point("connect_end") in (0, self.point("fetch_start"))
            and self.flatten_data.get(f"{self.TIMING_PREFIX}worker_matched_router_source") in (None, "", "fetch-event")
            and self.flatten_data.get(f"{self.TIMING_PREFIX}worker_final_router_source") != "cache"
        )

    def phases(self) -> list[Phase | None]:
        # 部分浏览器在 SW 场景不记录 requestStart / responseStart，按文档改用兜底时间点。
        request = self.point("request_start") or self.point("fetch_start")
        return [
            *self._redirect_and_wait_spans("queueing", self.point("worker_start")),
            self.span("sw_startup", self.point("worker_start"), self.point("fetch_start")),
            self.span("sw_request", self.point("fetch_start"), self.point("request_start")),
            self.span("sw_respond_with", request, self.point("response_start") or self.point("response_end")),
            self.span("first_byte", request, self.point("response_start")),
            self.span(
                "download", self.point("response_start") or self.point("fetch_start"), self.point("response_end")
            ),
        ]


class LocalLayout(ResourceTimingLayout):
    """C. 非网络响应：浏览器缓存、推断缓存或 SW 静态路由命中缓存。"""

    def matches(self) -> bool:
        connect_end = self.point("connect_end")
        if connect_end is None or connect_end not in (0, self.point("fetch_start")):
            return False
        delivery_type = self.flatten_data.get("attributes.resource.delivery_type") or None
        # 大小字段缺失保留 None，避免把未上报 transfer_size 的请求误判为缓存命中。
        no_transfer = get_safe_number(self.flatten_data.get("attributes.resource.transfer_size"), None) == 0
        return (
            (delivery_type == "cache" and no_transfer)
            # 未上报 delivery_type 的浏览器：没有传输字节但有正文，按缓存命中处理。
            or (delivery_type is None and no_transfer and (self.body_size() or 0) > 0)
            or self.flatten_data.get(f"{self.TIMING_PREFIX}worker_final_router_source") == "cache"
        )

    def phases(self) -> list[Phase | None]:
        return [
            *self._redirect_and_wait_spans("prepare", self.point("fetch_start")),
            self.span("first_byte", self.point("fetch_start"), self.point("response_start")),
            self.span(
                "download", self.point("response_start") or self.point("fetch_start"), self.point("response_end")
            ),
        ]


class NetworkLayout(ResourceTimingLayout):
    """E. 网络请求：普通请求、缓存重新验证等。"""

    def matches(self) -> bool:
        return (self.point("connect_start") or 0) > 0 and (self.point("connect_end") or 0) > 0

    def connection(self) -> list[Phase | None]:
        connect_start, connect_end = self.point("connect_start") or 0, self.point("connect_end") or 0
        tls = self.point("secure_connection_start") or 0
        # secureConnectionStart 落在连接区间外时，本次连接没有可见的 TLS 握手。
        if not connect_start <= tls <= connect_end:
            tls = 0
        dns_start = self.point("domain_lookup_start")
        if not self.uses_old_fields:
            dns_start = dns_start or None
        return [
            self.span("dns", dns_start, self.point("domain_lookup_end")),
            self.span("connect", connect_start, tls or connect_end),
            self.span("tls", tls, connect_end) if tls else None,
        ]

    def phases(self) -> list[Phase | None]:
        wait_end = self.point("domain_lookup_start" if self.uses_old_fields else "fetch_start")
        response_start = self.point("response_start")
        if not self.uses_old_fields:
            response_start = response_start or None
        return [
            *self._redirect_and_wait_spans("prepare", wait_end),
            *self.connection(),
            self.span("first_byte", self.point("connect_end"), response_start),
            self.span("download", response_start, self.point("response_end")),
        ]


class ReusedLayout(NetworkLayout):
    """D. 连接复用：与 E 同图，仅连接段不同；判定比 E 严格，需排在 E 之前匹配。"""

    def matches(self) -> bool:
        connect_end = self.point("connect_end") or 0
        return (
            connect_end != 0
            and (self.uses_old_fields or connect_end > 0)
            and self.point("domain_lookup_start")
            == self.point("domain_lookup_end")
            == self.point("connect_start")
            == connect_end
        )

    def connection(self) -> list[Phase | None]:
        # 三段以 0 耗时输出，前端据此合并为「连接复用」提示。
        connect_end = self.point("connect_end") or 0
        if not self.uses_old_fields and connect_end > (self.point("response_end") or 0):
            return []
        offset = connect_end - (self.point("start_time") or 0)
        return [(key, offset, 0) for key in ("dns", "connect", "tls")] if offset >= 0 else []
