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
import os
import socket
import threading
from typing import Collection

import MySQLdb
from celery.signals import beat_init, worker_process_init
from django.conf import settings
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation import dbapi
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.django import DjangoInstrumentor, _DjangoMiddleware
from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.instrumentation.kafka import KafkaInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import DEFAULT_OFF, DEFAULT_ON

from bkmonitor.trace.django import get_span_name
from bkmonitor.trace.django import request_hook as django_request_hook
from bkmonitor.trace.django import response_hook as django_response_hook
from bkmonitor.trace.elastic import BkElasticsearchInstrumentor
from bkmonitor.trace.logging import BkResourceLoggingInstrument
from bkmonitor.trace.requests import requests_span_callback
from bkmonitor.trace.threading import ThreadingInstrumentor
from bkmonitor.utils.common_utils import get_local_ip


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
        DjangoInstrumentor().uninstrument()
        RedisInstrumentor().uninstrument()
        BkElasticsearchInstrumentor().uninstrument()
        RequestsInstrumentor().uninstrument()
        CeleryInstrumentor().uninstrument()
        LoggingInstrumentor().uninstrument()
        ThreadingInstrumentor().uninstrument()
        KafkaInstrumentor().uninstrument()

    def _instrument(self, **kwargs):
        """Instrument the library"""
        if self.has_instrument:
            return
        otlp_http_host = os.getenv("BKAPP_OTLP_HTTP_HOST")
        sample_all = os.getenv("BKAPP_OTLP_SAMPLE_ALL", "false").lower() == "true"
        otlp_exporter = OTLPSpanExporter(endpoint=otlp_http_host)
        span_processor = LazyBatchSpanProcessor(otlp_exporter)
        sampler = DEFAULT_OFF

        if sample_all:
            sampler = DEFAULT_ON

        resource_info = {
            "service.name": settings.SERVICE_NAME,
            "service.version": settings.VERSION,
            "bk.data.token": os.getenv("BKAPP_OTLP_BK_DATA_TOKEN", ""),
            "service.environment": settings.ENVIRONMENT,
            "net.host.ip": get_local_ip(),
            "net.host.name": socket.gethostname(),
        }
        if settings.IS_CONTAINER_MODE and os.getenv("BKAPP_OTLP_BCS_CLUSTER_ID"):
            resource_info.update(
                {
                    "k8s.bcs.cluster.id": os.getenv("BKAPP_OTLP_BCS_CLUSTER_ID", ""),
                    "k8s.namespace.name": os.getenv("BKAPP_OTLP_BCS_CLUSTER_NAMESPACE", ""),
                    "k8s.pod.ip": get_local_ip(),
                    "k8s.pod.name": socket.gethostname(),
                }
            )
        tracer_provider = TracerProvider(resource=Resource.create(resource_info), sampler=sampler)
        tracer_provider.add_span_processor(span_processor)
        trace.set_tracer_provider(tracer_provider)

        _DjangoMiddleware._get_span_name = get_span_name  # pylint: disable=protected-access
        DjangoInstrumentor().instrument(request_hook=django_request_hook, response_hook=django_response_hook)
        RedisInstrumentor().instrument()
        BkElasticsearchInstrumentor().instrument()
        RequestsInstrumentor().instrument(span_callback=requests_span_callback)
        CeleryInstrumentor().instrument()
        BkResourceLoggingInstrument().instrument()
        ThreadingInstrumentor().instrument()
        KafkaInstrumentor().instrument()

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
def init_celery_worker_tracing(*args, **kwargs):
    if os.getenv("BKAPP_OTLP_HTTP_HOST") and os.getenv("BKAPP_OTLP_BK_DATA_TOKEN"):
        BluekingInstrumentor().instrument()


@beat_init.connect(weak=False)
def init_celery_beat_tracing(*args, **kwargs):
    if os.getenv("BKAPP_OTLP_HTTP_HOST") and os.getenv("BKAPP_OTLP_BK_DATA_TOKEN"):
        BluekingInstrumentor().instrument()
