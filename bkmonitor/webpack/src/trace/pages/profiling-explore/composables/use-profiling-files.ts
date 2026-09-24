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
import { type Ref, computed, nextTick, onScopeDispose, shallowRef, watch } from 'vue';

import { useI18n } from 'vue-i18n';

import { getProfileFiles } from '../services/files';
import { getLabelKeys, getLabelValues } from '../services/profiling';
import { buildFileQuery, createFileQueryState } from '../utils/query';
import { type IFilterField, type IGetValueFnParams, EFieldType, EMethod } from '@/components/retrieval-filter/typing';

import type { ProfileQuery, ProfileViewState, QueryState, SelectionRange } from '../types';
import type { FileQueryState, ProfileFile } from '../types/file';

export type UseProfilingFilesReturn = ReturnType<typeof useProfilingFiles>;

export function useProfilingFiles({
  state,
  bizId,
  patch,
  resolveRange,
}: {
  bizId: Ref<number>;
  patch: (value: Partial<QueryState>) => void;
  resolveRange: () => SelectionRange;
  state: Ref<QueryState>;
}) {
  const { t } = useI18n();
  const records = shallowRef<ProfileFile[]>([]);
  const loading = shallowRef(false);
  const initializing = shallowRef(true);
  const error = shallowRef('');
  const labelError = shallowRef('');
  const fields = shallowRef<IFilterField[]>([]);
  const submitted = shallowRef<null | ProfileQuery>(null);
  const revision = shallowRef(0);
  const refreshBusy = shallowRef(false);
  const active = computed(() => state.value.view.tab === 'file');
  const selected = computed(() => records.value.find(item => item.profile_id === state.value.file.profileId));
  const pending = (file: ProfileFile) => ['uploaded', 'parsing_succeed'].includes(file.status);
  let listController: AbortController;
  let labelController: AbortController;
  let valueController = new AbortController();
  let pollTimer: ReturnType<typeof setTimeout>;
  let disposed = false;
  let filterPending = false;
  const valueCache = new Map<string, Promise<string[]>>();

  function patchFile(value: Partial<FileQueryState>) {
    patch({ file: { ...state.value.file, ...value } });
  }

  function patchView(value: Partial<ProfileViewState>) {
    patchFile({ view: { ...state.value.file.view, ...value } });
  }

  function setRefreshBusy(value: boolean) {
    refreshBusy.value = value;
  }

  function clearLabels() {
    labelController?.abort();
    valueController.abort();
    valueController = new AbortController();
    valueCache.clear();
    fields.value = [];
    labelError.value = '';
  }

  async function loadLabels() {
    clearLabels();
    if (!submitted.value || !active.value) return;
    const current = new AbortController();
    labelController = current;
    try {
      const keys = await getLabelKeys(submitted.value, current.signal);
      if (current.signal.aborted) return;
      fields.value = keys
        .filter(key => !['start', 'end', '__proto__', 'constructor', 'prototype'].includes(key))
        .map(key => ({
          name: key,
          alias: key,
          type: EFieldType.keyword,
          isEnableOptions: true,
          methods: [{ value: EMethod.eq, alias: '=' }],
        }));
    } catch {
      if (!current.signal.aborted) labelError.value = t('标签加载失败，请重试');
    }
  }

  function executeQuery(refreshLabels = false) {
    filterPending = false;
    if (!active.value) return;
    if (selected.value?.status !== 'store_succeed' || !state.value.file.dataType) {
      submitted.value = null;
      return;
    }
    try {
      const range = resolveRange();
      const query = buildFileQuery(state.value, bizId.value, range);
      patch({ resolvedTimeRange: range });
      submitted.value = query;
      revision.value += 1;
      error.value = '';
      if (refreshLabels || !fields.value.length) loadLabels();
    } catch (e) {
      submitted.value = null;
      error.value = t((e as Error).message);
    }
  }

  function prepareFile(file: ProfileFile, resetTime: boolean) {
    submitted.value = null;
    clearLabels();
    if (file.status !== 'store_succeed') return;
    const selectedType = file.data_types.find(item => item.key === state.value.file.dataType);
    const dataType = selectedType || file.data_types[0];
    patchFile({
      fileName: file.file_name,
      dataType: dataType?.key || '',
      aggregation: selectedType ? state.value.file.aggregation : dataType?.default_agg_method || 'AVG',
    });
    if (resetTime) {
      const start = Number(file.query_start_time);
      const end = Number(file.query_end_time);
      if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) {
        error.value = t('文件时间范围无效，请重新上传');
        return;
      }
      patch({ timeRange: [start / 1000, end / 1000], baselineRange: null, comparisonRange: null });
    }
    patchFile({ pendingTimeRange: false });
    executeQuery(true);
  }

  function selectFile(file: ProfileFile) {
    error.value = '';
    patchFile({
      ...createFileQueryState(),
      profileId: file.profile_id,
      fileName: file.file_name,
      pendingTimeRange: pending(file),
    });
    prepareFile(file, true);
  }

  function schedulePoll() {
    clearTimeout(pollTimer);
    if (disposed || !active.value || !records.value.some(pending)) return;
    pollTimer = setTimeout(() => {
      if (document.hidden) schedulePoll();
      else refreshRecords();
    }, 3000);
  }

  async function refreshRecords(restore = false) {
    if (!active.value || disposed) return;
    listController?.abort();
    const current = new AbortController();
    listController = current;
    loading.value = true;
    error.value = '';
    if (restore) {
      initializing.value = true;
      submitted.value = null;
      clearLabels();
    }
    try {
      const previous = selected.value;
      const result = await getProfileFiles(bizId.value, current.signal);
      if (current.signal.aborted) return;
      records.value = result;
      if (!state.value.file.profileId) {
        const first = result.find(item => item.status === 'store_succeed') || result[0];
        if (first) selectFile(first);
      } else if (!selected.value) {
        submitted.value = null;
        clearLabels();
        error.value = t('文件不存在或已过期，请重新选择或上传');
      } else if (restore || previous?.status !== selected.value.status) {
        const resetTime = state.value.file.pendingTimeRange;
        prepareFile(selected.value, resetTime);
      }
    } catch (e) {
      if (!current.signal.aborted) error.value = (e as Error)?.message || t('文件列表加载失败，请重试');
    } finally {
      if (!current.signal.aborted) {
        loading.value = false;
        initializing.value = false;
        schedulePoll();
      }
    }
  }

  function acceptUploaded(file: ProfileFile) {
    if (!active.value) return;
    listController?.abort();
    loading.value = false;
    initializing.value = false;
    records.value = [file, ...records.value.filter(item => item.profile_id !== file.profile_id)];
    selectFile(file);
    schedulePoll();
  }

  function changeFilters(value: Partial<Pick<FileQueryState, 'commonWhere' | 'where'>>) {
    if (
      Object.entries(value).every(
        ([key, conditions]) => JSON.stringify(state.value.file[key]) === JSON.stringify(conditions)
      )
    )
      return;
    patchFile(value);
    if (filterPending) return;
    filterPending = true;
    nextTick(() => {
      if (filterPending && !disposed) executeQuery();
    });
  }

  function selectDataType(value: string) {
    const item = selected.value?.data_types.find(item => item.key === value);
    if (!item) return;
    patchFile({ dataType: value, aggregation: item.default_agg_method || 'AVG' });
    executeQuery(true);
  }

  async function getFieldValues(params: IGetValueFnParams) {
    const field = params.fields?.[0];
    if (!submitted.value || !field) return { count: 0, list: [] };
    const current = valueController;
    const limit = Math.max(params.limit || 50, 50);
    const key = `${field}:${limit}`;
    let request = valueCache.get(key);
    if (!request) {
      request = getLabelValues(submitted.value, field, limit, current.signal);
      valueCache.set(key, request);
    }
    try {
      const values = await request;
      if (current.signal.aborted) return { count: 0, list: [] };
      const search = String(params.where?.find(item => item.key === field)?.value?.[0] ?? '').toLowerCase();
      const matched = values.filter(value => value.toLowerCase().includes(search));
      return {
        count: values.length === limit ? limit + 1 : matched.length,
        list: matched.map(value => ({ id: value, name: value })),
      };
    } catch {
      if (!current.signal.aborted) {
        valueCache.delete(key);
        labelError.value = t('标签值加载失败，请重试');
      }
      return { count: 0, list: [] };
    }
  }

  function suspend() {
    listController?.abort();
    loading.value = false;
    clearTimeout(pollTimer);
    clearLabels();
    filterPending = false;
  }

  function reset() {
    suspend();
    records.value = [];
    initializing.value = true;
    submitted.value = null;
    error.value = '';
  }

  watch(active, value => {
    if (!value) suspend();
  });
  onScopeDispose(() => {
    disposed = true;
    suspend();
  });

  return {
    bizId,
    records,
    selected,
    loading,
    initializing,
    error,
    labelError,
    fields,
    active,
    submitted,
    revision,
    refreshBusy,
    setRefreshBusy,
    patchFile,
    patchView,
    refreshRecords,
    selectFile,
    acceptUploaded,
    executeQuery,
    changeFilters,
    selectDataType,
    getFieldValues,
    loadLabels,
    reset,
  };
}
