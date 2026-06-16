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

from monitor_web.k8s.core.gpu_compat import gpu_or
from monitor_web.k8s.core.meta import (
    K8sContainerMeta,
    K8sNamespaceMeta,
    K8sPodMeta,
    K8sWorkloadMeta,
)
from monitor_web.k8s.scenario import get_metrics

# setup_filter 默认注入 bcs_cluster_id 与 container_name!="POD" 两个过滤
FILTER = 'bcs_cluster_id="BCS-K8S-00000",container_name!="POD"'
# dcgm 支额外带 pod_name!="" 护栏(_attributed):只取已归属到 pod 的卡,排除空闲卡漏进 namespace/cluster 汇总
ATTR_FILTER = f'{FILTER},pod_name!=""'

# tke_gpu 容器场景的 6 个原生指标(须与前端 GPU_METRIC_SET、scenario/tke_gpu.py 三方对齐)
CONTAINER_GPU_METRIC_IDS = [
    "container_gpu_utilization",
    "container_gpu_memory_total",
    "container_core_utilization_percentage",
    "container_mem_utilization_percentage",
    "container_request_gpu_memory",
    "container_request_gpu_utilization",
]

# tke_gpu 场景按 workload / namespace / pod / container 四个层级 dispatch,四个 meta 类都要实现双源
CONTAINER_GPU_META_CLASSES = [K8sWorkloadMeta, K8sNamespaceMeta, K8sPodMeta, K8sContainerMeta]


class TestTkeGpuScenario(TestCase):
    def test_tke_gpu_metric_ids(self):
        # 场景目录声明的指标 id 与顺序锁定,避免与前端/双源映射表悄悄漂移
        metrics = get_metrics("tke_gpu")
        gpu_categories = [category for category in metrics if category["id"] == "GPU"]
        self.assertEqual(len(gpu_categories), 1)
        self.assertEqual([metric["id"] for metric in gpu_categories[0]["children"]], CONTAINER_GPU_METRIC_IDS)


class TestTkeGpuDualSourcePromql(TestCase):
    """容器场景 4 个层级的 container_* GPU 叶子都必须走双源:(原生 or dcgm 等价)。

    非 dcgm 集群 dcgm 支(锚定 DCGM_FI_* 选择器)为空,or 回退到原生 container_*;dcgm 集群原生缺席,
    走 dcgm 整卡语义等价。dcgm 侧 pod->pod_name / container->container_name 由 chart relabel(v3.6.180)对齐。
    """

    def test_fixture_filter_no_workload_diff(self):
        # 后续断言以 FILTER 直接构造叶子的前提:默认 fixture 无 workload 过滤,exclude="workload" 与全量一致
        meta = K8sPodMeta(2, "BCS-K8S-00000")
        self.assertEqual(meta.filter.filter_string(), FILTER)
        self.assertEqual(meta.filter.filter_string(exclude="workload"), FILTER)

    def test_all_levels_all_metrics_dual_source(self):
        # 防漏接:任一层级任一指标叶子没走双源(gpu_or 输出未原样出现)即失败
        for meta_cls in CONTAINER_GPU_META_CLASSES:
            meta = meta_cls(2, "BCS-K8S-00000")
            for metric_id in CONTAINER_GPU_METRIC_IDS:
                promql = getattr(meta, f"meta_prom_with_{metric_id}")
                self.assertTrue(promql, f"{meta_cls.__name__}.meta_prom_with_{metric_id} 返回空")
                self.assertIn(
                    gpu_or(metric_id, FILTER),
                    promql,
                    f"{meta_cls.__name__}.{metric_id} 叶子未走双源",
                )

    def test_used_metrics_rename_to_card_telemetry(self):
        # 实际用量类:整卡语义下直接取卡级遥测(算力->GPU_UTIL,显存->FB_USED);dcgm 支带 pod_name!="" 护栏
        meta = K8sPodMeta(2, "BCS-K8S-00000")
        self.assertIn(
            f"(container_gpu_utilization{{{FILTER}}} or DCGM_FI_DEV_GPU_UTIL{{{ATTR_FILTER}}})",
            meta.meta_prom_with_container_gpu_utilization,
        )
        self.assertIn(
            f"(container_gpu_memory_total{{{FILTER}}} or DCGM_FI_DEV_FB_USED{{{ATTR_FILTER}}})",
            meta.meta_prom_with_container_gpu_memory_total,
        )

    def test_request_metrics_use_oncard_constants(self):
        # 申请类:容器独占整卡 -> 申请显存=整卡总显存、申请算力=100%(乘 0 锚定 GPU_UTIL,非 dcgm 集群该支为空)
        meta = K8sContainerMeta(2, "BCS-K8S-00000")
        fb_total = (
            f"(DCGM_FI_DEV_FB_USED{{{ATTR_FILTER}}} + DCGM_FI_DEV_FB_FREE{{{ATTR_FILTER}}}"
            f" + DCGM_FI_DEV_FB_RESERVED{{{ATTR_FILTER}}})"
        )
        self.assertIn(
            f"(container_request_gpu_memory{{{FILTER}}} or {fb_total})",
            meta.meta_prom_with_container_request_gpu_memory,
        )
        self.assertIn(
            f"(container_request_gpu_utilization{{{FILTER}}} or (DCGM_FI_DEV_GPU_UTIL{{{ATTR_FILTER}}} * 0 + 100))",
            meta.meta_prom_with_container_request_gpu_utilization,
        )

    def test_mem_utilization_percentage_is_ratio(self):
        # 显存使用率%:整卡申请 -> 已用 / 整卡总显存 * 100
        meta = K8sPodMeta(2, "BCS-K8S-00000")
        ratio = (
            f"(DCGM_FI_DEV_FB_USED{{{ATTR_FILTER}}} "
            f"/ (DCGM_FI_DEV_FB_USED{{{ATTR_FILTER}}} + DCGM_FI_DEV_FB_FREE{{{ATTR_FILTER}}} "
            f"+ DCGM_FI_DEV_FB_RESERVED{{{ATTR_FILTER}}}) * 100)"
        )
        self.assertIn(
            f"(container_mem_utilization_percentage{{{FILTER}}} or {ratio})",
            meta.meta_prom_with_container_mem_utilization_percentage,
        )

    def test_namespace_level_keeps_workload_join_free_shape(self):
        # namespace 层走自身 tpl(无 workload join),双源叶子直接落在 sum by (namespace) 内
        meta = K8sNamespaceMeta(2, "BCS-K8S-00000")
        self.assertEqual(
            meta.meta_prom_with_container_gpu_utilization,
            f"sum by (namespace) ((container_gpu_utilization{{{FILTER}}} or DCGM_FI_DEV_GPU_UTIL{{{ATTR_FILTER}}}))",
        )

    def test_namespace_dcgm_branch_excludes_unattributed_cards(self):
        # 回归护栏:namespace 层无 workload-join,dcgm 支必须带 pod_name!="" 排除空闲卡(否则空闲卡按
        # dcgm-exporter 自身 kube-system 命名空间漏入,产出原生从不产出的伪造行)。6 个指标都要带护栏。
        meta = K8sNamespaceMeta(2, "BCS-K8S-00000")
        for metric_id in CONTAINER_GPU_METRIC_IDS:
            promql = getattr(meta, f"meta_prom_with_{metric_id}")
            # dcgm 支(DCGM_FI_*)出现处必带 pod_name!="";原生支(container_*)不带,保持干净
            self.assertIn("DCGM_FI_DEV", promql, f"{metric_id} 缺 dcgm 支")
            self.assertNotIn(f"DCGM_FI_DEV_GPU_UTIL{{{FILTER}}}", promql, f"{metric_id} dcgm 支漏了 pod_name 护栏")
            self.assertNotIn(f"DCGM_FI_DEV_FB_USED{{{FILTER}}}", promql, f"{metric_id} dcgm 支漏了 pod_name 护栏")
