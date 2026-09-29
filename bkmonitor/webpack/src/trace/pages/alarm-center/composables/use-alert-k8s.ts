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

import { getAlertK8sTarget } from '../services/alarm-detail';

import type { AlertK8sTargetItem, K8sTableColumnKeysEnum, SceneEnum } from '../typings';

/** useAlertK8s 入参选项 */
interface UseAlertK8sOptions {
  /** 告警ID */
  alertId: MaybeRef<string>;
  /** 业务ID */
  bizId: MaybeRef<number>;
}

/**
 * @function useAlertK8s 获取告警关联的 k8s基础信息 hook
 * @description 告警详情 - k8s 可选场景列表 & 关联容器对象列表
 * @param {UseAlertK8sOptions} options 选项参数
 * @param {MaybeRef<string>} options.alertId 告警ID
 * @param {MaybeRef<number>} options.bizId 业务ID
 */
export const useAlertK8s = (options: UseAlertK8sOptions) => {
  const { alertId, bizId } = options;
  /** 场景 */
  const scene = shallowRef<SceneEnum>();
  /** 当前选择的关联容器对象 */
  const currentTarget = shallowRef<AlertK8sTargetItem>();
  /** 可选择的场景列表 */
  const sceneList = shallowRef<SceneEnum[]>([]);
  /** 可选择的关联容器对象列表 */
  const targetList = shallowRef<AlertK8sTargetItem[]>([]);
  /** 汇聚维度 */
  const groupBy = shallowRef<K8sTableColumnKeysEnum>();
  /** 数据请求加载状态 */
  const loading = shallowRef(false);

  const error = shallowRef(false);
  const revision = shallowRef(0);
  watch([() => get(alertId), () => get(bizId), revision], async (_, __, onCleanup) => {
    let active = true;
    onCleanup(() => { active = false; });
    loading.value = true;
    error.value = false;
    currentTarget.value = undefined;
    targetList.value = [];
    sceneList.value = [];
    scene.value = undefined;
    try {
      const result = await getAlertK8sTarget({ alertId: get(alertId), bizId: get(bizId) });
      if (!active) return;
      targetList.value = result.target_list;
      groupBy.value = result.resource_type;
      currentTarget.value = targetList.value[0];
      sceneList.value = currentTarget.value?.scenario_list ?? [];
      scene.value = sceneList.value[0];
    } catch {
      if (active) error.value = true;
    } finally {
      if (active) loading.value = false;
    }
  }, { immediate: true });
  return {
    error,
    retry: () => { revision.value++; },
    scene,
    currentTarget,
    sceneList,
    targetList,
    groupBy,
    loading,
  };
};
