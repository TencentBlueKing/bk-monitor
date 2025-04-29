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

import mock
import pytest
from django.utils import timezone

from bkmonitor.models import (
    BCSCluster,
    BCSContainer,
    BCSIngress,
    BCSNode,
    BCSPod,
    BCSService,
    BCSWorkload,
)
from monitor_web.k8s.resources import (
    GetResourceDetail,
    GetScenarioMetric,
    ListBCSCluster,
    ScenarioMetricList,
)

"""公共resource"""


@pytest.mark.django_db
class TestListBCSCluster:
    def test_list_bcs_cluster(self, create_bcs_cluster):
        validated_request_data = {
            "bk_biz_id": 2,
        }
        bcs_cluster_list = ListBCSCluster()(**validated_request_data)
        assert bcs_cluster_list == [{"id": "BCS-K8S-00000", "name": "蓝鲸7.0(BCS-K8S-00000)"}]


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
            pytest.param(
                "capacity",
                [
                    {
                        "id": "CPU",
                        "name": "CPU",
                        "children": [
                            {
                                "id": "node_cpu_seconds_total",
                                "name": "节点CPU使用量",
                                "unit": "core",
                                "unsupported_resource": [],
                            },
                            {
                                "id": "node_cpu_capacity_ratio",
                                "name": "节点CPU装箱率",
                                "unit": "percentunit",
                                "unsupported_resource": [],
                            },
                            {
                                "id": "node_cpu_usage_ratio",
                                "name": "节点CPU使用率",
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
                                "id": "node_memory_working_set_bytes",
                                "name": "节点内存使用量",
                                "unit": "bytes",
                                "unsupported_resource": [],
                            },
                            {
                                "id": "node_memory_capacity_ratio",
                                "name": "节点内存装箱率",
                                "unit": "percentunit",
                                "unsupported_resource": ["namespace"],
                            },
                            {
                                "id": "node_memory_usage_ratio",
                                "name": "节点内存使用率",
                                "unit": "percentunit",
                                "unsupported_resource": ["namespace"],
                            },
                        ],
                    },
                    {
                        "id": "capacity",
                        "name": "容量",
                        "children": [
                            {
                                "id": "master_node_count",
                                "name": "集群Master节点计数",
                                "unit": "none",
                                "unsupported_resource": ["container"],
                            },
                            {
                                "id": "worker_node_count",
                                "name": "集群Worker节点计数",
                                "unit": "none",
                                "unsupported_resource": ["container"],
                            },
                            {
                                "id": "node_pod_usage",
                                "name": "节点Pod个数使用率",
                                "unit": "none",
                                "unsupported_resource": ["container"],
                            },
                        ],
                    },
                    {
                        "id": "network",
                        "name": "网络",
                        "children": [
                            {
                                "id": "node_network_receive_bytes_total",
                                "name": "节点网络入带宽",
                                "unit": "Bps",
                                "unsupported_resource": [],
                            },
                            {
                                "id": "node_network_transmit_bytes_total",
                                "name": "节点网络出带宽",
                                "unit": "Bps",
                                "unsupported_resource": [],
                            },
                            {
                                "id": "node_network_receive_packets_total",
                                "name": "节点网络入包量",
                                "unit": "pps",
                                "unsupported_resource": [],
                            },
                            {
                                "id": "node_network_transmit_packets_total",
                                "name": "节点网络出包量",
                                "unit": "pps",
                                "unsupported_resource": [],
                            },
                        ],
                    },
                ],
                id="capacity",
            ),
        ],
    )
    def test_ScenarioMetricList(self, scenario, except_metric_list):
        validated_request_data = {
            "bk_biz_id": 2,
            "scenario": scenario,
        }
        metric_list = ScenarioMetricList()(validated_request_data)
        assert metric_list == except_metric_list


class TestGetScenarioMetric:
    argnames: List[str] = [
        "scenario",
        "metric_id",
        "name",
        "unit",
        "unsupported_resource",
    ]
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
        # capacity
        pytest.param(
            "capacity",
            "node_cpu_seconds_total",
            "节点CPU使用量",
            "core",
            [],
            id="node_cpu_seconds_total",
        ),
        pytest.param(
            "capacity",
            "node_cpu_capacity_ratio",
            "节点CPU装箱率",
            "percentunit",
            [],
            id="node_cpu_capacity_ratio",
        ),
        pytest.param(
            "capacity",
            "node_cpu_usage_ratio",
            "节点CPU使用率",
            "percentunit",
            [],
            id="node_cpu_usage_ratio",
        ),
        pytest.param(
            "capacity",
            "node_memory_working_set_bytes",
            "节点内存使用量",
            "bytes",
            [],
            id="node_memory_working_set_bytes",
        ),
        pytest.param(
            "capacity",
            "node_memory_capacity_ratio",
            "节点内存装箱率",
            "percentunit",
            ["namespace"],
            id="node_memory_capacity_ratio",
        ),
        pytest.param(
            "capacity",
            "node_memory_usage_ratio",
            "节点内存使用率",
            "percentunit",
            ["namespace"],
            id="node_memory_usage_ratio",
        ),
        pytest.param(
            "capacity",
            "master_node_count",
            "集群Master节点计数",
            "none",
            ["container"],
            id="master_node_count",
        ),
        pytest.param(
            "capacity",
            "worker_node_count",
            "集群Worker节点计数",
            "none",
            ["container"],
            id="worker_node_count",
        ),
        pytest.param(
            "capacity",
            "node_pod_usage",
            "节点Pod个数使用率",
            "none",
            ["container"],
            id="node_pod_usage",
        ),
        pytest.param(
            "capacity",
            "node_network_receive_bytes_total",
            "节点网络入带宽",
            "Bps",
            [],
            id="node_network_receive_bytes_total",
        ),
        pytest.param(
            "capacity",
            "node_network_transmit_bytes_total",
            "节点网络出带宽",
            "Bps",
            [],
            id="node_network_transmit_bytes_total",
        ),
        pytest.param(
            "capacity",
            "node_network_receive_packets_total",
            "节点网络入包量",
            "pps",
            [],
            id="node_network_receive_packets_total",
        ),
        pytest.param(
            "capacity",
            "node_network_transmit_packets_total",
            "节点网络出包量",
            "pps",
            [],
            id="node_network_transmit_packets_total",
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


@pytest.mark.django_db
class TestGetResourceDetail:
    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    def test_with_pod(self, graph_unify_query):
        # craete_pod
        BCSPod(
            bk_biz_id=2,
            bcs_cluster_id="BCS-K8S-00000",
            namespace="blueking",
            name="bk-monitor-web-worker-784b79c9f-s9fhh",
            node_name="node-127-0-0-1",
            node_ip="127.0.0.1",
            workload_type="Deployment",
            workload_name="bk-monitor-web-worker",
            total_container_count=1,
            ready_container_count=1,
            pod_ip="127.0.0.1",
            restarts=0,
            created_at=timezone.now(),
            last_synced_at=timezone.now(),
        ).save()

        validated_request_data = {
            "bk_biz_id": 2,
            "bcs_cluster_id": "BCS-K8S-00000",
            "resource_type": "pod",
            "namespace": "blueking",
            "pod_name": "bk-monitor-web-worker-784b79c9f-s9fhh",
        }
        expected_result = [
            {
                "key": "name",
                "name": "Pod名称",
                "type": "string",
                "value": "bk-monitor-web-worker-784b79c9f-s9fhh",
            },
            {"key": "status", "name": "运行状态", "type": "string", "value": ""},
            {
                "key": "ready",
                "name": "是否就绪(实例运行数/期望数)",
                "type": "string",
                "value": "1/1",
            },
            {
                "key": "bcs_cluster_id",
                "name": "集群ID",
                "type": "string",
                "value": "BCS-K8S-00000",
            },
            {
                "key": "bk_cluster_name",
                "name": "集群名称",
                "type": "string",
                "value": "",
            },
            {
                "key": "namespace",
                "name": "NameSpace",
                "type": "string",
                "value": "blueking",
            },
            {
                "key": "total_container_count",
                "name": "容器数量",
                "type": "string",
                "value": 1,
            },
            {"key": "restarts", "name": "重启次数", "type": "number", "value": 0},
            {
                "key": "monitor_status",
                "name": "采集状态",
                "type": "status",
                "value": {"type": "failed", "text": "异常"},
            },
            {"key": "age", "name": "存活时间", "type": "string", "value": "a moment"},
            {
                "key": "request_cpu_usage_ratio",
                "name": "CPU使用率(request)",
                "type": "progress",
                "value": {"value": 0, "label": "", "status": "NODATA"},
            },
            {
                "key": "limit_cpu_usage_ratio",
                "name": "CPU使用率(limit)",
                "type": "progress",
                "value": {"value": 0, "label": "", "status": "NODATA"},
            },
            {
                "key": "request_memory_usage_ratio",
                "name": "内存使用率(request)",
                "type": "progress",
                "value": {"value": 0, "label": "", "status": "NODATA"},
            },
            {
                "key": "limit_memory_usage_ratio",
                "name": "内存使用率(limit) ",
                "type": "progress",
                "value": {"value": 0, "label": "", "status": "NODATA"},
            },
            {
                "key": "resource_usage_cpu",
                "name": "CPU使用量",
                "type": "string",
                "value": "",
            },
            {
                "key": "resource_usage_memory",
                "name": "内存使用量",
                "type": "string",
                "value": "",
            },
            {
                "key": "resource_usage_disk",
                "name": "磁盘使用量",
                "type": "string",
                "value": "",
            },
            {
                "key": "resource_requests_cpu",
                "name": "cpu request",
                "type": "string",
                "value": "0",
            },
            {
                "key": "resource_limits_cpu",
                "name": "cpu limit",
                "type": "string",
                "value": "0",
            },
            {
                "key": "resource_requests_memory",
                "name": "memory request",
                "type": "string",
                "value": "0",
            },
            {
                "key": "resource_limits_memory",
                "name": "memory limit",
                "type": "string",
                "value": "0",
            },
            {"key": "pod_ip", "name": "Pod IP", "type": "string", "value": "127.0.0.1"},
            {
                "key": "node_ip",
                "name": "节点IP",
                "type": "string",
                "value": "127.0.0.1",
            },
            {
                "key": "node_name",
                "name": "节点名称",
                "type": "string",
                "value": "node-127-0-0-1",
            },
            {
                "key": "workload",
                "name": "工作负载",
                "type": "string",
                "value": "Deployment:bk-monitor-web-worker",
            },
            {"key": "label_list", "name": "标签", "type": "kv", "value": []},
            {
                "key": "images",
                "name": "镜像",
                "type": "list",
                "value": [""],
            },
            {
                "key": "ingress_service_relation",
                "name": "ingress/service关联",
                "type": "list",
                "value": ["ingress1/service1", "ingress2/service1", "-/service2"],
            },
        ]

        mock_return_values = [
            {"series": [{"dimensions": {"service": "service1"}}, {"dimensions": {"service": "service2"}}]},
            {
                "series": [
                    {"dimensions": {"ingress": "ingress1"}},
                    {"dimensions": {"ingress": "ingress2"}},
                ]
            },
            {"series": []},
        ]

        graph_unify_query.side_effect = mock_return_values

        resource_detail = GetResourceDetail()(validated_request_data)

        assert resource_detail == expected_result

    def test_with_workload(self):
        # craete_workload
        BCSWorkload(
            bk_biz_id=2,
            bcs_cluster_id="BCS-K8S-00000",
            namespace="blueking",
            type="Deployment",
            name="bk-monitor-web",
            created_at=timezone.now(),
            last_synced_at=timezone.now(),
            pod_count=0,
        ).save()

        validated_request_data = {
            "bk_biz_id": 2,
            "bcs_cluster_id": "BCS-K8S-00000",
            "resource_type": "workload",
            "namespace": "blueking",
            "workload_name": "bk-monitor-web",
            "workload_type": "Deployment",
        }
        expected_result = [
            {
                "key": "name",
                "name": "工作负载名称",
                "type": "string",
                "value": "bk-monitor-web",
            },
            {
                "key": "bcs_cluster_id",
                "name": "集群ID",
                "type": "string",
                "value": "BCS-K8S-00000",
            },
            {
                "key": "bk_cluster_name",
                "name": "集群名称",
                "type": "string",
                "value": "",
            },
            {
                "key": "namespace",
                "name": "NameSpace",
                "type": "string",
                "value": "blueking",
            },
            {"key": "status", "name": "运行状态", "type": "string", "value": ""},
            {
                "key": "monitor_status",
                "name": "采集状态",
                "type": "status",
                "value": {"type": "failed", "text": "异常"},
            },
            {"key": "type", "name": "类型", "type": "string", "value": "Deployment"},
            {
                "key": "images",
                "name": "镜像",
                "type": "string",
                "value": "",
            },
            {"key": "label_list", "name": "标签", "type": "kv", "value": []},
            {"key": "pod_count", "name": "Pod数量", "type": "string", "value": 0},
            {
                "key": "container_count",
                "name": "容器数量",
                "type": "string",
                "value": 0,
            },
            {
                "key": "resources",
                "name": "资源",
                "type": "kv",
                "value": [],
            },
            {"key": "age", "name": "存活时间", "type": "string", "value": "a moment"},
        ]
        resource_detail = GetResourceDetail()(validated_request_data)

        assert resource_detail == expected_result

    def test_with_container(self):
        # craete_container
        BCSContainer(
            bk_biz_id=2,
            bcs_cluster_id="BCS-K8S-00000",
            name="bk-monitor-web-container",
            namespace="blueking",
            pod_name="bk-monitor-web-pod",
            workload_type="Deployment",
            workload_name="bk-monitor-web",
            created_at=timezone.now(),
            last_synced_at=timezone.now(),
        ).save()
        validated_request_data = {
            "bk_biz_id": 2,
            "bcs_cluster_id": "BCS-K8S-00000",
            "resource_type": "container",
            "namespace": "blueking",
            "pod_name": "bk-monitor-web-pod",
            "container_name": "bk-monitor-web-container",
        }

        expected_result = [
            {
                "key": "name",
                "name": "容器名称",
                "type": "string",
                "value": "bk-monitor-web-container",
            },
            {
                "key": "bcs_cluster_id",
                "name": "集群ID",
                "type": "string",
                "value": "BCS-K8S-00000",
            },
            {
                "key": "bk_cluster_name",
                "name": "集群名称",
                "type": "string",
                "value": "",
            },
            {
                "key": "namespace",
                "name": "NameSpace",
                "type": "string",
                "value": "blueking",
            },
            {"key": "status", "name": "运行状态", "type": "string", "value": ""},
            {
                "key": "monitor_status",
                "name": "采集状态",
                "type": "status",
                "value": {"type": "failed", "text": "异常"},
            },
            {
                "key": "pod_name",
                "name": "Pod名称",
                "type": "string",
                "value": "bk-monitor-web-pod",
            },
            {
                "key": "workload",
                "name": "工作负载",
                "type": "string",
                "value": "Deployment:bk-monitor-web",
            },
            {
                "key": "node_name",
                "name": "节点名称",
                "type": "string",
                "value": "",
            },
            {
                "key": "node_ip",
                "name": "节点IP",
                "type": "string",
                "value": None,
            },
            {
                "key": "image",
                "name": "镜像",
                "type": "string",
                "value": "",
            },
            {
                "key": "resource_usage_cpu",
                "name": "CPU使用量",
                "type": "string",
                "value": "",
            },
            {
                "key": "resource_usage_memory",
                "name": "内存使用量",
                "type": "string",
                "value": "",
            },
            {
                "key": "resource_usage_disk",
                "name": "磁盘使用量",
                "type": "string",
                "value": "",
            },
            {"key": "age", "name": "存活时间", "type": "string", "value": "a moment"},
        ]
        resource_detail = GetResourceDetail()(validated_request_data)

        assert resource_detail == expected_result

    @mock.patch("core.drf_resource.api.kubernetes.fetch_usage_ratio")
    def test_with_cluster(self, fetch_usage_ratio):
        # create_cluster
        BCSCluster(
            bk_biz_id=2,
            bcs_cluster_id="BCS-K8S-00000",
            name="蓝鲸7.0",
            created_at=timezone.now(),
            updated_at=timezone.now(),
            last_synced_at=timezone.now(),
            node_count=0,
            cpu_usage_ratio=25.84,
            memory_usage_ratio=50.89,
            disk_usage_ratio=49.2,
        ).save()
        validated_request_data = {
            "bk_biz_id": 2,
            "bcs_cluster_id": "BCS-K8S-00000",
            "resource_type": "cluster",
            "namespace": "blueking",
        }
        expected_result = [
            {
                "key": "bcs_cluster_id",
                "name": "集群ID",
                "type": "string",
                "value": "BCS-K8S-00000",
            },
            {"key": "name", "name": "集群名称", "type": "string", "value": "蓝鲸7.0"},
            {"key": "status", "name": "运行状态", "type": "string", "value": ""},
            {
                "key": "monitor_status",
                "name": "采集状态",
                "type": "status",
                "value": {"type": "failed", "text": "异常"},
            },
            {"key": "environment", "name": "环境", "type": "string", "value": ""},
            {"key": "node_count", "name": "节点数量", "type": "number", "value": 0},
            {
                "key": "cpu_usage_ratio",
                "name": "CPU使用率",
                "type": "progress",
                "value": {"value": 25.84, "label": "25.84%", "status": "SUCCESS"},
            },
            {
                "key": "memory_usage_ratio",
                "name": "内存使用率",
                "type": "progress",
                "value": {"value": 50.89, "label": "50.89%", "status": "SUCCESS"},
            },
            {
                "key": "disk_usage_ratio",
                "name": "磁盘使用率",
                "type": "progress",
                "value": {"value": 49.2, "label": "49.2%", "status": "SUCCESS"},
            },
            {"key": "area_name", "name": "区域", "type": "string", "value": ""},
            {
                "key": "created_at",
                "name": "创建时间",
                "type": "string",
                "value": "a moment",
            },
            {
                "key": "updated_at",
                "name": "更新时间",
                "type": "string",
                "value": "a moment",
            },
            {"key": "project_name", "name": "所属项目", "type": "string", "value": ""},
            {"key": "description", "name": "描述", "type": "string", "value": ""},
        ]
        fetch_usage_ratio.return_value = {}
        resource_detail = GetResourceDetail()(validated_request_data)

        assert resource_detail == expected_result

    def test_with_service(self):
        # create_service
        BCSService(
            bk_biz_id=2,
            bcs_cluster_id="BCS-K8S-00000",
            namespace="blueking",
            name="bk-ingress-nginx",
            created_at=timezone.now(),
            last_synced_at=timezone.now(),
        ).save()
        validated_request_data = {
            "bk_biz_id": 2,
            "bcs_cluster_id": "BCS-K8S-00000",
            "resource_type": "service",
            "namespace": "blueking",
            "service_name": "bk-ingress-nginx",
        }
        expected_result = [
            {
                "key": "name",
                "name": "服务名称",
                "type": "string",
                "value": "bk-ingress-nginx",
            },
            {
                "key": "bcs_cluster_id",
                "name": "集群ID",
                "type": "string",
                "value": "BCS-K8S-00000",
            },
            {
                "key": "bk_cluster_name",
                "name": "集群名称",
                "type": "string",
                "value": "",
            },
            {
                "key": "namespace",
                "name": "NameSpace",
                "type": "string",
                "value": "blueking",
            },
            {
                "key": "monitor_status",
                "name": "采集状态",
                "type": "status",
                "value": {"type": "failed", "text": "异常"},
            },
            {"key": "type", "name": "类型", "type": "string", "value": ""},
            {
                "key": "cluster_ip",
                "name": "Cluster IP",
                "type": "string",
                "value": "",
            },
            {
                "key": "external_ip",
                "name": "External IP",
                "type": "string",
                "value": "",
            },
            {
                "key": "ports",
                "name": "Ports",
                "type": "list",
                "value": [""],
            },
            {
                "key": "endpoint_count",
                "name": "Endpoint数量",
                "type": "number",
                "value": 0,
            },
            {"key": "pod_count", "name": "Pod数量", "type": "string", "value": 0},
            {
                "key": "pod_name_list",
                "name": "Pod名称",
                "type": "list",
                "value": ["not found"],
            },
            {"key": "age", "name": "存活时间", "type": "string", "value": "a moment"},
        ]
        resource_detail = GetResourceDetail()(validated_request_data)

        assert resource_detail == expected_result

    def test_with_ingress(self):
        BCSIngress(
            bk_biz_id=2,
            bcs_cluster_id="BCS-K8S-00000",
            namespace="blueking",
            name="bk-ingress-nginx",
            created_at=timezone.now(),
            last_synced_at=timezone.now(),
        ).save()
        validated_request_data = {
            "bk_biz_id": 2,
            "bcs_cluster_id": "BCS-K8S-00000",
            "resource_type": "ingress",
            "namespace": "blueking",
            "ingress_name": "bk-ingress-nginx",
        }
        expected_result = [
            {
                "key": "name",
                "name": "名称",
                "type": "string",
                "value": "bk-ingress-nginx",
            },
            {
                "key": "bcs_cluster_id",
                "name": "集群ID",
                "type": "string",
                "value": "BCS-K8S-00000",
            },
            {
                "key": "bk_cluster_name",
                "name": "集群名称",
                "type": "string",
                "value": "",
            },
            {
                "key": "namespace",
                "name": "NameSpace",
                "type": "string",
                "value": "blueking",
            },
            {
                "key": "monitor_status",
                "name": "采集状态",
                "type": "status",
                "value": {"type": "failed", "text": "异常"},
            },
            {"key": "class_name", "name": "Class", "type": "string", "value": ""},
            {"key": "age", "name": "存活时间", "type": "string", "value": "a moment"},
        ]
        resource_detail = GetResourceDetail()(validated_request_data)

        assert resource_detail == expected_result

    @mock.patch("core.drf_resource.api.kubernetes.fetch_k8s_node_performance")
    def test_with_node(self, fetch_k8s_node_performance):
        BCSNode(
            bk_biz_id=2,
            bcs_cluster_id="BCS-K8S-00000",
            name="master-127-0-0-1",
            created_at=timezone.now(),
            last_synced_at=timezone.now(),
            endpoint_count=0,
            pod_count=0,
        ).save()
        validated_request_data = {
            "bk_biz_id": 2,
            "bcs_cluster_id": "BCS-K8S-00000",
            "resource_type": "node",
            "namespace": "blueking",
            "node_name": "master-127-0-0-1",
        }

        expected_result = [
            {
                "key": "name",
                "name": "节点名称",
                "type": "string",
                "value": "master-127-0-0-1",
            },
            {"key": "pod_count", "name": "Pod数量", "type": "string", "value": 0},
            {
                "key": "bcs_cluster_id",
                "name": "集群ID",
                "type": "string",
                "value": "BCS-K8S-00000",
            },
            {
                "key": "bk_cluster_name",
                "name": "集群名称",
                "type": "string",
                "value": "",
            },
            {
                "key": "node_ip",
                "name": "节点IP",
                "type": "string",
                "value": "",
            },
            {"key": "cloud_id", "name": "云区域", "type": "string", "value": ""},
            {"key": "status", "name": "运行状态", "type": "string", "value": ""},
            {
                "key": "monitor_status",
                "name": "采集状态",
                "type": "status",
                "value": {"type": "failed", "text": "异常"},
            },
            {
                "key": "system_cpu_summary_usage",
                "name": "CPU使用率",
                "type": "progress",
                "value": {"value": 0, "label": "", "status": "NODATA"},
            },
            {
                "key": "system_mem_pct_used",
                "name": "应用内存使用率",
                "type": "progress",
                "value": {"value": 0, "label": "", "status": "NODATA"},
            },
            {
                "key": "system_io_util",
                "name": "磁盘IO使用率",
                "type": "progress",
                "value": {"value": 0, "label": "", "status": "NODATA"},
            },
            {
                "key": "system_disk_in_use",
                "name": "磁盘空间使用率",
                "type": "progress",
                "value": {"value": 0, "label": "", "status": "NODATA"},
            },
            {
                "key": "system_load_load15",
                "name": "CPU十五分钟负载",
                "type": "str",
                "value": "",
            },
            {
                "key": "taints",
                "name": "污点",
                "type": "list",
                "value": [],
            },
            {
                "key": "node_roles",
                "name": "角色",
                "type": "list",
                "value": [],
            },
            {
                "key": "endpoint_count",
                "name": "Endpoint数量",
                "type": "number",
                "value": 0,
            },
            {"key": "label_list", "name": "标签", "type": "kv", "value": []},
            {"key": "age", "name": "存活时间", "type": "string", "value": "a moment"},
        ]
        fetch_k8s_node_performance.return_value = {}
        resource_detail = GetResourceDetail()(validated_request_data)

        assert resource_detail == expected_result
