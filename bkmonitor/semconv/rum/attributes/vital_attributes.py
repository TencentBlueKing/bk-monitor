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

from constants.otel_query import FieldTypeEnum
from semconv.constants import FieldDisplayType
from semconv.rum.constants import VitalInpInteractionType, VitalMetric
from semconv.rum.field import FieldSpec


VITAL_ID = FieldSpec(field_name="vital.id", field_alias=_("指标 ID"))
VITAL_VERSION = FieldSpec(
    field_name="vital.version", field_alias=_("指标快照版本"), field_type=FieldTypeEnum.LONG.value
)
VITAL_METRIC = FieldSpec(field_name="vital.metric", field_alias=_("指标"), option_values=VitalMetric)
# vital 为动态单位：CLS 保持浮点数，其他指标按 ms 展示。
VITAL_VALUE = FieldSpec(
    field_name="vital.value",
    field_alias=_("指标值"),
    field_unit="vital",
    field_display_type=FieldDisplayType.DURATION.value,
)

# INP 相关字段
VITAL_INP_INTERACTION_TYPE = FieldSpec(
    field_name="vital.inp.interaction_type", field_alias=_("交互类型"), option_values=VitalInpInteractionType
)
VITAL_INP_TARGET_SELECTOR = FieldSpec(field_name="vital.inp.target_selector", field_alias=_("INP 交互目标选择器"))

# LCP 相关字段
VITAL_LCP_TARGET = FieldSpec(field_name="vital.lcp.target", field_alias=_("LCP 元素选择器"))
VITAL_LCP_URL = FieldSpec(field_name="vital.lcp.url", field_alias=_("LCP 资源 URL"))

# CLS 相关字段
VITAL_CLS_TARGET_SELECTOR = FieldSpec(field_name="vital.cls.target_selector", field_alias=_("CLS 主要位移元素选择器"))
