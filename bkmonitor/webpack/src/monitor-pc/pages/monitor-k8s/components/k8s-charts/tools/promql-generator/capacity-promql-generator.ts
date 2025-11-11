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
 * @class K8sCapacityPromqlGenerator K8s 容量场景 Promql生成器
 * @description K8s容量图表数据查询Promql生成器
 */
export class K8sCapacityPromqlGenerator extends K8sBasePromqlGenerator {
  readonly promqlGenerateScene = SceneEnum.Capacity;

  scenePrivatePromqlGenerateMain(metric: string, context: K8sBasePromqlGeneratorContext): string {
    const clusterId = context.bcs_cluster_id;
    switch (metric) {
      case 'node_cpu_seconds_total': // 节点CPU使用量
        return `${K8sBasePromqlGenerator.createCommonPromqlMethod(context)}(last_over_time(rate(node_cpu_seconds_total{${K8sBasePromqlGenerator.createCommonPromqlContent(context)},mode!="idle"}[$interval])[$interval:] $time_shift))`;
      case 'node_cpu_capacity_ratio': // 节点CPU装箱率
        return `${K8sBasePromqlGenerator.createCommonPromqlMethod(context)}(sum by (${context.groupByField},pod) (kube_pod_container_resource_requests{${K8sBasePromqlGenerator.createCommonPromqlContent(context)},container_name!="POD",resource="cpu"})
 /
 on (pod) group_left() count by (pod)(kube_pod_status_phase{bcs_cluster_id="${clusterId}",phase!="Evicted"}))
/
${K8sBasePromqlGenerator.createCommonPromqlMethod(context)} (kube_node_status_allocatable{${K8sBasePromqlGenerator.createCommonPromqlContent(context)},container_name!="POD",resource="cpu"})`;
      case 'node_cpu_usage_ratio': // 节点CPU使用率
        if (context.groupByField === K8sTableColumnKeysEnum.NODE) {
          return `(1 - avg by(node)(rate(node_cpu_seconds_total{mode="idle",${K8sBasePromqlGenerator.createCommonPromqlContent(context)}}[$interval] $time_shift))) * 100`;
        }
        return `(1 - avg by(bcs_cluster_id)(rate(node_cpu_seconds_total{mode="idle",${K8sBasePromqlGenerator.createCommonPromqlContent(context)}}[$interval] $time_shift))) * 100`;
      case 'node_memory_working_set_bytes': // 节点内存使用量
        return ` ${K8sBasePromqlGenerator.createCommonPromqlMethod(context)} (last_over_time(node_memory_MemTotal_bytes{${K8sBasePromqlGenerator.createCommonPromqlContent(context)}}[$interval:] $time_shift))
        -
       ${K8sBasePromqlGenerator.createCommonPromqlMethod(context)} (last_over_time(node_memory_MemAvailable_bytes{${K8sBasePromqlGenerator.createCommonPromqlContent(context)}}[$interval:] $time_shift))`;

      case 'node_memory_capacity_ratio': // 节点内存装箱率
        return `${K8sBasePromqlGenerator.createCommonPromqlMethod(context)} (sum by (${context.groupByField},pod) (kube_pod_container_resource_requests{${K8sBasePromqlGenerator.createCommonPromqlContent(context)},container_name!="POD",resource="memory"})
 /
 on (pod) group_left() count by (pod)(kube_pod_status_phase{bcs_cluster_id="${clusterId}",phase!="Evicted"}))
/
${K8sBasePromqlGenerator.createCommonPromqlMethod(context)}  (kube_node_status_allocatable{${K8sBasePromqlGenerator.createCommonPromqlContent(context)},container_name!="POD",resource="memory"})`;
      case 'node_memory_usage_ratio': // 节点内存使用率
        return ` (
        1 - (
          ${K8sBasePromqlGenerator.createCommonPromqlMethod(context)} (last_over_time(node_memory_MemAvailable_bytes{${K8sBasePromqlGenerator.createCommonPromqlContent(context)}}[$interval:] $time_shift))
          /
          ${K8sBasePromqlGenerator.createCommonPromqlMethod(context)} (last_over_time(node_memory_MemTotal_bytes{${K8sBasePromqlGenerator.createCommonPromqlContent(context)}}[$interval:] $time_shift))
          )
        )`;
      case 'master_node_count': // 集群Master节点计数
        return `count by(bcs_cluster_id)($method by(node, bcs_cluster_id)(kube_node_role{bcs_cluster_id="${clusterId}",role=~"master|control-plane"} $time_shift))`;
      case 'worker_node_count': // 集群Worker节点计数
        return `count by(bcs_cluster_id)(kube_node_labels{bcs_cluster_id="${clusterId}"} $time_shift)
         -
         count(sum by (node, bcs_cluster_id)(kube_node_role{bcs_cluster_id="${clusterId}",role=~"master|control-plane"} $time_shift))`;

      case 'node_pod_usage': // 节点Pod个数使用率
        return `${K8sBasePromqlGenerator.createCommonPromqlMethod(context)} (last_over_time(kubelet_running_pods{${K8sBasePromqlGenerator.createCommonPromqlContent(context)}}[$interval:] $time_shift))
        /
        ${K8sBasePromqlGenerator.createCommonPromqlMethod(context)}  (last_over_time(kube_node_status_capacity_pods{${K8sBasePromqlGenerator.createCommonPromqlContent(context)}}[$interval:] $time_shift))`;
      case 'node_network_receive_bytes_total': // 节点网络入带宽
        return `${K8sBasePromqlGenerator.createCommonPromqlMethod(context)} (last_over_time(rate(node_network_receive_bytes_total{${K8sBasePromqlGenerator.createCommonPromqlContent(context)},device!~"lo|veth.*"}[$interval])[$interval:] $time_shift))`;
      case 'node_network_transmit_bytes_total': // 节点网络出带宽
        return `${K8sBasePromqlGenerator.createCommonPromqlMethod(context)} (last_over_time(rate(node_network_transmit_bytes_total{${K8sBasePromqlGenerator.createCommonPromqlContent(context)},device!~"lo|veth.*"}[$interval])[$interval:] $time_shift))`;
      case 'node_network_receive_packets_total': // 节点网络入包量
        return `${K8sBasePromqlGenerator.createCommonPromqlMethod(context)} (last_over_time(rate(node_network_receive_packets_total{${K8sBasePromqlGenerator.createCommonPromqlContent(context)},device!~"lo|veth.*"}[$interval])[$interval:] $time_shift))`;
      case 'node_network_transmit_packets_total': // 节点网络出包量
        return `${K8sBasePromqlGenerator.createCommonPromqlMethod(context)} (last_over_time(rate(node_network_transmit_packets_total{${K8sBasePromqlGenerator.createCommonPromqlContent(context)},device!~"lo|veth.*"}[$interval])[$interval:] $time_shift))`;
      default:
        return '';
    }
  }
}
