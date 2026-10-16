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

import { getCollectionExecution } from '../services/collection-history';
import {
  downloadCollectionProfile,
  getCollectionDataTypes,
  getCollectionProfile,
} from '../services/collection-results';
import { canViewHostResult, executionResultRows, resultParams } from '../utils/collection-results';

import type { ProfileResult } from '../types';
import type { CollectionResultSelection } from '../types/collection-history';
import type { CollectionDataType, CollectionHostResult } from '../types/collection-results';

export function useCollectionResultDetail({
  bizId,
  selection,
  source,
  dataType,
  onDataType,
}: {
  bizId: Ref<number>;
  dataType: Ref<string>;
  onDataType: (value: string) => void;
  selection: Ref<CollectionResultSelection>;
  source: Ref<CollectionHostResult | undefined>;
}) {
  const { t } = useI18n();
  const row = shallowRef<CollectionHostResult>();
  const types = shallowRef<CollectionDataType[]>([]);
  const data = shallowRef<ProfileResult>({});
  const loading = shallowRef(false);
  const graphLoading = shallowRef(false);
  const error = shallowRef('');
  const graphError = shallowRef('');
  const exporting = shallowRef(false);
  const selectedType = computed(
    () => types.value.find(type => type.key === dataType.value)?.key || types.value[0]?.key || ''
  );
  let controller: AbortController;
  let graphController: AbortController;
  let exportController: AbortController;

  async function load() {
    controller?.abort();
    graphController?.abort();
    exportController?.abort();
    const current = new AbortController();
    controller = current;
    row.value = undefined;
    types.value = [];
    data.value = {};
    error.value = '';
    graphError.value = '';
    graphLoading.value = false;
    exporting.value = false;
    loading.value = true;
    try {
      const selected = selection.value;
      const host =
        source.value ||
        executionResultRows(await getCollectionExecution(bizId.value, selected, current.signal)).find(
          item => item.bk_host_id === selected.bk_host_id
        );
      if (current.signal.aborted) return;
      if (!host) throw new Error(t('未找到本次采集的主机'));
      row.value = host;
      if (!canViewHostResult(host)) throw new Error(t('本次采集暂无可查看的结果'));
      const result = await getCollectionDataTypes(resultParams(host, bizId.value), current.signal);
      if (!current.signal.aborted) types.value = result.data_types;
    } catch (e) {
      if (!current.signal.aborted) error.value = (e as Error)?.message || t('采集结果加载失败，请重试');
    } finally {
      if (!current.signal.aborted) loading.value = false;
    }
  }

  async function loadProfile() {
    graphController?.abort();
    exportController?.abort();
    exporting.value = false;
    graphLoading.value = false;
    graphError.value = '';
    data.value = {};
    if (!row.value || !selectedType.value) return;
    const current = new AbortController();
    graphController = current;
    graphLoading.value = true;
    try {
      const result = await getCollectionProfile(
        resultParams(row.value, bizId.value),
        selectedType.value,
        current.signal
      );
      if (!current.signal.aborted) data.value = result;
    } catch (e) {
      if (!current.signal.aborted) graphError.value = (e as Error)?.message || t('采集结果加载失败，请重试');
    } finally {
      if (!current.signal.aborted) graphLoading.value = false;
    }
  }

  async function exportProfile() {
    if (exporting.value || loading.value || graphLoading.value || !row.value || !selectedType.value) return;
    const current = new AbortController();
    exportController = current;
    exporting.value = true;
    try {
      const file = await downloadCollectionProfile(
        resultParams(row.value, bizId.value),
        selectedType.value,
        current.signal
      );
      if (current.signal.aborted) return;
      const url = URL.createObjectURL(file.data);
      const link = document.createElement('a');
      link.href = url;
      link.download = file.filename || `profiling-${row.value.bk_host_id}-${row.value.scheduled_at}.pprof`;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      Message({ theme: 'success', message: t('pprof 文件已生成，请查看浏览器下载列表') });
    } catch (e) {
      if (!current.signal.aborted) Message({ theme: 'error', message: t((e as Error)?.message || '导出失败，请重试') });
    } finally {
      if (!current.signal.aborted) exporting.value = false;
    }
  }

  watch([bizId, () => JSON.stringify(selection.value)], load, { immediate: true });
  watch(selectedType, value => {
    if (value && value !== dataType.value) onDataType(value);
    loadProfile();
  });
  onScopeDispose(() => {
    controller?.abort();
    graphController?.abort();
    exportController?.abort();
  });
  return {
    row,
    types,
    data,
    loading,
    graphLoading,
    error,
    graphError,
    exporting,
    selectedType,
    load,
    loadProfile,
    exportProfile,
  };
}
