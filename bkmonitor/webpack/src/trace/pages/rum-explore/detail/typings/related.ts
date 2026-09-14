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
/** Action 详情的关联数据，来自 statistics 接口按 span_type 分组的计数 */
export interface IRumActionRelated {
  /** 关联错误数 */
  errorCount: number;
  /** 关联 Long Task 数 */
  longTaskCount: number;
  /** 触发的请求数 */
  resourceCount: number;
}

/** Error 详情的关联数据 */
export interface IRumErrorRelated {
  /** 当前查询范围内的发生次数 */
  occurrenceCount: number;
  /** 影响会话数 */
  sessionCount: number;
  /** 24 小时趋势，每 1h 一桶 */
  trend: IRumErrorTrendPoint[];
  /** 影响用户数 */
  userCount: number;
  /** 影响用户数环比，单位 %，正值表示上涨 */
  userGrowthRate: number;
  /** 版本关联信息，接口暂未提供时为 undefined */
  version?: IRumErrorVersion;
}

/** Error 详情 24 小时趋势的一个时间桶 */
export interface IRumErrorTrendPoint {
  /** 桶起点，秒级时间戳 */
  time: number;
  value: number;
}

/** Error 详情的版本关联信息 */
export interface IRumErrorVersion {
  /** 当前版本 */
  current: string;
  /** 首次出现版本 */
  first: string;
  /** 说明 */
  note: string;
}

/** Long Task 详情的关联数据，来自 list_records 回查的 Action 记录 */
export interface IRumLongTaskRelated {
  /** 关联 Action 的目标元素名，未关联时为空 */
  actionName: string;
  /** 关联 Action 的交互类型 */
  actionType: string;
}

/** 关联数据的联合结构，按 span 类型取用其中一支 */
export type IRumRelatedData = Partial<IRumActionRelated & IRumErrorRelated & IRumLongTaskRelated>;
