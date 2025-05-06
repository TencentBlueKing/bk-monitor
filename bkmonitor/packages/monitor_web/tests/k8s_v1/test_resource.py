"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from unittest import mock
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
    ListBCSCluster,
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
