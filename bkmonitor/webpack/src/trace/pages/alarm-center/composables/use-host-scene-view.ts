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

import { type MaybeRef, shallowRef, watchEffect } from 'vue';

import { get } from '@vueuse/core';

import { getHostSceneView } from '../services/alarm-detail';

import type { IPanelModel } from 'monitor-ui/chart-plugins/typings';

/**
 * @description 主机场景仪表盘视图配置 hook
 */
export const useHostSceneView = (bizId: MaybeRef<number>) => {
  /** 主机监控 需要渲染的仪表盘面板配置数组 */
  const hostDashboards = shallowRef<IPanelModel[]>(null);
  /** 是否处于请求加载状态 */
  const loading = shallowRef(false);

  /**
   * @description 获取仪表盘数据数组
   */
  const getDashboardPanels = async () => {
    loading.value = true;
    const model = await getHostSceneView(get(bizId));
    hostDashboards.value = model?.panels ?? [];
    loading.value = false;
  };

  watchEffect(getDashboardPanels);
  return {
    hostDashboards,
    loading,
  };
};
