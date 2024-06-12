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

from apm import constants
from apm.core.deepflow.base import EBPFHandler
from apm.core.handlers.query.base import EsQueryBuilderMixin
from apm.utils.es_search import EsSearch
from apm_ebpf.resource import TraceQueryResource
from constants.apm import OtlpKey

logger = logging.getLogger("apm")


class EbpfQuery(EsQueryBuilderMixin):
    DEFAULT_SORT_FIELD = "end_time"

    def __init__(self, es_client, index_name):
        self.client = es_client
        self.client = es_client
        self.index_name = index_name

    @property
    def search(self):
        return EsSearch(using=self.client, index=self.index_name)

    def query_by_trace_id(self, trace_id):
        query = self.search

        query = self.add_filter(query, OtlpKey.TRACE_ID, trace_id)
        query = query.extra(size=constants.DISCOVER_BATCH_SIZE).sort(OtlpKey.START_TIME)

        return [i.to_dict() for i in query.execute()]


class DeepFlowQuery:
    @classmethod
    def get_ebpf(cls, trace_id: str, bk_biz_id: int):
        """
        获取ebpf数据
        """
        sql = (
            "SELECT pod_service_0, pod_service_1, pod_group_0, pod_group_1, pod_0, pod_1, service_0, "
            "service_1, resource_gl0_0, resource_gl0_1, chost_0, chost_1, pod_node_0, pod_node_1, "
            "Enum(auto_instance_type_0), Enum(auto_instance_type_1), auto_instance_0, auto_instance_1, "
            "Enum(auto_service_type_0), Enum(auto_service_type_1), auto_service_0, auto_service_1, gprocess_0, "
            "gprocess_1, _id, ip4_0, ip4_1, ip6_0, ip6_1, attribute, ip_0, ip_1, is_internet_0, "
            "is_internet_1, Enum(protocol), client_port, server_port, req_tcp_seq, "
            "resp_tcp_seq, Enum(l7_protocol), l7_protocol_str, version, Enum(type), request_type, request_domain, "
            "request_resource, request_id, response_code, response_exception, "
            "response_result, app_service, app_instance, endpoint, process_id_0, process_id_1, process_kname_0, "
            "process_kname_1, trace_id, span_id, parent_span_id, Enum(span_kind), "
            "x_request_id_0, x_request_id_1, tap_id, syscall_trace_id_request, syscall_trace_id_response, "
            "syscall_thread_0, syscall_thread_1, syscall_cap_seq_0, syscall_cap_seq_1, flow_id, vtap_id, "
            "toString(start_time) AS start_time, toString(end_time) AS end_time, Enum(signal_source), tap, vtap, "
            "Enum(nat_source), tap_port, tap_port_name, Enum(tap_port_type), Enum(tap_side), "
            "pod_cluster_id_0, pod_cluster_id_1, pod_ns_id_0, pod_ns_id_1, pod_node_id_0, pod_node_id_1,"
            "pod_service_id_0, pod_service_id_1, pod_group_id_0, pod_group_id_1, pod_id_0, pod_id_1, "
            "service_id_1, auto_instance_id_0, auto_instance_id_1, auto_service_id_0, "
            "auto_service_id_1, service_id_0, http_proxy_client, "
            "l7_protocol, signal_source, tap_side, tap_port_type, response_status, is_ipv4  FROM l7_flow_log"
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
