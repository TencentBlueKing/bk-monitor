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
from unittest import mock

import pytest
from django.utils import timezone

from bkmonitor.models import BCSContainer, BCSPod, BCSWorkload
from monitor_web.k8s.core.meta import NameSpace, NameSpaceQuerySet
from monitor_web.k8s.resources import (
    GetScenarioMetric,
    ListK8SResources,
    ResourceTrendResource,
    WorkloadOverview,
)
from packages.monitor_web.k8s.scenario import Scenario

SCENARIO: Scenario = "performance"

PERFORMANCE_COLUMNS_NAMESPACE = [
    "container_cpu_usage_seconds_total",
    "container_cpu_cfs_throttled_ratio",
    "container_memory_working_set_bytes",
    "container_network_receive_bytes_total",
    "container_network_transmit_bytes_total",
]

PERFORMANCE_COLUMNS_WORKLOAD = [
    "container_cpu_usage_seconds_total",
    "kube_pod_cpu_requests_ratio",
    "kube_pod_cpu_limits_ratio",
    "container_cpu_cfs_throttled_ratio",
    "container_memory_working_set_bytes",
    "kube_pod_memory_requests_ratio",
    "kube_pod_memory_limits_ratio",
    "container_network_receive_bytes_total",
    "container_network_transmit_bytes_total",
]

PERFORMANCE_COLUMNS_CONTAINER = [
    "container_cpu_usage_seconds_total",
    "kube_pod_cpu_requests_ratio",
    "kube_pod_cpu_limits_ratio",
    "container_cpu_cfs_throttled_ratio",
    "container_memory_working_set_bytes",
    "kube_pod_memory_requests_ratio",
    "kube_pod_memory_limits_ratio",
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


@pytest.fixture()
def get_start_time() -> int:
    return int(time.mktime((timezone.now() - timezone.timedelta(days=1)).timetuple()))


@pytest.fixture()
def get_end_time() -> int:
    return int(time.mktime((timezone.now()).timetuple()))


# ==================== Helper 函数 ====================


def _make_namespace_queryset(names, bk_biz_id=2, bcs_cluster_id="BCS-K8S-00000"):
    """创建内存中的 NameSpaceQuerySet"""
    return NameSpaceQuerySet(
        [NameSpace({"bk_biz_id": bk_biz_id, "bcs_cluster_id": bcs_cluster_id, "namespace": name}) for name in names]
    )


def _make_workload_queryset(workload_names, workload_type="Deployment"):
    """模拟 K8sWorkloadMeta.distinct 返回的 queryset（values 列表）"""
    return [{"workload": f"{workload_type}:{name}"} for name in workload_names]


def _make_pod_objects(pod_list, bk_biz_id=2, bcs_cluster_id="BCS-K8S-00000"):
    """创建内存中的 BCSPod 对象列表"""
    result = []
    for name, namespace, workload_type, workload_name in pod_list:
        obj = BCSPod()
        obj.name = name
        obj.namespace = namespace
        obj.workload_type = workload_type
        obj.workload_name = workload_name
        obj.bk_biz_id = bk_biz_id
        obj.bcs_cluster_id = bcs_cluster_id
        result.append(obj)
    return result


def _make_container_queryset(container_names):
    """模拟 K8sContainerMeta.distinct 返回的 queryset（values 列表）"""
    return [{"container": name} for name in container_names]


def _make_workload_objects(workload_list, bk_biz_id=2, bcs_cluster_id="BCS-K8S-00000"):
    """创建内存中的 BCSWorkload 对象列表"""
    result = []
    for namespace, wl_type, wl_name in workload_list:
        obj = BCSWorkload()
        obj.namespace = namespace
        obj.type = wl_type
        obj.name = wl_name
        obj.bk_biz_id = bk_biz_id
        obj.bcs_cluster_id = bcs_cluster_id
        result.append(obj)
    return result


def _make_container_objects(container_list, bk_biz_id=2, bcs_cluster_id="BCS-K8S-00000"):
    """创建内存中的 BCSContainer 对象列表"""
    result = []
    for pod_name, container_name, namespace, workload_type, workload_name in container_list:
        obj = BCSContainer()
        obj.pod_name = pod_name
        obj.name = container_name
        obj.namespace = namespace
        obj.workload_type = workload_type
        obj.workload_name = workload_name
        obj.bk_biz_id = bk_biz_id
        obj.bcs_cluster_id = bcs_cluster_id
        result.append(obj)
    return result


# ==================== WorkloadOverview 测试 ====================


class TestWorkloadOverview:
    """测试 WorkloadOverview，mock BCSWorkload.objects.filter 避免 DB 依赖"""

    def _make_mock_queryset(self, mock_data):
        """构造 mock queryset 用于 WorkloadOverview

        mock_data: list of [namespace, type, name]
        """

        class FakeQuerySet:
            def __init__(self, data):
                self._data = data
                self._values_fields = None

            def __iter__(self):
                return iter(self._data)

            def filter(self, **kwargs):
                filtered = list(self._data)
                if "namespace__in" in kwargs:
                    ns_list = kwargs["namespace__in"]
                    filtered = [d for d in filtered if d["namespace"] in ns_list]
                if "name__icontains" in kwargs:
                    q = kwargs["name__icontains"].lower()
                    filtered = [d for d in filtered if q in d["name"].lower()]
                return FakeQuerySet(filtered)

            def values(self, *fields):
                self._values_fields = fields
                return self

            def annotate(self, **kwargs):
                if "count" in kwargs:
                    result = {}
                    for item in self._data:
                        key = item[self._values_fields[0]]
                        name = item["name"]
                        if key not in result:
                            result[key] = set()
                        result[key].add(name)
                    self._data = [{self._values_fields[0]: k, "count": len(v)} for k, v in result.items()]
                return self

        data = [{"namespace": item[0], "type": item[1], "name": item[2]} for item in mock_data]
        return FakeQuerySet(data)

    @mock.patch("monitor_web.k8s.resources.BCSWorkload.objects")
    def test_workload_overview_with_nothing(self, mock_objects):
        mock_data = [
            ["blueking", "Deployment", "bk-monitor-web"],
            ["default", "Deployment", "demo"],
            ["blueking", "Deployment", "bk-monitor-web-worker"],
            ["qzx", "NewType", "new-workload-name"],
        ]
        mock_objects.filter.return_value = self._make_mock_queryset(mock_data)

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

    @mock.patch("monitor_web.k8s.resources.BCSWorkload.objects")
    def test_workload_overview_with_namespace(self, mock_objects):
        mock_data = [
            ["blueking", "Deployment", "bk-monitor-web"],
            ["default", "Deployment", "demo"],
            ["blueking", "Deployment", "bk-monitor-web-worker"],
            ["qzx", "NewType", "new-workload-name"],
        ]
        mock_objects.filter.return_value = self._make_mock_queryset(mock_data)

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

    @mock.patch("monitor_web.k8s.resources.BCSWorkload.objects")
    def test_workload_overview_with_query_string(self, mock_objects):
        mock_data = [
            ["blueking", "Deployment", "bk-monitor-web"],
            ["default", "Deployment", "demo"],
            ["blueking", "Deployment", "bk-monitor-web-worker"],
            ["qzx", "NewType", "new-workload-name"],
        ]
        mock_objects.filter.return_value = self._make_mock_queryset(mock_data)

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


# ==================== ResourceTrendResource 测试 ====================


class TestResourceTrendResourceWithPerformance:
    @pytest.mark.parametrize(
        ["column"],
        [pytest.param(c) for c in PERFORMANCE_COLUMNS_NAMESPACE],
    )
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
        [pytest.param(c) for c in PERFORMANCE_COLUMNS_WORKLOAD],
    )
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
        [pytest.param(c) for c in PERFORMANCE_COLUMNS_WORKLOAD],
    )
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
        [pytest.param(c) for c in PERFORMANCE_COLUMNS_CONTAINER],
    )
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
        [pytest.param(c) for c in PERFORMANCE_COLUMNS_CONTAINER],
    )
    @apply_setup_filter_mocks
    def test_with_no_resource_list(
        self,
        mock_space_uid,
        mock_cluster_info,
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


# ==================== ListK8SResources 测试 ====================


class TestListK8SResourcesWithPerformance:
    # ---- exclude_history 部分：mock distinct + get_from_meta ----

    @mock.patch("monitor_web.k8s.core.meta.K8sNamespaceMeta.get_from_meta")
    @mock.patch("monitor_web.k8s.core.meta.K8sNamespaceMeta.distinct")
    @apply_setup_filter_mocks
    def test_namespace_exclude_history(self, mock_space_uid, mock_cluster_info, mock_distinct, mock_get_from_meta):
        """查询不带历史数据的 namespace 列表"""
        mock_namespace_names = [
            "base",
            "bcs-op-yunwei-frodomei",
            "bcs-stag-cloud-test",
            "bcs-system",
            "bcsk8s-sutest",
        ]
        ns_qs = _make_namespace_queryset(mock_namespace_names)
        mock_get_from_meta.return_value = ns_qs
        mock_distinct.return_value = ns_qs

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
            "count": 5,
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

    @mock.patch("monitor_web.k8s.core.meta.K8sWorkloadMeta.get_from_meta")
    @mock.patch("monitor_web.k8s.core.meta.K8sWorkloadMeta.distinct")
    @apply_setup_filter_mocks
    def test_workload_exclude_history(self, mock_space_uid, mock_cluster_info, mock_distinct, mock_get_from_meta):
        """查询不带历史数据的 workload 列表"""
        workload_names = [
            "aasagent",
            "access",
            "add-pod-eni-ip-limit-webhook",
            "ap-nginx-portpool",
            "appassist",
        ]
        wl_qs = _make_workload_queryset(workload_names)
        mock_get_from_meta.return_value = wl_qs
        mock_distinct.return_value = wl_qs

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
            "count": 5,
            "items": [{"workload": f"Deployment:{name}"} for name in workload_names],
        }
        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]

    @mock.patch("monitor_web.k8s.core.meta.K8sPodMeta.get_from_meta")
    @mock.patch("monitor_web.k8s.core.meta.K8sPodMeta.distinct")
    @apply_setup_filter_mocks
    def test_pod_exclude_history(self, mock_space_uid, mock_cluster_info, mock_distinct, mock_get_from_meta):
        """查询不带历史数据的 pod 列表"""
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
        pod_objs = _make_pod_objects(mock_pods)
        mock_get_from_meta.return_value = pod_objs
        mock_distinct.return_value = pod_objs

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
            "count": 5,
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

    @mock.patch("monitor_web.k8s.core.meta.K8sContainerMeta.get_from_meta")
    @mock.patch("monitor_web.k8s.core.meta.K8sContainerMeta.distinct")
    @apply_setup_filter_mocks
    def test_container_exclude_history(self, mock_space_uid, mock_cluster_info, mock_distinct, mock_get_from_meta):
        """查询不带历史数据的 container 列表"""
        mock_containers = [
            "account-service",
            "add-pod-eni-ip-limit-webhook",
            "alertmanager",
            "analyzer",
            "api",
        ]
        ct_qs = _make_container_queryset(mock_containers)
        mock_get_from_meta.return_value = ct_qs
        mock_distinct.return_value = ct_qs

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
            "count": 5,
            "items": [{"container": item} for item in mock_containers],
        }
        result = ListK8SResources()(validated_request_data)
        assert mock_result["items"] == result["items"]

    # ---- next page exclude_history ----

    @mock.patch("monitor_web.k8s.core.meta.K8sNamespaceMeta.get_from_meta")
    @mock.patch("monitor_web.k8s.core.meta.K8sNamespaceMeta.distinct")
    @apply_setup_filter_mocks
    def test_next_page_namespace_exclude_history(
        self, mock_space_uid, mock_cluster_info, mock_distinct, mock_get_from_meta
    ):
        """查询下一页不带历史数据的 namespace 列表"""
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
        ns_qs = _make_namespace_queryset(mock_namespace_names)
        mock_get_from_meta.return_value = ns_qs
        mock_distinct.return_value = ns_qs

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
            "count": 10,
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

    @mock.patch("monitor_web.k8s.core.meta.K8sWorkloadMeta.get_from_meta")
    @mock.patch("monitor_web.k8s.core.meta.K8sWorkloadMeta.distinct")
    @apply_setup_filter_mocks
    def test_next_page_workload_exclude_history(
        self, mock_space_uid, mock_cluster_info, mock_distinct, mock_get_from_meta
    ):
        """查询下一页不带历史数据的 workload 列表"""
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
        wl_qs = _make_workload_queryset(mock_workloads)
        mock_get_from_meta.return_value = wl_qs
        mock_distinct.return_value = wl_qs

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
            "count": 10,
            "items": [{"workload": f"Deployment:{name}"} for name in mock_workloads],
        }

        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]

    @mock.patch("monitor_web.k8s.core.meta.K8sPodMeta.get_from_meta")
    @mock.patch("monitor_web.k8s.core.meta.K8sPodMeta.distinct")
    @apply_setup_filter_mocks
    def test_next_page_pod_exclude_history(self, mock_space_uid, mock_cluster_info, mock_distinct, mock_get_from_meta):
        """查询下一页不带历史数据的 pod 列表"""
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
        pod_objs = _make_pod_objects(mock_pods)
        mock_get_from_meta.return_value = pod_objs
        mock_distinct.return_value = pod_objs

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
            "count": 3,
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

    @mock.patch("monitor_web.k8s.core.meta.K8sContainerMeta.get_from_meta")
    @mock.patch("monitor_web.k8s.core.meta.K8sContainerMeta.distinct")
    @apply_setup_filter_mocks
    def test_next_page_container_exclude_history(
        self, mock_space_uid, mock_cluster_info, mock_distinct, mock_get_from_meta
    ):
        """查询下一页不带历史数据的 container 列表"""
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
        ct_qs = _make_container_queryset(mock_containers)
        mock_get_from_meta.return_value = ct_qs
        mock_distinct.return_value = ct_qs

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
            "count": 10,
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

    # ---- query_string exclude_history ----

    @mock.patch("monitor_web.k8s.core.meta.K8sNamespaceMeta.get_from_meta")
    @mock.patch("monitor_web.k8s.core.meta.K8sNamespaceMeta.distinct")
    @apply_setup_filter_mocks
    def test_namespace_with_query_string_exclude_history(
        self, mock_space_uid, mock_cluster_info, mock_distinct, mock_get_from_meta
    ):
        """模糊查询但不带历史数据的 namespace 列表"""
        mock_namespaces = ["bkmonitor-operator", "bkmonitor-operator-bkop"]
        ns_qs = _make_namespace_queryset(mock_namespaces)
        mock_get_from_meta.return_value = ns_qs
        mock_distinct.return_value = ns_qs

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

    @mock.patch("monitor_web.k8s.core.meta.K8sWorkloadMeta.get_from_meta")
    @mock.patch("monitor_web.k8s.core.meta.K8sWorkloadMeta.distinct")
    @apply_setup_filter_mocks
    def test_workload_with_query_string_exclude_history(
        self, mock_space_uid, mock_cluster_info, mock_distinct, mock_get_from_meta
    ):
        """模糊查询但不带历史数据的 workload 列表"""
        wl_qs = [{"workload": "Deployment:bk-datalink-unify-query-bkmonitor"}]
        mock_get_from_meta.return_value = wl_qs
        mock_distinct.return_value = wl_qs

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

    @mock.patch("monitor_web.k8s.core.meta.K8sPodMeta.get_from_meta")
    @mock.patch("monitor_web.k8s.core.meta.K8sPodMeta.distinct")
    @apply_setup_filter_mocks
    def test_pod_with_query_string_exclude_history(
        self, mock_space_uid, mock_cluster_info, mock_distinct, mock_get_from_meta
    ):
        """模糊查询但不带历史数据的 pod 列表"""
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
        pod_objs = _make_pod_objects(mock_pods)
        mock_get_from_meta.return_value = pod_objs
        mock_distinct.return_value = pod_objs

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
            "count": 5,
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

    @mock.patch("monitor_web.k8s.core.meta.K8sContainerMeta.get_from_meta")
    @mock.patch("monitor_web.k8s.core.meta.K8sContainerMeta.distinct")
    @apply_setup_filter_mocks
    def test_container_with_query_string_exclude_history(
        self, mock_space_uid, mock_cluster_info, mock_distinct, mock_get_from_meta
    ):
        """模糊查询但不带历史数据的 container 列表"""
        mock_containers = [
            "bkbase-clean-bkmonitorgz23-gz1-post-install-job",
            "bkmonitor-operator",
            "bkmonitorbeat",
            "dbm-bkmonitor-init",
        ]
        ct_qs = _make_container_queryset(mock_containers)
        mock_get_from_meta.return_value = ct_qs
        mock_distinct.return_value = ct_qs

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

    # ---- with_history 部分 ----

    @mock.patch("monitor_web.k8s.core.meta.K8sNamespaceMeta.get_from_meta")
    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    @apply_setup_filter_mocks
    def test_namespace_with_history(self, mock_space_uid, mock_cluster_info, graph_unify_query, mock_get_from_meta):
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
            "count": 11,
            "items": [
                {
                    "bk_biz_id": 2,
                    "bcs_cluster_id": "BCS-K8S-00000",
                    "namespace": namespace,
                }
                for namespace in mock_namespace_list[:10]
            ],
        }

        # PromQL 只返回前 5 个
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

        # get_from_meta 返回第 5-11 个（模拟从 DB 补充）
        db_ns_objs = _make_namespace_queryset(mock_namespace_list[4:])
        mock_get_from_meta.return_value = db_ns_objs

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
        # 即使 get_from_meta 为空也不影响（PromQL 数据已足够）
        mock_get_from_meta.return_value = _make_namespace_queryset([])
        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]

    @mock.patch("monitor_web.k8s.core.meta.K8sNamespaceMeta.get_from_meta")
    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    @apply_setup_filter_mocks
    def test_namespace_with_history_and_filter(
        self, mock_space_uid, mock_cluster_info, graph_unify_query, mock_get_from_meta
    ):
        """查询带历史数据和过滤条件的 namespace 列表"""
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
        mock_get_from_meta.return_value = _make_namespace_queryset(mock_namespace_list)

        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]

    @mock.patch("monitor_web.k8s.core.meta.K8sWorkloadMeta.get_from_meta")
    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    @apply_setup_filter_mocks
    def test_workload_with_history(self, mock_space_uid, mock_cluster_info, graph_unify_query, mock_get_from_meta):
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
        mock_get_from_meta.return_value = _make_workload_objects(mock_workload_list)

        mock_result = {
            "count": 10,
            "items": [
                {"namespace": namespace, "workload": f"{workload_type}:{workload_name}"}
                for namespace, workload_type, workload_name in mock_workload_list
            ],
        }

        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]

    @mock.patch("monitor_web.k8s.core.meta.K8sWorkloadMeta.get_from_meta")
    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    @apply_setup_filter_mocks
    def test_workload_with_history_and_filter(
        self, mock_space_uid, mock_cluster_info, graph_unify_query, mock_get_from_meta
    ):
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
            "count": 10,
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
        mock_get_from_meta.return_value = _make_workload_objects([(namespace, wk, wn) for wk, wn in mock_workload_list])

        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]

    @mock.patch("monitor_web.k8s.core.meta.K8sPodMeta.get_from_meta")
    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    @apply_setup_filter_mocks
    def test_pod_with_history(self, mock_space_uid, mock_cluster_info, graph_unify_query, mock_get_from_meta):
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
            "count": 10,
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
        pod_objs = _make_pod_objects(
            [
                (pod, namespace, workload.split(":")[0], workload.split(":")[1])
                for pod, namespace, workload in mock_pod_list
            ]
        )
        mock_get_from_meta.return_value = pod_objs

        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]

    @mock.patch("monitor_web.k8s.core.meta.K8sPodMeta.get_from_meta")
    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    @apply_setup_filter_mocks
    def test_pod_with_history_and_filter(
        self, mock_space_uid, mock_cluster_info, graph_unify_query, mock_get_from_meta
    ):
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
        pod_objs = _make_pod_objects(
            [
                (pod, namespace, workload.split(":")[0], workload.split(":")[1])
                for pod, namespace, workload in mock_pod_list
            ]
        )
        mock_get_from_meta.return_value = pod_objs

        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]

    @mock.patch("monitor_web.k8s.core.meta.K8sContainerMeta.get_from_meta")
    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    @apply_setup_filter_mocks
    def test_container_with_history(self, mock_space_uid, mock_cluster_info, graph_unify_query, mock_get_from_meta):
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
            "count": 10,
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
        container_objs = _make_container_objects(
            [
                (pod, container, namespace, workload.split(":")[0], workload.split(":")[1])
                for pod, container, namespace, workload in mock_container_list
            ]
        )
        mock_get_from_meta.return_value = container_objs

        result = ListK8SResources()(validated_request_data)
        assert result["items"] == mock_result["items"]

    @mock.patch("monitor_web.k8s.core.meta.K8sContainerMeta.get_from_meta")
    @mock.patch("core.drf_resource.resource.grafana.graph_unify_query")
    @apply_setup_filter_mocks
    def test_container_with_history_and_filter(
        self, mock_space_uid, mock_cluster_info, graph_unify_query, mock_get_from_meta
    ):
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
        container_objs = _make_container_objects(
            [
                (pod, container, namespace, workload.split(":")[0], workload.split(":")[1])
                for container, namespace, pod, workload in mock_container_list
            ]
        )
        mock_get_from_meta.return_value = container_objs

        result = ListK8SResources()(validated_request_data)
        assert result == mock_result
