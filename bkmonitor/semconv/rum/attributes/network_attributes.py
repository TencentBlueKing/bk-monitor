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
from semconv.constants import NetworkStatus, NetworkProtocolName, NetworkConnectionType

NETWORK_CONNECTION_TYPE = FieldSpec(
    field_name="network.connection.type", field_alias=_("连接类型"), option_values=NetworkConnectionType
)
NETWORK_EFFECTIVE_TYPE = FieldSpec(field_name="network.effective_type", field_alias=_("有效网络质量"))
NETWORK_STATUS = FieldSpec(field_name="network.status", field_alias=_("网络连接状态"), option_values=NetworkStatus)
NETWORK_PROTOCOL_NAME = FieldSpec(
    field_name="network.protocol.name", field_alias=_("应用层网络协议"), option_values=NetworkProtocolName
)
