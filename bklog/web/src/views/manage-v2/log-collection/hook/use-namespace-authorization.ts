/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
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

import { computed, onBeforeUnmount, ref } from 'vue';
import $http from '@/api';

export interface IAuthorizedNamespace {
  name: string;
  alias: string | null;
  bk_biz_id: number | null;
  is_authorized: boolean;
}

export interface INamespaceAuthorizationResult {
  name: string;
  bk_data_id: number;
  data_source_name: string;
  is_authorized: boolean;
}

export const namespaceLabel = (item: IAuthorizedNamespace): string => item.alias || item.name;

export const namespaceDataSourceUrl = (baseUrl: string, data: INamespaceAuthorizationResult): string => {
  const params = new URLSearchParams({
    project_id: data.name,
    search: JSON.stringify({ raw_data_id: String(data.bk_data_id) }),
  });
  return `${baseUrl}/v4/webserver/#/data-source?${params}`;
};

/** 数据加工弹窗的空间列表及授权状态。 */
export const useNamespaceAuthorization = () => {
  const namespaces = ref<IAuthorizedNamespace[]>([]);
  const selectedName = ref('');
  const selectedNamespace = computed(() => namespaces.value.find(item => item.name === selectedName.value));
  const loading = ref(false);
  const submitting = ref(false);
  let collectorId: number | string = '';
  let loadVersion = 0;

  const reset = () => {
    loadVersion += 1;
    collectorId = '';
    namespaces.value = [];
    selectedName.value = '';
    loading.value = false;
    submitting.value = false;
  };

  onBeforeUnmount(reset);

  const load = async (id: number | string) => {
    reset();
    const version = loadVersion;
    collectorId = id;
    if (!id) return;
    loading.value = true;
    try {
      const res = await $http.request('collect/authorizedNamespaces', {
        params: { collector_config_id: id },
      });
      if (version !== loadVersion) return;
      namespaces.value = res.result && Array.isArray(res.data) ? res.data : [];
    } catch {
      // 请求层统一反馈错误；弹窗只恢复为空列表。
      if (version === loadVersion) namespaces.value = [];
    } finally {
      if (version === loadVersion) loading.value = false;
    }
  };

  const authorize = async (): Promise<INamespaceAuthorizationResult | null> => {
    if (submitting.value || loading.value || !selectedNamespace.value || !collectorId) return null;
    const name = selectedName.value;
    submitting.value = true;
    try {
      const res = await $http.request('collect/authorizeNamespace', {
        params: { collector_config_id: collectorId },
        data: { name },
      });
      if (
        !res.result ||
        !res.data?.is_authorized ||
        !res.data.name ||
        res.data.bk_data_id === null ||
        res.data.bk_data_id === undefined
      ) {
        return null;
      }
      namespaces.value = namespaces.value.map(item => (item.name === name ? { ...item, is_authorized: true } : item));
      return res.data as INamespaceAuthorizationResult;
    } catch {
      // 请求层已处理错误，此处仅保留选项并恢复提交状态。
      return null;
    } finally {
      submitting.value = false;
    }
  };

  return {
    namespaces,
    selectedName,
    selectedNamespace,
    loading,
    submitting,
    load,
    reset,
    authorize,
  };
};
