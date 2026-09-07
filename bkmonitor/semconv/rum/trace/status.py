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

from semconv.constants import SpanStatusCode
from semconv.rum.field import FieldSpec


class Status(FieldSpec):
    """status.*（Span 状态字段）"""

    CODE = FieldSpec(field_name="code", field_alias=_("状态码"), option_values=SpanStatusCode)
    MESSAGE = FieldSpec(field_name="message", field_alias=_("状态消息"))
