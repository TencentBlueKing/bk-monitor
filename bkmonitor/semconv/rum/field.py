"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from dataclasses import dataclass, field, replace
from collections.abc import Iterator
from typing import NotRequired, Protocol, TypedDict


class HasChoicesCachedEnum(Protocol):
    """存在 choices 方法的枚举协议（结构化子类型）。

    仅用于静态类型检查，约束 option_values 所引用的类必须实现
    choices() 类方法；无需实际继承本类即可通过类型检查。
    """

    @classmethod
    def choices(cls) -> list[tuple[str | int | float, str | int | float]]:
        """获取枚举值列表"""
        ...


class VirtualFieldConfig(TypedDict):
    """通过模板组合真实字段的查询维度。

    按固定文本从右拆分，配置方保证右侧成员及默认值不含相邻分隔文本。
    例如浏览器名称允许含空格，版本不含空格；返回值不额外转义。
    """

    fields: dict[str, str]
    template: str


class CompositeFieldItem(TypedDict):
    """复用字段元数据的单元格内容。"""

    field_name: str
    icon: NotRequired[str]


class CompositeFieldSection(TypedDict, total=False):
    """一行正文与标签；空值由消费方隐藏。"""

    items: list[CompositeFieldItem]
    badges: list[CompositeFieldItem]
    separator: str


class CompositeFieldConfig(TypedDict):
    """只组织展示，分析、过滤和排序仍使用成员字段。"""

    primary: str
    sections: list[CompositeFieldSection]


@dataclass(frozen=True, slots=True)
class RatingThreshold:
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
        field_type: 字段存储类型，如 ``"keyword"``、``"double"``、``"long"``；
            ``None`` 表示由 data_source 返回值决定，仅虚拟字段需显式设置。
        field_display_type: 可选展示类型，取值为 ``FieldDisplayType`` 枚举成员的 ``value``；
            消费方根据 ``field_unit`` 换算原始值。
        is_real: 是否为真实存储字段；``False`` 表示虚拟字段（由预计算层或前端提供），
            默认 ``True``。
        option_values: 枚举候选值类型，为 ``CachedEnum`` 子类，无枚举时为 ``None``。
        rating_config: 评级阈值配置，按数组顺序匹配。
        virtual_config: 可查询组合字段的成员绑定与模板。
        composite_config: 多行单元格配置，primary 指定默认分析与排序成员。
    """

    field_name: str
    field_alias: str = ""
    field_unit: str | None = None
    field_type: str | None = None
    field_display_type: str | None = None
    is_real: bool = True
    option_values: type[HasChoicesCachedEnum] | None = None
    rating_config: tuple[RatingThreshold, ...] = ()
    virtual_config: VirtualFieldConfig | None = None
    composite_config: CompositeFieldConfig | None = None
    _full_field_name: str = field(default="", init=False, repr=False, compare=False)

    def children(self) -> Iterator["FieldSpec"]:
        """遍历本字段的直接子字段（类属性中名称全大写的 FieldSpec 实例）。"""
        return (
            candidate
            for name, candidate in vars(type(self)).items()
            if name.isupper() and isinstance(candidate, FieldSpec)
        )

    def get_full_field_name(self) -> str:
        return self._full_field_name or self.field_name

    def bind(self, full_field_name: str) -> "FieldSpec":
        bound = replace(self)
        object.__setattr__(bound, "_full_field_name", full_field_name)
        return bound
