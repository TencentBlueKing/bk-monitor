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

export enum EDimensionKey {
  container = 'container',
  namespace = 'namespace',
  pod = 'pod',
  workload = 'workload',
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
   * @description: cpu - CPU使用率
   */
  CPU = 'cpu',
  /**
   * @description: mem - 内存使用率
   */
  INTERNAL_MEMORY = 'mem',
  /**
   * @description: pod - pod
   */
  POD = 'pod',
  /**
   * @description: workload - workload
   */
  WORKLOAD = 'workload',
  /**
   * @description: workload_type - workload_type
   */
  WORKLOAD_TYPE = 'workload_type',
}

export enum SceneEnum {
  Performance = 'performance',
}

export interface GroupListItem<T = string> {
  id: T;
  name: string;
  count?: number;
  showMore?: boolean;
  children?: GroupListItem<T>[];
  relation?: Record<EDimensionKey, string>; // 关联维度
  [key: string]: any;
}

export interface K8sDimensionParams extends ICommonParams {
  query_string: string;
  pageSize: number;
  page_type: 'scrolling' | 'traditional';
}

export interface ICommonParams {
  scenario: SceneEnum;
  bcs_cluster_id: string;
  start_time: number;
  end_time: number;
}

export interface IK8SMetricItem {
  id: string;
  name: string;
  count?: number;
  unit?: string;
  children: IK8SMetricItem[];
}

export const K8SPerformanceMetricUnitMap = {
  container_cpu_usage_seconds_total: 'short',
  kube_pod_cpu_limits_ratio: 'percentunit',
  kube_pod_cpu_requests_ratio: 'percentunit',
  kube_pod_memory_limits_ratio: 'percentunit',
  kube_pod_memory_requests_ratio: 'percentunit',
  container_memory_rss: 'bytes',
};
