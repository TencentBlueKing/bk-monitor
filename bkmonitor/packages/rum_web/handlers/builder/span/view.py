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
from semconv.rum.constants import RumSpanType, ViewLoadingTimeSource, ViewLoadingType

from rum_web.handlers.builder.base import (
    BaseSection,
    DictItem,
    KeyValueItem,
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
    SpanBuilder,
    SpanOverview,
    SpanTypeItem,
)
from rum_web.handlers.builder.utils import get_safe_number


#: Web Vitals 五项指标，作为 :class:`ViewWebVitalsSection` 与 Marker 构造的单一事实源。
VITAL_METRICS: tuple[str, ...] = ("ttfb", "fcp", "lcp", "inp", "cls")

#: 每个 Web Vitals 指标在 flatten_data 中挂载的嵌套字典键，
#: 由 :meth:`ViewSpanBuilder._prepare_flatten_data` 用同 View ID 且 span_type=vital 的最新快照填充。
VITAL_METRIC_KEYS: dict[str, str] = {metric: f"display.vitals.{metric}" for metric in VITAL_METRICS}

#: View 快照从关联记录补齐的展示字段：头部时间（end_time / elapsed_time）与加载字段（attributes.view.*）。
#: ``start_time`` 取导航开始时间，不随快照更新，故不在此列。
VIEW_SNAPSHOT_FIELDS: tuple[str, ...] = (
    "end_time",
    "elapsed_time",
    "attributes.view.loading_time",
    "attributes.view.loading_time_source",
    "attributes.view.loading_type",
    "attributes.view.first_byte",
    "attributes.view.dom_content_loaded",
    "attributes.view.load_event",
)


def build_vital_source_key(metric: str, sub: str) -> str:
    """拼接 Vital 快照在展平 ``flatten_data`` 中的完整键。

    :meth:`ViewSpanBuilder._prepare_flatten_data` 将快照挂到 ``display.vitals.{metric}``，
    最终展平后子字段变为 ``display.vitals.{metric}.attributes.vital.*``，故此处需带前缀读取。
    """
    return f"{VITAL_METRIC_KEYS[metric.lower()]}.{sub}"


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
class DisplayViewDurationItem(KeyValueItem):
    """View 停留时长：由最新 View 快照的 end_time - start_time 换算为毫秒。"""

    key: str = "display.view.duration"

    def render(self, flatten_data: dict[str, Any]) -> dict[str, Any]:
        # start_time / end_time 为微秒级，相减后除以 1000 换算为毫秒。
        start_time = get_safe_number(flatten_data.get("start_time"), None)
        end_time = get_safe_number(flatten_data.get("end_time"), None)
        if start_time is None or end_time is None:
            return {self.key: 0}
        return {self.key: (end_time - start_time) / 1000}


@dataclass(frozen=True, slots=True)
class DisplayRatingConfigItem(KeyValueItem):
    """Web Vitals 指标评分阈值配置：``source`` 指明指标名（ttfb / fcp / ...）。"""

    key: str = "display.rating_config"

    def render(self, flatten_data: dict[str, Any]) -> dict[str, Any]:
        if self.source is None:
            raise ValueError("source is required")
        return {self.key: RatingLevel.get_rating_config(self.source)}


class ViewKeyInfoSection(BaseSection):
    """View 关键信息卡片：停留时长与加载生命周期字段。"""

    KEY = "key_info"
    TYPE = SectionType.SUMMARY_CARDS.value
    DATA = [
        DictItem(
            key="duration",
            items=[DisplayViewDurationItem()],
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


class ViewWebVitalsSection(BaseSection):
    """Web Vitals 指标区：TTFB / FCP / LCP / INP / CLS 五项。

    TTFB 额外包含 ``waiting`` / ``dns`` / ``connection`` / ``request`` 四段耗时；
    其他四项仅暴露主 ``value`` 与评分阈值配置。
    """

    KEY = "web_vitals"
    TYPE = SectionType.SUMMARY_CARDS.value
    DATA = [
        DictItem(
            key="ttfb",
            items=[
                KeyValueItem(
                    key="attributes.vital.metric", source=build_vital_source_key("ttfb", "attributes.vital.metric")
                ),
                KeyValueItem(
                    key="attributes.vital.value", source=build_vital_source_key("ttfb", "attributes.vital.value")
                ),
                KeyValueItem(
                    key="attributes.vital.ttfb.waiting_duration",
                    source=build_vital_source_key("ttfb", "attributes.vital.ttfb.waiting_duration"),
                ),
                KeyValueItem(
                    key="attributes.vital.ttfb.dns_duration",
                    source=build_vital_source_key("ttfb", "attributes.vital.ttfb.dns_duration"),
                ),
                KeyValueItem(
                    key="attributes.vital.ttfb.connection_duration",
                    source=build_vital_source_key("ttfb", "attributes.vital.ttfb.connection_duration"),
                ),
                KeyValueItem(
                    key="attributes.vital.ttfb.request_duration",
                    source=build_vital_source_key("ttfb", "attributes.vital.ttfb.request_duration"),
                ),
                DisplayRatingConfigItem(source="ttfb"),
            ],
        ),
        DictItem(
            key="fcp",
            items=[
                KeyValueItem(
                    key="attributes.vital.metric", source=build_vital_source_key("fcp", "attributes.vital.metric")
                ),
                KeyValueItem(
                    key="attributes.vital.value", source=build_vital_source_key("fcp", "attributes.vital.value")
                ),
                DisplayRatingConfigItem(source="fcp"),
            ],
        ),
        DictItem(
            key="lcp",
            items=[
                KeyValueItem(
                    key="attributes.vital.metric", source=build_vital_source_key("lcp", "attributes.vital.metric")
                ),
                KeyValueItem(
                    key="attributes.vital.value", source=build_vital_source_key("lcp", "attributes.vital.value")
                ),
                DisplayRatingConfigItem(source="lcp"),
            ],
        ),
        DictItem(
            key="inp",
            items=[
                KeyValueItem(
                    key="attributes.vital.metric", source=build_vital_source_key("inp", "attributes.vital.metric")
                ),
                KeyValueItem(
                    key="attributes.vital.value", source=build_vital_source_key("inp", "attributes.vital.value")
                ),
                DisplayRatingConfigItem(source="inp"),
            ],
        ),
        DictItem(
            key="cls",
            items=[
                KeyValueItem(
                    key="attributes.vital.metric", source=build_vital_source_key("cls", "attributes.vital.metric")
                ),
                KeyValueItem(
                    key="attributes.vital.value", source=build_vital_source_key("cls", "attributes.vital.value")
                ),
                DisplayRatingConfigItem(source="cls"),
            ],
        ),
    ]


class ViewLoadingTimingSection(BaseSection):
    """View 加载时序瀑布：按「字段缺失 → 不出段」组装，避免伪造全零瀑布。

    - TTFB 四段（prepare / dns / connect / first_byte）依赖同 View 的 Vital 快照，
      快照缺失时对应段整段不输出。
    - View 三段（dom_processing / resource_load / page_stable）依赖 ``attributes.view.*`` 字段，
      任意起终点缺失或时长为负则整段省略。
    - ``markers`` 从注入到 flatten_data 的 vital 快照中派生，缺失自动跳过。
    """

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

    MARKER_FIELDS: tuple[str, ...] = ("TTFB", "FCP", "LCP")

    def _phase(
        self,
        key: str,
        start: int | float | None,
        duration: int | float | None,
    ) -> dict[str, Any] | None:
        """构造单个 phase；起点或时长缺失、起点为负或时长为负则整段不输出。"""
        if start is None or duration is None or start < 0 or duration < 0:
            return None
        return {
            "key": key,
            "alias": self.PHASE_ALIASES[key],
            "start": start,
            "duration": duration,
        }

    @classmethod
    def _diff(cls, minuend: int | float | None, subtrahend: int | float | None) -> int | float | None:
        """空安全减法：任一操作数缺失直接返回 ``None``，避免 ``None - int`` 抛错。"""
        if minuend is None or subtrahend is None:
            return None
        return minuend - subtrahend

    def _build_phases(self) -> list[dict[str, Any]]:
        # ── TTFB 四段：全部来自 vital 快照，快照缺失时四段均不出段 ──
        prepare_duration = self.numeric_or_none(
            build_vital_source_key("ttfb", "attributes.vital.ttfb.waiting_duration")
        )
        vital_value = self.numeric_or_none(build_vital_source_key("ttfb", "attributes.vital.value"))

        first_byte_duration = self.numeric_or_none(
            build_vital_source_key("ttfb", "attributes.vital.ttfb.request_duration")
        )
        first_byte_start = self._diff(vital_value, first_byte_duration)

        connect_duration = self.numeric_or_none(
            build_vital_source_key("ttfb", "attributes.vital.ttfb.connection_duration")
        )
        connect_start = self._diff(first_byte_start, connect_duration)

        dns_duration = self.numeric_or_none(build_vital_source_key("ttfb", "attributes.vital.ttfb.dns_duration"))
        dns_start = self._diff(connect_start, dns_duration)

        # ── View 三段：起终点均需存在，duration 收敛非负 ──
        dom_processing_start = self.numeric_or_none("attributes.view.first_byte")
        resource_load_start = self.numeric_or_none("attributes.view.dom_content_loaded")
        dom_processing_duration = self._diff(resource_load_start, dom_processing_start)
        page_stable_start = self.numeric_or_none("attributes.view.load_event")
        resource_load_duration = self._diff(page_stable_start, resource_load_start)
        loading_time = self.numeric_or_none("attributes.view.loading_time")
        page_stable_duration = self._diff(loading_time, page_stable_start)

        phases_candidates = [
            self._phase("prepare", 0, prepare_duration),
            self._phase("dns", dns_start, dns_duration),
            self._phase("connect", connect_start, connect_duration),
            self._phase("first_byte", first_byte_start, first_byte_duration),
            self._phase("dom_processing", dom_processing_start, dom_processing_duration),
            self._phase("resource_load", resource_load_start, resource_load_duration),
        ]
        if self.flatten_data.get("attributes.view.loading_time_source") == ViewLoadingTimeSource.AUTO.value:
            phases_candidates.append(self._phase("page_stable", page_stable_start, page_stable_duration))
        return [p for p in phases_candidates if p is not None]

    def _build_markers(self) -> list[dict[str, Any]]:
        markers: list[dict[str, Any]] = []
        for name in self.MARKER_FIELDS:
            metric = name.lower()
            value = get_safe_number(
                self.flatten_data.get(build_vital_source_key(metric, "attributes.vital.value")), None
            )
            if value is None:
                continue
            markers.append(
                {
                    "key": name,
                    "field_name": name,
                    "value": value,
                    "display.rating_config": RatingLevel.get_rating_config(metric),
                }
            )
        return markers

    def _fill_data(self):
        # 非首次加载没有导航时间原点，不产生 TTFB / FCP / LCP，整段加载时序省略。
        if self.flatten_data.get("attributes.view.loading_type") != ViewLoadingType.INITIAL_LOAD.value:
            return

        phases = self._build_phases()
        markers = self._build_markers()

        # 整段时序都拿不到（既无 phase 又无 marker）时省略 ``data``，
        # 前端可据此区分「没有时序数据」与「耗时为 0」。
        if not phases and not markers:
            return

        # 横轴基准：有效 loading_time；缺失或非法（负）时省略（None），有效零值保留 0。
        loading_time = self.numeric_or_none("attributes.view.loading_time")
        data = {
            "unit": FieldUnit.MS.value,
            "phases": phases,
            "markers": markers,
        }
        # total_duration 等于有效的 view.loading_time；缺失或非法（负）时省略该键，不伪造 0。
        # 标记超出总耗时仅扩展横轴，不修改各 phase。
        if loading_time is not None and loading_time >= 0:
            total_duration = loading_time
            if markers:
                total_duration = max(total_duration, max(m["value"] for m in markers))
            data["total_duration"] = total_duration
        self.component_dict["data"] = data


class ViewSpanBuilder(SpanBuilder):
    """View 类型 Span 详情 Builder。

    通过 :meth:`_prepare_flatten_data` 将 ``related_spans`` 中的最新 View 快照与
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
    def _prepare_flatten_data(
        cls,
        span: dict[str, Any],
        related_spans: Sequence[dict[str, Any]] = (),
    ) -> dict[str, Any]:
        flatten_data = flatten_dict_data(span)
        latest_view = cls._latest_view_snapshot(related_spans)
        if latest_view:
            # 用最新 View 快照覆盖头部时间及加载字段，主记录仍保留在响应的 origin_data。
            # start_time 取导航开始时间，不随快照更新，故只补齐 VIEW_SNAPSHOT_FIELDS 内的字段。
            flatten_data.update({field: latest_view[field] for field in VIEW_SNAPSHOT_FIELDS if field in latest_view})
        vital_map = cls._build_vital_map(related_spans)
        for metric, key in VITAL_METRIC_KEYS.items():
            snapshot = vital_map.get(metric)
            if snapshot:
                flatten_data[key] = {k: v for k, v in snapshot.items() if k.startswith("attributes.vital")}
        return flatten_dict_data(flatten_data)

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
    def _build_vital_map(related_spans: Sequence[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """一次性构建各 Web Vitals 指标的最新快照表：``{metric: latest_snapshot}``。

        仅遍历并打平 ``related_spans`` 一次，按小写 ``attributes.vital.metric`` 分组，
        对同组记录以比较替换方式保留 ``end_time`` 最大者，避免逐个指标重复排序。
        """
        vital_map: dict[str, dict[str, Any]] = {}
        for item in related_spans:
            flat = flatten_dict_data(item)
            if flat.get("attributes.span_type") != RumSpanType.VITAL.value:
                continue
            metric = str(flat.get("attributes.vital.metric", "")).lower()
            if not metric:
                continue
            prev = vital_map.get(metric)
            if prev is None or get_safe_number(flat.get("end_time")) > get_safe_number(prev.get("end_time")):
                vital_map[metric] = flat
        return vital_map
