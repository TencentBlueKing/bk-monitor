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
import { type Ref, computed, onScopeDispose, shallowRef, watch } from 'vue';

import { useI18n } from 'vue-i18n';

import { getProfile, getTrend } from '../services/profiling';
import { getTrendQuery } from '../utils/query';

import type { GraphMode, ProfileQuery, ProfileResult, TrendResult } from '../types';

export function useProfileResults({
  query,
  active,
  revision,
  timeComparison,
  graphMode,
  traceMode,
}: {
  active: Ref<boolean>;
  graphMode: Ref<GraphMode>;
  query: Ref<null | ProfileQuery>;
  revision: Ref<number>;
  timeComparison: Ref<boolean>;
  traceMode: Ref<boolean>;
}) {
  const { t } = useI18n();
  const graph = shallowRef<ProfileResult>({});
  const callGraph = shallowRef('');
  const trends = shallowRef<TrendResult[]>([]);
  // 普通图与调用图的加载状态独立，切换视图不能提前结束仍在进行的普通图请求。
  const profileLoading = shallowRef(false);
  const callLoading = shallowRef(false);
  const graphLoading = computed(() => profileLoading.value || (graphMode.value === 'callgraph' && callLoading.value));
  const trendLoading = shallowRef(false);
  const profileError = shallowRef('');
  const callError = shallowRef('');
  const graphError = computed(() => (graphMode.value === 'callgraph' ? callError.value : profileError.value));
  const trendError = shallowRef('');
  let graphController: AbortController;
  let trendController: AbortController;
  let callController: AbortController;
  let callQueryKey = '';

  async function loadGraph() {
    graphController?.abort();
    callController?.abort();
    graphController = new AbortController();
    // 异步回调只检查本次 controller；旧请求的 finally 也不能关闭新请求的 loading。
    const current = graphController;
    graph.value = {};
    callGraph.value = '';
    callQueryKey = '';
    profileError.value = '';
    callError.value = '';
    callLoading.value = false;
    profileLoading.value = false;
    if (!query.value || !active.value) return;
    profileLoading.value = true;
    try {
      const data = await getProfile({ ...query.value, diagram_types: ['table', 'flamegraph'] }, current.signal);
      if (!current.signal.aborted) graph.value = data;
    } catch (e) {
      if (!current.signal.aborted) profileError.value = (e as Error)?.message || t('数据加载失败，请重试');
    } finally {
      if (!current.signal.aborted) profileLoading.value = false;
    }
    if (!current.signal.aborted && graphMode.value === 'callgraph') loadCallGraph();
  }

  async function loadCallGraph() {
    // 调用图仅在非对比模式按需加载，同一查询成功后可复用，失败则允许重试。
    if (!query.value || query.value.is_compared || !active.value || graphMode.value !== 'callgraph') return;
    const key = JSON.stringify(query.value);
    if (key === callQueryKey) return;
    callController?.abort();
    callController = new AbortController();
    const current = callController;
    callLoading.value = true;
    callError.value = '';
    try {
      const data = await getProfile({ ...query.value, diagram_types: ['callgraph'] }, current.signal);
      if (!current.signal.aborted) {
        callGraph.value = data.call_graph_data || '';
        callQueryKey = key;
      }
    } catch (e) {
      if (!current.signal.aborted) callError.value = (e as Error)?.message || t('调用图加载失败，请重试');
    } finally {
      if (!current.signal.aborted) callLoading.value = false;
    }
  }

  // 框选只更新可视化查询，趋势保留全局时间范围，避免拖动时反复请求趋势。
  const trendKey = computed(
    () => query.value && JSON.stringify([getTrendQuery(query.value), timeComparison.value, traceMode.value])
  );

  async function loadTrends() {
    trendController?.abort();
    trendController = new AbortController();
    const current = trendController;
    trends.value = [];
    trendError.value = '';
    trendLoading.value = false;
    if (!query.value || !active.value) return;
    const params =
      timeComparison.value || (traceMode.value && query.value.is_compared)
        ? [getTrendQuery(query.value, 'baseline'), getTrendQuery(query.value, 'comparison')]
        : [getTrendQuery(query.value)];
    trendLoading.value = true;
    try {
      const results = await Promise.all(
        params.map(p => getTrend(p, current.signal, traceMode.value && !timeComparison.value))
      );
      if (!current.signal.aborted) trends.value = results;
    } catch (e) {
      if (!current.signal.aborted) trendError.value = (e as Error)?.message || t('趋势加载失败，请重试');
    } finally {
      if (!current.signal.aborted) trendLoading.value = false;
    }
  }

  watch([query, active], () => {
    if (query.value?.is_compared && graphMode.value === 'callgraph') graphMode.value = 'combined';
    loadGraph();
  });
  watch([trendKey, revision, active], loadTrends);
  watch(graphMode, () => {
    if (graphMode.value === 'callgraph' && !profileLoading.value) loadCallGraph();
    else if (graphMode.value !== 'callgraph') {
      callController?.abort();
      callLoading.value = false;
      callError.value = '';
    }
  });
  onScopeDispose(() => {
    graphController?.abort();
    trendController?.abort();
    callController?.abort();
  });
  return {
    graphMode,
    traceMode,
    graph,
    callGraph,
    trends,
    graphLoading,
    trendLoading,
    graphError,
    trendError,
    retryGraph: () => (graphMode.value === 'callgraph' ? loadCallGraph() : loadGraph()),
    retryTrends: loadTrends,
  };
}
