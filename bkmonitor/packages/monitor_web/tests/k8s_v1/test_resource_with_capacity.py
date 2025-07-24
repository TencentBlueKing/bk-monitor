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
from monitor_web.tests.k8s_v1.conftest import create_node
from packages.monitor_web.k8s.scenario import Scenario

SCENARIO: Scenario = "capacity"


@pytest.mark.django_db
class TestResourceTrendResourceWithCapacity:
    @pytest.mark.parametrize(
        ["column"],
        [
            pytest.param("node_cpu_seconds_total"),
        ],
    )
    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    def test_with_node(
        self,
        graph_unify_query,
        column,
        get_start_time,
        get_end_time,
    ):
        """
        PromQL 示例
        ```PromQL
        sum by (node) (
          last_over_time(
            rate(
              node_cpu_seconds_total{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD",mode!="idle",node="master-127-0-0-1"}[1m]
            )[1m:]
          )
        )
        ```
        """
        name = "master-127-0-0-1"
        resource_type = "node"
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
                    "dimensions": {"node": "master-127-0-0-1"},
                    "target": "{node=master-127-0-0-1}",
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
            pytest.param("node_cpu_seconds_total"),
        ],
    )
    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    def test_with_cluster(
        self,
        graph_unify_query,
        column,
        get_start_time,
        get_end_time,
    ):
        """
        PromQL示例:
        ```PromQL
        topk(
          40,
          sum by (bcs_cluster_id) (
            last_over_time(
              node_boot_time_seconds{bcs_cluster_id="BCS-K8S-00000",bk_biz_id="2",container_name!="POD"}[1m:]
            )
          )
        )
        ```
        """
        resource_type = "cluster"
        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "start_time": get_start_time,
            "end_time": get_end_time,
            "column": column,
            "method": "sum",
            "resource_type": resource_type,
            "resource_list": ["BCS-K8S-00000"],
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
                "resource_name": "BCS-K8S-00000",
            },
        ]

        graph_unify_query.return_value = {
            "series": [
                {
                    "dimensions": {"bcs_cluster_id": "BCS-K8S-00000"},
                    "target": "{bcs_cluster_id=BCS-K8S-00000}",
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
class TestListK8SResourcesWithCapacity:
    def test_node_exclude_history(self):
        """
        查询不带历史数据的 node 列表
        """

        mock_node_names = [f"master-{i}" for i in range(5)]
        [create_node(name) for name in mock_node_names]
        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "query_string": "",
            "page_size": 5,
            "page_type": "scrolling",
            "start_time": 1744957564,
            "end_time": 1744961164,
            "resource_type": "node",
            "page": 1,
            "bk_biz_id": 2,
        }
        mock_result = {
            "count": 90,
            "items": [{"node": name, "ip": name} for name in mock_node_names],
        }
        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]

    def test_node_with_query_string_exclude_history(self):
        """
        模糊查询不带历史数据的 node 列表
        """
        name = "master-127-0-0-1"
        create_node(name)

        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "query_string": "master-127-0-0-1",
            "page_size": 5,
            "page_type": "scrolling",
            "start_time": 1745200006,
            "end_time": 1745203606,
            "resource_type": "node",
            "page": 1,
            "bk_biz_id": 2,
        }
        mock_result = {
            "count": 1,
            "items": [{"node": name, "ip": name}],
        }
        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]

    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    def test_node_with_history(self, graph_unify_query, get_end_time):
        """
        查询带历史数据的 node 列表

        容量场景只有 node 资源
        所以 column 的值意义不大，后端通过 node_boot_time_seconds 获取 node 列表
        """
        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "start_time": 1745283797,
            "end_time": get_end_time,
            "page_size": 10,
            "page": 1,
            "resource_type": "node",
            "with_history": True,
            "page_type": "scrolling",
            "column": "container_cpu_usage_seconds_total",  # 不关心该值
            "order_by": "desc",
            "method": "sum",
            "bk_biz_id": 2,
        }
        mock_node_list = [f"master-{i}" for i in range(10)]
        mock_result = {
            "count": 90,
            "items": [{"node": name, "ip": name} for name in mock_node_list],
        }

        graph_unify_query.return_value = {
            "series": [
                {
                    "dimensions": {
                        "node": node,
                        "ip": node,
                    },
                    "target": f"{{node={node}, ip={node}}}",
                    "metric_field": "_result_",
                    "datapoints": [[265.1846, 1744874940000]],
                    "alias": "_result_",
                    "type": "line",
                    "dimensions_translation": {},
                    "unit": "",
                }
                for node in mock_node_list[:5]
            ],
            "metrics": [],
        }
        [create_node(name) for name in mock_node_list[4:]]

        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]

    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    def test_node_with_history_and_filter(self, graph_unify_query):
        """
        查询带历史数据和过滤条件的 node 列表

        """
        node_name = "master-127-0-0-1"
        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {"node": [node_name]},
            "start_time": 1745315249,
            "end_time": 1745318849,
            "page_size": 20,
            "page": 2,
            "resource_type": "node",
            "with_history": True,
            "page_type": "scrolling",
            "column": "container_memory_working_set_bytes",
            "order_by": "desc",
            "method": "sum",
            "bk_biz_id": 2,
        }
        mock_result = {
            "count": 1,
            "items": [{"node": node_name, "ip": node_name}],
        }

        graph_unify_query.return_value = {
            "series": [
                {
                    "dimensions": {
                        "node": node_name,
                        "ip": node_name,
                    },
                    "target": f"{{node={node_name}, ip={node_name}}}",
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
        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]

    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    def test_cluster_with_history(self, graph_unify_query, get_end_time, create_bcs_cluster):
        """
        查询带历史数据的 cluster 列表

        因为是单业务单集群，所以只会有一个 cluster
        """
        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "start_time": 1745283797,
            "end_time": get_end_time,
            "page_size": 10,
            "page": 1,
            "resource_type": "cluster",
            "with_history": True,
            "page_type": "scrolling",
            "column": "container_cpu_usage_seconds_total",  # 不关心该值
            "order_by": "desc",
            "method": "sum",
            "bk_biz_id": 2,
        }
        mock_result = {"count": 1, "items": [{"cluster": "BCS-K8S-00000"}]}

        graph_unify_query.return_value = {
            "series": [
                {
                    "dimensions": {"bcs_cluster_id": "BCS-K8S-00000"},
                    "target": "{bcs_cluster_id=BCS-K8S-00000}",
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

        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]
