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

from constants.otel_query import RatingLevel
from semconv.constants import FieldUnit
from semconv.rum.field import RatingLevel as RatingThreshold
from semconv.rum.trace import SpanSpec


def get_safe_number(
    value: str | int | float | None,
    default: int | float | None = 0,
) -> int | float | None:
    """安全地将任意值转换为数字（int 或 float）。

    支持 str / int / float / None；值为 ``None`` 或转换抛出 ``TypeError`` / ``ValueError``
    时返回 ``default``。可转换的 NaN / Infinity 会原样保留，不校验数值是否有限。

    传入 ``default=None`` 可用于「缺失字段返回 ``None``」的语义，
    调用方可据此区分「字段不存在」与「字段值为 0」两种情况。
    """
    if value is None:
        return default
    try:
        numeric_value = float(value)
        return int(numeric_value) if numeric_value.is_integer() else numeric_value
    except (TypeError, ValueError):
        return default


def safe_diff(minuend: int | float | None, subtrahend: int | float | None) -> int | float | None:
    """空安全减法：任一操作数为 ``None`` 时返回 ``None``，避免 ``None - int`` 抛错。

    用于瀑布图各段起点/时长计算，缺失任一时序字段时整段不输出。
    """
    if minuend is None or subtrahend is None:
        return None
    return minuend - subtrahend


def phase(
    key: str,
    alias: str,
    start: int | float | None,
    duration: int | float | None,
    *,
    min_start: int | float | None = None,
) -> dict[str, Any] | None:
    """构造瀑布图单个 phase。

    起点或时长缺失、时长为负（``min_start`` 不为 ``None`` 时起点小于 ``min_start`` 也算非法）
    则整段不输出，避免伪造全零瀑布或在坐标轴原点渲染假段。

    - ``key``：phase 标识（如 ``"dns"`` / ``"tls"``）。
    - ``alias``：phase 展示别名；调用方自行从别名表中取值并兜底。
    - ``min_start``：起点下限，``None`` 表示不校验（Resource 侧），传 ``0`` 可拒绝负起点（View 侧）。
    """
    if start is None or duration is None or duration < 0 or (min_start is not None and start < min_start):
        return None
    return {"key": key, "alias": alias, "start": start, "duration": duration}


def waterfall(
    phases: Iterable[dict[str, Any] | None],
    total: int | float | None = None,
    **extras: Any,
) -> dict[str, Any] | None:
    """组装瀑布图 ``data``；``phases`` 与所有 ``extras`` 均为空则返回 ``None``。

    - 过滤 ``phases`` 中的空值（``None`` 或空 dict），只保留有效段。
    - ``phases`` 为空且 ``extras`` 中无任何非空值时返回 ``None``，调用方据此省略 ``data``，
      前端可区分「没有时序数据」与「耗时为 0」。
    - ``total`` 为 ``None`` 时省略 ``total_duration`` 键，传入 ``0`` 会显式写出 ``0``。
    - ``extras`` 透传为 ``data`` 的附加字段（如 ``markers`` / ``milestones``），
      是否为空由调用方自行判断是否传入。
    """
    phases = [p for p in phases if p]
    if not phases and not any(extras.values()):
        return None
    data: dict[str, Any] = {"unit": FieldUnit.MS.value, "phases": phases, **extras}
    if total is not None:
        data["total_duration"] = total
    return data


def _rating_config(metric: str) -> tuple[RatingThreshold, ...]:
    """按 metric 名称从 ``SpanSpec`` 读取评级阈值配置；``metric`` 为空或未注册时返回空元组。

    ``metric`` 大小写不敏感，内部统一转大写匹配 ``SpanSpec`` 中的 Web Vitals 虚拟字段注册名。
    """
    return SpanSpec.from_field(metric.upper()).rating_config


def build_rating_config(metric: str) -> list[dict[str, Any]]:
    """构造 Web Vitals 评级阈值配置（下发给前端用于评级条/刻度展示）。

    阈值从 :class:`SpanSpec` 读取（与 ``view_config`` 共用同一事实源），本函数仅附加评级
    别名；``value`` 为 ``None`` 的末项不输出 ``value`` 键，承接剩余值。``metric`` 为空
    或未配置阈值时返回空列表。
    """
    return [
        {
            "rating": level.rating,
            **({"value": level.value} if level.value is not None else {}),
            "alias": RatingLevel(level.rating).label,
        }
        for level in _rating_config(metric)
    ]


def match_rating(metric: str, value: float | int) -> RatingThreshold | None:
    """按包含性上界匹配 Web Vitals 指标的评级档位。

    - 阈值从 :class:`SpanSpec` 读取（与 ``view_config`` 共用同一事实源）。
    - ``level.value`` 为 ``None`` 的末项承接剩余值，始终命中。
    - ``metric`` 为空或 ``SpanSpec`` 未配置阈值时返回 ``None`` 表示不评级。

    注意：缺值（``attributes.vital.value`` 不存在）应由调用方提前判断并跳过本函数，
    避免 ``get_safe_number`` 的 0 默认值被误评为「良好」。
    """
    for level in _rating_config(metric):
        if level.value is None or value <= level.value:
            return level
    return None
