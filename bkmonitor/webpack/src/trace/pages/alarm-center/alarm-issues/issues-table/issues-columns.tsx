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

import { computed } from 'vue';

import dayjs from 'dayjs';

import { ExploreTableColumnTypeEnum } from '../../../trace-explore/components/trace-explore-table/typing';
import { IssuesPriorityMap, IssuesStatusMap, IssuesTypeMap } from '../constant';

import type {
  BaseTableColumn,
  TableCellRenderContext,
} from '../../../trace-explore/components/trace-explore-table/typing';
import type { IssueItem } from '../typing';
import type { UseIssuesHandlersReturnType } from './use-issues-handlers';
import type { SlotReturnValue } from 'tdesign-vue-next';

/** useIssuesColumns 入参：从 useIssuesHandlers 返回值中提取交互处理函数 */
type IssuesColumnsHandlers = Pick<
  UseIssuesHandlersReturnType,
  'handleAssignClick' | 'handleMarkResolved' | 'handlePriorityClick' | 'handleShowDetail'
>;

/**
 * @description Issues 表格列配置 Composable，通过闭包捕获交互处理函数，
 *              所有 cellRenderer 入参与 TableCellRenderer 签名严格一致
 * @param handlers - 交互处理函数（由 useIssuesHandlers 提供）
 * @returns {{ columns: ComputedRef<BaseTableColumn[]> }} 响应式列配置
 */
export const useIssuesColumns = (handlers: IssuesColumnsHandlers) => {
  /** Issues 表格列配置 */
  const columns = computed<BaseTableColumn[]>(() => [
    {
      colKey: 'row-select',
      type: 'multiple',
      width: 30,
      minWidth: 30,
      fixed: 'left',
    },
    {
      colKey: 'issue_name',
      title: 'Issues',
      minWidth: 200,
      fixed: 'left',
      cellRenderer: renderIssueName,
    },
    {
      colKey: 'tags',
      title: window.i18n.t('标签'),
      minWidth: 180,
      renderType: ExploreTableColumnTypeEnum.TAGS,
    },
    {
      colKey: 'last_seen',
      title: window.i18n.t('最后出现时间'),
      width: 180,
      sorter: true,
      cellRenderer: renderTimeCell,
    },
    {
      colKey: 'first_seen',
      title: window.i18n.t('最早发生时间'),
      width: 180,
      sorter: true,
      cellRenderer: renderTimeCell,
    },
    {
      colKey: 'trend_data',
      title: window.i18n.t('趋势'),
      width: 160,
      cellRenderer: renderTrendCell,
    },
    {
      colKey: 'impact_service',
      title: window.i18n.t('影响范围'),
      minWidth: 160,
      cellRenderer: renderImpactCell,
    },
    {
      colKey: 'priority',
      title: window.i18n.t('优先级'),
      width: 80,
      cellRenderer: renderPriorityCell,
    },
    {
      colKey: 'status',
      title: window.i18n.t('状态'),
      width: 120,
      cellRenderer: renderStatusCell,
    },
    {
      colKey: 'assignee',
      title: window.i18n.t('负责人'),
      minWidth: 120,
      cellRenderer: renderAssigneeCell,
    },
    {
      colKey: 'operation',
      title: window.i18n.t('操作'),
      width: 120,
      fixed: 'right',
      cellRenderer: renderOperationCell,
    },
  ]);

  /**
   * @description Issues 名称列渲染（三行结构：标题 + 异常类型 + 元信息标签）
   * @param row - 当前行 Issue 数据
   * @param columns - 列配置，用于判断是否启用省略号
   * @param renderCtx - 表格单元格渲染上下文
   * @returns 名称列 JSX
   */
  const renderIssueName = (
    row: IssueItem,
    columns: BaseTableColumn,
    renderCtx: TableCellRenderContext
  ): SlotReturnValue => {
    const typeConfig = IssuesTypeMap[row.issue_type];
    return (
      <div class='issues-name-col'>
        <div
          class={`issues-name-title ${renderCtx.isEnabledCellEllipsis(columns)}`}
          onClick={() => handlers.handleShowDetail(row.id)}
        >
          {row.issue_name}
        </div>
        <div class={`issues-name-exception ${renderCtx.isEnabledCellEllipsis(columns)}`}>{row.exception_type}</div>
        <div class='issues-name-meta'>
          <span
            style={{
              '--issues-type-bg': typeConfig?.bgColor || '#E1F5F0',
              '--issues-type-color': typeConfig?.color || '#21A380',
            }}
            class='issues-type-tag'
            title={typeConfig?.alias || row.issue_type}
          >
            <i class={typeConfig?.icon} />
          </span>
          <span class='issues-alert-count'>
            <i class='icon-monitor icon-shijianjiansuo' />
            {row.alert_count}
          </span>
        </div>
      </div>
    ) as unknown as SlotReturnValue;
  };

  /**
   * @description 时间列渲染（相对时间 + 绝对时间双行结构，通过 column.colKey 动态读取时间字段）
   * @param row - 当前行 Issue 数据
   * @param column - 列配置，通过 colKey 确定读取的时间字段
   * @param _renderCtx - 表格单元格渲染上下文（未使用）
   * @returns 时间列 JSX
   */
  const renderTimeCell = (
    row: IssueItem,
    column: BaseTableColumn,
    _renderCtx: TableCellRenderContext
  ): SlotReturnValue => {
    const timestamp = row[column.colKey as string] as number;
    if (!timestamp) return (<span>--</span>) as unknown as SlotReturnValue;
    const dayjsInstance = dayjs.unix(timestamp);
    return (
      <div class='issues-time-col'>
        <div class='time-relative'>{dayjsInstance.fromNow()}</div>
        <div class='time-absolute'>{dayjsInstance.format('YYYY-MM-DD HH:mm:ss')}</div>
      </div>
    ) as unknown as SlotReturnValue;
  };

  /**
   * @description 趋势列渲染（柱状迷你图 + 事件总数）
   * @param row - 当前行 Issue 数据
   * @returns 趋势列 JSX
   */
  const renderTrendCell = (row: IssueItem): SlotReturnValue => {
    const trendData = row.trend_data || [];
    const maxVal = Math.max(...trendData, 1);
    const total = trendData.reduce((sum, v) => sum + v, 0);
    return (
      <div class='issues-trend-col'>
        <div class='trend-bars'>
          {trendData.map((val, i) => (
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
   * @description 影响范围列渲染（服务名 + 主机数双行展示）
   * @param row - 当前行 Issue 数据
   * @returns 影响范围列 JSX
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
   * @description 优先级列渲染（色块标签，显示优先级文字，点击触发优先级选择弹出框）
   * @param row - 当前行 Issue 数据
   * @returns 优先级列 JSX
   */
  const renderPriorityCell = (row: IssueItem): SlotReturnValue => {
    const config = IssuesPriorityMap[row.priority];
    return (
      <div
        class='issues-priority-col'
        onClick={(e: MouseEvent) => handlers.handlePriorityClick(e, row)}
      >
        <span
          style={{
            backgroundColor: config?.bgColor,
            color: config?.color,
          }}
          class='priority-tag'
        >
          {config?.alias ?? '--'}
        </span>
      </div>
    ) as unknown as SlotReturnValue;
  };

  /**
   * @description 状态列渲染（圆角胶囊标签：状态图标 + 状态文字）
   * @param row - 当前行 Issue 数据
   * @returns 状态列 JSX
   */
  const renderStatusCell = (row: IssueItem): SlotReturnValue => {
    const config = IssuesStatusMap[row.status];
    return (
      <div class='issues-status-col'>
        <span
          style={{
            backgroundColor: config?.bgColor,
            color: config?.color,
          }}
          class='status-tag'
        >
          <i class={`status-icon ${config?.icon}`} />
          <span class='status-text'>{config?.alias || row.status}</span>
        </span>
      </div>
    ) as unknown as SlotReturnValue;
  };

  /**
   * @description 负责人列渲染（已指派显示用户标签列表 / 未指派显示可点击的指派入口）
   * @param row - 当前行 Issue 数据
   * @returns 负责人列 JSX
   */
  const renderAssigneeCell = (row: IssueItem): SlotReturnValue => {
    if (!row.assignee?.length) {
      return (
        <div class='issues-assignee-col'>
          <span
            class='assignee-unassigned'
            onClick={() => handlers.handleAssignClick(row)}
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
   * @description 操作列渲染（「标为已解决」快捷操作按钮）
   * @param row - 当前行 Issue 数据
   * @returns 操作列 JSX
   */
  const renderOperationCell = (row: IssueItem): SlotReturnValue => {
    return (
      <div class='issues-operation-col'>
        <span
          class='operation-btn'
          onClick={() => handlers.handleMarkResolved(row.id)}
        >
          {window.i18n.t('标为已解决')}
        </span>
      </div>
    ) as unknown as SlotReturnValue;
  };

  return { columns };
};
