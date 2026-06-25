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
    // GPU 指标写死聚合方法的 case 使用：node 层级按 node 分线，cluster 层级聚合到 bcs_cluster_id（序列上不存在 cluster label）
    const gpuByDim = context.groupByField === K8sTableColumnKeysEnum.NODE ? 'node' : 'bcs_cluster_id';
    switch (metric) {
      case 'node_cpu_seconds_total': // 节点CPU使用量
        return `${K8sBasePromqlGenerator.createCommonPromqlMethod(context)}(last_over_time(rate(node_cpu_seconds_total{${K8sBasePromqlGenerator.createCommonPromqlContent(context)},mode!="idle"}[$interval])[$interval:] $time_shift))`;
      case 'node_cpu_capacity_ratio': // 节点CPU装箱率（含原生 sidecar：常规容器 request + 运行中的 restartable-init request，用 status_running==1 近似识别 sidecar）
        return `${K8sBasePromqlGenerator.createCommonPromqlMethod(context)}(sum by (${context.groupByField},pod) (kube_pod_container_resource_requests{${K8sBasePromqlGenerator.createCommonPromqlContent(context)},container_name!="POD",resource="cpu"}
 or
 (kube_pod_init_container_resource_requests{${K8sBasePromqlGenerator.createCommonPromqlContent(context)},container_name!="POD",resource="cpu"} * on(namespace,pod,container) group_left() (kube_pod_init_container_status_running{bcs_cluster_id="${clusterId}"}==1)))
 /
 on (pod) group_left() count(count by (pod)(kube_pod_status_phase{bcs_cluster_id="${clusterId}",phase!="Evicted"})) by(pod))
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

      case 'node_memory_capacity_ratio': // 节点内存装箱率（含原生 sidecar：常规容器 request + 运行中的 restartable-init request，用 status_running==1 近似识别 sidecar）
        return `${K8sBasePromqlGenerator.createCommonPromqlMethod(context)} (sum by (${context.groupByField},pod) (kube_pod_container_resource_requests{${K8sBasePromqlGenerator.createCommonPromqlContent(context)},container_name!="POD",resource="memory"}
 or
 (kube_pod_init_container_resource_requests{${K8sBasePromqlGenerator.createCommonPromqlContent(context)},container_name!="POD",resource="memory"} * on(namespace,pod,container) group_left() (kube_pod_init_container_status_running{bcs_cluster_id="${clusterId}"}==1)))
 /
 on (pod) group_left() count(count by (pod)(kube_pod_status_phase{bcs_cluster_id="${clusterId}",phase!="Evicted"})) by(pod))
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
      case 'node_gpu_usage_ratio': // GPU使用率（卡级算力使用率均值，聚合写死 avg；数据源 elastic-gpu-exporter 卡级指标）
        return `avg by(${gpuByDim})(last_over_time(gpu_core_utilization_percentage{${K8sBasePromqlGenerator.createCommonPromqlContent(context)}}[$interval:] $time_shift))`;
      case 'node_gpu_mem_usage_ratio': // GPU显存使用率 = sum(已用显存)/sum(单卡总显存)*100，加权口径
        return `sum by(${gpuByDim})(last_over_time(gpu_mem_usage{${K8sBasePromqlGenerator.createCommonPromqlContent(context)}}[$interval:] $time_shift))
 /
 sum by(${gpuByDim})(last_over_time(gpu_mem_each_card{${K8sBasePromqlGenerator.createCommonPromqlContent(context)}}[$interval:] $time_shift)) * 100`;
      case 'node_gpu_mem_used': // GPU显存使用量（原始数据为MiB）
        return `${K8sBasePromqlGenerator.createCommonPromqlMethod(context)}(last_over_time(gpu_mem_usage{${K8sBasePromqlGenerator.createCommonPromqlContent(context)}}[$interval:] $time_shift))`;
      case 'node_gpu_power_usage': // GPU功耗（单位W）
        return `${K8sBasePromqlGenerator.createCommonPromqlMethod(context)}(last_over_time(gpu_power_usage{${K8sBasePromqlGenerator.createCommonPromqlContent(context)}}[$interval:] $time_shift))`;
      case 'node_gpu_temperature': // GPU温度（最高卡温，聚合写死 max；gpu_temprature 为 exporter 原始拼写）
        return `max by(${gpuByDim})(last_over_time(gpu_temprature{${K8sBasePromqlGenerator.createCommonPromqlContent(context)}}[$interval:] $time_shift))`;
      case 'node_gpu_anomaly_count': {
        // GPU异常数 = ECC错误增量(counter_type="aggregate"累计计数) + 掉卡数(gpu_count 对 1d 基线的下降)
        // or 兜底防空向量：exporter 静默的 GPU 节点按全卡掉卡计入；合法摘卡在基线滚动过期(1d)前会被计为掉卡
        const content = K8sBasePromqlGenerator.createCommonPromqlContent(context);
        if (context.groupByField === K8sTableColumnKeysEnum.NODE) {
          const baseline = `max by(node)(max_over_time(gpu_count{${content}}[1d] $time_shift))`;
          const current = `max by(node)(last_over_time(gpu_count{${content}}[$interval:] $time_shift))`;
          return `(sum by(node)(last_over_time(increase(gpu_ecc_error_count{${content},counter_type="aggregate"}[$interval])[$interval:] $time_shift)) or ${baseline} * 0)
 +
 clamp_min(${baseline} - (${current} or ${baseline} * 0), 0)`;
        }
        // cluster 层级：掉卡按 (bcs_cluster_id,node) 粒度求差后再 sum，避免集群级 max 折叠节点掩盖掉卡
        const baseline = `max by(bcs_cluster_id,node)(max_over_time(gpu_count{${content}}[1d] $time_shift))`;
        const current = `max by(bcs_cluster_id,node)(last_over_time(gpu_count{${content}}[$interval:] $time_shift))`;
        return `sum by(bcs_cluster_id)((sum by(bcs_cluster_id,node)(last_over_time(increase(gpu_ecc_error_count{${content},counter_type="aggregate"}[$interval])[$interval:] $time_shift)) or ${baseline} * 0)
 +
 clamp_min(${baseline} - (${current} or ${baseline} * 0), 0))`;
      }
      default:
        return '';
    }
  }
}
