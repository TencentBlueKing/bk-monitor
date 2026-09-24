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
from typing import Any

from semconv.rum.constants import RumSpanType

from rum_web.handlers.builder.span.base import SpanBuilder, SpanOverview

from .action import ActionSpanBuilder
from .error import ErrorSpanBuilder
from .longtask import LongTaskSpanBuilder
from .resource import ResourceSpanBuilder
from .view import ViewSpanBuilder
from .vital import VitalSpanBuilder


class DefaultSpanBuilder(SpanBuilder):
    """未命中具体类型时的兜底 Builder：保留公共 ``overview`` 与空 ``sections``。

    方案 0x03.h 约定默认实现「返回公共头部和空 sections」。若 fallback 到裸
    :class:`SpanBuilder`，``OVERVIEW`` 为 ``None`` 会导致响应缺失公共头部
    （``display.span_type``、``app_name``、时间、用户、环境等），点开非明确
    实现的类型详情基本是空白，因此这里强制挂上 :class:`SpanOverview`。
    """

    OVERVIEW = SpanOverview
    SECTIONS: list = []


#: ``attributes.span_type`` 到对应 Builder 的分派表，未命中时回落到 :class:`DefaultSpanBuilder`。
BUILDERS: dict[str, type[SpanBuilder]] = {
    RumSpanType.RESOURCE.value: ResourceSpanBuilder,
    RumSpanType.ACTION.value: ActionSpanBuilder,
    RumSpanType.LONG_TASK.value: LongTaskSpanBuilder,
    RumSpanType.ERROR.value: ErrorSpanBuilder,
    RumSpanType.VITAL.value: VitalSpanBuilder,
    RumSpanType.VIEW.value: ViewSpanBuilder,
}


def build(
    span: dict[str, Any],
    related_spans: Sequence[dict[str, Any]] = (),
) -> dict[str, Any]:
    """根据 ``attributes.span_type`` 分派到对应 Builder 并返回组装结果。

    未命中类型时回落到 :class:`DefaultSpanBuilder`，保证响应仍包含公共 ``overview``。
    """
    span_type = span.get("attributes", {}).get("span_type", "")
    builder = BUILDERS.get(span_type, DefaultSpanBuilder)
    return builder.process(span, related_spans)


__all__ = ["build"]
