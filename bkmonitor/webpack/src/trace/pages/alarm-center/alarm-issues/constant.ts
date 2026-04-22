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

/** Issues 详情操作功能枚举 */
export const IssueActionEnum = {
  /** 标记已解决 */
  RESOLVED: IssueStatusEnum.RESOLVED,
  /** 重新打开（未解决） */
  UNRESOLVED: IssueStatusEnum.UNRESOLVED,
  /** 归档 */
  ARCHIVED: IssueStatusEnum.ARCHIVED,
  /** 恢复（取消归档） */
  UN_ARCHIVED: 'un_archived',
} as const;

/** Issues 趋势状态枚举 */
export const TrendStatusEnum = {
  /** 未恢复 */
  ABNORMAL: 'ABNORMAL',
  /** 已恢复 */
  RECOVERED: 'RECOVERED',
  /** 已失效 */
  CLOSED: 'CLOSED',
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
  /** 重新打开 */
  UNRESOLVE: 'unresolve',
  /** 归档 */
  ARCHIVE: 'archive',
  /** 恢复归档 */
  UNARCHIVE: 'unarchive',
} as const;

/** Issues 负责人枚举 */
export const IssueAssigneeEnum = {
  /** 分派给我 */
  ASSIGNED_TO_ME: 'my_assignee',
  /** 未分派 */
  UNASSIGNED: 'no_assignee',
} as const;

/** Issues 活动节点类型枚举 */
export const IssueActiveNodeTypeEnum = {
  /** 负责人变更 */
  ASSIGNEE_CHANGE: 'assignee_change',
  /** 用户评论 */
  COMMENT: 'comment',
  /** 创建 */
  CREATE: 'create',
  /** 优先级变更 */
  PRIORITY_CHANGE: 'priority_change',
  /** 状态变更 */
  STATUS_CHANGE: 'status_change',
  /** 拆分 */
  SPLIT: 'split',
  /** 合并 */
  MERGE: 'merge',
} as const;

/** 影响范围资源类型枚举 */
export const ImpactScopeResourceKeyEnum = {
  /** 集群 */
  SET: 'set',
  /** 主机 */
  HOST: 'host',
  /** 服务实例 */
  SERVICE_INSTANCES: 'service_instances',
  /** K8S 集群 */
  CLUSTER: 'cluster',
  /** 节点 */
  NODE: 'node',
  /** Pod */
  POD: 'pod',
  /** Service */
  SERVICE: 'service',
  /** 应用 */
  APP: 'app',
  /** APM 服务 */
  APM_SERVICE: 'apm_service',
} as const;

/** 影响范围维度 key → 实例 ID 字段名 静态映射表 */
export const IMPACT_SCOPE_ID_FIELD_MAP: Record<string, string> = {
  [ImpactScopeResourceKeyEnum.SET]: 'set_id',
  [ImpactScopeResourceKeyEnum.HOST]: 'bk_host_id',
  [ImpactScopeResourceKeyEnum.SERVICE_INSTANCES]: 'bk_service_instance_id',
  [ImpactScopeResourceKeyEnum.CLUSTER]: 'bcs_cluster_id',
  [ImpactScopeResourceKeyEnum.NODE]: 'node',
  [ImpactScopeResourceKeyEnum.SERVICE]: 'service',
  [ImpactScopeResourceKeyEnum.POD]: 'pod',
  [ImpactScopeResourceKeyEnum.APP]: 'app_name',
  [ImpactScopeResourceKeyEnum.APM_SERVICE]: 'app_name',
};

/** 影响范围资源类型展示排序权重（值越小越靠前）：set > host > service_instances > cluster > node > service > pod > app > apm_service */
export const IMPACT_SCOPE_SORT_ORDER_MAP: Record<string, number> = {
  [ImpactScopeResourceKeyEnum.SET]: 0,
  [ImpactScopeResourceKeyEnum.HOST]: 1,
  [ImpactScopeResourceKeyEnum.SERVICE_INSTANCES]: 2,
  [ImpactScopeResourceKeyEnum.CLUSTER]: 3,
  [ImpactScopeResourceKeyEnum.NODE]: 4,
  [ImpactScopeResourceKeyEnum.SERVICE]: 5,
  [ImpactScopeResourceKeyEnum.POD]: 6,
  [ImpactScopeResourceKeyEnum.APP]: 7,
  [ImpactScopeResourceKeyEnum.APM_SERVICE]: 8,
};

/** 维度名称映射表 */
export const DIMENSION_NAME_MAP = {
  alert_name: window.i18n.t('告警名称'),
  metric: window.i18n.t('指标ID'),
  duration: window.i18n.t('持续时间'),
  ip: window.i18n.t('目标IP'),
  bk_cloud_id: window.i18n.t('管控区域ID'),
  strategy_id: window.i18n.t('策略ID'),
  strategy_name: window.i18n.t('策略名称'),
  assignee: window.i18n.t('通知人'),
  bk_service_instance_id: window.i18n.t('服务实例ID'),
  appointee: window.i18n.t('负责人'),
  labels: window.i18n.t('策略标签'),
  plugin_id: window.i18n.t('告警来源'),
  ipv6: window.i18n.t('目标IPv6'),
};

/** 告警维度内置白名单字段 */
export const DIMENSION_WHITE_LIST_FIELD = [
  'bk_biz_id',
  'ip',
  'ipv6',
  'bk_host_id',
  'bk_cloud_id',
  'bk_service_instance_id',
  'bk_topo_node',
  'target_type',
  'target',
  'category',
  'data_type',
];

// ===================== 常量映射 =====================

/** Issues 状态映射 */
export const ISSUES_STATUS_MAP: Record<IssueStatusType, MapEntry> = {
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
export const ISSUES_PRIORITY_MAP: Record<IssuePriorityType, MapEntry> = {
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
export const ISSUES_ASSIGNEE_MAP = {
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
export const ISSUES_REGRESSION_MAP: Record<string, MapEntry> = {
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
export const ISSUES_ACTIVE_NODE_ICON_MAP = {
  [IssueActiveNodeTypeEnum.ASSIGNEE_CHANGE]: {
    icon: dispatchIcon,
    alias: window.i18n.t('指派负责人'),
  },
  [IssueActiveNodeTypeEnum.COMMENT]: {
    icon: '',
    alias: window.i18n.t('用户评论'),
  },
  [IssueActiveNodeTypeEnum.CREATE]: {
    icon: firstIcon,
    alias: window.i18n.t('首次出现'),
  },
  [IssueActiveNodeTypeEnum.PRIORITY_CHANGE]: {
    icon: statusIcon,
    alias: window.i18n.t('优先级变更'),
  },
  [IssueActiveNodeTypeEnum.STATUS_CHANGE]: {
    icon: statusIcon,
    alias: window.i18n.t('状态流转'),
  },
};
