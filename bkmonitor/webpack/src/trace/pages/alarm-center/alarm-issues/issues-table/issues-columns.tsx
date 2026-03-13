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

import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';

import { ExploreTableColumnTypeEnum } from '../../../trace-explore/components/trace-explore-table/typing';
import { AlarmLevelIconMap } from '../../typings';
import { IssuesPriorityMap, IssuesStatusMap, IssuesTypeMap } from './typings';
import 'dayjs/locale/zh-cn';

import type { BaseTableColumn } from '../../../trace-explore/components/trace-explore-table/typing';
import type { IssueItem } from './typings';
import type { UseIssuesHandlersReturnType } from './use-issues-handlers';
import type { SlotReturnValue } from 'tdesign-vue-next';

dayjs.extend(relativeTime);
dayjs.locale('zh-cn');

/** 列配置工厂函数的交互上下文类型（从 useIssuesHandlers 返回值中提取） */
export type IssuesColumnsContext = Pick<
  UseIssuesHandlersReturnType,
  'handleAssignClick' | 'handleMarkResolved' | 'handlePriorityClick' | 'handleShowDetail'
>;

// ===================== 列渲染方法 =====================

/**
 * @description Issues 名称列渲染（三行结构）
 * @param row - Issue 行数据
 * @param context - 交互上下文
 * @returns 渲染 DOM
 */
const renderIssueName = (row: IssueItem, context: IssuesColumnsContext): SlotReturnValue => {
  const levelConfig = AlarmLevelIconMap?.[row.severity];
  const typeConfig = IssuesTypeMap[row.issue_type];
  return (
    <div class='issues-name-col'>
      {/* 左侧色标 */}
      <i
        style={{ '--issues-level-color': levelConfig?.iconColor || '#3A84FF' }}
        class='issues-level-bar'
      />
      <div class='issues-name-content'>
        {/* 第1行：Issue 标题 */}
        <div
          class='issues-name-title'
          onClick={() => context.handleShowDetail(row.id)}
        >
          {row.issue_name}
        </div>
        {/* 第2行：关键报错信息 */}
        <div class='issues-name-exception'>{row.exception_type}</div>
        {/* 第3行：Issues 类型 + 告警事件数量 */}
        <div class='issues-name-meta'>
          <span
            style={{ '--issues-type-color': typeConfig?.color || '#2DCB56' }}
            class='issues-type-tag'
          >
            <i class='type-dot' />
            {typeConfig?.alias || row.issue_type}
          </span>
          <span class='issues-alert-count'>
            <i class='icon-monitor icon-mc-alarm' />
            {row.alert_count}
          </span>
        </div>
      </div>
    </div>
  ) as unknown as SlotReturnValue;
};

/**
 * @description 时间列渲染（相对时间 + 绝对时间两行结构）
 * @param timestamp - 时间戳（秒）
 * @returns 渲染 DOM
 */
const renderTimeCell = (timestamp: number): SlotReturnValue => {
  if (!timestamp) return (<span>--</span>) as unknown as SlotReturnValue;
  const dayjsInstance = dayjs.unix(timestamp);
  const relativeStr = dayjsInstance.fromNow();
  const absoluteStr = dayjsInstance.format('YYYY-MM-DD HH:mm:ss');
  return (
    <div class='issues-time-col'>
      <div class='time-relative'>{relativeStr}</div>
      <div class='time-absolute'>{absoluteStr}</div>
    </div>
  ) as unknown as SlotReturnValue;
};

/**
 * @description 趋势列渲染（占位柱状条）
 * @param row - Issue 行数据
 * @returns 渲染 DOM
 */
const renderTrendCell = (row: IssueItem): SlotReturnValue => {
  const maxVal = Math.max(...(row.trend_data || []), 1);
  const total = (row.trend_data || []).reduce((sum, v) => sum + v, 0);
  return (
    <div class='issues-trend-col'>
      <div class='trend-bars'>
        {(row.trend_data || []).map((val, i) => (
          <div
            key={i}
            style={{ height: `${Math.max((val / maxVal) * 100, 2)}%` }}
            class='trend-bar'
          />
        ))}
      </div>
      <span class='trend-total'>{total}</span>
    </div>
  ) as unknown as SlotReturnValue;
};

/**
 * @description 影响范围列渲染
 * @param row - Issue 行数据
 * @returns 渲染 DOM
 */
const renderImpactCell = (row: IssueItem): SlotReturnValue => {
  return (
    <div class='issues-impact-col'>
      <div class='impact-row'>
        <span class='impact-label'>{window.i18n.t('服务')}：</span>
        <span class='impact-value'>{row.impact_service || '--'}</span>
      </div>
      <div class='impact-row'>
        <span class='impact-label'>{window.i18n.t('主机')}：</span>
        <span class='impact-value'>{row.impact_host_count ?? '--'}</span>
      </div>
    </div>
  ) as unknown as SlotReturnValue;
};

/**
 * @description 优先级列渲染（可点击更改）
 * @param row - Issue 行数据
 * @param context - 交互上下文
 * @returns 渲染 DOM
 */
const renderPriorityCell = (row: IssueItem, context: IssuesColumnsContext): SlotReturnValue => {
  const config = IssuesPriorityMap[row.priority];
  return (
    <div
      class='issues-priority-col'
      onClick={(e: MouseEvent) => context.handlePriorityClick(e, row)}
    >
      <i
        style={{ color: config?.color }}
        class={`priority-icon ${config?.prefixIcon}`}
      />
    </div>
  ) as unknown as SlotReturnValue;
};

/**
 * @description 状态列渲染
 * @param row - Issue 行数据
 * @returns 渲染 DOM
 */
const renderStatusCell = (row: IssueItem): SlotReturnValue => {
  const config = IssuesStatusMap[row.status];
  return (
    <div class='issues-status-col'>
      <i
        style={{ color: config?.color }}
        class={`status-icon ${config?.prefixIcon}`}
      />
      <span class='status-text'>{config?.alias || row.status}</span>
    </div>
  ) as unknown as SlotReturnValue;
};

/**
 * @description 负责人列渲染（区分已指派/未指派）
 * @param row - Issue 行数据
 * @param context - 交互上下文
 * @returns 渲染 DOM
 */
const renderAssigneeCell = (row: IssueItem, context: IssuesColumnsContext): SlotReturnValue => {
  const hasAssignee = row.assignee?.length > 0;
  if (!hasAssignee) {
    return (
      <div class='issues-assignee-col'>
        <span
          class='assignee-unassigned'
          onClick={() => context.handleAssignClick(row)}
        >
          {window.i18n.t('未指派')}
        </span>
      </div>
    ) as unknown as SlotReturnValue;
  }
  return (
    <div class='issues-assignee-col'>
      {row.assignee.map(user => (
        <span
          key={user}
          class='assignee-tag'
        >
          {user}
        </span>
      ))}
    </div>
  ) as unknown as SlotReturnValue;
};

/**
 * @description 操作列渲染
 * @param row - Issue 行数据
 * @param context - 交互上下文
 * @returns 渲染 DOM
 */
const renderOperationCell = (row: IssueItem, context: IssuesColumnsContext): SlotReturnValue => {
  return (
    <div class='issues-operation-col'>
      <span
        class='operation-btn'
        onClick={() => context.handleMarkResolved(row.id)}
      >
        {window.i18n.t('标为已解决')}
      </span>
    </div>
  ) as unknown as SlotReturnValue;
};

// ===================== 列配置工厂函数 =====================

/**
 * @description 获取 Issues 表格列配置
 * @param context - 交互上下文对象（由 useIssuesHandlers 提供的处理函数）
 * @returns BaseTableColumn[] 列配置数组
 */
export const getIssuesColumns = (context: IssuesColumnsContext): BaseTableColumn[] => {
  return [
    // 多选列
    {
      colKey: 'row-select',
      type: 'multiple',
      width: 50,
      minWidth: 50,
      fixed: 'left',
    },
    // Issues 名称
    {
      colKey: 'issue_name',
      title: 'Issues',
      minWidth: 280,
      fixed: 'left',
      cellRenderer: (row, _column, _renderCtx) => renderIssueName(row, context),
    },
    // 标签
    {
      colKey: 'tags',
      title: window.i18n.t('标签'),
      minWidth: 180,
      renderType: ExploreTableColumnTypeEnum.TAGS,
    },
    // 最后出现时间
    {
      colKey: 'last_seen',
      title: window.i18n.t('最后出现时间'),
      width: 180,
      sorter: true,
      cellRenderer: (row, _column, _renderCtx) => renderTimeCell(row.last_seen),
    },
    // 最早发生时间
    {
      colKey: 'first_seen',
      title: window.i18n.t('最早发生时间'),
      width: 180,
      sorter: true,
      cellRenderer: (row, _column, _renderCtx) => renderTimeCell(row.first_seen),
    },
    // 趋势
    {
      colKey: 'trend_data',
      title: window.i18n.t('趋势'),
      width: 160,
      cellRenderer: (row, _column, _renderCtx) => renderTrendCell(row),
    },
    // 影响范围
    {
      colKey: 'impact_service',
      title: window.i18n.t('影响范围'),
      minWidth: 160,
      cellRenderer: (row, _column, _renderCtx) => renderImpactCell(row),
    },
    // 优先级
    {
      colKey: 'priority',
      title: window.i18n.t('优先级'),
      width: 80,
      cellRenderer: (row, _column, _renderCtx) => renderPriorityCell(row, context),
    },
    // 状态
    {
      colKey: 'status',
      title: window.i18n.t('状态'),
      width: 120,
      cellRenderer: (row, _column, _renderCtx) => renderStatusCell(row),
    },
    // 负责人
    {
      colKey: 'assignee',
      title: window.i18n.t('负责人'),
      minWidth: 120,
      cellRenderer: (row, _column, _renderCtx) => renderAssigneeCell(row, context),
    },
    // 操作
    {
      colKey: 'operation',
      title: window.i18n.t('操作'),
      width: 120,
      fixed: 'right',
      cellRenderer: (row, _column, _renderCtx) => renderOperationCell(row, context),
    },
  ];
};
