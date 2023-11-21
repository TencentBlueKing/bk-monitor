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
import requests

from rest_framework import serializers
from six.moves.urllib.parse import urljoin

from apm.core.deepflow.base import EBPFHandler
from apm_ebpf.handlers.deepflow import DeepflowHandler
from apm_ebpf.handlers.l7_flow_tracing import L7FlowTracing
from bkmonitor.utils.thread_backend import ThreadPool
from core.drf_resource import Resource
from core.errors.api import BKAPIError

logger = logging.getLogger("apm_ebpf")


class TraceQueryResource(Resource):
    """
    查询eBPF数据
    """

    method = "POST"
    path = "/v1/query/"

    class RequestSerializer(serializers.Serializer):
        trace_id = serializers.CharField(label="TraceID", max_length=255, required=False)
        sql = serializers.CharField(label="sql语句", max_length=5000)
        db = serializers.CharField(label="查询数据库", max_length=50)
        bk_biz_id = serializers.IntegerField(label="业务id")
        start_time = serializers.IntegerField(label="开始时间", required=False, min_value=0)
        end_time = serializers.IntegerField(label="结束时间", required=False, min_value=0)

    @classmethod
    def build_param(cls, params):
        sql = params["sql"]
        filter_param = []
        if params.get("trace_id"):
            filter_param.append(" trace_id = '{}' ".format(params.get("trace_id")))
        if params.get("start_time"):
            filter_param.append(" time >= {} ".format(params.get("start_time")))
        if params.get("end_time"):
            filter_param.append(" time <= {} ".format(params.get("end_time")))

        if filter_param:
            sql += " WHERE" + "AND".join(filter_param)

        return {"db": params["db"], "sql": sql}

    @classmethod
    def query_ebpf_data(cls, base_url, params):

        url = urljoin(base_url, cls.path.format(**params))
        requests_params = {"method": cls.method, "url": url, "json": params}
        r = requests.request(timeout=60, **requests_params)
        result = r.status_code in [200]
        if not result:
            raise BKAPIError(system_name="deep-flow", url=url, result=r.text)

        # 数据解析
        response = r.json()
        result = response.get("result", {})
        ebpf_data = []
        result_values = result.get("values") if result.get("values") else []
        for values in result_values:
            ebpf_data.append(dict(zip(result.get("columns", []), values)))
        return ebpf_data

    @classmethod
    def batch_query_ebpf(cls, deep_flow_server_base_urls: list, params: dict):
        def inner(base_url, ebpf_param):
            return cls.query_ebpf_data(base_url, ebpf_param)

        futures = []
        pool = ThreadPool()
        for url in deep_flow_server_base_urls:
            futures.append(pool.apply_async(inner, args=(url, params)))

        ebpf_data = []
        for future in futures:
            try:
                ebpf_data.extend(future.get())
            except Exception as e:
                logger.info("batch_query_ebpf, {}".format(e))
        return ebpf_data

    def perform_request(self, params):
        query_params = self.build_param(params)
        deep_flow_server_base_urls = list(DeepflowHandler(params["bk_biz_id"]).server_addresses.values())
        return self.batch_query_ebpf(deep_flow_server_base_urls, query_params)


class QueryFlowTracingResource(Resource):
    """
    无 trace_id 查询， 根据 _id 查询数据，并串联 ebpf_span 数据
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务id")
        id = serializers.CharField(label="ebpf 数据id", max_length=50)
        start_time = serializers.IntegerField(label="开始时间", min_value=0)
        end_time = serializers.IntegerField(label="结束时间", min_value=0)
        max_iteration = serializers.IntegerField(label="span追踪深度", required=False, min_value=1, max_value=30)

    def perform_request(self, param):

        response = L7FlowTracing(param).query()
        ebpf_spans = []
        for item in response:
            span_data = EBPFHandler.l7_flow_log_to_resource_span(item)
            ebpf_spans.append(span_data)
        return ebpf_spans
