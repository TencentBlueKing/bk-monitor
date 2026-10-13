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
from rum_web.handlers.builder.span.base import SpanBuilder, SpanOverview, named
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
    KEY = "loading_timing"
    PHASE_ALIASES = {
        "prepare": _("浏览器准备"),
        "dns": _("DNS"),
        "connect": _("TCP"),
        "tls": _("TLS"),
        "first_byte": _("等待首字节"),
        "download": _("内容下载"),
    }
    PHASE_FIELDS = (
        ("dns", "dns"),
        ("connect", "connect"),
        ("tls", "ssl"),
        ("first_byte", "first_byte"),
        ("download", "download"),
    )

    def get_data(self) -> dict[str, Any] | None:
        redirect_start = self.numeric_or_none("attributes.resource.redirect.start")
        dns_start = self.numeric_or_none("attributes.resource.dns.start")
        timings = {
            "prepare": (redirect_start, safe_diff(dns_start, redirect_start)),
            **{
                key: (
                    self.numeric_or_none(f"attributes.resource.{field}.start"),
                    self.numeric_or_none(f"attributes.resource.{field}.duration"),
                )
                for key, field in self.PHASE_FIELDS
            },
        }
        tls_start, tls_duration = timings["tls"]
        connect_start, connect_duration = timings["connect"]
        # TLS 段有效时才扣除握手耗时，缺少字段不能视为发生或未发生握手。
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
