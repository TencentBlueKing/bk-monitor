/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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

import { EChartOption } from 'echarts';

// 时序性图表类型 bar: 柱状图 line: 线性图
export type TimeSeriesType = 'bar' | 'line';

export interface ITimeSeriesItem extends EChartOption.SeriesLine {
  // 时序型图表数据 [x, y][]  x: 时间戳 y: 数值
  data: [number, number][];
  // 图例名称
  name: string;
  // 单位
  unit: string;
  // 图表显示类型 bar | line
  type: TimeSeriesType;
  // 数据堆叠，同个类目轴上系列配置相同的stack值可以堆叠放置。
  stack?: string;
  color?: string;
  metricField?: string; // 指标
  traceData?: Record<number, IProfilingTraceInfo[]>;
}

export interface IProfilingTraceInfo {
  time: string;
  span_id: string;
}

export interface ITimeSeriesData {
  // 指标数据
  metrics?: [];
  // 图表数据
  series: ITimeSeriesItem[];
}
