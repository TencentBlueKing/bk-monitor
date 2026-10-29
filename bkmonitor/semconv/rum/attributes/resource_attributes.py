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
from semconv.rum.constants import ResourceType, ResourceRenderBlockingStatus, ResourceCacheHit
from semconv.constants import FieldUnit, FieldDisplayType
from constants.otel_query import FieldTypeEnum


RESOURCE_TYPE = FieldSpec(field_name="resource.type", field_alias=_("资源类型"), option_values=ResourceType)
RESOURCE_SIZE = FieldSpec(field_name="resource.size", field_alias=_("资源大小"), field_unit=FieldUnit.BYTES.value)
RESOURCE_TRANSFER_SIZE = FieldSpec(
    field_name="resource.transfer_size", field_alias=_("传输大小"), field_unit=FieldUnit.BYTES.value
)
RESOURCE_DECODED_BODY_SIZE = FieldSpec(
    field_name="resource.decoded_body_size", field_alias=_("解压后大小"), field_unit=FieldUnit.BYTES.value
)
RESOURCE_ENCODED_BODY_SIZE = FieldSpec(
    field_name="resource.encoded_body_size", field_alias=_("压缩后大小"), field_unit=FieldUnit.BYTES.value
)
RESOURCE_PROTOCOL = FieldSpec(field_name="resource.protocol", field_alias=_("资源协议"))
RESOURCE_CACHE_HIT = FieldSpec(
    field_name="resource.cache.hit",
    field_type=FieldTypeEnum.BOOLEAN.value,
    field_alias=_("缓存命中"),
    option_values=ResourceCacheHit,
)
RESOURCE_DELIVERY_TYPE = FieldSpec(field_name="resource.delivery_type", field_alias=_("资源获取方式"))
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
    field_name="resource.worker.start",
    field_alias=_("Service Worker 开始时间"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
RESOURCE_WORKER_DURATION = FieldSpec(
    field_name="resource.worker.duration",
    field_alias=_("Service Worker 耗时"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)

RESOURCE_DNS_START = FieldSpec(
    field_name="resource.dns.start",
    field_alias=_("DNS 解析开始时间"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
RESOURCE_DNS_DURATION = FieldSpec(
    field_name="resource.dns.duration",
    field_alias=_("DNS 解析耗时"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)

RESOURCE_CONNECT_START = FieldSpec(
    field_name="resource.connect.start",
    field_alias=_("连接开始时间"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
RESOURCE_CONNECT_DURATION = FieldSpec(
    field_name="resource.connect.duration",
    field_alias=_("连接耗时（含 TLS）"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)

RESOURCE_SSL_START = FieldSpec(
    field_name="resource.ssl.start",
    field_alias=_("TLS 握手开始时间"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
RESOURCE_SSL_DURATION = FieldSpec(
    field_name="resource.ssl.duration",
    field_alias=_("TLS 握手耗时"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)

RESOURCE_FIRST_BYTE_START = FieldSpec(
    field_name="resource.first_byte.start",
    field_alias=_("首字节等待开始时间"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
RESOURCE_FIRST_BYTE_DURATION = FieldSpec(
    field_name="resource.first_byte.duration",
    field_alias=_("首字节等待耗时"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)

RESOURCE_DOWNLOAD_START = FieldSpec(
    field_name="resource.download.start",
    field_alias=_("内容下载开始时间"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
RESOURCE_DOWNLOAD_DURATION = FieldSpec(
    field_name="resource.download.duration",
    field_alias=_("内容下载耗时"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)

# resource.timing.*：浏览器 PerformanceResourceTiming 的原样时间点（相对 timeOrigin），阶段耗时由消费方计算。
RESOURCE_TIMING_START_TIME = FieldSpec(
    field_name="resource.timing.start_time",
    field_alias=_("资源开始时间"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
RESOURCE_TIMING_REDIRECT_START = FieldSpec(
    field_name="resource.timing.redirect_start",
    field_alias=_("重定向开始时间"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
RESOURCE_TIMING_REDIRECT_END = FieldSpec(
    field_name="resource.timing.redirect_end",
    field_alias=_("重定向结束时间"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
RESOURCE_TIMING_FETCH_START = FieldSpec(
    field_name="resource.timing.fetch_start",
    field_alias=_("最后一跳获取开始时间"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
RESOURCE_TIMING_WORKER_START = FieldSpec(
    field_name="resource.timing.worker_start",
    field_alias=_("Service Worker 介入时间"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
RESOURCE_TIMING_WORKER_ROUTER_EVALUATION_START = FieldSpec(
    field_name="resource.timing.worker_router_evaluation_start",
    field_alias=_("Service Worker 路由评估时间"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
RESOURCE_TIMING_WORKER_CACHE_LOOKUP_START = FieldSpec(
    field_name="resource.timing.worker_cache_lookup_start",
    field_alias=_("Service Worker 缓存查询时间"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
RESOURCE_TIMING_DOMAIN_LOOKUP_START = FieldSpec(
    field_name="resource.timing.domain_lookup_start",
    field_alias=_("DNS 查询开始时间"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
RESOURCE_TIMING_DOMAIN_LOOKUP_END = FieldSpec(
    field_name="resource.timing.domain_lookup_end",
    field_alias=_("DNS 查询结束时间"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
RESOURCE_TIMING_CONNECT_START = FieldSpec(
    field_name="resource.timing.connect_start",
    field_alias=_("连接开始时间"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
RESOURCE_TIMING_SECURE_CONNECTION_START = FieldSpec(
    field_name="resource.timing.secure_connection_start",
    field_alias=_("TLS 开始时间"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
RESOURCE_TIMING_CONNECT_END = FieldSpec(
    field_name="resource.timing.connect_end",
    field_alias=_("连接完成时间"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
RESOURCE_TIMING_REQUEST_START = FieldSpec(
    field_name="resource.timing.request_start",
    field_alias=_("请求开始时间"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
RESOURCE_TIMING_RESPONSE_START = FieldSpec(
    field_name="resource.timing.response_start",
    field_alias=_("首个响应时间"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
RESOURCE_TIMING_FINAL_RESPONSE_HEADERS_START = FieldSpec(
    field_name="resource.timing.final_response_headers_start",
    field_alias=_("最终响应头时间"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)
RESOURCE_TIMING_RESPONSE_END = FieldSpec(
    field_name="resource.timing.response_end",
    field_alias=_("响应结束时间"),
    field_unit=FieldUnit.MS.value,
    field_display_type=FieldDisplayType.DURATION.value,
)

RESOURCE_TIMING_WORKER_MATCHED_ROUTER_SOURCE = FieldSpec(
    field_name="resource.timing.worker_matched_router_source", field_alias=_("Service Worker 命中来源")
)
RESOURCE_TIMING_WORKER_FINAL_ROUTER_SOURCE = FieldSpec(
    field_name="resource.timing.worker_final_router_source", field_alias=_("Service Worker 最终来源")
)
