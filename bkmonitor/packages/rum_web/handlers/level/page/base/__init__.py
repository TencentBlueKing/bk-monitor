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
from typing import Any, Protocol
from dataclasses import dataclass

from rum_web.handlers.level.page.constants import SectionType


EMPTY_VALUE = "--"


class ItemProtocol(Protocol):
    def render(self, origin_data: dict[str, Any]) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class NamedKeyValueItem:
    field_name: str
    field_alias: str | None = None
    alias: str | None = None
    value: str | float | int | bool | None = None

    def render(self, origin_data: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {"field_name": self.field_name}
        if self.field_alias is not None:
            result["field_alias"] = self.field_alias
        if self.alias is not None:
            result["alias"] = self.alias
        result["value"] = self.value if self.value is not None else origin_data.get(self.field_name, EMPTY_VALUE)
        return result


@dataclass(frozen=True, slots=True)
class KeyValueItem:
    key: str
    value: str | float | int | bool | ItemProtocol | list[dict[str, Any]] | None = None
    items: list[ItemProtocol] | None = None

    def __post_init__(self):
        if self.value is not None and self.items is not None:
            raise ValueError(f"KeyValueItem(key={self.key!r}) 不能同时传入 value 和 items")

    def render(self, origin_data: dict[str, Any]) -> dict[str, Any]:
        if self.items is not None:
            if not isinstance(self.items, list):
                raise ValueError(f"Items {self.items} is not a valid list")
            merge_dict: dict[str, Any] = {}
            for i, child in enumerate(self.items):
                if hasattr(child, "render"):
                    merge_dict.update(child.render(origin_data))
            return {self.key: merge_dict}
        if isinstance(self.value, list):
            value_list = []
            for child in self.value:
                if hasattr(child, "render"):
                    value_list.append(child.render(origin_data))
                else:
                    value_list.append(child)
            return {self.key: value_list}

        if self.value is not None:
            # 静态值 → 直接使用
            return {self.key: self.value}
        # 无值 → 从 origin_data 动态取
        return {self.key: origin_data.get(self.key, EMPTY_VALUE)}


class BaseComponent(ABC):
    EMPTY_VALUE = EMPTY_VALUE

    def __init__(self, origin_data: dict[str, Any]):
        self.origin_data: dict[str, Any] = origin_data
        self.component_dict: dict[str, Any] = {}

    @abstractmethod
    def render(self) -> dict[str, Any]:
        return self.component_dict


class BaseOverview(BaseComponent):
    BADGES: list[NamedKeyValueItem] = []
    ITEMS: list[NamedKeyValueItem] = []

    def __init__(self, origin_data: dict[str, Any]):
        super().__init__(origin_data)
        self.component_dict.update()

    def _fill_title(self):
        self.component_dict["title"] = self.origin_data.get("span_name", self.EMPTY_VALUE)

    def _fill_badges(self):
        self.component_dict["badges"] = []
        for item in self.BADGES:
            self.component_dict["badges"].append(item.render(self.origin_data))

    def _fill_items(self):
        self.component_dict["items"] = []
        for item in self.ITEMS:
            self.component_dict["items"].append(item.render(self.origin_data))

    def render(self) -> dict[str, Any]:
        self._fill_title()
        self._fill_badges()
        self._fill_items()
        return self.component_dict


class BaseSection(BaseComponent):
    KEY: str
    TYPE: SectionType

    def render(self) -> dict[str, Any]:
        self.component_dict.update(
            {
                "key": self.KEY,
                "type": self.TYPE,
            }
        )
        return self.component_dict


class BasePage(BaseComponent):
    OVERVIEW: type[BaseOverview] | None = None
    SECTIONS: list[type[BaseSection]] = []

    def _fill_overview(self):
        if self.OVERVIEW is None:
            return
        self.component_dict["overview"] = self.OVERVIEW(self.origin_data).render()

    def _fill_sessions(self):
        self.component_dict["sessions"] = []
        for section in self.SECTIONS:
            self.component_dict["sessions"].append(section(self.origin_data).render())

    def render(self) -> dict[str, Any]:
        self._fill_overview()
        self._fill_sessions()
        return self.component_dict


__all__ = ["BasePage", "BaseSection", "BaseComponent", "NamedKeyValueItem", "KeyValueItem"]
