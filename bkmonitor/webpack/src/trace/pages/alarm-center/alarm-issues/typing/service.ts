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

import type { CommonFilterParams, QuickFilterItem } from '../../typings';
import type { IssueItem } from './table';

/** Issue 搜索请求参数 */
export interface IssueSearchParams extends CommonFilterParams {
  /** 是否展示聚合 */
  show_aggs?: boolean;
  /** 是否展示 DSL */
  show_dsl?: boolean;
  /** 告警趋势图结束时间（跟随 end_time） */
  trend_end_time?: number;
  /** 告警趋势图开始时间（trend_end_time 往前推 24 小时） */
  trend_start_time?: number;
}

/** Issue 搜索响应结果 */
export interface IssueSearchResponse {
  /** 聚合数据 */
  aggs: QuickFilterItem[];
  /** Issue 列表 */
  issues: IssueItem[];
  /** 总数 */
  total: number;
}
