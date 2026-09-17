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

from rum_web.handlers.builder.base import BaseSection, KeyValueItem, NamedKeyValueItem
from rum_web.handlers.builder.span.base import SpanBuilder
from rum_web.handlers.builder.constants import SectionType
from rum_web.handlers.builder.span.base import (
    OVERVIEW_ELAPSED_TIME,
    SpanOverview,
)
from rum_web.handlers.builder.utils import get_safe_number


@dataclass(frozen=True, slots=True)
class RatingLevelBadgeItem(NamedKeyValueItem):
    """Overview 徽章：根据 metric 与 value 匹配评级，输出 rating 值与中文别名。"""

    field_name: str = "display.rating_level"

    @classmethod
    def _match_rating(cls, metric: str, value: float | int) -> dict[str, Any] | None:
        """按包含性上界匹配 Web Vitals 指标的评级，未设置 value 的末项承接剩余值。"""
        if not metric:
            return None
        for item in RatingLevel.get_rating_config(metric):
            threshold = item.get("value")
            if threshold is None or value <= threshold:
                return item
        return None

    def render(self, flatten_data: dict[str, Any]) -> dict[str, Any]:
        metric = flatten_data.get("attributes.vital.metric", "")
        value = get_safe_number(flatten_data.get("attributes.vital.value"))
        matched: dict[str, Any] = self._match_rating(metric, value) or {}
        return {
            "field_name": self.field_name,
            "value": matched.get("value", ""),
            "alias": matched.get("alias", ""),
        }


@dataclass(frozen=True, slots=True)
class RatingConfigItem(KeyValueItem):
    """`vital_rating` 区块的评级配置：按 metric 从内置阈值表读取。"""

    key: str = "display.rating_config"

    def render(self, flatten_data: dict[str, Any]) -> dict[str, Any]:
        metric = flatten_data.get("attributes.vital.metric", "")
        return {self.key: RatingLevel.get_rating_config(metric) if metric else []}


class VitalSpanOverview(SpanOverview):
    BADGES = [
        OVERVIEW_ELAPSED_TIME,
        RatingLevelBadgeItem(),
    ]


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
