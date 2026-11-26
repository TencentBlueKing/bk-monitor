"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the MIT License
is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and limitations under the License.
"""

from django.utils.translation import gettext_lazy as _

from constants.otel_query import FieldTypeEnum
from semconv.constants import FieldDisplayType, FieldUnit
from semconv.rum.field import FieldSpec


def _time_point(name: str, alias: str) -> FieldSpec:
    return FieldSpec(
        field_name=f"timing.{name}",
        field_alias=alias,
        field_unit=FieldUnit.MS.value,
        field_type=FieldTypeEnum.DOUBLE.value,
        field_display_type=FieldDisplayType.DURATION.value,
    )


TIMING_START_TIME = _time_point("start_time", _("时序开始时间"))
TIMING_REDIRECT_START = _time_point("redirect_start", _("重定向开始时间"))
TIMING_REDIRECT_END = _time_point("redirect_end", _("重定向结束时间"))
TIMING_FETCH_START = _time_point("fetch_start", _("最终资源获取开始时间"))
TIMING_WORKER_START = _time_point("worker_start", _("Service Worker 介入时间"))
TIMING_WORKER_ROUTER_EVALUATION_START = _time_point(
    "worker_router_evaluation_start", _("Service Worker 静态路由评估开始时间")
)
TIMING_WORKER_CACHE_LOOKUP_START = _time_point("worker_cache_lookup_start", _("Service Worker 缓存查询开始时间"))
TIMING_DOMAIN_LOOKUP_START = _time_point("domain_lookup_start", _("DNS 查询开始时间"))
TIMING_DOMAIN_LOOKUP_END = _time_point("domain_lookup_end", _("DNS 查询结束时间"))
TIMING_CONNECT_START = _time_point("connect_start", _("连接开始时间"))
TIMING_SECURE_CONNECTION_START = _time_point("secure_connection_start", _("TLS 握手开始时间"))
TIMING_CONNECT_END = _time_point("connect_end", _("连接完成时间"))
TIMING_REQUEST_START = _time_point("request_start", _("请求开始时间"))
TIMING_RESPONSE_START = _time_point("response_start", _("首个响应开始时间"))
TIMING_FINAL_RESPONSE_HEADERS_START = _time_point("final_response_headers_start", _("最终响应头开始时间"))
TIMING_RESPONSE_END = _time_point("response_end", _("响应结束时间"))
TIMING_UNLOAD_EVENT_START = _time_point("unload_event_start", _("上一页面卸载开始时间"))
TIMING_UNLOAD_EVENT_END = _time_point("unload_event_end", _("上一页面卸载完成时间"))
TIMING_DOM_INTERACTIVE = _time_point("dom_interactive", _("DOM 可交互时间"))
TIMING_DOM_CONTENT_LOADED_EVENT_START = _time_point(
    "dom_content_loaded_event_start", _("DOMContentLoaded 事件开始时间")
)
TIMING_DOM_CONTENT_LOADED_EVENT_END = _time_point("dom_content_loaded_event_end", _("DOMContentLoaded 事件结束时间"))
TIMING_DOM_COMPLETE = _time_point("dom_complete", _("DOM 完成时间"))
TIMING_LOAD_EVENT_START = _time_point("load_event_start", _("Load 事件开始时间"))
TIMING_LOAD_EVENT_END = _time_point("load_event_end", _("Load 事件结束时间"))
TIMING_ACTIVATION_START = _time_point("activation_start", _("预渲染页面激活开始时间"))

TIMING_WORKER_MATCHED_ROUTER_SOURCE = FieldSpec(
    field_name="timing.worker_matched_router_source", field_alias=_("Service Worker 命中来源")
)
TIMING_WORKER_FINAL_ROUTER_SOURCE = FieldSpec(
    field_name="timing.worker_final_router_source", field_alias=_("Service Worker 最终来源")
)
TIMING_INCOMPLETE = FieldSpec(
    field_name="timing.incomplete", field_alias=_("请求时序不完整"), field_type=FieldTypeEnum.BOOLEAN.value
)
