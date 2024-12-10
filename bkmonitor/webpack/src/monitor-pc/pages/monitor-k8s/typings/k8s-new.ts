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
   * @description: container - 容器
   */
  CONTAINER = 'container',
  /**
   * @description: cpu - CPU使用率
   */
  CPU = 'cpu',
  /**
   * @description: internal_memory - 内存使用率
   */
  INTERNAL_MEMORY = 'internal_memory',
  /**
   * @description: namespace - namespace
   */
  NAMESPACE = 'namespace',
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

export type SceneType = 'performance';
export interface GroupListItem {
  id: string;
  name: string;
  count?: number;
  hasMore?: boolean;
  children?: GroupListItem[];
  [key: string]: any;
}

export interface K8sDimensionParams {
  scene: SceneType;
  keyword: string;
  pageSize?: number;
}
