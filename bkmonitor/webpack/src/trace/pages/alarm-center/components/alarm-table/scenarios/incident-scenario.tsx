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

import { type MaybeRef } from 'vue';

import { get } from '@vueuse/core';

import { formatTraceTableDate } from '../../../../../components/trace-view/utils/date';
import {
  type BaseTableColumn,
  type TableCellRenderContext,
  ExploreTableColumnTypeEnum,
} from '../../../../trace-explore/components/trace-explore-table/typing';
import { INCIDENT_STORAGE_KEY } from '../../../services/incident-services';
import { type IncidentTableItem, type TableEmpty, IncidentLevelIconMap, IncidentStatusIconMap } from '../../../typings';
import { BaseScenario } from './base-scenario';

import type { IUsePopoverTools } from '../hooks/use-popover';
import type { SlotReturnValue } from 'tdesign-vue-next';
import type { Router } from 'vue-router';
/**
 * @class IncidentScenario
 * @classdesc 故障场景表格特殊列渲染配置类
 * @extends BaseScenario
 */
export class IncidentScenario extends BaseScenario {
  readonly name = INCIDENT_STORAGE_KEY;
  readonly privateClassName = 'incident-table';

  constructor(
    private readonly context: {
      [methodName: string]: any;
      hoverPopoverTools: IUsePopoverTools;
      router: Router;
      timeRange: MaybeRef<string[]>;
    }
  ) {
    super();
  }

  getEmptyConfig(): TableEmpty {
    return {
      type: 'search-empty',
      emptyText: window.i18n.t('当前检索范围，暂无故障'),
    };
  }

  getColumnsConfig(): Record<string, Partial<BaseTableColumn>> {
    const columns: Record<string, Partial<BaseTableColumn>> = {
      /** 故障名称(incident_name) 列 */
      incident_name: {
        attrs: { class: 'alarm-first-col' },
        cellRenderer: (row, column, renderCtx) => this.renderActionId(row, column, renderCtx),
      },
      /** 故障状态(status) 列 */
      status: {
        renderType: ExploreTableColumnTypeEnum.PREFIX_ICON,
        getRenderValue: row => IncidentStatusIconMap[row?.status],
      },
      /** 告警数量(alert_count) 列 */
      alert_count: {
        getRenderValue: row => row?.alert_count,
        clickCallback: row => this.jumpToIncidentDetail(row.id, 'FailureView'),
        cellRenderer: (row, column, renderCtx) => this.renderCount(row, column, renderCtx),
      },
      /** 标签(labels) 列 */
      labels: {
        renderType: ExploreTableColumnTypeEnum.TAGS,
        getRenderValue: row => this.formatterIncidentLabels(row?.labels),
      },
      /** 开始时间 / 结束时间(end_time) 列 */
      end_time: {
        cellRenderer: (row, column, renderCtx) => this.renderEndTime(row, column, renderCtx),
      },
      /** 负责人(assignees) 列 */
      assignees: {
        renderType: ExploreTableColumnTypeEnum.USER_TAGS,
      },
    };

    return columns;
  }

  // ----------------- 故障场景私有渲染方法 -----------------
  /**
   * @description 故障名称(incident_name) 列渲染方法
   * @param {IncidentTableItem} row 故障项
   * @param {BaseTableColumn} column 触发列的列配置项
   * @param {TableCellRenderContext} renderCtx 列渲染上下文
   * @returns {SlotReturnValue} 渲染dom
   */
  private renderActionId(
    row: IncidentTableItem,
    column: BaseTableColumn,
    renderCtx: TableCellRenderContext
  ): SlotReturnValue {
    const rectColor = IncidentLevelIconMap?.[row?.level]?.iconColor;
    return (
      <div class='explore-col lever-rect-col'>
        <i
          style={{ '--lever-rect-color': rectColor }}
          class='lever-rect'
        />
        <div
          class={`lever-rect-text ${renderCtx.isEnabledCellEllipsis(column)}`}
          onClick={() => this.jumpToIncidentDetail(row.id)}
        >
          <span>{row?.incident_name}</span>
        </div>
      </div>
    ) as unknown as SlotReturnValue;
  }
  /**
   * @description 告警数量(alert_count) 列渲染方法
   * @param {IncidentTableItem} row 故障项
   * @param {BaseTableColumn} column 触发列的列配置项
   * @param {TableCellRenderContext} renderCtx 列渲染上下文
   */
  private renderCount(
    row: IncidentTableItem,
    column: BaseTableColumn,
    renderCtx: TableCellRenderContext
  ): SlotReturnValue {
    const count = renderCtx.getTableCellRenderValue(row, column) as number;
    if (count > -1) {
      return renderCtx.cellRenderHandleMap?.[ExploreTableColumnTypeEnum.CLICK]?.(row, column, renderCtx);
    }
    return renderCtx.cellRenderHandleMap?.[ExploreTableColumnTypeEnum.TEXT]?.(row, column, renderCtx);
  }

  /**
   * @description 开始时间 / 结束时间(end_time) 列渲染方法
   * @param {IncidentTableItem} row 故障项
   * @param {BaseTableColumn} column 触发列的列配置项
   * @param {TableCellRenderContext} renderCtx 列渲染上下文
   * @returns {SlotReturnValue} 渲染dom
   */
  private renderEndTime(row: IncidentTableItem, column: BaseTableColumn, renderCtx: TableCellRenderContext) {
    const beginTime = row.begin_time ? formatTraceTableDate(row.begin_time) : '--';
    const endTime = row.end_time ? formatTraceTableDate(row.end_time) : '--';
    return (
      <div class={'explore-col explore-text-col incident-end-time-col'}>
        <div class={`${renderCtx.isEnabledCellEllipsis(column)}`}>
          <span class={'explore-col-text'}>
            {beginTime} / <br /> {endTime}
          </span>
        </div>
      </div>
    ) as unknown as SlotReturnValue;
  }

  // ----------------- 故障场景私有逻辑方法 -----------------
  /**
   * @description 跳转至故障详情页面
   * @param {string} id 故障id
   * @param {string} activeTab 跳转至故障页面后激活显示的tab
   */
  private jumpToIncidentDetail(id: string, activeTab = '') {
    const timeRange = get(this.context.timeRange) || [];
    this.context.router.push({
      name: 'incident-detail',
      params: {
        id,
      },
      query: {
        activeTab,
        from: timeRange[0],
        to: timeRange[1],
      },
    });
  }

  /**
   * @description 格式化故障标签数据
   * @param {string[]} labels 标签数组
   */
  private formatterIncidentLabels(labels) {
    return labels?.map?.(label => {
      if (typeof label === 'string') {
        return label.replace(/\//g, '');
      }
      if (label?.key) {
        return `${label.key}: ${label.value.replace(/\//g, '')}`;
      }
      return '--';
    });
  }
}
