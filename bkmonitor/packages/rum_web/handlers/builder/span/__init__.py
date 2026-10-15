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

from bkmonitor.data_source.format import flatten_dict_data
from semconv.rum.constants import RumSpanType

from rum_web.handlers.builder.span.base import SpanBuilder

from .action import ActionSpanBuilder
from .error import ErrorSpanBuilder
from .longtask import LongTaskSpanBuilder
from .resource import ResourceSpanBuilder
from .view import ViewSpanBuilder
from .vital import VitalSpanBuilder


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
    """按 Span 类型分派，未命中时保留公共概览和空 sections。"""
    span_type = flatten_dict_data(span).get("attributes.span_type") or ""
    builder = BUILDERS.get(span_type, SpanBuilder)
    return builder.process(span, related_spans)
