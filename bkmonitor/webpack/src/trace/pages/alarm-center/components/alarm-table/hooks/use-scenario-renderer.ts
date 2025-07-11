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

import { computed, onBeforeUnmount, onMounted, watch } from 'vue';

import { useAlarmCenterStore } from '../../../../../store/modules/alarm-center';
import { ACTION_STORAGE_KEY } from '../../../services/action-services';
import { ALERT_STORAGE_KEY } from '../../../services/alert-services';
import { INCIDENT_STORAGE_KEY } from '../../../services/incident-services';
import { ActionScenario } from '../scenarios/action-scenario';
import { AlertScenario } from '../scenarios/alert-scenario';
import { IncidentScenario } from '../scenarios/incident-scenario';

import type { TableColumnItem } from '../../../typings';
import type { BaseScenario } from '../scenarios/base-scenario';

export function useScenarioRenderer(context: any) {
  const alarmStore = useAlarmCenterStore();

  // 场景映射表
  const scenarioMap: Record<string, new (ctx: any) => BaseScenario> = {
    [ALERT_STORAGE_KEY]: AlertScenario,
    [INCIDENT_STORAGE_KEY]: IncidentScenario,
    [ACTION_STORAGE_KEY]: ActionScenario,
  };

  // 当前场景实例
  const currentScenario = computed<BaseScenario>(() => {
    const storageKey = alarmStore.alarmService.storageKey;
    // eslint-disable-next-line @typescript-eslint/naming-convention
    const ScenarioClass = scenarioMap[storageKey] || AlertScenario; // 默认告警场景
    return new ScenarioClass(context);
  });

  /**
   * @description 转换列配置
   */
  function transformColumns(columns: TableColumnItem[]) {
    const isAlert = currentScenario.value.name === ALERT_STORAGE_KEY;
    const targetColumns = [];

    if (isAlert) {
      // 告警场景需要添加多选列
      targetColumns.push({
        colKey: 'row-select',
        type: 'multiple',
        width: 50,
        minWidth: 50,
      });
    }
    const scenarioColumns = currentScenario.value.getColumnsConfig();
    for (const column of columns) {
      const scenarioConfig = scenarioColumns[column.colKey];
      const targetColumn = scenarioConfig ? { ...column, ...scenarioConfig } : column;
      targetColumns.push(targetColumn);
    }
    return targetColumns;
  }

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
  });

  return {
    currentScenario,
    transformColumns,
  };
}
