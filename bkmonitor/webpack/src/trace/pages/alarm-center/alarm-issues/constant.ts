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

import dispatchIcon from '../../../static/img/issues/dispatch.png';
import firstIcon from '../../../static/img/issues/first.png';
import mergeIcon from '../../../static/img/issues/merge.png';
import splitIcon from '../../../static/img/issues/split.png';
import statusIcon from '../../../static/img/issues/status.png';

import type { IssuePriorityType, IssueStatusType, MapEntry } from './typing';

// ===================== 枚举常量 =====================

/** Issues 详情 Tab 枚举 */
export const IssueDetailTabEnum = {
  /** 最近的告警 */
  LATEST: 'latest',
  /** 最早的告警 */
  EARLIEST: 'earliest',
  /** 告警列表 */
  LIST: 'list',
} as const;

/** Issues 优先级枚举 */
export const IssuePriorityEnum = {
  /** 高 */
  P0: 'P0',
  /** 中 */
  P1: 'P1',
  /** 低 */
  P2: 'P2',
} as const;

/** Issues 状态枚举 */
export const IssueStatusEnum = {
  /** 待审核 */
  PENDING_REVIEW: 'pending_review',
  /** 已解决 */
  RESOLVED: 'resolved',
  /** 未解决 */
  UNRESOLVED: 'unresolved',
  /** 归档 */
  ARCHIVED: 'archived',
} as const;

/** Issues 是否回归映射枚举（true=回归问题，false=新问题） */
export const IssueRegressionEnum = {
  /** 回归问题 */
  REGRESSION: true,
  /** 新问题 */
  NEW: false,
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

/** Issues 负责人枚举 */
export const IssueAssigneeEnum = {
  /** 分派给我 */
  ASSIGNED_TO_ME: 'my_assignee',
  /** 未分派 */
  UNASSIGNED: 'no_assignee',
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
  [IssueStatusEnum.ARCHIVED]: {
    alias: window.i18n.t('归档'),
    icon: 'icon-monitor icon-guidang',
    color: '#6F7F9A',
    bgColor: '#E9EDF5',
  },
};

/** Issues 优先级映射 */
export const IssuesPriorityMap: Record<IssuePriorityType, MapEntry> = {
  [IssuePriorityEnum.P0]: {
    alias: window.i18n.t('button-高'),
    bgColor: '#E54040',
    color: '#FFFFFF',
  },
  [IssuePriorityEnum.P1]: {
    alias: window.i18n.t('button-中'),
    bgColor: '#FAA41E',
    color: '#FFFFFF',
  },
  [IssuePriorityEnum.P2]: {
    alias: window.i18n.t('button-低'),
    bgColor: '#8F9FBD',
    color: '#FFFFFF',
  },
};

/** Issues 负责人映射 */
export const IssuesAssigneeMap = {
  [IssueAssigneeEnum.ASSIGNED_TO_ME]: {
    alias: window.i18n.t('分派给我'),
    icon: 'icon-monitor icon-gaojingfenpai',
    color: '#8F9FBD',
  },
  [IssueAssigneeEnum.UNASSIGNED]: {
    alias: window.i18n.t('未分派'),
    icon: 'icon-monitor icon-bangzhu',
    color: '#8F9FBD',
  },
};

/** Issues 回归类型映射（key 为 is_regression 布尔值的字符串形式） */
export const IssuesRegressionMap: Record<string, MapEntry> = {
  false: {
    alias: window.i18n.t('新问题'),
    bgColor: '#E1F5F0',
    color: '#21A380',
    icon: 'icon-monitor icon-New',
  },
  true: {
    alias: window.i18n.t('回归问题'),
    bgColor: '#FFEDD1',
    color: '#F09305',
    icon: 'icon-monitor icon-lishi',
  },
};

/** Issues 活跃节点类型icon映射 */
export const IssuesActiveNodeIconMap = {
  [IssueActiveNodeTypeEnum.FIRST]: {
    icon: firstIcon,
    alias: window.i18n.t('首次出现'),
  },
  [IssueActiveNodeTypeEnum.STATUS]: {
    icon: statusIcon,
    alias: window.i18n.t('状态流转：'),
  },
  [IssueActiveNodeTypeEnum.COMMENT]: {
    icon: '',
    alias: window.i18n.t('用户评论'),
  },
  [IssueActiveNodeTypeEnum.DISPATCH]: {
    icon: dispatchIcon,
    alias: window.i18n.t('指派负责人：'),
  },
  [IssueActiveNodeTypeEnum.SPLIT]: {
    icon: splitIcon,
    alias: window.i18n.t('Issue 拆分'),
  },
  [IssueActiveNodeTypeEnum.MERGE]: {
    icon: mergeIcon,
    alias: window.i18n.t('Issue 合并'),
  },
};
