"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from collections.abc import Mapping
from functools import reduce
from itertools import chain, product
from operator import or_
import re
from string import Formatter
from typing import Any

from django.db.models import Q

from semconv.rum.field import FieldSpec, VirtualFieldConfig


class VirtualField:
    """按模板展示成员，按命名分组反解到原始字段。"""

    def __init__(self, config: VirtualFieldConfig, field_specs: Mapping[str, FieldSpec]):
        self.fields = config["fields"]
        self.template = config["template"]
        self.pattern = re.compile(config["parse_pattern"], re.DOTALL)
        slots = [slot for _, slot, _, _ in Formatter().parse(self.template) if slot is not None]
        bindings = {f"{name}|--": field for name, field in self.fields.items()}
        if not slots or set(slots) != bindings.keys() or self.pattern.groupindex.keys() != self.fields.keys():
            raise ValueError("虚拟字段的模板、反解分组与字段绑定不一致")
        self.slots = {slot: bindings[slot] for slot in slots}
        self.field_names = list(self.slots.values())
        self.types = {name: int if field_specs[name].field_type == "long" else str for name in self.field_names}

    def format(self, flatten_data: Mapping[str, Any]) -> str | None:
        values = {
            slot: self.types[field](raw)
            for slot, field in self.slots.items()
            if (raw := flatten_data.get(field)) not in (None, "")
        }
        if not values:
            return None
        return self.template.format_map({slot: values.get(slot, "--") for slot in self.slots})

    def _match(self, value: str) -> dict[str, str | int | None] | None:
        match = self.pattern.fullmatch(value)
        if match is None:
            return None
        try:
            members = {
                field: None if (text := match[name]) in (None, "--") else self.types[field](text)
                for name, field in self.fields.items()
            }
        except ValueError:
            return None
        return members if self.format(members) == value else None

    def _member_conditions(self, field: str, value: str | int | None, exclude: bool) -> list[Q]:
        missing = Q(**{f"{field}__nexists": [""]})
        if value is not None:
            return [missing, Q(**{f"{field}__neq": value})] if exclude else [Q(**{f"{field}__eq": value})]
        if exclude:
            present = Q(**{f"{field}__exists": [""]})
            return [present] if self.types[field] is int else [present & Q(**{f"{field}__neq": ""})]
        return [missing] if self.types[field] is int else [missing, Q(**{f"{field}__eq": ""})]

    def build_filter(self, *values: str, exclude: bool = False, match_all: bool = False) -> Q:
        """同一组合的成员取 AND；不同展示值取 OR。"""
        if not values:
            return Q()
        distinct = dict.fromkeys(values)
        condition = Q()
        for value in distinct if not match_all or len(distinct) == 1 else ():
            match = self._match(value)
            if match is None:
                continue
            members = [self._member_conditions(field, raw, exclude) for field, raw in match.items()]
            if exclude:
                # 每个展示值都要排除；任一成员不同就排除了当前组合。
                condition &= reduce(or_, chain.from_iterable(members))
            else:
                # 组内同时匹配。先展开空值的两种表示，以便多个组合可以直接取 OR。
                for combination in product(*members):
                    condition |= Q(*combination)
        if not exclude and not condition:
            field = self.field_names[0]
            return Q(**{f"{field}__exists": [""]}) & Q(**{f"{field}__nexists": [""]})
        return condition


def get_virtual_fields(fields: list[FieldSpec]) -> dict[str, VirtualField]:
    field_specs: dict[str, FieldSpec] = {field.get_full_field_name(): field for field in fields}
    return {
        name: VirtualField(config, field_specs)
        for name, field in field_specs.items()
        if (config := field.extra_config.get("virtual")) is not None
    }
