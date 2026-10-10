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
from typing import Any

from rum_web.handlers.builder.base import KeyInfoSection, KeyValueItem, group
from rum_web.handlers.builder.span.base import SpanBuilder, SpanOverview, named


@dataclass(frozen=True, slots=True)
class ExceptionTypeItem(KeyValueItem):
    key: str = "events.attributes.exception.type"

    def render(self, flatten_data: dict[str, Any]) -> dict[str, Any]:
        value = flatten_data.get(self.key)
        return {self.key: (value[0] if value else None) if isinstance(value, list) else value}


class ErrorSpanOverview(SpanOverview):
    BADGES = named("attributes.outcome.type")


class ErrorKeyInfoSection(KeyInfoSection):
    DATA = (
        group("error_type", ExceptionTypeItem()),
        group("source", "attributes.code.filepath", "attributes.code.lineno", "attributes.code.column"),
    )


class ErrorSpanBuilder(SpanBuilder):
    OVERVIEW = ErrorSpanOverview
    SECTIONS = (ErrorKeyInfoSection,)
