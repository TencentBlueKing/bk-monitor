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

import { cloneDeep } from 'lodash';
import { getTemplateSrv } from 'monitor-pc/pages/query-template/variables/template/template-srv';
import { PanelModel } from 'monitor-ui/chart-plugins/typings';

import type { CompareTarget, MetricAggregationState } from '../../../types/aggregation';
import type { HostViewsGraphPanel } from '../../../types/panels';

/** 变量名 → 取值的扁平映射（值可为字符串、数字或数组） */
export type ScopedVarMap = Record<string, unknown>;

/** 仅匹配「整串就是单个变量」的情况，如 `$method` / `${method}` */
const PURE_VARIABLE_REG = /^\$\{?(\w+)\}?$/;

const isEmpty = (val: unknown) => val === '' || val === null || val === undefined;

/**
 * 把 toolbar 汇聚状态映射为变量取值。
 * 注：当前 toolbar 无「汇聚维度」字段，$group_by 默认空（占位会被移除）。
 * 对比相关变量仅在对应对比模式下生效，否则置空。
 */
export function buildScopedVars(state: MetricAggregationState, currentTarget?: CompareTarget | null): ScopedVarMap {
  return {
    interval: state.interval,
    method: state.method,
    group_by: [],
    time_shift: state.compareType === 'time' ? state.timeShift : [],
    current_target: currentTarget,
    compare_targets: state.compareType === 'target' ? state.compareTargets : [],
  };
}

/** 转换为 template-srv 需要的 scopedVars 结构（用于字符串内嵌变量插值） */
const toSrvScopedVars = (scopedVars: ScopedVarMap) =>
  Object.fromEntries(Object.entries(scopedVars).map(([name, value]) => [name, { value }]));

/**
 * 把一份带变量占位符的图表面板 JSON 解析为可直接取数渲染的 PanelModel。
 * @param panel 原始面板 JSON（含 $变量）
 * @param scopedVars 变量取值映射
 * @param dashboardId echarts 联动分组 id（同组图表共享 tooltip/缩放）
 */
export function resolveGraphPanel(
  panel: HostViewsGraphPanel,
  scopedVars: ScopedVarMap,
  dashboardId?: string
): PanelModel {
  const srvScopedVars = toSrvScopedVars(scopedVars);
  const targets = resolveValue(cloneDeep(panel.targets), scopedVars, srvScopedVars);
  return new PanelModel({
    id: panel.id,
    type: 'graph',
    title: panel.title,
    subTitle: panel.subTitle,
    targets,
    dashboardId,
  });
}

/**
 * 深度解析任意值中的变量占位符：
 * - 整串即单个变量：直接整体替换为变量值（支持数组/数字，不退化为字符串）；
 * - 数组：逐项解析后扁平化并去除空值（实现 $group_by/$compare_targets 的展开与裁剪）；
 * - 字符串内嵌变量：交给 template-srv 做插值。
 */
function resolveValue(
  value: unknown,
  scopedVars: ScopedVarMap,
  srvScopedVars: Record<string, { value: unknown }>
): any {
  if (Array.isArray(value)) {
    const result: unknown[] = [];
    for (const item of value) {
      const resolved = resolveValue(item, scopedVars, srvScopedVars);
      if (Array.isArray(resolved)) {
        result.push(...resolved.filter(v => !isEmpty(v)));
      } else if (!isEmpty(resolved)) {
        result.push(resolved);
      }
    }
    return result;
  }
  if (value && typeof value === 'object') {
    const result: Record<string, unknown> = {};
    for (const [key, val] of Object.entries(value)) {
      result[key] = resolveValue(val, scopedVars, srvScopedVars);
    }
    return result;
  }
  if (typeof value === 'string') {
    const pure = value.match(PURE_VARIABLE_REG);
    if (pure && Object.hasOwn(scopedVars, pure[1])) {
      return scopedVars[pure[1]];
    }
    return getTemplateSrv().replace(value, srvScopedVars);
  }
  return value;
}
