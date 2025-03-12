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

import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import EmptyStatus from '../../../components/empty-status/empty-status';
import TableSkeleton from '../../../components/skeleton/table-skeleton';
import { formatTime } from '../../../utils';
import {
  type DimensionsTypeEnum,
  type EventExploreTableColumn,
  type EventExploreTableRequestConfigs,
  type ExploreEntitiesMap,
  type ExploreFieldMap,
  ExploreSourceTypeEnum,
  ExploreTableColumnTypeEnum,
  ExploreTableLoadingEnum,
} from '../typing';
import { getEventLegendColorByType } from '../utils';
import ExploreExpandViewWrapper from './explore-expand-view-wrapper';

import type { EmptyStatusType } from '../../../components/empty-status/types';
import type { IWhereItem } from '../../../components/retrieval-filter/utils';

import './event-explore-table.scss';

interface EventExploreTableProps {
  requestConfigs: EventExploreTableRequestConfigs;
  fieldMap: ExploreFieldMap;
  entitiesMapList: ExploreEntitiesMap[];
}

interface EventExploreTableEvents {
  onConditionChange: (condition: IWhereItem[]) => void;
  onClearSearch: () => void;
}

/**
 * @description 事件来源不同类型所显示的图标 映射
 */
const SourceIconMap = {
  [ExploreSourceTypeEnum.BCS]: 'icon-bcs',
  [ExploreSourceTypeEnum.CICD]: 'icon-landun',
  [ExploreSourceTypeEnum.HOST]: 'icon-host',
};

@Component
export default class EventExploreTable extends tsc<EventExploreTableProps, EventExploreTableEvents> {
  /** 接口请求配置项 */
  @Prop({ type: Object, default: () => ({}) }) requestConfigs: EventExploreTableRequestConfigs;
  /** expand 展开 kv 面板使用 */
  @Prop({ type: Object, default: () => ({ source: {}, target: {} }) }) fieldMap: ExploreFieldMap;
  /** expand 展开 kv 面板使用 */
  @Prop({ type: Array, default: () => [] }) entitiesMapList: ExploreEntitiesMap[];

  /** table loading 配置*/
  tableLoading = {
    /** table 骨架屏 loading */
    [ExploreTableLoadingEnum.REFRESH]: false,
    /** 表格触底加载更多 loading  */
    [ExploreTableLoadingEnum.SCROLL]: false,
  };

  /** table 数据 */
  tableData = [];
  /** popover 实例 */
  popoverInstance = null;
  /** popover 延迟打开定时器 */
  popoverDelayTimer = null;

  get tableColumns() {
    const column = this.getTableColumns();
    const columnForKeyMap = column.reduce((prev, curr) => {
      prev[curr.id] = curr;
      return prev;
    }, {});

    return {
      columns: column,
      columnForKeyMap,
    };
  }

  /**
   * @description 判断当前数据是否需要触底加载更多
   *
   */
  get tableHasScrollLoading() {
    const total = this.requestConfigs?.total ?? 0;
    const dataLen = this.tableData?.length ?? 0;
    return !!total && dataLen < total;
  }

  /** table 空数据时显示样式类型 'search-empty'/'empty' */
  get tableEmptyType(): EmptyStatusType {
    // eslint-disable-next-line @typescript-eslint/naming-convention
    const { where, query_string } = this.requestConfigs?.data?.query_configs?.[0] || {};
    const queryString = query_string?.trim?.();
    if (where?.length || !!queryString) {
      return 'search-empty';
    }
    return 'empty';
  }

  @Watch('requestConfigs')
  requestConfigsChange() {
    this.getEventLogs();
  }

  @Emit('conditionChange')
  conditionChange(condition: IWhereItem[]) {
    return condition;
  }

  @Emit('clearSearch')
  clearSearch() {
    return;
  }

  created() {
    this.getEventLogs();
  }

  /**
   * @description 事件日志table表格列配置项
   *
   */
  getTableColumns(): Array<EventExploreTableColumn> {
    const { TIME, CONTENT, LINK, PREFIX_ICON, TEXT } = ExploreTableColumnTypeEnum;
    return [
      {
        id: 'time',
        name: this.$t('时间'),
        type: TIME,
        width: 150,
      },
      {
        id: 'source',
        name: this.$t('事件来源'),
        type: PREFIX_ICON,
        width: 150,
        customHeaderCls: 'explore-table-source-header-cell',
      },
      {
        id: 'event_name',
        name: this.$t('事件名'),
        type: TEXT,
        width: 160,
      },
      {
        id: 'event.content',
        name: this.$t('内容'),
        min_width: 590,
        type: CONTENT,
      },
      {
        id: 'target',
        name: this.$t('目标'),
        type: LINK,
        width: 190,
        fixed: 'right',
      },
    ];
  }

  /**
   * @description: 获取 table 表格数据
   *
   */
  async getEventLogs() {
    const { apiFunc, apiModule, data, loadingType = ExploreTableLoadingEnum.REFRESH } = this.requestConfigs;
    let updateTableDataFn = list => {
      this.tableData.push(...list);
    };

    if (!apiFunc || !apiModule) {
      this.tableData = [];
      return;
    }
    if (loadingType === ExploreTableLoadingEnum.REFRESH) {
      this.tableData = [];
      updateTableDataFn = list => {
        this.tableData = list;
      };
    } else if (!this.tableHasScrollLoading) {
      return;
    }

    this.tableLoading[loadingType] = true;
    const requestParam = {
      ...data,
      offset: this.tableData?.length || 0,
    };

    const res = await (this as any).$api[apiModule][apiFunc](requestParam, {
      needMessage: true,
    }).catch(() => ({ list: [] }));

    this.tableLoading[loadingType] = false;

    updateTableDataFn(res.list);
  }

  /**
   * @description: 根据当前事件类型获取 css 变量（表格行内最左侧的 颜色 和 宽度 ）
   * @param {DimensionsTypeEnum} type 事件类型
   *
   */
  getCssVarsByType(type: DimensionsTypeEnum) {
    return {
      '--table-legend-color': getEventLegendColorByType(type),
      '--table-legend-width': '3px',
    };
  }

  /**
   * @description: 事件目标列 hover 鼠标移入弹出内容详情 popover
   * @param {MouseEvent} e
   * @param detail 事件内容详情
   */
  handleTargetHover(e: MouseEvent, text: string) {
    const content = `
      <div class="explore-target-popover">
          ${text}
      </div>`;
    this.handlePopoverShow(e, content);
  }

  /**
   * @description: 事件内容列 hover 鼠标移入弹出内容详情 popover
   * @param {MouseEvent} e
   * @param detail 事件内容详情
   */
  handleContentHover(e: MouseEvent, detail: Record<string, any>) {
    const createListItem = item => {
      const itemValueDom =
        item?.type === 'link'
          ? `<a
            class='content-item-value-link'
            href=${item.url}
            rel='noreferrer'
            target='_blank'
          >
            ${item.alias || '--'}
          </a>`
          : `<span class="content-item-value">${item.alias || '--'}</span>`;
      return `
      <div class="explore-content-popover-main-item">
        <span class="content-item-key">${item.label}</span>
        <span class="content-item-colon">:</span>
        ${itemValueDom}
      </div>
      `;
    };

    const main = Object.values(detail).map(createListItem).join('');
    const content = `
      <div class="explore-content-popover">
        <div class="explore-content-popover-title">内容 :</div>
        <div class="explore-content-popover-main">
          ${main}
        </div>
      </div>`;
    this.handlePopoverShow(e, content);
  }

  /**
   * @description: 展开
   * @param {MouseEvent} e
   * @param {string} content
   */
  handlePopoverShow(e: MouseEvent, content: string, customOptions = {}) {
    if (this.popoverInstance || this.popoverDelayTimer) {
      this.handlePopoverHide();
    }
    this.popoverInstance = this.$bkPopover(e.currentTarget, {
      content,
      animation: false,
      maxWidth: 'none',
      arrow: true,
      boundary: 'window',
      interactive: true,
      theme: 'explore-content-popover',
      onHidden: () => {
        this.handlePopoverHide();
      },
      ...customOptions,
    });
    const popoverCache = this.popoverInstance;
    this.popoverDelayTimer = setTimeout(() => {
      if (popoverCache === this.popoverInstance) {
        this.popoverInstance?.show?.(0);
      } else {
        popoverCache?.hide?.(0);
        popoverCache?.destroy?.();
      }
    }, 500);
  }

  /**
   * @description: 清除popover
   */
  handlePopoverHide() {
    this.handleClearTimer();
    this.popoverInstance?.hide?.(0);
    this.popoverInstance?.destroy?.();
    this.popoverInstance = null;
  }

  handleClearTimer() {
    this.popoverDelayTimer && clearTimeout(this.popoverDelayTimer);
    this.popoverDelayTimer = null;
  }

  /**
   * @description: 事件表格展开行渲染方法
   * @param scopedParam
   */
  tableExpandSlots(scopedParam) {
    const rowData = scopedParam?.row;
    return (
      <ExploreExpandViewWrapper
        style={this.getCssVarsByType(rowData?.type?.value)}
        data={rowData?.origin_data || {}}
        entitiesMapList={this.entitiesMapList}
        fieldMap={this.fieldMap}
        onConditionChange={this.conditionChange}
      />
    );
  }

  /**
   * @description ExploreTableColumnTypeEnum.TIME 类型时间戳类型表格列渲染方法
   * @param {EventExploreTableColumn} column
   */
  timeColumnFormatter(column) {
    return row => {
      const value = formatTime(+row[column.id].value);
      return (
        <span
          class='explore-time-col explore-overflow-tip-col'
          v-bk-overflow-tips={{ content: value }}
        >
          {value}
        </span>
      );
    };
  }

  /**
   * @description ExploreTableColumnTypeEnum.TEXT 类型文本类型表格列渲染方法
   * @param {EventExploreTableColumn} column
   */
  textColumnFormatter(column: EventExploreTableColumn) {
    return row => {
      const alias = row[column.id].alias;
      return (
        <span
          class='explore-text-col explore-overflow-tip-col'
          v-bk-overflow-tips={{ content: alias }}
        >
          {alias}
        </span>
      );
    };
  }

  /**
   * @description ExploreTableColumnTypeEnum.PREFIX_ICON 类型事件来源表格列渲染方法
   * @param {EventExploreTableColumn} column
   */
  iconColumnFormatter(column: EventExploreTableColumn) {
    return row => {
      const item = row[column.id];
      const { alias, value } = item;

      return (
        <div class='explore-prefix-icon-col '>
          <i class={`source-icon ${SourceIconMap[value]}`} />
          <span
            class='explore-overflow-tip-col'
            v-bk-overflow-tips={{ content: alias }}
          >
            {alias}
          </span>
        </div>
      );
    };
  }

  /**
   * @description ExploreTableColumnTypeEnum.CONTENT 类型事件内容表格列渲染方法
   * @param {EventExploreTableColumn} column
   */
  contentColumnFormatter(column: EventExploreTableColumn) {
    return row => {
      const item = row[column.id];
      const { alias, detail } = item;
      return (
        <div class='explore-content-col'>
          <span class='content-label'>事件内容:</span>
          <span
            class='content-value explore-overflow-tip-col'
            onMouseenter={e => this.handleContentHover(e, detail)}
            onMouseleave={this.handleClearTimer}
          >
            {alias}
          </span>
        </div>
      );
    };
  }

  /**
   * @description ExploreTableColumnTypeEnum.LINK 类型事件来源表格列渲染方法
   * @param {EventExploreTableColumn} column
   */
  linkColumnFormatter(column: EventExploreTableColumn) {
    return row => {
      const item = row[column.id];
      // 当url为空时，使用textColumnFormatter渲染为普通 text 文本样式
      if (!item.url) {
        return this.textColumnFormatter(column)(row);
      }
      return (
        <div class='explore-link-col '>
          <a
            class='explore-overflow-tip-col'
            href={item.url}
            rel='noreferrer'
            target='_blank'
            onMouseenter={e => this.handleTargetHover(e, `点击前往: ${item.scenario || '--'}`)}
            onMouseleave={this.handleClearTimer}
          >
            {item.alias}
          </a>
        </div>
      );
    };
  }

  handleSetFormatter(column: EventExploreTableColumn) {
    switch (column.type) {
      case ExploreTableColumnTypeEnum.TIME:
        return this.timeColumnFormatter(column);
      case ExploreTableColumnTypeEnum.PREFIX_ICON:
        return this.iconColumnFormatter(column);
      case ExploreTableColumnTypeEnum.CONTENT:
        return this.contentColumnFormatter(column);
      case ExploreTableColumnTypeEnum.LINK:
        return this.linkColumnFormatter(column);
      default:
        return this.textColumnFormatter(column);
    }
  }

  transformColumn(column: EventExploreTableColumn) {
    return (
      <bk-table-column
        key={`column_${column.id}`}
        width={column.width}
        column-key={column.id}
        fixed={column.fixed}
        formatter={this.handleSetFormatter(column)}
        label={column.name}
        min-width={column.min_width}
        prop={column.id}
        show-overflow-tooltip={false}
      />
    );
  }

  render() {
    return (
      <div class='event-explore-table'>
        <bk-table
          row-style={e => {
            return this.getCssVarsByType(e?.row?.type?.value);
          }}
          style={{ display: !this.tableLoading[ExploreTableLoadingEnum.REFRESH] ? 'flex' : 'none' }}
          class='explore-table'
          header-cell-class-name={e => {
            const columnKey = e?.column?.columnKey;
            return this.tableColumns.columnForKeyMap?.[columnKey]?.customHeaderCls || '';
          }}
          border={false}
          data={this.tableData}
          outer-border={false}
        >
          <bk-table-column
            width={24}
            scopedSlots={{
              default: this.tableExpandSlots,
            }}
            type='expand'
          />
          {this.tableColumns.columns.map(column => this.transformColumn(column))}
          <EmptyStatus
            slot='empty'
            textMap={{
              empty: this.$t('暂无数据'),
            }}
            type={this.tableEmptyType}
            onOperation={this.clearSearch}
          />
          <div
            style={{ display: this.tableHasScrollLoading ? 'block' : 'none' }}
            class='export-table-loading'
            slot='append'
          >
            <bk-spin
              placement='right'
              size='mini'
            >
              {this.$t('加载中')}
            </bk-spin>
          </div>
        </bk-table>
        <TableSkeleton
          style={{ visibility: this.tableLoading[ExploreTableLoadingEnum.REFRESH] ? 'visible' : 'hidden' }}
          class='explore-table-skeleton'
          type={6}
        />
      </div>
    );
  }
}
