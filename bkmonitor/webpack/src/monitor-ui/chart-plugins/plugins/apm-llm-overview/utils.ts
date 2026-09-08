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
import deepmerge from 'deepmerge';
import { deepClone } from 'monitor-common/utils/utils';

import { MONITOR_LINE_OPTIONS, MONITOR_PIE_OPTIONS } from '../../constants';
import { getValueFormat } from '../../../monitor-echarts/valueFormats';

import type { MonitorEchartOptions } from '../../typings';

export type CalType =
  | 'cache_tokens'
  | 'duration'
  | 'input_tokens'
  | 'model_call_count'
  | 'operation_count'
  | 'output_tokens'
  | 'request_count'
  | 'total_tokens';

export type TrendTheme = 'brand' | 'success' | 'warn';

export const GROUP_BY_MODEL = ['gen_ai.response.model'];
export const GROUP_BY_OPERATION = ['gen_ai.operation.name'];
export const RANK_TOP = 10;
export const PIE_COLORS = ['#3370eb', '#56ccbc', '#fac20a', '#ff7763', '#fb99ed'];

export const OPERATION_NAME_MAP: Record<string, string> = {
  chat: '对话补全',
  generate_content: '多模态内容生成',
  text_completion: '文本补全',
  embeddings: '向量化',
  retrieval: '检索',
  fetch_response: '获取已生成响应',
  create_agent: '创建 Agent',
  invoke_agent: '调用 Agent',
  execute_tool: '执行工具',
  invoke_workflow: '调用工作流',
  plan: '规划',
  search_memory: '检索记忆',
  create_memory: '创建记忆',
  update_memory: '更新记忆',
  upsert_memory: '新增或更新记忆',
  delete_memory: '删除记忆',
  create_memory_store: '创建记忆库',
  delete_memory_store: '删除记忆库',
};

export interface ICalculateItem {
  '0s'?: number;
  dimensions?: Record<string, string>;
  growth_rates?: Record<string, null | number>;
  [key: string]: number | Record<string, null | number> | Record<string, string> | undefined;
}

export interface ICalculateResult {
  data?: ICalculateItem[];
  total?: number;
}

export interface IMetricCardConfig {
  calType: CalType;
  format: 'compact' | 'count';
  title: string;
  trendTheme: TrendTheme;
}

export interface IMetricCard {
  title: string;
  trend: string;
  trendTheme: TrendTheme;
  value: string;
}

export interface IPieLegendItem {
  color: string;
  name: string;
  rawValue: number;
  value: string;
}

export interface IRankItem {
  displayValue: string;
  name: string;
  value: number;
}

export interface ITimeSeriesItem {
  datapoints?: [number, number][];
  dimensions?: Record<string, string>;
  target?: string;
}

export interface ITimeSeriesResult {
  mock?: boolean;
  series?: ITimeSeriesItem[];
}

export const METRIC_CARD_CONFIG: IMetricCardConfig[] = [
  { calType: 'input_tokens', title: '输入 Tokens 总数', trendTheme: 'brand', format: 'compact' },
  { calType: 'output_tokens', title: '输出 Tokens 总数', trendTheme: 'brand', format: 'compact' },
  { calType: 'total_tokens', title: 'Tokens 总数', trendTheme: 'success', format: 'compact' },
  { calType: 'cache_tokens', title: '缓存 Tokens 总数', trendTheme: 'success', format: 'compact' },
  { calType: 'request_count', title: '请求数（提问数）', trendTheme: 'brand', format: 'count' },
  { calType: 'model_call_count', title: '模型调用次数', trendTheme: 'warn', format: 'count' },
];

export function unwrapCalculateList(res: ICalculateItem[] | ICalculateResult | null | undefined): ICalculateItem[] {
  if (Array.isArray(res)) return res;
  if (Array.isArray(res?.data)) return res.data;
  return [];
}

export function unwrapSeriesList(res: ITimeSeriesItem[] | ITimeSeriesResult | null | undefined): ITimeSeriesItem[] {
  if (Array.isArray(res)) return res;
  if (Array.isArray(res?.series)) return res.series;
  return [];
}

export function getDimensionName(item: ICalculateItem, key: string) {
  return item.dimensions?.[key] || '--';
}

export function getOperationDisplayName(name: string) {
  return OPERATION_NAME_MAP[name] || name;
}

export function formatCount(value: number) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '--';
  return Math.round(value).toLocaleString('en-US');
}

export function formatCompactNumber(value: number) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '--';
  const abs = Math.abs(value);
  if (abs >= 1e9) return `${trimFixed(value / 1e9)}B`;
  if (abs >= 1e6) return `${trimFixed(value / 1e6)}M`;
  if (abs >= 1e3) return `${trimFixed(value / 1e3)}K`;
  return formatCount(value);
}

export function formatDuration(value: number) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '--';
  const formatted = getValueFormat('µs')(value, 2);
  return `${formatted.text}${formatted.suffix || ''}`;
}

export function formatGrowthRate(rate: null | number | undefined) {
  if (typeof rate !== 'number' || Number.isNaN(rate)) return '--';
  if (rate === 0) return '0%';
  const sign = rate > 0 ? '+ ' : '- ';
  return `${sign}${Math.abs(rate)}%`;
}

export function formatMetricValue(value: number, format: IMetricCardConfig['format']) {
  return format === 'compact' ? formatCompactNumber(value) : formatCount(value);
}

export function sortByCurrentValue(list: ICalculateItem[], limit = RANK_TOP) {
  return [...list]
    .sort((a, b) => (Number(b['0s']) || 0) - (Number(a['0s']) || 0))
    .slice(0, limit)
    .filter(item => typeof item['0s'] === 'number');
}

export function toEchartsPoints(datapoints: [number, number][] = []): [number, number][] {
  return datapoints.map(([value, timestamp]) => [timestamp, value]);
}

export function buildTimeLineOptions(
  series: { color: string; data: [number, number][]; name: string }[]
): MonitorEchartOptions {
  const chartBaseOptions = deepClone(MONITOR_LINE_OPTIONS);
  return deepmerge(chartBaseOptions, {
    animation: false,
    toolbox: { show: false },
    legend: {
      show: true,
      bottom: 0,
      left: 0,
      icon: 'rect',
      itemWidth: 8,
      itemHeight: 2,
      itemGap: 24,
      padding: 0,
      textStyle: {
        color: '#4d4f56',
        fontSize: 12,
        lineHeight: 20,
      },
    },
    grid: {
      containLabel: true,
      left: 4,
      right: 16,
      top: 16,
      bottom: 32,
    },
    xAxis: {
      type: 'time',
      axisTick: { show: false },
      axisLine: { show: false },
      axisLabel: {
        fontSize: 12,
        color: '#979ba5',
        showMinLabel: true,
        showMaxLabel: true,
      },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      min: 0,
      axisTick: { show: false },
      axisLine: { show: false },
      axisLabel: {
        color: '#979ba5',
        fontSize: 12,
      },
      splitLine: {
        show: true,
        lineStyle: {
          color: '#f0f1f5',
          type: 'solid',
        },
      },
    },
    series: series.map(item => ({
      name: item.name,
      type: 'line',
      data: item.data,
      smooth: true,
      showSymbol: false,
      symbol: 'none',
      lineStyle: {
        width: 2,
        color: item.color,
      },
      itemStyle: {
        color: item.color,
      },
    })),
  }) as MonitorEchartOptions;
}

export function buildPieOptions(list: IPieLegendItem[]): MonitorEchartOptions {
  const chartBaseOptions = deepClone(MONITOR_PIE_OPTIONS);
  return deepmerge(chartBaseOptions, {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c}',
    },
    series: [
      {
        type: 'pie',
        radius: ['68%', '88%'],
        center: ['50%', '50%'],
        silent: false,
        label: { show: false },
        labelLine: { show: false },
        data: list.map(item => ({
          name: item.name,
          value: item.rawValue,
          itemStyle: { color: item.color },
        })),
      },
    ],
  }) as MonitorEchartOptions;
}

function trimFixed(value: number) {
  return value.toFixed(1).replace(/\.0$/, '');
}
