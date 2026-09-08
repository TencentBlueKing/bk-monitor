"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from functools import cached_property

from django.utils.translation import gettext_lazy as _

from constants.apm import CachedEnum


class FieldDisplayType(CachedEnum):
    """字段展示类型，用于告知前端如何渲染字段值"""

    DATETIME = "datetime"
    DURATION = "duration"

    @cached_property
    def label(self) -> str:
        return {
            self.DATETIME: _("日期"),
            self.DURATION: _("持续时长"),
        }.get(self, self.value)

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(member.value, member.label) for member in cls]


class FieldUnit(CachedEnum):
    US = "us"
    MS = "ms"
    BYTES = "bytes"

    @cached_property
    def label(self) -> str:
        return {
            self.US: _("微秒"),
            self.MS: _("毫秒"),
            self.BYTES: _("字节"),
        }.get(self, self.value)

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(member.value, member.label) for member in cls]


class SpanKind(CachedEnum):
    """Span 类型"""

    UNSPECIFIED = 0
    INTERNAL = 1
    SERVER = 2
    CLIENT = 3
    PRODUCER = 4
    CONSUMER = 5

    @cached_property
    def label(self) -> str:
        return str(
            {
                self.UNSPECIFIED: _("未定义"),
                self.INTERNAL: _("内部调用"),
                self.SERVER: _("同步被调"),
                self.CLIENT: _("同步主调"),
                self.PRODUCER: _("异步主调"),
                self.CONSUMER: _("异步被调"),
            }.get(self, str(self.value))
        )

    @classmethod
    def choices(cls) -> list[tuple[int, str]]:
        return [(member.value, member.label) for member in cls]


class SpanStatusCode(CachedEnum):
    """Span 状态码"""

    UNSET = 0
    OK = 1
    ERROR = 2

    @cached_property
    def label(self) -> str:
        return str(
            {
                self.UNSET: _("未设置"),
                self.OK: _("正常"),
                self.ERROR: _("异常"),
            }.get(self, str(self.value))
        )

    @classmethod
    def choices(cls) -> list[tuple[int, str]]:
        return [(member.value, member.label) for member in cls]
