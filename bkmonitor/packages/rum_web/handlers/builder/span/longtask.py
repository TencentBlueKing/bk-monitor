"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any

from rum_web.handlers.builder.base import KeyInfoSection, KeyValueItem, group
from rum_web.handlers.builder.span.base import SpanBuilder, SpanOverview, named
from semconv.rum.constants import LongTaskEntryType


class ActionIdsItem(KeyValueItem):
    def render(self, flatten_data: dict[str, Any]) -> dict[str, Any]:
        if self.key in flatten_data:
            return super().render(flatten_data)
        if "attributes.action.id" in flatten_data:
            return {"attributes.action.id": flatten_data["attributes.action.id"]}
        return {}


class LongTaskNameItem(KeyValueItem):
    def render(self, flatten_data: dict[str, Any]) -> dict[str, Any]:
        if flatten_data.get("attributes.long_task.entry_type") == LongTaskEntryType.LONG_TASK.value:
            return super().render(flatten_data)
        return {}


class LongTaskSpanOverview(SpanOverview):
    BADGES = named("elapsed_time", "attributes.outcome.type")


class LongTaskKeyInfoSection(KeyInfoSection):
    DATA = (
        group("duration", "elapsed_time", "attributes.long_task.blocking_duration"),
        group("action", ActionIdsItem("attributes.action.ids")),
        group("attribution", "attributes.long_task.entry_type", LongTaskNameItem("attributes.long_task.name")),
    )


class LongTaskSpanBuilder(SpanBuilder):
    OVERVIEW = LongTaskSpanOverview
    SECTIONS = (LongTaskKeyInfoSection,)
