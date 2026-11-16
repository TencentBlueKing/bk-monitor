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
import { commonPageSizeGet } from 'monitor-common/utils';
import { useI18n } from 'vue-i18n';

import {
  getCollectionMeta,
  getCollectionTasks,
  removeCollectionTask,
  saveCollectionTask,
  toggleCollectionTask,
} from '../services/collection';
import { createCollectionHostServices } from '../services/collection-hosts';
import { filterCollectionTasks, immediateCollectionPayload, isTaskDeleteBlocked } from '../utils/collection';
import { createHistoryFilters } from '../utils/collection-history';
import { useAppReadonlyInject } from '@/pages/provider';

import type {
  CollectionHost,
  CollectionMeta,
  CollectionQueryState,
  CollectionTask,
  CollectionTaskColumn,
} from '../types/collection';
import type { CollectionHistoryFilters } from '../types/collection-history';

export type UseProfilingCollectionReturn = ReturnType<typeof useProfilingCollection>;

export function useProfilingCollection(
  bizId: Ref<number>,
  state: Ref<CollectionQueryState>,
  patch: (value: Partial<CollectionQueryState>) => void
) {
  const { t } = useI18n();
  const readonly = useAppReadonlyInject();
  const records = shallowRef<CollectionTask[]>([]);
  /** 任务列表列定义，由接口下发，缺失时由消费方回退到固定列 */
  const taskColumns = shallowRef<CollectionTaskColumn[]>([]);
  const meta = shallowRef<CollectionMeta>();
  const loading = shallowRef(false);
  const error = shallowRef('');
  const busy = shallowRef<number>();
  const page = shallowRef(1);
  /** 每页条数，取全局统一分页配置（未配置时由 commonPageSizeGet 写入并返回 10） */
  const pageSize = shallowRef(commonPageSizeGet());
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
        taskColumns.value = [];
        detailId.value = undefined;
        deleting.value = undefined;
        executing.value = undefined;
        return;
      }
      const tasks = await getCollectionTasks(bizId.value, current.signal);
      if (current.signal.aborted) return;
      records.value = tasks.data;
      taskColumns.value = tasks.columns ?? [];
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
    if (readonly || busy.value || (action === 'delete' && isTaskDeleteBlocked(task))) return;
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
    const taskName = task?.name || '';
    const historyTaskId = task?.task_id || null;
    patch({
      tab: 'history',
      historyTaskId,
      historyTaskName: taskName,
      // 计划任务按 ID 精确定位，避免同名任务串结果；没有 ID 时沿用任务名筛选
      history: { ...createHistoryFilters(), task_id: historyTaskId, task_name: historyTaskId ? '' : taskName },
    });
  }

  function changeHistory(history: CollectionHistoryFilters) {
    patch({
      history,
      historyTaskId: history.task_id,
      // 按任务 ID 筛选时任务名不在筛选条件里，筛选面板沿用进入时的任务名回显
      historyTaskName: history.task_id ? state.value.historyTaskName : history.task_name,
    });
  }

  function saved(immediate: boolean) {
    editorOpen.value = false;
    // 立即执行的任务到采集任务历史看进度；指定时间 / 周期任务回到任务管理列表
    if (immediate) openHistory();
    else patch({ tab: 'tasks' });
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
      taskColumns.value = [];
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
    taskColumns,
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
    changeHistory,
    saved,
  };
}
