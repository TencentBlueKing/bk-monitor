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
import pytest  # noqa

from monitor_web.k8s.resources import (
    GetScenarioMetric,
    ListK8SResources,
    ResourceTrendResource,
)
from monitor_web.tests.k8s_v1.conftest import (
    create_container,
    create_ingress,
    create_namespace,
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
            pytest.param("nw_container_network_transmit_bytes_total"),
            pytest.param("nw_container_network_receive_packets_total"),
            pytest.param("nw_container_network_transmit_packets_total"),
            pytest.param("nw_container_network_receive_errors_total"),
            pytest.param("nw_container_network_transmit_errors_total"),
            pytest.param("nw_container_network_receive_errors_ratio"),
            pytest.param("nw_container_network_transmit_errors_ratio"),
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
        PromQL: 'sum by (namespace) (sum by (namespace, pod)(last_over_time(rate(container_network_receive_bytes_total{namespace="aiops"}[1m])[1m:])))'  # noqa
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
            pytest.param("nw_container_network_transmit_bytes_total"),
            pytest.param("nw_container_network_receive_packets_total"),
            pytest.param("nw_container_network_transmit_packets_total"),
            pytest.param("nw_container_network_receive_errors_total"),
            pytest.param("nw_container_network_transmit_errors_total"),
            pytest.param("nw_container_network_receive_errors_ratio"),
            pytest.param("nw_container_network_transmit_errors_ratio"),
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
        PromQL: 'sum by (ingress, namespace) ((count by (bk_biz_id, bcs_cluster_id, namespace, ingress, service, pod) (ingress_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",ingress="bk-dbm"}) * 0 + 1) * on (namespace, service) group_left(pod) (count by (service, namespace, pod) (pod_with_service_relation)) * on (namespace, pod) group_left() sum by (namespace, pod) (last_over_time(rate(container_network_receive_bytes_total{}[1m])[1m:])))'  # noqa
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
            pytest.param("nw_container_network_transmit_bytes_total"),
            pytest.param("nw_container_network_receive_packets_total"),
            pytest.param("nw_container_network_transmit_packets_total"),
            pytest.param("nw_container_network_receive_errors_total"),
            pytest.param("nw_container_network_transmit_errors_total"),
            pytest.param("nw_container_network_receive_errors_ratio"),
            pytest.param("nw_container_network_transmit_errors_ratio"),
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
        PromQL: 'sum by (namespace, service) ((count by (service, namespace, pod) (pod_with_service_relation{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",service="bk-gse-data"}) * 0 + 1) * on (namespace, pod) group_left() sum by (namespace, pod) (last_over_time(rate(container_network_receive_bytes_total{}[1m])[1m:])))'  # noqa
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
            pytest.param("nw_container_network_transmit_bytes_total"),
            pytest.param("nw_container_network_receive_packets_total"),
            pytest.param("nw_container_network_transmit_packets_total"),
            pytest.param("nw_container_network_receive_errors_total"),
            pytest.param("nw_container_network_transmit_errors_total"),
            pytest.param("nw_container_network_receive_errors_ratio"),
            pytest.param("nw_container_network_transmit_errors_ratio"),
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
        PromQL: 'label_replace(sum by (namespace, pod) (sum by (namespace, pod) (last_over_time(rate(container_network_receive_bytes_total{pod_name="kube-flannel-ds-kpcpv"}[1m])[1m:]))), "pod_name", "$1", "pod", "(.*)")'  # noqa
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
    def test_left_default_namespace(self):
        """获取左侧默认namespace列表"""
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
        result = ListK8SResources()(validated_request_data)  # noqa
        assert result["items"] == mock_result["items"]

    def test_right_ingress_with_filter(self):
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
            "start_time": 1745284082,
            "end_time": 1745287682,
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

    def test_right_service_with_filter(self):
        mock_service_list = [
            (
                "service-0238ac93f359ac407d5ceccc599655b4",
                "aiops-default",
            ),
            (
                "service-0238d26ae5c36675c65f07fea9f32273",
                "aiops-default",
            ),
            (
                "service-029f77b8bb2517480e2a2377a66c3670",
                "aiops-default",
            ),
            (
                "service-07efbaabe7ea713a9ebc7a222b24084d",
                "aiops-default",
            ),
            (
                "service-0852a0955d7531c0eb0df994303037bf",
                "aiops-default",
            ),
        ]
        [create_service(name, namespace) for name, namespace in mock_service_list]
        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "query_string": "",
            "page_size": 5,
            "page_type": "scrolling",
            "start_time": 1745284082,
            "end_time": 1745287682,
            "resource_type": "service",
            "page": 1,
            "bk_biz_id": 2,
        }

        mock_result = {
            "count": 598,
            "items": [
                {
                    "service": service,
                    "namespace": namespace,
                }
                for service, namespace in mock_service_list
            ],
        }
        result = ListK8SResources()(validated_request_data)
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
        resutlt = ListK8SResources()(validated_request_data)  # noqa
        assert mock_result["items"] == resutlt["items"]
