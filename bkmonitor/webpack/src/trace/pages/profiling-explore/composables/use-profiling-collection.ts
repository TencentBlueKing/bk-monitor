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

import {
  getCollectionMeta,
  getCollectionTasks,
  removeCollectionTask,
  saveCollectionTask,
  toggleCollectionTask,
} from '../services/collection';
import { createCollectionHostServices } from '../services/collection-hosts';
import { filterCollectionTasks, immediateCollectionPayload } from '../utils/collection';
import { createHistoryFilters } from '../utils/collection-history';
import { useAppReadonlyInject } from '@/pages/provider';

import type { CollectionHost, CollectionMeta, CollectionQueryState, CollectionTask } from '../types/collection';

export function useProfilingCollection(
  bizId: Ref<number>,
  state: Ref<CollectionQueryState>,
  patch: (value: Partial<CollectionQueryState>) => void
) {
  const { t } = useI18n();
  const readonly = useAppReadonlyInject();
  const records = shallowRef<CollectionTask[]>([]);
  const meta = shallowRef<CollectionMeta>();
  const loading = shallowRef(false);
  const error = shallowRef('');
  const busy = shallowRef<number>();
  const page = shallowRef(1);
  const pageSize = shallowRef(20);
  const editing = shallowRef<CollectionTask>();
  const editorOpen = shallowRef(false);
  const detailId = shallowRef<number>();
  const deleting = shallowRef<CollectionTask>();
  const executing = shallowRef<CollectionTask>();
  const filtered = computed(() => filterCollectionTasks(records.value, state.value));
  const rows = computed(() => filtered.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value));
  const detail = computed(() => records.value.find(task => task.task_id === detailId.value));
  const detailHosts = shallowRef<CollectionHost[]>([]);
  const detailHostError = shallowRef('');
  const detailHostLoading = shallowRef(false);
  let listController: AbortController;
  let detailController: AbortController;
  let actionController = new AbortController();

  async function refresh() {
    listController?.abort();
    const current = new AbortController();
    listController = current;
    loading.value = true;
    error.value = '';
    let config: CollectionMeta;
    try {
      config = await getCollectionMeta(bizId.value, current.signal);
      if (current.signal.aborted) return;
      meta.value = config;
      if (!config.enabled) {
        records.value = [];
        detailId.value = undefined;
        deleting.value = undefined;
        executing.value = undefined;
        return;
      }
      const tasks = await getCollectionTasks(bizId.value, current.signal);
      if (current.signal.aborted) return;
      records.value = tasks.data;
      page.value = Math.min(page.value, Math.max(1, Math.ceil(filtered.value.length / pageSize.value)));
    } catch (e) {
      if (!current.signal.aborted) {
        if (!config) meta.value = undefined;
        error.value = (e as Error)?.message || t(config ? '任务列表加载失败，请重试' : '主动采集配置加载失败，请重试');
      }
    } finally {
      if (!current.signal.aborted) loading.value = false;
    }
  }

  async function runAction(task: CollectionTask, action: 'delete' | 'execute' | 'switch') {
    if (readonly || busy.value || (action === 'delete' && task.task_status !== 'disabled')) return;
    const current = actionController;
    busy.value = task.task_id;
    try {
      if (action === 'delete') await removeCollectionTask(bizId.value, task.task_id, current.signal);
      if (action === 'switch')
        await toggleCollectionTask(bizId.value, task.task_id, task.task_status !== 'enabled', current.signal);
      if (action === 'execute')
        await saveCollectionTask(immediateCollectionPayload(task, bizId.value), undefined, current.signal);
      if (current.signal.aborted) return;
      Message({ theme: 'success', message: t(action === 'execute' ? '采集任务已提交' : '操作成功') });
      deleting.value = undefined;
      executing.value = undefined;
      if (action === 'execute') openHistory();
      else await refresh();
    } catch (e) {
      if (!current.signal.aborted) Message({ theme: 'error', message: (e as Error)?.message || t('操作失败，请重试') });
    } finally {
      if (!current.signal.aborted) busy.value = undefined;
    }
  }

  function openEditor(task?: CollectionTask) {
    if (readonly || !meta.value) return;
    detailId.value = undefined;
    editing.value = task;
    editorOpen.value = true;
  }

  function openHistory(task?: CollectionTask) {
    detailId.value = undefined;
    patch({
      tab: 'history',
      historyTaskId: task?.task_id || null,
      historyTaskName: task?.name || '',
      history: { ...createHistoryFilters(), task_name: task?.name || '' },
    });
  }

  function saved(immediate: boolean) {
    editorOpen.value = false;
    if (immediate) openHistory();
    refresh();
  }

  async function loadDetailHosts() {
    detailController?.abort();
    detailHostError.value = '';
    detailHosts.value = detail.value?.target_config.nodes.map(node => ({ host_id: node.bk_host_id })) || [];
    detailHostLoading.value = false;
    if (!detail.value) return;
    const current = new AbortController();
    detailController = current;
    detailHostLoading.value = true;
    try {
      const hosts = await createCollectionHostServices(bizId.value, current.signal).fetchHostsDetails({
        host_list: detailHosts.value,
      });
      if (current.signal.aborted) return;
      const byId = new Map(hosts.map(host => [host.host_id, host]));
      detailHosts.value = detailHosts.value.map(host => byId.get(host.host_id) || host);
    } catch (e) {
      if (!current.signal.aborted) detailHostError.value = (e as Error)?.message || t('主机信息加载失败，请重试');
    } finally {
      if (!current.signal.aborted) detailHostLoading.value = false;
    }
  }

  watch(
    [
      () => state.value.keyword,
      () => state.value.scheduleTypes,
      () => state.value.statuses,
      () => state.value.sort,
      pageSize,
    ],
    () => {
      page.value = 1;
    }
  );
  watch(
    bizId,
    () => {
      actionController.abort();
      actionController = new AbortController();
      records.value = [];
      meta.value = undefined;
      busy.value = undefined;
      editorOpen.value = false;
      detailId.value = undefined;
      deleting.value = undefined;
      executing.value = undefined;
      refresh();
    },
    { immediate: true }
  );
  watch(detail, loadDetailHosts);
  onScopeDispose(() => {
    listController?.abort();
    detailController?.abort();
    actionController.abort();
  });
  return {
    readonly,
    records,
    meta,
    loading,
    error,
    busy,
    page,
    pageSize,
    filtered,
    rows,
    editing,
    editorOpen,
    detailId,
    detail,
    detailHosts,
    detailHostError,
    detailHostLoading,
    loadDetailHosts,
    deleting,
    executing,
    refresh,
    runAction,
    openEditor,
    openHistory,
    saved,
  };
}
