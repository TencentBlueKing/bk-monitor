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

import { Message } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { saveCollectionTask } from '../services/collection';
import { getCollectionExecution } from '../services/collection-history';
import { getCollectionResults } from '../services/collection-results';
import {
  buildHostCollectionPayload,
  executionResultRows,
  resultExecutionKey,
  resultRowKey,
} from '../utils/collection-results';

import type { SelectionRange } from '../types';
import type { CollectionExecutionColumn, CollectionExecutionDetail } from '../types/collection-history';
import type { CollectionHostResult, CollectionResultsState } from '../types/collection-results';

const PAGE_LIMIT = 20;

export function useCollectionResults({
  bizId,
  state,
  range,
  revision,
  readonly,
  onCreated,
  resolveRange,
}: {
  bizId: Ref<number>;
  onCreated: () => void;
  range: Ref<SelectionRange>;
  readonly: Ref<boolean>;
  // 重新解析时间表达式；相对时间在每次查询时取最新边界
  resolveRange?: () => SelectionRange | undefined;
  revision: Ref<number>;
  state: Ref<CollectionResultsState>;
}) {
  const { t } = useI18n();
  const records = shallowRef<CollectionHostResult[]>([]);
  // 执行范围下后端下发的列定义；缺省时结果页沿用固定列
  const hostColumns = shallowRef<CollectionExecutionColumn[] | null>(null);
  // 执行范围下的执行详情，结果页用其中的任务名与主机 IP 回填筛选条件
  const executionDetail = shallowRef<CollectionExecutionDetail | null>(null);
  const loading = shallowRef(false);
  // 当前筛选条件下的结果总数，由后端下发；未下发或执行范围内保持 null，不展示统计行
  const total = shallowRef<null | number>(null);
  const error = shallowRef('');
  const hasMore = shallowRef(false);
  const pending = shallowRef<CollectionHostResult | null>(null);
  const busy = shallowRef(false);
  const actionError = shallowRef('');
  let controller: AbortController;
  let actionController: AbortController;
  let offset = 0;
  // 本次查询实际使用的绝对时间；翻页沿用首屏边界，避免相对时间跨页漂移
  let pageRange: null | SelectionRange = null;

  // 时间表达式无效时回退到已提交的绝对范围，避免查询时抛错
  function currentRange(): null | SelectionRange {
    try {
      return resolveRange?.() || range.value;
    } catch {
      return range.value;
    }
  }

  async function fetchPage() {
    const queryRange = pageRange;
    if (loading.value || (!queryRange && !state.value.execution)) return;
    const current = new AbortController();
    controller = current;
    loading.value = true;
    error.value = '';
    try {
      const execution = state.value.execution;
      const detail = execution ? await getCollectionExecution(bizId.value, execution, current.signal) : null;
      if (current.signal.aborted) return;
      executionDetail.value = detail;
      hostColumns.value = detail?.host_columns?.length ? detail.host_columns : null;
      const result = detail
        ? null
        : await getCollectionResults(
            bizId.value,
            queryRange as SelectionRange,
            state.value.filters,
            offset,
            current.signal
          );
      if (current.signal.aborted) return;
      const data = detail ? executionResultRows(detail) : result?.data || [];
      if (result && typeof result.total === 'number') total.value = result.total;
      const known = new Set(records.value.map(resultRowKey));
      records.value = [
        ...records.value,
        ...data.filter(row => {
          const key = resultRowKey(row);
          if (known.has(key)) return false;
          known.add(key);
          return true;
        }),
      ];
      offset += data.length;
      hasMore.value = !execution && data.length === PAGE_LIMIT;
    } catch (e) {
      if (!current.signal.aborted) error.value = (e as Error)?.message || t('采集结果加载失败，请重试');
    } finally {
      if (!current.signal.aborted) loading.value = false;
    }
  }

  function refresh() {
    controller?.abort();
    loading.value = false;
    records.value = [];
    hostColumns.value = null;
    executionDetail.value = null;
    total.value = null;
    offset = 0;
    hasMore.value = false;
    error.value = '';
    // 每次重新查询都刷新时间边界；翻页沿用这里定下的范围
    pageRange = currentRange();
    return fetchPage();
  }

  function loadMore() {
    if (hasMore.value) return fetchPage();
  }

  function requestRerun(row: CollectionHostResult) {
    if (readonly.value || busy.value || row.status === 'running') return;
    pending.value = row;
    actionError.value = '';
  }

  async function confirmRerun() {
    if (readonly.value || busy.value || !pending.value) return;
    const row = pending.value;
    const current = new AbortController();
    actionController = current;
    busy.value = true;
    actionError.value = '';
    try {
      const detail = await getCollectionExecution(bizId.value, resultExecutionKey(row), current.signal);
      if (current.signal.aborted || readonly.value) return;
      await saveCollectionTask(
        buildHostCollectionPayload(detail, row.bk_host_id, bizId.value),
        undefined,
        current.signal
      );
      if (current.signal.aborted) return;
      pending.value = null;
      Message({ theme: 'success', message: t('采集任务已创建') });
      onCreated();
    } catch (e) {
      if (!current.signal.aborted) actionError.value = t((e as Error)?.message || '重新采集失败，请重试');
    } finally {
      if (!current.signal.aborted) busy.value = false;
    }
  }

  watch([bizId, () => state.value.filters, () => state.value.execution, range, revision], refresh, { immediate: true });
  watch(
    bizId,
    () => {
      actionController?.abort();
      busy.value = false;
      pending.value = null;
      actionError.value = '';
    },
    { flush: 'sync' }
  );
  onScopeDispose(() => {
    controller?.abort();
    actionController?.abort();
  });
  return {
    records,
    hostColumns,
    executionDetail,
    loading,
    total,
    error,
    hasMore,
    pending,
    busy,
    actionError,
    refresh,
    loadMore,
    requestRerun,
    confirmRerun,
  };
}
