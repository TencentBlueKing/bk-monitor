"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.utils.translation import gettext_lazy as _

from semconv.rum.field import FieldSpec


PAGE = FieldSpec(
    field_name="display.page",
    field_alias=_("页面"),
    field_type="keyword",
    is_real=False,
    composite_config={
        "primary": "attributes.view.url_template",
        "sections": [
            {
                "items": [{"field_name": "attributes.view.url_template"}],
                "badges": [
                    {"field_name": "virtual.viewport", "icon": "icon-monitor icon-mc-tv"},
                    {"field_name": "attributes.view.loading_type"},
                ],
            },
            {"items": [{"field_name": "attributes.view.url", "icon": "icon-monitor icon-mc-link"}]},
        ],
    },
)
ENVIRONMENT = FieldSpec(
    field_name="display.environment",
    field_alias=_("客户端环境"),
    field_type="keyword",
    is_real=False,
    composite_config={
        "primary": "virtual.browser",
        "sections": [
            {
                "items": [
                    {"field_name": "virtual.browser"},
                    {"field_name": "resource.user_agent.os.name"},
                ],
                "separator": " · ",
            },
            {"items": [{"field_name": "virtual.network"}]},
        ],
    },
)
SPAN_NAME = FieldSpec(
    field_name="display.span_name",
    field_alias=_("Span 名称"),
    field_type="keyword",
    is_real=False,
    composite_config={
        "primary": "span_name",
        "sections": [
            {
                "items": [{"field_name": "span_name"}],
                "badges": [
                    {"field_name": "virtual.span_kind"},
                    {"field_name": "attributes.http.request.method"},
                    {"field_name": "attributes.http.response.status_code"},
                ],
            },
            {"items": [{"field_name": "attributes.url.full", "icon": "icon-monitor icon-mc-link"}]},
        ],
    },
)
RESOURCE_SIZE = FieldSpec(
    field_name="display.resource_size",
    field_alias=_("资源大小"),
    field_type="keyword",
    is_real=False,
    composite_config={
        "primary": "attributes.resource.size",
        "sections": [
            {"items": [{"field_name": "attributes.resource.size"}]},
            {"items": [{"field_name": "display.resource.delivery"}]},
        ],
    },
)
RESOURCE_DELIVERY = FieldSpec(
    field_name="display.resource.delivery",
    field_alias=_("资源获取说明"),
    field_type="keyword",
    is_real=False,
)
