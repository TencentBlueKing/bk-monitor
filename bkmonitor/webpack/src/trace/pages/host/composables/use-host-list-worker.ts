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

import { onScopeDispose, shallowRef, toRaw } from 'vue';

import { useDebounceFn } from '@vueuse/core';

import workerSource from '../workers/host-list.worker.raw.js?raw';

import type { IValue, IWhereItem } from '../../../components/retrieval-filter/typing';
import type { EHostQuickCategory, IHostListRow, IHostQuickCardStats } from '../types/host-list';
import type { IHostMetricInfo } from '../types/host';
import type { IHostBaseInfo } from '../types/host';
import type { IHostTopoTreeNode } from '../types/topo';

export interface IHostListComputeParams {
  activeCategory: EHostQuickCategory | '';
  keyword: string;
  page: number;
  pageSize: number;
  selectedNode: IHostTopoTreeNode | null;
  sortInfo: string;
  where: IWhereItem[];
}

type WorkerResponse =
  | { filterOptionsMap: Record<string, IValue[]>; rawRowCount: number; requestId: number; type: 'INIT_BASE_DONE' }
  | { filterOptionsMap: Record<string, IValue[]>; requestId: number; type: 'MERGE_METRICS_DONE' }
  | {
      categoryStats: IHostQuickCardStats;
      pagedRows: IHostListRow[];
      requestId: number;
      total: number;
      type: 'COMPUTE_DONE';
    }
  | { requestId: number; result: { count: number; list: IValue[] }; type: 'GET_FILTER_OPTIONS_DONE' }
  | { ips: string[]; requestId: number; type: 'GET_SELECTED_IPS_DONE' };

/** Worker postMessage 仅接受可结构化克隆的纯对象，需剥离 Vue 响应式代理 */
const cloneWorkerPayload = <T>(value: T): T => JSON.parse(JSON.stringify(toRaw(value)));

/** 拓扑节点仅传 Worker 过滤所需字段，避免克隆整棵子树 */
const serializeTopoNodeForWorker = (node: IHostTopoTreeNode | null) => {
  if (!node) {
    return null;
  }
  const raw = toRaw(node) as IHostTopoTreeNode & { bk_host_id?: number; bk_obj_id?: string };
  return {
    bk_host_id: raw.bk_host_id,
    bk_obj_id: raw.bk_obj_id,
    id: raw.id,
  };
};

const serializeComputeParams = (params: IHostListComputeParams) => ({
  activeCategory: params.activeCategory,
  keyword: params.keyword,
  page: params.page,
  pageSize: params.pageSize,
  selectedNode: serializeTopoNodeForWorker(params.selectedNode),
  sortInfo: params.sortInfo,
  where: cloneWorkerPayload(params.where),
});

/** 通过 Blob URL 创建 Worker，避免微前端 / webpack worker chunk 的跨域与 publicPath 问题 */
const createBlobWorker = (): Worker => {
  const blob = new Blob([workerSource], { type: 'application/javascript' });
  const url = URL.createObjectURL(blob);
  const instance = new Worker(url);
  instance.addEventListener('error', () => {
    URL.revokeObjectURL(url);
  });
  return instance;
};

/**
 * @description 主机列表 Worker 客户端：将行转换、过滤、排序、分页、候选项构建等重计算
 * 放到独立线程，主线程仅持有当前页数据与轻量状态。
 */
export const useHostListWorker = () => {
  const worker = shallowRef<Worker | null>(null);
  let requestSeq = 0;
  let latestComputeId = 0;
  const pendingRequests = new Map<number, { reject: (reason?: unknown) => void; resolve: (value: unknown) => void }>();

  const ensureWorker = () => {
    if (worker.value) {
      return worker.value;
    }
    const instance = createBlobWorker();
    instance.onmessage = (event: MessageEvent<WorkerResponse>) => {
      const data = event.data;
      if (data.type === 'COMPUTE_DONE') {
        if (data.requestId !== latestComputeId) {
          return;
        }
        onComputeDone?.(data);
        return;
      }
      const pending = pendingRequests.get(data.requestId);
      if (!pending) {
        return;
      }
      pendingRequests.delete(data.requestId);
      pending.resolve(data);
    };
    instance.onerror = error => {
      for (const { reject } of pendingRequests.values()) {
        reject(error);
      }
      pendingRequests.clear();
    };
    worker.value = instance;
    return instance;
  };

  const postRequest = <T extends WorkerResponse>(payload: Record<string, unknown>): Promise<T> => {
    const requestId = ++requestSeq;
    return new Promise((resolve, reject) => {
      pendingRequests.set(requestId, { resolve: resolve as (value: unknown) => void, reject });
      try {
        ensureWorker().postMessage(cloneWorkerPayload({ ...payload, requestId }));
      } catch (error) {
        pendingRequests.delete(requestId);
        reject(error);
      }
    });
  };

  let onComputeDone: ((data: Extract<WorkerResponse, { type: 'COMPUTE_DONE' }>) => void) | null = null;

  const setComputeHandler = (handler: (data: Extract<WorkerResponse, { type: 'COMPUTE_DONE' }>) => void) => {
    onComputeDone = handler;
  };

  const initBaseData = (baseList: IHostBaseInfo[]) =>
    postRequest<Extract<WorkerResponse, { type: 'INIT_BASE_DONE' }>>({
      baseList,
      type: 'INIT_BASE',
    });

  const mergeMetrics = (metricListMap: Record<string, IHostMetricInfo>) =>
    postRequest<Extract<WorkerResponse, { type: 'MERGE_METRICS_DONE' }>>({
      metricListMap,
      type: 'MERGE_METRICS',
    });

  const computeNow = (params: IHostListComputeParams) => {
    latestComputeId = ++requestSeq;
    ensureWorker().postMessage({
      params: serializeComputeParams(params),
      requestId: latestComputeId,
      type: 'COMPUTE',
    });
  };

  const scheduleCompute = useDebounceFn((params: IHostListComputeParams) => {
    computeNow(params);
  }, 150);

  const getFilterOptions = (field: string, search: string, limit: number) =>
    postRequest<Extract<WorkerResponse, { type: 'GET_FILTER_OPTIONS_DONE' }>>({
      field,
      limit,
      search,
      type: 'GET_FILTER_OPTIONS',
    });

  const getFilterOptionsMap = () =>
    postRequest<Extract<WorkerResponse, { type: 'GET_FILTER_OPTIONS_MAP_DONE' }>>({
      type: 'GET_FILTER_OPTIONS_MAP',
    });

  const getSelectedIps = (rowKeys: string[]) =>
    postRequest<Extract<WorkerResponse, { type: 'GET_SELECTED_IPS_DONE' }>>({
      rowKeys,
      type: 'GET_SELECTED_IPS',
    });

  onScopeDispose(() => {
    worker.value?.terminate();
    worker.value = null;
    pendingRequests.clear();
  });

  return {
    computeNow,
    getFilterOptions,
    getSelectedIps,
    initBaseData,
    mergeMetrics,
    scheduleCompute,
    setComputeHandler,
    getFilterOptionsMap,
  };
};
