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

import requests
from rest_framework import serializers
from six.moves.urllib.parse import urljoin

from core.drf_resource import Resource
from core.errors.api import BKAPIError


class DeepFlowAPIResource(Resource):
    """
    deep-flow 统一查询模块
    """

    method = ""
    path = ""

    # 获取deep_flow_app_host and deep_flow_app_port todo
    @classmethod
    def get_deep_flow_base_url(cls):
        return os.getenv("BK_MONITOR_DEEPFLOW_SERVER_URL")

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


class Query(DeepFlowAPIResource):
    """
    查询eBPF数据
    """

    SQL = (
        "SELECT client_port, req_tcp_seq, resp_tcp_seq, l7_protocol, l7_protocol_str, version, Enum(type), "
        "request_type, request_domain, request_resource, request_id, response_status, response_code, "
        "response_exception, app_service, app_instance, endpoint, trace_id, span_id, parent_span_id, "
        "Enum(span_kind) AS kind, http_proxy_client, syscall_trace_id_request, syscall_trace_id_response, "
        "syscall_thread_0, syscall_thread_1, syscall_cap_seq_0, syscall_cap_seq_1, flow_id, signal_source, "
        "tap, vtap, nat_source, tap_port, tap_port_name, tap_port_type, tap_side, tap_id, vtap_id, "
        "toString(start_time) AS start_time, toString(end_time) AS end_time FROM l7_flow_log"
    )

    method = "POST"
    path = "/v1/query/"

    class RequestSerializer(serializers.Serializer):
        trace_id = serializers.CharField(label="TraceID", max_length=255)

    @classmethod
    def build_param(cls, params):
        sql = cls.SQL + " WHERE trace_id = '{}' ".format(params["trace_id"])
        return {"db": "flow_log", "sql": sql}

    def perform_request(self, params):
        query_params = self.build_param(params)
        response = super().perform_request(query_params)
        result = response.get("result", {})

        ebpf_data = []
        for values in result.get("values", []):
            ebpf_data.append(dict(zip(result.get("columns", []), values)))
        return ebpf_data
