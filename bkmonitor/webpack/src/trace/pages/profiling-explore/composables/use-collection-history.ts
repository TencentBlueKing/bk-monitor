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
import { type Ref, onScopeDispose, shallowRef, watch } from 'vue';

import { useI18n } from 'vue-i18n';

import { COLLECTION_HISTORY_PAGE_SIZE, getCollectionHistory } from '../services/collection-history';
import { executionRowKey } from '../utils/collection-history';

import type { SelectionRange } from '../types';
import type { CollectionExecution, CollectionHistoryFilters, CollectionTaskColumn } from '../types/collection-history';

export type UseCollectionHistoryReturn = ReturnType<typeof useCollectionHistory>;

// 后端列定义只保证是数组，元素结构仍需运行时校验，避免异常数据中断表格渲染
const isTaskColumn = (value: unknown): value is CollectionTaskColumn =>
  !!value && typeof value === 'object' && typeof (value as CollectionTaskColumn).field === 'string';

export function useCollectionHistory({
  bizId,
  filters,
  range,
  revision,
  resolveRange,
}: {
  bizId: Ref<number>;
  filters: Ref<CollectionHistoryFilters>;
  range: Ref<SelectionRange>;
  // 重新解析时间表达式；相对时间在每次查询时取最新边界
  resolveRange?: () => SelectionRange | undefined;
  revision: Ref<number>;
}) {
  const { t } = useI18n();
  const rows = shallowRef<CollectionExecution[]>([]);
  // 后端下发的表头列定义；缺省时组件回退默认列
  const taskColumns = shallowRef<CollectionTaskColumn[]>([]);
  const loading = shallowRef(false);
  const error = shallowRef('');
  const hasMore = shallowRef(false);
  // 自动补页是否继续：某页没有带来新行时暂停，避免后端重复返回同一页时空转
  const canAutoFill = shallowRef(true);
  let controller: AbortController;
  // 静默刷新独立于主动请求，不参与 loading，失败也不影响列表状态
  let silentController: AbortController | null = null;
  let offset = 0;
  // 本次查询实际使用的绝对时间；翻页沿用首屏边界，避免相对时间跨页漂移
  let pageRange: null | SelectionRange = null;

  function abortSilentRefresh() {
    silentController?.abort();
    silentController = null;
  }

  // 时间表达式无效时回退到已提交的绝对范围，避免查询时抛错
  function currentRange(): null | SelectionRange {
    try {
      return resolveRange?.() || range.value;
    } catch {
      return range.value;
    }
  }

  async function fetchPage() {
    // 主动加载优先：取消进行中的静默刷新，避免两处同时改写列表
    abortSilentRefresh();
    const queryRange = pageRange;
    if (loading.value || !queryRange) return;
    controller = new AbortController();
    const current = controller;
    loading.value = true;
    error.value = '';
    try {
      const result = await getCollectionHistory(bizId.value, queryRange, filters.value, offset, current.signal);
      if (current.signal.aborted) return;
      // 翻页响应可能不带列定义，仅在结构有效的下发时覆盖
      if (Array.isArray(result.task_columns)) {
        const columns = result.task_columns.filter(isTaskColumn);
        if (columns.length) taskColumns.value = columns;
      }
      const known = new Set(rows.value.map(executionRowKey));
      const added = result.data.filter(row => {
        const key = executionRowKey(row);
        if (known.has(key)) return false;
        known.add(key);
        return true;
      });
      rows.value = [...rows.value, ...added];
      offset += result.data.length;
      // 是否还有更多仍按分页语义判断；「本页没有新增行」不等于「没有更多数据」，只用来暂停自动补页
      hasMore.value = result.data.length === COLLECTION_HISTORY_PAGE_SIZE;
      canAutoFill.value = added.length > 0;
    } catch (e) {
      if (!current.signal.aborted) error.value = (e as Error)?.message || t('采集历史加载失败，请重试');
    } finally {
      if (!current.signal.aborted) loading.value = false;
    }
  }

  function refresh() {
    controller?.abort();
    loading.value = false;
    rows.value = [];
    offset = 0;
    hasMore.value = false;
    canAutoFill.value = true;
    error.value = '';
    // 每次重新查询都刷新时间边界；翻页沿用这里定下的范围
    pageRange = currentRange();
    return fetchPage();
  }

  function loadMore() {
    if (hasMore.value) return fetchPage();
  }

  /**
   * 静默刷新：按已加载的分页范围重新请求并整体替换列表数据，
   * 不改 loading、不重置滚动与分页状态；失败时保留现有列表且不覆盖 error
   */
  async function silentRefresh() {
    const queryRange = pageRange;
    if (loading.value || silentController || !queryRange) return;
    const current = new AbortController();
    silentController = current;
    // 已加载行数决定需要重拉的页数，列表为空时按一页兜底
    const pages = Math.max(1, Math.ceil(rows.value.length / COLLECTION_HISTORY_PAGE_SIZE));
    try {
      const results = await Promise.all(
        Array.from({ length: pages }, (_, index) =>
          getCollectionHistory(
            bizId.value,
            queryRange,
            filters.value,
            index * COLLECTION_HISTORY_PAGE_SIZE,
            current.signal
          )
        )
      );
      if (current.signal.aborted) return;
      // 分页期间可能有新记录插入导致跨页重复，按执行键去重后替换
      const known = new Set<string>();
      rows.value = results
        .flatMap(result => result.data)
        .filter(row => {
          const key = executionRowKey(row);
          if (known.has(key)) return false;
          known.add(key);
          return true;
        });
      // 列表行数可能因新记录插入而变化，翻页游标跟随实际加载条数
      offset = rows.value.length;
    } catch {
      /* 静默刷新失败保留现有列表，由下一轮定时刷新或用户操作重试 */
    } finally {
      if (silentController === current) silentController = null;
    }
  }

  watch([bizId, filters, range, revision], refresh, { immediate: true });
  onScopeDispose(() => {
    controller?.abort();
    abortSilentRefresh();
  });
  return {
    rows,
    taskColumns,
    loading,
    error,
    hasMore,
    canAutoFill,
    refresh,
    loadMore,
    silentRefresh,
  };
}
