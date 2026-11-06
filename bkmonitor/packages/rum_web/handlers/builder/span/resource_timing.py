"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from rum_web.handlers.builder.base import BaseComponent
from rum_web.handlers.builder.utils import get_safe_number


TIMING_PREFIX = "attributes.resource.timing."


class TimingLayout(BaseComponent):
    """瀑布图类型策略：``matches`` 判定类型，``phases`` 按展示顺序返回阶段。"""

    def value(self, name: str) -> int | float:
        """时间点缺失按 0，与浏览器「未发生 / 跨域不可见」语义一致；「无 X 时改用 Y」写作 value(X) or value(Y)。"""
        return get_safe_number(self.flatten_data.get(f"{TIMING_PREFIX}{name}")) or 0

    def span(self, key: str, start: int | float, end: int | float) -> tuple[str, int | float, int | float] | None:
        """起点早于 start_time 或耗时 <= 0（含乱序）时返回 None；可选阶段由调用方判断是否发生。"""
        start_time = self.value("start_time")
        if not start_time <= start < end:
            return None
        return key, start - start_time, end - start

    def redirect_and_wait_spans(
        self, key: str, next_point: int | float
    ) -> list[tuple[str, int | float, int | float] | None]:
        """先展示重定向，后续等待从 redirect_end 起算；无重定向时回退到 start_time。"""
        return [
            self.span("redirect", self.value("redirect_start"), self.value("redirect_end")),
            self.span(key, self.value("redirect_end") or self.value("start_time"), next_point),
        ]

    def matches(self) -> bool:
        raise NotImplementedError

    def phases(self) -> list[tuple[str, int | float, int | float] | None]:
        raise NotImplementedError


class CrossOriginLayout(TimingLayout):
    """A. 跨域明细不可见：只展示总耗时，也是未匹配任何类型时的兜底。"""

    def matches(self) -> bool:
        decoded = get_safe_number(self.flatten_data.get("attributes.resource.decoded_body_size"), None)
        return self.value("request_start") == 0 and self.value("response_start") == 0 and decoded == 0

    def phases(self) -> list[tuple[str, int | float, int | float] | None]:
        return [self.span("total", self.value("start_time"), self.value("response_end"))]


class ServiceWorkerLayout(TimingLayout):
    """B. Service Worker 响应：网络耗时在 SW 内部请求上，主请求看不到 DNS 与建连。"""

    def matches(self) -> bool:
        return (
            self.value("worker_start") > 0
            and self.value("connect_end") in (0, self.value("fetch_start"))
            and self.flatten_data.get(f"{TIMING_PREFIX}worker_matched_router_source") in (None, "", "fetch-event")
            and self.flatten_data.get(f"{TIMING_PREFIX}worker_final_router_source") != "cache"
        )

    def phases(self) -> list[tuple[str, int | float, int | float] | None]:
        # 部分浏览器在 SW 场景不记录 requestStart / responseStart，按文档改用兜底时间点。
        request = self.value("request_start") or self.value("fetch_start")
        return [
            *self.redirect_and_wait_spans("queueing", self.value("worker_start")),
            self.span("sw_startup", self.value("worker_start"), self.value("fetch_start")),
            self.span("sw_request", self.value("fetch_start"), self.value("request_start")),
            self.span("sw_respond_with", request, self.value("response_start") or self.value("response_end")),
            self.span("first_byte", request, self.value("response_start")),
            self.span(
                "download", self.value("response_start") or self.value("fetch_start"), self.value("response_end")
            ),
        ]


class LocalLayout(TimingLayout):
    """C. 非网络响应：浏览器缓存、推断缓存或 SW 静态路由命中缓存。"""

    def matches(self) -> bool:
        if self.value("connect_end") not in (0, self.value("fetch_start")):
            return False
        delivery_type = self.flatten_data.get("attributes.resource.delivery_type") or None
        # 大小字段缺失保留 None，避免把未上报 transfer_size 的请求误判为缓存命中。
        no_transfer = get_safe_number(self.flatten_data.get("attributes.resource.transfer_size"), None) == 0
        decoded = get_safe_number(self.flatten_data.get("attributes.resource.decoded_body_size")) or 0
        return (
            (delivery_type == "cache" and no_transfer)
            # 未上报 delivery_type 的浏览器：没有传输字节但有正文，按缓存命中处理。
            or (delivery_type is None and no_transfer and decoded > 0)
            or self.flatten_data.get(f"{TIMING_PREFIX}worker_final_router_source") == "cache"
        )

    def phases(self) -> list[tuple[str, int | float, int | float] | None]:
        return [
            *self.redirect_and_wait_spans("prepare", self.value("fetch_start")),
            self.span("first_byte", self.value("fetch_start"), self.value("response_start")),
            self.span(
                "download", self.value("response_start") or self.value("fetch_start"), self.value("response_end")
            ),
        ]


class NetworkLayout(TimingLayout):
    """E. 网络请求：普通请求、缓存重新验证等。"""

    def matches(self) -> bool:
        return self.value("connect_start") > 0 and self.value("connect_end") > 0

    def connection(self) -> list[tuple[str, int | float, int | float] | None]:
        tls = self.value("secure_connection_start")
        # 复用连接时 secureConnectionStart 可能被钳到 fetchStart，落在连接区间外的值不代表握手。
        if not self.value("connect_start") <= tls <= self.value("connect_end"):
            tls = 0
        return [
            self.span("dns", self.value("domain_lookup_start"), self.value("domain_lookup_end")),
            # 有 TLS 时连接建立只算到握手开始。
            self.span("connect", self.value("connect_start"), tls or self.value("connect_end")),
            self.span("tls", tls, self.value("connect_end")) if tls else None,
        ]

    def phases(self) -> list[tuple[str, int | float, int | float] | None]:
        return [
            *self.redirect_and_wait_spans("prepare", self.value("domain_lookup_start")),
            *self.connection(),
            self.span("first_byte", self.value("connect_end"), self.value("response_start")),
            self.span("download", self.value("response_start"), self.value("response_end")),
        ]


class ReusedLayout(NetworkLayout):
    """D. 连接复用：与 E 同图，仅连接段不同；判定比 E 严格，需排在 E 之前匹配。"""

    def matches(self) -> bool:
        connect_end = self.value("connect_end")
        return (
            connect_end != 0
            and self.value("domain_lookup_start")
            == self.value("domain_lookup_end")
            == self.value("connect_start")
            == connect_end
        )

    def connection(self) -> list[tuple[str, int | float, int | float] | None]:
        # 与原有展示一致：三段以 0 耗时输出在 connect_end，前端据此合并为「连接复用」提示。
        offset = self.value("connect_end") - self.value("start_time")
        return [(key, offset, 0) for key in ("dns", "connect", "tls")] if offset >= 0 else []
