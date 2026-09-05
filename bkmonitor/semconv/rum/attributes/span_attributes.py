"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.utils.translation import gettext_lazy as _

from semconv.constants import FieldDisplayType, FieldUnit, SpanKind
from semconv.rum.field import FieldSpec

# ── Span 根级字段 ──────────────────────────────────────────────────────────────
TIME = FieldSpec(
    field_name="time",
    field_alias=_("时间"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DATETIME.value,
)
BK_BIZ_ID = FieldSpec(field_name="bk_biz_id", field_alias=_("业务 ID"))
APP_NAME = FieldSpec(field_name="app_name", field_alias=_("应用名称"))

TRACE_ID = FieldSpec(field_name="trace_id", field_alias="Trace ID")
TRACE_STATE = FieldSpec(field_name="trace_state", field_alias=_("Trace 状态"))
SPAN_NAME = FieldSpec(field_name="span_name", field_alias=_("Span 名称"))
SPAN_ID = FieldSpec(field_name="span_id", field_alias="Span ID")
PARENT_SPAN_ID = FieldSpec(field_name="parent_span_id", field_alias=_("父 Span ID"))
KIND = FieldSpec(field_name="kind", field_alias=_("Span 类型"), option_values=SpanKind)

# 时间字段
START_TIME = FieldSpec(
    field_name="start_time",
    field_alias=_("开始时间"),
    field_unit=FieldUnit.US.value,
    field_display_type=FieldDisplayType.DATETIME.value,
)
END_TIME = FieldSpec(
    field_name="end_time",
    field_alias=_("结束时间"),
    field_unit=FieldUnit.US.value,
    field_display_type=FieldDisplayType.DATETIME.value,
)
ELAPSED_TIME = FieldSpec(
    field_name="elapsed_time",
    field_alias=_("耗时"),
    field_unit=FieldUnit.US.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
