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

export interface SeriesItem {
  dimensions?: Record<string, any>; // 也可以用更具体的类型替代 `any`，根据实际数据结构
  target?: string;
  metric_field?: string;
  datapoints: Array<number>; // 数组包含多个数据点，每个数据点是一个含有两个数值的元组
  alias?: string;
  type?: string;
  dimensions_translation?: Record<string, any>; // 同样可以用更具体的类型替代 `any`
  unit?: string;
  stack?: string;
}

export interface EchartSeriesItem {
  data: number[];
  name: string;
  stack?: string;
  type?: string;
  xAxisIndex?: number;
  yAxisIndex?: number;
  unit?: string;
  raw_data: SeriesItem;
}

export type Series = SeriesItem[];

export type FormatterFunc = ((v: string) => string) | string;
