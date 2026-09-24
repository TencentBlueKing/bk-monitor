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

import type { ProfileQuery, ProfileViewState, QueryState, SelectionRange } from '../types';
import type { IWhereItem } from '@/components/retrieval-filter/typing';

/** 页面时间统一为毫秒，查询 API 使用微秒；外层为全局范围，标签内 start/end 为两侧选区。 */
export function buildProfileQuery(state: QueryState, bizId: number, range: SelectionRange): ProfileQuery {
  const filterLabels = toFilterLabels([...state.where, ...state.commonWhere]);
  const diffLabels =
    state.mode === 'none' ? {} : toFilterLabels([...state.comparisonWhere, ...state.comparisonCommonWhere]);
  const withRange = (labels: ProfileQuery['filter_labels'], selected: null | SelectionRange) =>
    selected ? { ...labels, start: selected[0] * 1000, end: selected[1] * 1000 } : labels;
  return {
    bk_biz_id: bizId,
    app_name: state.appName,
    service_name: state.serviceName,
    data_type: state.dataType,
    agg_method: state.aggregation,
    start: range[0] * 1000,
    end: range[1] * 1000,
    filter_labels: withRange(filterLabels, state.mode === 'time' ? state.baselineRange : null),
    diff_filter_labels: withRange(diffLabels, state.mode === 'time' ? state.comparisonRange : null),
    is_compared: state.mode !== 'none',
  };
}

export function clampSelection(range: SelectionRange, bounds: SelectionRange): null | SelectionRange {
  const start = Math.max(bounds[0], Math.min(...range));
  const end = Math.min(bounds[1], Math.max(...range));
  return Number.isFinite(start) && Number.isFinite(end) && end > start ? [start, end] : null;
}

export function createQueryState(timezone: string): QueryState {
  return {
    appName: '',
    serviceName: '',
    dataType: '',
    aggregation: 'SUM',
    mode: 'none',
    timeRange: ['now-15m', 'now'],
    timezone,
    refreshInterval: -1,
    where: [],
    commonWhere: [],
    comparisonWhere: [],
    comparisonCommonWhere: [],
    baselineRange: null,
    comparisonRange: null,
    resolvedTimeRange: null,
    view: createViewState(),
  };
}

export function createViewState(): ProfileViewState {
  return {
    tab: 'application',
    graphMode: 'combined',
    traceMode: false,
    trendCollapsed: false,
    legend: {},
    keyword: '',
    highlight: '',
    direction: 'ltr',
    sort: { sortBy: 'total', descending: true },
    flameFocus: [],
    callGraph: { scale: 1, x: 0, y: 0 },
  };
}

/** 趋势始终覆盖全局时间；指定 side 时拆成单侧查询，不能携带火焰图的框选范围。 */
export function getTrendQuery(query: ProfileQuery, side?: 'baseline' | 'comparison'): ProfileQuery {
  const clean = (labels: ProfileQuery['filter_labels']) =>
    Object.fromEntries(Object.entries(labels).filter(([key]) => key !== 'start' && key !== 'end'));
  return {
    ...query,
    filter_labels: clean(side === 'comparison' ? query.diff_filter_labels : query.filter_labels),
    diff_filter_labels: side ? {} : clean(query.diff_filter_labels),
    is_compared: side ? false : query.is_compared,
    diagram_types: ['tendency'],
  };
}

/** URL 与收藏共用恢复入口，只接收已知字段；条件能否转换为 API 参数由 toFilterLabels 校验。 */
export function restoreQueryState(value: unknown, timezone: string): QueryState {
  const defaults = createQueryState(timezone);
  if (!value || typeof value !== 'object') return defaults;
  const input = value as Partial<QueryState>;
  const view = restoreViewState(input.view);
  if (['time', 'condition'].includes(input.mode) && view.graphMode === 'callgraph') view.graphMode = 'combined';
  const range = (v: unknown): v is SelectionRange =>
    Array.isArray(v) && v.length === 2 && v.every(n => typeof n === 'number' && Number.isFinite(n)) && v[1] > v[0];
  const where = (v: unknown): IWhereItem[] =>
    Array.isArray(v)
      ? v.filter(
          item =>
            item &&
            typeof item.key === 'string' &&
            Array.isArray(item.value) &&
            item.value.every((n: unknown) => typeof n === 'number' || typeof n === 'string')
        )
      : [];
  return {
    ...defaults,
    appName: typeof input.appName === 'string' ? input.appName : '',
    serviceName: typeof input.serviceName === 'string' ? input.serviceName : '',
    dataType: typeof input.dataType === 'string' ? input.dataType : '',
    aggregation: ['AVG', 'SUM', 'LAST'].includes(input.aggregation) ? input.aggregation : defaults.aggregation,
    mode: ['none', 'condition', 'time'].includes(input.mode) ? input.mode : 'none',
    timeRange:
      Array.isArray(input.timeRange) &&
      input.timeRange.length === 2 &&
      input.timeRange.every(v => typeof v === 'number' || typeof v === 'string')
        ? input.timeRange
        : defaults.timeRange,
    timezone: typeof input.timezone === 'string' ? input.timezone : timezone,
    refreshInterval:
      typeof input.refreshInterval === 'number' && input.refreshInterval >= 60000 ? input.refreshInterval : -1,
    where: where(input.where),
    commonWhere: where(input.commonWhere),
    comparisonWhere: where(input.comparisonWhere),
    comparisonCommonWhere: where(input.comparisonCommonWhere),
    baselineRange: range(input.baselineRange) ? input.baselineRange : null,
    comparisonRange: range(input.comparisonRange) ? input.comparisonRange : null,
    resolvedTimeRange: range(input.resolvedTimeRange) ? input.resolvedTimeRange : null,
    view,
  };
}

/** 相对时间刷新/收藏恢复时，选区随全局范围平移；绝对时间链接保持原位置。 */
export function restoreSelection(state: QueryState, selected: null | SelectionRange, bounds: SelectionRange) {
  if (!selected) return null;
  const relative = state.timeRange.some(value => typeof value === 'string' && value.startsWith('now'));
  const offset = relative && state.resolvedTimeRange ? bounds[0] - state.resolvedTimeRange[0] : 0;
  return clampSelection([selected[0] + offset, selected[1] + offset], bounds);
}

/** 同一标签的多个等值作为 OR，不同标签作为 AND；拒绝无法无损转换的条件。 */
export function toFilterLabels(where: IWhereItem[]): ProfileQuery['filter_labels'] {
  const values = new Map<string, string[]>();
  for (const item of where) {
    if (
      (item.condition && item.condition.toLowerCase() !== 'and') ||
      (item.method && !['eq', 'equal'].includes(item.method)) ||
      item.options?.is_wildcard ||
      (item.options?.group_relation && item.options.group_relation.toUpperCase() !== 'OR')
    ) {
      throw new Error('Profiling 检索仅支持标签等值过滤');
    }
    if (
      !item.key ||
      !item.value.length ||
      ['start', 'end', '__proto__', 'constructor', 'prototype'].includes(item.key)
    ) {
      throw new Error('检索条件不完整或包含保留字段');
    }
    const next = [...new Set(item.value.map(String))];
    // 分开的同名标签为 AND，不能静默合并为 OR。
    const previous = values.get(item.key);
    const merged = previous ? previous.filter(value => next.includes(value)) : next;
    if (!merged.length) throw new Error('同一标签的检索条件存在冲突');
    values.set(item.key, merged);
  }
  return Object.fromEntries([...values].map(([key, value]) => [key, value.length === 1 ? value[0] : value]));
}

function restoreViewState(value: Partial<ProfileViewState> = {}): ProfileViewState {
  const defaults = createViewState();
  const input = value || {};
  const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);
  return {
    tab: ['application', 'collection', 'file'].includes(input.tab) ? input.tab : defaults.tab,
    graphMode: ['table', 'combined', 'flame', 'callgraph'].includes(input.graphMode)
      ? input.graphMode
      : defaults.graphMode,
    traceMode: input.traceMode === true,
    trendCollapsed: input.trendCollapsed === true,
    legend:
      input.legend && typeof input.legend === 'object'
        ? Object.fromEntries(Object.entries(input.legend).filter(([, value]) => typeof value === 'boolean'))
        : {},
    keyword: typeof input.keyword === 'string' ? input.keyword : '',
    highlight: typeof input.highlight === 'string' ? input.highlight : '',
    direction: input.direction === 'rtl' ? 'rtl' : 'ltr',
    sort:
      input.sort && ['name', 'self', 'total', 'baseline', 'comparison', 'diff'].includes(input.sort.sortBy)
        ? { sortBy: input.sort.sortBy, descending: input.sort.descending === true }
        : defaults.sort,
    flameFocus:
      Array.isArray(input.flameFocus) && input.flameFocus.every(name => typeof name === 'string')
        ? input.flameFocus
        : [],
    callGraph: {
      scale: finite(input.callGraph?.scale) ? Math.min(8, Math.max(0.2, input.callGraph.scale)) : 1,
      x: finite(input.callGraph?.x) ? input.callGraph.x : 0,
      y: finite(input.callGraph?.y) ? input.callGraph.y : 0,
    },
  };
}
