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

import type { IssuePriorityType, IssueStatusType, IssueTypeType, MapEntry } from './typing';

// ===================== 枚举常量 =====================

/** Issues 优先级枚举 */
export const IssuePriorityEnum = {
  /** 高 */
  HIGH: 'high',
  /** 中 */
  MEDIUM: 'medium',
  /** 低 */
  LOW: 'low',
} as const;

/** Issues 状态枚举 */
export const IssueStatusEnum = {
  /** 待审核 */
  PENDING_REVIEW: 'pending_review',
  /** 已解决 */
  RESOLVED: 'resolved',
  /** 未解决 */
  UNRESOLVED: 'unresolved',
} as const;

/** Issues 类型枚举 */
export const IssueTypeEnum = {
  /** 新问题 */
  NEW: 'new',
  /** 回归问题 */
  REGRESSION: 'regression',
} as const;

/** Issues 批量操作枚举 */
export const IssuesBatchActionEnum = {
  /** 指派负责人 */
  ASSIGN: 'assign',
  /** 添加跟进信息 */
  FOLLOW_UP: 'follow_up',
  /** 修改优先级 */
  PRIORITY: 'priority',
  /** 标记为已解决 */
  RESOLVE: 'resolve',
} as const;

/** Issues 活跃节点类型枚举 */
export const IssueActiveNodeTypeEnum = {
  /** 首次出现 */
  FIRST: 'first',
  /** 状态变更 */
  STATUS: 'status',
  /** 用户评论 */
  COMMENT: 'comment',
  /** 指派 */
  DISPATCH: 'dispatch',
  /** 拆分 */
  SPLIT: 'split',
  /** 合并 */
  MERGE: 'merge',
} as const;

// ===================== 常量映射 =====================

/** Issues 状态映射 */
export const IssuesStatusMap: Record<IssueStatusType, MapEntry> = {
  [IssueStatusEnum.PENDING_REVIEW]: {
    alias: window.i18n.t('待审核'),
    icon: 'icon-monitor icon-Waiting',
    color: '#3974FF',
    bgColor: '#F0F4FF',
  },
  [IssueStatusEnum.UNRESOLVED]: {
    alias: window.i18n.t('未解决'),
    icon: 'icon-monitor icon-unfinished',
    color: '#F09305',
    bgColor: '#FFF3E0',
  },
  [IssueStatusEnum.RESOLVED]: {
    alias: window.i18n.t('已解决'),
    icon: 'icon-monitor icon-mc-check-fill',
    color: '#21A380',
    bgColor: '#EDFAF6',
  },
};

/** Issues 优先级映射 */
export const IssuesPriorityMap: Record<IssuePriorityType, MapEntry> = {
  [IssuePriorityEnum.HIGH]: {
    alias: window.i18n.t('button-高'),
    bgColor: '#E54040',
    color: '#FFFFFF',
  },
  [IssuePriorityEnum.MEDIUM]: {
    alias: window.i18n.t('button-中'),
    bgColor: '#FAA41E',
    color: '#FFFFFF',
  },
  [IssuePriorityEnum.LOW]: {
    alias: window.i18n.t('button-低'),
    bgColor: '#8F9FBD',
    color: '#FFFFFF',
  },
};

/** Issues 类型映射 */
export const IssuesTypeMap: Record<IssueTypeType, MapEntry> = {
  [IssueTypeEnum.NEW]: {
    alias: window.i18n.t('新问题'),
    bgColor: '#E1F5F0',
    color: '#21A380',
    icon: 'icon-monitor icon-New',
  },
  [IssueTypeEnum.REGRESSION]: {
    alias: window.i18n.t('回归问题'),
    bgColor: '#FFEDD1',
    color: '#F09305',
    icon: 'icon-monitor icon-lishi',
  },
};

/** Issues 活跃节点类型icon映射*/
export const IssuesActiveNodeIconMap = {
  [IssueActiveNodeTypeEnum.FIRST]: {
    icon: '🚨',
    alias: window.i18n.t('首次出现'),
  },
  [IssueActiveNodeTypeEnum.STATUS]: {
    icon: '🔄',
    alias: window.i18n.t('状态流转：'),
  },
  [IssueActiveNodeTypeEnum.COMMENT]: {
    icon: '',
    alias: window.i18n.t('用户评论'),
  },
  [IssueActiveNodeTypeEnum.DISPATCH]: {
    icon: '📥',
    alias: window.i18n.t('指派负责人：'),
  },
  [IssueActiveNodeTypeEnum.SPLIT]: {
    icon: '✂️',
    alias: window.i18n.t('Issue 拆分'),
  },
  [IssueActiveNodeTypeEnum.MERGE]: {
    icon: '📦',
    alias: window.i18n.t('Issue 合并'),
  },
};
