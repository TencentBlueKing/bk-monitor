# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - Resource SDK (BlueKing - Resource SDK) available.
Copyright (C) 2022 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""
import logging

from apm.core.deepflow.base import EBPFHandler
from apm_ebpf.resource import TraceQueryResource

logger = logging.getLogger("apm")


class DeepFlowQuery:
    @classmethod
    def get_ebpf(cls, trace_id: str, bk_biz_id: int):
        """
        获取ebpf数据
        """
        sql = (
            "SELECT chost_0, chost_1, pod_node_0, pod_node_1, auto_instance_0, auto_instance_1, "
            "auto_service_0, auto_service_1, tap_port, tap_port_name, http_proxy_client, "
            "_id, ip4_0, ip4_1, ip6_0, ip6_1, attribute, ip_0, ip_1, is_internet_0, tap, vtap, "
            "is_internet_1, Enum(protocol), client_port, server_port, req_tcp_seq, "
            "resp_tcp_seq, Enum(l7_protocol), l7_protocol_str, version, Enum(type), request_type, request_domain, "
            "request_resource, request_id, response_code, response_exception, "
            "response_result, app_service, app_instance, endpoint, process_id_0, process_id_1, process_kname_0, "
            "process_kname_1, trace_id, span_id, parent_span_id, "
            "x_request_id_0, x_request_id_1, syscall_trace_id_request, syscall_trace_id_response, "
            "syscall_thread_0, syscall_thread_1, syscall_cap_seq_0, syscall_cap_seq_1, flow_id, "
            "toUnixTimestamp64Micro(start_time) AS start_time_us, toUnixTimestamp64Micro(end_time) AS end_time_us, "
            "l7_protocol, signal_source, tap_side, tap_port_type, response_status, is_ipv4 FROM l7_flow_log"
        )
        ebpf_spans = []
        ebpf_param = {"trace_id": trace_id, "bk_biz_id": bk_biz_id, "sql": sql, "db": "flow_log"}
        try:
            res = TraceQueryResource().request(ebpf_param)
            for item in res:
                span_data = EBPFHandler.l7_flow_log_to_resource_span(item)
                ebpf_spans.append(span_data)
        except Exception as e:
            logging.info("get_ebpf, {}".format(e))
        return ebpf_spans
