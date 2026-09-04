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

SPAN_TYPE_COMMON_DISPLAY_FIELDS = [
    "span_name",
    "attributes.span_type",
    "end_time",
    "elapsed_time",
    "status.code",
    "attributes.view.url_template",
    "attributes.user.id",
]


class RumSpanType(CachedEnum):
    """RUM Span 数据类型"""

    VIEW = "view"
    RESOURCE = "resource"
    ERROR = "error"
    VITAL = "vital"
    LONG_TASK = "long_task"
    ACTION = "action"
    WEBSOCKET = "websocket"
    CUSTOM = "custom"

    @cached_property
    def label(self) -> str:
        return str(
            {
                self.VIEW: _("视图"),
                self.RESOURCE: _("资源"),
                self.ERROR: _("错误"),
                self.VITAL: _("网页指标"),
                self.LONG_TASK: _("长任务"),
                self.ACTION: _("用户交互"),
                self.WEBSOCKET: "WebSocket",
                self.CUSTOM: _("自定义事件"),
            }.get(self, str(self.value))
        )

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(member.value, member.label) for member in cls]

    @classmethod
    def values(cls) -> list[str]:
        return [member.value for member in cls]

    @cached_property
    def display_fields(self) -> list[str]:
        return {
            self.VIEW: [*SPAN_TYPE_COMMON_DISPLAY_FIELDS],
            self.RESOURCE: [
                *SPAN_TYPE_COMMON_DISPLAY_FIELDS,
                "attributes.resource.type",
                "attributes.http.request.method",
            ],
            self.ERROR: [*SPAN_TYPE_COMMON_DISPLAY_FIELDS, "attributes.error.source"],
            self.VITAL: [*SPAN_TYPE_COMMON_DISPLAY_FIELDS, "attributes.vital.metric", "attributes.vital.value"],
            self.LONG_TASK: [
                *SPAN_TYPE_COMMON_DISPLAY_FIELDS,
                "attributes.long_task.name",
                "attributes.long_task.entry_type",
            ],
            self.ACTION: [*SPAN_TYPE_COMMON_DISPLAY_FIELDS, "attributes.action.id", "attributes.action.type"],
            self.WEBSOCKET: [*SPAN_TYPE_COMMON_DISPLAY_FIELDS],
            self.CUSTOM: [*SPAN_TYPE_COMMON_DISPLAY_FIELDS],
        }.get(self, SPAN_TYPE_COMMON_DISPLAY_FIELDS)
