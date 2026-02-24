/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
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

import { EMode } from '../../../../../components/retrieval-filter/typing';
import {
  type BaseTableColumn,
  type GetTableCellRenderValue,
  type TableCellRenderContext,
  ExploreTableColumnTypeEnum,
} from '../../../../trace-explore/components/trace-explore-table/typing';
import { ACTION_STORAGE_KEY } from '../../../services/action-services';
import {
  type ActionTableItem,
  type CommonCondition,
  type TableEmpty,
  ActionFailureTypeMap,
  ActionLevelIconMap,
  ActionStatusIconMap,
} from '../../../typings';
import { BaseScenario } from './base-scenario';

import type { IUsePopoverTools } from '../hooks/use-popover';
import type { SlotReturnValue } from 'tdesign-vue-next';

/**
 * @class ActionScenario
 * @classdesc 处理记录场景表格特殊列渲染配置类
 * @extends BaseScenario
 */
export class ActionScenario extends BaseScenario {
  readonly name = ACTION_STORAGE_KEY;
  readonly privateClassName = 'action-table';

  constructor(
    private readonly context: {
      [methodName: string]: any;
      handleActionSliderShowDetail: (id: string) => void;
      hoverPopoverTools: IUsePopoverTools;
    }
  ) {
    super();
  }

  getEmptyConfig(): TableEmpty {
    return {
      type: 'search-empty',
      emptyText: window.i18n.t('当前检索范围，暂无处理记录'),
    };
  }

  getColumnsConfig(): Record<string, Partial<BaseTableColumn>> {
    const columns: Record<string, Partial<BaseTableColumn>> = {
      /** 告警状态(id) 列 */
      id: {
        attrs: { class: 'alarm-first-col' },
        cellRenderer: (row, column, renderCtx) => this.renderActionId(row, column, renderCtx),
      },
      /** 负责人(operator) 列 */
      operator: {
        renderType: ExploreTableColumnTypeEnum.USER_TAGS,
      },
      /** 触发告警数(alert_count) 列 */
      alert_count: {
        getRenderValue: row => row?.alert_id?.length || 0,
        clickCallback: (row, column) => this.handleToAlertList(row, column),
        cellRenderer: (row, column, renderCtx) => this.renderCount(row, column, renderCtx),
      },
      /** 防御告警数(converge_count) 列 */
      converge_count: {
        clickCallback: (row, column) => this.handleToAlertList(row, column),
        cellRenderer: (row, column, renderCtx) => this.renderCount(row, column, renderCtx),
      },
      /** 执行状态(status) 列 */
      status: {
        renderType: ExploreTableColumnTypeEnum.PREFIX_ICON,
        getRenderValue: row => this.getStatusIconConfig(row),
      },
      /** 具体内容(content) 列 */
      content: {
        cellRenderer: (row, column, renderCtx) => this.renderContent(row, column, renderCtx),
      },
    };

    return columns;
  }

  // ----------------- 处理记录场景私有渲染方法 -----------------
  /**
   * @description 告警状态(id) 列渲染方法
   * @param {ActionTableItem} row 处理记录项
   * @param {BaseTableColumn} column 触发列的列配置项
   * @param {TableCellRenderContext} renderCtx 列渲染上下文
   * @returns {SlotReturnValue} 渲染dom
   */
  private renderActionId(
    row: ActionTableItem,
    column: BaseTableColumn,
    renderCtx: TableCellRenderContext
  ): SlotReturnValue {
    const rectColor = ActionLevelIconMap?.[row?.status]?.iconColor;
    return (
      <div class='explore-col lever-rect-col'>
        <i
          style={{ '--lever-rect-color': rectColor }}
          class='lever-rect'
        />
        <div
          class={`lever-rect-text ${renderCtx.isEnabledCellEllipsis(column)}`}
          onClick={() => this.context.handleActionSliderShowDetail(row.id)}
        >
          <span>{row?.id}</span>
        </div>
      </div>
    ) as unknown as SlotReturnValue;
  }

  /**
   * @description 触发告警数(alert_count) 和 防御告警数(converge_count) 列渲染方法
   * @param {ActionTableItem} row 处理记录项
   * @param {BaseTableColumn} column 触发列的列配置项
   * @param {TableCellRenderContext} renderCtx 列渲染上下文
   * @returns {SlotReturnValue} 渲染dom
   */
  private renderCount(
    row: ActionTableItem,
    column: BaseTableColumn,
    renderCtx: TableCellRenderContext
  ): SlotReturnValue {
    const count = renderCtx.getTableCellRenderValue(row, column) as number;
    if (count > 0) {
      return renderCtx.cellRenderHandleMap?.[ExploreTableColumnTypeEnum.CLICK]?.(row, column, renderCtx);
    }
    return renderCtx.cellRenderHandleMap?.[ExploreTableColumnTypeEnum.TEXT]?.(row, column, renderCtx);
  }

  /**
   * @description 具体内容(content) 列渲染方法
   * @param {ActionTableItem} row 处理记录项
   * @param {BaseTableColumn} column 触发列的列配置项
   * @param {TableCellRenderContext} renderCtx 列渲染上下文
   * @returns {SlotReturnValue} 渲染dom
   */
  private renderContent(
    row: ActionTableItem,
    column: BaseTableColumn,
    renderCtx: TableCellRenderContext
  ): SlotReturnValue {
    const contentArr = row?.content?.text.split('$') || [];
    let contentDom = null;
    if (contentArr[1]) {
      contentDom = (
        <span>
          {contentArr[0]}
          <a
            href={row.content.url}
            target='blank'
          >
            {contentArr[1]}
          </a>
          {contentArr[2] || ''}
        </span>
      );
    } else {
      contentDom = <span>{row?.content?.text || '--'}</span>;
    }
    return (
      <div class='explore-col action-content-col'>
        <div class={renderCtx.isEnabledCellEllipsis(column)}>{contentDom}</div>
      </div>
    ) as unknown as SlotReturnValue;
  }
  // ----------------- 处理记录场景私有逻辑方法 -----------------

  /**
   * @method handleToAlertList 触发告警数(alert_count) | 防御告警数(converge_count) 列 click事件
   * @description 新开页跳转至告警中心 - 告警场景页面并添加筛选项
   * @param {ActionTableItem} row 处理记录项
   * @param {BaseTableColumn} column 触发列的列配置项
   */
  private handleToAlertList(row: ActionTableItem, column: BaseTableColumn) {
    // eslint-disable-next-line @typescript-eslint/naming-convention
    const { id, create_time, end_time, bk_biz_id } = row;
    const bizId = bk_biz_id || (window.bk_biz_id as number) || (window.cc_biz_id as number) || undefined;
    const curUnix = dayjs.tz().unix() * 1000;
    const oneDay = 60 * 24 * 60 * 1000;
    const startTime = dayjs.tz(create_time * 1000 - oneDay).valueOf();
    const endTime = end_time
      ? dayjs.tz(end_time * 1000 + oneDay > curUnix ? curUnix : end_time * 1000 + oneDay).valueOf()
      : dayjs.tz().valueOf();
    const searchParams = new URLSearchParams({
      bizIds: JSON.stringify([bizId]),
      from: String(startTime),
      to: String(endTime),
      filterMode: EMode.ui,
      conditions: JSON.stringify([
        {
          key: column.colKey === 'converge_count' ? 'converge_id' : 'action_id',
          method: 'eq',
          value: [id],
          condition: 'and',
        },
      ] satisfies CommonCondition[]),
    });
    window.open(
      `${location.origin}${location.pathname}?bizId=${bizId}/#/trace/alarm-center?${searchParams.toString()}`
    );
  }

  /**
   * @description 状态(status) 列 获取prefixIcon 渲染配置项
   * @param {ActionTableItem} row 处理记录项
   * @return {GetTableCellRenderValue<ExploreTableColumnTypeEnum.PREFIX_ICON>} prefixIcon 渲染配置项
   */
  private getStatusIconConfig(row: ActionTableItem): GetTableCellRenderValue<ExploreTableColumnTypeEnum.PREFIX_ICON> {
    const prefixItem = ActionStatusIconMap[row.status];
    let alias = prefixItem?.alias;
    if (row.status === 'failure') {
      alias = ActionFailureTypeMap[row.failure_type] ?? alias;
    }
    return {
      alias,
      prefixIcon: prefixItem?.prefixIcon,
    };
  }
}
