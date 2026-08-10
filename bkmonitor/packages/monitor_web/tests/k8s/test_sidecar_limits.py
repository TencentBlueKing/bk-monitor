"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from unittest import TestCase

from monitor_web.k8s.core.meta import K8sContainerMeta, K8sPodMeta, K8sWorkloadMeta


CLUSTER_ID = "BCS-K8S-00000"
FILTER = f'bcs_cluster_id="{CLUSTER_ID}",namespace="default",container_name!="POD"'


class _ClusterFilter:
    @staticmethod
    def filter_string():
        return f'bcs_cluster_id="{CLUSTER_ID}"'


class _FilterCollection:
    filters = {"bcs_cluster_id": _ClusterFilter()}

    @staticmethod
    def filter_string(exclude=""):
        return FILTER


def _build_meta(meta_cls):
    meta = object.__new__(meta_cls)
    meta.filter = _FilterCollection()
    meta.method = "sum"
    meta.agg_interval = ""
    return meta


class TestSidecarResourceLimitsPromql(TestCase):
    def test_limit_ratios_include_running_init_container_limits(self):
        metric_cases = [
            ("kube_pod_cpu_limits_ratio", "cpu", "core"),
            ("kube_pod_memory_limits_ratio", "memory", "byte"),
        ]

        for meta_cls in (K8sPodMeta, K8sWorkloadMeta, K8sContainerMeta):
            meta = _build_meta(meta_cls)
            for metric_name, resource, unit in metric_cases:
                with self.subTest(meta=meta_cls.__name__, metric=metric_name):
                    promql = getattr(meta, f"meta_prom_with_{metric_name}")
                    resource_filter = f'resource="{resource}",unit="{unit}",{FILTER}'

                    self.assertIn(f"kube_pod_container_resource_limits{{{resource_filter}}}", promql)
                    self.assertIn(f"kube_pod_init_container_resource_limits{{{resource_filter}}}", promql)
                    self.assertIn(
                        f'kube_pod_init_container_status_running{{bcs_cluster_id="{CLUSTER_ID}"}} == 1',
                        promql,
                    )
                    self.assertIn("* on(namespace,pod,container) group_left()", promql)
