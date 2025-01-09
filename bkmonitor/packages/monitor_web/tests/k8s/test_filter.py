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

from datetime import datetime

import mock
from django.test import TestCase
from django.utils import timezone
from humanize import naturaldelta

from bkmonitor.models import BCSCluster
from monitor_web.k8s.core.filters import (
    ContainerFilter,
    NamespaceFilter,
    PodFilter,
    WorkloadFilter,
    load_resource_filter,
)
from monitor_web.k8s.core.meta import (
    BCSContainer,
    BCSPod,
    BCSWorkload,
    FilterCollection,
    K8sContainerMeta,
    K8sNamespaceMeta,
    K8sPodMeta,
    K8sWorkloadMeta,
    NameSpace,
    load_resource_meta,
)
from monitor_web.k8s.resources import (
    GetResourceDetail,
    ListK8SResources,
    WorkloadOverview,
)


class TestFilter(TestCase):
    def test_filter_with_resource(self):
        # 基于资源层级过滤
        self.assertEqual(NamespaceFilter("blueking").filter_string(), 'namespace="blueking"')
        self.assertEqual(
            PodFilter("bkm-kube-state-metrics-7bd44f995d-hjxwc").filter_string(),
            'pod_name="bkm-kube-state-metrics-7bd44f995d-hjxwc"',
        )
        self.assertEqual(
            WorkloadFilter("Deployment: bk-monitor-web").filter_string(),
            'workload_kind="Deployment",workload_name="bk-monitor-web"',
        )
        self.assertEqual(
            ContainerFilter("bk-monitor-web").filter_string(),
            'container_name="bk-monitor-web"',
        )

    def test_filter_with_resource_ns(self):
        # 基于namespace 过滤
        fc = FilterCollection(K8sNamespaceMeta(2, "BCS-K8S-00000"))
        fc.add(NamespaceFilter("blue", fuzzy=1))
        self.assertEqual(fc.filter_string(), 'namespace=~"(blue)"')

    def test_filter_with_resource_wl(self):
        # 基于 namespace + workload  过滤
        fc = FilterCollection(K8sWorkloadMeta(2, "BCS-K8S-00000"))
        fc.add(WorkloadFilter("monitor-web", fuzzy=1)).add(NamespaceFilter("blueking"))
        self.assertEqual(fc.filter_string(), 'workload_name=~"monitor-web",namespace="blueking"')
        fc.remove(WorkloadFilter("monitor-web", fuzzy=1))
        fc.add(WorkloadFilter("Deployment: bk-monitor-web"))
        self.assertEqual(
            fc.filter_string(),
            'namespace="blueking",workload_kind="Deployment",workload_name="bk-monitor-web"',
        )

    def test_filter_with_resource_pod(self):
        # 基于 namespace + pod 过滤
        fc = FilterCollection(K8sPodMeta(2, "BCS-K8S-00000"))
        fc.add(PodFilter("monitor-web", fuzzy=1)).add(NamespaceFilter("blueking"))
        self.assertEqual(fc.filter_string(), 'pod_name=~"(monitor-web)",namespace="blueking"')
        fc.remove(PodFilter("monitor-web")).add(NamespaceFilter("blueking"))
        fc.add(
            PodFilter(
                [
                    "bk-monitor-web-5dc76bbfd7-8w9c6",
                    "bk-monitor-web-query-api-5c6d68c5dc-jcn74",
                ]
            )
        )
        self.assertEqual(
            fc.filter_string(),
            'namespace="blueking",'
            'pod_name=~"^(bk-monitor-web-5dc76bbfd7-8w9c6|bk-monitor-web-query-api-5c6d68c5dc-jcn74)$"',
        )

    def test_filter_with_resource_container(self):
        # 基于 container 过滤
        fc = FilterCollection(K8sContainerMeta(2, "BCS-K8S-00000"))
        fc.add(ContainerFilter("monitor-web", fuzzy=1)).add(NamespaceFilter("blueking")).add(
            PodFilter("bk-monitor-web-5dc76bbfd7-8w9c6")
        ).add(load_resource_filter("container_exclude", ""))

        self.assertEqual(
            fc.filter_string(),
            'container_name=~"(monitor-web)",'
            'namespace="blueking",pod_name="bk-monitor-web-5dc76bbfd7-8w9c6",container_name!="POD"',
        )

    def test_filter_dict_with_workload_filter(self):
        """
        对 WorkloadFilter().filter_dict 的单元测试
        """
        workload_filter = WorkloadFilter("type:name")
        self.assertEqual(
            workload_filter.filter_dict,
            {"workload_kind": "type", "workload_name": "name"},
        )
        workload_filter = WorkloadFilter("type:")
        self.assertEqual(workload_filter.filter_dict, {"workload_kind": "type"})
        workload_filter = WorkloadFilter(":name")
        self.assertEqual(workload_filter.filter_dict, {"workload_name": "name"})
        workload_filter = WorkloadFilter("any")
        self.assertEqual(workload_filter.filter_dict, {"workload_name": "any"})

        workload_filter = WorkloadFilter("type:name", fuzzy=True)
        self.assertEqual(
            workload_filter.filter_dict,
            {"workload_kind": "type", "workload_name": "name"},
        )
        workload_filter = WorkloadFilter("type:", fuzzy=True)
        self.assertEqual(workload_filter.filter_dict, {"workload_kind": "type"})
        workload_filter = WorkloadFilter(":name", fuzzy=True)
        self.assertEqual(workload_filter.filter_dict, {"workload_name": "name"})
        workload_filter = WorkloadFilter("any", fuzzy=True)
        self.assertEqual(workload_filter.filter_dict, {"workload_name__icontains": "any"})


class TestGetResourcesDetail(TestCase):
    databases = {"default", "monitor_api"}

    def setUp(self):
        BCSPod(
            bk_biz_id=2,
            bcs_cluster_id="BCS-K8S-00000",
            name="pf-f991b578413c4ce48d7d92d53f2021f9-6c9757758b-4qmxp",
            namespace="bkmonitor",
            node_name="node-127-0-0-1",
            node_ip="127.0.0.1",
            workload_type="Deployment",
            workload_name="pf-f991b578413c4ce48d7d92d53f2021f9",
            total_container_count=1,
            ready_container_count=0,
            pod_ip="127.0.0.1",
            images="",
            restarts=0,
            monitor_status="success",
            created_at=timezone.now(),
            last_synced_at=timezone.now(),
            request_cpu_usage_ratio=96.5,
            limit_cpu_usage_ratio=96.5,
            request_memory_usage_ratio=54.98,
            limit_memory_usage_ratio=54.98,
            status="Running",
        ).save()
        BCSWorkload(
            bk_biz_id=2,
            bcs_cluster_id="BCS-K8S-00000",
            type="Deployment",
            name="pf-f991b578413c4ce48d7d92d53f2021f9",
            namespace="bkmonitor",
            images="",
            pod_count=1,
            container_count=1,
            created_at=timezone.now(),
            last_synced_at=timezone.now(),
            monitor_status="success",
            status="success",
        ).save()
        BCSContainer(
            bk_biz_id=2,
            bcs_cluster_id="BCS-K8S-00000",
            name="monitor-main-container",
            namespace="bkmonitor",
            pod_name="pf-f991b578413c4ce48d7d92d53f2021f9-6c9757758b-4qmxp",
            workload_name="pf-f991b578413c4ce48d7d92d53f2021f9",
            workload_type="Deployment",
            node_name="node-127-0-0-1",
            node_ip="127.0.0.1",
            image="",
            monitor_status="success",
            status="running",
            created_at=timezone.now(),
            last_synced_at=timezone.now(),
        ).save()
        BCSCluster(
            bk_biz_id=2,
            bcs_cluster_id="BCS-K8S-00000",
            name="",
            area_name="",
            project_name="",
            environment="正式",
            updated_at=timezone.now(),
            node_count=18,
            cpu_usage_ratio=19.22,
            memory_usage_ratio=65.36,
            disk_usage_ratio=51.45,
            created_at=timezone.now(),
            status="RUNNING",
            monitor_status="success",
            last_synced_at=timezone.now(),
        ).save()

    def test_link_to_string(self):
        items = [
            {"type": "link", "value": {"value": "baidu.com", "name": "baidu"}},
            {"type": "string", "value": "qq.com"},
        ]
        for item in items:
            GetResourceDetail.link_to_string(item)

        self.assertEqual(
            items,
            [
                {"type": "string", "value": "baidu.com"},
                {"type": "string", "value": "qq.com"},
            ],
        )

    def test_with_pod(self):
        validated_request_data = {
            "bk_biz_id": 2,
            "bcs_cluster_id": "BCS-K8S-00000",
            "namespace": "bkmonitor",
            "resource_type": "pod",
            "pod_name": "pf-f991b578413c4ce48d7d92d53f2021f9-6c9757758b-4qmxp",
        }
        age = naturaldelta(
            datetime.utcnow().replace(tzinfo=timezone.utc) - datetime.utcnow().replace(tzinfo=timezone.utc)
        )
        result = GetResourceDetail()(validated_request_data)
        expect_data = [
            {
                "key": "name",
                "name": "Pod名称",
                "type": "string",
                "value": "pf-f991b578413c4ce48d7d92d53f2021f9-6c9757758b-4qmxp",
            },
            {"key": "status", "name": "运行状态", "type": "string", "value": "Running"},
            {
                "key": "ready",
                "name": "是否就绪(实例运行数/期望数)",
                "type": "string",
                "value": "0/1",
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
                "value": "bkmonitor",
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
                "value": {"type": "success", "text": "正常"},
            },
            {"key": "age", "name": "存活时间", "type": "string", "value": age},
            {
                "key": "request_cpu_usage_ratio",
                "name": "CPU使用率(request)",
                "type": "progress",
                "value": {"value": 96.5, "label": "96.5%", "status": "SUCCESS"},
            },
            {
                "key": "limit_cpu_usage_ratio",
                "name": "CPU使用率(limit)",
                "type": "progress",
                "value": {"value": 96.5, "label": "96.5%", "status": "SUCCESS"},
            },
            {
                "key": "request_memory_usage_ratio",
                "name": "内存使用率(request)",
                "type": "progress",
                "value": {"value": 54.98, "label": "54.98%", "status": "SUCCESS"},
            },
            {
                "key": "limit_memory_usage_ratio",
                "name": "内存使用率(limit) ",
                "type": "progress",
                "value": {"value": 54.98, "label": "54.98%", "status": "SUCCESS"},
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
                "value": "Deployment:pf-f991b578413c4ce48d7d92d53f2021f9",
            },
            {"key": "label_list", "name": "标签", "type": "kv", "value": []},
            {"key": "images", "name": "镜像", "type": "list", "value": [""]},
        ]

        self.assertEqual(result, expect_data)

    def test_with_workload(self):
        validated_request_data = {
            "bk_biz_id": 2,
            "bcs_cluster_id": "BCS-K8S-00000",
            "namespace": "bkmonitor",
            "resource_type": "workload",
            "workload_name": "pf-f991b578413c4ce48d7d92d53f2021f9",
            "workload_type": "Deployment",
        }
        age = naturaldelta(
            datetime.utcnow().replace(tzinfo=timezone.utc) - datetime.utcnow().replace(tzinfo=timezone.utc)
        )
        result = GetResourceDetail()(validated_request_data)

        expect_data = [
            {
                "key": "name",
                "name": "工作负载名称",
                "type": "string",
                "value": "pf-f991b578413c4ce48d7d92d53f2021f9",
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
                "value": "bkmonitor",
            },
            {"key": "status", "name": "运行状态", "type": "string", "value": "success"},
            {
                "key": "monitor_status",
                "name": "采集状态",
                "type": "status",
                "value": {"type": "success", "text": "正常"},
            },
            {"key": "type", "name": "类型", "type": "string", "value": "Deployment"},
            {"key": "images", "name": "镜像", "type": "string", "value": ""},
            {"key": "label_list", "name": "标签", "type": "kv", "value": []},
            {
                "key": "pod_count",
                "name": "Pod数量",
                "type": "string",
                "value": 1,
            },
            {
                "key": "container_count",
                "name": "容器数量",
                "type": "string",
                "value": 1,
            },
            {"key": "resources", "name": "资源", "type": "kv", "value": []},
            {"key": "age", "name": "存活时间", "type": "string", "value": age},
        ]
        self.assertEqual(result, expect_data)

    def test_with_container(self):
        validated_request_data = {
            "bk_biz_id": 2,
            "bcs_cluster_id": "BCS-K8S-00000",
            "namespace": "bkmonitor",
            "resource_type": "container",
            "pod_name": "pf-f991b578413c4ce48d7d92d53f2021f9-6c9757758b-4qmxp",
            "container_name": "monitor-main-container",
        }
        age = naturaldelta(
            datetime.utcnow().replace(tzinfo=timezone.utc) - datetime.utcnow().replace(tzinfo=timezone.utc)
        )
        result = GetResourceDetail()(validated_request_data)

        expect_data = [
            {
                "key": "name",
                "name": "容器名称",
                "type": "string",
                "value": "monitor-main-container",
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
                "value": "bkmonitor",
            },
            {"key": "status", "name": "运行状态", "type": "string", "value": "running"},
            {
                "key": "monitor_status",
                "name": "采集状态",
                "type": "status",
                "value": {"type": "success", "text": "正常"},
            },
            {
                "key": "pod_name",
                "name": "Pod名称",
                "type": "string",
                "value": "pf-f991b578413c4ce48d7d92d53f2021f9-6c9757758b-4qmxp",
            },
            {
                "key": "workload",
                "name": "工作负载",
                "type": "string",
                "value": "Deployment:pf-f991b578413c4ce48d7d92d53f2021f9",
            },
            {
                "key": "node_name",
                "name": "节点名称",
                "type": "string",
                "value": "node-127-0-0-1",
            },
            {
                "key": "node_ip",
                "name": "节点IP",
                "type": "string",
                "value": "127.0.0.1",
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
            {"key": "age", "name": "存活时间", "type": "string", "value": age},
        ]
        self.assertEqual(result, expect_data)

    def test_with_cluster(self):
        validated_request_data = {
            "bk_biz_id": 2,
            "bcs_cluster_id": "BCS-K8S-00000",
            "namespace": "bkmonitor",
            "resource_type": "cluster",
        }
        age = naturaldelta(
            datetime.utcnow().replace(tzinfo=timezone.utc) - datetime.utcnow().replace(tzinfo=timezone.utc)
        )
        with mock.patch("bkmonitor.models.BCSCluster.update_monitor_status") as mock_update_monitor_status:
            mock_update_monitor_status.return_value = None

            actual_data = GetResourceDetail()(validated_request_data)
            expect_data = [
                {
                    "key": "bcs_cluster_id",
                    "name": "集群ID",
                    "type": "string",
                    "value": "BCS-K8S-00000",
                },
                {"key": "name", "name": "集群名称", "type": "string", "value": ""},
                {"key": "status", "name": "运行状态", "type": "string", "value": "RUNNING"},
                {
                    "key": "monitor_status",
                    "name": "采集状态",
                    "type": "status",
                    "value": {"type": "success", "text": "正常"},
                },
                {"key": "environment", "name": "环境", "type": "string", "value": "正式"},
                {"key": "node_count", "name": "节点数量", "type": "number", "value": 18},
                {
                    "key": "cpu_usage_ratio",
                    "name": "CPU使用率",
                    "type": "progress",
                    "value": {"value": 19.22, "label": "19.22%", "status": "SUCCESS"},
                },
                {
                    "key": "memory_usage_ratio",
                    "name": "内存使用率",
                    "type": "progress",
                    "value": {"value": 65.36, "label": "65.36%", "status": "SUCCESS"},
                },
                {
                    "key": "disk_usage_ratio",
                    "name": "磁盘使用率",
                    "type": "progress",
                    "value": {"value": 51.45, "label": "51.45%", "status": "SUCCESS"},
                },
                {"key": "area_name", "name": "区域", "type": "string", "value": ""},
                {
                    "key": "created_at",
                    "name": "创建时间",
                    "type": "string",
                    "value": age,
                },
                {
                    "key": "updated_at",
                    "name": "更新时间",
                    "type": "string",
                    "value": age,
                },
                {"key": "project_name", "name": "所属项目", "type": "string", "value": ""},
                {"key": "description", "name": "描述", "type": "string", "value": ""},
            ]
            self.assertEqual(expect_data, actual_data)


class TestWorkloadOverview(TestCase):
    databases = {"default", "monitor_api"}

    def setUp(self):
        """设置数据库初始化对象用"""
        self.create_workloads()

    def create_workloads(self):
        workload_info = [
            ["blueking", "Deployment", "bk-gateway-esb"],
            ["bkmonitor", "StatefulSet", "bk-monitor-api-status-1"],
            ["bkmonitor", "StatefulSet", "bk-monitor-api-status-2"],
            ["blueking", "StatefulSet", "bk-monitor-api-runing-1"],
            ["blueking", "StatefulSet", "bk-monitor-api-runing-2"],
            ["bkmonitor", "DaemonSet", "bk-monitor-daemon"],
            ["bkmonitor", "Job", "bk-monitor-jobs-1"],
            ["blueking", "Job", "bk-monitor-jobs-2"],
            ["bkmonitor", "CronJob", "bk-monitor-cron"],
        ]
        for info in workload_info:
            BCSWorkload(
                bk_biz_id=2,
                bcs_cluster_id="BCS-K8S-00000",
                namespace=info[0],
                type=info[1],
                name=info[2],
                created_at=timezone.now(),
                last_synced_at=timezone.now(),
                pod_count=0,
            ).save()

    def test_workload_overview(self):
        """
        测试获取工作负载的类型以及对应的类型
        测试内容：
        1. 没有 namespace, query_string 时，全量的数据
        2. 只有namespace， 时的数据
        3. 只有 query_string 时的数据
        """

        validated_request_data = {"bk_biz_id": 2, "bcs_cluster_id": "BCS-K8S-00000"}
        # 1. 测试 获取全量数据
        actual_result = WorkloadOverview()(validated_request_data)
        expect_result = [
            ["Deployment", 1],
            ["StatefulSet", 4],
            ["DaemonSet", 1],
            ["Job", 2],
            ["CronJob", 1],
        ]
        self.assertEqual(expect_result, actual_result)

        # 2. 测试 指定 namespace 的数据
        request_data = {**validated_request_data, "namespace": "bkmonitor"}
        actual_result = WorkloadOverview()(request_data)
        expect_result = [
            ["Deployment", 0],
            ["StatefulSet", 2],
            ["DaemonSet", 1],
            ["Job", 1],
            ["CronJob", 1],
        ]
        self.assertEqual(expect_result, actual_result)

        # 3. 测试 模糊 query_string 的数据
        request_data = {**validated_request_data, "query_string": "monitor"}
        actual_result = WorkloadOverview()(request_data)
        expect_result = [
            ["Deployment", 0],
            ["StatefulSet", 4],
            ["DaemonSet", 1],
            ["Job", 2],
            ["CronJob", 1],
        ]
        self.assertEqual(expect_result, actual_result)

        # 4. 测试 namespace + query_string
        request_data = {
            **validated_request_data,
            "query_string": "monitor",
            "namespace": "blueking",
        }
        actual_result = WorkloadOverview()(request_data)
        expect_result = [
            ["Deployment", 0],
            ["StatefulSet", 2],
            ["DaemonSet", 0],
            ["Job", 1],
            ["CronJob", 0],
        ]
        self.assertEqual(expect_result, actual_result)

        # 5. 测试 无数据
        request_data = {
            **validated_request_data,
            "query_string": "any",
            "namespace": "any",
        }
        actual_result = WorkloadOverview()(request_data)
        expect_result = [
            ["Deployment", 0],
            ["StatefulSet", 0],
            ["DaemonSet", 0],
            ["Job", 0],
            ["CronJob", 0],
        ]
        self.assertEqual(expect_result, actual_result)


class TestK8sListResources(TestCase):
    databases = {"default", "monitor_api"}

    def setUp(self):
        self.create_workloads()
        self.create_pods()
        self.craete_containers()

    def create_workloads(self):
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
        BCSWorkload(
            bk_biz_id=2,
            bcs_cluster_id="BCS-K8S-00000",
            namespace="default",
            type="Deployment",
            name="demo",
            created_at=timezone.now(),
            last_synced_at=timezone.now(),
            pod_count=0,
        ).save()
        BCSWorkload(
            bk_biz_id=2,
            bcs_cluster_id="BCS-K8S-00000",
            namespace="blueking",
            type="Deployment",
            name="bk-monitor-web-worker",
            created_at=timezone.now(),
            last_synced_at=timezone.now(),
            pod_count=0,
        ).save()

    def create_pods(self):
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
        BCSPod(
            bk_biz_id=2,
            bcs_cluster_id="BCS-K8S-00000",
            namespace="default",
            name="bk-monitor-web-worker-784b79c9f-8lw9j",
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
        BCSPod(
            bk_biz_id=2,
            bcs_cluster_id="BCS-K8S-00000",
            namespace="blueking",
            name="bk-monitor-web-worker-resource-557cd688bd-c2q2c",
            node_name="node-127-0-0-1",
            node_ip="127.0.0.1",
            workload_type="Deployment",
            workload_name="bk-monitor-web-worker-resource",
            total_container_count=1,
            ready_container_count=1,
            pod_ip="127.0.0.1",
            restarts=0,
            created_at=timezone.now(),
            last_synced_at=timezone.now(),
        ).save()

    def craete_containers(self):
        BCSContainer(
            bk_biz_id=2,
            bcs_cluster_id="BCS-K8S-00000",
            name="bk-monitor-web",
            namespace="blueking",
            pod_name="bk-monitor-web-579f6bf4bc-nmld9",
            workload_type="Deployment",
            workload_name="bk-monitor-web",
            node_ip="127.0.0.1",
            node_name="node-127-0-0-1",
            image="mirrors.tencent.com/build/blueking/bk-monitor:3.10.0-alpha.335",
            created_at=timezone.now(),
            last_synced_at=timezone.now(),
        ).save()
        BCSContainer(
            bk_biz_id=2,
            bcs_cluster_id="BCS-K8S-00000",
            name="bk-monitor-web",
            namespace="blueking",
            pod_name="bk-monitor-web-579f6bf4bc-qhmxk",
            workload_type="Deployment",
            workload_name="bk-monitor-web",
            node_ip="127.0.0.1",
            node_name="node-127-0-0-1",
            image="mirrors.tencent.com/build/blueking/bk-monitor:3.10.0-alpha.335",
            created_at=timezone.now(),
            last_synced_at=timezone.now(),
        ).save()
        BCSContainer(
            bk_biz_id=2,
            bcs_cluster_id="BCS-K8S-00000",
            name="bk-monitor-web",
            namespace="blueking",
            pod_name="bk-monitor-web-579f6bf4bc-qrzxv",
            workload_type="Deployment",
            workload_name="bk-monitor-web",
            node_ip="127.0.0.1",
            node_name="node-127-0-0-1",
            image="mirrors.tencent.com/build/blueking/bk-monitor:3.10.0-alpha.335",
            created_at=timezone.now(),
            last_synced_at=timezone.now(),
        ).save()

    def tearDown(self):
        pass

    def test_with_namespace(self):
        """
        测试k8s层级树资源过滤: NameSpace
        """
        validated_request_data = {
            "bk_biz_id": 2,
            "bcs_cluster_id": "BCS-K8S-00000",
            "resource_type": "namespace",
            # 资源名过滤
            "query_string": "",
            # 近一小时
            "start_time": 1732240257,
            "end_time": 1732243857,
            "filter_dict": {},
            "scenario": "performance",
            "with_history": False,
        }

        meta = load_resource_meta(validated_request_data["resource_type"], 2, "BCS-K8S-00000")
        # 验证meta类型
        self.assertIsInstance(meta, K8sNamespaceMeta)
        query_set = meta.filter.filter_queryset
        # 验证orm sql即可。 namespace 未定义ORM，因此直接用workload的表, 获取namespace信息
        self.assertEqual(
            str(query_set.query),
            (
                "SELECT `bkmonitor_bcsworkload`.`bk_biz_id`, "
                "`bkmonitor_bcsworkload`.`bcs_cluster_id`, "
                "`bkmonitor_bcsworkload`.`namespace` FROM `bkmonitor_bcsworkload` WHERE "
                "(`bkmonitor_bcsworkload`.`bcs_cluster_id` = BCS-K8S-00000 AND "
                "`bkmonitor_bcsworkload`.`bk_biz_id` = 2) "
                "ORDER BY `bkmonitor_bcsworkload`.`id` ASC"
            ),
        )
        # 因为用的workload表查询namespace信息， 因此需要验证去重
        orm_resource = [
            NameSpace(
                **{
                    "bk_biz_id": 2,
                    "bcs_cluster_id": "BCS-K8S-00000",
                    "namespace": "blueking",
                }
            ),
            NameSpace(
                **{
                    "bk_biz_id": 2,
                    "bcs_cluster_id": "BCS-K8S-00000",
                    "namespace": "default",
                }
            ),
        ]
        self.assertEqual(meta.get_from_meta(), orm_resource)

        # 验证promql 生成
        self.assertEqual(
            meta.meta_prom,
            "sum by (namespace) "
            '(rate(container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",'
            'bk_biz_id="2",container_name!="POD"}[1m]))',
        )

        # 验证基于promql 获取 namespace对象
        query_result = [
            {
                "dimensions": {
                    "bcs_cluster_id": "BCS-K8S-00000",
                    "bk_biz_id": "2",
                    "namespace": "apm-demo",
                },
                "target": "{bcs_cluster_id=BCS-K8S-00000, bk_biz_id=2, namespace=apm-demo}",
                "metric_field": "_result_",
                "datapoints": [
                    [1, 1732243560000],
                ],
                "alias": "_result_",
                "type": "line",
                "dimensions_translation": {},
                "unit": "",
            },
            {
                "dimensions": {
                    "bcs_cluster_id": "BCS-K8S-00000",
                    "bk_biz_id": "2",
                    "namespace": "default",
                },
                "target": "{bcs_cluster_id=BCS-K8S-00000, bk_biz_id=2, namespace=default}",
                "metric_field": "_result_",
                "datapoints": [
                    [1, 1732243560000],
                ],
                "alias": "_result_",
                "type": "line",
                "dimensions_translation": {},
                "unit": "",
            },
        ]

        # apm-demo 为promql查询结果特有的 namespace
        promql_resource = [
            NameSpace(
                **{
                    "bk_biz_id": 2,
                    "bcs_cluster_id": "BCS-K8S-00000",
                    "namespace": "apm-demo",
                }
            ),
            NameSpace(
                **{
                    "bk_biz_id": 2,
                    "bcs_cluster_id": "BCS-K8S-00000",
                    "namespace": "default",
                }
            ),
        ]
        with mock.patch("core.drf_resource.resource.grafana.graph_unify_query") as mock_graph_unify_query:
            mock_graph_unify_query.return_value = {"series": query_result}
            self.assertEqual(
                meta.get_from_promql(
                    validated_request_data["start_time"],
                    validated_request_data["end_time"],
                    order_by="-container_cpu_usage_seconds_total",
                ),
                promql_resource,
            )

            # 验证整体接口(不带历史数据)
            self.assertEqual(
                ListK8SResources()(validated_request_data),
                {
                    "count": len(orm_resource),
                    "items": orm_resource,
                },
            )

            # 带上历史数据, 去重 default
            validated_request_data["with_history"] = True
            self.assertEqual(
                ListK8SResources()(validated_request_data),
                {
                    "count": len(orm_resource + promql_resource[:1]),
                    "items": [
                        {'bcs_cluster_id': 'BCS-K8S-00000', 'bk_biz_id': 2, 'namespace': 'apm-demo'},
                        {'bcs_cluster_id': 'BCS-K8S-00000', 'bk_biz_id': 2, 'namespace': 'default'},
                        {'bcs_cluster_id': 'BCS-K8S-00000', 'bk_biz_id': 2, 'namespace': 'blueking'},
                    ],
                },
            )

            # 资源名过滤
            validated_request_data["with_history"] = False
            validated_request_data["query_string"] = "blue"

            # 验证 带 query_string 条件的sql生成
            meta = load_resource_meta(validated_request_data["resource_type"], 2, "BCS-K8S-00000")
            meta.filter.add(
                load_resource_filter(
                    validated_request_data["resource_type"],
                    validated_request_data["query_string"],
                    fuzzy=True,
                )
            )
            self.assertEqual(
                str(meta.filter.filter_queryset.query),
                (
                    "SELECT `bkmonitor_bcsworkload`.`bk_biz_id`, "
                    "`bkmonitor_bcsworkload`.`bcs_cluster_id`, "
                    "`bkmonitor_bcsworkload`.`namespace` FROM `bkmonitor_bcsworkload` WHERE "
                    "(`bkmonitor_bcsworkload`.`bcs_cluster_id` = BCS-K8S-00000 AND "
                    "`bkmonitor_bcsworkload`.`bk_biz_id` = 2 AND "
                    "`bkmonitor_bcsworkload`.`namespace` LIKE %blue%) "
                    "ORDER BY `bkmonitor_bcsworkload`.`id` ASC"
                ),
            )
            # 验证 带 query_string 条件的 promql
            self.assertEqual(
                meta.meta_prom,
                (
                    "sum by (namespace) "
                    '(rate(container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",'
                    'bk_biz_id="2",container_name!="POD",namespace=~"(blue)"}[1m]))'
                ),
            )
            # 第一个namespace: blueking 命中 检索
            self.assertEqual(
                ListK8SResources()(validated_request_data),
                {"count": len(orm_resource[:1]), "items": orm_resource[:1]},
            )

    def test_with_namespace_2(self):
        validated_request_data = {
            "bcs_cluster_id": "BCS-K8S-00000",
            "resource_type": "namespace",
            "filter_dict": {
                "container": [
                    "bk-monitor-web",
                    "bkmonitor-operator",
                ]
            },
            "start_time": 1734397230,
            "end_time": 1734400830,
            "scenario": "performance",
            "with_history": True,
            "page_size": 20,
            "page": 1,
            "page_type": "scrolling",
            "bk_biz_id": 2,
        }
        query_result = [
            {
                "dimensions": {"namespace": "bkmonitor-operator"},
                "target": "{namespace=bkmonitor-operator}",
                "metric_field": "_result_",
                "datapoints": [
                    [2812.33, 1734425040000],
                ],
                "alias": "_result_",
                "type": "line",
                "dimensions_translation": {},
                "unit": "",
            },
            {
                "dimensions": {"namespace": "blueking"},
                "target": "{namespace=blueking}",
                "metric_field": "_result_",
                "datapoints": [
                    [40.77, 1734425040000],
                ],
                "alias": "_result_",
                "type": "line",
                "dimensions_translation": {},
                "unit": "",
            },
        ]
        with mock.patch("core.drf_resource.resource.grafana.graph_unify_query") as mock_graph_unify_query:
            mock_graph_unify_query.return_value = {"series": query_result}
            ns_list = ListK8SResources()(validated_request_data)["items"]
            self.assertEqual(
                [
                    {'bk_biz_id': 2, 'bcs_cluster_id': 'BCS-K8S-00000', 'namespace': 'bkmonitor-operator'},
                    {'bk_biz_id': 2, 'bcs_cluster_id': 'BCS-K8S-00000', 'namespace': 'blueking'},
                ],
                ns_list,
            )

    def test_with_workload(self):
        validated_request_data = {
            "bk_biz_id": 2,
            "bcs_cluster_id": "BCS-K8S-00000",
            "resource_type": "workload",
            # 资源名过滤
            "query_string": "monitor",
            # 近一小时
            "start_time": 1732240257,
            "end_time": 1732243857,
            "filter_dict": {"namespace": "blueking"},
            "scenario": "performance",
            "with_history": False,
        }
        # 验证workload meta
        meta = load_resource_meta(validated_request_data["resource_type"], 2, "BCS-K8S-00000")
        # 验证meta类型
        self.assertIsInstance(meta, K8sWorkloadMeta)
        query_set = meta.filter.filter_queryset
        # 验证orm sql
        self.assertEqual(
            str(query_set.query),
            (
                "SELECT `bkmonitor_bcsworkload`.`id`, `bkmonitor_bcsworkload`.`bk_biz_id`, "
                "`bkmonitor_bcsworkload`.`bcs_cluster_id`, `bkmonitor_bcsworkload`.`type`, "
                "`bkmonitor_bcsworkload`.`name`, `bkmonitor_bcsworkload`.`namespace` FROM "
                "`bkmonitor_bcsworkload` WHERE (`bkmonitor_bcsworkload`.`bcs_cluster_id` = "
                "BCS-K8S-00000 AND `bkmonitor_bcsworkload`.`bk_biz_id` = 2) "
                "ORDER BY `bkmonitor_bcsworkload`.`id` ASC"
            ),
        )
        # 验证promql
        self.assertEqual(
            meta.meta_prom,
            "sum by (workload_kind, workload_name, namespace) "
            '(rate(container_cpu_usage_seconds_total{'
            'bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m]))',
        )
        # orm_resource = (
        #     BCSWorkload.objects.filter(**validated_request_data["filter_dict"])
        #     .filter(name__icontains=validated_request_data["query_string"])
        #     .only(*K8sWorkloadMeta.only_fields)
        # )
        # 验证get_from_meta
        workload_list = ListK8SResources()(validated_request_data)
        expect_workload_list = [
            {'workload': 'Deployment:bk-monitor-web'},
            {'workload': 'Deployment:bk-monitor-web-worker'},
        ]
        self.assertEqual(
            workload_list,
            {"items": expect_workload_list, "count": len(expect_workload_list)},
        )

        # 验证promql with  filter_dict AND query_string
        ListK8SResources().add_filter(meta, validated_request_data["filter_dict"])
        meta.filter.add(
            load_resource_filter(
                validated_request_data["resource_type"],
                validated_request_data["query_string"],
                fuzzy=True,
            )
        )
        self.assertEqual(
            meta.meta_prom,
            "sum by (workload_kind, workload_name, namespace) "
            '(rate(container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",'
            'bk_biz_id="2",container_name!="POD",namespace="blueking",workload_name=~"monitor"}[1m]))',
        )
        query_result = [
            {
                "dimensions": {
                    "namespace": "blueking",
                    "workload_kind": "Deployment",
                    "workload_name": "bk-monitor-web",
                },
                "target": "{namespace=blueking, workload_kind=Deployment, workload_name=bk-monitor-web}",
                "metric_field": "_result_",
                "datapoints": [
                    [587.75, 1732602420000],
                ],
                "alias": "_result_",
                "type": "line",
                "dimensions_translation": {},
                "unit": "",
            },
            {
                "dimensions": {
                    "namespace": "blueking",
                    "workload_kind": "Deployment",
                    "workload_name": "bk-monitor-web-beat",
                },
                # 历史出现的数据
                "target": "{namespace=blueking, workload_kind=Deployment, workload_name=bk-monitor-web-beat}",
                "metric_field": "_result_",
                "datapoints": [
                    [1.68, 1732602420000],
                ],
                "alias": "_result_",
                "type": "line",
                "dimensions_translation": {},
                "unit": "",
            },
        ]
        # 附带历史数据
        with mock.patch("core.drf_resource.resource.grafana.graph_unify_query") as mock_graph_unify_query:
            mock_graph_unify_query.return_value = {"series": query_result}
            validated_request_data["with_history"] = True
            workload_list = ListK8SResources()(validated_request_data)
            expect_workload_list = [
                {'namespace': 'blueking', 'workload': 'Deployment:bk-monitor-web'},
                {'namespace': 'blueking', 'workload': 'Deployment:bk-monitor-web-beat'},
                {'namespace': 'blueking', 'workload': 'Deployment:bk-monitor-web-worker'},
            ]
            self.assertEqual(
                workload_list,
                {"items": expect_workload_list, "count": len(expect_workload_list)},
            )

    def test_with_pod(self):
        validated_request_data = {
            "bk_biz_id": 2,
            "bcs_cluster_id": "BCS-K8S-00000",
            "resource_type": "pod",
            # 资源名过滤
            "query_string": "monitor",
            # 近一小时
            "start_time": 1732240257,
            "end_time": 1732243857,
            "filter_dict": {"namespace": "blueking"},
            "scenario": "performance",
            "with_history": False,
        }

        meta = load_resource_meta(validated_request_data["resource_type"], 2, "BCS-K8S-00000")
        # 验证 meta 类型
        self.assertIsInstance(meta, K8sPodMeta)
        query_set = meta.filter.filter_queryset
        # 验证 orm sql
        self.assertEqual(
            str(query_set.query),
            (
                "SELECT `bkmonitor_bcspod`.`id`, "
                "`bkmonitor_bcspod`.`bk_biz_id`, "
                "`bkmonitor_bcspod`.`bcs_cluster_id`, "
                "`bkmonitor_bcspod`.`name`, "
                "`bkmonitor_bcspod`.`namespace`, "
                "`bkmonitor_bcspod`.`workload_type`, "
                "`bkmonitor_bcspod`.`workload_name` "
                "FROM `bkmonitor_bcspod` WHERE "
                "(`bkmonitor_bcspod`.`bcs_cluster_id` = BCS-K8S-00000 AND "
                "`bkmonitor_bcspod`.`bk_biz_id` = 2) "
                "ORDER BY `bkmonitor_bcspod`.`id` ASC"
            ),
        )
        # 验证 promql
        self.assertEqual(
            meta.meta_prom,
            "sum by (workload_kind, workload_name, namespace, pod_name) "
            '(rate(container_cpu_usage_seconds_total{'
            'bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m]))',
        )

        # 校验包含更多查询的内容
        orm_resource = (
            BCSPod.objects.filter(**validated_request_data["filter_dict"])
            .filter(name__icontains=validated_request_data["query_string"])
            .only(*K8sPodMeta.only_fields)
        )
        # 验证 get_from_meta
        pod_list = ListK8SResources()(validated_request_data)
        expect_pod_list = [obj.to_meta_dict() for obj in orm_resource]
        self.assertEqual(pod_list, {"count": len(expect_pod_list), "items": expect_pod_list})
        # 验证 promql with  filter_dict AND query_string
        ListK8SResources().add_filter(meta, validated_request_data["filter_dict"])
        meta.filter.add(
            load_resource_filter(
                validated_request_data["resource_type"],
                validated_request_data["query_string"],
                fuzzy=True,
            )
        )
        self.assertEqual(
            meta.meta_prom,
            "sum by (workload_kind, workload_name, namespace, pod_name) "
            '(rate(container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",'
            'bk_biz_id="2",container_name!="POD",namespace="blueking",pod_name=~"(monitor)"}[1m]))',
        )
        query_result = [
            # mock 历史数据
            {
                "dimensions": {
                    "namespace": "blueking",
                    "pod_name": "bk-monitor-web-worker-scheduler-7b666c7788-2abcd",
                    "workload_kind": "Deployment",
                    "workload_name": "bk-monitor-web-worker-scheduler",
                },
                "target": """{
                    namespace=blueking,
                    pod_name=bk-monitor-web-worker-scheduler-7b666c7788-2abcd,
                    workload_kind=Deployment,
                    workload_name=bk-monitor-web-worker-scheduler
                }""",
                "metric_field": "_result_",
                "datapoints": [
                    [644.77, 1732794960000],
                ],
                "alias": "_result_",
                "type": "line",
                "dimensions_translation": {},
                "unit": "",
            },
        ]
        # 附带历史数据
        with mock.patch("core.drf_resource.resource.grafana.graph_unify_query") as mock_graph_unify_query:
            mock_graph_unify_query.return_value = {"series": query_result}
            validated_request_data["with_history"] = True
            pod_list = ListK8SResources()(validated_request_data)
            expect_pod_list = [
                BCSPod(
                    workload_type="Deployment",
                    workload_name="bk-monitor-web-worker-scheduler",
                    namespace="blueking",
                    name="bk-monitor-web-worker-scheduler-7b666c7788-2abcd",
                ).to_meta_dict()
            ] + [obj.to_meta_dict() for obj in orm_resource]
            self.assertEqual(pod_list, {"count": len(expect_pod_list), "items": expect_pod_list})

    def test_with_container(self):
        validated_request_data = {
            "bk_biz_id": 2,
            "bcs_cluster_id": "BCS-K8S-00000",
            "resource_type": "container",
            # 资源名过滤
            "query_string": "monitor",
            # 近一小时
            "start_time": 1732240257,
            "end_time": 1732243857,
            "filter_dict": {
                "namespace": "blueking",
                "workload": "bk-monitor-web",
            },  # 查询是否有相同命名空间的数据
            "scenario": "performance",
            "with_history": False,
        }

        meta = load_resource_meta(validated_request_data["resource_type"], 2, "BCS-K8S-00000")
        # 验证 meta 类型
        self.assertIsInstance(meta, K8sContainerMeta)
        query_set = meta.filter.filter_queryset
        # 验证 orm sql
        self.assertEqual(
            str(query_set.query),
            (
                "SELECT `bkmonitor_bcscontainer`.`id`, "
                "`bkmonitor_bcscontainer`.`bk_biz_id`, "
                "`bkmonitor_bcscontainer`.`bcs_cluster_id`, "
                "`bkmonitor_bcscontainer`.`name`, "
                "`bkmonitor_bcscontainer`.`namespace`, "
                "`bkmonitor_bcscontainer`.`pod_name`, "
                "`bkmonitor_bcscontainer`.`workload_type`, "
                "`bkmonitor_bcscontainer`.`workload_name` FROM `bkmonitor_bcscontainer` WHERE "
                "(`bkmonitor_bcscontainer`.`bcs_cluster_id` = BCS-K8S-00000 AND "
                "`bkmonitor_bcscontainer`.`bk_biz_id` = 2) "
                "ORDER BY `bkmonitor_bcscontainer`.`id` ASC"
            ),
        )
        # 验证 promql
        self.assertEqual(
            meta.meta_prom,
            (
                'sum by (workload_kind, workload_name, namespace, container_name, pod_name) '
                '(rate(container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",'
                'container_name!="POD"}[1m]))'
            ),
        )

        # 校验包含更多查询的内容
        orm_resource = (
            BCSContainer.objects.filter(namespace="blueking", workload_name="bk-monitor-web")
            # BCSContainer.objects.filter(**validated_request_data["filter_dict"])
            .filter(name__icontains=validated_request_data["query_string"]).only(*K8sContainerMeta.only_fields)
        )
        # 验证 get_from_meta
        contianer_list = ListK8SResources()(validated_request_data)
        expect_container_list = [{'container': 'bk-monitor-web'}]
        self.assertEqual(
            contianer_list,
            {"count": len(expect_container_list), "items": expect_container_list},
        )
        # 验证 promql with  filter_dict AND query_string
        ListK8SResources().add_filter(meta, validated_request_data["filter_dict"])
        meta.filter.add(
            load_resource_filter(
                validated_request_data["resource_type"],
                validated_request_data["query_string"],
                fuzzy=True,
            )
        )
        self.assertEqual(
            meta.meta_prom,
            "sum by (workload_kind, workload_name, namespace, container_name, pod_name) "
            '(rate(container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",'
            'bk_biz_id="2",container_name!="POD",namespace="blueking",workload_name="bk-monitor-web",'
            'container_name=~"(monitor)"}[1m]))',
        )
        meta.set_agg_interval(1732240257, 1732240257 + 1800)
        self.assertEqual(
            meta.meta_prom,
            (
                'sum by (workload_kind, workload_name, namespace, container_name, pod_name) '
                '(last_over_time(rate(container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",'
                'container_name!="POD",namespace="blueking",workload_name="bk-monitor-web",'
                'container_name=~"(monitor)"}[1m])[1m:]))'
            ),
        )
        query_result = [
            {
                "dimensions": {
                    "container_name": "bk-monitor-web",
                    "namespace": "blueking",
                    "pod_name": "bk-monitor-web-544d4dc768-4564s",
                    "workload_kind": "Deployment",
                    "workload_name": "bk-monitor-web",
                },
                "target": """{
                    container_name=bk-monitor-web,
                    namespace=blueking,
                    pod_name=bk-monitor-web-544d4dc768-4564s,
                    workload_kind=Deployment,
                    workload_name=bk-monitor-web
                }""",
                "metric_field": "_result_",
                "datapoints": [[661.64, 1733104260000]],
                "alias": "_result_",
                "type": "line",
                "dimensions_translation": {},
                "unit": "",
            }
        ]

        # 附带历史数据
        with mock.patch("core.drf_resource.resource.grafana.graph_unify_query") as mock_graph_unify_query:
            mock_graph_unify_query.return_value = {"series": query_result}
            validated_request_data["with_history"] = True
            container_list = ListK8SResources()(validated_request_data)
            expect_container_list = [
                BCSContainer(
                    pod_name="bk-monitor-web-544d4dc768-4564s",
                    name="bk-monitor-web",
                    namespace="blueking",
                    workload_type="Deployment",
                    workload_name="bk-monitor-web",
                ).to_meta_dict()
            ] + [obj.to_meta_dict() for obj in orm_resource]
            self.assertEqual(
                container_list["items"],
                expect_container_list,
            )
            self.assertEqual(container_list["count"], len(expect_container_list))

    def test_with_page(self):
        validated_request_data = {
            "scenario": "performance",
            "bcs_cluster_id": "BCS-K8S-00000",
            "start_time": 1735801850,
            "end_time": 1735805450,
            "filter_dict": {"workload": ["Deployment:bk-monitor-web"]},
            "page_size": 20,
            "page": 1,
            "resource_type": "pod",
            "with_history": True,
            "page_type": "scrolling",
            "bk_biz_id": 2,
            "order_by": "desc",
            "method": "max",
            "column": "container_cpu_usage_seconds_total",
        }
        query_result = [
            {
                "dimensions": {
                    "container_name": "bk-monitor-web",
                    "namespace": "blueking",
                    "pod_name": "bk-monitor-web-544d4dc768-4564s",
                    "workload_kind": "Deployment",
                    "workload_name": "bk-monitor-web",
                },
                "target": """{
                    container_name=bk-monitor-web,
                    namespace=blueking,
                    pod_name=bk-monitor-web-544d4dc768-4564s,
                    workload_kind=Deployment,
                    workload_name=bk-monitor-web
                }""",
                "metric_field": "_result_",
                "datapoints": [[661.64, 1733104260000]],
                "alias": "_result_",
                "type": "line",
                "dimensions_translation": {},
                "unit": "",
            }
        ]
        with mock.patch("core.drf_resource.resource.grafana.graph_unify_query") as mock_graph_unify_query:
            mock_graph_unify_query.return_value = {"series": query_result}
            container_list = ListK8SResources()(validated_request_data)
            print(container_list)

        meta = load_resource_meta(validated_request_data["resource_type"], 2, "BCS-K8S-00000")
        meta.set_agg_interval(validated_request_data["start_time"], validated_request_data["end_time"])
        meta.set_agg_method(validated_request_data["method"])
        print(meta.meta_prom_with_container_cpu_usage_seconds_total)
        print(meta.meta_prom_by_sort("container_cpu_usage_seconds_total"))
