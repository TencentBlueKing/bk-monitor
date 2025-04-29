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

from typing import List

import pytest

from monitor_web.k8s.resources import (
    GetScenarioMetric,
    ListBCSCluster,
    ScenarioMetricList,
)


class TestGetScenarioMetric:
    argnames: List[str] = ["scenario", "metric_id", "name", "unit", "unsupported_resource"]
    argvalues: List[pytest.param] = [
        # performance
        pytest.param(
            "performance",
            "container_cpu_usage_seconds_total",
            "CPU使用量",
            "core",
            [],
            id="container_cpu_usage_seconds_total",
        ),
        pytest.param(
            "performance",
            "kube_pod_cpu_requests_ratio",
            "CPU request使用率",
            "percentunit",
            ["namespace"],
            id="kube_pod_cpu_requests_ratio",
        ),
        pytest.param(
            "performance",
            "kube_pod_cpu_limits_ratio",
            "CPU limit使用率",
            "percentunit",
            ["namespace"],
            id="kube_pod_cpu_limits_ratio",
        ),
        pytest.param(
            "performance",
            "container_cpu_cfs_throttled_ratio",
            "CPU 限流占比",
            "percentunit",
            [],
            id="container_cpu_cfs_throttled_ratio",
        ),
        pytest.param(
            "performance",
            "container_memory_working_set_bytes",
            "内存使用量(Working Set)",
            "bytes",
            [],
            id="container_memory_working_set_bytes",
        ),
        pytest.param(
            "performance",
            "kube_pod_memory_requests_ratio",
            "内存 request使用率",
            "percentunit",
            ["namespace"],
            id="kube_pod_memory_requests_ratio",
        ),
        pytest.param(
            "performance",
            "kube_pod_memory_limits_ratio",
            "内存 limit使用率",
            "percentunit",
            ["namespace"],
            id="kube_pod_memory_limits_ratio",
        ),
        pytest.param(
            "performance",
            "container_network_receive_bytes_total",
            "网络入带宽",
            "Bps",
            ["container"],
            id="container_network_receive_bytes_total",
        ),
        pytest.param(
            "performance",
            "container_network_transmit_bytes_total",
            "网络出带宽",
            "Bps",
            ["container"],
            id="container_network_transmit_bytes_total",
        ),
        # network
        pytest.param(
            "network",
            "nw_container_network_receive_bytes_total",
            "网络入带宽",
            "Bps",
            [],
            id="nw_container_network_receive_bytes_total",
        ),
        pytest.param(
            "network",
            "nw_container_network_transmit_bytes_total",
            "网络出带宽",
            "Bps",
            [],
            id="nw_container_network_transmit_bytes_total",
        ),
        pytest.param(
            "network",
            "nw_container_network_receive_packets_total",
            "网络入包量",
            "pps",
            [],
            id="nw_container_network_receive_packets_total",
        ),
        pytest.param(
            "network",
            "nw_container_network_transmit_packets_total",
            "网络出包量",
            "pps",
            [],
            id="nw_container_network_transmit_packets_total",
        ),
        pytest.param(
            "network",
            "nw_container_network_receive_errors_total",
            "网络入丢包量",
            "pps",
            [],
            id="nw_container_network_receive_errors_total",
        ),
        pytest.param(
            "network",
            "nw_container_network_transmit_errors_total",
            "网络出丢包量",
            "pps",
            [],
            id="nw_container_network_transmit_errors_total",
        ),
        pytest.param(
            "network",
            "nw_container_network_receive_errors_ratio",
            "网络入丢包率",
            "percentunit",
            [],
            id="nw_container_network_receive_errors_ratio",
        ),
        pytest.param(
            "network",
            "nw_container_network_transmit_errors_ratio",
            "网络出丢包率",
            "percentunit",
            [],
            id="nw_container_network_transmit_errors_ratio",
        ),
    ]

    @pytest.mark.parametrize(argnames, argvalues)
    def test_with_metric(self, scenario, metric_id, name, unit, unsupported_resource):
        validated_request_data = {
            "bk_biz_id": 2,
            "scenario": scenario,
            "metric_id": metric_id,
        }

        metric = GetScenarioMetric()(validated_request_data)
        assert metric == {
            "unit": unit,
            "name": name,
            "id": metric_id,
            "unsupported_resource": unsupported_resource,
        }

    def test_with_unexist_metric(self):
        validated_request_data = {
            "bk_biz_id": 2,
            "scenario": "performance",
            "metric_id": "eunexist_metric",
        }

        metric = GetScenarioMetric()(validated_request_data)
        assert {} == metric


class TestScenarioMetricList:
    @pytest.mark.parametrize(
        ["scenario", "except_metric_list"],
        [
            pytest.param(
                "performance",
                [
                    {
                        "id": "CPU",
                        "name": "CPU",
                        "children": [
                            {
                                "id": "container_cpu_usage_seconds_total",
                                "name": "CPU使用量",
                                "unit": "core",
                                "unsupported_resource": [],
                            },
                            {
                                "id": "kube_pod_cpu_requests_ratio",
                                "name": "CPU request使用率",
                                "unit": "percentunit",
                                "unsupported_resource": ["namespace"],
                            },
                            {
                                "id": "kube_pod_cpu_limits_ratio",
                                "name": "CPU limit使用率",
                                "unit": "percentunit",
                                "unsupported_resource": ["namespace"],
                            },
                            {
                                "id": "container_cpu_cfs_throttled_ratio",
                                "name": "CPU 限流占比",
                                "unit": "percentunit",
                                "unsupported_resource": [],
                            },
                        ],
                    },
                    {
                        "id": "memory",
                        "name": "内存",
                        "children": [
                            {
                                "id": "container_memory_working_set_bytes",
                                "name": "内存使用量(Working Set)",
                                "unit": "bytes",
                                "unsupported_resource": [],
                            },
                            {
                                "id": "kube_pod_memory_requests_ratio",
                                "name": "内存 request使用率",
                                "unit": "percentunit",
                                "unsupported_resource": ["namespace"],
                            },
                            {
                                "id": "kube_pod_memory_limits_ratio",
                                "name": "内存 limit使用率",
                                "unit": "percentunit",
                                "unsupported_resource": ["namespace"],
                            },
                        ],
                    },
                    {
                        "id": "network",
                        "name": "流量",
                        "children": [
                            {
                                "id": "container_network_receive_bytes_total",
                                "name": "网络入带宽",
                                "unit": "Bps",
                                "unsupported_resource": ["container"],
                            },
                            {
                                "id": "container_network_transmit_bytes_total",
                                "name": "网络出带宽",
                                "unit": "Bps",
                                "unsupported_resource": ["container"],
                            },
                        ],
                    },
                ],
                id="performance",
            ),
            pytest.param(
                "network",
                [
                    {
                        "id": "traffic",
                        "name": "流量",
                        "children": [
                            {
                                "id": "nw_container_network_receive_bytes_total",
                                "name": "网络入带宽",
                                "unit": "Bps",
                                "unsupported_resource": [],
                            },
                            {
                                "id": "nw_container_network_transmit_bytes_total",
                                "name": "网络出带宽",
                                "unit": "Bps",
                                "unsupported_resource": [],
                            },
                        ],
                    },
                    {
                        "id": "packets",
                        "name": "包量",
                        "children": [
                            {
                                "id": "nw_container_network_receive_packets_total",
                                "name": "网络入包量",
                                "unit": "pps",
                                "unsupported_resource": [],
                            },
                            {
                                "id": "nw_container_network_transmit_packets_total",
                                "name": "网络出包量",
                                "unit": "pps",
                                "unsupported_resource": [],
                            },
                            {
                                "id": "nw_container_network_receive_errors_total",
                                "name": "网络入丢包量",
                                "unit": "pps",
                                "unsupported_resource": [],
                            },
                            {
                                "id": "nw_container_network_transmit_errors_total",
                                "name": "网络出丢包量",
                                "unit": "pps",
                                "unsupported_resource": [],
                            },
                            {
                                "id": "nw_container_network_receive_errors_ratio",
                                "name": "网络入丢包率",
                                "unit": "percentunit",
                                "unsupported_resource": [],
                            },
                            {
                                "id": "nw_container_network_transmit_errors_ratio",
                                "name": "网络出丢包率",
                                "unit": "percentunit",
                                "unsupported_resource": [],
                            },
                        ],
                    },
                ],
                id="network",
            ),
        ],
    )
    def test_with_scenario(self, scenario, except_metric_list):
        validated_request_data = {
            "bk_biz_id": 2,
            "scenario": scenario,
        }
        metric_list = ScenarioMetricList()(validated_request_data)
        assert metric_list == except_metric_list


class TestListBCSCluster:
    def test_list_bcs_cluster(self, create_bcs_cluster):
        validated_request_data = {
            "bk_biz_id": 2,
        }
        bcs_cluster_list = ListBCSCluster()(validated_request_data)
        assert bcs_cluster_list == [{"id": "BCS-K8S-00000", "name": "蓝鲸7.0(BCS-K8S-00000)"}]
