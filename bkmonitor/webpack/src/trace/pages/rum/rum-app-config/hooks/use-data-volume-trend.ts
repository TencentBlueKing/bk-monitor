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

import { type MaybeRef, onScopeDispose, shallowRef, watchEffect } from 'vue';

import { get } from '@vueuse/core';

import { fetchDataViewConfig } from '../services/data-state';

import type { IRumAppBaseParams } from '../../typings';
import type { IPanelModel } from 'monitor-ui/chart-plugins/typings';

export type UseDataVolumeTrendReturnType = ReturnType<typeof useDataVolumeTrend>;

interface UseDataVolumeTrendOptions {
  appName: MaybeRef<IRumAppBaseParams['app_name']>;
  bizId: MaybeRef<IRumAppBaseParams['bk_biz_id']>;
}

/**
 * @description 数据量趋势图表数据获取与状态管理 Hook
 * @description 仅负责调用 Service 层和 Vue 状态管理，不直接请求接口
 * @param {UseDataVolumeTrendOptions} options - 配置选项
 * @returns {UseDataVolumeTrendReturn} 状态和方法
 */
export const useDataVolumeTrend = (options: UseDataVolumeTrendOptions) => {
  const { bizId, appName } = options;
  /** 图表面板配置列表 */
  const dashboardPanels = shallowRef<IPanelModel[]>([]);
  /** 数据加载状态 */
  const loading = shallowRef(false);
  /** 请求中止控制器 */
  let abortController: AbortController | null = null;

  /**
   * @description 获取数据视图配置
   * @description 通过 Service 层获取数据，Hook 只负责状态管理
   * @returns {Promise<void>}
   */
  const fetchDashboardConfig = async (): Promise<void> => {
    if (!get(bizId) || !get(appName)) return;
    if (abortController) {
      abortController.abort();
    }
    loading.value = true;
    abortController = new AbortController();
    const { signal } = abortController;

    const { data, isAborted } = await fetchDataViewConfig(
      {
        bk_biz_id: get(bizId),
        app_name: get(appName),
      },
      { signal }
    );

    if (isAborted) return;
    loading.value = false;
    dashboardPanels.value = data;
  };

  watchEffect(() => {
    fetchDashboardConfig();
  });

  onScopeDispose(() => {
    if (abortController) {
      abortController.abort();
      abortController = null;
    }
  });

  return {
    dashboardPanels,
    loading,
  };
};
