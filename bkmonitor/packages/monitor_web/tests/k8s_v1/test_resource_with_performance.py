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
        PromQL示例:
        ```PromQL
        sum by (namespace) (
          last_over_time(
            rate(
              container_cpu_usage_seconds_total{
                bcs_cluster_id="BCS-K8S-00000",
                bk_biz_id="2",
                container_name!="POD",
                namespace="bkbase"
              }[1m]
            )[1m:]
          )
        )
        ```
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
        PromQL示例:
        ```PromQL
        sum by (workload_kind, workload_name, namespace) (
          last_over_time(
            rate(
              container_cpu_usage_seconds_total{
                bcs_cluster_id="BCS-K8S-00000",
                bk_biz_id="2",
                container_name!="POD",
                namespace="blueking",
                workload_kind="Deployment",
                workload_name="bk-datalink-transfer-default"
              }[1m]
            )[1m:]
          )
        )
        ```
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
                    "target": """{
                        namespace=blueking,
                        workload_kind=Deployment,
                        workload_name=bk-datalink-transfer-default
                    }""",
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
        PromQL示例:
        ```PromQL
        sum by (workload_kind, workload_name, namespace, pod_name) (
          last_over_time(
            rate(
              container_cpu_usage_seconds_total{
                bcs_cluster_id="BCS-K8S-00000",
                bk_biz_id="2",
                container_name!="POD",
                pod_name="python-backend--0--session-default---experiment-clear-backbvcgm"
              }[1m]
            )[1m:]
          )
        )        ```
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
                    "target": """{
                        namespace=aiops-default,
                        pod_name=python-backend--0--session-default---experiment-clear-backbvcgm,
                        workload_kind=Deployment,
                        workload_name=python-backend--0--session-default---experiment-clear-backend---owned
                    }""",
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
        PromQL示例:
        ```PromQL
        sum by (workload_kind, workload_name, namespace, container_name, pod_name) (
          last_over_time(
            rate(
              container_cpu_usage_seconds_total{
                bcs_cluster_id="BCS-K8S-00000",
                bk_biz_id="2",
                container_name!="POD",
                container_name="aiops"
              }[1m]
            )[1m:]
          )
        )
        ```
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
                    "target": """{
                        container_name=aiops,
                        namespace=aiops-default,
                        pod_name=python-backend--0--session-default---experiment-clear-backbvcgm,
                        workload_kind=Deployment,
                        workload_name=python-backend--0--session-default---experiment-clear-backend---owned
                    }""",
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
    def test_namespace_exclude_history(self):
        """
        查询不带历史数据的 namepsace 列表
        """

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
        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]

    def test_workload_exclude_history(self):
        """
        查询不带历史数据的 workload 列表
        """
        workload_names = [
            "aasagent",
            "access",
            "add-pod-eni-ip-limit-webhook",
            "ap-nginx-portpool",
            "appassist",
        ]
        [create_workload(name, type="Deployment") for name in workload_names]

        validated_request_data = {
            "scenario": SCENARIO,
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
        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]

    def test_pod_exclude_history(self):
        """
        查询不带历史数据的 pod 列表
        """
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
            "scenario": SCENARIO,
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
        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]

    def test_container_exclude_history(self):
        """
        查询不带历史数据的 container 列表
        """
        mock_containers = [
            "account-service",
            "add-pod-eni-ip-limit-webhook",
            "alertmanager",
            "analyzer",
            "api",
        ]
        [create_container(name=container) for container in mock_containers]

        validated_request_data = {
            "scenario": SCENARIO,
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
        resutlt = ListK8SResources()(validated_request_data)
        assert mock_result["items"] == resutlt["items"]

    def test_next_page_namespace_exclude_history(self):
        """
        查询下一页不带历史数据的 namespace 列表
        """
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

    def test_next_page_workload_exclude_history(self):
        """
        查询下一页不带历史数据的 workload 列表
        """
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
            "scenario": SCENARIO,
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

    def test_next_page_pod_exclude_history(self):
        """
        查询下一页不带历史数据的 pod 列表
        """
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
                "DaemonSet",
                "bcs-argocd-example-plugin",
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
            "scenario": SCENARIO,
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

    def test_next_page_container_exclude_history(self):
        """
        查询下一页不带历史数据的 container 列表
        """
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
            "scenario": SCENARIO,
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

    def test_namespace_with_query_string_exclude_history(self):
        """
        模糊查询但不带历史数据的 namespace 列表
        """
        mock_namespaces = ["bkmonitor-operator", "bkmonitor-operator-bkop"]
        [create_namespace(name=namespace) for namespace in mock_namespaces]
        validated_request_data = {
            "scenario": SCENARIO,
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

    def test_workload_with_query_string_exclude_history(self):
        """
        模糊查询但不带历史数据的 workload 列表
        """
        create_workload(name="bk-datalink-unify-query-bkmonitor", type="Deployment")
        validated_request_data = {
            "scenario": SCENARIO,
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

    def test_pod_with_query_string_exclude_history(self):
        """
        模糊查询但不带历史数据的 pod 列表
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
            "scenario": SCENARIO,
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

    def test_container_with_query_string_exclude_history(self):
        """
        模糊查询但不带历史数据的 container 列表
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
            "scenario": SCENARIO,
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

    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    def test_namespace_with_history(self, graph_unify_query):
        """
        查询带历史数据的 namespace

        场景: promql 查询数据不足，还需要从 db 中查询补充数据
        """
        mock_namespace_list = [
            "bkbase",
            "blueking",
            "bkbase-flink",
            "deepflow",
            "kube-system",
            "aiops-default",
            "bcs-system",
            "bk-bscp",
            "bkmonitor-operator",
            "default",
            "new_namespace",
        ]
        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "start_time": 1745283797,
            "end_time": 1745287397,
            "page_size": 10,
            "page": 1,
            "resource_type": "namespace",
            "with_history": True,
            "page_type": "scrolling",
            "column": "container_cpu_usage_seconds_total",
            "order_by": "desc",
            "method": "sum",
            "bk_biz_id": 2,
        }
        mock_result = {
            "count": 79,
            "items": [
                {
                    "bk_biz_id": 2,
                    "bcs_cluster_id": "BCS-K8S-00000",
                    "namespace": namespace,
                }
                for namespace in mock_namespace_list[:-1]
            ],
        }

        graph_unify_query.return_value = {
            "series": [
                {
                    "dimensions": {"namespace": namespace},
                    "target": f"{{namespace={namespace}}}",
                    "metric_field": "_result_",
                    "datapoints": [[265.1846, 1744874940000]],
                    "alias": "_result_",
                    "type": "line",
                    "dimensions_translation": {},
                    "unit": "",
                }
                for namespace in mock_namespace_list[:5]
            ],
            "metrics": [],
        }

        [create_namespace(name=namespace) for namespace in mock_namespace_list[4:]]  # 第 5 - 10 个

        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]

        # 当 PromQL 查询的数据大于 page_size 取 result[:page_size]
        graph_unify_query.return_value = {
            "series": [
                {
                    "dimensions": {"namespace": namespace},
                    "target": f"{{namespace={namespace}}}",
                    "metric_field": "_result_",
                    "datapoints": [[265.1846, 1744874940000]],
                    "alias": "_result_",
                    "type": "line",
                    "dimensions_translation": {},
                    "unit": "",
                }
                for namespace in mock_namespace_list
            ],
            "metrics": [],
        }
        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]

    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    def test_namespace_with_history_and_filter(self, graph_unify_query):
        """
        查询带历史数据和过滤条件的 namespace 列表
        """
        namespace = "aiops-default"
        mock_namespace_list = ["aiops-default"]
        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {"namespace": [namespace]},
            "start_time": 1745315249,
            "end_time": 1745318849,
            "page_size": 20,
            "page": 2,
            "resource_type": "namespace",
            "with_history": True,
            "page_type": "scrolling",
            "column": "container_memory_working_set_bytes",
            "order_by": "desc",
            "method": "sum",
            "bk_biz_id": 2,
        }
        mock_result = {
            "count": 1,
            "items": [{"bk_biz_id": 2, "bcs_cluster_id": "BCS-K8S-00000", "namespace": namespace}],
        }
        graph_unify_query.return_value = {
            "series": [
                {
                    "dimensions": {"namespace": namespace},
                    "target": f"{{namespace={namespace}}}",
                    "metric_field": "_result_",
                    "datapoints": [[265.1846, 1744874940000]],
                    "alias": "_result_",
                    "type": "line",
                    "dimensions_translation": {},
                    "unit": "",
                }
                for namespace in mock_namespace_list
            ],
            "metrics": [],
        }
        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]

    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    def test_workload_with_history(self, graph_unify_query):
        """
        查询带历史数据的 workload 列表

        PromQL示例:
        ```PromQL
        topk(
          10,
          sum by (workload_kind, workload_name, namespace) (
            last_over_time(
              container_memory_working_set_bytes{
                bcs_cluster_id="BCS-K8S-00000",
                bk_biz_id="2",
                container_name!="POD"
              }[1m:]
            )
          )
        )
        ```
        """
        mock_workload_list = [
            ("bkbase", "StatefulSet", "bkbase-clean-outer-inland-bcs1"),
            ("bkbase", "StatefulSet", "bkbase-vmraw-outer-inland-bcs1"),
            ("bkbase", "StatefulSet", "bkbase-doris-inner-inland-bcs2"),
            ("bkbase", "Deployment", "bkbase-vmraw-kafka-inland-bcs1-deployment"),
            ("bkbase", "StatefulSet", "bkbase-puller-kafka-pulsar-bcs1"),
            ("bcs-system", "StatefulSet", "bcs-bkcmdb-synchronizer"),
            ("bkbase", "Deployment", "bkbase-queryengine-default"),
            ("bkbase", "StatefulSet", "bkbase-hdfsiceberg-inner-inland-bcs1"),
            ("bkbase", "Deployment", "bkbase-vmraw-kafka-inland-bcs2-deployment"),
            ("bkbase", "Deployment", "bkbase-queryengine-bkmonitor"),
        ]
        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "start_time": 1745303090,
            "end_time": 1745306690,
            "page_size": 10,
            "page": 1,
            "resource_type": "workload",
            "with_history": True,
            "page_type": "scrolling",
            "column": "container_memory_working_set_bytes",
            "order_by": "desc",
            "method": "sum",
            "bk_biz_id": 2,
        }

        graph_unify_query.return_value = {
            "series": [
                {
                    "dimensions": {
                        "namespace": namespace,
                        "workload_kind": workload_kind,
                        "workload_name": workload_name,
                    },
                    "target": f"""{{
                        namespace={namespace},
                        workload_kind={workload_kind},
                        workload_name={workload_name}
                    }}""",
                    "metric_field": "_result_",
                    "datapoints": [[265.1846, 1744874940000]],
                    "alias": "_result_",
                    "type": "line",
                    "dimensions_translation": {},
                    "unit": "",
                }
                for namespace, workload_kind, workload_name in mock_workload_list
            ],
            "metrics": [],
        }

        mock_result = {
            "count": 1422,
            "items": [
                {"namespace": namespace, "workload": f"{workload_type}:{workload_name}"}
                for namespace, workload_type, workload_name in mock_workload_list
            ],
        }

        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]

    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    def test_workload_with_history_and_filter(self, graph_unify_query):
        """
        查询带历史数据和过滤条件的 workload 列表

        PromQL示例:
        ```PromQL
        topk(
          10,
          sum by (workload_kind, workload_name, namespace) (
            last_over_time(
              container_memory_working_set_bytes{
                bcs_cluster_id="BCS-K8S-00000",
                bk_biz_id="2",
                container_name!="POD",
                namespace="aiops-default"
              }[1m:]
            )
          )
        )
        ```
        """
        namespace = "aiops-default"
        mock_workload_list = [
            ("Deployment", "service--1--session-default-incident-task-runner-owned"),
            ("Deployment", "service--0--session-default-incident-task-runner-owned"),
            ("Deployment", "service--0--session-default---incident-status-tracker---owned"),
            (
                "Deployment",
                "service--0--session-default---scene-service-period-scene-session---owned",
            ),
            ("Deployment", "service--0--session-default-api-serving-2-metric-recommendation-owned"),
            ("Deployment", "service--1--session-default-api-serving-2-metric-recommendation-owned"),
            ("Deployment", "service--0--session-default-auto-scheduler-serving-stream-ci-13-owned"),
            ("Deployment", "python-backend--0--session-default---inner-session---owned"),
            ("Deployment", "service--0--session-default-auto-scheduler-serving-stream-ci-12-owned"),
            ("Deployment", "service--0--session-default-auto-scheduler-serving-stream-ci-11-owned"),
        ]

        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {"namespace": ["aiops-default"]},
            "start_time": 1745303283,
            "end_time": 1745306883,
            "page_size": 10,
            "page": 1,
            "resource_type": "workload",
            "with_history": True,
            "page_type": "scrolling",
            "column": "container_memory_working_set_bytes",
            "order_by": "desc",
            "method": "sum",
            "bk_biz_id": 2,
        }

        mock_result = {
            "count": 46,
            "items": [
                {
                    "namespace": namespace,
                    "workload": f"{workload_kind}:{workload_name}",
                }
                for workload_kind, workload_name in mock_workload_list
            ],
        }
        graph_unify_query.return_value = {
            "series": [
                {
                    "dimensions": {
                        "namespace": namespace,
                        "workload_kind": workload_kind,
                        "workload_name": workload_name,
                    },
                    "target": f"""{{
                        namespace={namespace}, 
                        workload_kind={workload_kind},
                        workload_name={workload_name}
                    }}
                    """,
                    "metric_field": "_result_",
                    "datapoints": [[265.1846, 1744874940000]],
                    "alias": "_result_",
                    "type": "line",
                    "dimensions_translation": {},
                    "unit": "",
                }
                for workload_kind, workload_name in mock_workload_list
            ],
            "metrics": [],
        }
        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]

    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    def test_pod_with_history(self, graph_unify_query):
        """
        查询带历史数据的 pod 列表

        PromQL示例:
        ```PromQL
        topk(
          10,
          sum by (workload_kind, workload_name, namespace, pod_name) (
            last_over_time(
              container_memory_working_set_bytes{
                bcs_cluster_id="BCS-K8S-00000",
                bk_biz_id="2",
                container_name!="POD"
              }[1m:]
            )
          )
        )
        ```
        """
        mock_pod_list = [
            ("bcs-bkcmdb-synchronizer-0", "bcs-system", "StatefulSet:bcs-bkcmdb-synchronizer"),
            (
                "vm-sql-58ec3c53525d4209a2a44e6a00c02402-0",
                "bkbase-flink",
                "StatefulSet:vm-sql-58ec3c53525d4209a2a44e6a00c02402",
            ),
            ("bkbase-queryengine-default-7785d74fc7-trs9s", "bkbase", "Deployment:bkbase-queryengine-default"),
            ("bkbase-queryengine-default-7785d74fc7-h4mdl", "bkbase", "Deployment:bkbase-queryengine-default"),
            (
                "bkbase-vmraw-kafka-inland-bcs2-deployment-56d658c54b-g2k59",
                "bkbase",
                "Deployment:bkbase-vmraw-kafka-inland-bcs2-deployment",
            ),
            (
                "bkbase-vmraw-kafka-inland-bcs1-deployment-68c79cd785-4rgv9",
                "bkbase",
                "Deployment:bkbase-vmraw-kafka-inland-bcs1-deployment",
            ),
            (
                "bkbase-vmraw-kafka-inland-bcs1-deployment-68c79cd785-d5499",
                "bkbase",
                "Deployment:bkbase-vmraw-kafka-inland-bcs1-deployment",
            ),
            ("bkbase-vmraw-outer-inland-bcs1-0", "bkbase", "StatefulSet:bkbase-vmraw-outer-inland-bcs1"),
            ("bkbase-vmraw-outer-inland-bcs1-1", "bkbase", "StatefulSet:bkbase-vmraw-outer-inland-bcs1"),
            ("bkbase-vmraw-outer-inland-bcs1-2", "bkbase", "StatefulSet:bkbase-vmraw-outer-inland-bcs1"),
        ]
        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "start_time": 1745303638,
            "end_time": 1745307238,
            "page_size": 10,
            "page": 1,
            "resource_type": "pod",
            "with_history": True,
            "page_type": "scrolling",
            "column": "container_memory_working_set_bytes",
            "order_by": "desc",
            "method": "sum",
            "bk_biz_id": 2,
        }

        mock_result = {
            "count": 2321,
            "items": [
                {
                    "pod": pod,
                    "namespace": namespace,
                    "workload": workload,
                }
                for pod, namespace, workload in mock_pod_list
            ],
        }
        graph_unify_query.return_value = {
            "series": [
                {
                    "dimensions": {
                        "namespace": namespace,
                        "pod_name": pod,
                        "workload_kind": workload.split(":")[0],
                        "workload_name": workload.split(":")[1],
                    },
                    "target": f"""{{
                        namespace={namespace},
                        pod_name={pod},
                        workload_kind={workload.split(":")[0]},
                        workload_name={workload.split(":")[1]}}}
                    """,
                    "metric_field": "_result_",
                    "datapoints": [[265.1846, 1744874940000]],
                    "alias": "_result_",
                    "type": "line",
                    "dimensions_translation": {},
                    "unit": "",
                }
                for pod, namespace, workload in mock_pod_list
            ],
            "metrics": [],
        }
        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]

    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    def test_pod_with_history_and_filter(self, graph_unify_query):
        """
        查询带历史数据和过滤条件的 pod 列表

        PromQL示例:
        ```PromQL
        topk(
          10,
          sum by (workload_kind, workload_name, namespace, pod_name) (
            last_over_time(
              container_memory_working_set_bytes{
                bcs_cluster_id="BCS-K8S-00000",
                bk_biz_id="2",
                container_name!="POD",
                namespace="bcs-system",
                workload_kind="Deployment",
                workload_name="bcs-services-stack-bk-micro-gateway"
              }[1m:]
            )
          )
        )
        """
        mock_pod_list = [
            (
                "bcs-services-stack-bk-micro-gateway-5fdf9488dd-j5hcv",
                "bcs-system",
                "Deployment:bcs-services-stack-bk-micro-gateway",
            ),
            (
                "bcs-services-stack-bk-micro-gateway-5fdf9488dd-4vnll",
                "bcs-system",
                "Deployment:bcs-services-stack-bk-micro-gateway",
            ),
        ]

        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {
                "namespace": ["bcs-system"],
                "workload": ["Deployment:bcs-services-stack-bk-micro-gateway"],
            },
            "start_time": 1745303835,
            "end_time": 1745307435,
            "page_size": 10,
            "page": 1,
            "resource_type": "pod",
            "with_history": True,
            "page_type": "scrolling",
            "column": "container_memory_working_set_bytes",
            "order_by": "desc",
            "method": "sum",
            "bk_biz_id": 2,
        }
        mock_result = {
            "count": 2,
            "items": [
                {
                    "pod": pod,
                    "namespace": namespace,
                    "workload": workload,
                }
                for pod, namespace, workload in mock_pod_list
            ],
        }
        graph_unify_query.return_value = {
            "series": [
                {
                    "dimensions": {
                        "namespace": namespace,
                        "pod_name": pod,
                        "workload_kind": workload.split(":")[0],
                        "workload_name": workload.split(":")[1],
                    },
                    "target": f"""{{
                        namespace={namespace},
                        pod_name={pod},
                        workload_kind={workload.split(":")[0]},
                        workload_name={workload.split(":")[1]}}}
                    """,
                    "metric_field": "_result_",
                    "datapoints": [[265.1846, 1744874940000]],
                    "alias": "_result_",
                    "type": "line",
                    "dimensions_translation": {},
                    "unit": "",
                }
                for pod, namespace, workload in mock_pod_list
            ],
            "metrics": [],
        }
        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]

    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    def test_container_with_history(self, graph_unify_query):
        """
        查询带历史数据的 container 列表

        PromQL示例:
        ```PromQL
        topk(
          10,
          sum by (workload_kind, workload_name, namespace, container_name, pod_name) (
            last_over_time(
              container_memory_working_set_bytes{
                bcs_cluster_id="BCS-K8S-00000",
                bk_biz_id="2",
                container_name!="POD"
              }[1m:]
            )
          )
        )
        ```
        """
        mock_container_list = [
            (
                "bcs-bkcmdb-synchronizer-0",
                "bcs-bkcmdb-synchronizer-server",
                "bcs-system",
                "StatefulSet:bcs-bkcmdb-synchronizer",
            ),
            (
                "vm-sql-58ec3c53525d4209a2a44e6a00c02402-0",
                "victoria-metrics-single-server",
                "bkbase-flink",
                "StatefulSet:vm-sql-58ec3c53525d4209a2a44e6a00c02402",
            ),
            (
                "bkbase-queryengine-default-7785d74fc7-trs9s",
                "queryengine",
                "bkbase",
                "Deployment:bkbase-queryengine-default",
            ),
            (
                "bkbase-queryengine-default-7785d74fc7-h4mdl",
                "queryengine",
                "bkbase",
                "Deployment:bkbase-queryengine-default",
            ),
            (
                "bkbase-vmraw-kafka-inland-bcs2-deployment-56d658c54b-g2k59",
                "bkbase-vmraw-kafka-inland-bcs2-container",
                "bkbase",
                "Deployment:bkbase-vmraw-kafka-inland-bcs2-deployment",
            ),
            (
                "bkbase-vmraw-kafka-inland-bcs1-deployment-68c79cd785-4rgv9",
                "bkbase-vmraw-kafka-inland-bcs1-container",
                "bkbase",
                "Deployment:bkbase-vmraw-kafka-inland-bcs1-deployment",
            ),
            (
                "bkbase-vmraw-kafka-inland-bcs1-deployment-68c79cd785-d5499",
                "bkbase-vmraw-kafka-inland-bcs1-container",
                "bkbase",
                "Deployment:bkbase-vmraw-kafka-inland-bcs1-deployment",
            ),
            (
                "bkbase-vmraw-outer-inland-bcs1-0",
                "bkbase-vmraw-outer-inland-bcs1-container",
                "bkbase",
                "StatefulSet:bkbase-vmraw-outer-inland-bcs1",
            ),
            (
                "bkbase-vmraw-outer-inland-bcs1-1",
                "bkbase-vmraw-outer-inland-bcs1-container",
                "bkbase",
                "StatefulSet:bkbase-vmraw-outer-inland-bcs1",
            ),
            (
                "bkbase-vmraw-outer-inland-bcs1-2",
                "bkbase-vmraw-outer-inland-bcs1-container",
                "bkbase",
                "StatefulSet:bkbase-vmraw-outer-inland-bcs1",
            ),
        ]

        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "start_time": 1745304052,
            "end_time": 1745307652,
            "page_size": 10,
            "page": 1,
            "resource_type": "container",
            "with_history": True,
            "page_type": "scrolling",
            "column": "container_memory_working_set_bytes",
            "order_by": "desc",
            "method": "sum",
            "bk_biz_id": 2,
        }
        mock_result = {
            "count": 2579,
            "items": [
                {
                    "pod": pod,
                    "container": container,
                    "namespace": namespace,
                    "workload": workload,
                }
                for pod, container, namespace, workload in mock_container_list
            ],
        }
        graph_unify_query.return_value = {
            "series": [
                {
                    "dimensions": {
                        "container_name": container,
                        "namespace": namespace,
                        "pod_name": pod,
                        "workload_kind": workload.split(":")[0],
                        "workload_name": workload.split(":")[1],
                    },
                    "target": f"""{{
                        container_name={container},
                        namespace={namespace},
                        pod_name={pod},
                        workload_kind={workload.split(":")[0]},
                        workload_name={workload.split(":")[1]}}}
                    """,
                    "metric_field": "_result_",
                    "datapoints": [[265.1846, 1744874940000]],
                    "alias": "_result_",
                    "type": "line",
                    "dimensions_translation": {},
                    "unit": "",
                }
                for pod, container, namespace, workload in mock_container_list
            ],
            "metrics": [],
        }

        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]

    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    def test_container_with_history_and_filter(self, graph_unify_query):
        """
        查询带历史数据和过滤条件的 container 列表

        PromQL示例:
        ```PromQL
        topk(
          40,
          sum by (workload_kind, workload_name, namespace, container_name, pod_name) (
            last_over_time(
              container_memory_working_set_bytes{
                bcs_cluster_id="BCS-K8S-00000",
                bk_biz_id="2",
                container_name!="POD",
                container_name="queryengine",
                namespace="bkbase",
                pod_name="bkbase-queryengine-bkmonitor-6f495fd54-pfjpq"
              }[1m:]
            )
          )
        )
        ```
        """
        mock_container_list = [
            (
                "bkbase-queryengine-bkmonitor-6f495fd54-pfjpq",
                "queryengine",
                "bkbase",
                "Deployment:bkbase-queryengine-bkmonitor",
            )
        ]
        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {
                "namespace": ["bkbase"],
                "pod": ["bkbase-queryengine-bkmonitor-6f495fd54-pfjpq"],
                "container": ["queryengine"],
            },
            "start_time": 1745304141,
            "end_time": 1745307741,
            "page_size": 10,
            "page": 1,
            "resource_type": "container",
            "with_history": True,
            "page_type": "scrolling",
            "column": "container_memory_working_set_bytes",
            "order_by": "desc",
            "method": "sum",
            "bk_biz_id": 2,
        }
        mock_result = {
            "count": 1,
            "items": [
                {
                    "pod": pod,
                    "container": container,
                    "namespace": namespace,
                    "workload": workload,
                }
                for container, namespace, pod, workload in mock_container_list
            ],
        }
        graph_unify_query.return_value = {
            "series": [
                {
                    "dimensions": {
                        "container_name": container,
                        "namespace": namespace,
                        "pod_name": pod,
                        "workload_kind": workload.split(":")[0],
                        "workload_name": workload.split(":")[1],
                    },
                    "target": f"""{{
                        container_name={container}, 
                        namespace={namespace}, 
                        pod_name={pod}, 
                        workload_kind={workload.split(":")[0]}, 
                        workload_name={workload.split(":")[1]}}}
                    """,
                    "metric_field": "_result_",
                    "datapoints": [[265.1846, 1744874940000]],
                    "alias": "_result_",
                    "type": "line",
                    "dimensions_translation": {},
                    "unit": "",
                }
                for container, namespace, pod, workload in mock_container_list
            ],
            "metrics": [],
        }
        result = ListK8SResources()(validated_request_data)
        assert result == mock_result
