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

import { Component, Emit, Prop, Provide, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { random } from 'monitor-common/utils';

import TableSkeleton from '../../../components/skeleton/table-skeleton';
import { formatTime } from '../../../utils';
import RetrievalEmptyShow from '../../data-retrieval/data-retrieval-view/retrieval-empty-show';
import { APIType, getEventLogs } from '../api-utils';
import {
  type ConditionChangeEvent,
  type DimensionsTypeEnum,
  type EventExploreTableColumn,
  type ExploreEntitiesMap,
  type ExploreFieldMap,
  type ExploreTableRequestParams,
  ExploreSourceTypeEnum,
  ExploreTableColumnTypeEnum,
} from '../typing';
import { type ExploreSubject, ExploreObserver, getEventLegendColorByType } from '../utils';
import ExploreExpandViewWrapper from './explore-expand-view-wrapper';

import type { EmptyStatusType } from '../../../components/empty-status/types';
import type { KVFieldList } from './explore-kv-list';

import './event-explore-table.scss';

/** 检索表格loading类型枚举 */
enum ExploreTableLoadingEnum {
  /** 刷新 -- 显示 骨架屏 效果loading */
  REFRESH = 'refreshLoading',
  /** 滚动 -- 显示 表格底部 loading */
  SCROLL = 'scrollLoading',
}

export interface TableSort {
  order: 'ascending' | 'descending' | null;
  prop: null | string;
}

interface EventExploreTableEvents {
  onClearSearch: () => void;
  onConditionChange: (condition: ConditionChangeEvent) => void;
  onSearch: () => void;
  onSetRouteParams: (otherQuery: Record<string, any>) => void;
  onShowEventSourcePopover: (event: Event) => void;
}

interface EventExploreTableProps {
  /** expand 展开 kv 面板使用 */
  entitiesMapList: ExploreEntitiesMap[];
  eventSourceType?: ExploreSourceTypeEnum[];
  /** expand 展开 kv 面板使用 */
  fieldMap: ExploreFieldMap;
  /** 表格单页条数 */
  limit?: number;
  /** 接口请求配置参数 */
  queryParams: Omit<ExploreTableRequestParams, 'limit' | 'offset'>;
  /** 刷新表格 */
  refreshTable: string;
  /** 滚动事件被观察者实例 */
  scrollSubject: ExploreSubject;
  /** 来源 */
  source: APIType;
  /** 数据总数 */
  total?: number;
}

/**
 * @description 事件来源不同类型所显示的图标 映射
 */
const SourceIconMap = {
  [ExploreSourceTypeEnum.BCS]: 'icon-explore-bcs',
  [ExploreSourceTypeEnum.BKCI]: 'icon-explore-landun',
  [ExploreSourceTypeEnum.HOST]: 'icon-explore-host',
  [ExploreSourceTypeEnum.DEFAULT]: 'icon-explore-default',
};
const SCROLL_ELEMENT_CLASS_NAME = '.event-explore-view-wrapper';
const SCROLL_COLUMN_CLASS_NAME = '.bk-table-fixed-header-wrapper th.is-last';
@Component
export default class EventExploreTable extends tsc<EventExploreTableProps, EventExploreTableEvents> {
  @Ref('tableRef') tableRef: Record<string, any>;

  /** 来源 */
  @Prop({ type: String, default: APIType.MONITOR }) source: APIType;
  /** 接口请求配置参数 */
  @Prop({ type: Object }) queryParams: Omit<ExploreTableRequestParams, 'limit' | 'offset'>;
  /** 数据总数 */
  @Prop({ type: Number, default: 0 }) total: number;
  /** 表格单页条数 */
  @Prop({ type: Number, default: 30 }) limit: number;
  /** expand 展开 kv 面板使用 */
  @Prop({ type: Object, default: () => ({ source: {}, target: {} }) }) fieldMap: ExploreFieldMap;
  /** expand 展开 kv 面板使用 */
  @Prop({ type: Array, default: () => [] }) entitiesMapList: ExploreEntitiesMap[];
  /** 滚动事件被观察者实例 */
  @Prop({ type: Object }) scrollSubject: ExploreSubject;
  /** 刷新表格 */
  @Prop({ type: String, default: random(8) }) refreshTable: string;
  @Prop({ type: Array, default: () => [ExploreSourceTypeEnum.ALL] }) eventSourceType: ExploreSourceTypeEnum[];
  /** table loading 配置*/
  tableLoading = {
    /** table 骨架屏 loading */
    [ExploreTableLoadingEnum.REFRESH]: false,
    /** 表格触底加载更多 loading  */
    [ExploreTableLoadingEnum.SCROLL]: false,
  };
  /** 表格列排序配置 */
  sortContainer: TableSort = {
    /** 排序字段 */
    prop: '',
    /** 排序顺序 */
    order: null,
  };

  /** table 数据 */
  tableData = [];
  /** popover 实例 */
  popoverInstance = null;
  /** popover 延迟打开定时器 */
  popoverDelayTimer = null;
  resizeObserver: ResizeObserver;
  /** 容器滚动表格header固定观察者 */
  scrollHeaderFixedObserver: ExploreObserver = null;
  /** 容器滚动到底部时触发请求观察者 */
  scrollEndObserver: ExploreObserver = null;
  /** 表格logs数据请求中止控制器 */
  abortController: AbortController = null;
  /** 滚动结束后回调逻辑执行计时器  */
  scrollPointerEventsTimer = null;
  /** kv 面板主要是利用接口中 origin_data 作为数据驱动渲染，
   * 所以使用 map 结构并采用 origin_data 作为 key 对处理成 kvField 的数据做一层缓存 */
  kvFieldMap = new WeakMap();

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
    const dataLen = this.tableData?.length ?? 0;
    return dataLen < this.total;
  }

  /** table 空数据时显示样式类型 'search-empty'/'empty' */
  get tableEmptyType(): EmptyStatusType {
    if (this.queryParams) {
      return 'search-empty';
    }
    return 'empty';
  }

  get queryConfig() {
    const query = this.queryParams?.query_configs?.[0] || {};
    return {
      ...query,
      // @ts-ignore
      result_table_id: query?.table,
    };
  }

  @Watch('queryParams')
  queryParamsChange(nVal, oVal) {
    const nQueryConfig = nVal?.query_configs?.[0];
    const oQueryConfig = oVal?.query_configs?.[0];
    if (
      !!oQueryConfig &&
      (nQueryConfig?.table !== oQueryConfig?.table ||
        nQueryConfig?.data_source_label !== oQueryConfig?.data_source_label)
    ) {
      this.handleSortChange();
      this.tableRef?.clearSort?.();
    }
  }

  @Watch('refreshTable')
  commonParamsChange() {
    this.getEventLogs();
  }

  @Emit('conditionChange')
  conditionChange(condition: ConditionChangeEvent) {
    return condition;
  }

  @Provide('refreshQueryFn')
  @Emit('clearSearch')
  clearSearch() {
    return;
  }

  @Emit('search')
  filterSearch() {
    return;
  }

  @Emit('setRouteParams')
  setRouteParams(otherQuery = {}) {
    return otherQuery;
  }

  beforeMount() {
    const { query } = this.$route;
    if (!query?.prop || !query?.order) {
      return;
    }
    this.sortContainer.prop = query?.prop as string;
    this.sortContainer.order = query?.order as 'ascending' | 'descending';
  }

  mounted() {
    this.$nextTick(() => {
      const scrollWrapper = document.querySelector(SCROLL_ELEMENT_CLASS_NAME);
      if (!scrollWrapper) return;
      this.resizeObserver = new ResizeObserver(() => {
        this.$nextTick(() => {
          this.handleHeaderFixedScroll({ target: scrollWrapper } as any);
        });
      });
      this.resizeObserver.observe(scrollWrapper);
      if (this.scrollSubject) {
        this.scrollHeaderFixedObserver = new ExploreObserver(this.handleHeaderFixedScroll.bind(this));
        this.scrollEndObserver = new ExploreObserver(this.handleScroll.bind(this));
        this.scrollSubject.addObserver(this.scrollHeaderFixedObserver);
        this.scrollSubject.addObserver(this.scrollEndObserver);
      }
    });
  }

  beforeDestroy() {
    this.scrollPointerEventsTimer && clearTimeout(this.scrollPointerEventsTimer);
    const scrollWrapper = document.querySelector(SCROLL_ELEMENT_CLASS_NAME);
    if (!scrollWrapper) return;
    this.resizeObserver.unobserve(scrollWrapper);
    if (this.scrollSubject) {
      this.scrollSubject.deleteObserver(this.scrollHeaderFixedObserver);
      this.scrollSubject.deleteObserver(this.scrollEndObserver);
    }
  }

  /**
   * @description: 缓存kv面板处理后的数据
   */
  setKvFieldMap(originData, kvFieldItem: KVFieldList) {
    this.kvFieldMap?.set?.(originData, kvFieldItem);
  }

  /**
   * @description: 表格固定列 header 吸顶效果处理
   *
   */
  handleHeaderFixedScroll(event: Event) {
    const scrollWrapper = event.target as HTMLElement;
    const { top: stickyTop } = scrollWrapper.getBoundingClientRect();
    const thNode = this.$el.querySelector(SCROLL_COLUMN_CLASS_NAME);
    const cell: HTMLDivElement = thNode?.querySelector('.cell');
    const { top, width } = thNode.getBoundingClientRect();
    if (top && top <= stickyTop) {
      cell.classList.add('scroll-fixed');
      cell.style.width = `${width}px`;
      cell.style.top = `${stickyTop}px`;
    } else {
      cell.classList.remove('scroll-fixed');
      cell.style.top = '0px';
    }
  }
  /**
   * @description 滚动触发事件
   * @param {Event} event 滚动事件对象
   *
   */
  handleScroll(event: Event) {
    if (!this.tableData?.length) return;
    if (this.$el) {
      this.updateTablePointEvents('none');
      this.handlePopoverHide?.();
    }
    this.handleScrollToEnd(event.target as HTMLElement);
    this.scrollPointerEventsTimer && clearTimeout(this.scrollPointerEventsTimer);
    this.scrollPointerEventsTimer = setTimeout(() => {
      this.updateTablePointEvents('auto');
    }, 600);
  }

  /**
   * @description: 容器滚动到底部时触发 table 请求
   *
   */
  handleScrollToEnd(target: HTMLElement) {
    if (!this.tableHasScrollLoading) {
      return;
    }
    const { scrollHeight } = target;
    const { scrollTop } = target;
    const { clientHeight } = target;
    const isEnd = !!scrollTop && Math.abs(scrollHeight - scrollTop - clientHeight) <= 1;
    const noScrollBar = scrollHeight <= clientHeight;
    const shouldRequest = noScrollBar || isEnd;

    if (
      !(this.tableLoading[ExploreTableLoadingEnum.REFRESH] || this.tableLoading[ExploreTableLoadingEnum.SCROLL]) &&
      shouldRequest
    ) {
      this.getEventLogs(ExploreTableLoadingEnum.SCROLL);
    }
  }

  updateTablePointEvents(val: 'auto' | 'none') {
    if (this.$el) {
      // @ts-ignore
      this.$el.style.pointerEvents = val;
    }
  }

  /**
   * @description 事件日志table表格列配置项
   *
   */
  getTableColumns(): Array<EventExploreTableColumn> {
    const { TIME, CONTENT, LINK, PREFIX_ICON, TEXT } = ExploreTableColumnTypeEnum;
    const { columns } = this.$route.query;
    let routerColumns = [];
    try {
      if (columns) {
        routerColumns = JSON.parse(decodeURIComponent(columns?.toString() || '[]'));
      }
    } catch {
      routerColumns = [];
    }
    return [
      {
        id: 'time',
        name: this.$t('时间'),
        type: TIME,
        width: 150,
        sortable: true,
      },
      this.source === APIType.APM
        ? {
            id: 'source',
            name: this.$t('事件来源'),
            type: PREFIX_ICON,
            width: 150,
            customHeaderCls: 'explore-table-source-header-cell',
            renderHeader: (column: EventExploreTableColumn) => (
              <div
                class='event-source-header'
                onClick={this.handleShowEventSourcePopover}
              >
                <span class='header-title'>{column.name}</span>
                <i
                  class={[
                    'icon-monitor icon-filter-fill filters',
                    { active: !this.eventSourceType.includes(ExploreSourceTypeEnum.ALL) },
                  ]}
                />
              </div>
            ),
          }
        : undefined,
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
      ...(routerColumns?.map(item => ({
        ...item,
      })) || []),
      {
        id: 'target',
        name: this.$t('目标'),
        type: LINK,
        width: 190,
        fixed: 'right',
      },
    ].filter(Boolean);
  }

  /**
   * @description: 获取 table 表格数据
   *
   */
  async getEventLogs(loadingType = ExploreTableLoadingEnum.REFRESH) {
    if (this.abortController) {
      this.abortController.abort();
      this.abortController = null;
    }
    if (!this.queryParams) {
      this.tableData = [];
      return;
    }
    let updateTableDataFn = list => {
      this.tableData.push(...list);
    };

    if (loadingType === ExploreTableLoadingEnum.REFRESH) {
      this.tableData = [];
      updateTableDataFn = list => {
        this.tableData = list;
      };
    }

    let sort = [];
    const { prop, order } = this.sortContainer || {};
    if (prop && order) {
      sort = [`${order === 'descending' ? '-' : ''}${prop}`];
    }
    this.tableLoading[loadingType] = true;
    const requestParam = {
      ...this.queryParams,
      limit: this.limit,
      offset: this.tableData?.length || 0,
      sort: sort,
    };
    this.abortController = new AbortController();
    const res = await getEventLogs(requestParam, this.source, {
      signal: this.abortController.signal,
    });
    if (res?.isAborted) {
      this.tableLoading[ExploreTableLoadingEnum.SCROLL] = false;
      return;
    }

    this.tableLoading[loadingType] = false;

    updateTableDataFn(res.list);
    requestAnimationFrame(() => {
      // 触底加载逻辑兼容屏幕过大或dpr很小的边际场景处理
      // 由于这里判断是否还有数据不是根据total而是根据接口返回数据是否为空判断
      // 所以该场景处理只能通过多次请求的方案来兼容，不能通过首次请求加大页码的方式来兼容
      // 否则在某些边界场景下会出现首次请求返回的不为空数据已经是全部数据了
      // 还是但未出现滚动条，导致无法触发触底逻辑再次请求接口判断是否已是全部数据
      // 从而导致触底loading一直存在但实际已没有更多数据
      this.handleScrollToEnd(document.querySelector(SCROLL_ELEMENT_CLASS_NAME));
    });
  }

  @Emit('showEventSourcePopover')
  handleShowEventSourcePopover(e: Event) {
    return e;
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
        item?.type === 'link' && item?.url
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

  /**
   * @description: 清除popover延时打开定时器
   *
   */
  handleClearTimer() {
    this.popoverDelayTimer && clearTimeout(this.popoverDelayTimer);
    this.popoverDelayTimer = null;
  }

  /**
   * @description: 事件表格行点击事件
   *
   */
  handleTableRowClick(row, event, column) {
    if (!this.tableRef || column.columnKey === 'target') return;
    this.tableRef.toggleRowExpansion(row);
  }

  /**
   * @description 表格排序
   * @param {string} sortEvent.prop 排序字段名
   * @param {'ascending' | 'descending' | null} sortEvent.order 排序方式
   *
   */
  handleSortChange(sortEvent?: TableSort) {
    let prop = sortEvent?.prop;
    let order = sortEvent?.order;
    if (!prop || !order) {
      prop = '';
      order = null;
    }
    this.sortContainer.prop = prop;
    this.sortContainer.order = order;
    this.setRouteParams({
      prop: prop || '',
      order: order,
    });
    this.getEventLogs();
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
        detailData={rowData?.['event.content']?.detail || {}}
        entitiesMapList={this.entitiesMapList}
        fieldMap={this.fieldMap}
        kvFieldCache={this.kvFieldMap}
        scrollSubject={this.scrollSubject}
        source={this.source}
        onConditionChange={this.conditionChange}
        onUpdateKvFieldCache={this.setKvFieldMap}
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
      const alias = row[column.id]?.alias || row.origin_data?.[column.id];
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
        render-header={column?.renderHeader ? () => column.renderHeader(column) : undefined}
        show-overflow-tooltip={false}
        sortable={column?.sortable && 'custom'}
      />
    );
  }

  render() {
    return (
      <div class='event-explore-table'>
        <bk-table
          ref='tableRef'
          style={{ display: !this.tableLoading[ExploreTableLoadingEnum.REFRESH] ? 'flex' : 'none' }}
          class='explore-table'
          header-cell-class-name={e => {
            const columnKey = e?.column?.columnKey;
            return this.tableColumns.columnForKeyMap?.[columnKey]?.customHeaderCls || '';
          }}
          row-style={e => {
            return this.getCssVarsByType(e?.row?.type?.value);
          }}
          border={false}
          data={this.tableData}
          default-sort={this.sortContainer}
          outer-border={false}
          row-key={row => row._meta.__index + row._meta.__doc_id}
          on-row-click={this.handleTableRowClick}
          on-sort-change={this.handleSortChange}
        >
          <bk-table-column
            width={24}
            scopedSlots={{
              default: this.tableExpandSlots,
            }}
            type='expand'
          />
          {this.tableColumns.columns.map(column => this.transformColumn(column))}
          <RetrievalEmptyShow
            slot='empty'
            emptyStatus={this.tableEmptyType}
            eventMetricParams={this.queryConfig}
            queryLoading={false}
            showType={'event'}
            onClickEventBtn={this.filterSearch}
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
