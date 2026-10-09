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

import { type MaybeRef, watch } from 'vue';

import { get } from '@vueuse/core';
import dayjs from 'dayjs';

import { useRumRequest } from '../../hooks/use-rum-request';
import { fetchDataSampling } from '../services/data-state';

import type { IDataSamplingItem, IRumAppBaseParams } from '../../typings';

export type UseDataSamplingReturnType = ReturnType<typeof useDataSampling>;

interface UseDataSamplingOptions {
  /** 应用名称 */
  appName: MaybeRef<IRumAppBaseParams['app_name']>;
  /** 业务 ID */
  bizId: MaybeRef<IRumAppBaseParams['bk_biz_id']>;
}

/**
 * @description 数据采样获取与状态管理 Hook
 * @description 负责采样数据初始化加载与刷新处理
 * @param {UseDataSamplingOptions} options - 配置选项
 * @returns {UseDataSamplingReturnType} 状态和方法
 */
export const useDataSampling = (options: UseDataSamplingOptions) => {
  const { bizId, appName } = options;
  const request = useRumRequest<IDataSamplingItem[]>(async signal => {
    const data = await fetchDataSampling({ bk_biz_id: get(bizId), app_name: get(appName) }, { signal });
    return (data || []).map(item => {
      const date = dayjs.tz(dayjs(item.sampling_time));
      return { ...item, sampling_time: date.isValid() ? date.format('YYYY-MM-DD HH:mm:ssZ') : '--' };
    });
  }, []);

  watch(
    () => [get(bizId), get(appName)],
    () => {
      if (get(bizId) && get(appName)) request.run();
    },
    { immediate: true }
  );

  return {
    samplingList: request.data,
    loading: request.loading,
    error: request.error,
    handleRefresh: request.run,
  };
};
