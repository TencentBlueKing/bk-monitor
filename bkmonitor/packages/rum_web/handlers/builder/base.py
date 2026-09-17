"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Protocol

from rum_web.handlers.builder.utils import get_safe_number


EMPTY_VALUE: str = "--"


class ItemProtocol(Protocol):
    def render(self, flatten_data: dict[str, Any]) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class NamedKeyValueItem:
    field_name: str
    field_alias: str | None = None
    alias: str | None = None
    value: str | float | int | bool | None = None

    def render(self, flatten_data: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {"field_name": self.field_name}
        if self.field_alias is not None:
            result["field_alias"] = self.field_alias
        if self.alias is not None:
            result["alias"] = self.alias
        result["value"] = self.value if self.value is not None else flatten_data.get(self.field_name, EMPTY_VALUE)
        return result


@dataclass(frozen=True, slots=True)
class DictItem:
    key: str
    items: list[ItemProtocol]

    def render(self, flatten_data: dict[str, Any]) -> dict[str, Any]:
        merge_dict: dict[str, Any] = {}
        for child in self.items:
            merge_dict.update(child.render(flatten_data))
        return {self.key: merge_dict}


@dataclass(frozen=True, slots=True)
class KeyValueItem:
    key: str
    value: str | float | int | bool | list[dict | ItemProtocol] | None = None
    source: str | None = None

    def render(self, flatten_data: dict[str, Any]) -> dict[str, Any]:
        # source 优先：从 flatten_data 中按 source 取值
        if self.source is not None:
            return {self.key: flatten_data.get(self.source, EMPTY_VALUE)}
        if isinstance(self.value, list):
            value_list = []
            for child in self.value:
                if hasattr(child, "render"):
                    value_list.append(child.render(flatten_data))
                else:
                    value_list.append(child)
            return {self.key: value_list}
        if self.value is not None:
            # 静态值 → 直接使用
            return {self.key: self.value}
        # 无值 → 从 flatten_data 按 key 动态取
        return {self.key: flatten_data.get(self.key, EMPTY_VALUE)}


class BaseComponent(ABC):
    def __init__(self, flatten_data: dict[str, Any]):
        self.flatten_data: dict[str, Any] = flatten_data
        self.component_dict: dict[str, Any] = {}

    @abstractmethod
    def render(self) -> dict[str, Any]:
        return self.component_dict


class BaseOverview(BaseComponent):
    BADGES: list[NamedKeyValueItem] = []
    ITEMS: list[NamedKeyValueItem] = []

    def _fill_title(self):
        self.component_dict["title"] = self.flatten_data.get("span_name", EMPTY_VALUE)

    def _fill_badges(self):
        self.component_dict["badges"] = []
        for item in self.BADGES:
            self.component_dict["badges"].append(item.render(self.flatten_data))

    def _fill_items(self):
        self.component_dict["items"] = []
        for item in self.ITEMS:
            self.component_dict["items"].append(item.render(self.flatten_data))

    def render(self) -> dict[str, Any]:
        self._fill_title()
        self._fill_badges()
        self._fill_items()
        return self.component_dict


class BaseSection(BaseComponent):
    KEY: str
    TYPE: str
    DATA: list[ItemProtocol] | None = None
    ITEMS: list[ItemProtocol] | None = None

    def numeric_or_none(self, key: str) -> int | float | None:
        return get_safe_number(self.flatten_data.get(key), None)

    def _fill_data(self):
        if self.DATA is None:
            return
        self.component_dict["data"] = {}
        for item in self.DATA:
            self.component_dict["data"].update(item.render(self.flatten_data))

    def _fill_items(self):
        if self.ITEMS is None:
            return
        self.component_dict["items"] = []
        for item in self.ITEMS:
            self.component_dict["items"].append(item.render(self.flatten_data))

    def render(self) -> dict[str, Any] | None:
        self.component_dict.update(
            {
                "key": self.KEY,
                "type": self.TYPE,
            }
        )
        self._fill_data()
        self._fill_items()
        if not self.component_dict.get("data") and not self.component_dict.get("items"):
            return None
        return self.component_dict


__all__ = [
    "BaseSection",
    "BaseComponent",
    "BaseOverview",
    "NamedKeyValueItem",
    "KeyValueItem",
    "DictItem",
    "EMPTY_VALUE",
]
