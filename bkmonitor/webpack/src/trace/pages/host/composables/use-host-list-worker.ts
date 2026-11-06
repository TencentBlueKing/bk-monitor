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
import type { IHostMetricInfo } from '../types/host';
import type { IHostBaseInfo } from '../types/host';
import type { EHostQuickCategory, IHostListRow, IHostQuickCardStats } from '../types/host-list';
import type { IHostTopoTreeNode } from '../types/topo';

export interface IHostListComputeParams {
  activeCategory: '' | EHostQuickCategory;
  keyword: string;
  page: number;
  pageSize: number;
  selectedNode: IHostTopoTreeNode | null;
  sortInfo: string;
  stickyValue: Record<string, number>;
  where: IWhereItem[];
}

type WorkerResponse =
  | {
      categoryStats: IHostQuickCardStats;
      pagedRows: IHostListRow[];
      requestId: number;
      total: number;
      type: 'COMPUTE_DONE';
    }
  | { filterOptionsMap: Record<string, IValue[]>; rawRowCount: number; requestId: number; type: 'INIT_BASE_DONE' }
  | { filterOptionsMap: Record<string, IValue[]>; requestId: number; type: 'GET_FILTER_OPTIONS_MAP_DONE' }
  | { filterOptionsMap: Record<string, IValue[]>; requestId: number; type: 'MERGE_METRICS_DONE' }
  | { ips: string[]; requestId: number; type: 'GET_SELECTED_IPS_DONE' }
  | { requestId: number; result: { count: number; list: IValue[] }; type: 'GET_FILTER_OPTIONS_DONE' }
  | { requestId: number; rowKeys: string[]; type: 'GET_FILTERED_ROW_KEYS_DONE' }
  | { requestId: number; rows: IHostListRow[]; type: 'GET_SELECTED_ROWS_DONE' };

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
  stickyValue: cloneWorkerPayload(params.stickyValue),
  where: cloneWorkerPayload(params.where),
});

/** 通过 Blob URL 创建 Worker，避免微前端 / webpack worker chunk 的跨域与 publicPath 问题 */
const createBlobWorker = (): { instance: Worker; url: string } => {
  const blob = new Blob([workerSource], { type: 'application/javascript' });
  const url = URL.createObjectURL(blob);
  try {
    return { instance: new Worker(url), url };
  } catch (error) {
    URL.revokeObjectURL(url);
    throw error;
  }
};

/**
 * @description 主机列表 Worker 客户端：将行转换、过滤、排序、分页、候选项构建等重计算
 * 放到独立线程，主线程仅持有当前页数据与轻量状态。
 */
export const useHostListWorker = () => {
  const worker = shallowRef<null | Worker>(null);
  let workerUrl: null | string = null;
  let disposed = false;
  let requestSeq = 0;
  let latestComputeId = 0;
  const pendingRequests = new Map<number, { reject: (reason?: unknown) => void; resolve: (value: unknown) => void }>();

  const terminateWorker = () => {
    worker.value?.terminate();
    worker.value = null;
    if (workerUrl) URL.revokeObjectURL(workerUrl);
    workerUrl = null;
  };

  const ensureWorker = () => {
    if (disposed) throw new Error('Host list worker disposed');
    if (worker.value) {
      return worker.value;
    }
    const { instance, url } = createBlobWorker();
    workerUrl = url;
    instance.onmessage = (event: MessageEvent<WorkerResponse>) => {
      const data = event.data;
      const pending = pendingRequests.get(data.requestId);
      if (pending) {
        pendingRequests.delete(data.requestId);
        pending.resolve(data);
        return;
      }
      if (data.type === 'COMPUTE_DONE') {
        if (data.requestId !== latestComputeId) {
          return;
        }
        onComputeDone?.(data);
        return;
      }
    };
    instance.onerror = error => {
      terminateWorker();
      for (const { reject } of pendingRequests.values()) {
        reject(error);
      }
      pendingRequests.clear();
    };
    worker.value = instance;
    return instance;
  };

  const postRequest = <T extends WorkerResponse>(payload: Record<string, unknown>, clonePayload = true): Promise<T> => {
    const requestId = ++requestSeq;
    return new Promise((resolve, reject) => {
      pendingRequests.set(requestId, { resolve: resolve as (value: unknown) => void, reject });
      try {
        const message = { ...payload, requestId };
        ensureWorker().postMessage(clonePayload ? cloneWorkerPayload(message) : message);
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
    // HTTP JSON 响应直接结构化克隆，不再为全量数据额外执行 JSON 往返。
    postRequest<Extract<WorkerResponse, { type: 'INIT_BASE_DONE' }>>({ baseList, type: 'INIT_BASE' }, false);

  const mergeMetrics = (metricListMap: Record<string, IHostMetricInfo>) =>
    postRequest<Extract<WorkerResponse, { type: 'MERGE_METRICS_DONE' }>>(
      { metricListMap, type: 'MERGE_METRICS' },
      false
    );

  /** 调用方按自己的数据与视图代次接替结果，计算异常通过 Promise 传播。 */
  const compute = (params: IHostListComputeParams) =>
    postRequest<Extract<WorkerResponse, { type: 'COMPUTE_DONE' }>>(
      { params: serializeComputeParams(params), type: 'COMPUTE' },
      false
    );

  const computeNow = (params: IHostListComputeParams) => {
    if (disposed) return;
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
  /** 按选中行 key 取完整行数据（用于复制指定 IP 字段） */
  const getSelectedRows = (rowKeys: string[]) =>
    postRequest<Extract<WorkerResponse, { type: 'GET_SELECTED_ROWS_DONE' }>>({
      rowKeys,
      type: 'GET_SELECTED_ROWS',
    });

  /** 跨页全选：取当前过滤条件下的全量行 key（与表格 rowKey=id 一致） */
  const getFilteredRowKeys = (params: IHostListComputeParams) =>
    postRequest<Extract<WorkerResponse, { type: 'GET_FILTERED_ROW_KEYS_DONE' }>>({
      params: serializeComputeParams(params),
      type: 'GET_FILTERED_ROW_KEYS',
    });

  onScopeDispose(() => {
    disposed = true;
    terminateWorker();
    for (const { reject } of pendingRequests.values()) {
      reject(new Error('Host list worker disposed'));
    }
    pendingRequests.clear();
  });

  return {
    compute,
    computeNow,
    getFilterOptions,
    getFilteredRowKeys,
    getSelectedIps,
    initBaseData,
    mergeMetrics,
    scheduleCompute,
    setComputeHandler,
    getFilterOptionsMap,
    getSelectedRows,
  };
};
