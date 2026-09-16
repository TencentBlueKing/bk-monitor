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
from semconv.constants import FieldUnit
from semconv.rum.constants import ResourceType

from rum_web.handlers.builder.base import (
    BaseSection,
    DictItem,
    KeyValueItem,
    NamedKeyValueItem,
    SpanBuilder,
)
from rum_web.handlers.builder.constants import SectionType
from rum_web.handlers.builder.span.base import (
    OVERVIEW_ATTRIBUTES_HTTP_RESPONSE_STATUS_CODE,
    OVERVIEW_ATTRIBUTES_RESOURCE_TYPE,
    OVERVIEW_ELAPSED_TIME,
    SpanOverview,
)


@dataclass(frozen=True, slots=True)
class CompressionRatioItem(KeyValueItem):
    key: str = "display.compression_ratio"

    def render(self, origin_data: dict[str, Any]) -> dict[str, Any]:
        ratio = 0
        if (
            "attributes.resource.transfer_size" in origin_data
            and "attributes.resource.decoded_body_size" in origin_data
        ):
            decoded_body_size = float(origin_data["attributes.resource.decoded_body_size"])
            if decoded_body_size != 0:
                ratio = 1 - float(origin_data["attributes.resource.transfer_size"]) / decoded_body_size
        return {self.key: ratio}


class ResourceSpanOverview(SpanOverview):
    BADGES = [
        OVERVIEW_ELAPSED_TIME,
        OVERVIEW_ATTRIBUTES_RESOURCE_TYPE,
        OVERVIEW_ATTRIBUTES_HTTP_RESPONSE_STATUS_CODE,
    ]


class ResourceXhrAndFetchKeyInfoSection(BaseSection):
    KEY = "key_info"
    TYPE = SectionType.SUMMARY_CARDS.value
    DATA = [
        DictItem(
            key="request",
            items=[
                KeyValueItem(key="attributes.http.request.method"),
                KeyValueItem(key="attributes.url.template"),
                KeyValueItem(key="attributes.url.full"),
                KeyValueItem(key="attributes.server.address"),
            ],
        ),
        DictItem(
            key="duration",
            items=[
                KeyValueItem(key="elapsed_time"),
            ],
        ),
        DictItem(
            key="http_result",
            items=[
                KeyValueItem(key="attributes.http.response.status_code"),
                KeyValueItem(key="attributes.outcome.type"),
            ],
        ),
        DictItem(
            key="transfer",
            items=[
                CompressionRatioItem(),
                KeyValueItem(key="attributes.resource.transfer_size"),
                KeyValueItem(key="attributes.resource.encoded_body_size"),
                KeyValueItem(key="attributes.resource.decoded_body_size"),
            ],
        ),
    ]


class LoadingTimingSection(BaseSection):
    KEY = "loading_timing"
    TYPE = SectionType.WATERFALL.value

    PHASE_ALIASES = {
        "prepare": _("浏览器准备"),
        "dns": _("DNS"),
        "connect": _("TCP"),
        "tls": _("TLS"),
        "first_byte": _("等待首字节"),
        "download": _("内容下载"),
    }

    def _fill_data(self):
        redirect_start = self.get_numeric_value("attributes.resource.redirect.start")
        dns_start = self.get_numeric_value("attributes.resource.dns.start")
        dns_duration = self.get_numeric_value("attributes.resource.dns.duration") - self.get_numeric_value(
            "attributes.resource.redirect.start"
        )
        connect_start = self.get_numeric_value("attributes.resource.connect.start")
        connect_duration = self.get_numeric_value("attributes.resource.connect.duration") - self.get_numeric_value(
            "attributes.resource.ssl.duration"
        )
        ssl_start = self.get_numeric_value("attributes.resource.ssl.start")
        ssl_duration = self.get_numeric_value("attributes.resource.ssl.duration")
        first_byte_start = self.get_numeric_value("attributes.resource.first_byte.start")
        first_byte_duration = self.get_numeric_value("attributes.resource.first_byte.duration")
        download_start = self.get_numeric_value("attributes.resource.download.start")
        download_duration = self.get_numeric_value("attributes.resource.download.duration")

        self.component_dict["data"] = {
            "unit": FieldUnit.MS.value,
            "total_duration": download_start + download_duration,
            "phases": [
                {
                    "key": "prepare",
                    "alias": self.PHASE_ALIASES["prepare"],
                    "start": redirect_start,
                    "duration": dns_start - redirect_start,
                },
                {
                    "key": "dns",
                    "alias": self.PHASE_ALIASES["dns"],
                    "start": dns_start,
                    "duration": dns_duration,
                },
                {
                    "key": "connect",
                    "alias": self.PHASE_ALIASES["connect"],
                    "start": connect_start,
                    "duration": connect_duration - ssl_duration,
                },
                {
                    "key": "tls",
                    "alias": self.PHASE_ALIASES["tls"],
                    "start": ssl_start,
                    "duration": ssl_duration,
                },
                {
                    "key": "first_byte",
                    "alias": self.PHASE_ALIASES["first_byte"],
                    "start": first_byte_start,
                    "duration": first_byte_duration,
                },
                {
                    "key": "download",
                    "alias": self.PHASE_ALIASES["download"],
                    "start": download_start,
                    "duration": download_duration,
                },
            ],
        }


class ResourceOthersKeyInfoSection(BaseSection):
    KEY = "key_info"
    TYPE = SectionType.SUMMARY_CARDS.value
    DATA = [
        DictItem(
            key="http_result",
            items=[
                KeyValueItem(key="attributes.http.response.status_code"),
                KeyValueItem(key="attributes.outcome.type"),
            ],
        ),
        DictItem(
            key="duration",
            items=[
                KeyValueItem(key="elapsed_time"),
            ],
        ),
        DictItem(
            key="transfer",
            items=[
                CompressionRatioItem(),
                KeyValueItem(key="attributes.resource.transfer_size"),
                KeyValueItem(key="attributes.resource.encoded_body_size"),
                KeyValueItem(key="attributes.resource.decoded_body_size"),
            ],
        ),
        DictItem(
            key="delivery",
            items=[
                KeyValueItem(key="attributes.resource.delivery_type"),
                KeyValueItem(key="attributes.resource.cache.hit"),
            ],
        ),
        DictItem(
            key="blocking",
            items=[
                KeyValueItem(key="attributes.resource.render_blocking_status"),
            ],
        ),
    ]


class ResourceOthersResourceInfoSection(BaseSection):
    KEY = "resource_info"
    TYPE = SectionType.SUMMARY_CARDS.value
    ITEMS = [
        NamedKeyValueItem("attributes.resource.type"),
        NamedKeyValueItem("attributes.url.template"),
        NamedKeyValueItem("attributes.server.address"),
        NamedKeyValueItem("attributes.http.request.method"),
        NamedKeyValueItem("attributes.resource.protocol"),
    ]


class ResourceSpanBuilder(SpanBuilder):
    """Resource 类型 Span 详情 Builder：按 ``attributes.resource.type`` 分派子协议。

    - XHR / Fetch：请求 → 耗时 → HTTP 结果 → 传输 + 加载瀑布。
    - 其他资源（img / css / js / ...）：结果 → 耗时 → 传输 → 投递 → 阻塞 + 资源信息 + 加载瀑布。
    """

    OVERVIEW = ResourceSpanOverview

    XHR_FETCH_SECTIONS: list[type[BaseSection]] = [
        ResourceXhrAndFetchKeyInfoSection,
        LoadingTimingSection,
    ]
    OTHERS_SECTIONS: list[type[BaseSection]] = [
        ResourceOthersKeyInfoSection,
        ResourceOthersResourceInfoSection,
        LoadingTimingSection,
    ]

    XHR_FETCH_TYPES: frozenset[str] = frozenset({ResourceType.XHR.value, ResourceType.FETCH.value})

    @classmethod
    def process(
        cls,
        span: dict[str, Any],
        related_spans: Sequence[dict[str, Any]] = (),
    ) -> dict[str, Any]:
        origin_data = flatten_dict_data(span)
        sections = (
            cls.XHR_FETCH_SECTIONS
            if origin_data.get("attributes.resource.type") in cls.XHR_FETCH_TYPES
            else cls.OTHERS_SECTIONS
        )
        return {
            "origin_data": span,
            "span_id": span.get("span_id", ""),
            "overview": cls.OVERVIEW(origin_data).render(),
            "sections": [section(origin_data).render() for section in sections],
        }
