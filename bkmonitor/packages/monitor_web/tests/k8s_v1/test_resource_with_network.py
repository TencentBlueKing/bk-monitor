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
)
from monitor_web.tests.k8s_v1.conftest import (
    create_ingress,
    create_namespace,
    create_pod,
    create_service,
)
from packages.monitor_web.k8s.scenario import Scenario

SCENARIO: Scenario = "network"


@pytest.mark.django_db
class TestResourceTrendResourceWithNetwork:
    @pytest.mark.parametrize(
        ["column"],
        [
            pytest.param("nw_container_network_receive_bytes_total"),
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
          sum by (namespace, pod) (
            last_over_time(rate(container_network_receive_bytes_total{namespace="aiops"}[1m])[1m:])
          )
        )
        ```
        """
        name = "bkbase"
        resource_type = "namespace"
        create_namespace(name)
        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {"namespace": [name]},
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
            pytest.param("nw_container_network_receive_bytes_total"),
        ],
    )
    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    def test_with_ingress(
        self,
        graph_unify_query,
        column,
        get_start_time,
        get_end_time,
    ):
        """
        PromQL示例:
        ```PromQL
        sum by (ingress, namespace) (
          (
            count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (
              ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",ingress="bk-dbm"}
            ) * 0 + 1
          )
          * on (namespace, service) group_left (pod)
            (count by (service, namespace, pod) (pod_with_service_relation))
          * on (namespace, pod) group_left ()
            sum by (namespace, pod) (last_over_time(rate(container_network_receive_bytes_total[1m])[1m:]))
        )
        ```
        """
        name = "bk-dbm"
        resource_type = "ingress"
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
                    "dimensions": {"ingress": "bk-dbm", "namespace": "blueking"},
                    "target": "{ingress=bk-dbm, namespace=blueking}",
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
            pytest.param("nw_container_network_receive_bytes_total"),
        ],
    )
    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    def test_with_service(
        self,
        graph_unify_query,
        column,
        get_start_time,
        get_end_time,
    ):
        """
        PromQL示例:
        ```PromQL
        sum by (namespace, service) (
            (
                  count by (service, namespace, pod) (
                    pod_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",service="bk-gse-data"}
                  )
                *
                  0
              +
                1
            )
          * on (namespace, pod) group_left ()
            sum by (namespace, pod) (last_over_time(rate(container_network_receive_bytes_total[1m])[1m:]))
        )
        ```
        """
        name = "bk-gse-data"
        resource_type = "service"

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
                    "dimensions": {"namespace": "blueking", "service": "bk-gse-data"},
                    "target": "{namespace=blueking, service=bk-gse-data}",
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
            pytest.param("nw_container_network_receive_bytes_total"),
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
        label_replace(
          sum by (namespace, pod) (
            sum by (namespace, pod) (
              last_over_time(
                rate(container_network_receive_bytes_total{pod_name="kube-flannel-ds-kpcpv"}[1m])[1m:]
              )
            )
          ),
          "pod_name",
          "$1",
          "pod",
          "(.*)"
        )
        ```
        """

        name = "kube-flannel-ds-kpcpv"
        resource_type = "pod"

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
                        "namespace": "kube-system",
                        "pod": "kube-flannel-ds-kpcpv",
                        "pod_name": "kube-flannel-ds-kpcpv",
                    },
                    "target": "{namespace=kube-system, pod=kube-flannel-ds-kpcpv, pod_name=kube-flannel-ds-kpcpv}",
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


@pytest.mark.django_db
class TestListK8SResourcesWithNetwork:
    def test_namespace_exclude_history(self):
        """
        查询不带历史数据的 namepsace 列表
        """
        mock_namespace_names = [
            "aiops-default",
            "apm-demo",
            "bcs-op",
            "bcs-system",
            "bk-bscp",
        ]
        [create_namespace(name) for name in mock_namespace_names]

        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "query_string": "",
            "page_size": 5,
            "page_type": "scrolling",
            "start_time": 1745284082,
            "end_time": 1745287682,
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

    def test_ingress_exclude_history(self):
        """
        查询不带历史数据的 ingress 列表
        """
        mock_ingress_list = [
            ("bcs-ui", "bcs-system"),
            ("stack-bcs-api-gateway-http", "bcs-system"),
            ("bk-bscp-apiserver", "bk-bscp"),
            ("bk-bscp-ui", "bk-bscp"),
            ("agent-plugin-subpath", "bkapp-agent-plugin-prod"),
        ]
        [create_ingress(name, namespace) for name, namespace in mock_ingress_list]
        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "query_string": "",
            "page_size": 5,
            "page_type": "scrolling",
            "start_time": 1745387225,
            "end_time": 1745390825,
            "resource_type": "ingress",
            "page": 1,
            "bk_biz_id": 2,
        }
        mock_result = {
            "count": 197,
            "items": [{"ingress": ingress, "namespace": namespace} for ingress, namespace in mock_ingress_list],
        }
        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]

    def test_service_exclude_history(self):
        """
        查询不带历史数据的 service 列表
        """
        mock_service_list = [
            ("service-0238ac93f359ac407d5ceccc599655b4", "aiops-default"),
            ("service-0238d26ae5c36675c65f07fea9f32273", "aiops-default"),
            ("service-029f77b8bb2517480e2a2377a66c3670", "aiops-default"),
            ("service-07efbaabe7ea713a9ebc7a222b24084d", "aiops-default"),
            ("service-0852a0955d7531c0eb0df994303037bf", "aiops-default"),
        ]
        [create_service(name, namespace) for name, namespace in mock_service_list]
        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "query_string": "",
            "page_size": 5,
            "page_type": "scrolling",
            "start_time": 1745387225,
            "end_time": 1745390825,
            "resource_type": "service",
            "page": 1,
            "bk_biz_id": 2,
        }
        mock_result = {
            "count": 598,
            "items": [{"service": service, "namespace": namespace} for service, namespace in mock_service_list],
        }
        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]

    def test_pod_exclude_history(self):
        """
        查询不带历史数据的 pod 列表
        """
        mock_pod_list = [
            (
                "python-backend--0--session-default---experiment-clear-backbvcgm",
                "aiops-default",
                "Deployment:python-backend--0--session-default---experiment-clear-backend---owned",
            ),
            (
                "python-backend--0--session-default---scene-service-period-d2cn7",
                "aiops-default",
                "Deployment:python-backend--0--session-default---scene-close-outdated-version-session---owned",
            ),
            (
                "python-backend--0--session-default---scene-service-plan-prrnm9l",
                "aiops-default",
                "Deployment:python-backend--0--session-default---scene-service-plan-preview---owned",
            ),
            (
                "python-backend--0--session-default---serving-status---owne6585s",
                "aiops-default",
                "Deployment:python-backend--0--session-default---serving-status---owned",
            ),
            ("apm-demo-6df7f957c9-68gzc", "apm-demo", "Deployment:apm-demo"),
        ]
        [
            create_pod(
                name=pod,
                namespace=namespace,
                workload_type=workload.split(":")[0],
                workload_name=workload.split(":")[1],
            )
            for pod, namespace, workload in mock_pod_list
        ]
        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "query_string": "",
            "page_size": 5,
            "page_type": "scrolling",
            "start_time": 1745387225,
            "end_time": 1745390825,
            "resource_type": "pod",
            "page": 1,
            "bk_biz_id": 2,
        }
        mock_result = {
            "count": 2351,
            "items": [
                {
                    "pod": pod,
                    "namespace": namespace,
                    "workload": workload,
                }
                for pod, namespace, workload in mock_pod_list
            ],
        }
        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]

    def test_next_page_namespace_exclude_history(self):
        """
        查询下一页不带历史数据的 namespace 列表
        """
        mock_namespace_list = [
            "aiops-default",
            "apm-demo",
            "bcs-op",
            "bcs-system",
            "bk-bscp",
            "bk-system",
            "bkapp-agent-plugin-prod",
            "bkapp-bk-fw-demo-stag",
            "bkapp-bk-nodeman2-stag",
            "bkapp-bk-notice-prod",
        ]
        [create_namespace(name) for name in mock_namespace_list]
        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "query_string": "",
            "page_size": 5,
            "page_type": "scrolling",
            "start_time": 1745388702,
            "end_time": 1745392302,
            "resource_type": "namespace",
            "page": 2,
            "bk_biz_id": 2,
        }
        mock_result = {
            "count": 78,
            "items": [
                {"bk_biz_id": 2, "bcs_cluster_id": "BCS-K8S-00000", "namespace": namespace}
                for namespace in mock_namespace_list
            ],
        }
        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]

    def test_next_page_ingress_exclude_history(self):
        """
        查询下一页不带历史数据的 ingress 列表
        """
        mock_ingress_list = [
            ("bcs-ui", "bcs-system"),
            ("stack-bcs-api-gateway-http", "bcs-system"),
            ("bk-bscp-apiserver", "bk-bscp"),
            ("bk-bscp-ui", "bk-bscp"),
            ("agent-plugin-subpath", "bkapp-agent-plugin-prod"),
            ("bk-fw-demo-subpath", "bkapp-bk-fw-demo-stag"),
            ("bk-nodeman2-m-webserver-subpath", "bkapp-bk-nodeman2-stag"),
            ("bk-notice-subpath", "bkapp-bk-notice-prod"),
            ("custom-bk-notice-bknotice.bkop.woa.com-5", "bkapp-bk-notice-prod"),
            ("bk-notice-subpath", "bkapp-bk-notice-stag"),
        ]
        [create_ingress(name=name, namespace=namespace) for name, namespace in mock_ingress_list]
        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "query_string": "",
            "page_size": 5,
            "page_type": "scrolling",
            "start_time": 1745388807,
            "end_time": 1745392407,
            "resource_type": "ingress",
            "page": 2,
            "bk_biz_id": 2,
        }
        mock_result = {
            "count": 197,
            "items": [{"ingress": ingress, "namespace": namespace} for ingress, namespace in mock_ingress_list],
        }
        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]

    def test_next_page_service_exclude_history(self):
        """
        查询下一页不带历史数据的 service 列表
        """
        namespace = "aiops-default"
        mock_service_list = [f"service-{i}" for i in range(10)]
        [create_service(name=name, namespace=namespace) for name in mock_service_list]
        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "query_string": "",
            "page_size": 5,
            "page_type": "scrolling",
            "start_time": 1745388858,
            "end_time": 1745392458,
            "resource_type": "service",
            "page": 2,
            "bk_biz_id": 2,
        }
        mock_result = {
            "count": 598,
            "items": [{"service": service, "namespace": namespace} for service in mock_service_list],
        }
        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]

    def test_next_page_pod_exclude_history(self):
        """
        查询下一页不带历史数据的 pod 列表
        """
        mock_pod_list = [
            (
                "python-backend--0--session-default---experiment-clear-backbvcgm",
                "aiops-default",
                "Deployment:python-backend--0--session-default---experiment-clear-backend---owned",
            ),
            (
                "python-backend--0--session-default---scene-service-period-d2cn7",
                "aiops-default",
                "Deployment:python-backend--0--session-default---scene-service-period-close-outdated-version-session---owned",
            ),
            (
                "python-backend--0--session-default---scene-service-plan-prrnm9l",
                "aiops-default",
                "Deployment:python-backend--0--session-default---scene-service-plan-preview---owned",
            ),
            (
                "python-backend--0--session-default---serving-status---owne6585s",
                "aiops-default",
                "Deployment:python-backend--0--session-default---serving-status---owned",
            ),
            ("apm-demo-6df7f957c9-68gzc", "apm-demo", "Deployment:apm-demo"),
            (
                "bcs-api-gateway-migration-czpv7",
                "bcs-system",
                "Job:bcs-api-gateway-migration",
            ),
            (
                "bcs-bkcmdb-synchronizer-0",
                "bcs-system",
                "StatefulSet:bcs-bkcmdb-synchronizer",
            ),
            (
                "bcs-cluster-manager-5f889c4b55-56xdg",
                "bcs-system",
                "Deployment:bcs-cluster-manager",
            ),
            (
                "bcs-cluster-manager-migration-9g2j6",
                "bcs-system",
                "Job:bcs-cluster-manager-migration",
            ),
            (
                "bcs-cluster-resources-6b977c5b84-j2vxm",
                "bcs-system",
                "Deployment:bcs-cluster-resources",
            ),
        ]
        [
            create_pod(
                name=pod,
                namespace=namespace,
                workload_type=workload.split(":")[0],
                workload_name=workload.split(":")[1],
            )
            for pod, namespace, workload in mock_pod_list
        ]
        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "query_string": "",
            "page_size": 5,
            "page_type": "scrolling",
            "start_time": 1745388904,
            "end_time": 1745392504,
            "resource_type": "pod",
            "page": 2,
            "bk_biz_id": 2,
        }
        mock_result = {
            "count": 2354,
            "items": [
                {
                    "pod": pod,
                    "namespace": namespace,
                    "workload": workload,
                }
                for pod, namespace, workload in mock_pod_list
            ],
        }
        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]

    def test_namespace_with_query_string_exclude_history(self):
        """
        模糊查询不带历史数据的 namespace 列表
        """
        namespace_name = "bcs-op"
        create_namespace(name=namespace_name)
        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "query_string": namespace_name,
            "page_size": 5,
            "page_type": "scrolling",
            "start_time": 1745389011,
            "end_time": 1745392611,
            "resource_type": "namespace",
            "page": 1,
            "bk_biz_id": 2,
        }
        mock_result = {
            "count": 1,
            "items": [{"bk_biz_id": 2, "bcs_cluster_id": "BCS-K8S-00000", "namespace": namespace_name}],
        }
        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]

    def test_ingress_with_query_string_exclude_history(self):
        """
        模糊查询不带历史数据的 ingress 列表
        """
        create_ingress(name="bcs-ui", namespace="bcs-system")
        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "query_string": "bcs-ui",
            "page_size": 5,
            "page_type": "scrolling",
            "start_time": 1745389052,
            "end_time": 1745392652,
            "resource_type": "ingress",
            "page": 1,
            "bk_biz_id": 2,
        }
        mock_result = {"count": 1, "items": [{"ingress": "bcs-ui", "namespace": "bcs-system"}]}
        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]

    def test_service_with_query_string_exclude_history(self):
        """
        模糊查询不带历史数据的 service 列表
        """
        create_service(name="bcs-ui", namespace="bcs-system")
        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "query_string": "bcs-ui",
            "page_size": 5,
            "page_type": "scrolling",
            "start_time": 1745389052,
            "end_time": 1745392652,
            "resource_type": "service",
            "page": 1,
            "bk_biz_id": 2,
        }
        mock_result = {"count": 1, "items": [{"service": "bcs-ui", "namespace": "bcs-system"}]}
        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]

    def test_pod_with_query_string_exclude_history(self):
        """
        模糊查询不带历史数据的 pod 列表
        """
        create_pod(
            name="bcs-ui-687c796845-452tc", namespace="bcs-system", workload_type="Deployment", workload_name="bcs-ui"
        )
        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "query_string": "bcs-ui",
            "page_size": 5,
            "page_type": "scrolling",
            "start_time": 1745389052,
            "end_time": 1745392652,
            "resource_type": "pod",
            "page": 1,
            "bk_biz_id": 2,
        }
        mock_result = {
            "count": 1,
            "items": [{"pod": "bcs-ui-687c796845-452tc", "namespace": "bcs-system", "workload": "Deployment:bcs-ui"}],
        }
        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]

    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    def test_namespace_with_history(self, graph_unify_query):
        """
        查询带历史数据的 namespace 列表
        """
        mock_namespace_list = [
            "kube-system",
            "bkmonitor-operator",
            "bkmonitor-operator-bkte",
            "blueking",
            "bkbase",
            "bkbase-flink",
            "deepflow",
            "bcs-system",
            "bkapp-bk0us0itsm-prod",
            "bkapp-bk0us0sops-m-pipeline-prod",
        ]
        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "start_time": 1745391390,
            "end_time": 1745394990,
            "page_size": 10,
            "page": 1,
            "resource_type": "namespace",
            "with_history": True,
            "page_type": "scrolling",
            "column": "nw_container_network_receive_bytes_total",
            "order_by": "desc",
            "method": "sum",
            "bk_biz_id": 2,
        }
        mock_result = {
            "count": 79,
            "items": [
                {"bk_biz_id": 2, "bcs_cluster_id": "BCS-K8S-00000", "namespace": namespace}
                for namespace in mock_namespace_list
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
        mock_namespace_list = ["kube-system"]
        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {"namespace": ["kube-system"]},
            "start_time": 1745391428,
            "end_time": 1745395028,
            "page_size": 20,
            "page": 2,
            "resource_type": "namespace",
            "with_history": True,
            "page_type": "scrolling",
            "column": "nw_container_network_receive_bytes_total",
            "order_by": "desc",
            "method": "sum",
            "bk_biz_id": 2,
        }
        mock_result = {
            "count": 1,
            "items": [{"bk_biz_id": 2, "bcs_cluster_id": "BCS-K8S-00000", "namespace": "kube-system"}],
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
    def test_ingress_with_history(self, graph_unify_query):
        """
        查询带历史数据的 ingress 列表
        """
        mock_ingress_list = [
            ("bk-ingress-rule", "blueking"),
            ("bk-apigateway-apigateway", "blueking"),
            ("stack-bcs-api-gateway-http", "bcs-system"),
            ("bcs-ui", "bcs-system"),
            ("bkunifyquery-test", "blueking"),
            ("bk-dbm", "blueking"),
            ("default-bkapp-bk0us0itsm-prod--direct", "bkapp-bk0us0itsm-prod"),
            ("default-bkapp-bk0us0itsm-prod--subpath", "bkapp-bk0us0itsm-prod"),
            ("custom-itsm-bkop.woa.com", "bkapp-bk0us0itsm-prod"),
            ("default-bkapp-bk0us0itsm-prod", "bkapp-bk0us0itsm-prod"),
        ]
        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "start_time": 1745391264,
            "end_time": 1745394864,
            "page_size": 20,
            "page": 2,
            "resource_type": "ingress",
            "with_history": True,
            "page_type": "scrolling",
            "column": "nw_container_network_receive_bytes_total",
            "order_by": "desc",
            "method": "sum",
            "bk_biz_id": 2,
        }
        mock_result = {
            "count": 197,
            "items": [{"ingress": ingress, "namespace": namespace} for ingress, namespace in mock_ingress_list],
        }

        graph_unify_query.return_value = {
            "series": [
                {
                    "dimensions": {"ingress": ingress, "namespace": namespace},
                    "target": f"{{ingress={ingress}, namespace={namespace}}}",
                    "metric_field": "_result_",
                    "datapoints": [[265.1846, 1744874940000]],
                    "alias": "_result_",
                    "type": "line",
                    "dimensions_translation": {},
                    "unit": "",
                }
                for ingress, namespace in mock_ingress_list
            ],
            "metrics": [],
        }
        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]

    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    def test_ingress_with_history_and_filter(self, graph_unify_query):
        """
        查询带历史数据和过滤条件的 ingress 列表
        """
        namespace = "blueking"
        mock_ingress_list = [
            "bk-ingress-rule",
            "bk-apigateway-apigateway",
            "stack-bcs-api-gateway-http",
            "bcs-ui",
            "bkunifyquery-test",
            "bk-dbm",
            "default-bkapp-bk0us0itsm-prod--direct",
            "default-bkapp-bk0us0itsm-prod--subpath",
            "custom-itsm-bkop.woa.com",
            "default-bkapp-bk0us0itsm-prod",
        ]
        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {"namespace": [namespace]},
            "start_time": 1745391482,
            "end_time": 1745395082,
            "page_size": 20,
            "page": 2,
            "resource_type": "ingress",
            "with_history": True,
            "page_type": "scrolling",
            "column": "nw_container_network_receive_bytes_total",
            "order_by": "desc",
            "method": "sum",
            "bk_biz_id": 2,
        }
        mock_result = {
            "count": 197,
            "items": [{"ingress": ingress, "namespace": namespace} for ingress in mock_ingress_list],
        }

        {"count": 31, "items": [{"ingress": ingress, "namespace": namespace} for ingress in mock_ingress_list]}

        graph_unify_query.return_value = {
            "series": [
                {
                    "dimensions": {"ingress": ingress, "namespace": namespace},
                    "target": f"{{ingress={ingress}, namespace={namespace}}}",
                    "metric_field": "_result_",
                    "datapoints": [[265.1846, 1744874940000]],
                    "alias": "_result_",
                    "type": "line",
                    "dimensions_translation": {},
                    "unit": "",
                }
                for ingress in mock_ingress_list
            ],
            "metrics": [],
        }
        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]

    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    def test_service_with_history(self, graph_unify_query):
        """
        查询带历史数据的 service 列表
        """
        mock_service_list = [
            ("bkmonitor-operator-prometheus-node-exporter", "bkmonitor-operator"),
            ("bkmonitor-operator-bkmonit-kube-proxy", "kube-system"),
            ("bkmonitor-operator-stack-b-kube-proxy", "kube-system"),
            ("bk-gse-data", "blueking"),
            ("bk-gse-data-headless", "blueking"),
            ("bk-gse-file-headless", "blueking"),
            ("bk-gse-file", "blueking"),
            ("bk-monitor-transfer-http", "blueking"),
            ("bk-ingress-nginx", "blueking"),
            ("bkbase-clean-kafka-bkbase-metric-bcs1-service", "bkbase"),
        ]
        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "start_time": 1745391307,
            "end_time": 1745394907,
            "page_size": 20,
            "page": 2,
            "resource_type": "service",
            "with_history": True,
            "page_type": "scrolling",
            "column": "nw_container_network_receive_bytes_total",
            "order_by": "desc",
            "method": "sum",
            "bk_biz_id": 2,
        }
        mock_result = {
            "count": 608,
            "items": [{"service": service, "namespace": namespace} for service, namespace in mock_service_list],
        }
        graph_unify_query.return_value = {
            "series": [
                {
                    "dimensions": {"service": service, "namespace": namespace},
                    "target": f"{{service={service}, namespace={namespace}}}",
                    "metric_field": "_result_",
                    "datapoints": [[265.1846, 1744874940000]],
                    "alias": "_result_",
                    "type": "line",
                    "dimensions_translation": {},
                    "unit": "",
                }
                for service, namespace in mock_service_list
            ],
            "metrics": [],
        }
        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]

    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    def test_service_with_history_and_filter(self, graph_unify_query):
        """
        查询带历史数据和过滤条件的 service 列表
        """
        namespace = "blueking"
        mock_service_list = [
            "bk-gse-data-headless",
            "bk-gse-data",
            "bk-gse-file-headless",
            "bk-gse-file",
            "bk-monitor-transfer-http",
            "bk-ingress-nginx",
            "ingress-nginx-controller-metrics",
            "ingress-nginx-controller",
            "ingress-nginx-controller-admission",
            "bk-gse-cluster-headless",
        ]
        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {"namespace": [namespace]},
            "start_time": 1745391553,
            "end_time": 1745395153,
            "page_size": 20,
            "page": 2,
            "resource_type": "service",
            "with_history": True,
            "page_type": "scrolling",
            "column": "nw_container_network_receive_bytes_total",
            "order_by": "desc",
            "method": "sum",
            "bk_biz_id": 2,
        }

        mock_result = {
            "count": 598,
            "items": [
                {
                    "service": service,
                    "namespace": namespace,
                }
                for service in mock_service_list
            ],
        }

        graph_unify_query.return_value = {
            "series": [
                {
                    "dimensions": {"service": service, "namespace": namespace},
                    "target": f"{{service={service}, namespace={namespace}}}",
                    "metric_field": "_result_",
                    "datapoints": [[265.1846, 1744874940000]],
                    "alias": "_result_",
                    "type": "line",
                    "dimensions_translation": {},
                    "unit": "",
                }
                for service in mock_service_list
            ],
            "metrics": [],
        }

        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]

    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    def test_pod_with_with_history(self, graph_unify_query):
        """
        查询带历史数据的 pod 列表
        """
        mock_pod_list = [
            ("kube-flannel-ds-5rqbl", "kube-system"),
            ("kube-flannel-ds-kpcpv", "kube-system"),
            ("csi-cosplugin-xcr55", "kube-system"),
            ("csi-coslauncher-rf7zz", "kube-system"),
            ("bkm-daemonset-worker-sc4wm", "bkmonitor-operator-bkte"),
            ("kube-proxy-k2g6b", "kube-system"),
            ("bkm-prometheus-node-exporter-xgrp2", "bkmonitor-operator"),
            ("kube-proxy-4bnk7", "kube-system"),
            ("csi-cosplugin-pvxrt", "kube-system"),
            ("csi-cosplugin-5j5t4", "kube-system"),
        ]
        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "start_time": 1745391630,
            "end_time": 1745395230,
            "page_size": 20,
            "page": 2,
            "resource_type": "pod",
            "with_history": True,
            "page_type": "scrolling",
            "column": "nw_container_network_receive_bytes_total",
            "order_by": "desc",
            "method": "sum",
            "bk_biz_id": 2,
        }
        mock_result = {
            "count": 2377,
            "items": [{"pod": pod, "namespace": namespace} for pod, namespace in mock_pod_list],
        }
        graph_unify_query.return_value = {
            "series": [
                {
                    "dimensions": {"namespace": namespace, "pod": pod, "pod_name": pod},
                    "target": f"{{namespace={namespace}, pod_name={pod}, pod={pod}}}",
                    "metric_field": "_result_",
                    "datapoints": [[265.1846, 1744874940000]],
                    "alias": "_result_",
                    "type": "line",
                    "dimensions_translation": {},
                    "unit": "",
                }
                for pod, namespace in mock_pod_list
            ],
            "metrics": [],
        }
        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]

    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    def test_pod_with_history_and_filter(self, graph_unify_query):
        """
        查询带历史数据和过滤条件的 pod 列表
        """
        namespace = "blueking"
        mock_pod_list = [
            "bk-ingress-nginx-6bc4765cc4-xzswrbk-gse-data-6558cbfd9-gtg2r",
            "bk-gse-data-6558cbfd9-ph75g",
            "bk-gse-file-7b48cf45db-dwg25",
            "bk-gse-data-6558cbfd9-6bgdf",
            "ingress-nginx-controller-5f95bb657-64mcz",
            "bk-gse-cluster-5bf94b8d79-wcj7g",
            "bk-gse-data-6558cbfd9-4r44n",
            "bk-gse-data-6558cbfd9-2sz57",
            "bk-gse-data-6558cbfd9-qchs9",
        ]
        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {"namespace": [namespace]},
            "start_time": 1745391585,
            "end_time": 1745395185,
            "page_size": 20,
            "page": 2,
            "resource_type": "pod",
            "with_history": True,
            "page_type": "scrolling",
            "column": "nw_container_network_receive_bytes_total",
            "order_by": "desc",
            "method": "sum",
            "bk_biz_id": 2,
        }
        mock_result = {
            "count": 940,
            "items": [{"pod": pod, "namespace": namespace} for pod in mock_pod_list],
        }

        graph_unify_query.return_value = {
            "series": [
                {
                    "dimensions": {"namespace": namespace, "pod": pod, "pod_name": pod},
                    "target": f"{{namespace={namespace}, pod={pod}, pod_name={pod}}}",
                    "metric_field": "_result_",
                    "datapoints": [[265.1846, 1744874940000]],
                    "alias": "_result_",
                    "type": "line",
                    "dimensions_translation": {},
                    "unit": "",
                }
                for pod in mock_pod_list
            ],
            "metrics": [],
        }

        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]

    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    def test_namespace_with_history_1(self, graph_unify_query):
        """
        查询带历史数据的 namespace 列表

        覆盖promql 查询不足，还需要从db中补充的场景，以及需要进行去重操作
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
            "column": "nw_container_network_receive_bytes_total",
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
                for namespace in mock_namespace_list
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

        [create_namespace(name=namespace) for namespace in mock_namespace_list[4:]]

        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]
