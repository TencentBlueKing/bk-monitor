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
from rum_web.handlers.builder.hover import (
    VIEW_NAVIGATION_PHASE_HOVERS,
    VIEW_PHASE_HOVERS,
    clone_hover,
    get_milestone_hover,
    get_vital_hover,
)
from rum_web.handlers.builder.span.base import (
    RatingConfigItem,
    SpanBuilder,
    SpanOverview,
    VitalHoverItem,
    insert_after,
    named,
)
from rum_web.handlers.builder.span.timing.view import ViewTimingLayout
from rum_web.handlers.builder.utils import build_rating_config, get_safe_number, phase, safe_diff, waterfall


VITAL_METRICS = ("ttfb", "fcp", "lcp", "inp", "cls")
MARKER_METRICS = VITAL_METRICS[:3]
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
    ITEMS = insert_after(
        SpanOverview.ITEMS, "attributes.view.url_template", *named("attributes.view.previous_url_template")
    )


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

    def render(self) -> dict[str, Any] | None:
        if (
            self.flatten_data.get("attributes.view.first_byte") is None
            and ViewTimingLayout(self.flatten_data).matches()
        ):
            return ViewNavigationKeyInfoSection(self.flatten_data).render()
        return super().render()


class ViewNavigationKeyInfoSection(KeyInfoSection):
    DATA = (
        group("duration", "display.view.duration"),
        group(
            "loading",
            "attributes.view.loading_time",
            "attributes.view.loading_time_source",
            "attributes.view.loading_type",
            KeyValueItem("attributes.view.first_byte", source="attributes.timing.response_start"),
            KeyValueItem("attributes.view.dom_content_loaded", source="attributes.timing.dom_content_loaded_event_end"),
            KeyValueItem("attributes.view.load_event", source="attributes.timing.load_event_end"),
        ),
    )


def vital_group(metric: str) -> DictItem:
    fields = ("attributes.vital.metric", "attributes.vital.value")
    return DictItem(
        metric,
        (
            *(KeyValueItem(field, source=vital_key(metric, field)) for field in fields),
            VitalHoverItem(metric=metric),
            RatingConfigItem(metric=metric),
        ),
    )


class ViewWebVitalsSection(BaseSection):
    KEY = "web_vitals"
    TYPE = SectionType.SUMMARY_CARDS.value
    DATA = tuple(vital_group(metric) for metric in VITAL_METRICS)


class ViewLoadingTimingSection(WaterfallSection):
    KEY = "loading_timing"
    PHASE_HOVERS = VIEW_NAVIGATION_PHASE_HOVERS
    PHASE_ALIASES = {
        "redirect": _("重定向"),
        "prepare": _("发起前等待"),
        "dns": _("DNS 查询"),
        "connect": _("建立连接"),
        "tls": _("TLS 建连"),
        "first_byte": _("等待首字节"),
        "download": _("内容传输"),
        "dom_parsing": _("DOM 解析"),
        "resource_load": _("资源加载"),
        "page_stable": _("页面趋于稳定"),
    }

    def get_data(self) -> dict[str, Any] | None:
        if self.flatten_data.get("attributes.view.loading_type") != ViewLoadingType.INITIAL_LOAD.value:
            return None

        layout = ViewTimingLayout(self.flatten_data)
        if not layout.matches():
            return self._legacy_waterfall()
        specs = [spec for spec in layout.phases() if spec is not None]
        if not specs:
            return self._legacy_waterfall()

        stable_end = layout.stable_end()
        stable_field = "attributes.view.loading_time"
        loading_time = self.numeric_or_none(stable_field)
        if stable_end is not None and stable_end != loading_time:
            stable_field = "attributes.timing.load_event_end"
        return waterfall(
            self.phases(specs),
            total=loading_time if loading_time is not None and loading_time >= 0 else None,
            markers=self._build_markers(),
            milestones=self._build_milestones(stable_field, stable_end),
        )

    def _legacy_waterfall(self) -> dict[str, Any] | None:
        """用旧 SDK 的 View 和 TTFB 字段构建瀑布图。"""
        aliases = {
            "prepare": _("浏览器准备"),
            "dns": _("DNS 查询"),
            "connect": _("网络连接建立"),
            "first_byte": _("等待首字节"),
            "dom_processing": _("内容传输与 DOM 处理"),
            "resource_load": _("剩余资源加载"),
            "page_stable": _("页面趋于稳定"),
        }

        def ttfb(field: str) -> int | float | None:
            return self.numeric_or_none(vital_key("ttfb", f"attributes.vital.{field}"))

        specs: list[tuple[str, int | float | None, int | float | None]] = [
            ("prepare", 0, ttfb("ttfb.waiting_duration"))
        ]
        end = ttfb("value")
        # TTFB 各段从首字节时间逆推，输出仍按 prepare → dns → connect → first_byte 排序。
        for key, segment in (("first_byte", "request"), ("connect", "connection"), ("dns", "dns")):
            duration = ttfb(f"ttfb.{segment}_duration")
            end = safe_diff(end, duration)
            specs.insert(1, (key, end, duration))

        first_byte = self.numeric_or_none("attributes.view.first_byte")
        dom_loaded = self.numeric_or_none("attributes.view.dom_content_loaded")
        load_event = self.numeric_or_none("attributes.view.load_event")
        loading_time = self.numeric_or_none("attributes.view.loading_time")
        is_auto = self.flatten_data.get("attributes.view.loading_time_source") == ViewLoadingTimeSource.AUTO.value
        specs.extend(
            (
                ("dom_processing", first_byte, safe_diff(dom_loaded, first_byte)),
                ("resource_load", dom_loaded, safe_diff(load_event, dom_loaded)),
            )
        )
        if is_auto:
            duration = safe_diff(loading_time, load_event)
            # 自动计时可能有浮点负差，稳定阶段保留零时长。
            specs.append(("page_stable", load_event, max(0, duration) if duration is not None else None))
        phases = (
            phase(key, aliases[key], start, duration, min_start=0, hover=clone_hover(VIEW_PHASE_HOVERS.get(key)))
            for key, start, duration in specs
        )
        total = loading_time if loading_time is not None and loading_time >= 0 else None
        data = waterfall(phases, total=total, markers=self._build_markers())
        if data is not None:
            data["milestones"] = self._build_milestones(
                "attributes.view.loading_time", loading_time if is_auto else None
            )
        return data

    def _build_markers(self) -> list[dict[str, Any]]:
        markers: list[dict[str, Any]] = []
        for metric in MARKER_METRICS:
            value = self.numeric_or_none(vital_key(metric, "attributes.vital.value"))
            if value is None:
                continue
            marker: dict[str, Any] = {
                "key": metric.upper(),
                "field_name": metric.upper(),
                "value": value,
                "display.rating_config": build_rating_config(metric),
            }
            if (hover := get_vital_hover(metric)) is not None:
                marker["hover"] = hover
            markers.append(marker)
        return markers

    def _build_milestones(self, stable_field: str, stable_end: int | float | None) -> list[dict[str, Any]]:
        def point(timing_field: str, fallback_field: str) -> tuple[str, int | float | None]:
            value = self.numeric_or_none(timing_field)
            if value is not None and value > 0:
                return timing_field, value
            return fallback_field, self.numeric_or_none(fallback_field)

        points = (
            ("dom_complete", *point("attributes.timing.dom_complete", "attributes.view.dom_complete")),
            ("load_event", *point("attributes.timing.load_event_end", "attributes.view.load_event")),
            ("page_stable", stable_field, stable_end),
        )
        milestones: list[dict[str, Any]] = []
        for key, field, value in points:
            if value is None:
                continue
            milestone: dict[str, Any] = {"key": key, "field_name": field, "value": value}
            if (hover := get_milestone_hover(key)) is not None:
                milestone["hover"] = hover
            milestones.append(milestone)
        return milestones


class ViewSpanBuilder(SpanBuilder):
    RECORD_ID_FIELD = "attributes.view.id"
    RELATED_SPAN_TYPES = (RumSpanType.VIEW.value, RumSpanType.VITAL.value)
    OVERVIEW = ViewSpanOverview
    SECTIONS = (ViewKeyInfoSection, ViewWebVitalsSection, ViewLoadingTimingSection)

    @classmethod
    def _prepare_flatten_data(
        cls, span: dict[str, Any], related_spans: Sequence[dict[str, Any]] = ()
    ) -> dict[str, Any]:
        flatten_data = flatten_dict_data(span)
        flat_related = [flatten_dict_data(item) for item in related_spans]
        views = [item for item in flat_related if item.get("attributes.span_type") == RumSpanType.VIEW.value]
        views.append(flatten_data)
        views.sort(key=lambda item: get_safe_number(item.get("attributes.view.version")), reverse=True)
        latest_view = views[0]
        # 导航时间点随 View 生命周期补报，按版本覆盖已上报的字段。
        flatten_data.update(
            {
                field: value
                for snapshot in reversed(views)
                for field, value in snapshot.items()
                if field.startswith(ViewTimingLayout.TIMING_PREFIX) or field == "attributes.view.dom_interactive"
            }
        )
        flatten_data.update({field: latest_view[field] for field in VIEW_SNAPSHOT_FIELDS if field in latest_view})
        # 瞬时 View 的根级 start_time 是上报时刻，优先使用最新快照的导航开始时间（ms）。
        started_at = _finite(latest_view.get("attributes.view.started_at")) or _finite(
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
