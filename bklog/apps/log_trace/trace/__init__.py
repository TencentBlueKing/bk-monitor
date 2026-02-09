"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

import json
import os
import socket
import threading
from collections.abc import Collection
from typing import Any

import MySQLdb
from celery.signals import worker_process_init
from django.conf import settings
from django.http import HttpRequest
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation import dbapi
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.django import DjangoInstrumentor
from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ALWAYS_OFF, ALWAYS_ON, DEFAULT_OFF
from opentelemetry.trace import Span, Status, StatusCode

from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.log_trace.trace.elastic import BkElasticsearchInstrumentor
from apps.utils import get_local_ip
from apps.utils.local import get_request_username

# 参数最大字符限制
MAX_PARAMS_SIZE = 10000


def jsonify(data: Any) -> str:
    """尝试将数据转为 JSON 字符串"""
    try:
        return json.dumps(data)
    except (TypeError, ValueError):
        if isinstance(data, dict):
            return json.dumps({k: v for k, v in data.items() if not v or isinstance(v, str | int | float | bool)})
        if isinstance(data, bytes):
            try:
                return data.decode("utf-8")
            except UnicodeDecodeError:
                return str(data)
        return str(data)


def requests_callback(span: Span, request, response):
    """处理蓝鲸格式返回码"""

    body = request.body

    try:
        authorization_header = request.headers.get("x-bkapi-authorization")
        if authorization_header:
            username = json.loads(authorization_header).get("bk_username")
            if username:
                span.set_attribute("user.username", username)
    except (TypeError, json.JSONDecodeError):
        if body:
            try:
                username = json.loads(body).get("bk_username")
                if username:
                    span.set_attribute("user.username", username)
            except (TypeError, json.JSONDecodeError):
                pass

    try:
        carrier = request.body.decode("utf-8")
    except Exception:  # noqa
        carrier = str(request.body)

    span.set_attribute("request.body", carrier[:MAX_PARAMS_SIZE])

    # 仅统计 JSON 请求
    # 流式请求不统计，避免流式失效
    if "application/json" not in response.headers.get("Content-Type", ""):
        return
    # bytes 一般是二进制数据
    if response.headers.get("Accept-Ranges", "") == "bytes":
        return

    try:
        json_result = response.json()
    except Exception:  # pylint: disable=broad-except
        return
    if not isinstance(json_result, dict):
        return

    # NOTE: esb got a result, but apigateway  /iam backend / search-engine got not result
    code = json_result.get("code", 0)
    span.set_attribute("http.response.code", code)
    span.set_attribute("http.response.message", json_result.get("message", ""))
    span.set_attribute("http.response.errors", str(json_result.get("errors", "")))
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

    if code in [0, "0", "00"]:
        span.set_status(Status(StatusCode.OK))
    else:
        span.set_status(Status(StatusCode.ERROR))


def django_request_hook(span: Span, request: HttpRequest):
    """将请求中的 GET、BODY 参数记录在 span 中"""

    if not request:
        return
    try:
        if getattr(request, "FILES", None) and request.method.upper() == "POST":
            # 请求中如果包含了文件 不取 Body 内容
            carrier = jsonify(request.POST)
        else:
            carrier = request.body.decode("utf-8")
    except Exception:  # noqa
        carrier = ""

    param_str = jsonify(dict(request.GET)) if request.GET else ""

    span.set_attribute("request.body", carrier[:MAX_PARAMS_SIZE])
    span.set_attribute("request.params", param_str[:MAX_PARAMS_SIZE])


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

    is_success = result.get("result", True)
    span.set_attribute("user.username", get_request_username())
    span.set_attribute("http.response.code", result.get("code", 0))
    span.set_attribute("http.response.message", result.get("message", ""))
    span.set_attribute("http.response.errors", str(result.get("errors", "")))
    span.set_attribute("http.response.result", str(is_success))

    if is_success:
        span.set_status(Status(StatusCode.OK))
        return
    span.set_status(Status(StatusCode.ERROR))
    span.record_exception(exception=Exception(result.get("message")))


class LazyBatchSpanProcessor(BatchSpanProcessor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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
        super().on_end(span)

    def shutdown(self) -> None:
        # signal the worker thread to finish and then wait for it
        self.done = True
        with self.condition:
            self.condition.notify_all()
        if self.worker_thread:
            self.worker_thread.join()
        self.span_exporter.shutdown()


class BluekingInstrumentor(BaseInstrumentor):
    has_instrument = False
    GRPC_HOST = "otlp_grpc_host"
    BK_DATA_TOKEN = "otlp_bk_data_token"
    SAMPLE_ALL = "sample_all"

    def _uninstrument(self, **kwargs):
        DjangoInstrumentor().uninstrument()
        RedisInstrumentor().uninstrument()
        BkElasticsearchInstrumentor().uninstrument()
        RequestsInstrumentor().uninstrument()
        CeleryInstrumentor().uninstrument()
        LoggingInstrumentor().uninstrument()
        dbapi.unwrap_connect(MySQLdb, "connect")

    def _instrument(self, **kwargs):
        """Instrument the library"""
        if self.has_instrument:
            return
        toggle = FeatureToggleObject.toggle("bk_log_trace")
        feature_config = toggle.feature_config
        otlp_grpc_host = settings.OTLP_GRPC_HOST
        otlp_bk_data_token = ""
        sample_all = False
        if feature_config:
            otlp_grpc_host = feature_config.get(self.GRPC_HOST, otlp_grpc_host)
            otlp_bk_data_token = feature_config.get(self.BK_DATA_TOKEN, otlp_bk_data_token)
            sample_all = feature_config.get(self.SAMPLE_ALL, sample_all)
        otlp_exporter = OTLPSpanExporter(endpoint=otlp_grpc_host)
        span_processor = LazyBatchSpanProcessor(otlp_exporter)

        # periord task not sampler
        sampler = DEFAULT_OFF
        if settings.IS_CELERY_BEAT:
            sampler = ALWAYS_OFF

        if sample_all:
            sampler = ALWAYS_ON

        resource_info = {
            "service.name": settings.SERVICE_NAME,
            "service.version": settings.VERSION,
            "service.environment": settings.ENVIRONMENT,
            "bk.data.token": otlp_bk_data_token,
            "net.host.ip": get_local_ip(),
            "net.host.name": socket.gethostname(),
        }
        if settings.IS_K8S_DEPLOY_MODE and os.getenv("BKAPP_OTLP_BCS_CLUSTER_ID"):
            resource_info["k8s.bcs.cluster.id"] = os.getenv("BKAPP_OTLP_BCS_CLUSTER_ID", "")
            resource_info["k8s.namespace.name"] = os.getenv("BKAPP_OTLP_BCS_CLUSTER_NAMESPACE", "")
            resource_info["k8s.pod.ip"] = get_local_ip()
            resource_info["k8s.pod.name"] = socket.gethostname()

        tracer_provider = TracerProvider(
            resource=Resource.create(resource_info),
            sampler=sampler,
        )

        tracer_provider.add_span_processor(span_processor)
        trace.set_tracer_provider(tracer_provider)
        DjangoInstrumentor().instrument(request_hook=django_request_hook, response_hook=django_response_hook)
        RedisInstrumentor().instrument()
        BkElasticsearchInstrumentor().instrument()
        RequestsInstrumentor().instrument(tracer_provider=tracer_provider, response_hook=requests_callback)
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
    from apps.feature_toggle.handlers.toggle import FeatureToggleObject

    if FeatureToggleObject.switch("bk_log_trace"):
        BluekingInstrumentor().instrument()
