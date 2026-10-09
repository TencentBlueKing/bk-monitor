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
from semconv.rum.constants import RumSpanType, ViewLoadingTimeSource, ViewLoadingType

from rum_web.handlers.builder.base import (
    BaseSection,
    DictItem,
    EMPTY_VALUE,
    KeyValueItem,
    NamedKeyValueItem,
)
from rum_web.handlers.builder.constants import SectionType
from rum_web.handlers.builder.span.base import (
    RatingConfigItem,
    SpanBuilder,
    SpanOverview,
    SpanTypeItem,
    named,
)
from rum_web.handlers.builder.utils import build_rating_config, get_safe_number, phase, safe_diff, waterfall


#: Web Vitals 五项指标，用于生成指标卡片与快照挂载键；时序标记由 MARKER_FIELDS 单独声明。
VITAL_METRICS: tuple[str, ...] = ("ttfb", "fcp", "lcp", "inp", "cls")

#: 每个 Web Vitals 指标在 flatten_data 中挂载的嵌套字典键，
#: 由 :meth:`ViewSpanBuilder._prepare_flatten_data` 用同 View ID 且 span_type=vital 的最新快照填充。
VITAL_METRIC_KEYS: dict[str, str] = {metric: f"display.vitals.{metric}" for metric in VITAL_METRICS}

#: TTFB 指标卡片额外展示的四段耗时字段。
TTFB_SEGMENTS: tuple[str, ...] = tuple(
    f"attributes.vital.ttfb.{segment}_duration" for segment in ("waiting", "dns", "connection", "request")
)

#: View 快照从关联记录补齐的展示字段：头部时间（end_time / elapsed_time）与加载字段（attributes.view.*）。
#: ``start_time`` 不在此列；另从最新快照或主记录的 ``attributes.view.started_at`` 回填。
VIEW_SNAPSHOT_FIELDS: tuple[str, ...] = (
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


def build_vital_source_key(metric: str, sub: str) -> str:
    """拼接 Vital 快照在展平 ``flatten_data`` 中的完整键。

    :meth:`ViewSpanBuilder._prepare_flatten_data` 将快照挂到 ``display.vitals.{metric}``，
    最终展平后子字段变为 ``display.vitals.{metric}.attributes.vital.*``，故此处需带前缀读取。
    """
    return f"{VITAL_METRIC_KEYS[metric.lower()]}.{sub}"


def _compute_view_duration_ms(flatten_data: dict[str, Any]) -> float | None:
    """计算 View 停留时长（毫秒）：由准备后的 ``end_time - start_time`` 换算而来。

    - ``start_time`` / ``end_time`` 单位为微秒，相减后除以 1000 换算为毫秒。
    - 准备后的任一时间字段缺失或无法转换为数值时返回 ``None``，调用方输出 :data:`EMPTY_VALUE`。
    - :meth:`ViewSpanBuilder._prepare_flatten_data` 优先读取最新 View 快照的
      ``attributes.view.started_at``；转换结果为 ``None`` 或 ``0`` 时回退到主记录的导航时间。
      回退后的结果为 ``None`` 时保留主记录的根级 ``start_time``。
      ``end_time`` 使用最新快照中的值；快照无该字段或无快照时保留主记录的值。
    """
    start_time = get_safe_number(flatten_data.get("start_time"), None)
    end_time = get_safe_number(flatten_data.get("end_time"), None)
    if start_time is None or end_time is None:
        return None
    return (end_time - start_time) / 1000


@dataclass(frozen=True, slots=True)
class DisplayViewDurationBadgeItem(NamedKeyValueItem):
    """Overview 徽章：展示 View 的停留时长（毫秒）。

    使用准备后的 ``start_time`` / ``end_time`` 计算时长，取代 ``elapsed_time`` 徽标；
    任一时间字段缺失或无法转换为数值时输出 :data:`EMPTY_VALUE`。
    响应结构与其他徽标一致（``field_name`` + ``value``）。
    """

    field_name: str = "display.view.duration"

    def render(self, flatten_data: dict[str, Any]) -> dict[str, Any]:
        duration = _compute_view_duration_ms(flatten_data)
        return {
            "field_name": self.field_name,
            "value": duration if duration is not None else EMPTY_VALUE,
        }


class ViewSpanOverview(SpanOverview):
    """View 类型 Span 的概览区。

    - ``BADGES``：徽标用停留时长（``display.view.duration``）取代 ``elapsed_time``，
      由 :class:`DisplayViewDurationBadgeItem` 实时从 ``start_time`` / ``end_time`` 计算。
    - ``ITEMS``：独立声明公共概览字段，并在 ``attributes.view.url_template`` 后增加
      ``attributes.view.previous_url_template``，不自动跟随父类 :attr:`SpanOverview.ITEMS` 更新。
    """

    BADGES = (DisplayViewDurationBadgeItem(),)
    ITEMS = (
        SpanTypeItem(),
        *named(
            "app_name",
            "attributes.view.url_template",
            "attributes.view.previous_url_template",
            "attributes.session.id",
            "attributes.view.id",
            "start_time",
            "end_time",
            "attributes.user.id",
            "resource.deployment.environment.name",
        ),
    )


@dataclass(frozen=True, slots=True)
class DisplayViewDurationItem(KeyValueItem):
    """View 停留时长：由准备后的 ``end_time - start_time`` 换算为毫秒。

    与 :class:`DisplayViewDurationBadgeItem` 共用 :func:`_compute_view_duration_ms` 算法，
    避免徽标与卡片两处对「停留时长」计算分叉；响应结构沿用 :class:`KeyValueItem` 的 ``{key: value}`` 形态。
    """

    key: str = "display.view.duration"

    def render(self, flatten_data: dict[str, Any]) -> dict[str, Any]:
        duration = _compute_view_duration_ms(flatten_data)
        return {self.key: duration if duration is not None else EMPTY_VALUE}


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


def vital_group(metric: str, extra: tuple[str, ...] = ()) -> DictItem:
    """构造单个 Web Vitals 指标卡片，公共字段与 ``extra`` 均从同指标快照读取。

    评级阈值配置复用 :class:`RatingConfigItem`，TTFB 通过 ``extra`` 补充四段耗时。
    """
    fields = ("attributes.vital.metric", "attributes.vital.value", *extra)
    return DictItem(
        key=metric,
        items=[
            *(KeyValueItem(key=field, source=build_vital_source_key(metric, field)) for field in fields),
            RatingConfigItem(source=metric),
        ],
    )


class ViewWebVitalsSection(BaseSection):
    """Web Vitals 指标区：TTFB / FCP / LCP / INP / CLS 五项。

    TTFB 额外包含 ``waiting`` / ``dns`` / ``connection`` / ``request`` 四段耗时；
    各项均包含 ``metric``、``value`` 与评分阈值配置，由 :func:`vital_group` 统一生成。
    """

    KEY = "web_vitals"
    TYPE = SectionType.SUMMARY_CARDS.value
    DATA = [vital_group("ttfb", TTFB_SEGMENTS), *(vital_group(metric) for metric in ("fcp", "lcp", "inp", "cls"))]


class ViewLoadingTimingSection(BaseSection):
    """View 加载时序瀑布：按「字段缺失 → 不出段」组装，避免伪造全零瀑布。

    - TTFB 四段（prepare / dns / connect / first_byte）依赖同 View 的 Vital 快照，
      快照缺失时对应段整段不输出。
    - View 三段（dom_processing / resource_load / page_stable）依赖 ``attributes.view.*`` 字段，
      起终点缺失时省略对应段；``dom_processing`` / ``resource_load`` 时长为负也省略。
      ``page_stable`` 仅自动计时来源输出，其起终点差值为负时归零，不设置误差阈值。
    - ``markers`` 从 Vital 快照中读取 TTFB / FCP / LCP；``milestones`` 从 View 字段中读取。
      两者均跳过缺失或无法转换为数值的值，不过滤负数或非有限数值。
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

    @classmethod
    def _diff(cls, minuend: int | float | None, subtrahend: int | float | None) -> int | float | None:
        """空安全减法：任一操作数缺失直接返回 ``None``，避免 ``None - int`` 抛错。"""
        return safe_diff(minuend, subtrahend)

    def _build_phases(self) -> list[dict[str, Any]]:
        is_auto = self.flatten_data.get("attributes.view.loading_time_source") == ViewLoadingTimeSource.AUTO.value
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

        # ── View 三段：起终点均需存在；前两段负时长过滤，page_stable 的负差归零 ──
        dom_processing_start = self.numeric_or_none("attributes.view.first_byte")
        resource_load_start = self.numeric_or_none("attributes.view.dom_content_loaded")
        dom_processing_duration = self._diff(resource_load_start, dom_processing_start)
        page_stable_start = self.numeric_or_none("attributes.view.load_event")
        resource_load_duration = self._diff(page_stable_start, resource_load_start)
        loading_time = self.numeric_or_none("attributes.view.loading_time")
        # 自动计时来源下，page_stable 起终点差值为负时统一归零，不区分负差大小或原因。
        page_stable_duration = self._diff(loading_time, page_stable_start)
        if is_auto and page_stable_duration is not None:
            page_stable_duration = max(0, page_stable_duration)

        # phase 构造：起点或时长缺失、起点为负或时长为负则整段不输出（min_start=0）
        aliases = self.PHASE_ALIASES
        phases_candidates = [
            phase("prepare", aliases.get("prepare", "prepare"), 0, prepare_duration, min_start=0),
            phase("dns", aliases.get("dns", "dns"), dns_start, dns_duration, min_start=0),
            phase("connect", aliases.get("connect", "connect"), connect_start, connect_duration, min_start=0),
            phase(
                "first_byte",
                aliases.get("first_byte", "first_byte"),
                first_byte_start,
                first_byte_duration,
                min_start=0,
            ),
            phase(
                "dom_processing",
                aliases.get("dom_processing", "dom_processing"),
                dom_processing_start,
                dom_processing_duration,
                min_start=0,
            ),
            phase(
                "resource_load",
                aliases.get("resource_load", "resource_load"),
                resource_load_start,
                resource_load_duration,
                min_start=0,
            ),
        ]
        if is_auto:
            phases_candidates.append(
                phase(
                    "page_stable",
                    aliases.get("page_stable", "page_stable"),
                    page_stable_start,
                    page_stable_duration,
                    min_start=0,
                )
            )
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
                    "display.rating_config": build_rating_config(metric),
                }
            )
        return markers

    # ── 里程碑：字段缺失时整项省略；page_stable 仅自动计时来源才输出 ──
    MILESTONES: tuple[tuple[str, str], ...] = (
        ("dom_complete", "attributes.view.dom_complete"),
        ("load_event", "attributes.view.load_event"),
        ("page_stable", "attributes.view.loading_time"),
    )

    def _build_milestones(self) -> list[dict[str, Any]]:
        is_auto = self.flatten_data.get("attributes.view.loading_time_source") == ViewLoadingTimeSource.AUTO.value
        return [
            {"key": key, "field_name": field, "value": value}
            for key, field in self.MILESTONES
            if (value := self.numeric_or_none(field)) is not None and (key != "page_stable" or is_auto)
        ]

    def _fill_data(self):
        # 非 initial_load 类型直接省略加载时序，不构造 phases、markers 或 milestones。
        if self.flatten_data.get("attributes.view.loading_type") != ViewLoadingType.INITIAL_LOAD.value:
            return

        phases = self._build_phases()
        markers = self._build_markers()
        milestones = self._build_milestones()

        # loading_time 转换结果不为 None 且 >= 0 时作为总耗时，保留零值；不额外校验有限性。
        # total_duration 不随 markers 变化；此处不计算前端横轴的展示范围。
        loading_time = self.numeric_or_none("attributes.view.loading_time")
        total = loading_time if loading_time is not None and loading_time >= 0 else None

        # phases / markers 均空时 waterfall 返回 None，调用方省略 ``data``；
        # milestones 不参与判空，在 data 存在时固定写入该键（即使为空列表）。
        data = waterfall(phases, total=total, markers=markers)
        if data is None:
            return
        data["milestones"] = milestones
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
            # start_time 不在 VIEW_SNAPSHOT_FIELDS 中，另按导航开始字段回填。
            flatten_data.update({field: latest_view[field] for field in VIEW_SNAPSHOT_FIELDS if field in latest_view})

        # 最新快照的导航时间转换结果为 None 或 0 时回退主记录；回退后为 None 则保留根级 start_time。
        # 不过滤 NaN / Infinity；选中此类值时，下面的 int 转换会抛出 ValueError / OverflowError。
        started_at = get_safe_number((latest_view or {}).get("attributes.view.started_at"), None) or get_safe_number(
            flatten_data.get("attributes.view.started_at"), None
        )
        if started_at is not None:
            flatten_data["start_time"] = int(started_at * 1000)  # 导航开始，µs

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
            flat
            for item in related_spans
            if (flat := flatten_dict_data(item)).get("attributes.span_type") == RumSpanType.VIEW.value
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
