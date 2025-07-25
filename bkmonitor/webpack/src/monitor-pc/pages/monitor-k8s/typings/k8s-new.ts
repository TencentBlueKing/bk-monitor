/* eslint-disable perfectionist/sort-enums */
/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
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

import type { TimeRangeType } from '../../../components/time-range/time-range';

export enum EDimensionKey {
  container = 'container',
  namespace = 'namespace',
  pod = 'pod',
  workload = 'workload',
  ingress = 'ingress',
  service = 'service',
  node = 'node',
}
/** 汇聚类型枚举 */
export enum K8sConvergeTypeEnum {
  AVG = 'avg',
  COUNT = 'count',
  MAX = 'max',
  MIN = 'min',
  SUM = 'sum',
}

/**
 * @description: k8s tab类型枚举
 */
export enum K8sNewTabEnum {
  /**
   * @description: 图表
   */
  CHART = 'chart',
  /**
   * @description: 数据明细
   */
  DETAIL = 'detail',
  /**
   * @description: 列表
   */
  LIST = 'list',
}

/**
 * @enum: k8s table column keys 枚举 (方便后期字段名维护)
 */
export enum K8sTableColumnKeysEnum {
  /**
   * @description: cluster - 集群
   */
  CLUSTER = 'cluster',
  /**
   * @description: namespace - namespace
   */
  NAMESPACE = 'namespace',
  /**
   * @description: container - 容器
   */
  CONTAINER = 'container',
  /**
   * @description: pod - pod
   */
  POD = 'pod',
  /**
   * @description: workload - workload
   */
  WORKLOAD = 'workload',
  /**
   * @description: workload_kind - workload_kind
   */
  WORKLOAD_KIND = 'workload_kind',
  /**
   * @description: ingress - 网络 场景特有维度字段
   */
  INGRESS = 'ingress',
  /**
   * @description: service - 网络 场景特有维度字段
   */
  SERVICE = 'service',
  /**
   * @description: node - 容量 场景特有维度字段
   */
  NODE = 'node',
  /**
   * @description: container_cpu_usage_seconds_total - CPU使用量
   */
  CPU_USAGE = 'container_cpu_usage_seconds_total',
  /**
   * @description: kube_pod_cpu_requests_ratio - CPU request使用率
   */
  CPU_REQUEST = 'kube_pod_cpu_requests_ratio',
  /**
   * @description: kube_pod_cpu_limits_ratio - CPU limit使用率
   */
  CPU_LIMIT = 'kube_pod_cpu_limits_ratio',
  /**
   * @description: container_cpu_cfs_throttled_ratio - CPU 限流占比
   */
  CPU_THROTTLED = 'container_cpu_cfs_throttled_ratio',
  /**
   * @description: container_memory_working_set_bytes - 内存使用量(rss)
   */
  MEMORY_RSS = 'container_memory_working_set_bytes',
  /**
   * @description: kube_pod_memory_requests_ratio - 内存 request使用率
   */
  MEMORY_REQUEST = 'kube_pod_memory_requests_ratio',
  /**
   * @description: kube_pod_memory_limits_ratio - 内存 limit使用率
   */
  MEMORY_LIMIT = 'kube_pod_memory_limits_ratio',
  /**
   * @description: container_network_receive_bytes_total - 网络入带宽
   */
  NETWORK_RECEIVE_BYTES = 'container_network_receive_bytes_total',
  /**
   * @description: container_network_transmit_bytes_total - 网络出带宽
   */
  NETWORK_TRANSMIT_BYTES = 'container_network_transmit_bytes_total',
}

export enum SceneEnum {
  Performance = 'performance',
  Network = 'network',
  Capacity = 'capacity',
}

export interface GroupListItem<T = string> {
  [key: string]: any;
  children?: GroupListItem<T>[];
  count?: number;
  id: T;
  name: string;
  relation?: Record<EDimensionKey, string>; // 关联维度
  showMore?: boolean;
}

export interface ICommonParams {
  bcs_cluster_id: string;
  scenario: SceneEnum;
  timeRange: TimeRangeType;
}

export interface IK8SMetricItem {
  children: IK8SMetricItem[];
  count?: number;
  id: string;
  name: string;
  unit?: string;
  unsupported_resource?: string[];
}

export interface K8sDimensionParams extends ICommonParams {
  page_size: number;
  page_type: 'scrolling' | 'traditional';
  query_string: string;
}

/** 排序类型 */
export type K8sSortType = '' | 'asc' | 'desc';

/** 指标字段 */
export type K8sTableMetricKeys =
  | 'CPU_LIMIT'
  | 'CPU_REQUEST'
  | 'CPU_THROTTLED'
  | 'CPU_USAGE'
  | 'MEMORY_LIMIT'
  | 'MEMORY_REQUEST'
  | 'MEMORY_RSS'
  | 'NETWORK_RECEIVE_BYTES'
  | 'NETWORK_TRANSMIT_BYTES';

export const K8SPerformanceMetricUnitMap = {
  container_cpu_usage_seconds_total: 'short',
  kube_pod_cpu_limits_ratio: 'percentunit',
  kube_pod_cpu_requests_ratio: 'percentunit',
  kube_pod_memory_limits_ratio: 'percentunit',
  kube_pod_memory_requests_ratio: 'percentunit',
  container_memory_working_set_bytes: 'bytes',
};
