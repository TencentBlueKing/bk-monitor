"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
import re
from typing import Any, Protocol, cast

from django.db.models import Q

from semconv.rum.field import FieldSpec, VirtualFieldConfig


class FieldCatalog(Protocol):
    @classmethod
    def fields(cls) -> list[FieldSpec]: ...


@dataclass(frozen=True, slots=True)
class Placeholder:
    name: str
    default: str | None = None


@dataclass(frozen=True, slots=True)
class OptionalPart:
    parts: tuple[str | Placeholder, ...]


Part = str | Placeholder | OptionalPart


def is_empty(value: Any) -> bool:
    return value is None or value == ""


def normalize_filter(condition: Q) -> Q:
    """将虚拟条件的取反下推到叶子，兼容不保留 Q.negated 的查询序列化。"""

    def normalize(node: Q, negated: bool = False) -> Q:
        negated ^= node.negated
        connector: str = node.connector
        if negated:
            connector = Q.OR if connector == Q.AND else Q.AND
        children: list[Q | tuple[str, Any]] = []
        for child in node.children:
            if isinstance(child, Q):
                children.append(normalize(child, negated))
                continue
            if not negated:
                children.append(child)
                continue
            lookup, value = child
            name, operation = lookup.rsplit("__", 1)
            if operation == "eq":
                # SQL 中 NULL != value 不成立，取补集时显式保留字段缺失的记录。
                children.append(Q(**{f"{name}__nexists": [""]}) | Q(**{f"{name}__neq": value}))
            else:
                inverse: str = {"neq": "eq", "exists": "nexists", "nexists": "exists"}[operation]
                children.append((f"{name}__{inverse}", value))
        return Q(*children, _connector=connector)

    return normalize(condition)


def _parse_template(template: str) -> tuple[Part, ...]:
    """将固定文本、占位符和一层可选片段编译成节点。"""
    position: int = 0

    def parse(optional: bool = False) -> tuple[Part, ...]:
        nonlocal position
        parts: list[Part] = []
        literal: str = ""
        while position < len(template):
            char: str = template[position]
            pair: str = template[position : position + 2]
            if pair in ("{{", "}}", "[[", "]]"):
                literal += char
                position += 2
                continue
            if char not in "{}[]":
                literal += char
                position += 1
                continue
            if literal:
                parts.append(literal)
                literal = ""
            position += 1
            if char == "{":
                end: int = template.find("}", position)
                if end < 0:
                    raise ValueError("虚拟字段模板的占位符未闭合")
                name, separator, default = template[position:end].partition("|")
                if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
                    raise ValueError(f"无效的模板变量：{name}")
                parts.append(Placeholder(name, default if separator else None))
                position = end + 1
            elif char == "[" and not optional:
                parts.append(OptionalPart(parse(optional=True)))
            elif char == "]" and optional:
                return tuple(parts)
            else:
                raise ValueError("虚拟字段模板含未配对或嵌套的括号")
        if optional:
            raise ValueError("虚拟字段模板的可选片段未闭合")
        if literal:
            parts.append(literal)
        return tuple(parts)

    return parse()


def _placeholders(parts: tuple[Part, ...]) -> Iterator[Placeholder]:
    for part in parts:
        if isinstance(part, Placeholder):
            yield part
        elif isinstance(part, OptionalPart):
            yield from _placeholders(part.parts)


class VirtualField:
    """同一模板负责生成组合值和展开等价的原字段过滤条件。"""

    INTEGER_TYPES = {"byte", "short", "integer", "long", "unsigned_long"}
    FLOAT_TYPES = {"half_float", "float", "double", "scaled_float"}

    def __init__(self, config: VirtualFieldConfig, field_specs: Mapping[str, FieldSpec]):
        self.parts: tuple[Part, ...] = _parse_template(config["template"])
        names: list[str] = list(dict.fromkeys(part.name for part in _placeholders(self.parts)))
        if not names or set(names) != set(config["fields"]):
            raise ValueError("虚拟字段模板变量与字段绑定不一致")
        self.fields: dict[str, str] = config["fields"]
        self.field_specs: dict[str, FieldSpec] = {name: field_specs[field] for name, field in self.fields.items()}
        self.field_names: list[str] = list(dict.fromkeys(self.fields[name] for name in names))
        self.branches: list[tuple[tuple[str | Placeholder, ...], Q]] = self._expand_parts()
        for parts, _ in self.branches:
            for previous, current in zip(parts, parts[1:]):
                if isinstance(previous, Placeholder) and isinstance(current, Placeholder):
                    raise ValueError("虚拟字段模板的成员之间必须有固定文本边界")

    def _empty_filter(self, name: str) -> Q:
        field_name: str = self.fields[name]
        missing: Q = Q(**{f"{field_name}__nexists": [""]})
        field_type: str = self.field_specs[name].field_type or "keyword"
        if field_type not in self.INTEGER_TYPES | self.FLOAT_TYPES | {"boolean"}:
            missing |= Q(**{f"{field_name}__eq": ""})
        return missing

    def exists_filter(self) -> Q:
        """至少一个成员非空；全空判断优先于模板默认值。"""
        return ~Q(*(self._empty_filter(name) for name in self.fields))

    def _false_filter(self) -> Q:
        field: str = self.field_names[0]
        return Q(**{f"{field}__exists": [""]}) & Q(**{f"{field}__nexists": [""]})

    def _expand_parts(self) -> list[tuple[tuple[str | Placeholder, ...], Q]]:
        branches: list[tuple[tuple[str | Placeholder, ...], Q]] = [((), Q())]
        for part in self.parts:
            if not isinstance(part, OptionalPart):
                branches = [(parts + (part,), condition) for parts, condition in branches]
                continue
            required: list[Placeholder] = [member for member in _placeholders(part.parts) if member.default is None]
            visible: Q = Q(*(~self._empty_filter(member.name) for member in required))
            present = [(parts + part.parts, condition & visible) for parts, condition in branches]
            absent = [(parts, condition & ~visible) for parts, condition in branches] if required else []
            branches = present + absent
        return branches

    def _coerce(self, name: str, value: Any) -> str | int | float | bool:
        field_type: str = self.field_specs[name].field_type or "keyword"
        if field_type in self.INTEGER_TYPES:
            return int(value)
        if field_type in self.FLOAT_TYPES:
            return float(value)
        if field_type == "boolean":
            return {"true": True, "false": False, "1": True, "0": False}[str(value).lower()]
        return str(value)

    @staticmethod
    def _stringify(value: str | int | float | bool) -> str:
        return str(value).lower() if isinstance(value, bool) else str(value)

    def format(self, flatten_data: Mapping[str, Any]) -> str | None:
        """输入扁平原始记录，输出可直接回传过滤接口的字符串。"""
        if all(is_empty(flatten_data.get(field)) for field in self.field_names):
            return None
        result: list[str] = []
        for part in self.parts:
            if isinstance(part, OptionalPart):
                if any(
                    member.default is None and is_empty(flatten_data.get(self.fields[member.name]))
                    for member in _placeholders(part.parts)
                ):
                    continue
                pieces: tuple[str | Placeholder, ...] = part.parts
            else:
                pieces = (part,)
            for piece in pieces:
                if isinstance(piece, str):
                    result.append(piece)
                    continue
                raw: Any = flatten_data.get(self.fields[piece.name])
                value: str = piece.default or "" if is_empty(raw) else self._stringify(self._coerce(piece.name, raw))
                result.append(value)
        return "".join(result)

    def _member_filter(self, part: Placeholder, text: str) -> Q | None:
        branches: list[Q] = []
        if text == (part.default or ""):
            branches.append(self._empty_filter(part.name))
        if text:
            try:
                value: str | int | float | bool = self._coerce(part.name, text)
            except (ValueError, KeyError):
                pass
            else:
                if self._stringify(value) == text:
                    branches.append(Q(**{f"{self.fields[part.name]}__eq": value}))
        return Q(*branches, _connector=Q.OR) if branches else None

    def _match(self, parts: tuple[str | Placeholder, ...], value: str) -> Q | None:
        """按模板从右拆分；配置方保证右侧成员及默认值不含相邻分隔文本。"""
        condition: Q = Q()
        index: int = len(parts) - 1
        while index >= 0:
            part: str | Placeholder = parts[index]
            if isinstance(part, str):
                if not value.endswith(part):
                    return None
                value = value[: -len(part)]
                index -= 1
                continue
            if index == 0:
                text, value = value, ""
                index -= 1
            elif index == 1:
                prefix: str = cast(str, parts[0])
                if not value.startswith(prefix):
                    return None
                text, value = value[len(prefix) :], ""
                index -= 2
            else:
                boundary: str = cast(str, parts[index - 1])
                value, separator, text = value.rpartition(boundary)
                if not separator:
                    return None
                index -= 2
            member: Q | None = self._member_filter(part, text)
            if member is None:
                return None
            condition &= member
        return condition if not value else None

    def build_filter(self, value: str) -> Q:
        """按可选片段的显示与隐藏分支展开原字段条件。"""
        branches: list[Q] = []
        for parts, condition in self.branches:
            match: Q | None = self._match(parts, value)
            if match is not None:
                branches.append(condition & match)
        matched: Q = Q(*branches, _connector=Q.OR) if branches else self._false_filter()
        return self.exists_filter() & matched


def get_virtual_fields(spec: type[FieldCatalog]) -> dict[str, VirtualField]:
    field_specs: dict[str, FieldSpec] = {field.get_full_field_name(): field for field in spec.fields()}
    return {
        name: VirtualField(field.virtual_config, field_specs)
        for name, field in field_specs.items()
        if field.virtual_config is not None
    }
