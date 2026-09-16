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
from constants.otel_query import RatingLevel
from semconv.constants import FieldUnit
from semconv.rum.constants import RumSpanType

from rum_web.handlers.builder.base import (
    BaseSection,
    DictItem,
    KeyValueItem,
    SpanBuilder,
)
from rum_web.handlers.builder.constants import SectionType
from rum_web.handlers.builder.span.base import (
    OVERVIEW_APP_NAME,
    OVERVIEW_ATTRIBUTES_SESSION_ID,
    OVERVIEW_ATTRIBUTES_USER_ID,
    OVERVIEW_ATTRIBUTES_VIEW_ID,
    OVERVIEW_ATTRIBUTES_VIEW_PREVIOUS_URL_TEMPLATE,
    OVERVIEW_ATTRIBUTES_VIEW_URL_TEMPLATE,
    OVERVIEW_ELAPSED_TIME,
    OVERVIEW_END_TIME,
    OVERVIEW_RESOURCE_DEPLOYMENT_ENVIRONMENT_NAME,
    OVERVIEW_START_TIME,
    SpanOverview,
    SpanTypeItem,
)
from rum_web.handlers.builder.utils import get_safe_number


# 每个 Web Vitals 指标在 origin_data 中挂载的嵌套字典键，
# 由 :meth:`ViewSpanBuilder._prepare_origin_data` 用同 View ID 且 span_type=vital 的最新快照填充。
VITAL_METRIC_KEYS: dict[str, str] = {
    "ttfb": "display.vitals.ttfb",
    "fcp": "display.vitals.fcp",
    "lcp": "display.vitals.lcp",
    "inp": "display.vitals.inp",
    "cls": "display.vitals.cls",
}


class ViewSpanOverview(SpanOverview):
    """View 类型 Span 的概览区。"""

    BADGES = [OVERVIEW_ELAPSED_TIME]
    ITEMS = [
        SpanTypeItem(),
        OVERVIEW_APP_NAME,
        OVERVIEW_ATTRIBUTES_VIEW_URL_TEMPLATE,
        OVERVIEW_ATTRIBUTES_VIEW_PREVIOUS_URL_TEMPLATE,
        OVERVIEW_ATTRIBUTES_SESSION_ID,
        OVERVIEW_ATTRIBUTES_VIEW_ID,
        OVERVIEW_START_TIME,
        OVERVIEW_END_TIME,
        OVERVIEW_ATTRIBUTES_USER_ID,
        OVERVIEW_RESOURCE_DEPLOYMENT_ENVIRONMENT_NAME,
    ]


@dataclass(frozen=True, slots=True)
class DisplayViewDurationKeyValueItem(KeyValueItem):
    key: str = "display.view.duration"

    def render(self, origin_data: dict[str, Any]) -> dict[str, Any]:
        return {
            "display.view.duration": 0,
        }


class ViewKeyInfoSection(BaseSection):
    """View 关键信息卡片：停留时长与加载生命周期字段。"""

    KEY = "key_info"
    TYPE = SectionType.SUMMARY_CARDS.value
    DATA = [
        DictItem(
            key="duration",
            items=[DisplayViewDurationKeyValueItem()],
        ),
        DictItem(
            key="loading",
            items=[
                KeyValueItem(key="attributes.view.loading_time"),
                KeyValueItem(key="attributes.view.loading_time_source"),
                KeyValueItem(key="attributes.view.loading_type"),
                KeyValueItem(key="attributes.view.first_byte"),
                KeyValueItem(key="attributes.view.dom_content_loaded"),
                KeyValueItem(key="attributes.view.load_event"),
            ],
        ),
    ]


@dataclass(frozen=True, slots=True)
class DisplayRatingConfigItem(KeyValueItem):
    """显示 Web Vitals 指标评分配置。"""

    key: str = "display.rating_config"

    def render(self, origin_data: dict[str, Any]) -> dict[str, Any]:
        if self.source is None:
            raise ValueError("source is required")
        return {
            "display.rating_config": RatingLevel.get_rating_config(self.source),
        }


class ViewWebVitalsSection(BaseSection):
    """Web Vitals 指标区：TTFB / FCP / LCP / INP / CLS 五项。"""

    KEY = "web_vitals"
    TYPE = SectionType.SUMMARY_CARDS.value
    DATA = [
        DictItem(
            key="ttfb",
            items=[
                KeyValueItem(key="attributes.vital.metric"),
                KeyValueItem(key="attributes.vital.value"),
                KeyValueItem(key="attributes.vital.ttfb.waiting_duration"),
                KeyValueItem(key="attributes.vital.ttfb.dns_duration"),
                KeyValueItem(key="attributes.vital.ttfb.connection_duration"),
                KeyValueItem(key="attributes.vital.ttfb.request_duration"),
                DisplayRatingConfigItem(source="ttfb"),
            ],
        ),
        DictItem(
            key="fcp",
            items=[
                KeyValueItem(key="attributes.vital.metric"),
                KeyValueItem(key="attributes.vital.value"),
                DisplayRatingConfigItem(source="fcp"),
            ],
        ),
        DictItem(
            key="lcp",
            items=[
                KeyValueItem(key="attributes.vital.metric"),
                KeyValueItem(key="attributes.vital.value"),
                DisplayRatingConfigItem(source="lcp"),
            ],
        ),
        DictItem(
            key="inp",
            items=[
                KeyValueItem(key="attributes.vital.metric"),
                KeyValueItem(key="attributes.vital.value"),
                DisplayRatingConfigItem(source="inp"),
            ],
        ),
        DictItem(
            key="cls",
            items=[
                KeyValueItem(key="attributes.vital.metric"),
                KeyValueItem(key="attributes.vital.value"),
                DisplayRatingConfigItem(source="cls"),
            ],
        ),
    ]


class ViewLoadingTimingSection(BaseSection):
    """View 加载时序瀑布区，含 TTFB 四段、View 三段以及 Vital 标记点。"""

    KEY = "loading_timing"
    TYPE = SectionType.WATERFALL.value

    PHASE_ALIASES = {
        "prepare": _("浏览器准备"),
        "dns": _("DNS 查询"),
        "connect": _("网络连接建立"),
        "first_byte": _("等待首字节"),
        "dom_processing": _("内容传输与 DOM 处理"),
        "resource_load": _("剩余资源加载"),
        "page_stable": _("页面趋于稳定"),
    }

    MARKER_FIELDS = ("TTFB", "FCP", "LCP")

    def _build_phases(self) -> list[dict[str, Any]]:
        prepare_duration = self.get_numeric_value("attributes.vital.ttfb.waiting_duration")
        vital_value = self.get_numeric_value("attributes.vital.value")
        first_byte_duration = self.get_numeric_value("attributes.vital.ttfb.request_duration")
        first_byte_start = vital_value - first_byte_duration
        connect_duration = self.get_numeric_value("attributes.vital.ttfb.connection_duration")
        connect_start = first_byte_start - connect_duration
        dns_duration = self.get_numeric_value("attributes.vital.ttfb.dns_duration")
        dns_start = connect_start - dns_duration
        dom_processing_start = self.get_numeric_value("attributes.view.first_byte")
        dom_processing_duration = self.get_numeric_value("attributes.view.dom_content_loaded") - dom_processing_start
        resource_load_start = self.get_numeric_value("attributes.view.dom_content_loaded")
        resource_load_duration = self.get_numeric_value("attributes.view.load_event") - resource_load_start
        page_stable_start = self.get_numeric_value("attributes.view.load_event")
        page_stable_duration = self.get_numeric_value("attributes.view.loading_time") - page_stable_start

        return [
            {"key": "prepare", "alias": self.PHASE_ALIASES["prepare"], "start": 0, "duration": prepare_duration},
            {"key": "dns", "alias": self.PHASE_ALIASES["dns"], "start": dns_start, "duration": dns_duration},
            {
                "key": "connect",
                "alias": self.PHASE_ALIASES["connect"],
                "start": connect_start,
                "duration": connect_duration,
            },
            {
                "key": "first_byte",
                "alias": self.PHASE_ALIASES["first_byte"],
                "start": first_byte_start,
                "duration": first_byte_duration,
            },
            {
                "key": "dom_processing",
                "alias": self.PHASE_ALIASES["dom_processing"],
                "start": dom_processing_start,
                "duration": dom_processing_duration,
            },
            {
                "key": "resource_load",
                "alias": self.PHASE_ALIASES["resource_load"],
                "start": resource_load_start,
                "duration": resource_load_duration,
            },
            {
                "key": "page_stable",
                "alias": self.PHASE_ALIASES["page_stable"],
                "start": page_stable_start,
                "duration": page_stable_duration,
            },
        ]

    def _build_markers(self) -> list[dict[str, Any]]:
        markers: list[dict[str, Any]] = []
        for name in self.MARKER_FIELDS:
            snapshot = self.origin_data.get(VITAL_METRIC_KEYS[name.lower()]) or {}
            if "attributes.vital.value" not in snapshot:
                continue
            markers.append(
                {
                    "key": name,
                    "field_name": name,
                    "value": get_safe_number(snapshot.get("attributes.vital.value")),
                }
            )
        return markers

    def _fill_data(self):
        self.component_dict["data"] = {
            "unit": FieldUnit.MS.value,
            "total_duration": self.get_numeric_value("attributes.view.loading_time"),
            "phases": self._build_phases(),
            "markers": self._build_markers(),
        }


class ViewSpanBuilder(SpanBuilder):
    """View 类型 Span 详情 Builder。

    通过 :meth:`_prepare_origin_data` 将 ``related_spans`` 中的最新 View 快照与
    每个 Web Vitals 指标的最新记录注入到打平后的原始数据中，供各 Section 渲染。
    ``origin_data`` 和 ``span_id`` 始终保留主记录。
    """

    OVERVIEW = ViewSpanOverview
    SECTIONS = [
        ViewKeyInfoSection,
        ViewWebVitalsSection,
        ViewLoadingTimingSection,
    ]

    @classmethod
    def _prepare_origin_data(
        cls,
        span: dict[str, Any],
        related_spans: Sequence[dict[str, Any]] = (),
    ) -> dict[str, Any]:
        origin_data = flatten_dict_data(span)
        latest_view = cls._latest_view_snapshot(related_spans)
        if latest_view:
            # 用最新 View 快照覆盖头部时间及加载字段，主记录仍保留在响应的 origin_data。
            origin_data.update(latest_view)
        for metric, key in VITAL_METRIC_KEYS.items():
            snapshot = cls._latest_vital_snapshot(related_spans, metric)
            if snapshot:
                origin_data[key] = snapshot
        return origin_data

    @staticmethod
    def _latest_view_snapshot(related_spans: Sequence[dict[str, Any]]) -> dict[str, Any] | None:
        """从关联记录中挑选最新 View 快照：按 ``attributes.view.version`` 降序取首条。"""
        candidates = [
            flatten_dict_data(item)
            for item in related_spans
            if flatten_dict_data(item).get("attributes.span_type") == RumSpanType.VIEW.value
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda item: get_safe_number(item.get("attributes.view.version")), reverse=True)
        return candidates[0]

    @staticmethod
    def _latest_vital_snapshot(
        related_spans: Sequence[dict[str, Any]],
        metric: str,
    ) -> dict[str, Any] | None:
        """从关联记录中挑选指定 Vital 指标的最新快照：按 ``end_time`` 降序取首条。"""
        candidates = []
        for item in related_spans:
            flat = flatten_dict_data(item)
            if flat.get("attributes.span_type") != RumSpanType.VITAL.value:
                continue
            if str(flat.get("attributes.vital.metric", "")).lower() != metric:
                continue
            candidates.append(flat)
        if not candidates:
            return None
        candidates.sort(key=lambda item: get_safe_number(item.get("end_time")), reverse=True)
        return candidates[0]
