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


URL_FULL = FieldSpec(field_name="url.full", field_alias=_("完整 URL"))
URL_SCHEME = FieldSpec(field_name="url.scheme", field_alias=_("协议"))
URL_TEMPLATE = FieldSpec(field_name="url.template", field_alias=_("请求路径"))

HTTP_REQUEST_METHOD = FieldSpec(field_name="http.request.method", field_alias=_("Method"))
HTTP_RESPONSE_STATUS_CODE = FieldSpec(field_name="http.response.status_code", field_alias=_("状态码"))

SERVER_ADDRESS = FieldSpec(field_name="server.address", field_alias=_("地址"))
SERVER_PORT = FieldSpec(field_name="server.port", field_alias=_("端口"))
