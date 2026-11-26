"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from semconv.rum.field import CompositeFieldConfig


PAGE: CompositeFieldConfig = {
    "sections": [
        {
            "items": [{"field_name": "attributes.view.url_template"}],
            "badges": [
                {"field_name": "virtual.viewport"},
                {"field_name": "attributes.view.loading_type"},
            ],
        },
        {"items": [{"field_name": "attributes.view.url", "type": "link"}]},
    ],
}
ENVIRONMENT: CompositeFieldConfig = {
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
}
SESSION: CompositeFieldConfig = {
    "sections": [
        {"items": [{"field_name": "attributes.session.id"}]},
        {
            "items": [{"field_name": "enter_url_template"}],
            "badges": [{"field_name": "virtual.viewport"}],
        },
    ],
}
_RESOURCE = {"attributes.span_type": ["resource"]}
_HTTP_REQUEST = {**_RESOURCE, "attributes.resource.type": ["xhr", "fetch"]}
_ACTION = {"attributes.span_type": ["action"]}


SPAN_NAME: CompositeFieldConfig = {
    "sections": [
        {
            "items": [{"field_name": "span_name"}],
            "badges": [
                {
                    "field_name": "virtual.viewport",
                    "show_if": {"attributes.span_type": ["view"]},
                },
                {"field_name": "attributes.resource.type", "show_if": _RESOURCE},
                {"field_name": "attributes.http.request.method", "show_if": _HTTP_REQUEST},
                {"field_name": "attributes.http.response.status_code", "show_if": _HTTP_REQUEST},
                {
                    "field_name": "attributes.long_task.entry_type",
                    "show_if": {"attributes.span_type": ["long_task"]},
                },
                {"field_name": "attributes.action.type", "show_if": _ACTION},
                {"field_name": "attributes.action.frustration.type", "show_if": _ACTION},
                {"field_name": "events.attributes.exception.type", "show_if": {"attributes.span_type": ["error"]}},
            ],
        },
        {
            "items": [
                {"field_name": "attributes.action.target.tag", "show_if": _ACTION},
                {
                    "field_name": "attributes.view.url",
                    "type": "link",
                    "show_if": {"attributes.span_type": ["view"]},
                },
                {"field_name": "attributes.url.full", "type": "link", "show_if": _RESOURCE},
            ],
        },
    ],
}
ERROR_LOCATION: CompositeFieldConfig = {
    "sections": [
        {
            "items": [
                {"field_name": "attributes.code.filepath"},
                {"field_name": "attributes.code.lineno"},
                {"field_name": "attributes.code.column"},
            ],
            "separator": ":",
        },
        {"items": [{"field_name": "attributes.error.source"}]},
    ],
}
RESOURCE_SIZE: CompositeFieldConfig = {
    "sections": [
        {"items": [{"field_name": "attributes.resource.size"}]},
        {"items": [{"field_name": "attributes.resource.delivery_type"}]},
    ],
}
