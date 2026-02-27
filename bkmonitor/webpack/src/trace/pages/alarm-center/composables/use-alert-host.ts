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

import { getHostTargetList } from '../services/alarm-detail';
import { type AlertHostTargetItem } from '../typings';

/**
 * @function useAlertHost 获取告警关联的主机基础信息 hook
 * @description 告警详情 - 主机 获取告警关联主机对象列表
 * @param {MaybeRef<string>} alertId 告警ID
 */
export const useAlertHost = (alertId: MaybeRef<string>) => {
  /** 当前选中的主机对象 */
  const currentTarget = shallowRef<AlertHostTargetItem | null>({
    bk_target_ip: '0.0.0.0',
    bk_cloud_id: 0,
  });
  /** 告警关联主机对象列表 */
  const targetList = shallowRef<AlertHostTargetItem[]>([]);
  /** 数据请求加载状态 */
  const loading = shallowRef(false);

  /**
   * @method hasTarget 判断是否已经存在目标
   * @param target 目标
   * @returns {boolean} 是否已经存在目标
   */
  const hasTarget = (target: AlertHostTargetItem) => {
    if (!target) {
      return false;
    }
    return targetList.value.some(item => item?.bk_host_id === target?.bk_host_id);
  };

  /**
   * @method getHostList 获取可选择的关联主机对象列表
   * @returns {Promise<void>}
   */
  const getHostList = async () => {
    loading.value = true;
    targetList.value = await getHostTargetList(get(alertId));
    if (targetList.value?.length && !hasTarget(currentTarget.value)) {
      currentTarget.value = targetList.value[0];
    }
    loading.value = false;
  };

  watchEffect(getHostList);
  return {
    targetList,
    loading,
    currentTarget,
  };
};
