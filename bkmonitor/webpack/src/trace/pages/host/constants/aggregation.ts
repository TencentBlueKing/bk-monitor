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
import type { MetricAggregationState, MetricCompareType, SelectOption } from '../types/aggregation';

/** 汇聚周期默认值 */
export const DEFAULT_INTERVAL = 'auto';
/** 汇聚方法默认值 */
export const DEFAULT_METHOD = 'MAX';
/** 对比方法默认值 */
export const DEFAULT_COMPARE_TYPE: MetricCompareType = 'none';

/** 汇聚方法选项，与旧版一致；默认 MAX */
export const METHOD_OPTIONS: SelectOption[] = [
  { id: 'AVG', name: 'AVG' },
  { id: 'SUM', name: 'SUM' },
  { id: 'MIN', name: 'MIN' },
  { id: 'MAX', name: 'MAX' },
];

/** 对比方法选项：不对比 / 目标对比 / 时间对比 */
export const COMPARE_TYPE_OPTIONS: { id: MetricCompareType; name: string }[] = [
  { id: 'none', name: window.i18n.t('不对比') },
  { id: 'target', name: window.i18n.t('目标对比') },
  { id: 'time', name: window.i18n.t('时间对比') },
];

/** 时间对比的时间偏移选项，与旧版一致 */
export const TIME_SHIFT_OPTIONS: SelectOption[] = [
  { id: '1h', name: window.i18n.t('1 小时前') },
  { id: '1d', name: window.i18n.t('昨天') },
  { id: '1w', name: window.i18n.t('上周') },
  { id: '1M', name: window.i18n.t('一月前') },
];

/** 列数可选值 */
export const COLUMN_VALUES = [1, 2, 3] as const;

/** 列数对应的图标类名（icon-monitor 字体） */
export const COLUMN_ICON_MAP: Record<number, string> = {
  1: 'icon-mc-one-column',
  2: 'icon-mc-two-column',
  3: 'icon-mc-three-column',
};

/** Toolbar 默认状态 */
export const DEFAULT_AGGREGATION_STATE: MetricAggregationState = {
  columns: 3,
  compareTargets: [],
  compareType: DEFAULT_COMPARE_TYPE,
  highlightPeak: false,
  interval: DEFAULT_INTERVAL,
  keyword: '',
  method: DEFAULT_METHOD,
  showStatistics: false,
  timeShift: ['1h'],
};
