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
import copy
import random

from apm_ebpf.handlers.l7_flow_tracing import sort_all_flows


def test_ebpf_sort_01():
    test_data_01 = [
        {
            "Enum(l7_protocol)": "HTTP",
            "Enum(response_status)": "Success",
            "Enum(tap_side)": "Client NIC",
            "_ids": [
                "7303798689530628046"
            ],
            "app_instance": "",
            "app_service": "",
            "attribute": None,
            "auto_instance": "loadgenerator-585868f98b-2xnc5",
            "childs": [
                1
            ],
            "deepflow_parent_span_id": "",
            "deepflow_span_id": "None.c.0",
            "duration": 17733,
            "end_time_us": 1700548150423219,
            "endpoint": "",
            "flow_id": "6802192598646439086",
            "id": 0,
            "l7_protocol": 20,
            "l7_protocol_str": "HTTP",
            "parent_id": -1,
            "parent_span_id": "",
            "process_id": None,
            "related_ids": [
                "1-network-7303798689530628044"
            ],
            "req_tcp_seq": 2320448903,
            "request_id": None,
            "request_resource": "/productpage",
            "request_type": "GET",
            "resource_from_vtap": "loadgenerator-585868f98b-2xnc5",
            "resp_tcp_seq": 2126587115,
            "response_status": 0,
            "selftime": 15,
            "service_uid": None,
            "service_uname": None,
            "set_parent_info": None,
            "span_id": "",
            "start_time_us": 1700548150405486,
            "syscall_cap_seq_0": 0,
            "syscall_cap_seq_1": 0,
            "syscall_trace_id_request": "0",
            "syscall_trace_id_response": "0",
            "tap": "虚拟网络",
            "tap_id": 3,
            "tap_port": "42:de:15:83",
            "tap_port_name": "eth0",
            "tap_side": "c",
            "trace_id": "",
            "vtap_id": 6,
            "x_request_id_0": "",
            "x_request_id_1": ""
        },
        {
            "Enum(l7_protocol)": "HTTP",
            "Enum(response_status)": "Success",
            "Enum(tap_side)": "Server NIC",
            "_ids": [
                "7303798689530628044"
            ],
            "app_instance": "",
            "app_service": "",
            "attribute": None,
            "auto_instance": "productpage-v1-66b87bf8f7-zcnkq",
            "childs": [],
            "deepflow_parent_span_id": "None.c.0",
            "deepflow_span_id": "None.s.1",
            "duration": 17718,
            "end_time_us": 1700548150423210,
            "endpoint": "",
            "flow_id": "6802192598646439087",
            "id": 1,
            "l7_protocol": 20,
            "l7_protocol_str": "HTTP",
            "parent_id": 0,
            "parent_span_id": "",
            "process_id": None,
            "related_ids": [
                "1-base-7303798689530628044",
                "0-network-7303798689530628046"
            ],
            "req_tcp_seq": 2320448903,
            "request_id": None,
            "request_resource": "/productpage",
            "request_type": "GET",
            "resource_from_vtap": "productpage-v1-66b87bf8f7-zcnkq",
            "resp_tcp_seq": 2126587115,
            "response_status": 0,
            "selftime": 17718,
            "service_uid": None,
            "service_uname": None,
            "set_parent_info": "trace mounted due to tcp_seq",
            "span_id": "",
            "start_time_us": 1700548150405492,
            "syscall_cap_seq_0": 0,
            "syscall_cap_seq_1": 0,
            "syscall_trace_id_request": "0",
            "syscall_trace_id_response": "0",
            "tap": "虚拟网络",
            "tap_id": 3,
            "tap_port": "d3:4f:7b:a4",
            "tap_port_name": "eth0",
            "tap_side": "s",
            "trace_id": "",
            "vtap_id": 6,
            "x_request_id_0": "",
            "x_request_id_1": ""
        }
    ]
    copy_test_data_01 = copy.deepcopy(test_data_01)
    random.shuffle(copy_test_data_01)
    ebpf_data = sort_all_flows(copy_test_data_01)

    assert len(test_data_01) == len(ebpf_data)
    assert test_data_01 == ebpf_data


def test_ebpf_sort_02():
    test_data_02 = [
        {
            "Enum(l7_protocol)": "HTTP",
            "Enum(response_status)": "Success",
            "Enum(tap_side)": "Client NIC",
            "_ids": [
                "7303775092979056209"
            ],
            "app_instance": "",
            "app_service": "",
            "attribute": None,
            "auto_instance": "productpage-v1-66b87bf8f7-zcnkq",
            "childs": [
                3
            ],
            "deepflow_parent_span_id": "",
            "deepflow_span_id": "None.c.2",
            "duration": 7034,
            "end_time_us": 1700542656677748,
            "endpoint": "",
            "flow_id": "6802170625593585553",
            "id": 2,
            "l7_protocol": 20,
            "l7_protocol_str": "HTTP",
            "parent_id": -1,
            "parent_span_id": "",
            "process_id": None,
            "related_ids": [
                "1-network-7303775092979054641",
                "3-network-7303775092979056208",
                "0-network-7303775092979054642"
            ],
            "req_tcp_seq": 2695464485,
            "request_id": None,
            "request_resource": "/reviews/0",
            "request_type": "GET",
            "resource_from_vtap": "productpage-v1-66b87bf8f7-zcnkq",
            "resp_tcp_seq": 1319506714,
            "response_status": 0,
            "selftime": 18,
            "service_uid": None,
            "service_uname": None,
            "set_parent_info": None,
            "span_id": "",
            "start_time_us": 1700542656670714,
            "syscall_cap_seq_0": 0,
            "syscall_cap_seq_1": 0,
            "syscall_trace_id_request": "0",
            "syscall_trace_id_response": "0",
            "tap": "虚拟网络",
            "tap_id": 3,
            "tap_port": "d3:4f:7b:a4",
            "tap_port_name": "eth0",
            "tap_side": "c",
            "trace_id": "",
            "vtap_id": 6,
            "x_request_id_0": "",
            "x_request_id_1": ""
        },
        {
            "Enum(l7_protocol)": "HTTP",
            "Enum(response_status)": "Success",
            "Enum(tap_side)": "Client K8s Node",
            "_ids": [
                "7303775092979056208"
            ],
            "app_instance": "",
            "app_service": "",
            "attribute": None,
            "auto_instance": "productpage-v1-66b87bf8f7-zcnkq",
            "childs": [
                0
            ],
            "deepflow_parent_span_id": "None.c.2",
            "deepflow_span_id": "None.c-nd.3",
            "duration": 7016,
            "end_time_us": 1700542656677737,
            "endpoint": "",
            "flow_id": "6802170625593585554",
            "id": 3,
            "l7_protocol": 20,
            "l7_protocol_str": "HTTP",
            "parent_id": 2,
            "parent_span_id": "",
            "process_id": None,
            "related_ids": [
                "1-network-7303775092979054641",
                "2-network-7303775092979056209",
                "0-network-7303775092979054642"
            ],
            "req_tcp_seq": 2695464485,
            "request_id": None,
            "request_resource": "/reviews/0",
            "request_type": "GET",
            "resource_from_vtap": "10.0.7.93",
            "resp_tcp_seq": 1319506714,
            "response_status": 0,
            "selftime": 108,
            "service_uid": None,
            "service_uname": None,
            "set_parent_info": "trace mounted due to tcp_seq",
            "span_id": "",
            "start_time_us": 1700542656670721,
            "syscall_cap_seq_0": 0,
            "syscall_cap_seq_1": 0,
            "syscall_trace_id_request": "0",
            "syscall_trace_id_response": "0",
            "tap": "虚拟网络",
            "tap_id": 3,
            "tap_port": "00:db:d5:25",
            "tap_port_name": "eth0",
            "tap_side": "c-nd",
            "trace_id": "",
            "vtap_id": 6,
            "x_request_id_0": "",
            "x_request_id_1": ""
        },
        {
            "Enum(l7_protocol)": "HTTP",
            "Enum(response_status)": "Success",
            "Enum(tap_side)": "Server K8s Node",
            "_ids": [
                "7303775092979054642"
            ],
            "app_instance": "",
            "app_service": "",
            "attribute": None,
            "auto_instance": "reviews-v3-85fdcf54cc-25prt",
            "childs": [
                1
            ],
            "deepflow_parent_span_id": "None.c-nd.3",
            "deepflow_span_id": "None.s-nd.0",
            "duration": 6908,
            "end_time_us": 1700542656677537,
            "endpoint": "",
            "flow_id": "6802170625606372296",
            "id": 0,
            "l7_protocol": 20,
            "l7_protocol_str": "HTTP",
            "parent_id": 3,
            "parent_span_id": "",
            "process_id": None,
            "related_ids": [
                "1-network-7303775092979054641",
                "2-network-7303775092979056209",
                "3-network-7303775092979056208"
            ],
            "req_tcp_seq": 2695464485,
            "request_id": None,
            "request_resource": "/reviews/0",
            "request_type": "GET",
            "resource_from_vtap": "10.0.7.36",
            "resp_tcp_seq": 1319506714,
            "response_status": 0,
            "selftime": 15,
            "service_uid": None,
            "service_uname": None,
            "set_parent_info": "trace mounted due to tcp_seq",
            "span_id": "",
            "start_time_us": 1700542656670629,
            "syscall_cap_seq_0": 0,
            "syscall_cap_seq_1": 0,
            "syscall_trace_id_request": "0",
            "syscall_trace_id_response": "0",
            "tap": "虚拟网络",
            "tap_id": 3,
            "tap_port": "00:38:45:06",
            "tap_port_name": "eth0",
            "tap_side": "s-nd",
            "trace_id": "",
            "vtap_id": 3,
            "x_request_id_0": "",
            "x_request_id_1": ""
        },
        {
            "Enum(l7_protocol)": "HTTP",
            "Enum(response_status)": "Success",
            "Enum(tap_side)": "Server NIC",
            "_ids": [
                "7303775092979054641"
            ],
            "app_instance": "",
            "app_service": "",
            "attribute": None,
            "auto_instance": "reviews-v3-85fdcf54cc-25prt",
            "childs": [],
            "deepflow_parent_span_id": "None.s-nd.0",
            "deepflow_span_id": "None.s.1",
            "duration": 6893,
            "end_time_us": 1700542656677528,
            "endpoint": "",
            "flow_id": "6802170625606372297",
            "id": 1,
            "l7_protocol": 20,
            "l7_protocol_str": "HTTP",
            "parent_id": 0,
            "parent_span_id": "",
            "process_id": None,
            "related_ids": [
                "1-base-7303775092979054641",
                "2-network-7303775092979056209",
                "3-network-7303775092979056208",
                "0-network-7303775092979054642"
            ],
            "req_tcp_seq": 2695464485,
            "request_id": None,
            "request_resource": "/reviews/0",
            "request_type": "GET",
            "resource_from_vtap": "reviews-v3-85fdcf54cc-25prt",
            "resp_tcp_seq": 1319506714,
            "response_status": 0,
            "selftime": 6893,
            "service_uid": None,
            "service_uname": None,
            "set_parent_info": "trace mounted due to tcp_seq",
            "span_id": "",
            "start_time_us": 1700542656670635,
            "syscall_cap_seq_0": 0,
            "syscall_cap_seq_1": 0,
            "syscall_trace_id_request": "0",
            "syscall_trace_id_response": "0",
            "tap": "虚拟网络",
            "tap_id": 3,
            "tap_port": "8c:69:2e:11",
            "tap_port_name": "eth0",
            "tap_side": "s",
            "trace_id": "",
            "vtap_id": 3,
            "x_request_id_0": "",
            "x_request_id_1": ""
        }
    ]
    copy_test_data_02 = copy.deepcopy(test_data_02)
    random.shuffle(copy_test_data_02)
    ebpf_data = sort_all_flows(copy_test_data_02)

    assert len(test_data_02) == len(ebpf_data)
    assert test_data_02 == ebpf_data


def test_ebpf_sort_03():
    test_data_03 = [
        {
            "Enum(l7_protocol)": "HTTP",
            "Enum(response_status)": "Success",
            "Enum(tap_side)": "Client NIC",
            "_ids": [
                "7303775092979054640"
            ],
            "app_instance": "",
            "app_service": "",
            "attribute": None,
            "auto_instance": "reviews-v3-85fdcf54cc-25prt",
            "childs": [
                1
            ],
            "deepflow_parent_span_id": "",
            "deepflow_span_id": "None.c.0",
            "duration": 1096,
            "end_time_us": 1700542656676373,
            "endpoint": "",
            "flow_id": "6802170625606372300",
            "id": 0,
            "l7_protocol": 20,
            "l7_protocol_str": "HTTP",
            "parent_id": -1,
            "parent_span_id": "",
            "process_id": None,
            "related_ids": [
                "3-network-7303775092979056837",
                "1-network-7303775092979054639",
                "2-network-7303775092979056838"
            ],
            "req_tcp_seq": 776912665,
            "request_id": None,
            "request_resource": "/ratings/0",
            "request_type": "GET",
            "resource_from_vtap": "reviews-v3-85fdcf54cc-25prt",
            "resp_tcp_seq": 2791666805,
            "response_status": 0,
            "selftime": 13,
            "service_uid": None,
            "service_uname": None,
            "set_parent_info": None,
            "span_id": "",
            "start_time_us": 1700542656675277,
            "syscall_cap_seq_0": 0,
            "syscall_cap_seq_1": 0,
            "syscall_trace_id_request": "0",
            "syscall_trace_id_response": "0",
            "tap": "虚拟网络",
            "tap_id": 3,
            "tap_port": "8c:69:2e:11",
            "tap_port_name": "eth0",
            "tap_side": "c",
            "trace_id": "",
            "vtap_id": 3,
            "x_request_id_0": "",
            "x_request_id_1": ""
        },
        {
            "Enum(l7_protocol)": "HTTP",
            "Enum(response_status)": "Success",
            "Enum(tap_side)": "Client K8s Node",
            "_ids": [
                "7303775092979054639"
            ],
            "app_instance": "",
            "app_service": "",
            "attribute": None,
            "auto_instance": "reviews-v3-85fdcf54cc-25prt",
            "childs": [
                2
            ],
            "deepflow_parent_span_id": "None.c.0",
            "deepflow_span_id": "None.c-nd.1",
            "duration": 1083,
            "end_time_us": 1700542656676367,
            "endpoint": "",
            "flow_id": "6802170625606372301",
            "id": 1,
            "l7_protocol": 20,
            "l7_protocol_str": "HTTP",
            "parent_id": 0,
            "parent_span_id": "",
            "process_id": None,
            "related_ids": [
                "3-network-7303775092979056837",
                "2-network-7303775092979056838",
                "0-network-7303775092979054640"
            ],
            "req_tcp_seq": 776912665,
            "request_id": None,
            "request_resource": "/ratings/0",
            "request_type": "GET",
            "resource_from_vtap": "10.0.7.36",
            "resp_tcp_seq": 2791666805,
            "response_status": 0,
            "selftime": 677,
            "service_uid": None,
            "service_uname": None,
            "set_parent_info": "trace mounted due to tcp_seq",
            "span_id": "",
            "start_time_us": 1700542656675284,
            "syscall_cap_seq_0": 0,
            "syscall_cap_seq_1": 0,
            "syscall_trace_id_request": "0",
            "syscall_trace_id_response": "0",
            "tap": "虚拟网络",
            "tap_id": 3,
            "tap_port": "00:38:45:06",
            "tap_port_name": "eth0",
            "tap_side": "c-nd",
            "trace_id": "",
            "vtap_id": 3,
            "x_request_id_0": "",
            "x_request_id_1": ""
        },
        {
            "Enum(l7_protocol)": "HTTP",
            "Enum(response_status)": "Success",
            "Enum(tap_side)": "Server K8s Node",
            "_ids": [
                "7303775092979056838"
            ],
            "app_instance": "",
            "app_service": "",
            "attribute": None,
            "auto_instance": "ratings-v1-6d57c9fd89-brzwc",
            "childs": [
                3
            ],
            "deepflow_parent_span_id": "None.c-nd.1",
            "deepflow_span_id": "None.s-nd.2",
            "duration": 406,
            "end_time_us": 1700542656675832,
            "endpoint": "",
            "flow_id": "6802170625605333214",
            "id": 2,
            "l7_protocol": 20,
            "l7_protocol_str": "HTTP",
            "parent_id": 1,
            "parent_span_id": "",
            "process_id": None,
            "related_ids": [
                "3-network-7303775092979056837",
                "1-network-7303775092979054639",
                "0-network-7303775092979054640"
            ],
            "req_tcp_seq": 776912665,
            "request_id": None,
            "request_resource": "/ratings/0",
            "request_type": "GET",
            "resource_from_vtap": "10.0.6.4",
            "resp_tcp_seq": 2791666805,
            "response_status": 0,
            "selftime": 18,
            "service_uid": None,
            "service_uname": None,
            "set_parent_info": "trace mounted due to tcp_seq",
            "span_id": "",
            "start_time_us": 1700542656675426,
            "syscall_cap_seq_0": 0,
            "syscall_cap_seq_1": 0,
            "syscall_trace_id_request": "0",
            "syscall_trace_id_response": "0",
            "tap": "虚拟网络",
            "tap_id": 3,
            "tap_port": "00:45:c5:2b",
            "tap_port_name": "eth0",
            "tap_side": "s-nd",
            "trace_id": "",
            "vtap_id": 8,
            "x_request_id_0": "",
            "x_request_id_1": ""
        },
        {
            "Enum(l7_protocol)": "HTTP",
            "Enum(response_status)": "Success",
            "Enum(tap_side)": "Server NIC",
            "_ids": [
                "7303775092979056837"
            ],
            "app_instance": "",
            "app_service": "",
            "attribute": None,
            "auto_instance": "ratings-v1-6d57c9fd89-brzwc",
            "childs": [],
            "deepflow_parent_span_id": "None.s-nd.2",
            "deepflow_span_id": "None.s.3",
            "duration": 388,
            "end_time_us": 1700542656675824,
            "endpoint": "",
            "flow_id": "6802170625605333215",
            "id": 3,
            "l7_protocol": 20,
            "l7_protocol_str": "HTTP",
            "parent_id": 2,
            "parent_span_id": "",
            "process_id": None,
            "related_ids": [
                "3-base-7303775092979056837",
                "1-network-7303775092979054639",
                "2-network-7303775092979056838",
                "0-network-7303775092979054640"
            ],
            "req_tcp_seq": 776912665,
            "request_id": None,
            "request_resource": "/ratings/0",
            "request_type": "GET",
            "resource_from_vtap": "ratings-v1-6d57c9fd89-brzwc",
            "resp_tcp_seq": 2791666805,
            "response_status": 0,
            "selftime": 388,
            "service_uid": None,
            "service_uname": None,
            "set_parent_info": "trace mounted due to tcp_seq",
            "span_id": "",
            "start_time_us": 1700542656675436,
            "syscall_cap_seq_0": 0,
            "syscall_cap_seq_1": 0,
            "syscall_trace_id_request": "0",
            "syscall_trace_id_response": "0",
            "tap": "虚拟网络",
            "tap_id": 3,
            "tap_port": "64:50:cf:1d",
            "tap_port_name": "eth0",
            "tap_side": "s",
            "trace_id": "",
            "vtap_id": 8,
            "x_request_id_0": "",
            "x_request_id_1": ""
        }
    ]
    copy_test_data_03 = copy.deepcopy(test_data_03)
    random.shuffle(copy_test_data_03)
    ebpf_data = sort_all_flows(copy_test_data_03)

    assert len(test_data_03) == len(ebpf_data)
    assert test_data_03 == ebpf_data
