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

import { shallowRef, watch, watchEffect } from 'vue';

import { listServiceK8sTargets } from 'monitor-api/modules/apm_container';

import type { AlertK8sTargetItem, K8sTableColumnKeysEnum, SceneEnum } from '../typings';

/** useAlertK8s 入参选项 */
interface UseTraceSpanK8sOptions {
  appName: string;
  bizId: number;
  serviceName: string;
  spanId: string;
}

/**
 * @function useTraceSpanK8s 获取 Trace 下 Span 详情中的容器监控所需参数 hook
 * @description Trace下 Span详情所需的容器监控所需参数 - k8s 可选场景列表 & 关联容器对象列表
 * @param {UseAlertK8sOptions} options 选项参数
 */
export const useTraceSpanK8s = (options: UseTraceSpanK8sOptions) => {
  const { spanId, bizId, serviceName, appName } = options;
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

  /**
   * @method hasTarget 判断是否已经存在目标
   * @param target 目标
   * @returns {boolean} 是否已经存在目标
   */
  const hasTarget = (target: AlertK8sTargetItem) => {
    if (!target) {
      return false;
    }
    return targetList.value.some(item => item?.[groupBy.value] === target?.[groupBy.value]);
  };

  /**
   * @method getTargetList 获取可选择的关联容器对象列表
   * @returns {Promise<void>}
   */
  const getTargetList = async () => {
    const result = await listServiceK8sTargets({
      span_id: spanId,
      bk_biz_id: bizId,
      service_name: serviceName,
      app_name: appName,
    });
    targetList.value = result.target_list.map(item => ({
      ...item,
      display_name: item[item.resource_type],
    }));
  };

  /**
   * @method handleRequest 处理请求
   */
  const handleRequest = async () => {
    loading.value = true;
    await getTargetList();
    if (targetList.value?.length && !hasTarget(currentTarget.value)) {
      currentTarget.value = targetList.value[0];
    }
    loading.value = false;
  };

  watchEffect(handleRequest);

  watch(
    currentTarget,
    () => {
      sceneList.value = currentTarget.value?.scenario_list ?? [];
      scene.value = sceneList.value[0];
      groupBy.value = currentTarget.value?.resource_type;
    },
    { immediate: true, deep: true }
  );

  return {
    scene,
    currentTarget,
    sceneList,
    targetList,
    groupBy,
    loading,
  };
};
