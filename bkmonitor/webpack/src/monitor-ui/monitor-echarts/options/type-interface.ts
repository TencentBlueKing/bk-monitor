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
import type { MonitorEchartOptions } from '../types/monitor-echarts';

export type ChartType = 'bar' | 'line' | 'map' | 'pie' | 'scatter' | 'status' | 'table' | 'text';
export interface IAnnotation {
  color: string;
  list?: IAnnotationListItem[];
  name: string;
  show: boolean;
  title: string;
  x: number;
  y: number;
}
export interface IAnnotationListItem {
  id: string;
  show: boolean;
  value: any;
}

export interface IChartInstance {
  getOptions: (
    data: any,
    otherOptions?: MonitorEchartOptions
  ) => { legendData: ILegendItem[]; options: MonitorEchartOptions };
}

export type IChartOption = IStatusChartOption | ITextChartOption | MonitorEchartOptions;

export interface IChartOptionPorps {
  chartOption: MonitorEchartOptions;
  chartType: ChartType;
  colors: string[];
  lineWidth: number;
  showExtremum: boolean;
}
export interface ILegendItem {
  avg: number;
  color: string;
  hidden?: boolean;
  max: number;
  min: number | string;
  name: string;
  show: boolean;
  total: number;
}
export interface IMoreToolItem {
  checked: boolean;
  id: string;
  name: string;
  nextName?: string;
}
export interface IStatusChartOption {
  series: IStatusSeries[];
}

export interface IStatusSeries {
  status: number | string;
  value: number | string;
}

export interface ITableSeries {
  columns?: { text: string; type: string }[];
  rows?: unknown[][];
}
export interface ITextChartOption {
  series: ITextSeries;
}

export interface ITextSeries {
  unit?: string;
  value?: number | string;
}

export type MoreChartToolItem = 'area' | 'explore' | 'set' | 'strategy';
