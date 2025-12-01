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

import type { K8sBasePromqlGeneratorContext } from '../../typing';

/**
 * @class K8sPerformancePromqlGenerator K8s 性能场景 Promql生成器
 * @description K8s性能图表数据查询Promql生成器
 */
export class K8sPerformancePromqlGenerator extends K8sBasePromqlGenerator {
  readonly promqlGenerateScene = SceneEnum.Performance;

  scenePrivatePromqlGenerateMain(metric: string, context: K8sBasePromqlGeneratorContext): string {
    switch (metric) {
      case 'container_cpu_usage_seconds_total': // CPU使用量
        return `${K8sBasePromqlGenerator.createCommonPromqlMethod(context)}(rate(${metric}{${K8sBasePromqlGenerator.createCommonPromqlContent(context)}}[$interval] $time_shift))`;
      case 'container_network_receive_bytes_total': // 网络入带宽
      case 'container_network_transmit_bytes_total': // 网络出带宽
        return `${K8sBasePromqlGenerator.createCommonPromqlMethod(context)}(rate(${metric}{${K8sBasePromqlGenerator.createCommonPromqlContent(context, false, false)}}[$interval] $time_shift))`;
      case 'kube_pod_cpu_limits_ratio': // CPU limit使用率
        if (context.groupByField === K8sTableColumnKeysEnum.WORKLOAD)
          return `$method by (workload_kind, workload_name)(rate(container_cpu_usage_seconds_total{${K8sBasePromqlGenerator.createCommonPromqlContent(context)},container_name!="POD"}[1m] $time_shift)) / ${K8sBasePromqlGenerator.createWorkLoadRequestOrLimit(context, true)}`;
        return `${K8sBasePromqlGenerator.createCommonPromqlMethod(context)}(rate(${'container_cpu_usage_seconds_total'}{${K8sBasePromqlGenerator.createCommonPromqlContent(context)}}[$interval] $time_shift)) / ${K8sBasePromqlGenerator.createCommonPromqlMethod(context)}(kube_pod_container_resource_limits_cpu_cores{${K8sBasePromqlGenerator.createCommonPromqlContent(context)}} $time_shift)`;
      case 'container_cpu_cfs_throttled_ratio': // CPU 限流占比
        return `${K8sBasePromqlGenerator.createCommonPromqlMethod(context)}((increase(container_cpu_cfs_throttled_periods_total{${K8sBasePromqlGenerator.createCommonPromqlContent(context)}}[$interval] $time_shift) / increase(container_cpu_cfs_periods_total{${K8sBasePromqlGenerator.createCommonPromqlContent(context)}}[$interval] $time_shift)))`;
      case 'kube_pod_cpu_requests_ratio': // CPU request使用率
        if (context.groupByField === K8sTableColumnKeysEnum.WORKLOAD)
          return `$method by (workload_kind, workload_name)(rate(container_cpu_usage_seconds_total{${K8sBasePromqlGenerator.createCommonPromqlContent(context)},container_name!="POD"}[1m] $time_shift)) / ${K8sBasePromqlGenerator.createWorkLoadRequestOrLimit(context, false)}`;
        return `${K8sBasePromqlGenerator.createCommonPromqlMethod(context)}(rate(${'container_cpu_usage_seconds_total'}{${K8sBasePromqlGenerator.createCommonPromqlContent(context)}}[$interval] $time_shift)) / ${K8sBasePromqlGenerator.createCommonPromqlMethod(context)}(kube_pod_container_resource_requests_cpu_cores{${K8sBasePromqlGenerator.createCommonPromqlContent(context)}} $time_shift)`;
      case 'container_memory_working_set_bytes': // 内存使用量(rss)
        return `${K8sBasePromqlGenerator.createCommonPromqlMethod(context)}(${metric}{${K8sBasePromqlGenerator.createCommonPromqlContent(context)}} $time_shift)`;
      case 'kube_pod_memory_limits_ratio': // 内存limit使用率
        if (context.groupByField === K8sTableColumnKeysEnum.WORKLOAD)
          return `$method by (workload_kind, workload_name)(container_memory_working_set_bytes{${K8sBasePromqlGenerator.createCommonPromqlContent(context)},container_name!="POD"} $time_shift) / ${K8sBasePromqlGenerator.createWorkLoadRequestOrLimit(context, true, false)}`;
        return `${K8sBasePromqlGenerator.createCommonPromqlMethod(context)}(${'container_memory_working_set_bytes'}{${K8sBasePromqlGenerator.createCommonPromqlContent(context)}} $time_shift) / ${K8sBasePromqlGenerator.createCommonPromqlMethod(context)}(kube_pod_container_resource_limits_memory_bytes{${K8sBasePromqlGenerator.createCommonPromqlContent(context)}} $time_shift)`;
      case 'kube_pod_memory_requests_ratio': // 内存request使用率
        if (context.groupByField === K8sTableColumnKeysEnum.WORKLOAD)
          return `$method by (workload_kind, workload_name)(container_memory_working_set_bytes{${K8sBasePromqlGenerator.createCommonPromqlContent(context)},container_name!="POD"} $time_shift) / ${K8sBasePromqlGenerator.createWorkLoadRequestOrLimit(context, false, false)}`;
        return `${K8sBasePromqlGenerator.createCommonPromqlMethod(context)}(${'container_memory_working_set_bytes'}{${K8sBasePromqlGenerator.createCommonPromqlContent(context)}} $time_shift) / ${K8sBasePromqlGenerator.createCommonPromqlMethod(context)}(kube_pod_container_resource_requests_memory_bytes{${K8sBasePromqlGenerator.createCommonPromqlContent(context)}} $time_shift)`;
      default:
        return '';
    }
  }
}
