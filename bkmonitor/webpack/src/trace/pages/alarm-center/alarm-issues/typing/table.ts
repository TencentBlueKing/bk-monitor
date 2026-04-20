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

import type { ImpactScopeResourceKeyType, IssuePriorityType, IssueStatusType } from './constants';

/** 聚合配置 */
export interface AggregateConfig {
  /** 聚合维度 */
  aggregate_dimensions: { display_name: string; field: string }[];
  /** 告警级别 */
  alert_levels: number[];
  /** 条件 */
  conditions: unknown[];
}

/** 影响范围（动态资源类型字典） */
export type ImpactScope = Partial<Record<ImpactScopeResourceKeyType, ImpactScopeResource>>;

/** 影响范围点击事件对象（用于打开 / 关闭侧滑面板） */
export interface ImpactScopeEvent {
  /** 资源类型完整数据，null 表示关闭 / 清空 */
  resource: ImpactScopeResource | null;
  /** 资源类型 key（如 host、cluster 等），空字符串表示关闭 / 清空 */
  resourceKey: '' | ImpactScopeResourceKeyType;
}

/** 影响范围资源实例（instance_list 中的单条记录） */
export interface ImpactScopeInstance {
  /** 其余字段为动态标识字段（如 bk_host_id、bcs_cluster_id 等），用于 link_tpl 模板渲染 */
  [key: string]: number | string;
  /** 展示名称 */
  display_name: string;
}

/** 影响范围单一资源类型 */
export interface ImpactScopeResource {
  /** 该资源类型的总数量 */
  count: number;
  /** 资源类型展示名称（如"集群"、"主机"、"bcs集群"等） */
  display_name: string;
  /** 实例列表，最多 50 条 */
  instance_list: ImpactScopeInstance[];
  /** 跳转链接模板，null 表示不可点击 */
  link_tpl: null | string;
}

/** Issues 数据项 */
export interface IssueItem extends Record<string, unknown> {
  /** 聚合配置 */
  aggregate_config: AggregateConfig;
  /** 关联告警总数 */
  alert_count: number;
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
  /** 存活时长（人类可读格式，如 "1d 1h"） */
  duration: string;
  /** 首条关联告警时间（秒级时间戳） */
  first_alert_time: number;
  /** Issue 唯一标识 */
  id: string;
  /** 影响范围 */
  impact_scope: ImpactScope;
  /** 是否为回归 Issue */
  is_regression: boolean;
  /** 是否已解决 */
  is_resolved: boolean;
  /** 标签列表 */
  labels: string[];
  /** 最近关联告警时间（秒级时间戳） */
  last_alert_time: number;
  /** Issue 名称（回归问题带 [回归] 前缀） */
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
  /** 告警时间分布趋势 [[毫秒时间戳, 数量], ...] */
  trend: [number, number][];
  /** 最近更新时间（秒级时间戳） */
  update_time: number;
}
