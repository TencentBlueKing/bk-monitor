"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from dataclasses import replace

from django.utils.translation import gettext_lazy as _

from constants.otel_query import FieldTypeEnum
from semconv.constants import FieldDisplayType, FieldUnit
from semconv.rum.field import FieldSpec
from semconv.rum.trace import SpanSpec


def raw_field(name: str, field_type: str = FieldTypeEnum.KEYWORD.value) -> FieldSpec:
    spec: FieldSpec = SpanSpec.from_field(name)
    return replace(spec, field_name=name, field_type=spec.field_type or field_type)


TRACE_COUNT = FieldSpec("trace_count", _("Trace 数量"), field_type="long", is_real=False)
ERROR_COUNT = FieldSpec("error_count", _("错误数量"), field_type="long", is_real=False)
ACTION_COUNT = FieldSpec("action_count", _("动作数量"), field_type="long", is_real=False)
FRUSTRATION_COUNT = FieldSpec("frustration_count", _("挫败行为数"), field_type="long", is_real=False)
REQUEST_COUNT = FieldSpec("request_count", _("API 请求数量"), field_type="long", is_real=False)
REQUEST_ERROR_COUNT = FieldSpec("request_error_count", _("API 错误请求数量"), field_type="long", is_real=False)
LONG_TASK_COUNT = FieldSpec("long_task_count", _("Long Task 数量"), field_type="long", is_real=False)

COUNT_FIELDS: tuple[FieldSpec, ...] = (
    TRACE_COUNT,
    ERROR_COUNT,
    ACTION_COUNT,
    FRUSTRATION_COUNT,
    REQUEST_COUNT,
    REQUEST_ERROR_COUNT,
    LONG_TASK_COUNT,
)
IS_ACTIVE = FieldSpec("is_active", _("是否进行中"), field_type="boolean", is_real=False)
CLOSE_REASON = FieldSpec("close_reason", _("关闭原因"), field_type="keyword", is_real=False)
CLOSE_TIME = FieldSpec("close_time", _("关闭时间"), FieldUnit.US.value, "long", FieldDisplayType.DATETIME.value, False)
DURATION = FieldSpec("duration", _("持续时长"), FieldUnit.US.value, "long", FieldDisplayType.DURATION.value, False)
START_TIME = FieldSpec("start_time", _("开始时间"), FieldUnit.US.value, "long", FieldDisplayType.DATETIME.value, False)

LIFECYCLE_FIELDS: tuple[FieldSpec, ...] = (
    IS_ACTIVE,
    CLOSE_REASON,
    CLOSE_TIME,
    DURATION,
    START_TIME,
)
