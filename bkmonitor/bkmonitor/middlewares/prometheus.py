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

import socket
from django.conf import settings
from django_prometheus.middleware import (
    Metrics,
    PrometheusAfterMiddleware,
    PrometheusBeforeMiddleware,
)
from django_prometheus.utils import Time, TimeSince

from core.prometheus import metrics
from core.prometheus.base import REGISTRY

HOSTNAME = socket.gethostname()
STAGE = settings.ENVIRONMENT


class CustomMetrics(Metrics):
    def register_metric(self, metric_cls, name, documentation, labelnames=(), **kwargs):
        return super().register_metric(
            metric_cls,
            name,
            documentation,
            labelnames=[*labelnames, "hostname", "stage", "bk_app_code", "role"],
            registry=REGISTRY,
            **kwargs,
        )


class MetricsBeforeMiddleware(PrometheusBeforeMiddleware):
    metrics_cls = CustomMetrics

    def process_request(self, request):
        self.metrics.requests_total.labels(
            hostname=HOSTNAME, stage=STAGE, bk_app_code=settings.APP_CODE, role=settings.ROLE
        ).inc()
        request.prometheus_before_middleware_event = Time()

    def process_response(self, request, response):
        self.metrics.responses_total.labels(
            hostname=HOSTNAME, stage=STAGE, bk_app_code=settings.APP_CODE, role=settings.ROLE
        ).inc()
        if hasattr(request, "prometheus_before_middleware_event"):
            self.metrics.requests_latency_before.labels(
                hostname=HOSTNAME, stage=STAGE, bk_app_code=settings.APP_CODE, role=settings.ROLE
            ).observe(TimeSince(request.prometheus_before_middleware_event))
        else:
            self.metrics.requests_unknown_latency_before.labels(
                hostname=HOSTNAME, stage=STAGE, bk_app_code=settings.APP_CODE, role=settings.ROLE
            ).inc()
        metrics.report_all()
        return response


class MetricsAfterMiddleware(PrometheusAfterMiddleware):
    metrics_cls = CustomMetrics

    def label_metric(self, metric, request, response=None, **labels):
        labels.update({"hostname": HOSTNAME, "stage": STAGE, "bk_app_code": settings.APP_CODE, "role": settings.ROLE})
        return super().label_metric(metric, request, response=response, **labels)
