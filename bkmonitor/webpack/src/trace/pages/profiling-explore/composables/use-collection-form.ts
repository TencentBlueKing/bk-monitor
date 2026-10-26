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
import { computed, onScopeDispose, shallowRef, watch } from 'vue';

import { Message } from 'bkui-vue';
import { bkUiMessage } from 'trace/common/message';
import { useI18n } from 'vue-i18n';

import { getProcessPreview, saveCollectionTask } from '../services/collection';
import { createCollectionHostServices } from '../services/collection-hosts';
import {
  buildCollectionPayload,
  buildPreviewSelector,
  collectionFieldErrors,
  collectionTarget,
  createCollectionDraft,
  ERROR_FIELDS_BY_DRAFT_KEY,
  processKey,
  SWITCH_DRAFT_KEYS,
} from '../utils/collection';

import type {
  CollectionDraft,
  CollectionFieldKey,
  CollectionHost,
  CollectionMeta,
  CollectionMethod,
  CollectionTask,
  CollectionType,
  ProcessDraft,
  ProcessPreview,
  ProcessRow,
} from '../types/collection';

export type CollectionForm = ReturnType<typeof useCollectionForm>;

export function useCollectionForm(
  meta: CollectionMeta,
  bizId: number,
  timezone: string,
  task: CollectionTask | undefined,
  saved: (immediate: boolean) => void
) {
  const { t } = useI18n();
  const draft = shallowRef(createCollectionDraft(meta, timezone, task));
  const loading = shallowRef(false);
  const fieldErrors = shallowRef<Partial<Record<CollectionFieldKey, string>>>({});
  const hostError = shallowRef('');
  const previewLoading = shallowRef(false);
  const previewError = shallowRef('');
  const preview = shallowRef<ProcessPreview>({ columns: [], data: [] });
  const previewPage = shallowRef(1);
  const previewPageSize = shallowRef(10);
  const previewed = shallowRef(false);
  const hostSelectorOpen = shallowRef(false);
  const advancedOpen = shallowRef(false);
  const controller = new AbortController();
  const hostServices = createCollectionHostServices(bizId, controller.signal);
  let previewController: AbortController;
  const selected = computed(() => draft.value.process.selected);
  const dynamic = computed(() => draft.value.processMode === 'command' && draft.value.process.dynamic);
  const manualSelection = computed(() => draft.value.processMode === 'command' && !dynamic.value);
  const processCondition = computed(() => {
    try {
      return buildPreviewSelector(draft.value);
    } catch {
      return undefined;
    }
  });

  function patch(value: Partial<CollectionDraft>) {
    draft.value = { ...draft.value, ...value };
    const keys = Object.keys(value) as Array<keyof CollectionDraft>;
    const touched = keys.flatMap(key => ERROR_FIELDS_BY_DRAFT_KEY[key] ?? []);
    if (!touched.length) return;
    const next = { ...fieldErrors.value };
    // 切选项（采集方式/类型、进程匹配方式、执行方式）只清除旧提示，填内容才即时校验
    const errors = keys.some(key => SWITCH_DRAFT_KEYS.includes(key))
      ? {}
      : collectionFieldErrors(draft.value, Boolean(task));
    for (const key of touched) {
      const message = errors[key];
      if (message) next[key] = t(message);
      else delete next[key];
    }
    fieldErrors.value = next;
  }
  function patchProcess(value: Partial<ProcessDraft>) {
    patch({ process: { ...draft.value.process, ...value } });
  }
  function changeType(collectionType: CollectionType) {
    patch({ collectionType, collector: { ...meta.collector_config[collectionType] } });
  }
  function changeMethod(method: CollectionMethod) {
    patch({ method });
    changeType(meta.collection_types_by_method[method]?.[0]);
  }
  function selectProcesses(rows: ProcessRow[]) {
    if (!manualSelection.value || previewLoading.value) return;
    patchProcess({ selected: rows });
  }
  function clearTargets() {
    if (draft.value.processMode === 'pid') patchProcess({ pids: '' });
    else if (draft.value.processMode === 'pid_file') patchProcess({ pidPath: '' });
    else if (dynamic.value) patchProcess({ matchPattern: '', excludePattern: '' });
    else selectProcesses([]);
  }
  function changeHosts(hosts: CollectionHost[]) {
    const ids = new Set(hosts.map(host => host.host_id));
    const previous = draft.value.process.selected;
    patch({
      hosts,
      process: {
        ...draft.value.process,
        selected: previous.filter(row => ids.has(row.bk_host_id)),
      },
    });
    hostSelectorOpen.value = false;
  }
  function selectPreview(keys: Array<number | string>) {
    if (!manualSelection.value || previewLoading.value) return;
    const selectedKeys = new Set(keys);
    const visibleKeys = new Set(
      preview.value.data
        .slice((previewPage.value - 1) * previewPageSize.value, previewPage.value * previewPageSize.value)
        .map(processKey)
    );
    const previous = selected.value.filter(
      row => !visibleKeys.has(processKey(row)) || selectedKeys.has(processKey(row))
    );
    const rows = [
      ...previous,
      ...preview.value.data.filter(row => selectedKeys.has(processKey(row)) && !row.err_msg && row.pid),
    ];
    selectProcesses([...new Map(rows.map(row => [processKey(row), row])).values()]);
  }
  function clearPreview() {
    previewController?.abort();
    previewLoading.value = false;
    previewError.value = '';
    preview.value = { columns: [], data: [] };
    previewed.value = false;
    previewPage.value = 1;
  }
  async function queryProcesses() {
    if (previewLoading.value || !draft.value.hosts.length || draft.value.method === 'golang') return;
    clearPreview();
    const current = new AbortController();
    previewController = current;
    try {
      const selector = buildPreviewSelector(draft.value);
      previewLoading.value = true;
      const result = await getProcessPreview(bizId, collectionTarget(draft.value.hosts), selector, current.signal);
      if (current.signal.aborted) return;
      preview.value = result;
      previewed.value = true;
      if (draft.value.processMode === 'command') {
        const rows = new Map(result.data.filter(row => !row.err_msg && row.pid).map(row => [processKey(row), row]));
        patchProcess({ selected: selected.value.map(row => rows.get(processKey(row)) || row) });
      }
    } catch (e) {
      if (!current.signal.aborted) previewError.value = t((e as Error)?.message || '进程查询失败，请重试');
    } finally {
      if (!current.signal.aborted) previewLoading.value = false;
    }
  }
  async function hydrateHosts() {
    if (!draft.value.hosts.length) return;
    hostError.value = '';
    try {
      const hosts = await hostServices.fetchHostsDetails({ host_list: draft.value.hosts });
      if (controller.signal.aborted) return;
      const byId = new Map(hosts.map(host => [host.host_id, host]));
      patch({ hosts: draft.value.hosts.map(host => byId.get(host.host_id) || host) });
    } catch (e) {
      if (!controller.signal.aborted) hostError.value = (e as Error)?.message || t('主机信息加载失败，请重试');
    }
  }
  /** 提交，返回是否保存成功；校验失败时 fieldErrors 已写入全部字段错误 */
  async function submit(validateCron?: () => Promise<boolean>): Promise<boolean> {
    if (loading.value) return false;
    const now = Date.now();
    const errors = collectionFieldErrors(draft.value, Boolean(task), now);
    if (draft.value.scheduleType === 'cron' && !(await validateCron?.()) && !errors.cron)
      errors.cron = '请填写有效的五段式 Cron 表达式';
    // 一次性替换，避免先清空再回填导致已有提示闪烁
    fieldErrors.value = Object.fromEntries(Object.entries(errors).map(([key, message]) => [key, t(message as string)]));
    if (Object.keys(errors).length) return false;
    loading.value = true;
    try {
      const payload = buildCollectionPayload(draft.value, bizId, now);
      await saveCollectionTask(payload, task?.task_id, controller.signal);
      if (controller.signal.aborted) return false;
      Message({ theme: 'success', message: t(task ? '保存成功' : '采集任务已提交') });
      saved(payload.schedule.type === 'immediate');
      return true;
    } catch (e) {
      if (!controller.signal.aborted) {
        const error = e as Error & {
          data?: { error_details?: Record<string, unknown> };
          error_details?: Record<string, unknown>;
        };
        const details = error.data?.error_details ?? error.error_details;
        if (details) bkUiMessage(details);
        else Message({ theme: 'error', message: error.message || t('保存失败，请重试') });
      }
      return false;
    } finally {
      if (!controller.signal.aborted) loading.value = false;
    }
  }
  watch(
    [
      () => draft.value.hosts.map(host => host.host_id).join(','),
      () => draft.value.method,
      () => draft.value.processMode,
      () => draft.value.process.matchPattern,
      () => draft.value.process.excludePattern,
      () => draft.value.process.pidPath,
      () => draft.value.process.pids,
    ],
    clearPreview,
    { flush: 'sync' }
  );
  watch(previewPageSize, () => {
    previewPage.value = 1;
  });
  if (task) hydrateHosts();
  onScopeDispose(() => {
    controller.abort();
    previewController?.abort();
  });
  return {
    draft,
    loading,
    fieldErrors,
    hostError,
    previewLoading,
    previewError,
    preview,
    previewPage,
    previewPageSize,
    previewed,
    hostSelectorOpen,
    advancedOpen,
    hostServices,
    selected,
    dynamic,
    manualSelection,
    processCondition,
    clearTargets,
    patch,
    patchProcess,
    changeType,
    changeMethod,
    selectProcesses,
    changeHosts,
    selectPreview,
    queryProcesses,
    hydrateHosts,
    submit,
  };
}
