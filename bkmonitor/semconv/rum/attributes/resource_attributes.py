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
from semconv.rum.constants import ResourceType, ResourceRenderBlockingStatus
from semconv.constants import (
    FieldUnit,
    FieldDisplayType,
)


RESOURCE_TYPE = FieldSpec(field_name="resource.type", field_alias=_("资源类型"), option_values=ResourceType)
RESOURCE_SIZE = FieldSpec(field_name="resource.size", field_alias=_("资源大小"), field_unit=FieldUnit.BYTES.value)
RESOURCE_TRANSFER_SIZE = FieldSpec(
    field_name="resource.transfer_size", field_alias=_("传输大小"), field_unit=FieldUnit.BYTES.value
)
RESOURCE_DECODED_BODY_SIZE = FieldSpec(
    field_name="resource.decoded_body_size", field_alias=_("解码后正文大小"), field_unit=FieldUnit.BYTES.value
)
RESOURCE_ENCODED_BODY_SIZE = FieldSpec(
    field_name="resource.encoded_body_size", field_alias=_("编码后正文大小"), field_unit=FieldUnit.BYTES.value
)
RESOURCE_PROTOCOL = FieldSpec(field_name="resource.protocol", field_alias=_("传输协议"))
RESOURCE_CACHE_HIT = FieldSpec(field_name="resource.cache.hit", field_alias=_("缓存命中标记"))
RESOURCE_DELIVERY_TYPE = FieldSpec(field_name="resource.delivery_type", field_alias=_("交付类型"))
RESOURCE_RENDER_BLOCKING_STATUS = FieldSpec(
    field_name="resource.render_blocking_status",
    field_alias=_("渲染阻塞状态"),
    option_values=ResourceRenderBlockingStatus,
)

RESOURCE_REDIRECT_START = FieldSpec(
    field_name="resource.redirect.start", field_alias=_("重定向开始时间"), field_unit=FieldUnit.MS.value
)
RESOURCE_REDIRECT_DURATION = FieldSpec(
    field_name="resource.redirect.duration",
    field_alias=_("重定向耗时"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)

RESOURCE_WORKER_START = FieldSpec(
    field_name="resource.worker.start", field_alias=_("Service Worker 开始时间"), field_unit=FieldUnit.MS.value
)
RESOURCE_WORKER_DURATION = FieldSpec(
    field_name="resource.worker.duration",
    field_alias=_("Service Worker 耗时"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)

RESOURCE_DNS_START = FieldSpec(
    field_name="resource.dns.start", field_alias=_("DNS 查询开始时间"), field_unit=FieldUnit.MS.value
)
RESOURCE_DNS_DURATION = FieldSpec(
    field_name="resource.dns.duration",
    field_alias=_("DNS 查询耗时"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)

RESOURCE_CONNECT_START = FieldSpec(
    field_name="resource.connect.start", field_alias=_("传输连接开始时间"), field_unit=FieldUnit.MS.value
)
RESOURCE_CONNECT_DURATION = FieldSpec(
    field_name="resource.connect.duration",
    field_alias=_("传输连接耗时"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)

RESOURCE_SSL_START = FieldSpec(
    field_name="resource.ssl.start", field_alias=_("TLS 握手开始时间"), field_unit=FieldUnit.MS.value
)
RESOURCE_SSL_DURATION = FieldSpec(
    field_name="resource.ssl.duration",
    field_alias=_("TLS 握手耗时"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)

RESOURCE_FIRST_BYTE_START = FieldSpec(
    field_name="resource.first_byte.start", field_alias=_("首字节阶段开始时间"), field_unit=FieldUnit.MS.value
)
RESOURCE_FIRST_BYTE_DURATION = FieldSpec(
    field_name="resource.first_byte.duration",
    field_alias=_("首字节耗时"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)

RESOURCE_DOWNLOAD_START = FieldSpec(
    field_name="resource.download.start", field_alias=_("下载开始时间"), field_unit=FieldUnit.MS.value
)
RESOURCE_DOWNLOAD_DURATION = FieldSpec(
    field_name="resource.download.duration",
    field_alias=_("下载耗时"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
