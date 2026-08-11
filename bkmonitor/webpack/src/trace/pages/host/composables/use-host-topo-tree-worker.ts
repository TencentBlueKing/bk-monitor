/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import { onScopeDispose, shallowRef, toRaw } from 'vue';

import workerSource from '../workers/host-topo-tree.worker.raw.js?raw';

import type { IHostTopoHostNode, IHostTopoInstNode, IHostTopoTreeNode } from '../types';

export type IHostTopoViewRow = (IHostTopoHostNode | Omit<IHostTopoInstNode, 'children'>) & {
  depth: number;
  hasChildren: boolean;
  hostCount: number;
  isExpanded: boolean;
};

interface IWorkerViewResult {
  rows: IHostTopoViewRow[];
  total: number;
}

type WorkerResponse =
  | (IWorkerViewResult & {
      requestId: number;
      type: 'COLLAPSE_ALL_DONE' | 'EXPAND_ALL_DONE' | 'GET_RANGE_DONE' | 'SET_FILTER_DONE' | 'TOGGLE_DONE';
    })
  | {
      nodeCount: number;
      requestId: number;
      /** 选中的拓扑节点数据 */
      selectedNode: IHostTopoTreeNode | null;
      /** 选中节点在可视列表中的偏移行号（用于虚拟滚动聚焦定位，-1 表示未找到） */
      selectedNodeOffset: number;
      total: number;
      type: 'INIT_DONE';
    };

/** 创建 Blob Worker */
const createBlobWorker = () => {
  const blob = new Blob([workerSource], { type: 'application/javascript' });
  const url = URL.createObjectURL(blob);
  const worker = new Worker(url);
  return { url, worker };
};

/**
 * 拓扑树 Worker 客户端。Worker 持有全量索引，主线程只获取可视区切片。
 */
export const useHostTopoTreeWorker = () => {
  const workerRef = shallowRef<null | Worker>(null);
  let workerUrl = '';
  let requestSeq = 0;
  const pendingRequests = new Map<number, { reject: (reason?: unknown) => void; resolve: (value: unknown) => void }>();

  /** 确保 Worker 实例 */
  const ensureWorker = () => {
    if (workerRef.value) {
      return workerRef.value;
    }
    const { url, worker } = createBlobWorker();
    workerUrl = url;
    worker.onmessage = (event: MessageEvent<WorkerResponse>) => {
      const pending = pendingRequests.get(event.data.requestId);
      if (!pending) {
        return;
      }
      pendingRequests.delete(event.data.requestId);
      pending.resolve(event.data);
    };
    worker.onerror = error => {
      for (const pending of pendingRequests.values()) {
        pending.reject(error);
      }
      pendingRequests.clear();
    };
    workerRef.value = worker;
    return worker;
  };

  /** 发送请求 */
  const postRequest = <T extends WorkerResponse>(payload: Record<string, unknown>): Promise<T> => {
    const requestId = ++requestSeq;
    return new Promise((resolve, reject) => {
      pendingRequests.set(requestId, { reject, resolve: resolve as (value: unknown) => void });
      try {
        ensureWorker().postMessage({ ...payload, requestId });
      } catch (error) {
        pendingRequests.delete(requestId);
        reject(error);
      }
    });
  };

  /** 初始化 */
  const init = (treeData: IHostTopoTreeNode[], hideEmptyNode: boolean, searchValue: string, selectedId: string) =>
    postRequest<Extract<WorkerResponse, { type: 'INIT_DONE' }>>({
      hideEmptyNode,
      searchValue,
      selectedId,
      treeData: toRaw(treeData),
      type: 'INIT',
    });

  /** 获取可视区切片 */
  const getRange = (start: number, end: number) =>
    postRequest<Extract<WorkerResponse, { type: 'GET_RANGE_DONE' }>>({
      end,
      start,
      type: 'GET_RANGE',
    });

  /** 设置过滤条件 */
  const setFilter = (hideEmptyNode: boolean, searchValue: string, start: number, end: number) =>
    postRequest<Extract<WorkerResponse, { type: 'SET_FILTER_DONE' }>>({
      end,
      hideEmptyNode,
      searchValue,
      start,
      type: 'SET_FILTER',
    });

  /** 切换节点展开状态 */
  const toggle = (id: string, expanded: boolean, start: number, end: number) =>
    postRequest<Extract<WorkerResponse, { type: 'TOGGLE_DONE' }>>({
      end,
      expanded,
      id,
      start,
      type: 'TOGGLE',
    });

  /** 折叠所有节点 */
  const collapseAll = (start: number, end: number) =>
    postRequest<Extract<WorkerResponse, { type: 'COLLAPSE_ALL_DONE' }>>({
      end,
      start,
      type: 'COLLAPSE_ALL',
    });

  /** 展开所有节点 */
  const expandAll = (start: number, end: number) =>
    postRequest<Extract<WorkerResponse, { type: 'EXPAND_ALL_DONE' }>>({
      end,
      start,
      type: 'EXPAND_ALL',
    });

  /** 销毁 Worker */
  onScopeDispose(() => {
    workerRef.value?.terminate();
    workerRef.value = null;
    pendingRequests.clear();
    if (workerUrl) {
      URL.revokeObjectURL(workerUrl);
      workerUrl = '';
    }
  });

  return {
    collapseAll,
    expandAll,
    getRange,
    init,
    setFilter,
    toggle,
  };
};
