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

from semconv.constants import FieldDisplayType, FieldUnit
from semconv.rum.constants import VitalInpInteractionType, VitalMetric
from semconv.rum.field import FieldSpec


VITAL_ID = FieldSpec(field_name="vital.id", field_alias=_("指标 ID"))
VITAL_METRIC = FieldSpec(field_name="vital.metric", field_alias=_("指标"), option_values=VitalMetric)
# vital 为动态单位：CLS 保持浮点数，其他指标按 ms 展示。
VITAL_VALUE = FieldSpec(
    field_name="vital.value",
    field_alias=_("指标值"),
    field_unit="vital",
    field_display_type=FieldDisplayType.DURATION.value,
)

# INP 相关字段
VITAL_INP_INPUT_DELAY = FieldSpec(
    field_name="vital.inp.input_delay",
    field_alias=_("输入延迟"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
VITAL_INP_INTERACTION_TARGET = FieldSpec(field_name="vital.inp.interaction_target", field_alias=_("交互目标元素"))
VITAL_INP_INTERACTION_TYPE = FieldSpec(
    field_name="vital.inp.interaction_type", field_alias=_("交互类型"), option_values=VitalInpInteractionType
)
VITAL_INP_PROCESSING_DURATION = FieldSpec(
    field_name="vital.inp.processing_duration",
    field_alias=_("交互处理耗时"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
VITAL_INP_PRESENTATION_DELAY = FieldSpec(
    field_name="vital.inp.presentation_delay",
    field_alias=_("呈现延迟"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)

# LCP 相关字段
VITAL_LCP_TARGET = FieldSpec(field_name="vital.lcp.target", field_alias=_("LCP 元素选择器"))
VITAL_LCP_URL = FieldSpec(field_name="vital.lcp.url", field_alias=_("LCP 资源 URL"))
VITAL_LCP_RESOURCE_LOAD_DURATION = FieldSpec(
    field_name="vital.lcp.resource_load_duration",
    field_alias=_("LCP 资源加载耗时"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
VITAL_LCP_ELEMENT_RENDER_DELAY = FieldSpec(
    field_name="vital.lcp.element_render_delay",
    field_alias=_("LCP 元素渲染延迟"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)

# TTFB 相关字段
VITAL_TTFB_WAITING_DURATION = FieldSpec(
    field_name="vital.ttfb.waiting_duration",
    field_alias=_("请求准备耗时"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
VITAL_TTFB_DNS_DURATION = FieldSpec(
    field_name="vital.ttfb.dns_duration",
    field_alias=_("DNS 阶段耗时"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
VITAL_TTFB_CONNECTION_DURATION = FieldSpec(
    field_name="vital.ttfb.connection_duration",
    field_alias=_("连接耗时（含 TLS）"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
VITAL_TTFB_REQUEST_DURATION = FieldSpec(
    field_name="vital.ttfb.request_duration",
    field_alias=_("请求阶段耗时"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
