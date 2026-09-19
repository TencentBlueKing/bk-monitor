"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from rum_web.handlers.builder.base import BaseSection, DictItem, KeyValueItem
from rum_web.handlers.builder.span.base import SpanBuilder
from rum_web.handlers.builder.constants import SectionType
from rum_web.handlers.builder.span.base import (
    OVERVIEW_ATTRIBUTES_OUTCOME_TYPE,
    OVERVIEW_ELAPSED_TIME,
    SpanOverview,
)


class LongTaskSpanOverview(SpanOverview):
    BADGES = [
        OVERVIEW_ELAPSED_TIME,
        OVERVIEW_ATTRIBUTES_OUTCOME_TYPE,
    ]


class LongTaskKeyInfoSection(BaseSection):
    KEY = "key_info"
    TYPE = SectionType.SUMMARY_CARDS.value
    DATA = [
        DictItem(
            key="duration",
            items=[
                KeyValueItem(key="elapsed_time"),
                KeyValueItem(key="attributes.long_task.blocking_duration"),
            ],
        ),
        DictItem(
            key="action",
            items=[
                KeyValueItem(key="attributes.action.id"),
            ],
        ),
        DictItem(
            key="attribution",
            items=[
                KeyValueItem(key="attributes.long_task.entry_type"),
                KeyValueItem(key="attributes.long_task.name"),
            ],
        ),
    ]


class LongTaskSpanBuilder(SpanBuilder):
    OVERVIEW = LongTaskSpanOverview
    SECTIONS = [
        LongTaskKeyInfoSection,
    ]
