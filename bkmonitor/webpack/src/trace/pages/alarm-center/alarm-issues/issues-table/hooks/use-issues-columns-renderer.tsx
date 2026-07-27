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

import type { MaybeRef } from 'vue';

import { get } from '@vueuse/core';
import { Loading, Radio } from 'bkui-vue';
import dayjs from 'dayjs';
import { useI18n } from 'vue-i18n';
import VueJsonPretty from 'vue-json-pretty';

import { formatTraceTableDate } from '../../../../../components/trace-view/utils/date';
import {
  type BaseTableColumn,
  type TableCellRenderContext,
  ExploreTableColumnTypeEnum,
} from '../../../../trace-explore/components/trace-explore-table/typing';
import { isEllipsisActiveLine } from '../../../../trace-explore/components/trace-explore-table/utils/dom-helper';
import MiniBarChart from '../../components/mini-bar-chart/mini-bar-chart';
import {
  IMPACT_SCOPE_SORT_ORDER_MAP,
  ISSUES_PRIORITY_MAP,
  ISSUES_REGRESSION_MAP,
  ISSUES_STATUS_MAP,
  IssueStatusEnum,
  TrendRangeEnum,
} from '../../constant';
import IssueNameCell from '../components/issue-name-cell/issue-name-cell';

import type { IUsePopoverTools } from '../../../components/alarm-table/hooks/use-popover';
import type { TableColumnItem } from '../../../typings';
import type { ImpactScopeResource, ImpactScopeResourceKeyType, IssueItem, TrendRangeType } from '../../typing';
import type { UseIssuesHandlersReturnType } from './use-issues-handlers';
import type { SlotReturnValue } from 'tdesign-vue-next';

import 'vue-json-pretty/lib/styles.css';

/** useIssuesColumnsRenderer 入参：useIssuesHandlers 返回的交互处理函数 + clickPopoverTools 弹出框工具 */
export type IssuesColumnsRendererCtx = {
  /** 图表联动 ID（相同 group 的 MiniBarChart 实例会联动 tooltip / 高亮） */
  chartGroupId?: MaybeRef<string>;
  /** click popover 工具（基础设施依赖） */
  clickPopoverTools: IUsePopoverTools;
  /** 提交 Issue 名称变更（返回 Promise，用于 loading 状态管理） */
  handleNameChange: (row: IssueItem, name: string) => Promise<void>;
  /** hover popover 工具（基础设施依赖） */
  hoverPopoverTools: IUsePopoverTools;
  /** 趋势时间范围切换回调 */
  onTrendRangeChange?: (range: TrendRangeType) => void;
  /** 趋势数据是否加载中 */
  trendLoading?: MaybeRef<boolean>;
  /** 当前趋势时间范围 */
  trendRange?: MaybeRef<TrendRangeType>;
} & UseIssuesHandlersReturnType;

/**
 * @description Issues 表格列渲染器 hook，负责将静态列配置与各列的自定义渲染逻辑合并
 * @param {IssuesColumnsRendererCtx} rendererCtx - 交互处理函数、clickPopoverTools 弹出框工具及可选的 chartGroupId 图表联动 ID
 * @returns {{ transformColumns: (columns: TableColumnItem[]) => BaseTableColumn[] }} 列转换函数
 */
export const useIssuesColumnsRenderer = (rendererCtx: IssuesColumnsRendererCtx) => {
  const { t } = useI18n();

  /**
   * @description Issues 名称列渲染（三行结构：标题 + 异常消息 + 元信息行（回归类型图标 + 告警数量））
   * @param {IssueItem} row - 当前行 Issue 数据
   * @param {BaseTableColumn} column - 列配置，用于判断是否启用省略号
   * @param {TableCellRenderContext} renderCtx - 表格单元格渲染上下文，提供 isEnabledCellEllipsis 等工具方法
   * @returns {SlotReturnValue} 名称列 JSX
   */
  const renderIssueName = (
    row: IssueItem,
    column: BaseTableColumn,
    renderCtx: TableCellRenderContext
  ): SlotReturnValue => {
    const regressionConfig = ISSUES_REGRESSION_MAP[String(row.is_regression)];

    return (
      <div class='issues-name-col'>
        <div class='issues-name-title'>
          <span
            style={{
              '--issues-type-bg': regressionConfig?.bgColor || '#E1F5F0',
              '--issues-type-color': regressionConfig?.color || '#21A380',
            }}
            class='issues-type-tag'
            onMouseenter={e =>
              rendererCtx.hoverPopoverTools.showPopover(e, regressionConfig?.alias ?? '--', {
                theme: 'alarm-center-popover max-width-50vw text-wrap',
              })
            }
            onMouseleave={() => rendererCtx.hoverPopoverTools.clearPopoverTimer()}
          >
            <i class={regressionConfig?.icon} />
          </span>
          {row.merge_status?.role === 'main' && row.merge_status.active_members?.length && (
            <span
              class='issues-merge-badge'
              onClick={() => rendererCtx.handleSplitClick(row)}
              onMouseenter={e =>
                rendererCtx.hoverPopoverTools.showPopover(
                  e,
                  t('合并了 {n} 个 Issue，点击查看合并明细', { n: row.merge_status?.active_members?.length ?? 0 }),
                  { theme: 'alarm-center-popover max-width-50vw text-wrap' }
                )
              }
              onMouseleave={() => rendererCtx.hoverPopoverTools.clearPopoverTimer()}
            >
              <i class='icon-monitor icon-a-ziIssue' />
              <span class='issues-merge-badge-count'>{row.merge_status?.active_members?.length ?? 0}</span>
            </span>
          )}
          <IssueNameCell
            ellipsisClass={renderCtx.isEnabledCellEllipsis(column)}
            name={row.name || ''}
            onShowDetail={() => rendererCtx.handleShowDetail(row)}
            onSubmit={(newName: string) => rendererCtx.handleNameChange(row, newName)}
          />
        </div>
        <div class='issues-name-description'>
          <span
            class='issues-alert-count'
            onMouseenter={e =>
              rendererCtx.hoverPopoverTools.showPopover(e, `${t('告警事件数')}: ${row.alert_count ?? '--'}`, {
                theme: 'alarm-center-popover max-width-50vw text-wrap',
              })
            }
            onMouseleave={() => rendererCtx.hoverPopoverTools.clearPopoverTimer()}
          >
            <i class='icon-monitor icon-alert-line' />
            <span class='issues-alert-count-number'>{row.alert_count}</span>
          </span>
          <span
            class='issues-name-exception-text'
            onMouseenter={e => {
              const el = e.target as HTMLElement;
              const { isEllipsisActive, content } = isEllipsisActiveLine(el);
              if (isEllipsisActive) {
                let popoverConfigs: {
                  content: Element | string;
                  theme: string;
                } = {
                  content: content,
                  theme: 'dart',
                };
                try {
                  const parsed = JSON.parse(content);
                  popoverConfigs = {
                    content: (
                      <div class='issues-json-popover-content'>
                        <VueJsonPretty
                          data={parsed}
                          showDoubleQuotes={false}
                          showLine={false}
                        />
                      </div>
                    ) as unknown as Element,
                    theme: 'light',
                  };
                } catch {
                  // Not valid JSON, keep original text content
                }
                rendererCtx.hoverPopoverTools.showPopover(e, popoverConfigs.content, {
                  theme: `${popoverConfigs.theme} issues-json-popover max-width-50vw text-wrap`,
                });
              }
            }}
            onMouseleave={() => rendererCtx.hoverPopoverTools.clearPopoverTimer()}
          >
            {row.log_content || row.anomaly_message || '--'}
          </span>
        </div>
      </div>
    ) as unknown as SlotReturnValue;
  };

  /**
   * @description 时间列渲染（相对时间 + 绝对时间双行结构，通过 column.colKey 动态读取时间字段）
   * @param {IssueItem} row - 当前行 Issue 数据
   * @param {BaseTableColumn} column - 列配置，通过 colKey 确定读取的时间字段
   * @param {TableCellRenderContext} renderCtx - 表格单元格渲染上下文，用于绝对时间行的省略号判断
   * @returns {SlotReturnValue} 时间列 JSX
   */
  const renderTimeCell = (
    row: IssueItem,
    column: BaseTableColumn,
    renderCtx: TableCellRenderContext
  ): SlotReturnValue => {
    const timestamp = row[column.colKey as string] as number;
    if (!timestamp) return (<span>--</span>) as unknown as SlotReturnValue;
    const alias = formatTraceTableDate(timestamp);
    return (
      <div class='issues-time-col'>
        <div class='time-relative'>{dayjs.unix(timestamp).fromNow()}</div>
        <div class={`time-absolute ${renderCtx.isEnabledCellEllipsis(column)}`}>{alias}</div>
      </div>
    ) as unknown as SlotReturnValue;
  };

  /**
   * @description 趋势列渲染（MiniBarChart 柱状迷你图，支持通过 chartGroupId 进行图表联动）
   * @param {IssueItem} row - 当前行 Issue 数据
   * @returns {SlotReturnValue} 趋势列 JSX
   */
  const renderTrendCell = (row: IssueItem): SlotReturnValue => {
    if (get(rendererCtx.trendLoading)) {
      return (
        <div class='issues-trend-col is-loading'>
          <Loading
            loading={true}
            mode='spin'
            size='mini'
            theme='primary'
          />
        </div>
      ) as unknown as SlotReturnValue;
    }
    const trend = row.trend || [];
    const effectiveTrend = trend.filter(([, count]) => count > 0);
    if (!effectiveTrend.length) {
      return (
        <div class='issues-trend-col is-empty'>
          <span class='empty-text'>{t('暂无数据')}</span>
        </div>
      ) as unknown as SlotReturnValue;
    }
    const seriesList = [
      {
        datapoints: trend.map(([ts, count]) => [count, ts] as [number, number]),
        name: t('告警事件数'),
        type: 'bar',
        unit: 'none',
      },
    ];
    return (
      <div class='issues-trend-col'>
        <MiniBarChart
          group={get(rendererCtx.chartGroupId)}
          seriesList={seriesList}
        />
      </div>
    ) as unknown as SlotReturnValue;
  };

  /**
   * @description 影响范围列渲染
   * @param {IssueItem} row - 当前行 Issue 数据
   * @returns {SlotReturnValue} 影响范围列 JSX
   */
  const renderImpactCell = (row: IssueItem): SlotReturnValue => {
    const entries = (
      Object.entries(row.impact_scope ?? {}) as Array<[ImpactScopeResourceKeyType, ImpactScopeResource]>
    ).sort((a, b) => IMPACT_SCOPE_SORT_ORDER_MAP[a[0]] - IMPACT_SCOPE_SORT_ORDER_MAP[b[0]]);
    if (!entries.length) {
      return (<span>--</span>) as unknown as SlotReturnValue;
    }
    return (
      <div class='issues-impact-col'>
        {entries.map(([resourceKey, resource]) => (
          <div
            key={resourceKey}
            class='impact-row'
          >
            <span class='impact-label'>{resource.display_name}：</span>
            <span
              class='impact-value is-number'
              onClick={() =>
                rendererCtx.handleImpactScopeClick({
                  resourceKey,
                  resource,
                })
              }
            >
              {resource?.count}
            </span>
          </div>
        ))}
      </div>
    ) as unknown as SlotReturnValue;
  };

  /**
   * @description 优先级列渲染（色块标签，当 popover 激活时高亮当前行，点击触发优先级选择弹出框）
   * @param {IssueItem} row - 当前行 Issue 数据
   * @returns {SlotReturnValue} 优先级列 JSX
   */
  const renderPriorityCell = (row: IssueItem): SlotReturnValue => {
    const config = ISSUES_PRIORITY_MAP[row.priority];
    return (
      <div
        class={[
          'issues-priority-col',
          { 'is-active': get(rendererCtx.clickPopoverTools?.popoverInstance)?.instanceKey === `${row.id}-priority` },
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
   * @param {IssueItem} row - 当前行 Issue 数据
   * @returns {SlotReturnValue} 状态列 JSX
   */
  const renderStatusCell = (
    row: IssueItem,
    column: BaseTableColumn,
    renderCtx: TableCellRenderContext
  ): SlotReturnValue => {
    const config = ISSUES_STATUS_MAP[row.status];
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
          <span class={['status-text', renderCtx.isEnabledCellEllipsis(column)]}>{config?.alias || row.status}</span>
        </span>
      </div>
    ) as unknown as SlotReturnValue;
  };

  /**
   * @description 负责人列渲染（已指派使用 UserTagsCell 显示用户标签 / 未指派显示可点击的指派入口）
   * @param {IssueItem} row - 当前行 Issue 数据
   * @param {BaseTableColumn} column - 列配置
   * @param {TableCellRenderContext} renderCtx - 表格单元格渲染上下文
   * @returns {SlotReturnValue} 负责人列 JSX
   */
  const renderAssigneeCell = (
    row: IssueItem,
    column: BaseTableColumn,
    renderCtx: TableCellRenderContext
  ): SlotReturnValue => {
    return (
      <div
        class='issues-assignee-col'
        onClick={() => rendererCtx.handleAssignClick(row)}
      >
        {row.assignee?.length ? (
          (renderCtx.cellRenderHandleMap[ExploreTableColumnTypeEnum.USER_TAGS]?.(
            row,
            column,
            renderCtx
          ) as SlotReturnValue)
        ) : (
          <div class='assignee-tag-wrapper'>
            <span class='assignee-unassigned'>{t('未指派')}</span>
            <i class='icon-monitor icon-mc-arrow-down' />
          </div>
        )}
      </div>
    ) as unknown as SlotReturnValue;
  };

  /**
   * @description 操作列渲染（根据状态显示「标记为已解决」/「重新打开」/「归档」/「恢复」按钮）
   * @param {IssueItem} row - 当前行 Issue 数据
   * @returns {SlotReturnValue} 操作列 JSX
   */
  const renderOperationCell = (row: IssueItem): SlotReturnValue => {
    const isResolved = row.status === IssueStatusEnum.RESOLVED;
    const isArchived = row.status === IssueStatusEnum.ARCHIVED;
    const canSplit = row.merge_status?.role === 'main' && row.merge_status.active_members?.length;
    return (
      <div class='issues-operation-col'>
        {row.status !== IssueStatusEnum.ARCHIVED && (
          <span
            class='operation-btn'
            onClick={() => rendererCtx.handleAction(row, 'resolve')}
          >
            {isResolved ? t('重新打开') : t('标为已解决')}
          </span>
        )}
        {row.status !== IssueStatusEnum.RESOLVED && (
          <span
            class='operation-btn'
            onClick={() => rendererCtx.handleAction(row, 'archive')}
          >
            {isArchived ? t('恢复') : t('归档')}
          </span>
        )}
        {canSplit && (
          <span
            class='operation-btn'
            onClick={() => rendererCtx.handleSplitClick(row)}
          >
            {t('拆分')}
          </span>
        )}
      </div>
    ) as unknown as SlotReturnValue;
  };

  /** 趋势列头渲染（24h / 7d 胶囊切换） */
  const renderTrendTitle = (): SlotReturnValue => {
    return (
      <div class='issues-trend-header'>
        <Radio.Group
          modelValue={get(rendererCtx.trendRange)}
          size='small'
          type='capsule'
          onUpdate:modelValue={(val: TrendRangeType) => rendererCtx.onTrendRangeChange?.(val)}
        >
          <Radio.Button label={TrendRangeEnum.HOURS_24}>24h</Radio.Button>
          <Radio.Button label={TrendRangeEnum.DAYS_7}>7d</Radio.Button>
        </Radio.Group>
        <span class='issues-trend-header-text'>{t('趋势')}</span>
      </div>
    ) as unknown as SlotReturnValue;
  };

  /** 列渲染配置映射表：按 colKey 定义各列的 cellRenderer / renderType / 布局等配置 */
  const columnsRendererMap: Record<string, Partial<BaseTableColumn>> = {
    name: { cellRenderer: renderIssueName },
    labels: { renderType: ExploreTableColumnTypeEnum.TAGS },
    last_alert_time: { cellRenderer: renderTimeCell },
    first_alert_time: { cellRenderer: renderTimeCell },
    trend: { cellRenderer: renderTrendCell, title: renderTrendTitle },
    impact_scope: { cellRenderer: renderImpactCell },
    priority: { cellRenderer: renderPriorityCell },
    status: { cellRenderer: renderStatusCell },
    assignee: { cellRenderer: renderAssigneeCell, attrs: { class: 'issues-assignee-cell' } },
    operation: { cellRenderer: renderOperationCell },
  };

  /**
   * @description 将外部静态列配置与 columnsRendererMap 中的渲染配置按 colKey 合并，生成完整列定义
   * @param {TableColumnItem[]} columns - 外部传入的静态列配置
   * @returns {BaseTableColumn[]} 合并渲染配置后的完整列定义数组
   */
  const transformColumns = (columns: TableColumnItem[]): BaseTableColumn[] => {
    return columns.map(col => {
      const renderer = columnsRendererMap[col.colKey as string];
      return renderer ? { ...col, ...renderer } : { ...col };
    });
  };

  return { transformColumns };
};
