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

import { disableNoDataStrategy, enableNoDataStrategy, fetchNoDataStrategyInfo } from '../services/data-state';

import type { AsyncDialogConfirmEvent, IRumAppBaseParams, IStrategyData } from '../../typings';

export type UseNoDataStrategyReturn = ReturnType<typeof useNoDataStrategy>;

interface UseNoDataStrategyOptions {
  /** 应用 ID */
  applicationId: MaybeRef<number>;
  /** 应用名称 */
  appName: MaybeRef<IRumAppBaseParams['app_name']>;
  /** 业务 ID */
  bizId: MaybeRef<IRumAppBaseParams['bk_biz_id']>;
}

/**
 * @description 无数据告警策略状态管理 Hook
 * @description 负责策略信息初始化加载与开关变更处理
 * @param {UseNoDataStrategyOptions} options - 应用基础参数
 * @returns {UseNoDataStrategyReturn} 策略状态与处理方法
 */
export const useNoDataStrategy = (options: UseNoDataStrategyOptions) => {
  const { applicationId, bizId, appName } = options;
  /** 告警策略信息 */
  const strategyInfo = shallowRef<IStrategyData>(null);
  /** 数据加载状态 */
  const loading = shallowRef(false);
  /** 请求中止控制器 */
  let abortController: AbortController | null = null;

  /**
   * @description 处理无数据告警开关变化，通过 AsyncDialogConfirmEvent 的 resolve/reject 控制 Switcher 状态
   * @param {AsyncDialogConfirmEvent<{ is_enabled: boolean }>} event - 异步确认事件
   * @returns {void}
   */
  const handleEnabledChange = (event: AsyncDialogConfirmEvent<{ is_enabled: boolean }>) => {
    const action = event.payload.is_enabled ? enableNoDataStrategy : disableNoDataStrategy;
    action({ application_id: get(applicationId) })
      .then(() => {
        strategyInfo.value = { ...strategyInfo.value, is_enabled: event.payload.is_enabled };
        event.resolve();
        fetchStrategyInfo();
      })
      .catch(() => event.reject());
  };

  /**
   * @description 获取无数据策略信息
   * @description 通过 Service 层获取数据，Hook 只负责状态管理
   * @returns {Promise<void>}
   */
  const fetchStrategyInfo = async (): Promise<void> => {
    if (!get(bizId) || !get(appName)) return;
    if (abortController) {
      abortController.abort();
    }

    loading.value = true;
    abortController = new AbortController();
    const { signal } = abortController;

    const { data, isAborted } = await fetchNoDataStrategyInfo(
      {
        bk_biz_id: get(bizId),
        app_name: get(appName),
      },
      { signal }
    );

    if (isAborted) return;
    loading.value = false;
    strategyInfo.value = data;
  };

  watchEffect(() => {
    fetchStrategyInfo();
  });

  onScopeDispose(() => {
    if (abortController) {
      abortController.abort();
      abortController = null;
    }
  });

  return {
    handleEnabledChange,
    loading,
    strategyInfo,
  };
};
