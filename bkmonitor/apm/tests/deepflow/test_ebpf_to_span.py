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

from apm.core.deepflow.base import EBPFHandler

EBPF_DATA = {
    "client_port": 46730,
    "req_tcp_seq": 1804383822,
    "resp_tcp_seq": 411410582,
    "l7_protocol": 20,
    "l7_protocol_str": "HTTP",
    "version": "1.1",
    "Enum(type)": "Session",
    "request_type": "POST",
    "request_domain": "127.0.0.1:9200",
    "request_resource": "/write_20231105_2_bklog_demodemo102300001/_bulk",
    "request_id": None,
    "response_status": 4,
    "response_code": 200,
    "response_exception": "",
    "app_service": "",
    "app_instance": "",
    "endpoint": "",
    "trace_id": "",
    "span_id": "",
    "parent_span_id": "",
    "kind": "",
    "http_proxy_client": "",
    "syscall_trace_id_request": 0,
    "syscall_trace_id_response": 0,
    "syscall_thread_0": 0,
    "syscall_thread_1": 0,
    "syscall_cap_seq_0": 0,
    "syscall_cap_seq_1": 0,
    "flow_id": 6796564550824959000,
    "signal_source": 0,
    "tap": "虚拟网络",
    "vtap": "",
    "nat_source": 0,
    "tap_port": "00:45:c5:2b",
    "tap_port_name": "",
    "tap_port_type": 0,
    "tap_side": "c-nd",
    "tap_id": 3,
    "vtap_id": 29,
    "start_time": "2023-11-05 08:00:02.272966",
    "end_time": "2023-11-05 08:00:02.389924",
}


def test_span_name():
    span = EBPFHandler.l7_flow_log_to_resource_span(EBPF_DATA)

    assert span.get("span_name") == "HTTP POST"


def test_service_name():
    span = EBPFHandler.l7_flow_log_to_resource_span(EBPF_DATA)

    assert span.get("resource", {}).get("service.name") == "deepflow"


def test_status_code():
    span = EBPFHandler.l7_flow_log_to_resource_span(EBPF_DATA)
    assert span.get("status", {}).get("code") == 2

    EBPF_DATA["response_status"] = 0
    span = EBPFHandler.l7_flow_log_to_resource_span(EBPF_DATA)
    assert span.get("status", {}).get("code") == 1

    EBPF_DATA["response_status"] = 1
    span = EBPFHandler.l7_flow_log_to_resource_span(EBPF_DATA)
    assert span.get("status", {}).get("code") == 2

    EBPF_DATA["response_status"] = 2
    span = EBPFHandler.l7_flow_log_to_resource_span(EBPF_DATA)
    assert span.get("status", {}).get("code") == 0

    EBPF_DATA["response_status"] = 3
    span = EBPFHandler.l7_flow_log_to_resource_span(EBPF_DATA)
    assert span.get("status", {}).get("code") == 2


def test_kind():
    span = EBPFHandler.l7_flow_log_to_resource_span(EBPF_DATA)
    assert span.get("kind") == 3
