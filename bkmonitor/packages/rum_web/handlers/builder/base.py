"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from django.utils.functional import Promise

from rum_web.handlers.builder.constants import SectionType
from rum_web.handlers.builder.utils import get_safe_number, phase


class ItemProtocol(Protocol):
    def render(self, flatten_data: dict[str, Any]) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class NamedKeyValueItem:
    field_name: str
    field_alias: str | Promise | None = None

    def render(self, flatten_data: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {"field_name": self.field_name, "value": flatten_data.get(self.field_name)}
        if self.field_alias is not None:
            result["field_alias"] = self.field_alias
        return result


@dataclass(frozen=True, slots=True)
class DictItem:
    key: str
    items: Sequence[ItemProtocol]

    def render(self, flatten_data: dict[str, Any]) -> dict[str, Any]:
        return {self.key: {key: value for item in self.items for key, value in item.render(flatten_data).items()}}


@dataclass(frozen=True, slots=True)
class KeyValueItem:
    key: str
    source: str | None = None

    def render(self, flatten_data: dict[str, Any]) -> dict[str, Any]:
        return {self.key: flatten_data.get(self.source or self.key)}


def group(key: str, *fields: str | ItemProtocol) -> DictItem:
    return DictItem(key, tuple(KeyValueItem(field) if isinstance(field, str) else field for field in fields))


class BaseComponent:
    def __init__(self, flatten_data: dict[str, Any]):
        self.flatten_data = flatten_data


class BaseOverview(BaseComponent):
    BADGES: tuple[NamedKeyValueItem, ...] = ()
    ITEMS: tuple[NamedKeyValueItem, ...] = ()

    def render(self) -> dict[str, Any]:
        return {
            "title": self.flatten_data.get("span_name"),
            "badges": [item.render(self.flatten_data) for item in self.BADGES],
            "items": [item.render(self.flatten_data) for item in self.ITEMS],
        }


class BaseSection(BaseComponent):
    KEY: str
    TYPE: str
    DATA: tuple[ItemProtocol, ...] | None = None
    ITEMS: tuple[NamedKeyValueItem, ...] | None = None

    def numeric_or_none(self, key: str) -> int | float | None:
        return get_safe_number(self.flatten_data.get(key), None)

    def get_data(self) -> dict[str, Any] | None:
        if self.DATA is not None:
            return {key: value for item in self.DATA for key, value in item.render(self.flatten_data).items()}

    def render(self) -> dict[str, Any] | None:
        result: dict[str, Any] = {"key": self.KEY, "type": self.TYPE}
        if (data := self.get_data()) is not None:
            result["data"] = data
        if self.ITEMS is not None:
            result["items"] = [item.render(self.flatten_data) for item in self.ITEMS]
        return result if result.get("data") or result.get("items") else None


class KeyInfoSection(BaseSection):
    KEY = "key_info"
    TYPE = SectionType.SUMMARY_CARDS.value


class WaterfallSection(BaseSection):
    TYPE = SectionType.WATERFALL.value
    PHASE_ALIASES: dict[str, Any]
    MIN_START: int | None = None

    def phases(
        self, specs: Iterable[tuple[str, int | float | None, int | float | None]]
    ) -> list[dict[str, Any] | None]:
        return [
            phase(key, self.PHASE_ALIASES[key], start, duration, min_start=self.MIN_START)
            for key, start, duration in specs
        ]
