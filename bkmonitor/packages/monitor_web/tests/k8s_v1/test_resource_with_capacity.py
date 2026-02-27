"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
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
from packages.monitor_web.k8s.scenario import Scenario

SCENARIO: Scenario = "capacity"

CAPACITY_COLUMNS = [
    "node_cpu_seconds_total",
    "node_cpu_capacity_ratio",
    "node_cpu_usage_ratio",
    "node_memory_working_set_bytes",
    "node_memory_capacity_ratio",
    "node_memory_usage_ratio",
]

# mock 掉 setup_filter 中的外部 API 调用，避免 DB/API 依赖
MOCK_SETUP_FILTER_DEPS = [
    mock.patch("monitor_web.k8s.core.meta.bk_biz_id_to_space_uid", return_value="bkcc__2"),
    mock.patch("monitor_web.k8s.core.meta.api.kubernetes.get_cluster_info_from_bcs_space", return_value={}),
]


def apply_setup_filter_mocks(func):
    """装饰器: 批量应用 setup_filter 相关 mock"""
    for p in reversed(MOCK_SETUP_FILTER_DEPS):
        func = p(func)
    return func


# ==================== ResourceTrendResource 测试 ====================


class TestResourceTrendResourceWithCapacity:
    """测试 capacity 场景下 ResourceTrendResource 的各个 resource_type"""

    @pytest.mark.parametrize(["column"], [pytest.param(c) for c in CAPACITY_COLUMNS])
    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    @apply_setup_filter_mocks
    def test_with_node(
        self,
        mock_space_uid,
        mock_cluster_info,
        graph_unify_query,
        column,
        get_start_time,
        get_end_time,
    ):
        """测试节点级别的容量指标趋势"""
        name = "master-127-0-0-1"

        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "start_time": get_start_time,
            "end_time": get_end_time,
            "column": column,
            "method": "sum",
            "resource_type": "node",
            "resource_list": [name],
            "bk_biz_id": 2,
        }

        metric = GetScenarioMetric()(metric_id=column, scenario=SCENARIO, bk_biz_id=2)
        mock_expected_result = [
            {
                column: {
                    "datapoints": [[265.1846, 1744874940000]],
                    "unit": metric["unit"],
                    "value_title": metric["name"],
                },
                "resource_name": name,
            },
        ]

        graph_unify_query.return_value = {
            "series": [
                {
                    "dimensions": {"node": name},
                    "target": f"{{node={name}}}",
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

    @pytest.mark.parametrize(["column"], [pytest.param(c) for c in CAPACITY_COLUMNS])
    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    @apply_setup_filter_mocks
    def test_with_cluster(
        self,
        mock_space_uid,
        mock_cluster_info,
        graph_unify_query,
        column,
        get_start_time,
        get_end_time,
    ):
        """测试集群级别的容量指标趋势"""
        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "start_time": get_start_time,
            "end_time": get_end_time,
            "column": column,
            "method": "sum",
            "resource_type": "cluster",
            "resource_list": ["BCS-K8S-00000"],
            "bk_biz_id": 2,
        }

        metric = GetScenarioMetric()(metric_id=column, scenario=SCENARIO, bk_biz_id=2)
        mock_expected_result = [
            {
                column: {
                    "datapoints": [[265.1846, 1744874940000]],
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

    @apply_setup_filter_mocks
    def test_with_no_resource_list(
        self,
        mock_space_uid,
        mock_cluster_info,
        get_start_time,
        get_end_time,
    ):
        """测试空 resource_list 边界情况（应返回空列表）"""
        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "start_time": get_start_time,
            "end_time": get_end_time,
            "column": "node_cpu_seconds_total",
            "method": "sum",
            "resource_type": "node",
            "resource_list": [],
            "bk_biz_id": 2,
        }
        result = ResourceTrendResource()(validated_request_data)
        assert result == []


# ==================== ListK8SResources 测试 ====================


class TestListK8SResourcesWithCapacity:
    """测试 capacity 场景下 ListK8SResources 的各个 resource_type 和查询维度"""

    # ---------- Node ----------

    @mock.patch("monitor_web.k8s.core.meta.K8sNodeMeta.distinct")
    @mock.patch("monitor_web.k8s.core.meta.K8sNodeMeta.get_from_meta")
    @apply_setup_filter_mocks
    def test_node_exclude_history(
        self,
        mock_space_uid,
        mock_cluster_info,
        mock_get_from_meta,
        mock_distinct,
    ):
        """查询不带历史数据的节点列表"""
        from bkmonitor.models import BCSNode

        mock_node_names = [f"master-{i}" for i in range(5)]
        mock_node_objects = []
        for name in mock_node_names:
            node = BCSNode()
            node.name = name
            node.bk_biz_id = 2
            node.bcs_cluster_id = "BCS-K8S-00000"
            mock_node_objects.append(node)

        mock_distinct.return_value = mock_node_objects

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
        expected_items = [{"node": name} for name in mock_node_names]
        result = ListK8SResources()(validated_request_data)
        assert result["items"] == expected_items

    @mock.patch("monitor_web.k8s.core.meta.K8sNodeMeta.distinct")
    @mock.patch("monitor_web.k8s.core.meta.K8sNodeMeta.get_from_meta")
    @apply_setup_filter_mocks
    def test_node_with_query_string_exclude_history(
        self,
        mock_space_uid,
        mock_cluster_info,
        mock_get_from_meta,
        mock_distinct,
    ):
        """模糊查询不带历史数据的节点列表"""
        from bkmonitor.models import BCSNode

        node = BCSNode()
        node.name = "master-127-0-0-1"
        node.bk_biz_id = 2
        node.bcs_cluster_id = "BCS-K8S-00000"

        mock_distinct.return_value = [node]

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
        expected_items = [{"node": "master-127-0-0-1"}]
        result = ListK8SResources()(validated_request_data)
        assert result["items"] == expected_items

    @mock.patch("monitor_web.k8s.core.meta.K8sNodeMeta.distinct")
    @mock.patch("monitor_web.k8s.core.meta.K8sNodeMeta.get_from_meta")
    @apply_setup_filter_mocks
    def test_next_page_node_exclude_history(
        self,
        mock_space_uid,
        mock_cluster_info,
        mock_get_from_meta,
        mock_distinct,
    ):
        """查询下一页不带历史数据的节点列表"""
        from bkmonitor.models import BCSNode

        mock_node_names = [f"master-{i}" for i in range(10)]
        mock_node_objects = []
        for name in mock_node_names:
            node = BCSNode()
            node.name = name
            node.bk_biz_id = 2
            node.bcs_cluster_id = "BCS-K8S-00000"
            mock_node_objects.append(node)

        mock_distinct.return_value = mock_node_objects

        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "query_string": "",
            "page_size": 5,
            "page_type": "scrolling",
            "start_time": 1745199913,
            "end_time": 1745203513,
            "resource_type": "node",
            "page": 2,
            "bk_biz_id": 2,
        }
        expected_items = [{"node": name} for name in mock_node_names]
        result = ListK8SResources()(validated_request_data)
        assert result["items"] == expected_items

    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    @mock.patch("monitor_web.k8s.core.meta.K8sResourceMeta.get_from_meta", return_value=[])
    @apply_setup_filter_mocks
    def test_node_with_history(
        self,
        mock_space_uid,
        mock_cluster_info,
        mock_get_from_meta,
        graph_unify_query,
        get_end_time,
    ):
        """查询带历史数据的节点列表

        容量场景只有 node 资源，
        所以 column 的值意义不大，后端通过 node_boot_time_seconds 获取 node 列表
        """
        mock_node_list = [f"master-{i}" for i in range(5)]

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
            "column": "container_cpu_usage_seconds_total",
            "order_by": "desc",
            "method": "sum",
            "bk_biz_id": 2,
        }

        expected_items = [{"node": name} for name in mock_node_list]

        graph_unify_query.return_value = {
            "series": [
                {
                    "dimensions": {"node": node},
                    "target": f"{{node={node}}}",
                    "metric_field": "_result_",
                    "datapoints": [[265.1846, 1744874940000]],
                    "alias": "_result_",
                    "type": "line",
                    "dimensions_translation": {},
                    "unit": "",
                }
                for node in mock_node_list
            ],
            "metrics": [],
        }

        result = ListK8SResources()(validated_request_data)
        assert result["items"] == expected_items

    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    @mock.patch("monitor_web.k8s.core.meta.K8sResourceMeta.get_from_meta", return_value=[])
    @apply_setup_filter_mocks
    def test_node_with_history_and_filter(
        self,
        mock_space_uid,
        mock_cluster_info,
        mock_get_from_meta,
        graph_unify_query,
    ):
        """查询带历史数据和过滤条件的节点列表"""
        node_name = "master-127-0-0-1"

        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {"node": [node_name]},
            "start_time": 1745315249,
            "end_time": 1745318849,
            "page_size": 20,
            "page": 1,
            "resource_type": "node",
            "with_history": True,
            "page_type": "scrolling",
            "column": "container_memory_working_set_bytes",
            "order_by": "desc",
            "method": "sum",
            "bk_biz_id": 2,
        }

        expected_items = [{"node": node_name}]

        graph_unify_query.return_value = {
            "series": [
                {
                    "dimensions": {"node": node_name},
                    "target": f"{{node={node_name}}}",
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
        assert result["items"] == expected_items

    # ---------- Cluster ----------

    @mock.patch("monitor_web.k8s.core.meta.K8sClusterMeta.distinct")
    @mock.patch("monitor_web.k8s.core.meta.K8sClusterMeta.get_from_meta")
    @apply_setup_filter_mocks
    def test_cluster_exclude_history(
        self,
        mock_space_uid,
        mock_cluster_info,
        mock_get_from_meta,
        mock_distinct,
    ):
        """查询不带历史数据的集群列表"""
        from bkmonitor.models import BCSCluster

        mock_cluster = BCSCluster()
        mock_cluster.bcs_cluster_id = "BCS-K8S-00000"
        mock_cluster.bk_biz_id = 2

        mock_distinct.return_value = [mock_cluster]

        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "query_string": "",
            "page_size": 10,
            "page_type": "scrolling",
            "start_time": 1744957564,
            "end_time": 1744961164,
            "resource_type": "cluster",
            "page": 1,
            "bk_biz_id": 2,
        }
        expected_items = [{"cluster": "BCS-K8S-00000"}]
        result = ListK8SResources()(validated_request_data)
        assert result["items"] == expected_items

    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    @mock.patch("monitor_web.k8s.core.meta.K8sResourceMeta.get_from_meta", return_value=[])
    @apply_setup_filter_mocks
    def test_cluster_with_history(
        self,
        mock_space_uid,
        mock_cluster_info,
        mock_get_from_meta,
        graph_unify_query,
        get_end_time,
    ):
        """查询带历史数据的集群列表（单业务单集群，只会有一个）"""
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
            "column": "container_cpu_usage_seconds_total",
            "order_by": "desc",
            "method": "sum",
            "bk_biz_id": 2,
        }

        expected_items = [{"cluster": "BCS-K8S-00000"}]

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
        assert result["items"] == expected_items
