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

import logging
import os

import requests
from rest_framework import serializers
from six.moves.urllib.parse import urljoin

from core.drf_resource import Resource
from core.errors.api import BKAPIError

logger = logging.getLogger(__name__)


class DeepFlowAPIResource(Resource):
    """
    deep-flow 统一查询模块
    """

    method = ""
    path = ""

    # 获取deep_flow_app_host and deep_flow_app_port todo
    @classmethod
    def get_deep_flow_base_url(cls):
        return os.getenv("BK_MONITOR_DEEP_FLOW_URL", "http://172.17.1.140:20418")

    def perform_request(self, params):
        base_url = self.get_deep_flow_base_url()
        url = urljoin(base_url, self.path.format(**params))

        requests_params = {"method": self.method, "url": url}
        if self.method in ["PUT", "POST", "PATCH"]:
            requests_params["json"] = params
        elif self.method in ["GET", "HEAD", "DELETE"]:
            requests_params["params"] = params

        r = requests.request(timeout=60, **requests_params)

        result = r.status_code in [200]
        if not result:
            raise BKAPIError(system_name="deep-flow", url=url, result=r.text)

        return r.json()


class QueryTracingCompletionByExternalAppSpansResource(DeepFlowAPIResource):
    """
    查询数据
    """

    method = "POST"
    path = "/v1/stats/querier/tracing-completion-by-external-app-spans/"

    class RequestSerializer(serializers.Serializer):
        class AppSpanSerializer(serializers.Serializer):
            trace_id = serializers.CharField(label="TraceID")
            span_id = serializers.CharField(label="SpanID", allow_blank=True)
            parent_span_id = serializers.CharField(label="ParentSpanID", allow_blank=True)
            span_kind = serializers.IntegerField(label="span kind")
            start_time_us = serializers.IntegerField(label="开始时间")
            end_time_us = serializers.IntegerField(label="结束时间")

        app_spans = serializers.ListSerializer(child=AppSpanSerializer())
        max_iteration = serializers.IntegerField(label="系统 Span 追踪的深度", required=False, min_value=1)
        network_delay_us = serializers.IntegerField(label="网络 Span 追踪的时间跨度 ", required=False, min_value=1)
