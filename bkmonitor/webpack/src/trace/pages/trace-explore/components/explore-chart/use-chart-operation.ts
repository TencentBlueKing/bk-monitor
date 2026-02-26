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

import { type MaybeRef, shallowRef, watch } from 'vue';

import { get } from '@vueuse/core';

import type { DateValue } from '@blueking/date-picker';

/**
 * @description 图表相关操作
 * 1. 框选，复位
 */
export const useChartOperation = (defaultTimeRange: MaybeRef<DateValue>) => {
  const showRestore = shallowRef(false);
  const timeRange = shallowRef(null);
  const cacheTimeRange = shallowRef(null);

  /**
   * @description 处理数据框选变化
   * @param value 框选范围
   */
  const handleDataZoomChange = (value: any[]) => {
    if (JSON.stringify(timeRange.value) !== JSON.stringify(value)) {
      cacheTimeRange.value = JSON.parse(JSON.stringify(timeRange.value));
      timeRange.value = value;
      showRestore.value = true;
    }
  };

  /**
   * @description 复位时间范围
   */
  const handleRestore = () => {
    const cacheTime = JSON.parse(JSON.stringify(cacheTimeRange.value));
    timeRange.value = cacheTime;
    showRestore.value = false;
  };

  /**
   * @description 初始化默认时间范围
   * @param defaultTimeRange 默认时间范围
   */
  const initDefaultTimeRange = (defaultTimeRange: DateValue) => {
    timeRange.value = defaultTimeRange;
    cacheTimeRange.value = defaultTimeRange;
    showRestore.value = false;
  };

  watch(
    () => get(defaultTimeRange),
    () => {
      initDefaultTimeRange(get(defaultTimeRange));
    },
    { immediate: true }
  );

  return {
    showRestore,
    timeRange,
    cacheTimeRange,
    handleDataZoomChange,
    handleRestore,
    initDefaultTimeRange,
  };
};
