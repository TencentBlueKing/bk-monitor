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


SPAN_KIND = FieldSpec(
    field_name="virtual.span_kind",
    field_alias=_("事件类型"),
    field_type="keyword",
    is_real=False,
    virtual_config={
        "fields": {"span_type": "attributes.span_type", "resource_type": "attributes.resource.type"},
        "template": "{span_type|--}[（{resource_type}）]",
    },
)
VIEWPORT = FieldSpec(
    field_name="virtual.viewport",
    field_alias=_("视口"),
    field_type="keyword",
    is_real=False,
    virtual_config={
        "fields": {"width": "attributes.browser.viewport.width", "height": "attributes.browser.viewport.height"},
        "template": "{width|--} x {height|--}",
    },
)
BROWSER = FieldSpec(
    field_name="virtual.browser",
    field_alias=_("浏览器"),
    field_type="keyword",
    is_real=False,
    virtual_config={
        "fields": {"name": "resource.user_agent.name", "version": "resource.user_agent.version"},
        "template": "{name|--} {version|--}",
    },
)
NETWORK = FieldSpec(
    field_name="virtual.network",
    field_alias=_("网络质量"),
    field_type="keyword",
    is_real=False,
    virtual_config={
        "fields": {"connection": "attributes.network.connection.type", "quality": "attributes.network.effective_type"},
        "template": "{connection|--} / {quality|--}",
    },
)
