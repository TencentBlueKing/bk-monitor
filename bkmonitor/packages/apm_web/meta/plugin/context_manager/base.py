# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import typing
from dataclasses import dataclass
from enum import Enum


class ScopeType(Enum):
    INNER = "inner"
    OPEN = "open"


@dataclass
class Field:
    name: str
    scope: str
    value: typing.Any

    @property
    def key(self) -> str:
        return f"{self.scope}-{self.name}"


class FieldManager:
    _FIELDS: typing.Dict[str, Field] = {}

    @classmethod
    def register(cls, meta):
        try:
            field_obj: Field = Field(name=meta.name, scope=meta.scope, value=meta.value)
        except AttributeError as e:
            raise AttributeError(f"lost attrs -> {e}")

        cls._FIELDS[field_obj.key] = field_obj

    @classmethod
    def get_context(cls, scope: str) -> typing.Dict[str, typing.Any]:
        context: typing.Dict[str, str] = {}
        for field in cls._FIELDS.values():
            if field.scope != scope:
                continue
            context[field.name] = field.value
        return context


class FieldMeta(type):
    def __new__(cls, name, bases, dct):
        parents = [b for b in bases if isinstance(b, FieldMeta)]
        if not parents:
            super().__new__(cls, name, bases, dct)

        new_cls = super().__new__(cls, name, bases, dct)
        try:
            FieldManager.register(new_cls.Meta)
        except AttributeError:
            raise AttributeError("Meta class is required")

        return new_cls
