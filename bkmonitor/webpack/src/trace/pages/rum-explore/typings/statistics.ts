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

import type { IStatisticsInfo, ITopKField } from '../../trace-explore/typing';

/** 统计信息与 TopK 的结构与 trace 检索完全一致，直接复用以便共享 StatisticsList */
export type { IStatisticsInfo, ITopKField };

export interface IRumStatisticsGraph {
  series: IRumStatisticsSeries[];
}

/** field_statistics_graph 的 field 入参：字符类传 topk 值，数值类传 [min, max, distinctCount, intervalNum] */
export interface IRumStatisticsGraphField {
  field_name: string;
  field_type: 'keyword' | 'numeric';
  values?: Array<number | string>;
}

/** field_statistics_graph 返回的单条序列 */
export interface IRumStatisticsSeries {
  alias: string;
  /** 数据点，每项为 [值, 毫秒时间戳] */
  datapoints: Array<[number | string, number]>;
  dimensions: Record<string, string>;
  dimensions_translation?: Record<string, string>;
  metric_field: string;
  stat?: Record<string, unknown>;
  target: string;
  type: string;
  unit?: string;
}
