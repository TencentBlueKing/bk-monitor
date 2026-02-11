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

import { getAlertK8sScenarioList, getAlertK8sTarget } from '../services/alarm-detail';

import type { AlertK8sTargetItem, K8sTableColumnKeysEnum, SceneEnum } from '../typings';

/**
 * @function useAlertK8s 获取告警关联的 k8s基础信息 hook
 * @description 告警详情 - k8s 可选场景列表 & 关联容器对象列表
 * @param {MaybeRef<string>} alertId 告警ID
 */
export const useAlertK8s = (alertId: MaybeRef<string>) => {
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
   * @method hasScene 判断是否已经存在场景
   * @param scene 场景
   * @returns {boolean} 是否已经存在场景
   */
  const hasScene = (scene: SceneEnum) => {
    if (!scene) {
      return false;
    }
    return sceneList.value.includes(scene);
  };

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
   * @method getSceneList 获取可选择的场景列表
   * @returns {Promise<void>}
   */
  const getSceneList = async () => {
    const list = await getAlertK8sScenarioList(get(alertId));
    sceneList.value = list;
  };

  /**
   * @method getTargetList 获取可选择的关联容器对象列表
   * @returns {Promise<void>}
   */
  const getTargetList = async () => {
    const result = await getAlertK8sTarget(get(alertId));
    targetList.value = result.target_list;
    groupBy.value = result.resource_type;
  };

  /**
   * @method handleRequest 处理请求
   */
  const handleRequest = async () => {
    loading.value = true;
    await Promise.all([getSceneList(), getTargetList()]);
    if (sceneList.value?.length && !hasScene(scene.value)) {
      scene.value = sceneList.value[0];
    }
    if (targetList.value?.length && !hasTarget(currentTarget.value)) {
      currentTarget.value = targetList.value[0];
    }
    loading.value = false;
  };

  watchEffect(handleRequest);
  return {
    scene,
    currentTarget,
    sceneList,
    targetList,
    groupBy,
    loading,
  };
};
