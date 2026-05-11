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

import { onScopeDispose, shallowRef, watchEffect } from 'vue';

import { useAlarmCenterStore } from '@/store/modules/alarm-center';

import type { CommonCondition, QuickFilterItem } from '../typings';
import type { EmptyStatusOperationType, EmptyStatusType } from '@/components/empty-status/empty-status';

export function useQuickFilter() {
  const alarmStore = useAlarmCenterStore();
  /** 快捷筛选列表 */
  const quickFilterList = shallowRef<QuickFilterItem[]>([]);
  /**
   * 是否是第一次初始化
   * 不同阶段的初始化所展示的loading效果不一致
   */
  const isFirstInit = shallowRef(true);

  const quickFilterLoading = shallowRef(false);
  const quickFilterEmptyStatusType = shallowRef<EmptyStatusType>('empty');

  // 请求中止控制器
  let abortController: AbortController | null = null;
  const effectFunc = async () => {
    // 中止上一次未完成的请求
    if (abortController) {
      abortController.abort();
    }
    // 创建新的中止控制器
    abortController = new AbortController();
    const { signal } = abortController;

    quickFilterLoading.value = true;
    quickFilterEmptyStatusType.value = 'empty';
    const quickFilter = await alarmStore.alarmService.getQuickFilterList(alarmStore.commonFilterParams, { signal });
    // 检查请求是否已被中止，确保不会更新过期数据
    if (signal.aborted) return;
    /** 最后一次操作的分类不同步最新数量 */
    const index = quickFilter.findIndex(item => item.id === alarmStore.lastQuickFilterOperationCategory);
    if (index !== -1 && alarmStore.lastQuickFilterOperationCategoryData) {
      quickFilter[index] = alarmStore.lastQuickFilterOperationCategoryData;
    }
    quickFilterList.value = quickFilter;
    isFirstInit.value = false;
    quickFilterLoading.value = false;
  };
  watchEffect(effectFunc, { flush: 'post' });

  const updateQuickFilterValue = (value: CommonCondition[]) => {
    alarmStore.quickFilterValue = value;
  };

  const handleQuickFilteringOperation = (operator: EmptyStatusOperationType) => {
    if (operator === 'refresh') {
      effectFunc();
      return;
    }

    if (operator === 'clear-filter') {
      updateQuickFilterValue([]);
    }
  };

  onScopeDispose(() => {
    quickFilterList.value = [];
    quickFilterLoading.value = false;
  });
  return {
    isFirstInit,
    quickFilterEmptyStatusType,
    quickFilterList,
    quickFilterLoading,
    quickFilterValue: alarmStore.quickFilterValue,
    updateQuickFilterValue,
    handleQuickFilteringOperation,
  };
}
