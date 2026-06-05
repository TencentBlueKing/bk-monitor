"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.test import TestCase

from monitor_web.k8s.core.meta import K8sClusterMeta, K8sNodeMeta
from monitor_web.k8s.scenario import get_metrics

# setup_filter 默认注入 bcs_cluster_id 与 container_name!="POD" 两个过滤
FILTER = 'bcs_cluster_id="BCS-K8S-00000",container_name!="POD"'

GPU_METRIC_IDS = [
    "node_gpu_usage_ratio",
    "node_gpu_mem_usage_ratio",
    "node_gpu_mem_used",
    "node_gpu_power_usage",
    "node_gpu_temperature",
    "node_gpu_anomaly_count",
]


class TestCapacityGpuScenario(TestCase):
    def test_capacity_contains_gpu_category(self):
        metrics = get_metrics("capacity")
        gpu_categories = [category for category in metrics if category["id"] == "GPU"]
        self.assertEqual(len(gpu_categories), 1)
        self.assertEqual([metric["id"] for metric in gpu_categories[0]["children"]], GPU_METRIC_IDS)

    def test_gpu_category_appended_last(self):
        # GPU 分类必须在列表末尾：表格默认排序列取第一个可见指标列，避免无 GPU 集群默认排序无数据
        metrics = get_metrics("capacity")
        self.assertEqual(metrics[-1]["id"], "GPU")


class TestCapacityGpuPromql(TestCase):
    """容量场景 cluster/node 两层级都会 dispatch，K8sNodeMeta 与 K8sClusterMeta 必须双双实现 GPU promql"""

    def test_gpu_promql_dispatch_on_both_levels(self):
        # 防止方法落错类导致 getattr 时 AttributeError
        for metric_id in GPU_METRIC_IDS:
            for meta in (K8sNodeMeta(2, "BCS-K8S-00000"), K8sClusterMeta(2, "BCS-K8S-00000")):
                promql = getattr(meta, f"meta_prom_with_{metric_id}")
                self.assertTrue(promql, f"{type(meta).__name__}.meta_prom_with_{metric_id} 返回空")

    def test_node_gpu_usage_ratio(self):
        self.assertEqual(
            K8sNodeMeta(2, "BCS-K8S-00000").meta_prom_with_node_gpu_usage_ratio,
            f"avg by (node) (gpu_core_utilization_percentage{{{FILTER}}})",
        )
        self.assertEqual(
            K8sClusterMeta(2, "BCS-K8S-00000").meta_prom_with_node_gpu_usage_ratio,
            f"avg by (bcs_cluster_id) (gpu_core_utilization_percentage{{{FILTER}}})",
        )

    def test_node_gpu_mem_usage_ratio(self):
        self.assertEqual(
            K8sNodeMeta(2, "BCS-K8S-00000").meta_prom_with_node_gpu_mem_usage_ratio,
            f"(sum by (node) (gpu_mem_usage{{{FILTER}}}) / sum by (node) (gpu_mem_each_card{{{FILTER}}})) * 100",
        )
        self.assertEqual(
            K8sClusterMeta(2, "BCS-K8S-00000").meta_prom_with_node_gpu_mem_usage_ratio,
            f"(sum by (bcs_cluster_id) (gpu_mem_usage{{{FILTER}}})"
            f" / sum by (bcs_cluster_id) (gpu_mem_each_card{{{FILTER}}})) * 100",
        )

    def test_node_gpu_mem_used(self):
        # 默认聚合方法 sum，尊重用户选择（不写死）
        self.assertEqual(
            K8sNodeMeta(2, "BCS-K8S-00000").meta_prom_with_node_gpu_mem_used,
            f"sum by (node) (gpu_mem_usage{{{FILTER}}})",
        )
        self.assertEqual(
            K8sClusterMeta(2, "BCS-K8S-00000").meta_prom_with_node_gpu_mem_used,
            f"sum by (bcs_cluster_id) (gpu_mem_usage{{{FILTER}}})",
        )

    def test_node_gpu_power_usage(self):
        self.assertEqual(
            K8sNodeMeta(2, "BCS-K8S-00000").meta_prom_with_node_gpu_power_usage,
            f"sum by (node) (gpu_power_usage{{{FILTER}}})",
        )
        self.assertEqual(
            K8sClusterMeta(2, "BCS-K8S-00000").meta_prom_with_node_gpu_power_usage,
            f"sum by (bcs_cluster_id) (gpu_power_usage{{{FILTER}}})",
        )

    def test_node_gpu_temperature(self):
        # 聚合写死 max；指标名 gpu_temprature 为 exporter 原始拼写
        self.assertEqual(
            K8sNodeMeta(2, "BCS-K8S-00000").meta_prom_with_node_gpu_temperature,
            f"max by (node) (gpu_temprature{{{FILTER}}})",
        )
        self.assertEqual(
            K8sClusterMeta(2, "BCS-K8S-00000").meta_prom_with_node_gpu_temperature,
            f"max by (bcs_cluster_id) (gpu_temprature{{{FILTER}}})",
        )

    def test_node_gpu_anomaly_count(self):
        ecc_filter = f'{FILTER},counter_type="aggregate"'
        node_baseline = f"max by (node) (max_over_time(gpu_count{{{FILTER}}}[1d]))"
        node_current = f"max by (node) (gpu_count{{{FILTER}}})"
        # 注意最外层括号：meta_prom_by_sort 升序会拼接 " * -1"，裸 A + B 会因运算符优先级变成 A - B
        node_promql = K8sNodeMeta(2, "BCS-K8S-00000").meta_prom_with_node_gpu_anomaly_count
        self.assertTrue(node_promql.startswith("(") and node_promql.endswith(")"))
        self.assertEqual(
            node_promql,
            f"((sum by (node) (increase(gpu_ecc_error_count{{{ecc_filter}}}[5m])) or {node_baseline} * 0)"
            f" + clamp_min({node_baseline} - ({node_current} or {node_baseline} * 0), 0))",
        )
        cluster_baseline = f"max by (bcs_cluster_id, node) (max_over_time(gpu_count{{{FILTER}}}[1d]))"
        cluster_current = f"max by (bcs_cluster_id, node) (gpu_count{{{FILTER}}})"
        self.assertEqual(
            K8sClusterMeta(2, "BCS-K8S-00000").meta_prom_with_node_gpu_anomaly_count,
            "sum by (bcs_cluster_id) ("
            f"(sum by (bcs_cluster_id, node) (increase(gpu_ecc_error_count{{{ecc_filter}}}[5m]))"
            f" or {cluster_baseline} * 0)"
            f" + clamp_min({cluster_baseline} - ({cluster_current} or {cluster_baseline} * 0), 0)"
            ")",
        )
