"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from django.utils.translation import gettext_lazy as _

from bkmonitor.data_source.format import flatten_dict_data
from semconv.rum.constants import ResourceType
from rum_web.handlers.builder.base import BaseSection, KeyInfoSection, KeyValueItem, WaterfallSection, group
from rum_web.handlers.builder.constants import SectionType
from rum_web.handlers.builder.hover import RESOURCE_PHASE_HOVERS
from rum_web.handlers.builder.span.base import SpanBuilder, SpanOverview, named
from rum_web.handlers.builder.span.resource_timing import (
    CrossOriginLayout,
    LocalLayout,
    NetworkLayout,
    ReusedLayout,
    ServiceWorkerLayout,
)
from rum_web.handlers.builder.utils import get_safe_number, safe_diff, waterfall


@dataclass(frozen=True, slots=True)
class CompressionRatioItem(KeyValueItem):
    """正文压缩率不含协议头；缺失或分母为零时返回 None。"""

    key: str = "display.compression_ratio"

    def render(self, flatten_data: dict[str, Any]) -> dict[str, Any]:
        encoded = get_safe_number(flatten_data.get("attributes.resource.encoded_body_size"), None)
        decoded = get_safe_number(flatten_data.get("attributes.resource.decoded_body_size"), None)
        return {self.key: None if encoded is None or not decoded else 1 - encoded / decoded}


class ResourceSpanOverview(SpanOverview):
    BADGES = named("elapsed_time", "attributes.resource.type", "attributes.http.response.status_code")


DURATION = group("duration", "elapsed_time")
HTTP_RESULT = group("http_result", "attributes.http.response.status_code", "attributes.outcome.type")
TRANSFER = group(
    "transfer",
    CompressionRatioItem(),
    "attributes.resource.transfer_size",
    "attributes.resource.encoded_body_size",
    "attributes.resource.decoded_body_size",
)


class ResourceXhrAndFetchKeyInfoSection(KeyInfoSection):
    DATA = (
        group(
            "request",
            "attributes.http.request.method",
            "attributes.url.template",
            "attributes.url.full",
            "attributes.server.address",
        ),
        DURATION,
        HTTP_RESULT,
        TRANSFER,
    )


class LoadingTimingSection(WaterfallSection):
    """按 A→E 瀑布图类型输出阶段；缺少新时间点时独立兼容旧阶段字段。"""

    KEY = "loading_timing"
    PHASE_HOVERS = RESOURCE_PHASE_HOVERS
    PHASE_ALIASES = {
        "total": _("总耗时"),
        "redirect": _("重定向"),
        "prepare": _("发起前等待"),
        "queueing": _("[资源调度] 正在排队"),
        "sw_startup": _("[ServiceWorker] 启动"),
        "sw_request": _("[ServiceWorker] 发送请求"),
        "sw_respond_with": _("[ServiceWorker] respondWith"),
        "dns": _("DNS"),
        "connect": _("连接建立"),
        "tls": _("TLS"),
        "first_byte": _("等待首字节"),
        "download": _("内容下载"),
    }

    # 按 A→E 顺序匹配，E 的「未匹配 A–D」由顺序保证；ReusedLayout 继承 NetworkLayout，必须排在其前。
    LAYOUTS = (CrossOriginLayout, ServiceWorkerLayout, LocalLayout, ReusedLayout, NetworkLayout)

    def get_data(self) -> dict[str, Any] | None:
        start = self.numeric_or_none("attributes.resource.timing.start_time")
        end = self.numeric_or_none("attributes.resource.timing.response_end")
        if start is None or end is None:
            return self._legacy_waterfall()
        if end <= start:
            return None
        for layout_cls in self.LAYOUTS:
            if (layout := layout_cls(self.flatten_data)).matches():
                break
        else:
            # 未匹配任何类型时只展示总耗时。
            layout = CrossOriginLayout(self.flatten_data)
        # 可选阶段（如未发生重定向）、乱序阶段在 span 中返回 None，这里统一过滤。
        specs = [spec for spec in layout.phases() if spec is not None]
        return waterfall(self.phases(specs), total=end - start)

    def _legacy_waterfall(self) -> dict[str, Any] | None:
        """兼容仅上报 resource.*.start / duration 的旧版 SDK。

        旧 start 是相对资源 entry.startTime 的偏移，缺少还原到 timeOrigin 的基准，
        不能传入 TimingLayout；此处直接按旧阶段字段构建瀑布图。
        """
        redirect_start = self.numeric_or_none("attributes.resource.redirect.start")
        dns_start = self.numeric_or_none("attributes.resource.dns.start")
        timings = {
            "prepare": (redirect_start, safe_diff(dns_start, redirect_start)),
            **{
                key: (
                    self.numeric_or_none(f"attributes.resource.{field}.start"),
                    self.numeric_or_none(f"attributes.resource.{field}.duration"),
                )
                for key, field in (
                    ("dns", "dns"),
                    ("connect", "connect"),
                    ("tls", "ssl"),
                    ("first_byte", "first_byte"),
                    ("download", "download"),
                )
            },
        }
        tls_start, tls_duration = timings["tls"]
        connect_start, connect_duration = timings["connect"]
        # 旧 connect.duration 包含 TLS；仅在 TLS 字段有效时扣除，避免缺失值导致误算。
        if tls_start is not None and tls_duration is not None and tls_duration >= 0 and connect_duration is not None:
            timings["connect"] = (connect_start, connect_duration - tls_duration)
        download_start, download_duration = timings["download"]
        total = (
            download_start + download_duration
            if download_start is not None and download_duration is not None and download_duration >= 0
            else 0
        )
        return waterfall(self.phases((key, start, duration) for key, (start, duration) in timings.items()), total=total)


class ResourceOthersKeyInfoSection(KeyInfoSection):
    DATA = (
        HTTP_RESULT,
        DURATION,
        TRANSFER,
        group("delivery", "attributes.resource.delivery_type", "attributes.resource.cache.hit"),
        group("blocking", "attributes.resource.render_blocking_status"),
    )


class ResourceOthersResourceInfoSection(BaseSection):
    KEY = "resource_info"
    TYPE = SectionType.SUMMARY_CARDS.value
    ITEMS = named(
        "attributes.resource.type",
        "attributes.url.template",
        "attributes.server.address",
        "attributes.http.request.method",
        "attributes.resource.protocol",
    )


class ResourceXhrAndFetchSpanBuilder(SpanBuilder):
    OVERVIEW = ResourceSpanOverview
    SECTIONS = (ResourceXhrAndFetchKeyInfoSection, LoadingTimingSection)


class ResourceOthersSpanBuilder(SpanBuilder):
    OVERVIEW = ResourceSpanOverview
    SECTIONS = (ResourceOthersKeyInfoSection, ResourceOthersResourceInfoSection, LoadingTimingSection)


class ResourceSpanBuilder(SpanBuilder):
    XHR_FETCH_TYPES = frozenset({ResourceType.XHR.value, ResourceType.FETCH.value})

    @classmethod
    def process(cls, span: dict[str, Any], related_spans: Sequence[dict[str, Any]] = ()) -> dict[str, Any]:
        resource_type = flatten_dict_data(span).get("attributes.resource.type")
        builder = ResourceXhrAndFetchSpanBuilder if resource_type in cls.XHR_FETCH_TYPES else ResourceOthersSpanBuilder
        return builder.process(span, related_spans)
