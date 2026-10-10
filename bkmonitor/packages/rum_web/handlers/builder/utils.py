"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from collections.abc import Iterable
from typing import Any

from semconv.constants import FieldUnit
from semconv.rum.constants import RatingLevel
from semconv.rum.field import RatingThreshold
from semconv.rum.trace import SpanSpec


def get_safe_number(value: Any, default: int | float | None = 0) -> int | float | None:
    """default=None 用于区分字段缺失和有效的零值。"""
    if value is None:
        return default
    try:
        number = float(value)
        return int(number) if number.is_integer() else number
    except (TypeError, ValueError):
        return default


def safe_diff(minuend: int | float | None, subtrahend: int | float | None) -> int | float | None:
    return None if minuend is None or subtrahend is None else minuend - subtrahend


def phase(
    key: str,
    alias: str,
    start: int | float | None,
    duration: int | float | None,
    *,
    min_start: int | float | None = None,
) -> dict[str, Any] | None:
    """缺少起点或时长、时长为负或起点低于 min_start 时，整段省略。"""
    if start is None or duration is None or duration < 0 or (min_start is not None and start < min_start):
        return None
    return {"key": key, "alias": alias, "start": start, "duration": duration}


def waterfall(
    phases: Iterable[dict[str, Any] | None], total: int | float | None = None, **extras: Any
) -> dict[str, Any] | None:
    """没有有效段及附加标记时省略瀑布，total 本身不构成时序数据。"""
    phases = [item for item in phases if item]
    if not phases and not any(extras.values()):
        return None
    data: dict[str, Any] = {"unit": FieldUnit.MS.value, "phases": phases, **extras}
    if total is not None:
        data["total_duration"] = total
    return data


def build_rating_config(metric: str) -> list[dict[str, Any]]:
    """与 view_config 共用 SpanSpec 中的阈值，仅补充评级别名。"""
    return [
        {
            "rating": level.rating,
            **({"value": level.value} if level.value is not None else {}),
            "alias": RatingLevel(level.rating).label,
        }
        for level in SpanSpec.from_field(metric.upper()).rating_config
    ]


def match_rating(metric: str, value: float | int) -> RatingThreshold | None:
    """按包含性上界匹配，未设置阈值的末项承接剩余值。"""
    return next(
        (
            level
            for level in SpanSpec.from_field(metric.upper()).rating_config
            if level.value is None or value <= level.value
        ),
        None,
    )
