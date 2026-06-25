"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import datetime
from typing import Any
from urllib.parse import urljoin, urlparse

from django.utils.translation import gettext_lazy as _
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.semconv.trace import SpanAttributes

from apm_web.models import Application
from constants.apm import OtlpKey, RpcAttributes, TrpcAttributes
from core.drf_resource import api


class SpanHandler:
    UNKNOWN_EXCEPTION_TYPE = "unknown"
    EXCEPTION_NAME = "exception"
    EXCEPTION_REFER = "exception.refer"
    EXCEPTION_ALIAS = "exception.alias"
    ERROR_SPAN_FIELDS = [
        OtlpKey.RESOURCE,
        OtlpKey.SPAN_NAME,
        OtlpKey.TRACE_ID,
        OtlpKey.EVENTS,
        OtlpKey.ATTRIBUTES,
        OtlpKey.STATUS,
        OtlpKey.START_TIME,
        OtlpKey.END_TIME,
    ]
    DEFAULT_EXCEPTION_REFER = f"{OtlpKey.EVENTS}.{OtlpKey.get_attributes_key(SpanAttributes.EXCEPTION_TYPE)}"
    RPC_EXCEPTION_FIELDS = {
        RpcAttributes.RPC_ERROR_CODE: RpcAttributes.RPC_ERROR_MESSAGE,
        TrpcAttributes.TRPC_STATUS_CODE: TrpcAttributes.TRPC_STATUS_MSG,
    }

    @classmethod
    def get_lastly_span(cls, bk_biz_id, app_name):
        """获取一天内最近一条span"""
        app = Application.objects.get(bk_biz_id=bk_biz_id, app_name=app_name)
        if not app.trace_result_table_id:
            # 未开启 trace，这里直接返回空
            return None

        end: int = int(datetime.datetime.now().timestamp())
        # 先从一个较小的时间范围内查询，加快有数据应用的查询速度。
        for duration in [datetime.timedelta(minutes=5), datetime.timedelta(hours=6), datetime.timedelta(days=1)]:
            try:
                return api.apm_api.query_span(
                    {
                        "bk_biz_id": app.bk_biz_id,
                        "app_name": app.app_name,
                        "start_time": int(end - duration.total_seconds()),
                        "end_time": end,
                        "limit": 1,
                    }
                )[0]
            except IndexError:
                continue

        return None

    @classmethod
    def _get_key_pair(cls, key):
        pair = key.split(".", 1)
        if len(pair) == 1:
            return "", pair[0]
        return pair[0], pair[1]

    @classmethod
    def get_span_field_value(cls, span, key):
        if not span:
            return None

        first, second = cls._get_key_pair(key)
        first_item = span.get(first, span)
        if not isinstance(first_item, dict):
            return None

        return first_item.get(second, "")

    @classmethod
    def get_span_urls(
        cls, app: Application, start_time: datetime.datetime, end_time: datetime.datetime, service_name: str = None
    ):
        """获取 500 条 attributes.http.url 候选项"""
        filters: list[dict[str, Any]] = []
        if service_name:
            filters.append(
                {
                    "key": OtlpKey.get_resource_key(ResourceAttributes.SERVICE_NAME),
                    "operator": "equal",
                    "value": [service_name],
                }
            )

        field: str = OtlpKey.get_attributes_key(SpanAttributes.HTTP_URL)
        field_options: dict[str, list[str]] = api.apm_api.query_span_option_values(
            {
                "bk_biz_id": app.bk_biz_id,
                "app_name": app.app_name,
                "start_time": int(start_time.timestamp()),
                "end_time": int(end_time.timestamp()),
                "filters": filters,
                "fields": [field],
                "limit": 500,
            }
        )
        return field_options.get(field, [])

    @classmethod
    def get_span_uris(cls, app, start_time, end_time, service_name=None):
        urls = cls.get_span_urls(app, start_time, end_time, service_name)
        res = []
        for url in urls:
            url_parse = urlparse(url)
            res.append(cls.generate_uri(url_parse))

        return list(set(res))

    @classmethod
    def generate_uri(cls, url_parser):
        return urljoin(f"{url_parser.scheme}://{url_parser.netloc}", url_parser.path).rstrip("/")

    @classmethod
    def process_rpc_span(cls, span: dict[str, Any]) -> dict[str, Any]:
        """标准化 span 的 RPC / tRPC 异常事件。

        :param span: span 数据
        :return: 补齐 exception event 后的 span 数据
        """
        events: list[dict[str, Any]] = span.get(OtlpKey.EVENTS) or []
        span[OtlpKey.EVENTS] = events
        exception_refers: set[str] = {
            (event.get(OtlpKey.ATTRIBUTES) or {}).get(cls.EXCEPTION_REFER, "")
            for event in events
            if event.get("name") == cls.EXCEPTION_NAME
        }

        attributes: dict[str, Any] = span.get(OtlpKey.ATTRIBUTES) or {}
        status_message: str = (span.get(OtlpKey.STATUS) or {}).get("message", "")
        for code_field, message_field in cls.RPC_EXCEPTION_FIELDS.items():
            code: Any | None = attributes.get(code_field)
            # 注：code 可以为 0，因此不能改写为 `if not code`
            if code is None or code == "":
                continue
            if code_field in exception_refers:
                break

            exception_type: str = str(code)
            message_text: str = attributes.get(message_field) or status_message

            events.append(
                {
                    "name": cls.EXCEPTION_NAME,
                    "timestamp": span["start_time"],
                    OtlpKey.ATTRIBUTES: {
                        cls.EXCEPTION_REFER: code_field,
                        SpanAttributes.EXCEPTION_TYPE: exception_type,
                        cls.EXCEPTION_ALIAS: _("返回码 - {code}").format(code=exception_type),
                        SpanAttributes.EXCEPTION_MESSAGE: message_text,
                    },
                }
            )
            break

        return span

    @classmethod
    def get_selected_exception_refer(cls, exception_type: str, exception_refer: str) -> str:
        """返回当前筛选上下文使用的异常来源字段。"""
        if exception_refer:
            return exception_refer
        if exception_type and exception_type != cls.UNKNOWN_EXCEPTION_TYPE:
            return cls.DEFAULT_EXCEPTION_REFER
        return ""

    @classmethod
    def get_exception_events(cls, span: dict[str, Any]) -> list[dict[str, Any]]:
        """返回标准化后的逻辑异常事件列表。"""
        span = cls.process_rpc_span(span)
        status_message: str = (span.get(OtlpKey.STATUS) or {}).get("message", "")

        exception_events: list[dict[str, Any]] = []
        for event in span.get(OtlpKey.EVENTS) or []:
            if event.get("name") != cls.EXCEPTION_NAME:
                continue

            event_attributes: dict[str, Any] = event.get(OtlpKey.ATTRIBUTES) or {}
            exception_type: str = event_attributes.get(SpanAttributes.EXCEPTION_TYPE, cls.UNKNOWN_EXCEPTION_TYPE)
            exception_refer: str = event_attributes.get(cls.EXCEPTION_REFER, cls.DEFAULT_EXCEPTION_REFER)
            exception_alias: str = event_attributes.get(cls.EXCEPTION_ALIAS, exception_type)
            exception_message: str = event_attributes.get(SpanAttributes.EXCEPTION_MESSAGE) or status_message
            stacktrace: str = event_attributes.get(SpanAttributes.EXCEPTION_STACKTRACE) or ""
            timestamp: int = int(event.get("timestamp", span.get(OtlpKey.START_TIME, 0)))
            exception_events.append(
                {
                    "exception_type": exception_type,
                    "exception_refer": exception_refer,
                    "exception_alias": exception_alias,
                    "exception_message": exception_message,
                    "timestamp": timestamp,
                    "stacktrace": stacktrace,
                    "has_stack": bool(stacktrace),
                }
            )

        return exception_events

    @classmethod
    def get_matched_exception_events(
        cls,
        span: dict[str, Any],
        exception_type: str = "",
        exception_refer: str = "",
        include_unknown: bool = False,
    ) -> list[dict[str, Any]]:
        exception_events: list[dict[str, Any]] = cls.get_exception_events(span)
        if not exception_events and include_unknown:
            exception_events = [
                {
                    "exception_type": cls.UNKNOWN_EXCEPTION_TYPE,
                    "exception_refer": "",
                    "exception_alias": cls.UNKNOWN_EXCEPTION_TYPE,
                    "exception_message": (span.get(OtlpKey.STATUS) or {}).get("message", ""),
                    "timestamp": int(span.get(OtlpKey.END_TIME) or span.get(OtlpKey.START_TIME) or 0),
                    "stacktrace": "",
                    "has_stack": False,
                }
            ]

        if not exception_type:
            return exception_events

        selected_exception_refer: str = cls.get_selected_exception_refer(exception_type, exception_refer)
        return [
            exception_event
            for exception_event in exception_events
            if exception_event.get("exception_type") == exception_type
            and exception_event.get("exception_refer", "") == selected_exception_refer
        ]

    @classmethod
    def build_exception_params(
        cls, exception_type: str, exception_refer: str, operator_key: str = "op"
    ) -> list[dict[str, Any]]:
        """构造异常筛选条件。"""
        if not exception_type:
            return []

        selected_exception_refer: str = cls.get_selected_exception_refer(exception_type, exception_refer)
        if exception_type == cls.UNKNOWN_EXCEPTION_TYPE and not selected_exception_refer:
            return []

        operator_value: str = "equal" if operator_key == "operator" else "="
        if selected_exception_refer == cls.DEFAULT_EXCEPTION_REFER:
            return [
                {"key": f"{OtlpKey.EVENTS}.name", operator_key: operator_value, "value": [cls.EXCEPTION_NAME]},
                {"key": cls.DEFAULT_EXCEPTION_REFER, operator_key: operator_value, "value": [exception_type]},
            ]

        selected_key: str = OtlpKey.get_attributes_key(selected_exception_refer)
        return [{"key": selected_key, operator_key: operator_value, "value": [exception_type]}]
