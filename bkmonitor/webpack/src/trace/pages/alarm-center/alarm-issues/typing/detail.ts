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

import type { IssuePriorityType, IssueStatusType, TrendStatusType } from './constants';
import type { AggregateConfig, ImpactScope } from './table';

/* ============== Issue 详情接口 - 返回数据 ============== */

/** 维度统计项 */
export interface DimensionSummaryItem {
  /** 维度字段名，对应 alert.dimensions 中的 key */
  dimension_key: string;
  /** 维度显示名称（中文），来源于告警 dimensions 的 display_key */
  dimension_name: string;
  /** 维度值分布列表（Top5 + 其他） */
  items: DimensionSummaryValue[];
  /** 该维度在所有告警中出现的总次数 */
  total_count: number;
}

/** 维度统计值项 */
export interface DimensionSummaryValue {
  /** 该值出现次数 */
  count: number;
  /** 占比百分比（保留2位小数） */
  percentage: number;
  /** 维度值，聚合剩余项时值为翻译后的 "其他" */
  value: string;
}

/** Issue 详情数据 */
export interface IssueDetail extends Record<string, unknown> {
  /** 聚合配置 */
  aggregate_config: AggregateConfig;
  /** 关联告警总数 */
  alert_count: number;
  /** 全部关联告警的 ID 列表 */
  alert_ids: string[];
  /** 异常信息描述 */
  anomaly_message: string;
  /** 负责人用户名列表，空数组表示未指派 */
  assignee: string[];
  /** 所属业务 ID */
  bk_biz_id: number;
  /** 业务名称 */
  bk_biz_name: string;
  /** 创建时间（秒级时间戳） */
  create_time: number;
  /** 维度统计 */
  dimension_summary: DimensionSummaryItem[];
  /** 存活时长（人类可读格式，如 "1d 1h"） */
  duration: string;
  /** 最早告警 ID，用于点击跳转到最早告警详情 */
  earliest_alert_id: string;
  /** 首条关联告警时间（秒级时间戳） */
  first_alert_time: number;
  /** Issue 唯一标识 */
  id: string;
  /** 影响范围 */
  impact_scope: ImpactScope | Record<string, never>;
  /** 是否为回归 Issue */
  is_regression: boolean;
  /** 是否已解决 */
  is_resolved: boolean;
  /** 标签列表 */
  labels: string[];
  /** 最近关联告警时间（秒级时间戳） */
  last_alert_time: number;
  /** 最新告警 ID，用于点击跳转到最新告警详情 */
  latest_alert_id: string;
  /** Issue 名称（策略名称） */
  name: string;
  /** 优先级 */
  priority: IssuePriorityType;
  /** 优先级中文名 */
  priority_display: string;
  /** 解决时间，仅 resolved 状态有值 */
  resolved_time: null | number;
  /** 状态 */
  status: IssueStatusType;
  /** 状态中文名 */
  status_display: string;
  /** 关联策略 ID */
  strategy_id: string;
  /** 策略名称 */
  strategy_name: string;
  /** 趋势统计（按状态分组） */
  trend: IssueTrendItem[];
  /** 最近更新时间（秒级时间戳） */
  update_time: number;
}

/** Issue 详情查询请求参数 */
export interface IssueDetailParams {
  /** 业务 ID（用于权限校验） */
  bk_biz_id: number;
  /** 趋势图结束时间（秒级时间戳），默认 last_alert_time 或当前时间 */
  end_time?: number;
  /** Issue ID */
  id: string;
  /** 趋势图开始时间（秒级时间戳），默认 first_alert_time */
  start_time?: number;
}

/* ============== Issue 详情接口 - 请求参数 ============== */

/** 趋势统计项 */
export interface IssueTrendItem {
  /** 时间序列数据，格式为 [[毫秒时间戳, 数量], ...] */
  data: [number, number][];
  /** 状态中文名：未恢复 / 已恢复 / 已失效 */
  display_name: string;
  /** 状态枚举值：ABNORMAL / RECOVERED / CLOSED */
  name: TrendStatusType;
}
