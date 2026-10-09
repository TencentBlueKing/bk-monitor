"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from dataclasses import dataclass
from typing import Any

from constants.otel_query import RatingLevel

from rum_web.handlers.builder.base import BaseSection, EMPTY_VALUE, KeyValueItem, NamedKeyValueItem
from rum_web.handlers.builder.constants import SectionType
from rum_web.handlers.builder.span.base import (
    RatingConfigItem,
    SpanBuilder,
    SpanOverview,
    named,
)
from rum_web.handlers.builder.utils import get_safe_number, match_rating


@dataclass(frozen=True, slots=True)
class RatingLevelBadgeItem(NamedKeyValueItem):
    """Overview 徽章：根据 metric 与 value 匹配评级，输出评级标识与本地化别名。

    - ``value``：评级标识（``good`` / ``needs_improvement`` / ``poor``），不是档位阈值。
    - 指标值缺失、无法转换为数值或指标无评级配置时，``value`` 与 ``alias`` 输出 :data:`EMPTY_VALUE`，
      避免 ``get_safe_number`` 的 0 默认值被误评为「良好」。
    """

    field_name: str = "display.rating_level"

    def render(self, flatten_data: dict[str, Any]) -> dict[str, Any]:
        metric = flatten_data.get("attributes.vital.metric", "")
        value = get_safe_number(flatten_data.get("attributes.vital.value"), None)
        matched = match_rating(metric, value) if value is not None else None
        return {
            "field_name": self.field_name,
            "value": matched.rating if matched else EMPTY_VALUE,
            "alias": RatingLevel(matched.rating).label if matched else EMPTY_VALUE,
        }


class VitalSpanOverview(SpanOverview):
    BADGES = (
        *named("elapsed_time"),
        RatingLevelBadgeItem(),
    )


class VitalRatingSection(BaseSection):
    KEY = "vital_rating"
    TYPE = SectionType.RATING_BAR.value
    DATA = [
        KeyValueItem(key="attributes.vital.metric"),
        KeyValueItem(key="attributes.vital.value"),
        RatingConfigItem(),
    ]


class VitalSpanBuilder(SpanBuilder):
    OVERVIEW = VitalSpanOverview
    SECTIONS = [
        VitalRatingSection,
    ]
