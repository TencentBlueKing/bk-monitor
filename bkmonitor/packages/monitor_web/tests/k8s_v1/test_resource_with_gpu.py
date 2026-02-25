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

SCENARIO: Scenario = "tke_gpu"

GPU_COLUMNS = [
    "container_gpu_utilization",
    "container_gpu_memory_total",
    "container_core_utilization_percentage",
    "container_mem_utilization_percentage",
    "container_request_gpu_memory",
    "container_request_gpu_utilization",
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


class TestResourceTrendResourceWithGPU:
    """测试 GPU 场景下 ResourceTrendResource 的各个 resource_type"""

    @pytest.mark.parametrize(["column"], [pytest.param(c) for c in GPU_COLUMNS])
    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    @apply_setup_filter_mocks
    def test_with_namespace(
        self,
        mock_space_uid,
        mock_cluster_info,
        graph_unify_query,
        column,
        get_start_time,
        get_end_time,
    ):
        """测试命名空间级别的 GPU 指标趋势"""
        name = "gpu-namespace"

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

        metric = GetScenarioMetric()(metric_id=column, scenario=SCENARIO, bk_biz_id=2)
        mock_expected_result = [
            {
                column: {
                    "datapoints": [[85.5, 1744874940000]],
                    "unit": metric["unit"],
                    "value_title": metric["name"],
                },
                "resource_name": name,
            },
        ]

        graph_unify_query.return_value = {
            "series": [
                {
                    "dimensions": {"namespace": name},
                    "target": f"{{namespace={name}}}",
                    "metric_field": "_result_",
                    "datapoints": [[85.5, 1744874940000]],
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

    @pytest.mark.parametrize(["column"], [pytest.param(c) for c in GPU_COLUMNS])
    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    @apply_setup_filter_mocks
    def test_with_workload(
        self,
        mock_space_uid,
        mock_cluster_info,
        graph_unify_query,
        column,
        get_start_time,
        get_end_time,
    ):
        """测试工作负载级别的 GPU 指标趋势"""
        name = "gpu-namespace|Deployment:gpu-training-job"

        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "start_time": get_start_time,
            "end_time": get_end_time,
            "column": column,
            "method": "sum",
            "resource_type": "workload",
            "resource_list": [name],
            "bk_biz_id": 2,
        }

        metric = GetScenarioMetric()(metric_id=column, scenario=SCENARIO, bk_biz_id=2)
        mock_expected_result = [
            {
                column: {
                    "datapoints": [[72.3, 1744874940000]],
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
                        "namespace": "gpu-namespace",
                        "workload_kind": "Deployment",
                        "workload_name": "gpu-training-job",
                    },
                    "target": """{
                        namespace=gpu-namespace,
                        workload_kind=Deployment,
                        workload_name=gpu-training-job
                    }""",
                    "metric_field": "_result_",
                    "datapoints": [[72.3, 1744874940000]],
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

    @pytest.mark.parametrize(["column"], [pytest.param(c) for c in GPU_COLUMNS])
    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    @apply_setup_filter_mocks
    def test_with_pod(
        self,
        mock_space_uid,
        mock_cluster_info,
        graph_unify_query,
        column,
        get_start_time,
        get_end_time,
    ):
        """测试 Pod 级别的 GPU 指标趋势"""
        name = "gpu-training-pod-abc123"

        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {"pod": [name]},
            "start_time": get_start_time,
            "end_time": get_end_time,
            "column": column,
            "method": "sum",
            "resource_type": "pod",
            "resource_list": [name],
            "bk_biz_id": 2,
        }

        metric = GetScenarioMetric()(metric_id=column, scenario=SCENARIO, bk_biz_id=2)
        mock_expected_result = [
            {
                column: {
                    "datapoints": [[90.2, 1744874940000]],
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
                        "pod_name": name,
                        "namespace": "gpu-namespace",
                        "workload_kind": "Deployment",
                        "workload_name": "gpu-training-job",
                    },
                    "target": f"""{{
                        pod_name={name},
                        namespace=gpu-namespace,
                        workload_kind=Deployment,
                        workload_name=gpu-training-job
                    }}""",
                    "metric_field": "_result_",
                    "datapoints": [[90.2, 1744874940000]],
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

    @pytest.mark.parametrize(["column"], [pytest.param(c) for c in GPU_COLUMNS])
    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    @apply_setup_filter_mocks
    def test_with_container(
        self,
        mock_space_uid,
        mock_cluster_info,
        graph_unify_query,
        column,
        get_start_time,
        get_end_time,
    ):
        """测试容器级别的 GPU 指标趋势"""
        container_name = "gpu-container"
        pod_name = "gpu-pod-abc123"

        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "start_time": get_start_time,
            "end_time": get_end_time,
            "column": column,
            "method": "sum",
            "resource_type": "container",
            "resource_list": [container_name],
            "bk_biz_id": 2,
        }

        metric = GetScenarioMetric()(metric_id=column, scenario=SCENARIO, bk_biz_id=2)
        # resource_name 格式: "{pod_name}:{container_name}" (由 K8sContainerMeta.resource_field_list 决定)
        resource_name = f"{pod_name}:{container_name}"
        mock_expected_result = [
            {
                column: {
                    "datapoints": [[85.5, 1744874940000]],
                    "unit": metric["unit"],
                    "value_title": metric["name"],
                },
                "resource_name": resource_name,
            },
        ]

        graph_unify_query.return_value = {
            "series": [
                {
                    "dimensions": {
                        "container_name": container_name,
                        "pod_name": pod_name,
                        "namespace": "blueking",
                        "workload_kind": "Deployment",
                        "workload_name": "gpu-workload",
                    },
                    "target": f"{{container_name={container_name},pod_name={pod_name}}}",
                    "metric_field": "_result_",
                    "datapoints": [[85.5, 1744874940000]],
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

    @pytest.mark.parametrize(["column"], [pytest.param(c) for c in GPU_COLUMNS])
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
        """测试集群级别的 GPU 指标趋势"""
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
                    "datapoints": [[95.0, 1744874940000]],
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
                    "datapoints": [[95.0, 1744874940000]],
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

    @pytest.mark.parametrize(["column"], [pytest.param(c) for c in GPU_COLUMNS])
    @apply_setup_filter_mocks
    def test_with_no_resource_list(
        self,
        mock_space_uid,
        mock_cluster_info,
        column,
        get_start_time,
        get_end_time,
    ):
        """测试空 resource_list 边界情况（应返回空列表）"""
        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {"container": ["gpu-container"]},
            "start_time": get_start_time,
            "end_time": get_end_time,
            "column": column,
            "method": "sum",
            "resource_type": "container",
            "resource_list": [],
            "bk_biz_id": 2,
        }
        result = ResourceTrendResource()(validated_request_data)
        assert result == []


# ==================== ListK8SResources 测试 ====================


class TestListK8SResourcesWithGPU:
    """测试 GPU 场景下 ListK8SResources 的各个 resource_type 和查询维度"""

    # ---------- Namespace ----------

    @mock.patch("monitor_web.k8s.core.meta.K8sNamespaceMeta.distinct")
    @mock.patch("monitor_web.k8s.core.meta.K8sNamespaceMeta.get_from_meta")
    @apply_setup_filter_mocks
    def test_namespace_exclude_history(
        self,
        mock_space_uid,
        mock_cluster_info,
        mock_get_from_meta,
        mock_distinct,
    ):
        """查询不带历史数据的 GPU 命名空间列表"""
        mock_namespace_names = [
            "gpu-training",
            "gpu-inference",
            "gpu-monitoring",
            "gpu-batch",
            "gpu-dev",
        ]
        mock_distinct.return_value = [
            {"bk_biz_id": 2, "bcs_cluster_id": "BCS-K8S-00000", "namespace": name} for name in mock_namespace_names
        ]

        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "query_string": "",
            "page_size": 10,
            "page_type": "scrolling",
            "start_time": 1744957564,
            "end_time": 1744961164,
            "resource_type": "namespace",
            "page": 1,
            "bk_biz_id": 2,
        }
        expected_items = [
            {"bk_biz_id": 2, "bcs_cluster_id": "BCS-K8S-00000", "namespace": name} for name in mock_namespace_names
        ]
        result = ListK8SResources()(validated_request_data)
        assert result["items"] == expected_items

    @mock.patch("monitor_web.k8s.core.meta.K8sNamespaceMeta.distinct")
    @mock.patch("monitor_web.k8s.core.meta.K8sNamespaceMeta.get_from_meta")
    @apply_setup_filter_mocks
    def test_namespace_with_query_string_exclude_history(
        self,
        mock_space_uid,
        mock_cluster_info,
        mock_get_from_meta,
        mock_distinct,
    ):
        """模糊查询不带历史数据的 GPU 命名空间列表"""
        mock_distinct.return_value = [
            {"bk_biz_id": 2, "bcs_cluster_id": "BCS-K8S-00000", "namespace": "gpu-training"},
        ]

        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "query_string": "training",
            "page_size": 10,
            "page_type": "scrolling",
            "start_time": 1745200006,
            "end_time": 1745203606,
            "resource_type": "namespace",
            "page": 1,
            "bk_biz_id": 2,
        }
        expected_items = [
            {"bk_biz_id": 2, "bcs_cluster_id": "BCS-K8S-00000", "namespace": "gpu-training"},
        ]
        result = ListK8SResources()(validated_request_data)
        assert result["items"] == expected_items

    @mock.patch("monitor_web.k8s.core.meta.K8sNamespaceMeta.distinct")
    @mock.patch("monitor_web.k8s.core.meta.K8sNamespaceMeta.get_from_meta")
    @apply_setup_filter_mocks
    def test_next_page_namespace_exclude_history(
        self,
        mock_space_uid,
        mock_cluster_info,
        mock_get_from_meta,
        mock_distinct,
    ):
        """查询下一页不带历史数据的 GPU 命名空间列表"""
        mock_namespace_names = [
            "gpu-training",
            "gpu-inference",
            "gpu-monitoring",
            "gpu-batch",
            "gpu-dev",
            "gpu-staging",
            "gpu-prod",
            "gpu-testing",
            "gpu-research",
            "gpu-experiment",
        ]
        mock_distinct.return_value = [
            {"bk_biz_id": 2, "bcs_cluster_id": "BCS-K8S-00000", "namespace": name} for name in mock_namespace_names
        ]

        validated_request_data = {
            "scenario": SCENARIO,
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
        expected_items = [
            {"bk_biz_id": 2, "bcs_cluster_id": "BCS-K8S-00000", "namespace": name} for name in mock_namespace_names
        ]
        result = ListK8SResources()(validated_request_data)
        assert result["items"] == expected_items

    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    @mock.patch("monitor_web.k8s.core.meta.K8sNamespaceMeta.get_from_meta", return_value=[])
    @apply_setup_filter_mocks
    def test_namespace_with_history(
        self,
        mock_space_uid,
        mock_cluster_info,
        mock_get_from_meta,
        graph_unify_query,
        get_end_time,
    ):
        """查询带历史数据的 GPU 命名空间列表"""
        mock_namespace_list = [
            "gpu-training",
            "gpu-inference",
            "gpu-monitoring",
            "gpu-batch",
            "gpu-dev",
        ]

        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "start_time": 1745283797,
            "end_time": get_end_time,
            "page_size": 10,
            "page": 1,
            "resource_type": "namespace",
            "with_history": True,
            "page_type": "scrolling",
            "column": "container_gpu_utilization",
            "order_by": "desc",
            "method": "sum",
            "bk_biz_id": 2,
        }

        expected_items = [
            {"bk_biz_id": 2, "bcs_cluster_id": "BCS-K8S-00000", "namespace": namespace}
            for namespace in mock_namespace_list
        ]

        graph_unify_query.return_value = {
            "series": [
                {
                    "dimensions": {"namespace": namespace},
                    "target": f"{{namespace={namespace}}}",
                    "metric_field": "_result_",
                    "datapoints": [[85.5, 1744874940000]],
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
        assert result["items"] == expected_items

    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    @mock.patch("monitor_web.k8s.core.meta.K8sNamespaceMeta.get_from_meta", return_value=[])
    @apply_setup_filter_mocks
    def test_namespace_with_history_and_filter(
        self,
        mock_space_uid,
        mock_cluster_info,
        mock_get_from_meta,
        graph_unify_query,
    ):
        """查询带历史数据和过滤条件的 GPU 命名空间列表"""
        namespace = "gpu-training"

        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {"namespace": [namespace]},
            "start_time": 1745315249,
            "end_time": 1745318849,
            "page_size": 20,
            "page": 1,
            "resource_type": "namespace",
            "with_history": True,
            "page_type": "scrolling",
            "column": "container_gpu_memory_total",
            "order_by": "desc",
            "method": "sum",
            "bk_biz_id": 2,
        }

        expected_items = [{"bk_biz_id": 2, "bcs_cluster_id": "BCS-K8S-00000", "namespace": namespace}]

        graph_unify_query.return_value = {
            "series": [
                {
                    "dimensions": {"namespace": namespace},
                    "target": f"{{namespace={namespace}}}",
                    "metric_field": "_result_",
                    "datapoints": [[4096.0, 1744874940000]],
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

    # ---------- Workload ----------

    @mock.patch("monitor_web.k8s.core.meta.K8sWorkloadMeta.distinct")
    @mock.patch("monitor_web.k8s.core.meta.K8sWorkloadMeta.get_from_meta")
    @apply_setup_filter_mocks
    def test_workload_exclude_history(
        self,
        mock_space_uid,
        mock_cluster_info,
        mock_get_from_meta,
        mock_distinct,
    ):
        """查询不带历史数据的 GPU 工作负载列表"""
        workload_names = [
            "gpu-training-job",
            "gpu-inference-server",
            "gpu-batch-processor",
        ]
        mock_distinct.return_value = [{"workload": f"Deployment:{name}"} for name in workload_names]

        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {"workload": "Deployment:"},
            "query_string": "",
            "page_size": 10,
            "page_type": "scrolling",
            "start_time": 1744957564,
            "end_time": 1744961164,
            "resource_type": "workload",
            "bk_biz_id": 2,
        }
        expected_items = [{"workload": f"Deployment:{name}"} for name in workload_names]
        result = ListK8SResources()(validated_request_data)
        assert result["items"] == expected_items

    @mock.patch("monitor_web.k8s.core.meta.K8sWorkloadMeta.distinct")
    @mock.patch("monitor_web.k8s.core.meta.K8sWorkloadMeta.get_from_meta")
    @apply_setup_filter_mocks
    def test_workload_with_query_string_exclude_history(
        self,
        mock_space_uid,
        mock_cluster_info,
        mock_get_from_meta,
        mock_distinct,
    ):
        """模糊查询不带历史数据的 GPU 工作负载列表"""
        mock_distinct.return_value = [{"workload": "Deployment:gpu-training-job"}]

        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {"workload": "Deployment:"},
            "query_string": "training",
            "page_size": 10,
            "page_type": "scrolling",
            "start_time": 1745200006,
            "end_time": 1745203606,
            "resource_type": "workload",
            "bk_biz_id": 2,
        }
        expected_items = [{"workload": "Deployment:gpu-training-job"}]
        result = ListK8SResources()(validated_request_data)
        assert result["items"] == expected_items

    @mock.patch("monitor_web.k8s.core.meta.K8sWorkloadMeta.distinct")
    @mock.patch("monitor_web.k8s.core.meta.K8sWorkloadMeta.get_from_meta")
    @apply_setup_filter_mocks
    def test_next_page_workload_exclude_history(
        self,
        mock_space_uid,
        mock_cluster_info,
        mock_get_from_meta,
        mock_distinct,
    ):
        """查询下一页不带历史数据的 GPU 工作负载列表"""
        workload_names = [
            "gpu-training-job-1",
            "gpu-training-job-2",
            "gpu-inference-1",
            "gpu-inference-2",
            "gpu-batch-1",
            "gpu-batch-2",
            "gpu-monitor-1",
            "gpu-monitor-2",
            "gpu-dev-1",
            "gpu-dev-2",
        ]
        mock_distinct.return_value = [{"workload": f"Deployment:{name}"} for name in workload_names]

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
        expected_items = [{"workload": f"Deployment:{name}"} for name in workload_names]
        result = ListK8SResources()(validated_request_data)
        assert result["items"] == expected_items

    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    @mock.patch("monitor_web.k8s.core.meta.K8sResourceMeta.get_from_meta", return_value=[])
    @apply_setup_filter_mocks
    def test_workload_with_history(
        self,
        mock_space_uid,
        mock_cluster_info,
        mock_get_from_meta,
        graph_unify_query,
        get_end_time,
    ):
        """查询带历史数据的 GPU 工作负载列表"""
        mock_workload_list = [
            ("gpu-training", "Deployment", "gpu-training-job"),
            ("gpu-training", "Deployment", "gpu-training-preprocessor"),
            ("gpu-inference", "Deployment", "gpu-inference-server"),
            ("gpu-batch", "StatefulSet", "gpu-batch-worker"),
        ]

        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "start_time": 1745303090,
            "end_time": get_end_time,
            "page_size": 10,
            "page": 1,
            "resource_type": "workload",
            "with_history": True,
            "page_type": "scrolling",
            "column": "container_gpu_utilization",
            "order_by": "desc",
            "method": "sum",
            "bk_biz_id": 2,
        }

        expected_items = [
            {"namespace": namespace, "workload": f"{workload_kind}:{workload_name}"}
            for namespace, workload_kind, workload_name in mock_workload_list
        ]

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
                    "datapoints": [[85.5, 1744874940000]],
                    "alias": "_result_",
                    "type": "line",
                    "dimensions_translation": {},
                    "unit": "",
                }
                for namespace, workload_kind, workload_name in mock_workload_list
            ],
            "metrics": [],
        }

        result = ListK8SResources()(validated_request_data)
        assert result["items"] == expected_items

    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    @mock.patch("monitor_web.k8s.core.meta.K8sResourceMeta.get_from_meta", return_value=[])
    @apply_setup_filter_mocks
    def test_workload_with_history_and_filter(
        self,
        mock_space_uid,
        mock_cluster_info,
        mock_get_from_meta,
        graph_unify_query,
    ):
        """查询带历史数据和过滤条件的 GPU 工作负载列表"""
        namespace = "gpu-training"
        mock_workload_list = [
            ("Deployment", "gpu-training-job"),
            ("Deployment", "gpu-training-preprocessor"),
        ]

        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {"namespace": [namespace]},
            "start_time": 1745303283,
            "end_time": 1745306883,
            "page_size": 10,
            "page": 1,
            "resource_type": "workload",
            "with_history": True,
            "page_type": "scrolling",
            "column": "container_gpu_memory_total",
            "order_by": "desc",
            "method": "sum",
            "bk_biz_id": 2,
        }

        expected_items = [
            {"namespace": namespace, "workload": f"{workload_kind}:{workload_name}"}
            for workload_kind, workload_name in mock_workload_list
        ]

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
                    "datapoints": [[4096.0, 1744874940000]],
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
        assert result["items"] == expected_items

    # ---------- Pod ----------

    @mock.patch("monitor_web.k8s.core.meta.K8sPodMeta.distinct")
    @mock.patch("monitor_web.k8s.core.meta.K8sPodMeta.get_from_meta")
    @apply_setup_filter_mocks
    def test_pod_exclude_history(
        self,
        mock_space_uid,
        mock_cluster_info,
        mock_get_from_meta,
        mock_distinct,
    ):
        """查询不带历史数据的 GPU Pod 列表"""
        from bkmonitor.models import BCSPod

        mock_pod = BCSPod()
        mock_pod.name = "gpu-pod-training"
        mock_pod.namespace = "blueking"
        mock_pod.workload_type = "Deployment"
        mock_pod.workload_name = "gpu-workload"
        mock_pod.bk_biz_id = 2
        mock_pod.bcs_cluster_id = "BCS-K8S-00000"

        mock_distinct.return_value = [mock_pod]

        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "query_string": "",
            "page_size": 10,
            "page_type": "scrolling",
            "start_time": 1744957564,
            "end_time": 1744961164,
            "resource_type": "pod",
            "page": 1,
            "bk_biz_id": 2,
        }
        expected_items = [
            {
                "pod": "gpu-pod-training",
                "namespace": "blueking",
                "workload": "Deployment:gpu-workload",
            }
        ]
        result = ListK8SResources()(validated_request_data)
        assert result["items"] == expected_items

    @mock.patch("monitor_web.k8s.core.meta.K8sPodMeta.distinct")
    @mock.patch("monitor_web.k8s.core.meta.K8sPodMeta.get_from_meta")
    @apply_setup_filter_mocks
    def test_pod_with_query_string_exclude_history(
        self,
        mock_space_uid,
        mock_cluster_info,
        mock_get_from_meta,
        mock_distinct,
    ):
        """模糊查询不带历史数据的 GPU Pod 列表"""
        from bkmonitor.models import BCSPod

        mock_pod = BCSPod()
        mock_pod.name = "gpu-training-pod-abc123"
        mock_pod.namespace = "gpu-training"
        mock_pod.workload_type = "Deployment"
        mock_pod.workload_name = "gpu-training-job"
        mock_pod.bk_biz_id = 2
        mock_pod.bcs_cluster_id = "BCS-K8S-00000"

        mock_distinct.return_value = [mock_pod]

        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "query_string": "training",
            "page_size": 10,
            "page_type": "scrolling",
            "start_time": 1745200006,
            "end_time": 1745203606,
            "resource_type": "pod",
            "page": 1,
            "bk_biz_id": 2,
        }
        expected_items = [
            {
                "pod": "gpu-training-pod-abc123",
                "namespace": "gpu-training",
                "workload": "Deployment:gpu-training-job",
            }
        ]
        result = ListK8SResources()(validated_request_data)
        assert result["items"] == expected_items

    @mock.patch("monitor_web.k8s.core.meta.K8sPodMeta.distinct")
    @mock.patch("monitor_web.k8s.core.meta.K8sPodMeta.get_from_meta")
    @apply_setup_filter_mocks
    def test_next_page_pod_exclude_history(
        self,
        mock_space_uid,
        mock_cluster_info,
        mock_get_from_meta,
        mock_distinct,
    ):
        """查询下一页不带历史数据的 GPU Pod 列表"""
        from bkmonitor.models import BCSPod

        mock_pods_data = [
            ("gpu-pod-1", "gpu-training", "Deployment", "gpu-training-job"),
            ("gpu-pod-2", "gpu-training", "Deployment", "gpu-training-job"),
            ("gpu-pod-3", "gpu-inference", "Deployment", "gpu-inference-server"),
        ]
        mock_pod_objects = []
        for name, ns, wl_type, wl_name in mock_pods_data:
            pod = BCSPod()
            pod.name = name
            pod.namespace = ns
            pod.workload_type = wl_type
            pod.workload_name = wl_name
            pod.bk_biz_id = 2
            pod.bcs_cluster_id = "BCS-K8S-00000"
            mock_pod_objects.append(pod)

        mock_distinct.return_value = mock_pod_objects

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
        expected_items = [
            {"pod": name, "namespace": ns, "workload": f"{wl_type}:{wl_name}"}
            for name, ns, wl_type, wl_name in mock_pods_data
        ]
        result = ListK8SResources()(validated_request_data)
        assert result["items"] == expected_items

    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    @mock.patch("monitor_web.k8s.core.meta.K8sResourceMeta.get_from_meta", return_value=[])
    @apply_setup_filter_mocks
    def test_pod_with_history(
        self,
        mock_space_uid,
        mock_cluster_info,
        mock_get_from_meta,
        graph_unify_query,
        get_end_time,
    ):
        """查询带历史数据的 GPU Pod 列表"""
        mock_pod_list = [
            ("gpu-pod-1", "blueking", "Deployment:gpu-workload"),
            ("gpu-pod-2", "default", "StatefulSet:gpu-training"),
        ]

        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "start_time": 1745283797,
            "end_time": get_end_time,
            "page_size": 10,
            "page": 1,
            "resource_type": "pod",
            "with_history": True,
            "page_type": "scrolling",
            "column": "container_gpu_utilization",
            "order_by": "desc",
            "method": "sum",
            "bk_biz_id": 2,
        }

        expected_items = [
            {"pod": pod, "namespace": namespace, "workload": workload} for pod, namespace, workload in mock_pod_list
        ]

        graph_unify_query.return_value = {
            "series": [
                {
                    "dimensions": {
                        "pod_name": pod,
                        "namespace": namespace,
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
                    "datapoints": [[65.3, 1744874940000]],
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
        assert result["items"] == expected_items

    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    @mock.patch("monitor_web.k8s.core.meta.K8sResourceMeta.get_from_meta", return_value=[])
    @apply_setup_filter_mocks
    def test_pod_with_history_and_filter(
        self,
        mock_space_uid,
        mock_cluster_info,
        mock_get_from_meta,
        graph_unify_query,
    ):
        """查询带历史数据和过滤条件的 GPU Pod 列表"""
        mock_pod_list = [
            ("gpu-pod-inference-1", "gpu-inference", "Deployment:gpu-inference-server"),
            ("gpu-pod-inference-2", "gpu-inference", "Deployment:gpu-inference-server"),
        ]

        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {
                "namespace": ["gpu-inference"],
                "workload": ["Deployment:gpu-inference-server"],
            },
            "start_time": 1745303835,
            "end_time": 1745307435,
            "page_size": 10,
            "page": 1,
            "resource_type": "pod",
            "with_history": True,
            "page_type": "scrolling",
            "column": "container_gpu_memory_total",
            "order_by": "desc",
            "method": "sum",
            "bk_biz_id": 2,
        }

        expected_items = [
            {"pod": pod, "namespace": namespace, "workload": workload} for pod, namespace, workload in mock_pod_list
        ]

        graph_unify_query.return_value = {
            "series": [
                {
                    "dimensions": {
                        "pod_name": pod,
                        "namespace": namespace,
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
                    "datapoints": [[4096.0, 1744874940000]],
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
        assert result["items"] == expected_items

    # ---------- Container ----------

    @mock.patch(
        "monitor_web.k8s.core.meta.K8sContainerMeta.distinct",
        return_value=[{"container": "gpu-container-1"}],
    )
    @mock.patch("monitor_web.k8s.core.meta.K8sContainerMeta.get_from_meta")
    @apply_setup_filter_mocks
    def test_container_exclude_history(
        self,
        mock_space_uid,
        mock_cluster_info,
        mock_get_from_meta,
        mock_distinct,
    ):
        """查询不带历史数据的 GPU 容器列表"""
        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "query_string": "",
            "page_size": 10,
            "page_type": "scrolling",
            "start_time": 1744957564,
            "end_time": 1744961164,
            "resource_type": "container",
            "page": 1,
            "bk_biz_id": 2,
        }
        expected_items = [{"container": "gpu-container-1"}]
        result = ListK8SResources()(validated_request_data)
        assert result["items"] == expected_items

    @mock.patch(
        "monitor_web.k8s.core.meta.K8sContainerMeta.distinct",
        return_value=[{"container": "gpu-training-container"}],
    )
    @mock.patch("monitor_web.k8s.core.meta.K8sContainerMeta.get_from_meta")
    @apply_setup_filter_mocks
    def test_container_with_query_string_exclude_history(
        self,
        mock_space_uid,
        mock_cluster_info,
        mock_get_from_meta,
        mock_distinct,
    ):
        """模糊查询不带历史数据的 GPU 容器列表"""
        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "query_string": "training",
            "page_size": 10,
            "page_type": "scrolling",
            "start_time": 1745200006,
            "end_time": 1745203606,
            "resource_type": "container",
            "page": 1,
            "bk_biz_id": 2,
        }
        expected_items = [{"container": "gpu-training-container"}]
        result = ListK8SResources()(validated_request_data)
        assert result["items"] == expected_items

    @mock.patch(
        "monitor_web.k8s.core.meta.K8sContainerMeta.distinct",
        return_value=[
            {"container": "gpu-container-1"},
            {"container": "gpu-container-2"},
            {"container": "gpu-container-3"},
            {"container": "gpu-container-4"},
            {"container": "gpu-container-5"},
            {"container": "gpu-container-6"},
            {"container": "gpu-container-7"},
            {"container": "gpu-container-8"},
            {"container": "gpu-container-9"},
            {"container": "gpu-container-10"},
        ],
    )
    @mock.patch("monitor_web.k8s.core.meta.K8sContainerMeta.get_from_meta")
    @apply_setup_filter_mocks
    def test_next_page_container_exclude_history(
        self,
        mock_space_uid,
        mock_cluster_info,
        mock_get_from_meta,
        mock_distinct,
    ):
        """查询下一页不带历史数据的 GPU 容器列表"""
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
        expected_items = [{"container": f"gpu-container-{i}"} for i in range(1, 11)]
        result = ListK8SResources()(validated_request_data)
        assert result["items"] == expected_items

    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    @mock.patch("monitor_web.k8s.core.meta.K8sResourceMeta.get_from_meta", return_value=[])
    @apply_setup_filter_mocks
    def test_container_with_history(
        self,
        mock_space_uid,
        mock_cluster_info,
        mock_get_from_meta,
        graph_unify_query,
        get_end_time,
    ):
        """查询带历史数据的 GPU 容器列表"""
        mock_container_list = [
            ("gpu-pod-1", "gpu-container-1", "blueking", "Deployment:gpu-workload"),
            ("gpu-pod-2", "gpu-container-2", "blueking", "Deployment:gpu-workload"),
            ("gpu-pod-3", "gpu-container-3", "default", "StatefulSet:gpu-training"),
        ]

        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {},
            "start_time": 1745283797,
            "end_time": get_end_time,
            "page_size": 10,
            "page": 1,
            "resource_type": "container",
            "with_history": True,
            "page_type": "scrolling",
            "column": "container_gpu_utilization",
            "order_by": "desc",
            "method": "sum",
            "bk_biz_id": 2,
        }

        expected_items = [
            {"pod": pod, "container": container, "namespace": namespace, "workload": workload}
            for pod, container, namespace, workload in mock_container_list
        ]

        graph_unify_query.return_value = {
            "series": [
                {
                    "dimensions": {
                        "container_name": container,
                        "pod_name": pod,
                        "namespace": namespace,
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
                    "datapoints": [[75.5, 1744874940000]],
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
        assert result["items"] == expected_items

    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    @mock.patch("monitor_web.k8s.core.meta.K8sResourceMeta.get_from_meta", return_value=[])
    @apply_setup_filter_mocks
    def test_container_with_history_and_filter(
        self,
        mock_space_uid,
        mock_cluster_info,
        mock_get_from_meta,
        graph_unify_query,
    ):
        """查询带历史数据和过滤条件的 GPU 容器列表"""
        mock_container_list = [
            ("gpu-pod-inference", "gpu-inference-container", "blueking", "Deployment:gpu-inference"),
        ]

        validated_request_data = {
            "scenario": SCENARIO,
            "bcs_cluster_id": "BCS-K8S-00000",
            "filter_dict": {"container": ["gpu-inference-container"]},
            "start_time": 1745315249,
            "end_time": 1745318849,
            "page_size": 20,
            "page": 1,
            "resource_type": "container",
            "with_history": True,
            "page_type": "scrolling",
            "column": "container_gpu_memory_total",
            "order_by": "desc",
            "method": "sum",
            "bk_biz_id": 2,
        }

        expected_items = [
            {"pod": pod, "container": container, "namespace": namespace, "workload": workload}
            for pod, container, namespace, workload in mock_container_list
        ]

        graph_unify_query.return_value = {
            "series": [
                {
                    "dimensions": {
                        "container_name": container,
                        "pod_name": pod,
                        "namespace": namespace,
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
                    "datapoints": [[80.2, 1744874940000]],
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
        """查询不带历史数据的 GPU 集群列表"""
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
        """查询带历史数据的 GPU 集群列表（单业务单集群，只会有一个）"""
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
            "column": "container_gpu_utilization",
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
                    "datapoints": [[95.0, 1744874940000]],
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
