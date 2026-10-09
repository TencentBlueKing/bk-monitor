"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import math
from collections.abc import Sequence
from typing import Any

from django.utils.translation import gettext_lazy as _

from bkmonitor.data_source.format import flatten_dict_data
from semconv.rum.constants import RumSpanType, ViewLoadingTimeSource, ViewLoadingType
from rum_web.handlers.builder.base import BaseSection, DictItem, KeyInfoSection, KeyValueItem, WaterfallSection, group
from rum_web.handlers.builder.constants import SectionType
from rum_web.handlers.builder.span.base import RatingConfigItem, SpanBuilder, SpanOverview, named
from rum_web.handlers.builder.utils import build_rating_config, get_safe_number, safe_diff, waterfall


VITAL_METRICS = ("ttfb", "fcp", "lcp", "inp", "cls")
MARKER_METRICS = VITAL_METRICS[:3]
TTFB_SEGMENTS = tuple(
    f"attributes.vital.ttfb.{segment}_duration" for segment in ("waiting", "dns", "connection", "request")
)
VIEW_SNAPSHOT_FIELDS = (
    "end_time",
    "elapsed_time",
    "attributes.view.loading_time",
    "attributes.view.loading_time_source",
    "attributes.view.loading_type",
    "attributes.view.first_byte",
    "attributes.view.dom_content_loaded",
    "attributes.view.load_event",
    "attributes.view.dom_complete",
)


def vital_key(metric: str, field: str) -> str:
    return f"display.vitals.{metric}.{field}"


def _finite(value: Any) -> int | float | None:
    number = get_safe_number(value, None)
    return number if number is not None and math.isfinite(number) else None


class ViewSpanOverview(SpanOverview):
    BADGES = named("display.view.duration")
    ITEMS = (*SpanOverview.ITEMS[:3], *named("attributes.view.previous_url_template"), *SpanOverview.ITEMS[3:])


class ViewKeyInfoSection(KeyInfoSection):
    DATA = (
        group("duration", "display.view.duration"),
        group(
            "loading",
            "attributes.view.loading_time",
            "attributes.view.loading_time_source",
            "attributes.view.loading_type",
            "attributes.view.first_byte",
            "attributes.view.dom_content_loaded",
            "attributes.view.load_event",
        ),
    )


def vital_group(metric: str, extra: tuple[str, ...] = ()) -> DictItem:
    fields = ("attributes.vital.metric", "attributes.vital.value", *extra)
    return DictItem(
        metric,
        (*(KeyValueItem(field, source=vital_key(metric, field)) for field in fields), RatingConfigItem(metric=metric)),
    )


class ViewWebVitalsSection(BaseSection):
    KEY = "web_vitals"
    TYPE = SectionType.SUMMARY_CARDS.value
    DATA = (vital_group("ttfb", TTFB_SEGMENTS), *(vital_group(metric) for metric in VITAL_METRICS[1:]))


class ViewLoadingTimingSection(WaterfallSection):
    KEY = "loading_timing"
    MIN_START = 0
    PHASE_ALIASES = {
        "prepare": _("浏览器准备"),
        "dns": _("DNS 查询"),
        "connect": _("网络连接建立"),
        "first_byte": _("等待首字节"),
        "dom_processing": _("内容传输与 DOM 处理"),
        "resource_load": _("剩余资源加载"),
        "page_stable": _("页面趋于稳定"),
    }
    TTFB_PHASES = (("first_byte", "request"), ("connect", "connection"), ("dns", "dns"))
    VIEW_PHASES = ("dom_processing", "resource_load", "page_stable")
    VIEW_POINTS = ("first_byte", "dom_content_loaded", "load_event", "loading_time")
    MILESTONES = (
        ("dom_complete", "attributes.view.dom_complete"),
        ("load_event", "attributes.view.load_event"),
        ("page_stable", "attributes.view.loading_time"),
    )

    def _build_phases(self, is_auto: bool) -> list[dict[str, Any] | None]:
        def ttfb(field: str) -> int | float | None:
            return self.numeric_or_none(vital_key("ttfb", f"attributes.vital.{field}"))

        specs: list[tuple[str, int | float | None, int | float | None]] = [
            ("prepare", 0, ttfb("ttfb.waiting_duration"))
        ]
        end = ttfb("value")
        # TTFB 各段从首字节时间逆推，输出仍按 prepare → dns → connect → first_byte 排序。
        for key, segment in self.TTFB_PHASES:
            duration = ttfb(f"ttfb.{segment}_duration")
            end = safe_diff(end, duration)
            specs.insert(1, (key, end, duration))
        points = [self.numeric_or_none(f"attributes.view.{point}") for point in self.VIEW_POINTS]
        for key, start, stop in zip(self.VIEW_PHASES, points, points[1:]):
            duration = safe_diff(stop, start)
            if key == "page_stable":
                if not is_auto:
                    continue
                # 自动计时可能有浮点负差，稳定阶段保留零时长。
                duration = None if duration is None else max(0, duration)
            specs.append((key, start, duration))
        return self.phases(specs)

    def _build_markers(self) -> list[dict[str, Any]]:
        return [
            {
                "key": metric.upper(),
                "field_name": metric.upper(),
                "value": value,
                "display.rating_config": build_rating_config(metric),
            }
            for metric in MARKER_METRICS
            if (value := self.numeric_or_none(vital_key(metric, "attributes.vital.value"))) is not None
        ]

    def _build_milestones(self, is_auto: bool) -> list[dict[str, Any]]:
        return [
            {"key": key, "field_name": field, "value": value}
            for key, field in self.MILESTONES
            if (value := self.numeric_or_none(field)) is not None and (key != "page_stable" or is_auto)
        ]

    def get_data(self) -> dict[str, Any] | None:
        if self.flatten_data.get("attributes.view.loading_type") != ViewLoadingType.INITIAL_LOAD.value:
            return None
        is_auto = self.flatten_data.get("attributes.view.loading_time_source") == ViewLoadingTimeSource.AUTO.value
        loading_time = self.numeric_or_none("attributes.view.loading_time")
        total = loading_time if loading_time is not None and loading_time >= 0 else None
        # total_duration 只取 loading_time，标记超出时由前端扩展横轴。
        data = waterfall(self._build_phases(is_auto), total=total, markers=self._build_markers())
        if data is not None:
            data["milestones"] = self._build_milestones(is_auto)
        return data


class ViewSpanBuilder(SpanBuilder):
    OVERVIEW = ViewSpanOverview
    SECTIONS = (ViewKeyInfoSection, ViewWebVitalsSection, ViewLoadingTimingSection)

    @classmethod
    def _prepare_flatten_data(
        cls, span: dict[str, Any], related_spans: Sequence[dict[str, Any]] = ()
    ) -> dict[str, Any]:
        flatten_data = flatten_dict_data(span)
        flat_related = [flatten_dict_data(item) for item in related_spans]
        views = [item for item in flat_related if item.get("attributes.span_type") == RumSpanType.VIEW.value]
        latest_view = max(
            views,
            key=lambda item: get_safe_number(item.get("attributes.view.version")) or 0,
            default=None,
        )
        if latest_view:
            flatten_data.update({field: latest_view[field] for field in VIEW_SNAPSHOT_FIELDS if field in latest_view})
        # 瞬时 View 的根级 start_time 是上报时刻，优先使用最新快照的导航开始时间（ms）。
        started_at = _finite((latest_view or {}).get("attributes.view.started_at")) or _finite(
            flatten_data.get("attributes.view.started_at")
        )
        if started_at is not None:
            flatten_data["start_time"] = int(started_at * 1000)
        duration = safe_diff(
            get_safe_number(flatten_data.get("end_time"), None), get_safe_number(flatten_data.get("start_time"), None)
        )
        flatten_data["display.view.duration"] = None if duration is None else duration / 1000
        vital_map = cls._build_vital_map(flat_related)
        for metric, snapshot in vital_map.items():
            flatten_data.update(
                {vital_key(metric, key): value for key, value in snapshot.items() if key.startswith("attributes.vital")}
            )
        return flatten_data

    @staticmethod
    def _build_vital_map(flat_related: Sequence[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        vital_map: dict[str, dict[str, Any]] = {}
        for item in flat_related:
            if item.get("attributes.span_type") != RumSpanType.VITAL.value:
                continue
            metric = str(item.get("attributes.vital.metric", "")).lower()
            if metric not in VITAL_METRICS:
                continue
            previous = vital_map.get(metric)
            if previous is None or (get_safe_number(item.get("end_time")) or 0) > (
                get_safe_number(previous.get("end_time")) or 0
            ):
                vital_map[metric] = item
        return vital_map
