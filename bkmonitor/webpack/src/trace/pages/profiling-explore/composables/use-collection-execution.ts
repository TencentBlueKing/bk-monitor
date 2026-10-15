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

import { saveCollectionTask } from '../services/collection';
import { getCollectionExecution, stopCollectionExecution } from '../services/collection-history';
import { buildExecutionPayload, canRetryExecution, compareExecutionHostStatus } from '../utils/collection-history';

import type {
  CollectionExecution,
  CollectionExecutionAction,
  CollectionExecutionDetail,
} from '../types/collection-history';

export type UseCollectionExecutionReturn = ReturnType<typeof useCollectionExecution>;

export function useCollectionExecution({
  bizId,
  readonly,
  revision,
  onUpdated,
  onCreated,
}: {
  bizId: Ref<number>;
  onCreated: () => void;
  onUpdated: () => void;
  readonly: Ref<boolean>;
  revision: Ref<number>;
}) {
  const { t } = useI18n();
  const selected = shallowRef<CollectionExecution | null>(null);
  const detail = shallowRef<CollectionExecutionDetail | null>(null);
  const loading = shallowRef(false);
  const error = shallowRef('');
  const keyword = shallowRef('');
  const hostSort = shallowRef<'' | 'asc' | 'desc'>('');
  const tab = shallowRef('results');
  const pending = shallowRef<null | { action: CollectionExecutionAction; execution: CollectionExecution }>(null);
  const busy = shallowRef(false);
  const actionError = shallowRef('');
  let controller: AbortController;
  let actionController: AbortController;
  const hosts = computed(() => {
    const search = keyword.value.trim().toLowerCase();
    const filtered = (detail.value?.hosts || []).filter(
      host =>
        !search ||
        [host.ip, ...host.processes.flatMap(process => [process.process_name, String(process.pid)])].some(value =>
          value.toLowerCase().includes(search)
        )
    );
    if (!hostSort.value) return filtered;
    return filtered.sort(
      (left, right) => compareExecutionHostStatus(left, right) * (hostSort.value === 'desc' ? -1 : 1)
    );
  });

  async function refresh() {
    controller?.abort();
    controller = new AbortController();
    const current = controller;
    error.value = '';
    loading.value = false;
    if (!selected.value) return;
    loading.value = true;
    try {
      const result = await getCollectionExecution(bizId.value, selected.value, current.signal);
      if (!current.signal.aborted) detail.value = result;
    } catch (e) {
      if (!current.signal.aborted) error.value = (e as Error)?.message || t('执行详情加载失败，请重试');
    } finally {
      if (!current.signal.aborted) loading.value = false;
    }
  }

  function open(execution: CollectionExecution) {
    if (busy.value) return;
    selected.value = execution;
    detail.value = null;
    keyword.value = '';
    hostSort.value = '';
    tab.value = 'results';
    return refresh();
  }

  function close() {
    if (busy.value) return;
    controller?.abort();
    selected.value = null;
    detail.value = null;
    loading.value = false;
    error.value = '';
  }

  function requestAction(action: CollectionExecutionAction, execution: CollectionExecution) {
    if (readonly.value || busy.value) return;
    if (
      action === 'cancel'
        ? execution.execution_status !== 'running' || !execution.hosts.length
        : execution.execution_status === 'running'
    )
      return;
    pending.value = { action, execution };
    actionError.value = '';
  }

  function dismissAction() {
    if (!busy.value) pending.value = null;
  }

  async function confirmAction() {
    if (readonly.value || busy.value || !pending.value) return;
    const { action, execution } = pending.value;
    actionController = new AbortController();
    const current = actionController;
    busy.value = true;
    actionError.value = '';
    try {
      if (action === 'cancel') {
        await stopCollectionExecution(bizId.value, execution, current.signal);
      } else {
        const snapshot = await getCollectionExecution(bizId.value, execution, current.signal);
        if (current.signal.aborted || readonly.value) return;
        if (snapshot.execution_status === 'running') throw new Error(t('采集中，暂不能重新执行'));
        if (action === 'retry' && !canRetryExecution(snapshot)) throw new Error(t('没有可重试的失败主机'));
        await saveCollectionTask(
          buildExecutionPayload(snapshot, bizId.value, action === 'retry'),
          undefined,
          current.signal
        );
      }
      if (current.signal.aborted) return;
      pending.value = null;
      if (action === 'cancel') {
        onUpdated();
        refresh();
      } else {
        busy.value = false;
        close();
        onCreated();
      }
    } catch (e) {
      if (!current.signal.aborted) actionError.value = t((e as Error)?.message || '操作失败，请重试');
    } finally {
      if (!current.signal.aborted) busy.value = false;
    }
  }

  watch(revision, () => {
    if (!busy.value) refresh();
  });
  watch(
    bizId,
    () => {
      actionController?.abort();
      busy.value = false;
      pending.value = null;
      actionError.value = '';
      close();
    },
    { flush: 'sync' }
  );
  onScopeDispose(() => {
    controller?.abort();
    actionController?.abort();
  });
  return {
    selected,
    detail,
    hosts,
    keyword,
    hostSort,
    tab,
    loading,
    error,
    pending,
    busy,
    actionError,
    open,
    close,
    refresh,
    requestAction,
    dismissAction,
    confirmAction,
  };
}
