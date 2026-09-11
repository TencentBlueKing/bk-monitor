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
from dataclasses import dataclass
from django.utils.translation import gettext_lazy as _


from semconv.rum.constants import RumSpanType
from rum_web.handlers.level.page.base import NamedKeyValueItem, BaseOverview


# ── Overview 标题 ──────────────────────────────────────────────────────────────
OVERVIEW_TITLE = NamedKeyValueItem(field_name="span_name")

# ── 通用 Badge 字段 ────────────────────────────────────────────────────────────
OVERVIEW_ELAPSED_TIME = NamedKeyValueItem(field_name="elapsed_time")
OVERVIEW_ATTRIBUTES_RESOURCE_TYPE = NamedKeyValueItem(field_name="attributes.resource.type")
OVERVIEW_ATTRIBUTES_HTTP_RESPONSE_STATUS_CODE = NamedKeyValueItem(field_name="attributes.http.response.status_code")

# ── 通用 Item 字段 ─────────────────────────────────────────────────────────────
OVERVIEW_APP_NAME = NamedKeyValueItem(field_name="app_name")
OVERVIEW_ATTRIBUTES_VIEW_URL_TEMPLATE = NamedKeyValueItem(field_name="attributes.view.url_template")
OVERVIEW_ATTRIBUTES_VIEW_URL = NamedKeyValueItem(field_name="attributes.view.url")
OVERVIEW_ATTRIBUTES_SESSION_ID = NamedKeyValueItem(field_name="attributes.session.id")
OVERVIEW_ATTRIBUTES_VIEW_ID = NamedKeyValueItem(field_name="attributes.view.id")
OVERVIEW_START_TIME = NamedKeyValueItem(field_name="start_time")
OVERVIEW_END_TIME = NamedKeyValueItem(field_name="end_time")
OVERVIEW_ATTRIBUTES_USER_ID = NamedKeyValueItem(field_name="attributes.user.id")
OVERVIEW_RESOURCE_DEPLOYMENT_ENVIRONMENT_NAME = NamedKeyValueItem(field_name="resource.deployment.environment.name")


@dataclass(frozen=True, slots=True)
class SpanTypeItem(NamedKeyValueItem):
    field_name: str = "display.span_type"
    field_alias: str = _("类型")

    def render(self, origin_data: dict[str, Any]) -> Any:
        result: dict[str, Any] = {"field_name": self.field_name, "field_alias": self.field_alias}
        if origin_data.get("attributes.span_type") == RumSpanType.RESOURCE.value:
            resource_type = origin_data.get("attributes.resource.type", "")
            result["alias"] = result["value"] = (
                f"{RumSpanType.RESOURCE.value}({resource_type})" if resource_type else RumSpanType.RESOURCE.value
            )
        else:
            result["alias"] = result["value"] = origin_data.get("span_type", "")
        return result


class SpanOverview(BaseOverview):
    BADGES: list[NamedKeyValueItem] = []
    ITEMS: list[NamedKeyValueItem] = [
        SpanTypeItem(),
        OVERVIEW_APP_NAME,
        OVERVIEW_ATTRIBUTES_VIEW_URL_TEMPLATE,
        OVERVIEW_ATTRIBUTES_SESSION_ID,
        OVERVIEW_ATTRIBUTES_VIEW_ID,
        OVERVIEW_START_TIME,
        OVERVIEW_END_TIME,
        OVERVIEW_ATTRIBUTES_USER_ID,
        OVERVIEW_RESOURCE_DEPLOYMENT_ENVIRONMENT_NAME,
    ]

    def __init__(self, origin_data: dict[str, Any]):
        super().__init__(origin_data)

    def _fill_title(self):
        self.component_dict["title"] = self.origin_data.get("span_name", self.EMPTY_VALUE)

    def _fill_badges(self):
        self.component_dict.setdefault("badges", [])
        for item in self.BADGES:
            self.component_dict["badges"].append(item.render(self.origin_data))

    def _fill_items(self):
        self.component_dict.setdefault("items", [])
        for item in self.ITEMS:
            self.component_dict["items"].append(item.render(self.origin_data))

    def render(self) -> dict[str, Any]:
        self._fill_title()
        self._fill_badges()
        self._fill_items()
        return self.component_dict
