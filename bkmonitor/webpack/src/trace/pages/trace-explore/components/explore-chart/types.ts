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
export interface DataPoint {
  [index: number]: number;
}

export interface DataZoomBatchItem {
  batch: Array<DataZoomBatchItem> | null;
  dataZoomId: string;
  endValue: number;
  from: string;
  startValue: number;
  type: string; // "datazoom"
}

export interface DataZoomEvent {
  batch: Array<DataZoomBatchItem>;
  type: string; // "datazoom"
}

export type DecimalCount = null | number | undefined;
export interface EchartSeriesItem {
  data: number[];
  name: string;
  raw_data: SeriesItem;
  stack?: string;
  type?: string;
  unit?: string;
  xAxisIndex?: number;
  yAxisIndex?: number;
}
export interface FormattedValue {
  prefix?: string;
  suffix?: string;
  text: string;
}
export type FormatterFunc = ((v: string) => string) | string;
export interface ILegendItem {
  alias?: string;
  avg?: number | string;
  avgSource?: number;
  borderColor?: string;
  color: string;
  hidden?: boolean;
  max?: number | string;
  maxSource?: number;
  metricField?: string;
  min?: number | string;
  minSource?: number;
  name: string;
  show: boolean;
  total?: number | string;
  totalSource?: number;
  value?: number | string;
}
export interface ILegendItem {
  alias?: string;
  avg?: number | string;
  avgSource?: number;
  borderColor?: string;
  color: string;
  hidden?: boolean;
  max?: number | string;
  maxSource?: number;
  metricField?: string;
  min?: number | string;
  minSource?: number;
  name: string;
  show: boolean;
  total?: number | string;
  totalSource?: number;
  value?: number | string;
}
export type LegendActionType = 'click' | 'downplay' | 'highlight' | 'shift-click';

export type Series = SeriesItem[];

export interface SeriesItem {
  alias?: string;
  datapoints: Array<number>; // 数组包含多个数据点，每个数据点是一个含有两个数值的元组
  dimensions?: Record<string, any>; // 也可以用更具体的类型替代 `any`，根据实际数据结构
  dimensions_translation?: Record<string, any>; // 同样可以用更具体的类型替代 `any`
  metric_field?: string;
  stack?: string;
  target?: string;
  type?: string;
  unit?: string;
}

export type TableLegendHeadType = 'Avg' | 'Max' | 'Min';

export type ValueFormatter = (
  value: number,
  decimals?: DecimalCount,
  scaledDecimals?: DecimalCount,
  timeZone?
) => FormattedValue;
