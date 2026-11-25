"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from semconv.constants import FieldDisplayType, FieldUnit
from semconv.rum import hover
from semconv.rum.constants import RatingLevel
from semconv.rum.field import FieldSpec, RatingThreshold
from constants.otel_query import FieldTypeEnum

CLS = FieldSpec(
    field_name="CLS",
    field_alias="CLS",
    field_type=FieldTypeEnum.DOUBLE.value,
    is_real=False,
    rating_config=(
        RatingThreshold(rating=RatingLevel.GOOD.value, value=0.1),
        RatingThreshold(rating=RatingLevel.NEEDS_IMPROVEMENT.value, value=0.25),
        RatingThreshold(rating=RatingLevel.POOR.value),
    ),
    extra_config={"hover": hover.CLS},
)

INP = FieldSpec(
    field_name="INP",
    field_alias="INP",
    field_unit=FieldUnit.MS.value,
    field_type=FieldTypeEnum.DOUBLE.value,
    field_display_type=FieldDisplayType.DURATION.value,
    is_real=False,
    rating_config=(
        RatingThreshold(rating=RatingLevel.GOOD.value, value=200),
        RatingThreshold(rating=RatingLevel.NEEDS_IMPROVEMENT.value, value=500),
        RatingThreshold(rating=RatingLevel.POOR.value),
    ),
    extra_config={"hover": hover.INP},
)

LCP = FieldSpec(
    field_name="LCP",
    field_alias="LCP",
    field_unit=FieldUnit.MS.value,
    field_type=FieldTypeEnum.DOUBLE.value,
    field_display_type=FieldDisplayType.DURATION.value,
    is_real=False,
    rating_config=(
        RatingThreshold(rating=RatingLevel.GOOD.value, value=2500),
        RatingThreshold(rating=RatingLevel.NEEDS_IMPROVEMENT.value, value=4000),
        RatingThreshold(rating=RatingLevel.POOR.value),
    ),
    extra_config={"hover": hover.LCP},
)

FCP = FieldSpec(
    field_name="FCP",
    field_alias="FCP",
    field_unit=FieldUnit.MS.value,
    field_type=FieldTypeEnum.DOUBLE.value,
    field_display_type=FieldDisplayType.DURATION.value,
    is_real=False,
    rating_config=(
        RatingThreshold(rating=RatingLevel.GOOD.value, value=1800),
        RatingThreshold(rating=RatingLevel.NEEDS_IMPROVEMENT.value, value=3000),
        RatingThreshold(rating=RatingLevel.POOR.value),
    ),
    extra_config={"hover": hover.FCP},
)

TTFB = FieldSpec(
    field_name="TTFB",
    field_alias="TTFB",
    field_unit=FieldUnit.MS.value,
    field_type=FieldTypeEnum.DOUBLE.value,
    field_display_type=FieldDisplayType.DURATION.value,
    is_real=False,
    rating_config=(
        RatingThreshold(rating=RatingLevel.GOOD.value, value=800),
        RatingThreshold(rating=RatingLevel.NEEDS_IMPROVEMENT.value, value=1800),
        RatingThreshold(rating=RatingLevel.POOR.value),
    ),
    extra_config={"hover": hover.TTFB},
)
