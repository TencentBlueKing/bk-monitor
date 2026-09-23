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
import { onScopeDispose, shallowRef } from 'vue';
import type { ShallowRef } from 'vue';

import { getHostInfoList, getHostInfoPage, getHostMetricInfoList, getHostMetricStats } from '../services/host-service';
import { createHostListRow } from '../utils/host-list-core';

import type { IHostBaseInfo, IHostMetricInfo } from '../types/host';
import type { EHostQuickCategory, IHostListRow, IHostQuickCardStats } from '../types/host-list';
import type { HostScopeParams } from '../utils/share-scope';
import type { IHostListComputeParams, useHostListWorker } from './use-host-list-worker';

interface HostListDataOptions {
  page: ShallowRef<number>;
  pageSize: ShallowRef<number>;
  worker: ReturnType<typeof useHostListWorker>;
  getComputeParams: () => IHostListComputeParams;
  getPageScope: () => HostScopeParams;
  getScope: () => HostScopeParams;
  getTimeParams: () => { end_time: number; start_time: number };
}

const emptyStats = (): IHostQuickCardStats => ({ alarm: 0, cpu: 0, disk: 0, mem: 0 });
const emptyCategoryStates = () => ({
  alarm: { loading: true, error: false },
  cpu: { loading: true, error: false },
  disk: { loading: true, error: false },
  mem: { loading: true, error: false },
});

/** 页数据独立展示；全量 Worker 的最新视图及统计一起接替。 */
export const useHostListData = (options: HostListDataOptions) => {
  const loading = shallowRef(false);
  const loadError = shallowRef(false);
  const metricLoading = shallowRef(false);
  const metricLoadError = shallowRef(false);
  const fullDataReady = shallowRef(false);
  const fullLoading = shallowRef(false);
  const fullLoadError = shallowRef(false);
  const rawRowCount = shallowRef(0);
  const total = shallowRef(0);
  const pagedRows = shallowRef<IHostListRow[]>([]);
  const categoryStats = shallowRef(emptyStats());
  const categoryStates = shallowRef(emptyCategoryStates());
  const filterOptionsMap = shallowRef<Record<string, unknown>>({});

  let generation = 0;
  let pageRequest = 0;
  let metricRequest = 0;
  let fullRequest = 0;
  let viewRequest = 0;
  let disposed = false;
  let prepared = false;
  let pageBase: IHostBaseInfo[] = [];
  let fullBase: IHostBaseInfo[] | null = null;
  let fullMetrics: null | Record<string, IHostMetricInfo> = null;
  let fullRowCount = 0;
  let timeParams: ReturnType<HostListDataOptions['getTimeParams']>;
  let fullScope: HostScopeParams;
  const categoryRequests: Record<EHostQuickCategory, number> = { alarm: 0, cpu: 0, disk: 0, mem: 0 };
  const isCurrent = (value: number) => !disposed && generation === value;

  const setCategoryState = (key: EHostQuickCategory, loading: boolean, error: boolean) => {
    categoryStates.value = { ...categoryStates.value, [key]: { loading, error } };
  };

  const retryCategory = async (category: EHostQuickCategory) => {
    if (category === 'alarm' || fullDataReady.value || !timeParams || disposed) return;
    const currentGeneration = generation;
    const requestId = ++categoryRequests[category];
    const isLatest = () =>
      isCurrent(currentGeneration) && requestId === categoryRequests[category] && !fullDataReady.value;
    setCategoryState(category, true, false);
    try {
      const result = await getHostMetricStats({ ...options.getPageScope(), ...timeParams, category });
      if (!isLatest()) return;
      if (!result.complete || result.value === null) {
        setCategoryState(category, false, true);
        return;
      }
      categoryStats.value = { ...categoryStats.value, [category]: result.value };
      setCategoryState(category, false, false);
    } catch {
      if (isLatest()) setCategoryState(category, false, true);
    }
  };

  const loadCategoryStats = () => Promise.all((['cpu', 'mem', 'disk'] as const).map(retryCategory));

  const invalidateView = () => {
    viewRequest += 1;
  };
  const invalidatePage = () => {
    pageRequest += 1;
    metricRequest += 1;
    pageBase = [];
    invalidateView();
  };

  const loadMetricData = async () => {
    if (fullDataReady.value || !timeParams || disposed) return;
    const currentGeneration = generation;
    const currentPage = pageRequest;
    const requestId = ++metricRequest;
    const base = pageBase;
    if (!base.length) return;
    const isLatest = () =>
      isCurrent(currentGeneration) &&
      currentPage === pageRequest &&
      requestId === metricRequest &&
      !fullDataReady.value;
    metricLoading.value = true;
    metricLoadError.value = false;
    try {
      const metrics = await getHostMetricInfoList({
        ...fullScope,
        ...timeParams,
        bk_host_ids: base.map(row => row.bk_host_id),
      });
      if (isLatest()) pagedRows.value = base.map(row => createHostListRow(row, metrics[row.bk_host_id]));
    } catch {
      if (isLatest()) metricLoadError.value = true;
    } finally {
      if (isLatest()) metricLoading.value = false;
    }
  };

  const loadPageData = async () => {
    if (fullDataReady.value || !timeParams || disposed) return;
    const currentGeneration = generation;
    const requestId = ++pageRequest;
    metricRequest += 1;
    pageBase = [];
    loading.value = true;
    loadError.value = false;
    metricLoading.value = true;
    metricLoadError.value = false;
    const isLatest = () => isCurrent(currentGeneration) && requestId === pageRequest && !fullDataReady.value;
    try {
      const result = await getHostInfoPage({
        ...options.getPageScope(),
        page: options.page.value,
        page_size: options.pageSize.value,
      });
      if (!isLatest()) return;
      const lastPage = Math.max(1, Math.ceil(result.total / options.pageSize.value));
      if (options.page.value > lastPage) {
        options.page.value = lastPage;
        return;
      }
      pageBase = result.items;
      total.value = result.total;
      rawRowCount.value = result.total;
      pagedRows.value = result.items.map(row => createHostListRow(row));
      loading.value = false;
      metricLoading.value = result.items.length > 0;
      await loadMetricData();
    } catch {
      if (!isLatest()) return;
      pagedRows.value = [];
      loadError.value = true;
      loading.value = false;
      metricLoading.value = false;
    }
  };

  const refreshList = async () => {
    const requestId = ++viewRequest;
    if (!prepared || disposed) return;
    const currentGeneration = generation;
    const params = options.getComputeParams();
    const isLatest = () => isCurrent(currentGeneration) && requestId === viewRequest && prepared;
    try {
      const result = await options.worker.compute(params);
      if (!isLatest()) return;
      const lastPage = Math.max(1, Math.ceil(result.total / params.pageSize));
      if (params.page > lastPage) {
        options.page.value = lastPage;
        return;
      }
      // Vue 在同一轮更新中提交表格及统计，之后页级/独立统计响应均失效。
      pagedRows.value = result.pagedRows;
      total.value = result.total;
      categoryStats.value = result.categoryStats;
      categoryStates.value = {
        alarm: { loading: false, error: false },
        cpu: { loading: false, error: false },
        disk: { loading: false, error: false },
        mem: { loading: false, error: false },
      };
      rawRowCount.value = fullRowCount;
      fullBase = null;
      fullMetrics = null;
      fullDataReady.value = true;
      fullLoading.value = false;
      fullLoadError.value = false;
      loading.value = false;
      metricLoading.value = false;
      loadError.value = false;
      metricLoadError.value = false;
      pageBase = [];
    } catch {
      if (!isLatest()) return;
      prepared = false;
      fullDataReady.value = false;
      fullLoading.value = false;
      fullLoadError.value = true;
      void loadPageData();
      void loadCategoryStats();
    }
  };

  const retryFullData = async () => {
    if (!timeParams || disposed || fullDataReady.value) return;
    const currentGeneration = generation;
    const requestId = ++fullRequest;
    const isLatest = () => isCurrent(currentGeneration) && requestId === fullRequest;
    prepared = false;
    viewRequest += 1;
    fullLoading.value = true;
    fullLoadError.value = false;
    const scope = fullScope;
    const range = timeParams;
    // 分享仍沿用明确 ID 子集的查询协议；普通业务全量指标立即并发且省略 ID。
    const basePromise = fullBase
      ? Promise.resolve(fullBase)
      : getHostInfoList(scope).then(rows => {
          if (isLatest()) fullBase = rows;
          return rows;
        });
    const scoped = scope.bk_host_id != null || (scope.bk_obj_id && scope.bk_inst_id != null);
    const metricPromise = fullMetrics
      ? Promise.resolve(fullMetrics)
      : (scoped
          ? basePromise.then(rows =>
              rows.length
                ? getHostMetricInfoList({ ...scope, ...range, bk_host_ids: rows.map(row => row.bk_host_id) })
                : {}
            )
          : getHostMetricInfoList({ ...scope, ...range })
        ).then(metrics => {
          if (isLatest()) fullMetrics = metrics;
          return metrics;
        });
    try {
      const [rows, metrics] = await Promise.all([basePromise, metricPromise]);
      if (!isLatest()) return;
      await options.worker.initBaseData(rows);
      if (!isLatest()) return;
      const result = await options.worker.mergeMetrics(metrics);
      if (!isLatest()) return;
      fullRowCount = rows.length;
      filterOptionsMap.value = result.filterOptionsMap;
      prepared = true;
      await refreshList();
    } catch {
      if (!isLatest()) return;
      fullLoading.value = false;
      fullLoadError.value = true;
    }
  };

  const loadData = () => {
    generation += 1;
    viewRequest += 1;
    fullRequest += 1;
    prepared = false;
    fullDataReady.value = false;
    fullBase = null;
    fullMetrics = null;
    filterOptionsMap.value = {};
    categoryStats.value = emptyStats();
    categoryStates.value = emptyCategoryStates();
    timeParams = options.getTimeParams();
    fullScope = options.getScope();
    return Promise.all([loadPageData(), retryFullData(), loadCategoryStats()]);
  };

  onScopeDispose(() => {
    disposed = true;
    generation += 1;
    pageBase = [];
    fullBase = null;
    fullMetrics = null;
  });

  return {
    categoryStates,
    categoryStats,
    filterOptionsMap,
    fullDataReady,
    fullLoadError,
    fullLoading,
    invalidatePage,
    invalidateView,
    loadCategoryStats,
    loadData,
    loadError,
    loading,
    loadMetricData,
    loadPageData,
    metricLoadError,
    metricLoading,
    pagedRows,
    rawRowCount,
    refreshList,
    retryCategory,
    retryFullData,
    total,
  };
};
