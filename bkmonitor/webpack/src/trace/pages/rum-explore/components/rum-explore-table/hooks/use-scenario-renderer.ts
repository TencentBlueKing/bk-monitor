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
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
 * rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 */

import { type ComputedRef, type MaybeRef, computed, onBeforeUnmount, onMounted, watch } from 'vue';

import { get } from '@vueuse/core';

import { RumModeEnum } from '../../../constants';
import { SpanScenario } from '../scenarios/span-scenario';

import type { BaseTableColumn } from '../../../../trace-explore/components/trace-explore-table/typing';
import type { RumModeType } from '../../../typings';
import type { BaseScenario } from '../scenarios/base-scenario';

export interface ScenarioRenderer {
  /** 当前场景实例 */
  currentScenario: ComputedRef<BaseScenario>;
  /** 当前表格行唯一键（取当前场景声明，避免新增场景时遗漏同步硬编码值） */
  tableRowKey: ComputedRef<string>;
  /** 当前场景私有类名 */
  tableScenarioClassName: ComputedRef<string>;
  /** 转换列配置：将场景声明式配置注入基础列 */
  transformColumns: (baseColumns: BaseTableColumn[]) => BaseTableColumn[];
}

/**
 * @function useScenarioRenderer 表格场景工厂渲染器 hook
 * @description 按检索模式选择场景渲染器实例（session / view 场景待实现），未注册的场景模式将显式抛错，
 *              负责将基础列（列展示元数据）注入场景产出的声明式渲染配置（renderType 等），
 *              实现「列展示」「场景配置」「渲染执行」三者分离
 * @param {MaybeRef<RumModeType>} mode 检索视角（由组件以 prop 显式传入，避免隐式依赖全局 store）
 * @param {SpanScenario['context']} context 场景上下文（包含 fieldMap）
 * @returns {ScenarioRenderer} 当前激活的场景渲染器相关属性
 */
export const useScenarioRenderer = (
  mode: MaybeRef<RumModeType>,
  context: SpanScenario['context']
): ScenarioRenderer => {
  /** 场景渲染器实例缓存映射，由于是无状态类，所以用 Map 缓存场景实例，避免重复创建节省资源 */
  let scenarioInstanceMap = new Map<string, BaseScenario>();
  /** 场景渲染器类映射 */
  const scenarioMap: Partial<Record<RumModeType, new (ctx: SpanScenario['context']) => BaseScenario>> = {
    [RumModeEnum.SPAN]: SpanScenario,
  };
  /** 当前激活的场景渲染器实例 */
  const currentScenario = computed<BaseScenario>(() => {
    const m = get(mode);
    // eslint-disable-next-line @typescript-eslint/naming-convention
    const ScenarioClass = scenarioMap[m];
    if (!ScenarioClass) {
      throw new Error(
        `[useScenarioRenderer] 未注册的场景模式 "${m}"，已支持的场景: ${Object.keys(scenarioMap).join(', ')}。`
      );
    }
    if (!scenarioInstanceMap.has(m)) {
      scenarioInstanceMap.set(m, new ScenarioClass(context));
    }
    return scenarioInstanceMap.get(m);
  });
  /** 当前场景私有类名 */
  const tableScenarioClassName = computed(() => currentScenario.value.privateClassName || '');
  /** 当前表格行唯一键：取当前场景声明，避免新增场景时遗漏同步硬编码值 */
  const tableRowKey = computed(() => currentScenario.value?.rowKey || 'span_id');

  /**
   * @method transformColumns 转换列配置
   * @description 将基础列注入场景产出的声明式渲染配置（renderType 等），渲染由内置公共列渲染按 renderType 分派
   * @param {BaseTableColumn[]} baseColumns 基础列配置（已包含表头渲染）
   * @returns {BaseTableColumn[]} 场景渲染所需的最终列配置
   */
  const transformColumns = (baseColumns: BaseTableColumn[]) => {
    if (!baseColumns?.length) return [];
    const scenario = currentScenario.value;
    return baseColumns.map(column => ({
      ...column,
      title: scenario.renderHeader(column.colKey),
      ...scenario.resolveColumnConfig(column.colKey),
    }));
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
    tableScenarioClassName,
    tableRowKey,
    transformColumns,
  };
};
