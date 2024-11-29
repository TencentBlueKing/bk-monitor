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


import mock
from django.test import TestCase
from django.utils import timezone

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
from monitor_web.k8s.resources import ListK8SResources


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
            fc.filter_string(), 'namespace="blueking",workload_kind="Deployment",workload_name="bk-monitor-web"'
        )

    def test_filter_with_resource_pod(self):
        # 基于 namespace + pod 过滤
        fc = FilterCollection(K8sPodMeta(2, "BCS-K8S-00000"))
        fc.add(PodFilter("monitor-web", fuzzy=1)).add(NamespaceFilter("blueking"))
        self.assertEqual(fc.filter_string(), 'pod_name=~"(monitor-web)",namespace="blueking"')
        fc.remove(PodFilter("monitor-web")).add(NamespaceFilter("blueking"))
        fc.add(PodFilter(["bk-monitor-web-5dc76bbfd7-8w9c6", "bk-monitor-web-query-api-5c6d68c5dc-jcn74"]))
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
        )
        self.assertEqual(
            fc.filter_string(),
            'container_name=~"(monitor-web)",container_name!="POD",'
            'namespace="blueking",pod_name="bk-monitor-web-5dc76bbfd7-8w9c6"',
        )


class TestK8sListResources(TestCase):
    databases = {'default', 'monitor_api'}

    def setUp(self):
        self.create_workloads()
        self.create_pods()

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
            node_name="node-9-136-175-75",
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
            node_name="node-30-167-61-89",
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
            node_name="node-30-167-61-61",
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
            name="bk-monitor-web",  # <- meta_data
            namespace="blueking",  # <- meta_data
            pod_name="bk-monitor-web-579f6bf4bc-nmld9",  # <- meta_data
            workload_type="Deployment",  # <- meta_data
            workload_name="bk-monitor-web",  # <- meta_data
            node_ip="127.0.0.1",
            node_name="node-30-186-110-66",
            image="mirrors.tencent.com/build/blueking/bk-monitor:3.10.0-alpha.335",
        ).save()
        BCSContainer(
            bk_biz_id=2,
            bcs_cluster_id="BCS-K8S-00000",
            name="bk-monitor-web",  # <- meta_data
            namespace="blueking",  # <- meta_data
            pod_name="bk-monitor-web-579f6bf4bc-qhmxk",  # <- meta_data
            workload_type="Deployment",  # <- meta_data
            workload_name="bk-monitor-web",  # <- meta_data
            node_ip="127.0.0.1",
            node_name="node-9-136-133-78",
            image="mirrors.tencent.com/build/blueking/bk-monitor:3.10.0-alpha.335",
        ).save()
        BCSContainer(
            bk_biz_id=2,
            bcs_cluster_id="BCS-K8S-00000",
            name="bk-monitor-web",  # <- meta_data
            namespace="blueking",  # <- meta_data
            pod_name="bk-monitor-web-579f6bf4bc-qrzxv",  # <- meta_data
            workload_type="Deployment",  # <- meta_data
            workload_name="bk-monitor-web",  # <- meta_data
            node_ip="127.0.0.1",
            node_name="node-30-186-151-225",
            image="mirrors.tencent.com/build/blueking/bk-monitor:3.10.0-alpha.335",
        ).save()
        # 充当历史数据
        # BCSContainer(
        #     bk_biz_id=2,
        #     bcs_cluster_id="BCS-K8S-00000",
        #     name="bk-monitor-web",  # <- meta_data
        #     namespace="blueking",  # <- meta_data
        #     pod_name="bk-monitor-web-579f6bf4bc-nmld9",  # <- meta_data
        #     workload_type="Deployment",  # <- meta_data
        #     workload_name="bk-monitor-web",  # <- meta_data
        #     node_ip="",
        #     node_name="node-30-186-110-66",
        #     image="mirrors.tencent.com/build/blueking/bk-monitor:3.10.0-alpha.335"
        # ).save()
        pass

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
                'SELECT `bkmonitor_bcsworkload`.`bk_biz_id`, '
                '`bkmonitor_bcsworkload`.`bcs_cluster_id`, '
                '`bkmonitor_bcsworkload`.`namespace` FROM `bkmonitor_bcsworkload` WHERE '
                '(`bkmonitor_bcsworkload`.`bcs_cluster_id` = BCS-K8S-00000 AND '
                '`bkmonitor_bcsworkload`.`bk_biz_id` = 2)'
            ),
        )
        # 因为用的workload表查询namespace信息， 因此需要验证去重
        orm_resource = [
            NameSpace(**{"bk_biz_id": 2, "bcs_cluster_id": "BCS-K8S-00000", "namespace": "blueking"}),
            NameSpace(**{"bk_biz_id": 2, "bcs_cluster_id": "BCS-K8S-00000", "namespace": "default"}),
        ]
        self.assertEqual(meta.get_from_meta(), orm_resource)

        # 验证promql 生成
        self.assertEqual(
            meta.meta_prom,
            'sum by (bk_biz_id,bcs_cluster_id,namespace) '
            '(kube_namespace_labels{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"})',
        )

        # 验证基于promql 获取 namespace对象
        query_result = [
            {
                'dimensions': {'bcs_cluster_id': 'BCS-K8S-00000', 'bk_biz_id': '2', 'namespace': 'apm-demo'},
                'target': '{bcs_cluster_id=BCS-K8S-00000, bk_biz_id=2, namespace=apm-demo}',
                'metric_field': '_result_',
                'datapoints': [
                    [1, 1732243560000],
                ],
                'alias': '_result_',
                'type': 'line',
                'dimensions_translation': {},
                'unit': '',
            },
            {
                'dimensions': {'bcs_cluster_id': 'BCS-K8S-00000', 'bk_biz_id': '2', 'namespace': 'default'},
                'target': '{bcs_cluster_id=BCS-K8S-00000, bk_biz_id=2, namespace=default}',
                'metric_field': '_result_',
                'datapoints': [
                    [1, 1732243560000],
                ],
                'alias': '_result_',
                'type': 'line',
                'dimensions_translation': {},
                'unit': '',
            },
        ]

        # apm-demo 为promql查询结果特有的 namespace
        promql_resource = [
            NameSpace(**{"bk_biz_id": 2, "bcs_cluster_id": "BCS-K8S-00000", "namespace": "apm-demo"}),
            NameSpace(**{"bk_biz_id": 2, "bcs_cluster_id": "BCS-K8S-00000", "namespace": "default"}),
        ]
        with mock.patch("core.drf_resource.resource.grafana.graph_unify_query") as mock_graph_unify_query:
            mock_graph_unify_query.return_value = {"series": query_result}
            self.assertEqual(
                meta.get_from_promql(validated_request_data["start_time"], validated_request_data["end_time"]),
                promql_resource,
            )

            # 验证整体接口(不带历史数据)
            self.assertEqual(ListK8SResources()(validated_request_data), orm_resource)

            # 带上历史数据, 去重 default
            validated_request_data["with_history"] = True
            self.assertEqual(ListK8SResources()(validated_request_data), orm_resource + promql_resource[:1])

            # 资源名过滤
            validated_request_data["with_history"] = False
            validated_request_data["query_string"] = "blue"

            # 验证 带 query_string 条件的sql生成
            meta = load_resource_meta(validated_request_data["resource_type"], 2, "BCS-K8S-00000")
            meta.filter.add(
                load_resource_filter(
                    validated_request_data["resource_type"], validated_request_data["query_string"], fuzzy=True
                )
            )
            self.assertEqual(
                str(meta.filter.filter_queryset.query),
                (
                    'SELECT `bkmonitor_bcsworkload`.`bk_biz_id`, '
                    '`bkmonitor_bcsworkload`.`bcs_cluster_id`, '
                    '`bkmonitor_bcsworkload`.`namespace` FROM `bkmonitor_bcsworkload` WHERE '
                    '(`bkmonitor_bcsworkload`.`bcs_cluster_id` = BCS-K8S-00000 AND '
                    '`bkmonitor_bcsworkload`.`bk_biz_id` = 2 AND '
                    '`bkmonitor_bcsworkload`.`namespace` LIKE %blue%)'
                ),
            )
            # 验证 带 query_string 条件的 promql
            self.assertEqual(
                meta.meta_prom,
                (
                    'sum by (bk_biz_id,bcs_cluster_id,namespace) '
                    '(kube_namespace_labels{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",namespace=~"(blue)"})'
                ),
            )
            # 第一个namespace: blueking 命中 检索
            self.assertEqual(ListK8SResources()(validated_request_data), orm_resource[:1])

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
                'SELECT `bkmonitor_bcsworkload`.`id`, `bkmonitor_bcsworkload`.`bk_biz_id`, '
                '`bkmonitor_bcsworkload`.`bcs_cluster_id`, `bkmonitor_bcsworkload`.`type`, '
                '`bkmonitor_bcsworkload`.`name`, `bkmonitor_bcsworkload`.`namespace` FROM '
                '`bkmonitor_bcsworkload` WHERE (`bkmonitor_bcsworkload`.`bcs_cluster_id` = '
                'BCS-K8S-00000 AND `bkmonitor_bcsworkload`.`bk_biz_id` = 2)'
            ),
        )
        # 验证promql
        self.assertEqual(
            meta.meta_prom,
            'sum by (workload_kind, workload_name, namespace) '
            '(container_cpu_system_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"})',
        )
        orm_resource = (
            BCSWorkload.objects.filter(**validated_request_data["filter_dict"])
            .filter(name__icontains=validated_request_data["query_string"])
            .only(*K8sWorkloadMeta.only_fields)
        )
        # 验证get_from_meta
        workload_list = ListK8SResources()(validated_request_data)
        self.assertEqual(workload_list, [obj.to_meta_dict() for obj in orm_resource])

        # 验证promql with  filter_dict AND query_string
        ListK8SResources().add_filter(meta, validated_request_data["filter_dict"])
        meta.filter.add(
            load_resource_filter(
                validated_request_data["resource_type"], validated_request_data["query_string"], fuzzy=True
            )
        )
        self.assertEqual(
            meta.meta_prom,
            'sum by (workload_kind, workload_name, namespace) '
            '(container_cpu_system_seconds_total{bcs_cluster_id="BCS-K8S-00000",'
            'bk_biz_id="2",namespace="blueking",workload_name=~"monitor"})',
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
            self.assertEqual(
                workload_list,
                (
                    [obj.to_meta_dict() for obj in orm_resource]
                    # + ...  # TODO: 这里需要通过打断点搞明白 为什么要加点东西, workload_list 里面有啥， orm_resource 有啥
                    + [BCSWorkload(namespace="blueking", type="Deployment", name="bk-monitor-web-beat").to_meta_dict()]
                ),
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
                'SELECT `bkmonitor_bcspod`.`id`, '
                '`bkmonitor_bcspod`.`bk_biz_id`, '
                '`bkmonitor_bcspod`.`bcs_cluster_id`, '
                '`bkmonitor_bcspod`.`name`, '
                '`bkmonitor_bcspod`.`namespace`, '
                '`bkmonitor_bcspod`.`workload_type`, '
                '`bkmonitor_bcspod`.`workload_name` '
                'FROM `bkmonitor_bcspod` WHERE '
                '(`bkmonitor_bcspod`.`bcs_cluster_id` = BCS-K8S-00000 AND '
                '`bkmonitor_bcspod`.`bk_biz_id` = 2)'
            ),
        )
        # 验证 promql
        self.assertEqual(
            meta.meta_prom,
            'sum by (workload_kind, workload_name, namespace, pod_name) '
            '(container_cpu_system_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"})',
        )

        # 校验包含更多查询的内容
        orm_resource = (
            BCSPod.objects.filter(**validated_request_data["filter_dict"])
            .filter(name__icontains=validated_request_data["query_string"])
            .only(*K8sPodMeta.only_fields)
        )
        # 验证 get_from_meta
        pod_list = ListK8SResources()(validated_request_data)
        self.assertEqual(pod_list, [obj.to_meta_dict() for obj in orm_resource])
        # 验证 promql with  filter_dict AND query_string
        ListK8SResources().add_filter(meta, validated_request_data["filter_dict"])
        meta.filter.add(
            load_resource_filter(
                validated_request_data["resource_type"], validated_request_data["query_string"], fuzzy=True
            )
        )
        self.assertEqual(
            meta.meta_prom,
            'sum by (workload_kind, workload_name, namespace, pod_name) '
            '(container_cpu_system_seconds_total{bcs_cluster_id="BCS-K8S-00000",'
            'bk_biz_id="2",namespace="blueking",pod_name=~"(monitor)"})',
        )
        query_result = [
            # {
            #     "dimensions": {
            #         "namespace": "blueking",
            #         "pod_name": "bk-datalink-bk-worker-scheduler-695856bb4f-fh6dn",
            #         "workload_kind": "Deployment",
            #         "workload_name": "bk-datalink-bk-worker-scheduler"
            #     },
            #     "target": "{namespace=blueking, pod_name=bk-datalink-bk-worker-scheduler-695856bb4f-fh6dn, workload_kind=Deployment, workload_name=bk-datalink-bk-worker-scheduler}",
            #     "metric_field": "_result_",
            #     "datapoints": [
            #         [3044.11,1732777440000],
            #     ],
            #     "alias": "_result_",
            #     "type": "line",
            #     "dimensions_translation": {},
            #     "unit": ""
            # },
            # mock 历史数据
            {
                "dimensions": {
                    "namespace": "blueking",
                    "pod_name": "bk-monitor-web-worker-scheduler-7b666c7788-2abcd",
                    "workload_kind": "Deployment",
                    "workload_name": "bk-monitor-web-worker-scheduler",
                },
                "target": "{namespace=blueking, pod_name=bk-monitor-web-worker-scheduler-7b666c7788-2abcd, workload_kind=Deployment, workload_name=bk-monitor-web-worker-scheduler}",
                "metric_field": "_result_",
                "datapoints": [
                    [644.77, 1732794960000],
                ],
                "alias": "_result_",
                "type": "line",
                "dimensions_translation": {},
                "unit": "",
            },
            # {
            #     "dimensions": {
            #         "namespace": "blueking",
            #         "pod_name": "bk-monitor-web-worker-7b666c4fc6-srlgb",
            #         "workload_kind": "Deployment",
            #         "workload_name": "bk-monitor-web-worker"
            #     },
            #     "target": "{namespace=blueking, pod_name=bk-monitor-web-worker-7b666c4fc6-srlgb, workload_kind=Deployment, workload_name=bk-monitor-web-worker}",
            #     "metric_field": "_result_",
            #     "datapoints": [
            #         [ 413.64,1732794960000],
            #     ],
            #     "alias": "_result_",
            #     "type": "line",
            #     "dimensions_translation": {},
            #     "unit": ""
            # }
        ]
        # 附带历史数据
        with mock.patch("core.drf_resource.resource.grafana.graph_unify_query") as mock_graph_unify_query:
            mock_graph_unify_query.return_value = {"series": query_result}
            validated_request_data["with_history"] = True
            pod_list = ListK8SResources()(validated_request_data)
            self.assertEqual(
                pod_list,
                (
                    [obj.to_meta_dict() for obj in orm_resource]
                    + [
                        BCSPod(
                            workload_type="Deployment",
                            workload_name="bk-monitor-web-worker-scheduler",
                            namespace="blueking",
                            name="bk-monitor-web-worker-scheduler-7b666c7788-2abcd",
                        ).to_meta_dict()
                    ]
                ),
            )

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
            "filter_dict": {"namespace": "blueking", "workload": "bk-monitor-web"},  # 查询是否有相同命名空间的数据
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
                'SELECT `bkmonitor_bcscontainer`.`id`, '
                '`bkmonitor_bcscontainer`.`bk_biz_id`, '
                '`bkmonitor_bcscontainer`.`bcs_cluster_id`, '
                '`bkmonitor_bcscontainer`.`name`, '
                '`bkmonitor_bcscontainer`.`namespace`, '
                '`bkmonitor_bcscontainer`.`pod_name`, '
                '`bkmonitor_bcscontainer`.`workload_type`, '
                '`bkmonitor_bcscontainer`.`workload_name` FROM `bkmonitor_bcscontainer` WHERE '
                '(`bkmonitor_bcscontainer`.`bcs_cluster_id` = BCS-K8S-00000 AND '
                '`bkmonitor_bcscontainer`.`bk_biz_id` = 2)'
            ),
        )
        # 验证 promql
        self.assertEqual(
            meta.meta_prom,
            'sum by (workload_kind, workload_name, namespace, container_name, pod_name) '
            '(container_cpu_system_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2"})',
        )

        # 校验包含更多查询的内容
        orm_resource = (
            BCSContainer.objects.filter(namespace="blueking", workload_name="bk-monitor-web")
            # BCSContainer.objects.filter(**validated_request_data["filter_dict"])
            .filter(name__icontains=validated_request_data["query_string"]).only(*K8sContainerMeta.only_fields)
        )
        # 验证 get_from_meta
        contianer_list = ListK8SResources()(validated_request_data)
        orm_data = [obj.to_meta_dict() for obj in orm_resource]

        self.assertEqual(contianer_list, [obj.to_meta_dict() for obj in orm_resource])
        # 验证 promql with  filter_dict AND query_string
        ListK8SResources().add_filter(meta, validated_request_data["filter_dict"])
        meta.filter.add(
            load_resource_filter(
                validated_request_data["resource_type"], validated_request_data["query_string"], fuzzy=True
            )
        )
        self.assertEqual(
            meta.meta_prom,
            'sum by (workload_kind, workload_name, namespace, container_name, pod_name) '
            '(container_cpu_system_seconds_total{bcs_cluster_id="BCS-K8S-00000",'
            'bk_biz_id="2",namespace="blueking",workload_name=~"monitor"})',  # <- 这里应该需要添加一个 podname可能
        )
        query_result = [
            # 需要构造数据
            {
                "dimensions": {
                    "namespace": "blueking",
                    "pod_name": "bk-datalink-bk-monitor-worker-scheduler-695856bb4f-fh6dn",
                    "workload_kind": "Deployment",
                    "workload_name": "bk-datalink-bk-monitor-worker-scheduler",
                },
                "target": "{namespace=blueking, pod_name=bk-datalink-bk-monitor-worker-scheduler-695856bb4f-fh6dn, workload_kind=Deployment, workload_name=bk-datalink-bk-monitor-worker-scheduler}",
                "metric_field": "_result_",
                "datapoints": [
                    [3044.11, 1732777440000],
                ],
                "alias": "_result_",
                "type": "line",
                "dimensions_translation": {},
                "unit": "",
            },
            {
                "dimensions": {
                    "namespace": "blueking",
                    "pod_name": "bk-datalink-bk-monitor-worker-web-c7f56d8b6-m789s",
                    "workload_kind": "Deployment",
                    "workload_name": "bk-datalink-bk-monitor-worker-web",
                },
                "target": "{namespace=blueking, pod_name=bk-datalink-bk-monitor-worker-web-c7f56d8b6-m789s, workload_kind=Deployment, workload_name=bk-datalink-bk-monitor-worker-web}",
                "metric_field": "_result_",
                "datapoints": [
                    [64.41, 1732777440000],
                ],
                "alias": "_result_",
                "type": "line",
                "dimensions_translation": {},
                "unit": "",
            },
            {
                "dimensions": {
                    "namespace": "blueking",
                    "pod_name": "bk-datalink-bk-monitor-worker-worker-queue-alarm-85b46bf576gfdb",
                    "workload_kind": "Deployment",
                    "workload_name": "bk-datalink-bk-monitor-worker-worker-queue-alarm",
                },
                "target": "{namespace=blueking, pod_name=bk-datalink-bk-monitor-worker-worker-queue-alarm-85b46bf576gfdb, workload_kind=Deployment, workload_name=bk-datalink-bk-monitor-worker-worker-queue-alarm}",
                "metric_field": "_result_",
                "datapoints": [
                    [3271.04, 1732777440000],
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
            self.assertEqual(
                pod_list,
                (
                    [obj.to_meta_dict() for obj in orm_resource]
                    # + ...  # TODO: 这里需要通过打断点搞明白 为什么要就加点东西
                ),
            )
