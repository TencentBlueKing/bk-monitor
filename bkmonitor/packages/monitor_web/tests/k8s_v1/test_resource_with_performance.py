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
    ResourceTrendResource,
    WorkloadOverview,
)
from monitor_web.tests.k8s_v1.conftest import create_namespace
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
