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
import { type MaybeRef, shallowRef, watch, watchEffect } from 'vue';

import { get } from '@vueuse/core';

import { getK8sScenarioMetricList } from '../services/alarm-detail';

import type { IK8SMetricItem, SceneEnum } from 'monitor-pc/pages/monitor-k8s/typings/k8s-new';

/**
 * @description 容器监控图表面板 panel hook
 */
export function useK8sChartPanel(scene: MaybeRef<SceneEnum>) {
  /** 容器监控-场景需要展示的指标项数组 */
  let _metricList: IK8SMetricItem[] = [];
  const panels = shallowRef([]);
  /** 是否处于请求加载状态 */
  const loading = shallowRef(false);
  /**
   * @description 获取场景指标列表
   */
  async function getScenarioMetricList() {
    console.log('getScenarioMetricList');
    loading.value = true;
    _metricList = await getK8sScenarioMetricList(get(scene));
    loading.value = false;
  }

  async function _createPanelList(hasLoading = true) {
    if (hasLoading) {
      loading.value = true;
    }
  }
  watch(
    () => scene,
    () => {
      console.log('scene change');
    }
  );
  watchEffect(getScenarioMetricList);
  return { panels };
}
