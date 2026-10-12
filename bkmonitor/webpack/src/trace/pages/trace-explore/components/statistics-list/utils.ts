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
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

import { formatPercent } from 'monitor-common/utils';

import { formatDuration } from '../../../../components/trace-view/utils/date';
import { formatUnitValue as formatBytesUnitValue } from '../../../rum-explore/utils';
import { transformFieldName } from '../trace-explore-table/constants';

import type { IStatisticsInfo, ITopKField } from '../../typing';

/** 耗时字段 topk 数据，min/max 为格式化后的取值范围文本 */
export type IDurationTopKField = ITopKField & { max: string; min: string };

/** 统计展示模式：耗时字段 / 数值字段 / 文本字段 */
export type StatisticsMode = 'duration' | 'integer' | 'text';

export const EMPTY_STATISTICS_INFO: IStatisticsInfo = {
  field: '',
  total_count: 0,
  field_count: 0,
  distinct_count: 0,
  field_percent: 0,
};

export const EMPTY_TOPK_FIELD: ITopKField = {
  distinct_count: 0,
  field: '',
  list: [],
};

export const EMPTY_DURATION_TOPK_FIELD: IDurationTopKField = {
  distinct_count: 0,
  field: '',
  max: '',
  min: '',
  list: [],
};

/** 数值/耗时模式下进度条与图表系列的统一颜色 */
export const UNIFORM_SERIES_COLOR = '#5AB8A8';

/** 各模式的图表标题（i18n key）与图表类型 */
export const MODE_CHART_CONFIG: Record<StatisticsMode, { seriesType: 'histogram' | 'line'; titleKey: string }> = {
  duration: { seriesType: 'histogram', titleKey: '耗时区间' },
  integer: { seriesType: 'histogram', titleKey: '数值分布直方图' },
  text: { seriesType: 'line', titleKey: 'TOP 5 时序图' },
};

/** 耗时字段 topk 列表逻辑特殊：由 graph 接口返回的直方图数据在前端生成 */
export function buildDurationTopK(datapoints: [number, string][], field: string): IDurationTopKField {
  const total = datapoints.reduce((pre, cur) => pre + cur[0], 0);
  let min = '';
  let max = '';
  const list = datapoints.map((item, index) => {
    const [start, end] = item[1].split('-');
    if (index === 0) min = start;
    if (index === datapoints.length - 1) max = end;
    return {
      alias: item[1],
      count: item[0],
      proportions: formatPercent((item[0] / total) * 100, 3, 3, 3),
      value: item[1],
    };
  });
  return {
    distinct_count: list.length,
    field,
    list: list.sort((a, b) => b.count - a.count),
    min,
    max,
  };
}

/** 按字段单位格式化数值（bytes / us / μs / ms），其他单位返回原值 */
export function formatUnitValue(value: number | string, unit: string) {
  switch (unit) {
    case 'bytes':
      return formatBytesUnitValue(Number(value), unit);
    case 'us':
    case 'μs':
    case 'ms':
      return formatDuration(Number(value) || 0, '', 3, unit).replace(/ /g, '');
    default:
      return value;
  }
}

/** 数值直方图 x 轴刻度格式化："1000-2000" → "1ms-2ms"（具体单位由 formatter 决定） */
export function parseRangeText(value: number | string, formatter: (value: number | string) => string) {
  if (typeof value !== 'string') return formatter(value) || value;
  const matched = value.match(/^(-?\d+)-(-?\d+)$/);
  if (!matched) return formatter(value) || value;
  return `${formatter(matched[1]) || matched[1]}-${formatter(matched[2]) || matched[2]}`;
}

/** 模式判定：isDuration 优先于 isInteger（耗时字段的 isInteger 也为 true） */
export function resolveStatisticsMode(isDuration: boolean, isInteger: boolean): StatisticsMode {
  if (isDuration) return 'duration';
  return isInteger ? 'integer' : 'text';
}

/** 计算展示别名：优先选项值别名，其次字段名转换，最后按单位格式化 */
export function resolveTopKAlias(
  value: string,
  options: {
    fieldName: string;
    optionValues?: { alias?: string; value: string }[];
    unit: string;
  }
) {
  const { fieldName, optionValues, unit } = options;
  const alias =
    optionValues?.find(option => option.value === value)?.alias ||
    transformFieldName(fieldName, value) ||
    formatUnitValue(value, unit);
  return alias === value ? '' : alias;
}

/** 将 topk 数据写入目标容器；不传 data 时清空 */
export function setTopKData(target: ITopKField, data?: Partial<ITopKField>) {
  target.distinct_count = data?.distinct_count || 0;
  target.field = data?.field || '';
  target.list = data?.list || [];
}
