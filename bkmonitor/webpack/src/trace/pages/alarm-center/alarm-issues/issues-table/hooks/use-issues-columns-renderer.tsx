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

import { ExploreTableColumnTypeEnum } from '../../../../trace-explore/components/trace-explore-table/typing';
import { IssuesPriorityMap, IssuesStatusMap, IssuesTypeMap } from '../../constant';

import type {
  BaseTableColumn,
  TableCellRenderContext,
} from '../../../../trace-explore/components/trace-explore-table/typing';
import type { IUsePopoverTools } from '../../../components/alarm-table/hooks/use-popover';
import type { TableColumnItem } from '../../../typings';
import type { IssueItem } from '../../typing';
import type { UseIssuesHandlersReturnType } from '../use-issues-handlers';
import type { SlotReturnValue } from 'tdesign-vue-next';

/** useIssuesColumnsRenderer 入参：从 useIssuesHandlers 返回值中提取交互处理函数 */
export type IssuesColumnsRendererCtx = UseIssuesHandlersReturnType & { clickPopoverTools: IUsePopoverTools };

/**
 * @method useIssuesColumnsRenderer issue表格列渲染器 hook
 * @description 无状态 hook，只充当表格列渲染器职责
 * @param rendererCtx - 交互处理函数（由 useIssuesHandlers 提供）
 * @returns {{ transformColumns: (columns: TableColumnItem[]) => BaseTableColumn[] }} 列转换函数
 */
export const useIssuesColumnsRenderer = (rendererCtx: IssuesColumnsRendererCtx) => {
  /**
   * @description Issues 名称列渲染（三行结构：标题 + 异常类型 + 元信息标签）
   * @param row - 当前行 Issue 数据
   * @param column - 列配置，用于判断是否启用省略号
   * @param renderCtx - 表格单元格渲染上下文
   * @returns 名称列 JSX
   */
  const renderIssueName = (
    row: IssueItem,
    column: BaseTableColumn,
    renderCtx: TableCellRenderContext
  ): SlotReturnValue => {
    const typeConfig = IssuesTypeMap[row.issue_type];
    return (
      <div class='issues-name-col'>
        <div class={`issues-name-title ${renderCtx.isEnabledCellEllipsis(column)}`}>
          <span
            class='issues-name-title-text'
            onClick={() => rendererCtx.handleShowDetail(row.id)}
          >
            {row.issue_name}
          </span>
        </div>
        <div class={`issues-name-exception ${renderCtx.isEnabledCellEllipsis(column)}`}>
          <span class='issues-name-exception-text'>{row.exception_type}</span>
        </div>
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
   * @param renderCtx - 表格单元格渲染上下文（未使用）
   * @returns 时间列 JSX
   */
  const renderTimeCell = (
    row: IssueItem,
    column: BaseTableColumn,
    renderCtx: TableCellRenderContext
  ): SlotReturnValue => {
    const timestamp = row[column.colKey as string] as number;
    if (!timestamp) return (<span>--</span>) as unknown as SlotReturnValue;
    const dayjsInstance = dayjs.unix(timestamp);
    return (
      <div class='issues-time-col'>
        <div class='time-relative'>{dayjsInstance.fromNow()}</div>
        <div class={`time-absolute ${renderCtx.isEnabledCellEllipsis(column)}`}>
          {dayjsInstance.format('YYYY-MM-DD HH:mm:ss')}
        </div>
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
  const renderImpactCell = (
    row: IssueItem,
    column: BaseTableColumn,
    renderCtx: TableCellRenderContext
  ): SlotReturnValue => {
    return (
      <div class='issues-impact-col'>
        <div class='impact-row'>
          <span class='impact-label'>{window.i18n.t('服务')} ：</span>
          <span class={`impact-value is-string ${renderCtx.isEnabledCellEllipsis(column)}`}>
            {row.impact_service || '--'}
          </span>
        </div>
        <div class='impact-row'>
          <span class='impact-label'>{window.i18n.t('主机')} ：</span>
          <span class='impact-value is-number'>{row.impact_host_count ?? '--'}</span>
        </div>
      </div>
    ) as unknown as SlotReturnValue;
  };

  /**
   * @description 优先级列渲染（色块标签 + hover 高亮 wrapper，点击触发优先级选择弹出框）
   * @param row - 当前行 Issue 数据
   * @returns 优先级列 JSX
   */
  const renderPriorityCell = (row: IssueItem): SlotReturnValue => {
    const config = IssuesPriorityMap[row.priority];
    return (
      <div
        class={[
          'issues-priority-col',
          { 'is-active': rendererCtx.clickPopoverTools?.popoverInstance?.value?.instanceKey === `${row.id}-priority` },
        ]}
        onClick={(e: MouseEvent) => rendererCtx.handlePriorityClick(e, row)}
      >
        <div class='priority-tag-wrapper'>
          <div
            style={{
              backgroundColor: config?.bgColor,
              color: config?.color,
            }}
            class='priority-tag'
          >
            {config?.alias ?? '--'}
          </div>
        </div>
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
            onClick={() => rendererCtx.handleAssignClick(row)}
          >
            {window.i18n.t('未指派')}
          </span>
          <i class='icon-monitor icon-mc-arrow-down' />
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
          onClick={() => rendererCtx.handleMarkResolved(row.id)}
        >
          {window.i18n.t('标为已解决')}
        </span>
      </div>
    ) as unknown as SlotReturnValue;
  };

  /** cellRenderer / renderType 映射表：按 colKey 定义各列的渲染配置 */
  const columnsRendererMap: Record<string, Partial<BaseTableColumn>> = {
    'row-select': { type: 'multiple', width: 30, minWidth: 30, fixed: 'left' },
    issue_name: { cellRenderer: renderIssueName },
    tags: { renderType: ExploreTableColumnTypeEnum.TAGS },
    last_seen: { cellRenderer: renderTimeCell },
    first_seen: { cellRenderer: renderTimeCell },
    trend_data: { cellRenderer: renderTrendCell },
    impact_service: { cellRenderer: renderImpactCell },
    priority: { cellRenderer: renderPriorityCell },
    status: { cellRenderer: renderStatusCell },
    assignee: { cellRenderer: renderAssigneeCell },
    operation: { cellRenderer: renderOperationCell },
  };

  /**
   * @description 将静态列配置与 cellRenderer 按 colKey 合并，返回完整列配置
   * @param columns - 外部传入的静态列配置
   * @returns 合并后的完整列配置
   */
  const transformColumns = (columns: TableColumnItem[]): BaseTableColumn[] => {
    return columns.map(col => {
      const renderer = columnsRendererMap[col.colKey as string];
      return renderer ? { ...col, ...renderer } : { ...col };
    });
  };

  return { transformColumns };
};
