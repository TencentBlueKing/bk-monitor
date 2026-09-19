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

from rum_web.handlers.builder.base import BaseOverview, BaseSection, NamedKeyValueItem
from semconv.rum.constants import RumSpanType


# ── Badge 字段 ────────────────────────────────────────────────────────────
OVERVIEW_ELAPSED_TIME = NamedKeyValueItem(field_name="elapsed_time")
OVERVIEW_ATTRIBUTES_OUTCOME_TYPE = NamedKeyValueItem(field_name="attributes.outcome.type")
# resource
OVERVIEW_ATTRIBUTES_RESOURCE_TYPE = NamedKeyValueItem(field_name="attributes.resource.type")
OVERVIEW_ATTRIBUTES_HTTP_RESPONSE_STATUS_CODE = NamedKeyValueItem(field_name="attributes.http.response.status_code")
# action
OVERVIEW_ATTRIBUTES_ACTION_TYPE = NamedKeyValueItem(field_name="attributes.action.type")

# ── 通用 Item 字段 ─────────────────────────────────────────────────────────────
OVERVIEW_APP_NAME = NamedKeyValueItem(field_name="app_name")
OVERVIEW_ATTRIBUTES_VIEW_URL_TEMPLATE = NamedKeyValueItem(field_name="attributes.view.url_template")
OVERVIEW_ATTRIBUTES_SESSION_ID = NamedKeyValueItem(field_name="attributes.session.id")
OVERVIEW_ATTRIBUTES_VIEW_ID = NamedKeyValueItem(field_name="attributes.view.id")
OVERVIEW_START_TIME = NamedKeyValueItem(field_name="start_time")
OVERVIEW_END_TIME = NamedKeyValueItem(field_name="end_time")
OVERVIEW_ATTRIBUTES_USER_ID = NamedKeyValueItem(field_name="attributes.user.id")
OVERVIEW_RESOURCE_DEPLOYMENT_ENVIRONMENT_NAME = NamedKeyValueItem(field_name="resource.deployment.environment.name")
# view
OVERVIEW_ATTRIBUTES_VIEW_PREVIOUS_URL_TEMPLATE = NamedKeyValueItem(field_name="attributes.view.previous_url_template")


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
    BADGES: list[NamedKeyValueItem] = []
    ITEMS: list[NamedKeyValueItem] = [
        SpanTypeItem(),
        OVERVIEW_APP_NAME,
        OVERVIEW_ATTRIBUTES_VIEW_URL_TEMPLATE,
        OVERVIEW_ATTRIBUTES_SESSION_ID,
        OVERVIEW_ATTRIBUTES_VIEW_ID,
        OVERVIEW_START_TIME,
        OVERVIEW_END_TIME,
        OVERVIEW_ATTRIBUTES_USER_ID,
        OVERVIEW_RESOURCE_DEPLOYMENT_ENVIRONMENT_NAME,
    ]


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
]
