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

from semconv.constants import FieldDisplayType, FieldUnit, VitalMetric
from semconv.rum.field import FieldSpec


VITAL_ID = FieldSpec(field_name="vital.id", field_alias=_("Vital 唯一标识"))
VITAL_METRIC = FieldSpec(field_name="vital.metric", field_alias=_("指标名"), option_values=VitalMetric)
# CLS 单位为 1，FCP、INP、LCP、TTFB 单位为 ms，单位随指标变化，此处不固定
VITAL_VALUE = FieldSpec(field_name="vital.value", field_alias=_("指标测量值"))

# INP 相关字段
VITAL_INP_INPUT_DELAY = FieldSpec(
    field_name="vital.inp.input_delay",
    field_alias=_("输入延迟"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
VITAL_INP_INTERACTION_TARGET = FieldSpec(field_name="vital.inp.interaction_target", field_alias=_("交互目标元素标识"))
VITAL_INP_INTERACTION_TYPE = FieldSpec(field_name="vital.inp.interaction_type", field_alias=_("交互类型"))
VITAL_INP_PROCESSING_DURATION = FieldSpec(
    field_name="vital.inp.processing_duration",
    field_alias=_("处理耗时"),
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
VITAL_LCP_TARGET = FieldSpec(field_name="vital.lcp.target", field_alias=_("DOM 选择器"))
VITAL_LCP_URL = FieldSpec(field_name="vital.lcp.url", field_alias=_("元素对应资源 URL（已脱敏）"))
VITAL_LCP_RESOURCE_LOAD_DURATION = FieldSpec(
    field_name="vital.lcp.resource_load_duration",
    field_alias=_("资源加载耗时"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
VITAL_LCP_ELEMENT_RENDER_DELAY = FieldSpec(
    field_name="vital.lcp.element_render_delay",
    field_alias=_("元素渲染延迟"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)

# TTFB 相关字段
VITAL_TTFB_WAITING_DURATION = FieldSpec(
    field_name="vital.ttfb.waiting_duration",
    field_alias=_("请求就绪后的等待耗时"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
VITAL_TTFB_DNS_DURATION = FieldSpec(
    field_name="vital.ttfb.dns_duration",
    field_alias=_("DNS 解析耗时"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
VITAL_TTFB_CONNECTION_DURATION = FieldSpec(
    field_name="vital.ttfb.connection_duration",
    field_alias=_("TCP + TLS 连接建立耗时"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
VITAL_TTFB_REQUEST_DURATION = FieldSpec(
    field_name="vital.ttfb.request_duration",
    field_alias=_("请求发送后等待首字节耗时"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
