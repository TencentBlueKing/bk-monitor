/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

import { K8sTableColumnKeysEnum, SceneEnum } from '../../../../typings/k8s-new';
import { K8sBasePromqlGenerator } from './base-promql-generator';
import { gpuOr } from './gpu-dcgm-compat';

import type { K8sBasePromqlGeneratorContext } from '../../typing';

/**
 * GPU 场景指标集合，需与后端 tke_gpu 场景指标列表保持一致
 */
const GPU_METRIC_SET = new Set<string>([
  'container_gpu_utilization',
  'container_gpu_memory_total',
  'container_core_utilization_percentage',
  'container_mem_utilization_percentage',
  'container_request_gpu_memory',
  'container_request_gpu_utilization',
]);

/**
 * @class K8sGpuPromqlGenerator K8s GPU 场景 Promql 生成器
 * @description K8s GPU 图表数据查询 Promql 生成器。
 * GPU 指标自带 namespace / pod_name / container_name 维度，但不带 workload 维度：
 * - 按 namespace / pod / container 聚合时，可直接按对应维度查询；
 * - 按 workload 聚合时，优先关联独立的 pod_with_workload_relation，
 *   未部署新关系指标的集群兼容回退到 container_cpu_usage_seconds_total。
 * 注意 GPU 指标的 pod 维度标签为 pod_name（非 pod），聚合维度需对应。
 */
export class K8sGpuPromqlGenerator extends K8sBasePromqlGenerator {
  readonly promqlGenerateScene = SceneEnum.GPU;

  scenePrivatePromqlGenerateMain(metric: string, context: K8sBasePromqlGeneratorContext): string {
    if (!GPU_METRIC_SET.has(metric)) return '';
    // 按 workload 聚合：新关系按 Pod 优先，旧 CPU 关系仅补新指标尚未覆盖的 Pod，避免双算或关系冲突
    if (context.groupByField === K8sTableColumnKeysEnum.WORKLOAD) {
      const relationDimensions = 'bcs_cluster_id, workload_kind, workload_name, namespace, pod_name';
      const relation = (filter: string) => `max by (${relationDimensions}) (
          label_replace(
            pod_with_workload_relation{${filter}} $time_shift,
            "pod_name", "$1", "pod", "(.+)"
          )
        )`;
      const workloadFilter = K8sBasePromqlGenerator.createCommonPromqlContent(context);
      const namespaceFilter = K8sBasePromqlGenerator.createCommonPromqlContent(context, true);
      return `${K8sBasePromqlGenerator.createCommonPromqlMethod(context)} (
        (
          (${relation(workloadFilter)})
          or (
            (count by (${relationDimensions}) (
              container_cpu_usage_seconds_total{${workloadFilter},container_name!="POD"} $time_shift
            ) * 0 + 1)
            unless on(bcs_cluster_id, namespace, pod_name)
            (${relation(namespaceFilter)})
          )
        )
        * on(bcs_cluster_id, pod_name, namespace) group_right(workload_kind, workload_name)
        sum by (bcs_cluster_id, pod_name, namespace) (
          ${gpuOr(metric, namespaceFilter, ' $time_shift')}
        )
      )`;
    }
    // 按 namespace / pod / container 聚合：GPU 指标自带对应维度，直接查询
    // POD 聚合时基类按 pod 标签聚合，而 GPU 指标 pod 维度为 pod_name，需改写
    const method =
      context.groupByField === K8sTableColumnKeysEnum.POD
        ? '$method by(pod_name)'
        : K8sBasePromqlGenerator.createCommonPromqlMethod(context);
    return `${method} (${gpuOr(metric, K8sBasePromqlGenerator.createCommonPromqlContent(context), ' $time_shift')})`;
  }
}
