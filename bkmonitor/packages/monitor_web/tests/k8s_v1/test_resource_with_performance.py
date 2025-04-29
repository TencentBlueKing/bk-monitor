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
import pytest

from monitor_web.k8s.resources import (
    GetScenarioMetric,
    ListK8SResources,
    ResourceTrendResource,
    WorkloadOverview,
)
from monitor_web.tests.k8s_v1.conftest import (
    create_container,
    create_namespace,
    create_pod,
    create_workload,
)
from packages.monitor_web.k8s.scenario import Scenario

SCENARIO: Scenario = "performance"


@pytest.mark.django_db
class TestWorkloadOverview:
    def test_workload_overview_with_nothing(self, create_workloads):
        """
        不添加过滤条件，获取所有workload的概览信息
        """
        validated_request_data = {"bk_biz_id": 2, "bcs_cluster_id": "BCS-K8S-00000"}
        expected_result = [
            ["Deployment", 3],
            ["StatefulSet", 0],
            ["DaemonSet", 0],
            ["Job", 0],
            ["CronJob", 0],
            ["NewType", 1],
        ]
        assert expected_result == WorkloadOverview()(validated_request_data)

    def test_workload_overview_with_namespace(self, create_workloads):
        validated_request_data = {
            "bk_biz_id": 2,
            "bcs_cluster_id": "BCS-K8S-00000",
            "namespace": "blueking",
        }
        expected_result = [
            ["Deployment", 2],
            ["StatefulSet", 0],
            ["DaemonSet", 0],
            ["Job", 0],
            ["CronJob", 0],
        ]
        assert expected_result == WorkloadOverview()(validated_request_data)

    def test_workload_overview_with_query_string(self, create_workloads):
        validated_request_data = {
            "bk_biz_id": 2,
            "bcs_cluster_id": "BCS-K8S-00000",
            "query_string": "bk-monitor-web",
        }
        expected_result = [
            ["Deployment", 2],
            ["StatefulSet", 0],
            ["DaemonSet", 0],
            ["Job", 0],
            ["CronJob", 0],
        ]
        assert expected_result == WorkloadOverview()(validated_request_data)


@pytest.mark.django_db
class TestResourceTrendResourceWithPerformance:
    @pytest.mark.parametrize(
        ["column"],
        [
            pytest.param("container_cpu_usage_seconds_total"),
            pytest.param("container_cpu_cfs_throttled_ratio"),
            pytest.param("container_memory_working_set_bytes"),
            pytest.param("container_network_receive_bytes_total"),
            pytest.param("container_network_transmit_bytes_total"),
        ],
    )
    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    def test_with_namespace(
        self,
        graph_unify_query,
        column,
        get_start_time,
        get_end_time,
    ):
        """
        PromQL: 'sum by (namespace) (last_over_time(rate(container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD",namespace="bkbase"}[1m])[1m:]))'    # noqa
        """
        name = "bkbase"
        create_namespace(name)
        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {"namespace": [name]},
            "start_time": get_start_time,
            "end_time": get_end_time,
            "column": column,
            "method": "sum",
            "resource_type": "namespace",
            "resource_list": [name],
            "bk_biz_id": 2,
        }

        metric = GetScenarioMetric()(
            metric_id=column,
            scenario=SCENARIO,
            bk_biz_id=2,
        )
        mock_expected_result = [
            {
                column: {
                    "datapoints": [
                        [
                            265.1846,
                            1744874940000,
                        ],
                    ],
                    "unit": metric["unit"],
                    "value_title": metric["name"],
                },
                "resource_name": name,
            },
        ]

        graph_unify_query.return_value = {
            "series": [
                {
                    "dimensions": {"namespace": "bkbase"},
                    "target": "{namespace=bkbase}",
                    "metric_field": "_result_",
                    "datapoints": [[265.1846, 1744874940000]],
                    "alias": "_result_",
                    "type": "line",
                    "dimensions_translation": {},
                    "unit": "",
                }
            ],
            "metrics": [],
        }

        result = ResourceTrendResource()(validated_request_data)

        assert result == mock_expected_result

    @pytest.mark.parametrize(
        ["column"],
        [
            pytest.param("container_cpu_usage_seconds_total"),
            pytest.param("kube_pod_cpu_requests_ratio"),
            pytest.param("kube_pod_cpu_limits_ratio"),
            pytest.param("container_cpu_cfs_throttled_ratio"),
            pytest.param("container_memory_working_set_bytes"),
            pytest.param("kube_pod_memory_requests_ratio"),
            pytest.param("kube_pod_memory_limits_ratio"),
            pytest.param("container_network_receive_bytes_total"),
            pytest.param("container_network_transmit_bytes_total"),
        ],
    )
    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    def test_with_workload(
        self,
        graph_unify_query,
        column,
        get_start_time,
        get_end_time,
    ):
        """
        PromQL: 'sum by (workload_kind, workload_name, namespace) (last_over_time(rate(container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD",workload_kind="Deployment",workload_name="bk-datalink-transfer-default",namespace="blueking"}[1m])[1m:]))'  # noqa
        """

        name = "blueking|Deployment:bk-datalink-transfer-default"
        resource_type = "workload"
        create_namespace(name)
        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "start_time": get_start_time,
            "end_time": get_end_time,
            "column": column,
            "method": "sum",
            "resource_type": resource_type,
            "resource_list": [name],
            "bk_biz_id": 2,
        }

        metric = GetScenarioMetric()(
            metric_id=column,
            scenario=SCENARIO,
            bk_biz_id=2,
        )
        mock_expected_result = [
            {
                column: {
                    "datapoints": [
                        [
                            265.1846,
                            1744874940000,
                        ],
                    ],
                    "unit": metric["unit"],
                    "value_title": metric["name"],
                },
                "resource_name": name,
            },
        ]

        graph_unify_query.return_value = {
            "series": [
                {
                    "dimensions": {
                        "namespace": "blueking",
                        "workload_kind": "Deployment",
                        "workload_name": "bk-datalink-transfer-default",
                    },
                    "target": "{namespace=blueking, workload_kind=Deployment, workload_name=bk-datalink-transfer-default}",  # noqa
                    "metric_field": "_result_",
                    "datapoints": [[265.1846, 1744874940000]],
                    "alias": "_result_",
                    "type": "line",
                    "dimensions_translation": {},
                    "unit": "",
                }
            ],
            "metrics": [],
        }

        result = ResourceTrendResource()(validated_request_data)

        assert result == mock_expected_result

    @pytest.mark.parametrize(
        ["column"],
        [
            pytest.param("container_cpu_usage_seconds_total"),
            pytest.param("kube_pod_cpu_requests_ratio"),
            pytest.param("kube_pod_cpu_limits_ratio"),
            pytest.param("container_cpu_cfs_throttled_ratio"),
            pytest.param("container_memory_working_set_bytes"),
            pytest.param("kube_pod_memory_requests_ratio"),
            pytest.param("kube_pod_memory_limits_ratio"),
            pytest.param("container_network_receive_bytes_total"),
            pytest.param("container_network_transmit_bytes_total"),
        ],
    )
    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    def test_with_pod(
        self,
        graph_unify_query,
        column,
        get_start_time,
        get_end_time,
    ):
        """
        PromQL: 'sum by (workload_kind, workload_name, namespace, pod_name) (last_over_time(rate(container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD",pod_name="python-backend--0--session-default---experiment-clear-backbvcgm"}[1m])[1m:]))'  # noqa
        """

        name = "python-backend--0--session-default---experiment-clear-backbvcgm"
        resource_type = "pod"
        # create_namespace(name)

        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {"pod": [name]},
            "start_time": get_start_time,
            "end_time": get_end_time,
            "column": column,
            "method": "sum",
            "resource_type": resource_type,
            "resource_list": [name],
            "bk_biz_id": 2,
        }

        metric = GetScenarioMetric()(
            metric_id=column,
            scenario=SCENARIO,
            bk_biz_id=2,
        )
        mock_expected_result = [
            {
                column: {
                    "datapoints": [
                        [
                            265.1846,
                            1744874940000,
                        ],
                    ],
                    "unit": metric["unit"],
                    "value_title": metric["name"],
                },
                "resource_name": name,
            },
        ]

        graph_unify_query.return_value = {
            "series": [
                {
                    "dimensions": {
                        "namespace": "aiops-default",
                        "pod_name": "python-backend--0--session-default---experiment-clear-backbvcgm",
                        "workload_kind": "Deployment",
                        "workload_name": "python-backend--0--session-default---experiment-clear-backend---owned",
                    },
                    "target": "{namespace=aiops-default, pod_name=python-backend--0--session-default---experiment-clear-backbvcgm, workload_kind=Deployment, workload_name=python-backend--0--session-default---experiment-clear-backend---owned}",  # noqa
                    "metric_field": "_result_",
                    "datapoints": [[265.1846, 1744874940000]],
                    "alias": "_result_",
                    "type": "line",
                    "dimensions_translation": {},
                    "unit": "",
                }
            ],
            "metrics": [],
        }

        result = ResourceTrendResource()(validated_request_data)

        assert result == mock_expected_result

    @pytest.mark.parametrize(
        ["column"],
        [
            pytest.param("container_cpu_usage_seconds_total"),
            pytest.param("kube_pod_cpu_requests_ratio"),
            pytest.param("kube_pod_cpu_limits_ratio"),
            pytest.param("container_cpu_cfs_throttled_ratio"),
            pytest.param("container_memory_working_set_bytes"),
            pytest.param("kube_pod_memory_requests_ratio"),
            pytest.param("kube_pod_memory_limits_ratio"),
        ],
    )
    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    def test_with_container(
        self,
        graph_unify_query,
        column,
        get_start_time,
        get_end_time,
    ):
        """
        PromQL: 'sum by (workload_kind, workload_name, namespace, container_name, pod_name) (last_over_time(rate(container_cpu_usage_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD",container_name="aiops"}[1m])[1m:]))'  # noqa
        """

        name = "aiops"
        pod_name = "python-backend--0--session-default---experiment-clear-backbvcgm"
        resource_type = "container"

        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {"container": [name]},
            "start_time": get_start_time,
            "end_time": get_end_time,
            "column": column,
            "method": "sum",
            "resource_type": resource_type,
            "resource_list": [name],
            "bk_biz_id": 2,
        }

        metric = GetScenarioMetric()(
            metric_id=column,
            scenario=SCENARIO,
            bk_biz_id=2,
        )
        mock_expected_result = [
            {
                column: {
                    "datapoints": [
                        [
                            265.1846,
                            1744874940000,
                        ],
                    ],
                    "unit": metric["unit"],
                    "value_title": metric["name"],
                },
                # 容器名称会结合 pod_name 应为 K8sContainerMeta().resource_field_list() -> ["pod_name", self.resource_field]
                "resource_name": f"{pod_name}:{name}",
            },
        ]

        graph_unify_query.return_value = {
            "series": [
                {
                    "dimensions": {
                        "container_name": "aiops",
                        "namespace": "aiops-default",
                        "pod_name": "python-backend--0--session-default---experiment-clear-backbvcgm",
                        "workload_kind": "Deployment",
                        "workload_name": "python-backend--0--session-default---experiment-clear-backend---owned",
                    },
                    "target": "{container_name=aiops, namespace=aiops-default, pod_name=python-backend--0--session-default---experiment-clear-backbvcgm, workload_kind=Deployment, workload_name=python-backend--0--session-default---experiment-clear-backend---owned}",  # noqa
                    "metric_field": "_result_",
                    "datapoints": [[265.1846, 1744874940000]],
                    "alias": "_result_",
                    "type": "line",
                    "dimensions_translation": {},
                    "unit": "",
                }
            ],
            "metrics": [],
        }

        result = ResourceTrendResource()(validated_request_data)

        assert result == mock_expected_result

    @pytest.mark.parametrize(
        ["column"],
        [
            pytest.param("container_cpu_usage_seconds_total"),
            pytest.param("kube_pod_cpu_requests_ratio"),
            pytest.param("kube_pod_cpu_limits_ratio"),
            pytest.param("container_cpu_cfs_throttled_ratio"),
            pytest.param("container_memory_working_set_bytes"),
            pytest.param("kube_pod_memory_requests_ratio"),
            pytest.param("kube_pod_memory_limits_ratio"),
        ],
    )
    def test_with_no_resource_list(
        self,
        column,
        get_start_time,
        get_end_time,
    ):
        name = "aiops"
        resource_type = "container"

        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {"container": [name]},
            "start_time": get_start_time,
            "end_time": get_end_time,
            "column": column,
            "method": "sum",
            "resource_type": resource_type,
            "resource_list": [],
            "bk_biz_id": 2,
        }
        result = ResourceTrendResource()(validated_request_data)

        assert result == []


@pytest.mark.django_db
class TestListK8SResourcesWithPerformance:
    def test_left_default_namespace(self):
        """获取左侧默认namespace列表"""
        mock_namespace_names = [
            "base",
            "bcs-op-yunwei-frodomei",
            "bcs-stag-cloud-test",
            "bcs-system",
            "bcsk8s-sutest",
        ]
        [create_namespace(name) for name in mock_namespace_names]

        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "query_string": "",
            "page_size": 5,
            "page_type": "scrolling",
            "start_time": 1744957564,
            "end_time": 1744961164,
            "resource_type": "namespace",
            "page": 1,
            "bk_biz_id": 2,
        }

        mock_result = {
            "count": 90,
            "items": [
                {
                    "bk_biz_id": 2,
                    "bcs_cluster_id": "BCS-K8S-00000",
                    "namespace": name,
                }
                for name in mock_namespace_names
            ],
        }
        result = ListK8SResources()(validated_request_data)  # noqa
        assert result["items"] == mock_result["items"]

    def test_left_default_workload(self):
        workload_names = [
            "aasagent",
            "access",
            "add-pod-eni-ip-limit-webhook",
            "ap-nginx-portpool",
            "appassist",
        ]
        [create_workload(name, type="Deployment") for name in workload_names]

        validated_request_data = {
            "scenario": "performance",
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {"workload": "Deployment:"},
            "query_string": "",
            "page_size": 5,
            "page_type": "scrolling",
            "start_time": 1744957564,
            "end_time": 1744961164,
            "resource_type": "workload",
            "bk_biz_id": 2,
        }
        mock_result = {
            "count": 425,
            "items": [{"workload": f"Deployment:{name}"} for name in workload_names],
        }
        result = ListK8SResources()(validated_request_data)  # noqa
        assert result["items"] == mock_result["items"]

    def test_left_default_pod(self):
        mock_pods = [
            (
                "bcs-argocd-controller-7c776dcc5c-88tqm",
                "bcs-system",
                "Deployment",
                "bcs-argocd-controller",
            ),
            (
                "bcs-argocd-etcd-0",
                "bcs-system",
                "StatefulSet",
                "bcs-argocd-etcd",
            ),
            (
                "bcs-argocd-example-plugin-8579c7bc99-25xhd",
                "bcs-system",
                "Deployment",
                "bcs-argocd-example-plugin",
            ),
            (
                "bcs-argocd-server-f84dd95b-mlvqh",
                "bcs-system",
                "Deployment",
                "bcs-argocd-server",
            ),
            (
                "bcs-egress-operator-7c658d6674-hd49f",
                "bcs-system",
                "Deployment",
                "bcs-egress-operator",
            ),
        ]
        [
            create_pod(
                name=pod,
                namespace=namespace,
                workload_type=workload_type,
                workload_name=workload_name,
            )
            for pod, namespace, workload_type, workload_name in mock_pods
        ]
        validated_request_data = {
            "scenario": "performance",
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "query_string": "",
            "page_size": 5,
            "page_type": "scrolling",
            "start_time": 1744957564,
            "end_time": 1744961164,
            "resource_type": "pod",
            "page": 1,
            "bk_biz_id": 2,
        }
        mock_result = {
            "count": 2159,
            "items": [
                {
                    "pod": pod,
                    "namespace": namespace,
                    "workload": f"{workload_type}:{workload_name}",
                }
                for pod, namespace, workload_type, workload_name in mock_pods
            ],
        }
        result = ListK8SResources()(validated_request_data)  # noqa
        assert result["items"] == mock_result["items"]

    def test_left_default_container(self):
        mock_containers = [
            "account-service",
            "add-pod-eni-ip-limit-webhook",
            "alertmanager",
            "analyzer",
            "api",
        ]
        [create_container(name=container) for container in mock_containers]

        validated_request_data = {
            "scenario": "performance",
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "query_string": "",
            "page_size": 5,
            "page_type": "scrolling",
            "start_time": 1744957564,
            "end_time": 1744961164,
            "resource_type": "container",
            "page": 1,
            "bk_biz_id": 2,
        }
        mock_result = {
            "count": 400,
            "items": [{"container": item} for item in mock_containers],
        }
        resutlt = ListK8SResources()(validated_request_data)  # noqa
        assert mock_result["items"] == resutlt["items"]

    def test_left_next_page_namespace(self):
        mock_namespace_names = [
            "base",
            "bcs-op-yunwei-frodomei",
            "bcs-stag-cloud-test",
            "bcs-system",
            "bcsk8s-sutest",
            "bk-monitor",
            "bk-system",
            "bkenvmanager-k8s-wesleytest",
            "bkmonitor-operator",
            "bkmonitor-operator-bkop",
        ]
        [create_namespace(name) for name in mock_namespace_names]

        validated_request_data = {
            "scenario": "network",
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "query_string": "",
            "page_size": 5,
            "page_type": "scrolling",
            "start_time": 1745199913,
            "end_time": 1745203513,
            "resource_type": "namespace",
            "page": 2,
            "bk_biz_id": 2,
        }
        mock_result = {
            "count": 89,
            "items": [
                {
                    "bk_biz_id": 2,
                    "bcs_cluster_id": "BCS-K8S-00000",
                    "namespace": name,
                }
                for name in mock_namespace_names
            ],
        }
        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]

    def test_left_next_page_workload(self):
        mock_workloads = [
            "aasagent",
            "access",
            "add-pod-eni-ip-limit-webhook",
            "ap-nginx-portpool",
            "appassist",
            "authagent",
            "auto-lqa-schedule-server",
            "bcs-argocd-controller",
            "bcs-argocd-example-plugin",
            "bcs-argocd-server",
        ]
        [create_workload(name, type="Deployment") for name in mock_workloads]

        validated_request_data = {
            "scenario": "performance",
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {"workload": "Deployment:"},
            "query_string": "",
            "page_size": 5,
            "page_type": "scrolling",
            "start_time": 1745214975,
            "end_time": 1745218575,
            "resource_type": "workload",
            "page": 2,
            "bk_biz_id": 2,
        }
        mock_result = {
            "count": 429,
            "items": [{"workload": f"Deployment:{name}"} for name in mock_workloads],
        }

        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]

    def test_left_next_page_pod(self):
        mock_pods = [
            (
                "bcs-argocd-controller-7c776dcc5c-88tqm",
                "bcs-system",
                "Deployment",
                "bcs-argocd-controller",
            ),
            (
                "bcs-argocd-etcd-0",
                "bcs-system",
                "StatefulSet",
                "bcs-argocd-etcd",
            ),
            (
                "bcs-argocd-example-plugin-8579c7bc99-25xhd",
                "bcs-system",
                "Deployment",
                "bcs-argocd-example-plugin",
            ),
            (
                "bcs-argocd-server-f84dd95b-mlvqh",
                "bcs-system",
                "Deployment",
                "bcs-argocd-server",
            ),
            (
                "bcs-egress-operator-7c658d6674-hd49f",
                "bcs-system",
                "Deployment",
                "bcs-egress-operator",
            ),
            {
                "bcs-gamedeployment-operator-847b879d69-xldv8",
                "bcs-system",
                "Deployment",
                "bcs-gamedeployment-operator",
            },
            {
                "bcs-gamestatefulset-operator-644ffbbdf-pcnnc",
                "bcs-system",
                "Deployment",
                "bcs-gamestatefulset-operator",
            },
            {
                "bcs-general-pod-autoscaler-78cc6465cd-9hxnb",
                "bcs-system",
                "Deployment",
                "bcs-general-pod-autoscaler",
            },
            {
                "bcs-general-pod-autoscaler-78cc6465cd-wjxjk",
                "bcs-system",
                "Deployment",
                "bcs-general-pod-autoscaler",
            },
            {
                "bcs-hook-operator-7bc6d76-r4vzx",
                "bcs-system",
                "Deployment",
                "bcs-hook-operator",
            },
        ]
        [
            create_pod(
                name=pod,
                namespace=namespace,
                workload_type=workload_type,
                workload_name=workload_name,
            )
            for pod, namespace, workload_type, workload_name in mock_pods
        ]
        validated_request_data = {
            "scenario": "performance",
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "query_string": "",
            "page_size": 5,
            "page_type": "scrolling",
            "start_time": 1745215030,
            "end_time": 1745218630,
            "resource_type": "pod",
            "page": 2,
            "bk_biz_id": 2,
        }
        mock_result = {
            "count": 2159,
            "items": [
                {
                    "pod": pod,
                    "namespace": namespace,
                    "workload": f"{workload_type}:{workload_name}",
                }
                for pod, namespace, workload_type, workload_name in mock_pods
            ],
        }

        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]

    def test_left_next_page_container(self):
        mock_containers = [
            "account-service",
            "add-pod-eni-ip-limit-webhook",
            "alertmanager",
            "analyzer",
            "api",
            "apiquery",
            "app",
            "applicationset-controller",
            "argocd-repo-server",
            "argocd-server",
        ]
        [create_container(name=container) for container in mock_containers]

        validated_request_data = {
            "scenario": "performance",
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "query_string": "",
            "page_size": 5,
            "page_type": "scrolling",
            "start_time": 1745215087,
            "end_time": 1745218687,
            "resource_type": "container",
            "page": 2,
            "bk_biz_id": 2,
        }
        mock_result = {
            "count": 406,
            "items": [
                {"container": "account-service"},
                {"container": "add-pod-eni-ip-limit-webhook"},
                {"container": "alertmanager"},
                {"container": "analyzer"},
                {"container": "api"},
                {"container": "apiquery"},
                {"container": "app"},
                {"container": "applicationset-controller"},
                {"container": "argocd-repo-server"},
                {"container": "argocd-server"},
            ],
        }
        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]

    def test_left_namespace_with_query_string(self):
        """
        添加 query_string 模糊查询 namespace 列表
        """
        mock_namespaces = ["bkmonitor-operator", "bkmonitor-operator-bkop"]
        [create_namespace(name=namespace) for namespace in mock_namespaces]
        validated_request_data = {
            "scenario": "performance",
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "query_string": "bkmonitor",
            "page_size": 5,
            "page_type": "scrolling",
            "start_time": 1745200006,
            "end_time": 1745203606,
            "resource_type": "namespace",
            "page": 1,
            "bk_biz_id": 2,
        }
        mock_result = {
            "count": 2,
            "items": [
                {
                    "bk_biz_id": 2,
                    "bcs_cluster_id": "BCS-K8S-00000",
                    "namespace": item,
                }
                for item in mock_namespaces
            ],
        }
        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]

    def test_left_workload_with_query_string(self):
        """
        添加 query_string 模糊查询 namespace 列表
        """
        create_workload(name="bk-datalink-unify-query-bkmonitor", type="Deployment")
        validated_request_data = {
            "scenario": "performance",
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {"workload": "Deployment:"},
            "query_string": "bkmonitor",
            "page_size": 5,
            "page_type": "scrolling",
            "start_time": 1745200006,
            "end_time": 1745203606,
            "resource_type": "workload",
            "bk_biz_id": 2,
        }
        mock_result = {
            "count": 1,
            "items": [{"workload": "Deployment:bk-datalink-unify-query-bkmonitor"}],
        }

        result = ListK8SResources()(validated_request_data)
        assert result == mock_result

    def test_left_pod_with_query_string(self):
        """
        添加 query_string 模糊查询 namespace 列表
        """
        mock_pods = [
            (
                "bkbase-clean-bkmonitorgz23-gz1-post-install-x6wlm",
                "ieg-bkbase-databus-kafka-prod",
                "Job",
                "bkbase-clean-bkmonitorgz23-gz1-post-install",
            ),
            (
                "bkm-daemonset-worker-ldlgn-x-bkmonitor-operator-x-vc-31e8a0d526",
                "ieg-bkbase-sr-dev",
                "Service",
                "vcluster-k8s-bkbase",
            ),
            (
                "bkm-event-worker-76776c96b8-b2w5r-x-bkmonitor-operat-24194ba6dc",
                "ieg-bkbase-sr-dev",
                "Service",
                "vcluster-k8s-bkbase",
            ),
            (
                "bkm-operator-cdcb975b6-vs54s-x-bkmonitor-operator-x--ea2f7fdb84",
                "ieg-bkbase-sr-dev",
                "Service",
                "vcluster-k8s-bkbase",
            ),
            (
                "bkm-prometheus-node-exporter-dc2nl-x-bkmonitor-opera-2ea3908caa",
                "ieg-bkbase-sr-dev",
                "Service",
                "vcluster-k8s-bkbase",
            ),
        ]
        [
            create_pod(
                name=pod,
                namespace=namespace,
                workload_type=workload_type,
                workload_name=workload_name,
            )
            for pod, namespace, workload_type, workload_name in mock_pods
        ]
        validated_request_data = {
            "scenario": "performance",
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "query_string": "bkmonitor",
            "page_size": 5,
            "page_type": "scrolling",
            "start_time": 1745200006,
            "end_time": 1745203606,
            "resource_type": "pod",
            "page": 1,
            "bk_biz_id": 2,
        }
        mock_result = {
            "count": 13,
            "items": [
                {
                    "pod": pod,
                    "namespace": namespace,
                    "workload": f"{workload_type}:{workload_name}",
                }
                for pod, namespace, workload_type, workload_name in mock_pods
            ],
        }
        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]

    def test_left_container_with_query_string(self):
        """
        添加 query_string 模糊查询 namespace 列表
        """
        mock_containers = [
            "account-service",
            "bkbase-clean-bkmonitorgz23-gz1-post-install-job",
            "bkmonitor-operator",
            "bkmonitorbeat",
            "dbm-bkmonitor-init",
        ]
        [create_container(name=container) for container in mock_containers]

        validated_request_data = {
            "scenario": "performance",
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "query_string": "bkmonitor",
            "page_size": 5,
            "page_type": "scrolling",
            "start_time": 1745200006,
            "end_time": 1745203606,
            "resource_type": "container",
            "page": 1,
            "bk_biz_id": 2,
        }
        mock_result = {
            "count": 4,
            "items": [
                {"container": "bkbase-clean-bkmonitorgz23-gz1-post-install-job"},
                {"container": "bkmonitor-operator"},
                {"container": "bkmonitorbeat"},
                {"container": "dbm-bkmonitor-init"},
            ],
        }
        result = ListK8SResources()(validated_request_data)
        assert result == mock_result
