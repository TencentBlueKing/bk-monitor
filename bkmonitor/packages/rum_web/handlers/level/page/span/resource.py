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
from dataclasses import dataclass
from django.utils.translation import gettext_lazy as _

from semconv.constants import FieldUnit

from rum_web.handlers.level.page.base import BasePage, BaseSection, KeyValueItem
from rum_web.handlers.level.page.span.base import (
    OVERVIEW_ELAPSED_TIME,
    OVERVIEW_ATTRIBUTES_RESOURCE_TYPE,
    OVERVIEW_ATTRIBUTES_HTTP_RESPONSE_STATUS_CODE,
    SpanOverview,
)
from rum_web.handlers.level.page.constants import SectionType


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


class ResourceXhrAndFetchKeyInfoSection(BaseSection):
    KEY = "key_info"
    TYPE = SectionType.SUMMARY_CARDS.value
    DATA = [
        KeyValueItem(
            key="request",
            items=[
                KeyValueItem(key="attributes.http.request.method"),
                KeyValueItem(key="attributes.url.template"),
                KeyValueItem(key="attributes.url.full"),
                KeyValueItem(key="attributes.server.address"),
            ],
        ),
        KeyValueItem(
            key="duration",
            items=[
                KeyValueItem(key="elapsed_time"),
            ],
        ),
        KeyValueItem(
            key="http_result",
            items=[
                KeyValueItem(key="attributes.http.response.status_code"),
                KeyValueItem(key="attributes.outcome.type"),
            ],
        ),
        KeyValueItem(
            key="transfer",
            items=[
                CompressionRatioItem(),
                KeyValueItem(key="attributes.resource.transfer_size"),
                KeyValueItem(key="attributes.resource.encoded_body_size"),
                KeyValueItem(key="attributes.resource.decoded_body_size"),
            ],
        ),
    ]

    def _fill_data(self):
        self.component_dict["data"] = {}
        for item in self.DATA:
            self.component_dict["data"].update(item.render(self.origin_data))

    def render(self) -> dict[str, Any]:
        super().render()
        self._fill_data()
        return self.component_dict


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

    @classmethod
    def safe_number(cls, value: str | int | float | None, default: int | float = 0) -> int | float:
        """安全地将任意值转换为数字（int 或 float）。

        支持 str / int / float / None；转换失败时返回 default 而非 nan，
        避免 nan 参与后续比较/计算产生隐蔽错误。
        """
        if value is None:
            return default
        try:
            numeric_value = float(value)
            return int(numeric_value) if numeric_value.is_integer() else numeric_value
        except (TypeError, ValueError):
            return default

    def get_numeric_value(self, key: str):
        return self.safe_number(self.origin_data.get(key))

    def _fill_data(self):
        redirect_start = self.get_numeric_value("attributes.resource.redirect.start")
        dns_start = self.get_numeric_value("attributes.resource.dns.start")
        dns_duration = self.get_numeric_value("attributes.resource.dns.duration")
        connect_start = self.get_numeric_value("attributes.resource.connect.start")
        connect_duration = self.get_numeric_value("attributes.resource.connect.duration")
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

    def render(self) -> dict[str, Any]:
        self.component_dict.update({"key": self.KEY, "type": self.TYPE})
        self._fill_data()
        return self.component_dict


class ResourceSpanOverview(SpanOverview):
    BADGES = [
        OVERVIEW_ELAPSED_TIME,
        OVERVIEW_ATTRIBUTES_RESOURCE_TYPE,
        OVERVIEW_ATTRIBUTES_HTTP_RESPONSE_STATUS_CODE,
    ]


class ResourceXhrAndFetchPage(BasePage):
    OVERVIEW = ResourceSpanOverview
    SECTIONS = [
        ResourceXhrAndFetchKeyInfoSection,
        LoadingTimingSection,
    ]
