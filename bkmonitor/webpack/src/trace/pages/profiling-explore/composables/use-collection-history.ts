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

import { getCollectionHistory } from '../services/collection-history';
import { executionRowKey } from '../utils/collection-history';
import { useCollectionCandidates } from './use-collection-candidates';

import type { SelectionRange } from '../types';
import type { CollectionExecution, CollectionHistoryFilters } from '../types/collection-history';

export type UseCollectionHistoryReturn = ReturnType<typeof useCollectionHistory>;

export function useCollectionHistory({
  bizId,
  filters,
  range,
  revision,
}: {
  bizId: Ref<number>;
  filters: Ref<CollectionHistoryFilters>;
  range: Ref<SelectionRange>;
  revision: Ref<number>;
}) {
  const { t } = useI18n();
  const rows = shallowRef<CollectionExecution[]>([]);
  const loading = shallowRef(false);
  const error = shallowRef('');
  const hasMore = shallowRef(false);
  const candidateState = useCollectionCandidates(bizId, range);
  let controller: AbortController;
  let offset = 0;

  async function fetchPage() {
    if (loading.value || !range.value) return;
    controller = new AbortController();
    const current = controller;
    loading.value = true;
    error.value = '';
    try {
      const result = await getCollectionHistory(bizId.value, range.value, filters.value, offset, current.signal);
      if (current.signal.aborted) return;
      const known = new Set(rows.value.map(executionRowKey));
      rows.value = [
        ...rows.value,
        ...result.data.filter(row => {
          const key = executionRowKey(row);
          if (known.has(key)) return false;
          known.add(key);
          return true;
        }),
      ];
      offset += result.data.length;
      hasMore.value = result.data.length === 20;
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
    error.value = '';
    return fetchPage();
  }

  function loadMore() {
    if (hasMore.value) return fetchPage();
  }

  watch([bizId, filters, range, revision], refresh, { immediate: true });
  onScopeDispose(() => {
    controller?.abort();
  });
  return {
    rows,
    loading,
    error,
    hasMore,
    ...candidateState,
    refresh,
    loadMore,
  };
}
