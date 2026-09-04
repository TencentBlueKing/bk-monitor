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
from semconv.rum.field import FieldSpec, RatingLevel

# ── Web Vitals 虚拟指标字段（非存储字段，由前端计算或预计算层提供）──────────────
# 注册在 SpanSpec 根级，可直接通过字段名查找，如 SpanSpec.from_field("LCP")。

#: 累积布局偏移（无单位，数值越小越好）
CLS = FieldSpec(
    field_name="CLS",
    field_alias=_("累积布局偏移"),
    rating_config=(
        RatingLevel(rating="good", value=0.1),
        RatingLevel(rating="needs_improvement", value=0.25),
        RatingLevel(rating="poor"),
    ),
)

#: 交互到下一次绘制
INP = FieldSpec(
    field_name="INP",
    field_alias=_("交互到下一次绘制"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
    rating_config=(
        RatingLevel(rating="good", value=200),
        RatingLevel(rating="needs_improvement", value=500),
        RatingLevel(rating="poor"),
    ),
)

#: 最大内容绘制
LCP = FieldSpec(
    field_name="LCP",
    field_alias=_("最大内容绘制"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
    rating_config=(
        RatingLevel(rating="good", value=2500),
        RatingLevel(rating="needs_improvement", value=4000),
        RatingLevel(rating="poor"),
    ),
)

#: 首次内容绘制
FCP = FieldSpec(
    field_name="FCP",
    field_alias=_("首次内容绘制"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
    rating_config=(
        RatingLevel(rating="good", value=1800),
        RatingLevel(rating="needs_improvement", value=3000),
        RatingLevel(rating="poor"),
    ),
)

#: 首字节耗时
TTFB = FieldSpec(
    field_name="TTFB",
    field_alias=_("首字节耗时"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
    rating_config=(
        RatingLevel(rating="good", value=800),
        RatingLevel(rating="needs_improvement", value=1800),
        RatingLevel(rating="poor"),
    ),
)
