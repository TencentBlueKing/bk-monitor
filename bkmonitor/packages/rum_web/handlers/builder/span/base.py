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

from bkmonitor.data_source.format import flatten_dict_data
from django.utils.translation import gettext_lazy as _

from rum_web.handlers.builder.base import BaseOverview, BaseSection, KeyValueItem, NamedKeyValueItem
from rum_web.handlers.builder.utils import build_rating_config
from semconv.rum.constants import RumSpanType


def named(*field_names: str) -> tuple[NamedKeyValueItem, ...]:
    """按 ``field_names`` 批量构造按名透传取值的概览 Item 元组。

    用于子类拼装 ``BADGES`` / ``ITEMS``，典型用法：

        BADGES = named("elapsed_time", "attributes.outcome.type")
        ITEMS = (SpanTypeItem(), *named("app_name", "attributes.view.url_template"))

    返回元组而非列表，匹配 ``BADGES`` / ``ITEMS`` 的不可变类级配置语义。
    """
    return tuple(NamedKeyValueItem(field_name=name) for name in field_names)


@dataclass(frozen=True, slots=True)
class RatingConfigItem(KeyValueItem):
    """Web Vitals 评级阈值配置：``source`` 优先，缺失时回退到 flatten_data 中的 ``attributes.vital.metric``。

    列表侧（View 的 Web Vitals 区块）与详情侧（Vital 的 rating 区块）共用，避免两份等价实现分叉。
    """

    key: str = "display.rating_config"

    def render(self, flatten_data: dict[str, Any]) -> dict[str, Any]:
        source = self.source or flatten_data.get("attributes.vital.metric", "")
        return {self.key: build_rating_config(source)}


@dataclass(frozen=True, slots=True)
class SpanTypeItem(NamedKeyValueItem):
    field_name: str = "display.span_type"
    field_alias: str = _("类型")

    SPAN_TYPE_MAP = {
        RumSpanType.VIEW.value: "View",
        RumSpanType.RESOURCE.value: "Resource",
        RumSpanType.ERROR.value: "Error",
        RumSpanType.VITAL.value: "Web Vital",
        RumSpanType.LONG_TASK.value: "Long Task",
        RumSpanType.ACTION.value: "Action",
        RumSpanType.WEBSOCKET.value: "WebSocket",
        RumSpanType.CUSTOM.value: "Custom",
    }

    def render(self, flatten_data: dict[str, Any]) -> Any:
        result: dict[str, Any] = {"field_name": self.field_name, "field_alias": self.field_alias}
        span_type: str = flatten_data.get("attributes.span_type", "")
        span_type_display: str = self.SPAN_TYPE_MAP.get(span_type, "")
        if span_type == RumSpanType.RESOURCE.value:
            resource_type: str = flatten_data.get("attributes.resource.type", "")
            result["alias"] = result["value"] = (
                f"{span_type_display}({resource_type})" if resource_type else span_type_display
            )
        else:
            result["alias"] = result["value"] = span_type_display
        return result


class SpanOverview(BaseOverview):
    BADGES: tuple[NamedKeyValueItem, ...] = ()
    ITEMS: tuple[NamedKeyValueItem, ...] = (
        SpanTypeItem(),
        *named(
            "app_name",
            "attributes.view.url_template",
            "attributes.session.id",
            "attributes.view.id",
            "start_time",
            "end_time",
            "attributes.user.id",
            "resource.deployment.environment.name",
        ),
    )


class SpanBuilder:
    """Span 详情 Builder 基类。

    子类通过声明 ``OVERVIEW`` 与 ``SECTIONS`` 组装区块，特殊类型可覆盖
    :meth:`_prepare_flatten_data` 或 :meth:`process` 自定义装配逻辑。
    公共头部 ``origin_data``、``span_id`` 与空 ``sections`` 在此统一处理。
    """

    OVERVIEW: type[BaseOverview] | None = None
    SECTIONS: list[type[BaseSection]] | None = None

    @classmethod
    def process(
        cls,
        span: dict[str, Any],
        related_spans: Sequence[dict[str, Any]] = (),
    ) -> dict[str, Any]:
        """组装 Span 详情响应。

        - ``span``：主 Span 的原始记录（未打平），用于回填 ``origin_data``、``span_id``。
        - ``related_spans``：关联 Span 列表（仅 View 会传入生命周期与 Vital 快照）。

        默认按 ``OVERVIEW``、``SECTIONS`` 顺序渲染，未声明则返回空区块。
        """
        flatten_data = cls._prepare_flatten_data(span, related_spans)
        result: dict[str, Any] = {
            "origin_data": span,
            "span_id": span.get("span_id", ""),
            "sections": [],
        }
        if cls.OVERVIEW is not None:
            result["overview"] = cls.OVERVIEW(flatten_data).render()
        if cls.SECTIONS is not None:
            for section_cls in cls.SECTIONS:
                section_render = section_cls(flatten_data).render()
                if section_render is not None:
                    result["sections"].append(section_render)
        return result

    @classmethod
    def _prepare_flatten_data(
        cls,
        span: dict[str, Any],
        related_spans: Sequence[dict[str, Any]] = (),
    ) -> dict[str, Any]:
        """默认返回主 Span 打平后的字典；子类可注入关联 Span 附加信息。"""
        return flatten_dict_data(span)


__all__ = [
    "SpanBuilder",
    "SpanOverview",
    "SpanTypeItem",
    "named",
    "RatingConfigItem",
]
