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

import pytest

from monitor_web.k8s.scenario import get_all_metrics, get_metrics

ALL_METRICS = [
    # 容量场景
    "node_cpu_seconds_total",
    "node_cpu_capacity_ratio",
    "node_cpu_usage_ratio",
    "node_memory_working_set_bytes",
    "node_memory_capacity_ratio",
    "node_memory_usage_ratio",
    "master_node_count",
    "worker_node_count",
    "node_pod_usage",
    "node_network_receive_bytes_total",
    "node_network_transmit_bytes_total",
    "node_network_receive_packets_total",
    "node_network_transmit_packets_total",
    # 网络场景
    "nw_container_network_receive_bytes_total",
    "nw_container_network_transmit_bytes_total",
    "nw_container_network_receive_packets_total",
    "nw_container_network_transmit_packets_total",
    "nw_container_network_receive_errors_total",
    "nw_container_network_transmit_errors_total",
    "nw_container_network_receive_errors_ratio",
    "nw_container_network_transmit_errors_ratio",
    # 性能场景
    "container_cpu_usage_seconds_total",
    "kube_pod_cpu_requests_ratio",
    "kube_pod_cpu_limits_ratio",
    "container_cpu_cfs_throttled_ratio",
    "container_memory_working_set_bytes",
    "kube_pod_memory_requests_ratio",
    "kube_pod_memory_limits_ratio",
    "container_network_receive_bytes_total",
    "container_network_transmit_bytes_total",
]

SCENARIO_LIST = ["performance", "network", "capacity"]


def test_get_all_metrics():
    assert ALL_METRICS == get_all_metrics()


@pytest.mark.parametrize(
    ["scenario", "result"],
    [
        pytest.param(
            "performance",
            [
                {
                    'id': 'CPU',
                    'name': 'CPU',
                    'children': [
                        {
                            'id': 'container_cpu_usage_seconds_total',
                            'name': 'CPU使用量',
                            'unit': 'core',
                            'unsupported_resource': [],
                        },
                        {
                            'id': 'kube_pod_cpu_requests_ratio',
                            'name': 'CPU request使用率',
                            'unit': 'percentunit',
                            'unsupported_resource': ['namespace'],
                        },
                        {
                            'id': 'kube_pod_cpu_limits_ratio',
                            'name': 'CPU limit使用率',
                            'unit': 'percentunit',
                            'unsupported_resource': ['namespace'],
                        },
                        {
                            'id': 'container_cpu_cfs_throttled_ratio',
                            'name': 'CPU 限流占比',
                            'unit': 'percentunit',
                            'unsupported_resource': [],
                        },
                    ],
                },
                {
                    'id': 'memory',
                    'name': '内存',
                    'children': [
                        {
                            'id': 'container_memory_working_set_bytes',
                            'name': '内存使用量(Working Set)',
                            'unit': 'bytes',
                            'unsupported_resource': [],
                        },
                        {
                            'id': 'kube_pod_memory_requests_ratio',
                            'name': '内存 request使用率',
                            'unit': 'percentunit',
                            'unsupported_resource': ['namespace'],
                        },
                        {
                            'id': 'kube_pod_memory_limits_ratio',
                            'name': '内存 limit使用率',
                            'unit': 'percentunit',
                            'unsupported_resource': ['namespace'],
                        },
                    ],
                },
                {
                    'id': 'network',
                    'name': '流量',
                    'children': [
                        {
                            'id': 'container_network_receive_bytes_total',
                            'name': '网络入带宽',
                            'unit': 'Bps',
                            'unsupported_resource': ['container'],
                        },
                        {
                            'id': 'container_network_transmit_bytes_total',
                            'name': '网络出带宽',
                            'unit': 'Bps',
                            'unsupported_resource': ['container'],
                        },
                    ],
                },
            ],
        ),
        pytest.param(
            "network",
            [
                {
                    'id': 'traffic',
                    'name': '流量',
                    'children': [
                        {
                            'id': 'nw_container_network_receive_bytes_total',
                            'name': '网络入带宽',
                            'unit': 'Bps',
                            'unsupported_resource': [],
                        },
                        {
                            'id': 'nw_container_network_transmit_bytes_total',
                            'name': '网络出带宽',
                            'unit': 'Bps',
                            'unsupported_resource': [],
                        },
                    ],
                },
                {
                    'id': 'packets',
                    'name': '包量',
                    'children': [
                        {
                            'id': 'nw_container_network_receive_packets_total',
                            'name': '网络入包量',
                            'unit': 'pps',
                            'unsupported_resource': [],
                        },
                        {
                            'id': 'nw_container_network_transmit_packets_total',
                            'name': '网络出包量',
                            'unit': 'pps',
                            'unsupported_resource': [],
                        },
                        {
                            'id': 'nw_container_network_receive_errors_total',
                            'name': '网络入丢包量',
                            'unit': 'pps',
                            'unsupported_resource': [],
                        },
                        {
                            'id': 'nw_container_network_transmit_errors_total',
                            'name': '网络出丢包量',
                            'unit': 'pps',
                            'unsupported_resource': [],
                        },
                        {
                            'id': 'nw_container_network_receive_errors_ratio',
                            'name': '网络入丢包率',
                            'unit': 'percentunit',
                            'unsupported_resource': [],
                        },
                        {
                            'id': 'nw_container_network_transmit_errors_ratio',
                            'name': '网络出丢包率',
                            'unit': 'percentunit',
                            'unsupported_resource': [],
                        },
                    ],
                },
            ],
        ),
        pytest.param(
            "capacity",
            [
                {
                    'id': 'CPU',
                    'name': 'CPU',
                    'children': [
                        {
                            'id': 'node_cpu_seconds_total',
                            'name': '节点CPU使用量',
                            'unit': 'core',
                            'unsupported_resource': [],
                        },
                        {
                            'id': 'node_cpu_capacity_ratio',
                            'name': '节点CPU装箱率',
                            'unit': 'percentunit',
                            'unsupported_resource': [],
                        },
                        {
                            'id': 'node_cpu_usage_ratio',
                            'name': '节点CPU使用率',
                            'unit': 'percentunit',
                            'unsupported_resource': [],
                        },
                    ],
                },
                {
                    'id': 'memory',
                    'name': '内存',
                    'children': [
                        {
                            'id': 'node_memory_working_set_bytes',
                            'name': '节点内存使用量',
                            'unit': 'bytes',
                            'unsupported_resource': [],
                        },
                        {
                            'id': 'node_memory_capacity_ratio',
                            'name': '节点内存装箱率',
                            'unit': 'percentunit',
                            'unsupported_resource': ['namespace'],
                        },
                        {
                            'id': 'node_memory_usage_ratio',
                            'name': '节点内存使用率',
                            'unit': 'percentunit',
                            'unsupported_resource': ['namespace'],
                        },
                    ],
                },
                {
                    'id': 'capacity',
                    'name': '容量',
                    'children': [
                        {
                            'id': 'master_node_count',
                            'name': '集群Master节点计数',
                            'unit': 'none',
                            'unsupported_resource': ['container'],
                        },
                        {
                            'id': 'worker_node_count',
                            'name': '集群Worker节点计数',
                            'unit': 'none',
                            'unsupported_resource': ['container'],
                        },
                        {
                            'id': 'node_pod_usage',
                            'name': '节点Pod个数使用率',
                            'unit': 'none',
                            'unsupported_resource': ['container'],
                        },
                    ],
                },
                {
                    'id': 'network',
                    'name': '网络',
                    'children': [
                        {
                            'id': 'node_network_receive_bytes_total',
                            'name': '节点网络入带宽',
                            'unit': 'Bps',
                            'unsupported_resource': [],
                        },
                        {
                            'id': 'node_network_transmit_bytes_total',
                            'name': '节点网络出带宽',
                            'unit': 'Bps',
                            'unsupported_resource': [],
                        },
                        {
                            'id': 'node_network_receive_packets_total',
                            'name': '节点网络入包量',
                            'unit': 'pps',
                            'unsupported_resource': [],
                        },
                        {
                            'id': 'node_network_transmit_packets_total',
                            'name': '节点网络出包量',
                            'unit': 'pps',
                            'unsupported_resource': [],
                        },
                    ],
                },
            ],
        ),
    ],
)
def test_get_metrics(scenario, result):
    assert get_metrics(scenario) == result
