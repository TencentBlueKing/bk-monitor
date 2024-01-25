# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import json
import os
import sys
import threading
from typing import Collection

import MySQLdb
from celery.signals import worker_process_init
from django.conf import settings
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation import dbapi
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.django import DjangoInstrumentor
from opentelemetry.instrumentation.elasticsearch import ElasticsearchInstrumentor
from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import DEFAULT_OFF, DEFAULT_ON
from opentelemetry.trace import Span, Status, StatusCode

from bkmonitor.utils.common_utils import get_local_ip


def requests_callback(span: Span, response):
    """处理蓝鲸格式返回码"""
    try:
        json_result = response.json()
    except Exception:  # pylint: disable=broad-except
        return
    if not isinstance(json_result, dict):
        return

    # NOTE: esb got a result, but apigateway  /iam backend / search-engine got not result
    code = json_result.get("code", 0)
    span.set_attribute("result_code", code)
    span.set_attribute("result_message", json_result.get("message", ""))
    span.set_attribute("result_errors", str(json_result.get("errors", "")))
    try:
        request_id = (
            # new esb and apigateway
            response.headers.get("x-bkapi-request-id")
            # iam backend
            or response.headers.get("x-request-id")
            # old esb
            or json_result.get("request_id", "")
        )
        if request_id:
            span.set_attribute("bk.request_id", request_id)
    except Exception:  # pylint: disable=broad-except
        pass

    if code in [0, "0", "00", 200]:
        span.set_status(Status(StatusCode.OK))
    else:
        span.set_status(Status(StatusCode.ERROR))


def django_request_hook(span: Span, request):
    # Extract parameters from the request
    params = request.GET if request.method == 'GET' else request.POST

    # Try to serialize parameters as a JSON string
    try:
        params_str = json.dumps(params)
    except TypeError:
        # If a parameter cannot be serialized, ignore it
        params_str = json.dumps({k: v for k, v in params.items() if not v or isinstance(v, (str, int, float, bool))})

    # Set the serialized parameters as an attribute on the span
    span.set_attribute("request.params", params_str)


def django_response_hook(span, request, response):
    if hasattr(response, "data"):
        result = response.data
    else:
        try:
            result = json.loads(response.content)
        except Exception:  # pylint: disable=broad-except
            return
    if not isinstance(result, dict):
        return
    span.set_attribute("result_code", result.get("code", 0))
    span.set_attribute("result_message", result.get("message", ""))
    span.set_attribute("result_errors", result.get("errors", ""))
    result = result.get("result", True)
    if result:
        span.set_status(Status(StatusCode.OK))
        return
    span.set_status(Status(StatusCode.ERROR))


class LazyBatchSpanProcessor(BatchSpanProcessor):
    def __init__(self, *args, **kwargs):
        super(LazyBatchSpanProcessor, self).__init__(*args, **kwargs)
        # 停止默认线程
        self.done = True
        with self.condition:
            self.condition.notify_all()
        self.worker_thread.join()
        self.done = False
        self.worker_thread = None

    def on_end(self, span: ReadableSpan) -> None:
        if self.worker_thread is None:
            self.worker_thread = threading.Thread(target=self.worker, daemon=True)
            self.worker_thread.start()
        super(LazyBatchSpanProcessor, self).on_end(span)

    def shutdown(self) -> None:
        self.done = True
        with self.condition:
            self.condition.notify_all()
        if self.worker_thread:
            self.worker_thread.join()
        self.span_exporter.shutdown()


class BluekingInstrumentor(BaseInstrumentor):
    has_instrument = False

    def _uninstrument(self, **kwargs):
        pass

    def _instrument(self, **kwargs):
        """Instrument the library"""
        if self.has_instrument:
            return
        otlp_http_host = os.getenv("BKAPP_OTLP_HTTP_HOST")
        otlp_bk_data_id = os.getenv("BKAPP_OTLP_BK_DATA_ID")
        otlp_bk_data_token = os.getenv("BKAPP_OTLP_BK_DATA_TOKEN", "")
        sample_all = os.getenv("BKAPP_OTLP_SAMPLE_ALL", "false").lower() == "true"
        otlp_exporter = OTLPSpanExporter(endpoint=otlp_http_host)
        span_processor = LazyBatchSpanProcessor(otlp_exporter)
        sampler = DEFAULT_OFF
        suffix = "web"

        if settings.ROLE == "api":
            suffix = "api"
        if "celery" in sys.argv or settings.ROLE == "worker":
            suffix = "worker"
        if "beat" in sys.argv:
            suffix = "beat"

        if sample_all:
            sampler = DEFAULT_ON

        tracer_provider = TracerProvider(
            resource=Resource.create(
                {
                    "service.name": settings.APP_CODE + "_" + suffix,
                    "service.version": settings.VERSION,
                    "bk_data_id": otlp_bk_data_id,
                    "bk.data.token": otlp_bk_data_token,
                    "net.host.ip": get_local_ip(),
                }
            ),
            sampler=sampler,
        )
        tracer_provider.add_span_processor(span_processor)
        trace.set_tracer_provider(tracer_provider)
        DjangoInstrumentor().instrument(request_hook=django_request_hook, response_hook=django_response_hook)
        RedisInstrumentor().instrument()
        ElasticsearchInstrumentor().instrument()
        RequestsInstrumentor().instrument(tracer_provider=tracer_provider, span_callback=requests_callback)
        CeleryInstrumentor().instrument(tracer_provider=tracer_provider)
        LoggingInstrumentor().instrument()
        dbapi.wrap_connect(
            __name__,
            MySQLdb,
            "connect",
            "mysql",
            {
                "database": "db",
                "port": "port",
                "host": "host",
                "user": "user",
            },
            tracer_provider=tracer_provider,
        )
        self.has_instrument = True

    def instrumentation_dependencies(self) -> Collection[str]:
        return []


@worker_process_init.connect(weak=False)
def init_celery_tracing(*args, **kwargs):
    if os.getenv("BKAPP_OTLP_GRPC_HOST") and os.getenv("BKAPP_OTLP_BK_DATA_ID"):
        BluekingInstrumentor().instrument()
