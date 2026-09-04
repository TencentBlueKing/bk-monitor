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
from collections.abc import Iterator
from typing import Protocol


class HasChoicesCachedEnum(Protocol):
    """存在 choices 方法的枚举协议（结构化子类型）。

    仅用于静态类型检查，约束 option_values 所引用的类必须实现
    choices() 类方法；无需实际继承本类即可通过类型检查。
    """

    @classmethod
    def choices(cls) -> list[tuple[str | int | float, str | int | float]]:
        """获取枚举值列表"""
        ...


@dataclass(frozen=True, slots=True)
class RatingLevel:
    """评级阈值描述符。

    按数组顺序匹配：``value`` 是包含性上界，单位沿用字段的 ``field_unit``；
    未设置 ``value`` 的末项承接剩余值。

    Attributes:
        rating: 评级名称，如 ``"good"``、``"needs_improvement"``、``"poor"``。
        value: 包含性上界阈值，``None`` 表示兜底项。
    """

    rating: str
    value: float | None = None


@dataclass(frozen=True, slots=True)
class FieldSpec:
    """字段语义描述符。

    原子字段只定义一次，复合字段通过大写类属性组合子字段。
    `FieldRegistry` 遍历字段树时以大写属性名识别子字段。

    Attributes:
        field_name: 字段在存储中的实际名称（不含父级前缀）。
        field_alias: 字段展示别名，默认空串（由消费方按需填充）。
        field_unit: 字段计量单位，取值为 ``FieldUnit`` 枚举成员的 ``value``，无单位时为 ``None``。
        field_display_type: 可选展示类型，取值为 ``FieldDisplayType`` 枚举成员的 ``value``；
            消费方根据 ``field_unit`` 换算原始值。
        option_values: 枚举候选值类型，为 ``CachedEnum`` 子类，无枚举时为 ``None``。
        rating_config: 评级阈值配置，按数组顺序匹配。
    """

    field_name: str
    field_alias: str = ""
    field_unit: str | None = None
    field_display_type: str | None = None
    option_values: type[HasChoicesCachedEnum] | None = None
    rating_config: tuple[RatingLevel, ...] = ()

    def children(self) -> Iterator["FieldSpec"]:
        """遍历本字段的直接子字段（类属性中名称全大写的 FieldSpec 实例）。"""
        return (
            candidate
            for name, candidate in vars(type(self)).items()
            if name.isupper() and isinstance(candidate, FieldSpec)
        )
