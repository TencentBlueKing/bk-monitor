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
import time

from django.test import TestCase

from monitor_web.k8s.core.filters import *
from monitor_web.k8s.core.meta import FilterCollection


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
            ContainerFilter("bk-monitor-web").filter_string(), 'container_name="bk-monitor-web",container_name!="POD"'
        )

    def test_filter_with_resource_ns(self):
        # 基于namespace 过滤
        fc = FilterCollection()
        fc.add(NamespaceFilter("blue", fuzzy=1))
        self.assertEqual(fc.filter_string(), 'namespace=~"(blue)"')

    def test_filter_with_resource_wl(self):
        # 基于 namespace + workload  过滤
        fc = FilterCollection()
        fc.add(WorkloadFilter("monitor-web", fuzzy=1)).add(NamespaceFilter("blueking"))
        self.assertEqual(fc.filter_string(), 'workload_name=~"monitor-web",namespace="blueking"')
        fc.remove(WorkloadFilter("monitor-web", fuzzy=1))
        fc.add(WorkloadFilter("Deployment: bk-monitor-web"))
        self.assertEqual(
            fc.filter_string(), 'namespace="blueking",workload_kind="Deployment",workload_name="bk-monitor-web"'
        )

    def test_filter_with_resource_pod(self):
        # 基于 namespace + pod 过滤
        fc = FilterCollection()
        fc.add(PodFilter("monitor-web", fuzzy=1)).add(NamespaceFilter("blueking"))
        self.assertEqual(fc.filter_string(), 'pod_name=~"(monitor-web)",namespace="blueking"')
        fc.remove(PodFilter("monitor-web")).add(NamespaceFilter("blueking"))
        fc.add(PodFilter(["bk-monitor-web-5dc76bbfd7-8w9c6", "bk-monitor-web-query-api-5c6d68c5dc-jcn74"]))
        self.assertEqual(
            fc.filter_string(),
            'namespace="blueking",pod_name=~"^(bk-monitor-web-5dc76bbfd7-8w9c6|bk-monitor-web-query-api-5c6d68c5dc-jcn74)$"',
        )

    def test_filter_with_resource_container(self):
        # 基于 container 过滤
        fc = FilterCollection()
        fc.add(ContainerFilter("monitor-web", fuzzy=1)).add(NamespaceFilter("blueking")).add(
            PodFilter("bk-monitor-web-5dc76bbfd7-8w9c6")
        )
        self.assertEqual(
            fc.filter_string(),
            'container_name=~"(monitor-web)",container_name!="POD",namespace="blueking",pod_name="bk-monitor-web-5dc76bbfd7-8w9c6"',
        )


class TestK8sListResources(TestCase):
    def test_with_namespace(self):
        """
        测试k8s层级树资源过滤
        """
        query_dict = {
            "bk_biz_id": 2,
            "bcs_cluster_id": "BCS-K8S-00000",
            "resource_type": "namespace",
            # 过滤
            "query_string": "",
            # 近一小时
            "start_time": int(time.time()) - 3600,
            "end_time": int(time.time()),
        }
        pass
