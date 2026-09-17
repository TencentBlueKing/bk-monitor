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

from semconv.constants import FieldUnit
from semconv.rum.constants import ResourceType

from rum_web.handlers.builder.base import (
    BaseSection,
    DictItem,
    EMPTY_VALUE,
    KeyValueItem,
    NamedKeyValueItem,
)
from rum_web.handlers.builder.constants import SectionType
from rum_web.handlers.builder.span.base import (
    OVERVIEW_ATTRIBUTES_HTTP_RESPONSE_STATUS_CODE,
    OVERVIEW_ATTRIBUTES_RESOURCE_TYPE,
    OVERVIEW_ELAPSED_TIME,
    SpanBuilder,
    SpanOverview,
)
from rum_web.handlers.builder.utils import get_safe_number


@dataclass(frozen=True, slots=True)
class CompressionRatioItem(KeyValueItem):
    """压缩率 = 1 - encoded_body_size / decoded_body_size。

    - 分子 ``encoded_body_size``：压缩后正文大小（不含协议头）。
    - 分母 ``decoded_body_size``：解压后正文大小。
    - 缺失或分母为 0 时返回 :data:`BaseComponent.EMPTY_VALUE`，避免与「真实压缩率为 0」混淆；
      也避免使用 ``transfer_size`` 导致缓存命中（transfer=0）时压缩率恒为 100%。
    """

    key: str = "display.compression_ratio"

    def render(self, flatten_data: dict[str, Any]) -> dict[str, Any]:
        encoded = get_safe_number(flatten_data.get("attributes.resource.encoded_body_size"), None)
        decoded = get_safe_number(flatten_data.get("attributes.resource.decoded_body_size"), None)
        if encoded is None or not decoded:
            return {self.key: EMPTY_VALUE}
        return {self.key: 1 - encoded / decoded}


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
    """加载时序瀑布：按「字段缺失 → 不出段」组装，避免伪造全零瀑布。

    - 跨域资源无 ``Timing-Allow-Origin`` 时时序字段全为空，应返回空 ``phases``。
    - ``tls`` 段缺失整段不输出，不能在时间轴原点渲染一条 duration=0 的假 TLS 段。
    - 各段 ``duration`` 收敛负值，避免 ``connect - ssl`` 之类的相减产生负数。
    """

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

    def _numeric_or_none(self, key: str) -> int | float | None:
        """字段缺失或非数值返回 ``None``，用于「缺失 → 不出段」判定。"""
        return get_safe_number(self.flatten_data.get(key), None)

    def _phase(
        self,
        key: str,
        start: int | float | None,
        duration: int | float | None,
    ) -> dict[str, Any] | None:
        """构造单个 phase；起点或时长缺失、时长为负则整段不输出。"""
        if start is None or duration is None or duration < 0:
            return None
        return {
            "key": key,
            "alias": self.PHASE_ALIASES[key],
            "start": start,
            "duration": duration,
        }

    def _fill_data(self):
        redirect_start = self._numeric_or_none("attributes.resource.redirect.start")
        dns_start = self._numeric_or_none("attributes.resource.dns.start")
        dns_duration = self._numeric_or_none("attributes.resource.dns.duration")
        connect_start = self._numeric_or_none("attributes.resource.connect.start")
        connect_duration = self._numeric_or_none("attributes.resource.connect.duration")
        ssl_start = self._numeric_or_none("attributes.resource.ssl.start")
        ssl_duration = self._numeric_or_none("attributes.resource.ssl.duration")
        first_byte_start = self._numeric_or_none("attributes.resource.first_byte.start")
        first_byte_duration = self._numeric_or_none("attributes.resource.first_byte.duration")
        download_start = self._numeric_or_none("attributes.resource.download.start")
        download_duration = self._numeric_or_none("attributes.resource.download.duration")

        # prepare 段：redirect_start 与 dns_start 均需存在，duration 收敛非负
        prepare_duration = dns_start - redirect_start if redirect_start is not None and dns_start is not None else None
        # connect 仅在 TLS 分段有效时扣除 ssl_duration，其他情况保持原值
        adjusted_connect_duration = connect_duration
        if connect_duration is not None and ssl_duration is not None:
            adjusted_connect_duration = connect_duration - ssl_duration

        phases_candidates = [
            self._phase("prepare", redirect_start, prepare_duration),
            self._phase("dns", dns_start, dns_duration),
            self._phase("connect", connect_start, adjusted_connect_duration),
            # TLS 段任一字段缺失整段省略：不能在时间轴原点渲染 duration=0 的假段
            self._phase("tls", ssl_start, ssl_duration),
            self._phase("first_byte", first_byte_start, first_byte_duration),
            self._phase("download", download_start, download_duration),
        ]
        phases = [p for p in phases_candidates if p is not None]

        # 整段时序都拿不到时省略 ``data``，前端可据此区分「没有时序数据」与「耗时为 0」
        if not phases:
            return

        total_duration = 0
        if download_start is not None and download_duration is not None and download_duration >= 0:
            total_duration = download_start + download_duration

        self.component_dict["data"] = {
            "unit": FieldUnit.MS.value,
            "total_duration": total_duration,
            "phases": phases,
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


class ResourceXhrAndFetchSpanBuilder(SpanBuilder):
    """Resource(xhr / fetch) 子协议：请求 → 耗时 → HTTP 结果 → 传输 + 加载瀑布。"""

    OVERVIEW = ResourceSpanOverview
    SECTIONS: list[type[BaseSection]] = [
        ResourceXhrAndFetchKeyInfoSection,
        LoadingTimingSection,
    ]


class ResourceOthersSpanBuilder(SpanBuilder):
    """Resource(其它类型，img / css / js / ...) 子协议：
    结果 → 耗时 → 传输 → 投递 → 阻塞 + 资源信息 + 加载瀑布。
    """

    OVERVIEW = ResourceSpanOverview
    SECTIONS: list[type[BaseSection]] = [
        ResourceOthersKeyInfoSection,
        ResourceOthersResourceInfoSection,
        LoadingTimingSection,
    ]


class ResourceSpanBuilder(SpanBuilder):
    """Resource 类型 Span 详情 Builder 入口：仅负责按 ``attributes.resource.type`` 分派子 Builder。

    - XHR / Fetch → :class:`ResourceXhrAndFetchSpanBuilder`
    - 其它资源  → :class:`ResourceOthersSpanBuilder`

    子 Builder 各自声明 ``OVERVIEW`` / ``SECTIONS``，复用 :class:`SpanBuilder.process` 的
    公共装配流程（``origin_data`` / ``span_id`` / ``overview`` / ``sections``）。
    """

    XHR_FETCH_TYPES: frozenset[str] = frozenset({ResourceType.XHR.value, ResourceType.FETCH.value})

    @classmethod
    def process(
        cls,
        span: dict[str, Any],
        related_spans: Sequence[dict[str, Any]] = (),
    ) -> dict[str, Any]:
        resource_type: str = span.get("attributes", {}).get("resource.type", "")
        sub_builder: type[SpanBuilder] = (
            ResourceXhrAndFetchSpanBuilder if resource_type in cls.XHR_FETCH_TYPES else ResourceOthersSpanBuilder
        )
        return sub_builder.process(span, related_spans)
