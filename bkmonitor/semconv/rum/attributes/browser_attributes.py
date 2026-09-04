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


# screen
BROWSER_SCREEN_HEIGHT = FieldSpec(field_name="browser.screen.height", field_alias=_("屏幕高度"))
BROWSER_SCREEN_WIDTH = FieldSpec(field_name="browser.screen.width", field_alias=_("屏幕宽度"))

# viewport
BROWSER_VIEWPORT_HEIGHT = FieldSpec(field_name="browser.viewport.height", field_alias=_("视口高度"))
BROWSER_VIEWPORT_WIDTH = FieldSpec(field_name="browser.viewport.width", field_alias=_("视口宽度"))
