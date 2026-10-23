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
import { useCollectionCandidates } from './use-collection-candidates';

import type { SelectionRange } from '../types';
import type { CollectionHostResult, CollectionResultsState } from '../types/collection-results';

export function useCollectionResults({
  bizId,
  state,
  range,
  revision,
  readonly,
  onCreated,
}: {
  bizId: Ref<number>;
  onCreated: () => void;
  range: Ref<SelectionRange>;
  readonly: Ref<boolean>;
  revision: Ref<number>;
  state: Ref<CollectionResultsState>;
}) {
  const { t } = useI18n();
  const records = shallowRef<CollectionHostResult[]>([]);
  const loading = shallowRef(false);
  const error = shallowRef('');
  const hasMore = shallowRef(false);
  const pending = shallowRef<CollectionHostResult | null>(null);
  const busy = shallowRef(false);
  const actionError = shallowRef('');
  const candidateState = useCollectionCandidates(bizId, range);
  const rows = computed(() => {
    if (!state.value.execution) return records.value;
    const filters = state.value.filters;
    const contains = (value: string, terms: string[]) => !terms.length || terms.some(term => value.includes(term));
    return records.value.filter(
      row =>
        (!filters.ips.length || filters.ips.includes(row.ip)) &&
        (!filters.task_name || row.task.name.includes(filters.task_name)) &&
        (!filters.status || row.status === filters.status) &&
        (!filters.process_names.length ||
          row.processes.some(process => contains(process.process_name, filters.process_names))) &&
        (!filters.process_pids.length ||
          row.processes.some(process => contains(String(process.pid), filters.process_pids)))
    );
  });
  let controller: AbortController;
  let actionController: AbortController;
  let offset = 0;

  async function fetchPage() {
    if (loading.value || (!range.value && !state.value.execution)) return;
    const current = new AbortController();
    controller = current;
    loading.value = true;
    error.value = '';
    try {
      const execution = state.value.execution;
      const data = execution
        ? executionResultRows(await getCollectionExecution(bizId.value, execution, current.signal))
        : (await getCollectionResults(bizId.value, range.value, state.value.filters, offset, current.signal)).data;
      if (current.signal.aborted) return;
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
      hasMore.value = !execution && data.length === 20;
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
    offset = 0;
    hasMore.value = false;
    error.value = '';
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

  watch(
    [bizId, () => state.value.filters, () => state.value.execution, range, revision],
    (next, prev) => {
      // 执行范围内结果由前端按筛选过滤，筛选单独变化时无需重新请求
      const othersChanged =
        next.length !== prev.length || next.some((value, index) => index !== 1 && value !== prev[index]);
      if (next[2] && !othersChanged) return;
      refresh();
    },
    { immediate: true }
  );
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
    rows,
    records,
    loading,
    error,
    hasMore,
    pending,
    busy,
    actionError,
    ...candidateState,
    refresh,
    loadMore,
    requestRerun,
    confirmRerun,
  };
}
