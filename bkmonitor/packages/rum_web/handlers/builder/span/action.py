"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from rum_web.handlers.builder.base import KeyInfoSection, group
from rum_web.handlers.builder.span.base import SpanBuilder, SpanOverview, named


class ActionSpanOverview(SpanOverview):
    BADGES = named("elapsed_time", "attributes.action.type", "attributes.outcome.type")


class ActionKeyInfoSection(KeyInfoSection):
    DATA = (
        group("interaction", "attributes.action.type"),
        group("target", "attributes.action.target.name", "attributes.action.target.tag"),
    )


class ActionSpanBuilder(SpanBuilder):
    OVERVIEW = ActionSpanOverview
    SECTIONS = (ActionKeyInfoSection,)
