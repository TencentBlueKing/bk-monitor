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

// ===================== 枚举类型 =====================

/** Issues 优先级枚举 */
export enum IssuePriorityEnum {
  /** 紧急 */
  CRITICAL = 'critical',
  /** 高 */
  HIGH = 'high',
  /** 低 */
  LOW = 'low',
  /** 中 */
  MEDIUM = 'medium',
}

/** Issues 状态枚举 */
export enum IssueStatusEnum {
  /** 待审核 */
  PENDING_REVIEW = 'pending_review',
  /** 已解决 */
  RESOLVED = 'resolved',
  /** 待解决 */
  UNRESOLVED = 'unresolved',
}

/** Issues 类型枚举 */
export enum IssueTypeEnum {
  /** 新问题 */
  NEW = 'new',
  /** 回归问题 */
  REGRESSION = 'regression',
}

// ===================== 类型定义 =====================

/** Issues 数据项 */
export interface IssueItem extends Record<string, unknown> {
  /** 告警事件数量 */
  alert_count: number;
  /** 负责人列表 */
  assignee: string[];
  /** 关键报错信息 */
  exception_type: string;
  /** 最早发生时间（时间戳，秒） */
  first_seen: number;
  /** Issue 唯一标识 */
  id: string;
  /** 影响主机数 */
  impact_host_count: number;
  /** 影响服务 */
  impact_service: string;
  /** Issue 名称（默认为告警策略名称） */
  issue_name: string;
  /** Issue 类型 */
  issue_type: IssueType;
  /** 最后出现时间（时间戳，秒） */
  last_seen: number;
  /** 优先级 */
  priority: IssuePriority;
  /** 告警级别 */
  severity: number;
  /** 状态 */
  status: IssueStatus;
  /** 标签列表 */
  tags: string[];
  /** 趋势数据 */
  trend_data: number[];
}

/** Issues 优先级类型 */
export type IssuePriority = `${IssuePriorityEnum}`;

/** Issues 状态类型 */
export type IssueStatus = `${IssueStatusEnum}`;

/** Issues 类型 */
export type IssueType = `${IssueTypeEnum}`;

// ===================== 常量映射 =====================

/** 映射条目通用结构 */
export interface MapEntry {
  /** 显示别名 */
  alias: string;
  /** 颜色值 */
  color: string;
  /** 图标类名 */
  prefixIcon: string;
}

/** Issues 状态映射 */
export const IssuesStatusMap: Record<IssueStatus, MapEntry> = {
  [IssueStatusEnum.PENDING_REVIEW]: {
    alias: window.i18n.t('待审核'),
    prefixIcon: 'icon-monitor icon-mc-wait-fill',
    color: '#3A84FF',
  },
  [IssueStatusEnum.UNRESOLVED]: {
    alias: window.i18n.t('待解决'),
    prefixIcon: 'icon-monitor icon-mind-fill',
    color: '#FF9C01',
  },
  [IssueStatusEnum.RESOLVED]: {
    alias: window.i18n.t('已解决'),
    prefixIcon: 'icon-monitor icon-mc-check-fill',
    color: '#2DCB56',
  },
};

/** Issues 优先级映射 */
export const IssuesPriorityMap: Record<IssuePriority, MapEntry> = {
  [IssuePriorityEnum.CRITICAL]: {
    alias: window.i18n.t('紧急'),
    prefixIcon: 'icon-monitor icon-mc-fault',
    color: '#EA3636',
  },
  [IssuePriorityEnum.HIGH]: {
    alias: window.i18n.t('高'),
    prefixIcon: 'icon-monitor icon-danger',
    color: '#FF9C01',
  },
  [IssuePriorityEnum.MEDIUM]: {
    alias: window.i18n.t('中'),
    prefixIcon: 'icon-monitor icon-mind-fill',
    color: '#FFD695',
  },
  [IssuePriorityEnum.LOW]: {
    alias: window.i18n.t('低'),
    prefixIcon: 'icon-monitor icon-tips',
    color: '#3A84FF',
  },
};

/** Issues 类型映射 */
export const IssuesTypeMap: Record<IssueType, Omit<MapEntry, 'prefixIcon'>> = {
  [IssueTypeEnum.NEW]: {
    alias: window.i18n.t('新问题'),
    color: '#2DCB56',
  },
  [IssueTypeEnum.REGRESSION]: {
    alias: window.i18n.t('回归问题'),
    color: '#FF9C01',
  },
};
