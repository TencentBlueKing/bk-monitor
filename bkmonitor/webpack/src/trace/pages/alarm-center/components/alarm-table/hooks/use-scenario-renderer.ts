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

import { type MaybeRef, computed, onBeforeUnmount, onMounted, watch } from 'vue';

import { useAlarmCenterStore } from '../../../../../store/modules/alarm-center';
import { ACTION_STORAGE_KEY } from '../../../services/action-services';
import { ALERT_STORAGE_KEY } from '../../../services/alert-services';
import { INCIDENT_STORAGE_KEY } from '../../../services/incident-services';
import { ActionScenario } from '../scenarios/action-scenario';
import { AlertScenario } from '../scenarios/alert-scenario';
import { IncidentScenario } from '../scenarios/incident-scenario';

import type { TableColumnItem, TableEmpty } from '../../../typings';
import type { BaseScenario } from '../scenarios/base-scenario';

export interface ScenarioRenderer {
  /** 当前场景实例 */
  currentScenario: MaybeRef<BaseScenario>;
  /** 当前场景表格空状态配置 */
  tableEmpty: MaybeRef<TableEmpty>;
  /** 当前场景私有类名 */
  tableScenarioClassName: MaybeRef<string>;
  /** 转换列配置 */
  transformColumns: (columns: TableColumnItem[]) => TableColumnItem[];
}

/**
 * @function useScenarioRenderer 表格场景工厂渲染器 hook
 * @description 用于渲染告警中心不同场景的表格
 * @param {ActionScenario['context'] & AlertScenario['context'] & IncidentScenario['context']} context 场景上下文
 * @returns {ScenarioRenderer} 当前激活的场景渲染器相关属性
 */
export const useScenarioRenderer = (
  context: ActionScenario['context'] & AlertScenario['context'] & IncidentScenario['context']
): ScenarioRenderer => {
  const alarmStore = useAlarmCenterStore();
  /** 场景渲染器实例缓存映射，由于是无状态类，所以用 Map 缓存场景实例，避免重复创建节省资源 */
  let scenarioInstanceMap = new Map<string, BaseScenario>();
  /** 场景渲染器类映射 */
  const scenarioMap: Record<
    string,
    new (ctx: ActionScenario['context'] & AlertScenario['context'] & IncidentScenario['context']) => BaseScenario
  > = {
    [ALERT_STORAGE_KEY]: AlertScenario,
    [INCIDENT_STORAGE_KEY]: IncidentScenario,
    [ACTION_STORAGE_KEY]: ActionScenario,
  };
  /** 当前激活的场景渲染器实例 */
  const currentScenario = computed<BaseScenario>(() => {
    const storageKey = alarmStore.alarmService.storageKey;
    // eslint-disable-next-line @typescript-eslint/naming-convention
    const ScenarioClass = scenarioMap[storageKey] || AlertScenario; // 默认告警场景
    if (!scenarioInstanceMap.has(storageKey)) {
      scenarioInstanceMap.set(storageKey, new ScenarioClass(context));
    }
    return scenarioInstanceMap.get(storageKey);
  });
  /** 当前场景表格空状态时显示的dom内容配置 */
  const tableEmpty = computed<TableEmpty>(() => currentScenario.value.getEmptyConfig());
  /** 当前场景私有类名 */
  const tableScenarioClassName = computed(() => currentScenario.value.privateClassName || '');

  /**
   * @method transformColumns 转换列配置
   * @description 将基础列配置转换为场景渲染所需结构列配置
   * @param {TableColumnItem[]} columns 基础列配置
   * @returns {TableColumnItem[]} 场景渲染所需结构列配置
   */
  const transformColumns = (columns: TableColumnItem[]) => {
    const isAlert = currentScenario.value.name === ALERT_STORAGE_KEY;
    const targetColumns = [];

    if (isAlert) {
      // 告警场景需要添加多选列
      targetColumns.push({
        colKey: 'row-select',
        type: 'multiple',
        width: 50,
        minWidth: 50,
        fixed: 'left',
      });
    }
    const scenarioColumns = currentScenario.value.getMergedColumnsConfig();
    for (const column of columns) {
      const scenarioConfig = scenarioColumns[column.colKey];
      const targetColumn = scenarioConfig ? { ...column, ...scenarioConfig } : column;
      targetColumns.push(targetColumn);
    }
    return targetColumns;
  };

  watch(
    () => currentScenario.value,
    (newScenario, oldScenario) => {
      oldScenario.cleanup?.();
      newScenario.initialize?.();
    }
  );

  // 生命周期管理
  onMounted(() => {
    currentScenario.value?.initialize?.();
  });

  onBeforeUnmount(() => {
    currentScenario.value?.cleanup?.();
    scenarioInstanceMap.clear();
    scenarioInstanceMap = null;
  });

  return {
    currentScenario,
    tableEmpty,
    tableScenarioClassName,
    transformColumns,
  };
};
