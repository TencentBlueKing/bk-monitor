import { Component, Emit, Inject, InjectReactive, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import dayjs from 'dayjs';
import { connect, disconnect } from 'echarts/core';
import bus from 'monitor-common/utils/event-bus';
import { random } from 'monitor-common/utils/utils';
import loadingIcon from 'monitor-ui/chart-plugins/icons/spinner.svg';
import MiniTimeSeries from 'monitor-ui/chart-plugins/plugins/mini-time-series/mini-time-series';
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
import JsonViewer from 'vue-json-viewer';

import { DEFAULT_TIME_RANGE } from '../../../components/time-range/utils';
import { Storage } from '../../../utils';
import CommonStatus from './common-status/common-status';
import CommonTagList from './common-tag-list/common-tag-list';
import MoreOperate from './more-operate/more-operate';
import TextOverflowCopy from './text-overflow-copy/text-overflow-copy';

import type {
  ColumnSort,
  IFilterDict,
  IFilterItem,
  ITableColumn,
  ITableItem,
  ITablePagination,
  TablePaginationType,
  TableRow,
  TableSizeType,
} from '../typings';

import './common-table.scss';

const HEADER_PRE_ICON_NAME = 'header_pre_icon';
export interface ICommonTableProps {
  // 是否可选择行
  checkable?: boolean;
  // 表格字段集合
  columns?: ITableColumn[];
  // 表格数据
  data?: TableRow[];
  // 表格默认尺寸
  defaultSize?: TableSizeType;
  // 是否显示表格列设置
  hasColumnSetting?: boolean;
  // 表格高度 默认为自动高度  height为Number类型，单位px height为String类型，则高度会设置为 Table 的 style.height
  height?: number | string;
  // 是否高亮当前行
  highlightCurrentRow?: boolean;
  // jsonViewer 数据为空时提示文案
  jsonViewerDataEmptyText?: string;
  // jsonViewer 要展示数据的key showExpand = true生效
  jsonViewerDataKey?: string;
  // 表格loading
  loading?: boolean;
  // 表格最大高度
  maxHeight?: number | string;
  // 表格外边框
  outerBorder?: boolean;
  // 表格概览数据行
  overviewData?: TableRow;
  // 分页设置
  pagination?: ITablePagination;
  // 分页的样式类型
  paginationType?: TablePaginationType;
  scrollLoading?: boolean;
  // 是否可以展开
  showExpand?: boolean;
  // 是否显示表头
  showHeader?: boolean;
  // 是否显示每页个数
  showLimit?: boolean;
  // 设置表头字段 存储到本地localstorage key值 默认不设置
  storeKey?: string;
  // 是否为斑马纹
  stripe?: boolean;
  // 动态计算表格列宽度 需配合max_width属性使用
  calcColumnWidth?: (maxWidth: number) => number;
}
interface ICommonTableEvent {
  // 表头字段设置事件
  onColumnSettingChange: string[];
  // 表格列数据项筛选事件
  onFilterChange: IFilterDict;
  // 页码事件
  onLimitChange: number;
  // 页数事件
  onPageChange: number;
  // 选择行数据事件
  onSelectChange: TableRow[];
  // 排序事件
  onSortChange: { prop: string; sort: ColumnSort };
  onSwitchOverview: boolean;
  // 清空选择行事件
  onClearSelect: () => void;
  // 收藏事件（在外层调用接口）
  onCollect?: (value: ITableItem<'collect'>) => void;
  onRowClick: (row) => void;
  // 固定表头情况下 滚动至底部事件
  onScrollEnd: () => void;
}
@Component
export default class CommonTable extends tsc<ICommonTableProps, ICommonTableEvent> {
  @Inject({
    from: 'handleShowAuthorityDetail',
    default: null,
  })
  handleShowAuthorityDetail;
  @Ref('table') tableRef: any;
  // table loading
  @Prop({ default: false }) loading: boolean;
  // scroll Loading
  @Prop({ default: false }) scrollLoading: boolean;
  // 是否显示表格列设置
  @Prop({ default: true }) hasColumnSetting: boolean;
  // 设置的表格固定列保存在localstorage的key值
  @Prop({ default: '' }) storeKey: string;
  // 表格是否可以设置多选
  @Prop({ default: true }) checkable: boolean;
  // 表格数据
  @Prop({ default: () => [] }) data: TableRow[];
  // 表格概览数据行
  @Prop({ type: Object }) overviewData: TableRow;
  // 表格列设置
  @Prop({ default: () => [] }) columns: ITableColumn[];
  // 表格分页设置
  @Prop({
    default: () => ({
      current: 1,
      count: 100,
      limit: 10,
      showTotalCount: true,
    }),
  })
  pagination: ITablePagination | null;
  // 表格尺寸设置 small medium large
  @Prop({ default: 'medium', type: String }) defaultSize: TableSizeType;
  // 表格分页器类型 normal simple
  @Prop({ default: 'mormal', type: String }) paginationType: TablePaginationType;
  // 是否可以展开（展开数据默认为当前行的json数据）
  @Prop({ default: false, type: Boolean }) showExpand: boolean;
  // 表格外边框
  @Prop({ default: false, type: Boolean }) outerBorder: boolean;
  // 是否显示每页个数
  @Prop({ default: true, type: Boolean }) showLimit: boolean;
  // jsonViewer 要展示数据的key
  @Prop({ type: String }) jsonViewerDataKey: string;
  // jsonViewer 数据为空时提示文案
  @Prop({ type: String }) jsonViewerDataEmptyText: string;
  // 是否为斑马纹
  @Prop({ type: Boolean, default: false }) stripe: boolean;
  // 表格高度
  @Prop({ type: [String, Number] }) height: number | string;
  // 表格最大高度
  @Prop({ type: [String, Number] }) maxHeight: number | string;
  // 是否显示表头
  @Prop({ type: Boolean, default: true }) showHeader: boolean;
  // 是否高亮当前行
  @Prop({ type: Boolean, default: false }) highlightCurrentRow: boolean;
  // 动态计算表格列宽度
  @Prop({ type: Function, default: undefined }) calcColumnWidth: (maxWidth: number) => number;

  // 是否在分屏展示
  @InjectReactive('isSplitPanel') isSplitPanel: boolean;
  // 是否是只读模式
  @InjectReactive('readonly') readonly readonly: boolean;
  @Inject({ from: 'linkSelfClick', default: () => {} }) linkSelfClick: (val: ITableItem<'link'>) => void;
  // 选择行数
  selectedCount = 0;
  // 表格尺寸
  tableSize: TableSizeType = 'medium';
  // 表格渲染key值
  tableKey = random(10);
  // 表格列数据项过滤
  filterDict: IFilterDict = {};
  // 管理localstorage的实例
  storage: Storage = null;

  get tableColumns() {
    // 设置的表格固定列保存在localstorage的key值
    const columnKeysCaches = this.storage.get(this.storeKey) || [];
    return this.columns.map(item => ({
      ...item,
      checked:
        typeof item.checked === 'boolean'
          ? columnKeysCaches?.length
            ? columnKeysCaches.includes(item.id)
            : item.checked
          : true,
      disabled: !!item.disabled,
    }));
  }

  /** 缩略图分组Id枚举 */
  get chartGroupIdsMap() {
    return this.tableColumns.reduce((acc, cur, ind) => {
      if (cur.type === 'datapoints') {
        if (acc[cur.id]) disconnect(acc[cur.id]);
        acc[cur.id] = `${random(8)}_${ind}`;
        connect(acc[cur.id]);
      }
      return acc;
    }, {});
  }

  /** 表格类名 */
  get tableClass() {
    const classNames = [];
    classNames.push(`table-pagination-${this.paginationType}`);
    !this.outerBorder && classNames.push('table-outer-border-none');
    !this.showLimit && classNames.push('table-no-limit');
    return classNames.join(' ');
  }
  /** 是否存在概览数据行 */
  get hasOverviewData() {
    return !!this.overviewData;
  }

  created() {
    this.storage = new Storage();
    this.tableSize = this.defaultSize;
  }

  destroyed() {
    for (const groupId of Object.keys(this.chartGroupIdsMap)) {
      disconnect(groupId);
    }
  }

  // 常用值格式化
  commonFormatter(val: ITableItem<'string'>, column: ITableColumn) {
    if (typeof val !== 'number' && !val) return '--';
    if (typeof val === 'object') {
      return (
        <span class='string-col'>
          {val.icon ? (
            val.icon.length > 30 ? (
              <img
                alt=''
                src={val.icon}
              />
            ) : (
              <i class={['icon-monitor', 'link-icon', val.icon]} />
            )
          ) : (
            ''
          )}
          <TextOverflowCopy val={val?.name || ''} />
        </span>
      );
    }
    return (
      <span class='string-col'>
        <TextOverflowCopy
          isEveryCopy={column.name === 'Span Name'}
          val={val}
        />
      </span>
    );
  }
  // 数字类型
  numberFormatter(val: ITableItem<'number'>) {
    if (typeof val !== 'number' && !val) return '--';
    const isObjectVal = typeof val === 'object';
    return (
      <span style={`color:${isObjectVal && val.color ? val.color : ''}`}>
        {isObjectVal ? `${val.value}${val.unit}` : String(val)}
      </span>
    );
  }
  // 时间格式化
  timeFormatter(time: ITableItem<'time'>) {
    if (!time) return '--';
    if (typeof time !== 'number') return time;
    if (time.toString().length < 13) return dayjs.tz(time * 1000).format('YYYY-MM-DD HH:mm:ss');
    return dayjs.tz(time).format('YYYY-MM-DD HH:mm:ss');
  }
  // list类型格式化
  listFormatter(val: ITableItem<'list'>) {
    const key = random(10);
    let element = null;
    setTimeout(() => {
      try {
        element = document.querySelector(`#${key}`);
      } catch {
        element = undefined;
      }
    }, 300);
    return (
      <div
        id={key}
        class='list-type-wrap'
        v-bk-overflow-tips={{
          content: element,
          allowHTML: true,
          theme: 'light common-table',
        }}
      >
        {val.map((item, index) => (
          <div
            key={`${item}_${index}`}
            class='list-type-item'
          >
            {item}
            {index === val.length - 1 ? undefined : ','}
          </div>
        ))}
      </div>
    );
  }
  // tag类型格式化
  tagFormatter(val: ITableItem<'tag'>) {
    return <CommonTagList value={val} />;
  }
  // key-value类型格式化
  kvFormatter(val: ITableItem<'kv'>) {
    const key = random(10);
    let element = null;
    setTimeout(() => {
      try {
        element = document.querySelector(`#${key}`);
      } catch {
        element = undefined;
      }
    }, 300);
    return (
      <div
        id={key}
        class='tag-column'
        v-bk-overflow-tips={{
          content: element,
          allowHTML: true,
          theme: 'light common-table',
        }}
      >
        {val?.length
          ? val.map((item, index) => (
              <div
                key={index}
                class='tag-item set-item'
              >
                <span
                  key={`key__${index}`}
                  class='tag-item-key'
                >
                  {item.key}
                </span>
                &nbsp;:&nbsp;
                <span
                  key={`val__${index}`}
                  class='tag-item-val'
                >
                  {item.value}
                </span>
              </div>
            ))
          : '--'}
      </div>
    );
  }
  // link格式化
  linkFormatter(column: ITableColumn, val: ITableItem<'link'>, row: TableRow) {
    if (typeof val !== 'number' && !val) return '--';
    const hasPermission = row.permission?.[column.actionId] ?? true;
    return (
      <div
        class={['link-col', { 'disabled-click': !!val?.disabledClick }]}
        v-authority={{ active: !hasPermission }}
        onClick={e => {
          if (val?.disabledClick) {
            return;
          }
          hasPermission ? this.handleLinkClick(val, e) : this.handleShowAuthorityDetail?.(column.actionId);
        }}
      >
        {val.icon ? (
          val.icon.length > 30 ? (
            <img
              alt=''
              src={val.icon}
            />
          ) : (
            <i class={['icon-monitor', 'link-icon', val.icon]} />
          )
        ) : (
          ''
        )}
        {` ${val.display_value || val.value || val?.name || ''}`}
      </div>
    );
  }
  // link格式化
  stackLinkFormatter(column: ITableColumn, val: ITableItem<'stack_link'>, row: TableRow) {
    const hasPermission = row.permission?.[column.actionId] ?? true;
    return (
      <div class='stack-link-col'>
        <div class='stack-link-wrap'>
          <div
            class='link-col stack-link'
            v-authority={{ active: !hasPermission }}
            onClick={e =>
              hasPermission ? this.handleLinkClick(val, e) : this.handleShowAuthorityDetail(column.actionId)
            }
          >
            {val.icon ? (
              val.icon.length > 30 ? (
                <img
                  alt=''
                  src={val.icon}
                />
              ) : (
                <i class={['icon-monitor', 'link-icon', val.icon]} />
              )
            ) : (
              ''
            )}
            <span>{` ${val.value}`}</span>
          </div>
          {val.is_stack && <span class='stack-icon'>{this.$t('堆栈')}</span>}
        </div>
        {val.subtitle && <div class='link-subtitle'>{val.subtitle}</div>}
      </div>
    );
  }
  // 多个link格式化
  linkListFormatter(column: ITableColumn, val: ITableItem<'link_list'>, row: TableRow) {
    const hasPermission = row.permission?.[column.actionId] ?? true;
    return (
      <div class='link-list'>
        {val?.map(item => (
          <div
            key={item.value}
            class='link-col'
            v-authority={{ active: !hasPermission }}
            onClick={e => {
              hasPermission ? this.handleLinkClick(item, e) : this.handleShowAuthorityDetail?.(column.actionId);
            }}
          >
            {item.icon ? (
              <img
                alt=''
                src={item.icon}
              />
            ) : (
              ''
            )}
            {item.value}
          </div>
        ))}
      </div>
    );
  }
  // 关联类型
  relationFormatter(val: ITableItem<'relation'>) {
    return (
      <div class='relation-col'>
        {val.map((item, index) => (
          <span
            key={`${item.name}_${index}`}
            class='relation-col-item'
          >
            {index !== 0 && <span class='icon-monitor icon-back-right' />}
            <span class='label'>{item.label}</span>
            <span class='name'>{item.name}</span>
          </span>
        ))}
      </div>
    );
  }
  // link点击事件
  handleLinkClick(item: ITableItem<'link'>, e: MouseEvent) {
    if (this.readonly) return;
    // 空事件 不做任何操作 允许冒泡
    if (item.target === 'null_event') return;

    e?.stopPropagation?.();
    let urlStr = item.url;
    if (item.syncTime) {
      urlStr += urlStr.indexOf('?') === -1 ? '?' : '&';
      const { from, to } = this.$route.query;
      urlStr += `from=${from || DEFAULT_TIME_RANGE[0]}&to=${to || DEFAULT_TIME_RANGE[1]}`;
    }

    if (item.target === 'self') {
      const { route, href } = this.$router.resolve({
        path: urlStr,
      });
      if (this.isSplitPanel) {
        const url = location.href.replace(location.pathname, '/').replace(location.hash, '') + href;
        window.open(url);
      } else {
        // 跳转路径和当前路径一致，不进行跳转
        if (route.fullPath === this.$route.fullPath) {
          return;
        }
        if (urlStr.startsWith('?')) {
          window.location.href = urlStr;
          // this.$router.push({
          //   path: urlStr,
          // });
          return;
        }
        if (urlStr.startsWith('/service')) {
          this.$emit('goToServiceByLink', item);
        }
        this.$router.push({
          path: `${window.__BK_WEWEB_DATA__?.baseroute || ''}${urlStr}`.replace(/\/\//g, '/'),
        });
        this.linkSelfClick?.(item);
      }
      return;
    }
    if (item.target === 'event') {
      bus.$emit(item.key, item);
    } else {
      window.open(urlStr, random(10));
    }
  }
  // status格式化
  statusFormatter(val: ITableItem<'status'>) {
    return val ? (
      <CommonStatus
        text={val.text}
        tips={val.tips}
        type={val.type}
      />
    ) : (
      '--'
    );
  }
  // progress格式化
  progressFormatter(val: ITableItem<'progress'>) {
    return val ? (
      <div class='common-table-progress'>
        <div class='table-progress-text'>{val.label ?? val.value ?? '--'}</div>
        <bk-progress
          class={['common-progress-color', `color-${val.status}`]}
          percent={Number((val.value * 0.01).toFixed(2)) || 0}
          showText={false}
          size='small'
        />
      </div>
    ) : (
      '--'
    );
  }
  // 作用域插槽类型
  scopedSlotFormatter(val: ITableItem<'scoped_slots'>, row: TableRow, id: string, column: ITableColumn) {
    return (this.$scopedSlots?.[id] || this.$scopedSlots?.[val?.slotId])?.(row, column);
  }
  // 收藏类型
  collectFormatter(val: ITableItem<'collect'>) {
    return (
      <div class='collect-item'>
        {val.is_collect ? (
          <span
            class='icon-monitor icon-mc-collect'
            onClick={() => !this.readonly && this.handleCollect(val)}
          />
        ) : (
          <span
            class='icon-monitor icon-mc-uncollect'
            onClick={() => !this.readonly && this.handleCollect(val)}
          />
        )}
      </div>
    );
  }
  // 更多操作 类型
  moreOperateFormatter(val: ITableItem<'more_operate'>) {
    return val?.length ? (
      <div class='more-operate'>
        <MoreOperate
          options={val}
          onOptionClick={this.handleLinkClick}
        />
      </div>
    ) : (
      '--'
    );
  }

  // data_status 类型
  dataStatusFormatter(value: ITableItem<'data_status'>) {
    const icons = {
      normal: {
        icon: 'icon-mc-check-small',
        text: '',
      },
      no_data: {
        icon: 'icon-tixing',
        text: this.$t('无数据'),
      },
      disabled: {
        icon: 'icon-zhongzhi',
        text: this.$t('未开启'),
      },
    };
    return value?.icon ? (
      <i
        class={`icon-monitor ${icons[value.icon].icon || ''} data_status_column`}
        v-bk-tooltips={{ content: icons[value.icon].text, disabled: !icons[value.icon].text }}
      />
    ) : (
      ''
    );
  }

  // datapoints 类型
  datapointsFormatter(column: ITableColumn, value: ITableItem<'datapoints'>) {
    if (!value?.datapoints?.length) {
      return '--';
    }
    return (
      <MiniTimeSeries
        data={value.datapoints || []}
        disableHover={true}
        groupId={this.chartGroupIdsMap[column.id]}
        lastValueWidth={80}
        unit={value.unit}
        unitDecimal={value?.unitDecimal}
        valueTitle={value.valueTitle}
      />
    );
  }

  @Emit('pageChange')
  handlePageChange(v: number) {
    return v;
  }
  @Emit('limitChange')
  handlePageLimitChange(v: number) {
    return v;
  }
  @Emit('sortChange')
  handleSortChange({ prop, order }) {
    return { prop, order };
  }
  @Emit('selectChange')
  handleSelectChange(selectList: TableRow[]) {
    this.selectedCount = selectList?.length || 0;
    return selectList;
  }
  @Emit('columnSettingChange')
  handleSettingChange({ size, fields }) {
    this.tableSize = size;
    this.tableColumns.forEach(item => (item.checked = fields.some(field => field.id === item.id)));
    const colList = this.tableColumns.filter(item => item.checked || item.disabled).map(item => item.id);
    this.storeKey && this.storage.set(this.storeKey, colList);
    this.tableKey = random(10);
    return colList;
  }
  @Emit('clearSelect')
  handleClearSelected() {
    this?.tableRef?.clearSelection?.();
    this.selectedCount = 0;
  }
  @Emit('collect')
  handleCollect(val: ITableItem<'collect'>) {
    return val;
  }
  @Emit('filterChange')
  handleFilterChange(filters: IFilterItem) {
    Object.keys(filters).forEach(item => {
      if (filters[item].length) {
        this.filterDict[item] = filters[item];
      } else if (this.filterDict[item]) {
        delete this.filterDict[item];
      }
    });
    return this.filterDict;
  }

  @Emit('scrollEnd')
  handleScrollEnd() {}

  @Emit('switchOverview')
  handleSwitchOverview(val: boolean) {
    return val;
  }
  handleOverviewRow(e: MouseEvent) {
    e.stopPropagation();
    this?.tableRef?.setCurrentRow?.();
    this.handleSwitchOverview(true);
  }
  handleSelectedRow(row) {
    this?.tableRef?.setCurrentRow?.(row);
  }
  handleSetFormatter(id: string, row: TableRow) {
    const column = this.columns.find(item => item.id === id);
    if (!column) return '--';
    if (column.asyncable)
      return (
        <img
          class='loading-svg'
          alt=''
          src={loadingIcon}
        />
      ); // 用于异步加载loading
    const value: ITableItem<typeof column.type> = row[id];
    switch (column.type) {
      case 'time':
        return this.timeFormatter(row[id] as ITableItem<'time'>);
      case 'list':
        return this.listFormatter(value as ITableItem<'list'>);
      case 'tag':
        return this.tagFormatter(value as ITableItem<'tag'>);
      case 'kv':
        return this.kvFormatter(value as ITableItem<'kv'>);
      case 'link':
        return this.linkFormatter(column, value as ITableItem<'link'>, row);
      case 'status':
        return this.statusFormatter(value as ITableItem<'status'>);
      case 'progress':
        return this.progressFormatter(value as ITableItem<'progress'>);
      case 'scoped_slots':
        return this.scopedSlotFormatter(value as ITableItem<'scoped_slots'>, row, column.id, column);
      case 'collect':
        return this.collectFormatter(value as ITableItem<'collect'>);
      case 'number':
        return this.numberFormatter(value as ITableItem<'number'>);
      case 'link_list':
        return this.linkListFormatter(column, value as ITableItem<'link_list'>, row);
      case 'stack_link':
        return this.stackLinkFormatter(column, value as ITableItem<'stack_link'>, row);
      case 'relation':
        return this.relationFormatter(value as ITableItem<'relation'>);
      case 'more_operate':
        return this.moreOperateFormatter(value as ITableItem<'more_operate'>);
      case 'data_status':
        return this.dataStatusFormatter(value as ITableItem<'data_status'>);
      case 'datapoints':
        return this.datapointsFormatter(column, value as ITableItem<'datapoints'>);
      default:
        return this.commonFormatter(value as ITableItem<'string'>, column);
    }
  }
  /**
   * 表格头部自定义模板
   * @param column 表格列数据
   * 有概览数据 和 汇聚方法icon时生效
   * @returns vnode
   */
  renderColumnsHeader(column) {
    const headerPreIcon = column[HEADER_PRE_ICON_NAME];
    return (
      <div class={['column-header-wrap', { 'has-pre-icon': !!headerPreIcon }]}>
        <div class='column-header-title'>
          {!!headerPreIcon && <i class={['icon-monitor', 'header-pre-icon', headerPreIcon]} />}
          <div
            class='column-header-text'
            v-bk-overflow-tips
          >
            {column.name}
          </div>
          {!!column.sortable && (
            <span class='column-header-sort'>
              <i class='icon-monitor icon-mc-triangle-down icon-up' />
              <i class='icon-monitor icon-mc-triangle-down icon-down' />
            </span>
          )}
        </div>
        {this.hasOverviewData && (
          <div
            class='column-header-content'
            v-bk-overflow-tips
            onClick={e => this.handleOverviewRow(e)}
          >
            {this.overviewData[column.id] ? this.handleSetFormatter(column.id, this.overviewData) : '-'}
          </div>
        )}
      </div>
    );
  }
  renderRowExpand() {
    return data => {
      // data数据为空则展示提示内容
      if (!!this.jsonViewerDataKey && data.row[this.jsonViewerDataKey] === null) {
        return <span style='color:#c4c6cc'>{this.jsonViewerDataEmptyText}</span>;
      }

      return (
        <JsonViewer
          class='json-viewer-wrap'
          preview-mode={true}
          value={this.jsonViewerDataKey ? data.row[this.jsonViewerDataKey] : data.row}
        />
      );
    };
  }
  transformColumns() {
    const columList = this.tableColumns
      .filter(item => (item.checked || item.disabled) && !(this.readonly && ['operation'].includes(item.id)))
      .map(column => {
        const showOverflowTooltip = ['tag', 'list', 'kv'].includes(column.type)
          ? false
          : (column.showOverflowTooltip ?? true);
        // header-pre-icon
        const headerPreIcon = column[HEADER_PRE_ICON_NAME];
        return (
          <bk-table-column
            key={`column_${column.id}`}
            render-header={
              (this.hasOverviewData || !!headerPreIcon) && column.checked
                ? () => this.renderColumnsHeader(column)
                : column?.renderHeader
                  ? () => column.renderHeader()
                  : undefined
            }
            formatter={(row: TableRow) => this.handleSetFormatter(column.id, row)}
            label={column.name}
            prop={column.id}
            show-overflow-tooltip={showOverflowTooltip}
            {...{
              props: {
                ...column.props,
                ...{
                  fixed: column.fixed,
                  sortable: column.sortable,
                  filters: column.filterable ? column.filter_list : undefined,
                  filteredValue: column.filter_value?.length ? column.filter_value : [],
                  resizable: typeof column.resizable === 'boolean' ? column.resizable : true,
                  width: column.max_width ? this.calcColumnWidth(column.max_width) : column.width,
                  minWidth: column.min_width,
                  columnKey: column.id,
                },
              },
            }}
          />
        );
      });
    if (this.checkable) {
      columList.unshift(
        <bk-table-column
          width='50'
          fixed='left'
          minWidth='50'
          type='selection'
        />
      );
    }
    return columList;
  }
  @Emit('rowClick')
  handleRowClick(row, event) {
    if (this.showExpand) {
      const expandDom = event.path.find(item => item.className.includes('bk-table-row'));
      expandDom.firstChild.querySelector('.bk-table-expand-icon').click();
    }
    this.handleSwitchOverview(false);
    return row;
  }
  render() {
    /** cell 类名 */
    const cellName = ({ column }) => {
      const id = column.property;
      const columnData = this.columns.find(item => item.id === id);
      return columnData?.[HEADER_PRE_ICON_NAME] ? 'has-header-pre-icon' : '';
    };
    /** header cell 类名 */
    const headerCellname = ({ column }) => `${cellName({ column })} ${this.hasOverviewData ? 'overview-header' : ''}`;
    return (
      <div class='common-table'>
        <bk-table
          key={`${this.tableKey}__table`}
          ref='table'
          height={this.height}
          class={this.tableClass}
          v-bkloading={{ isLoading: this.loading, zIndex: 1000 }}
          scroll-loading={{
            isLoading: this.scrollLoading,
            size: 'mini',
            theme: 'info',
            icon: 'circle-2-1',
            placement: 'right',
          }}
          cell-class-name={cellName}
          data={this.data}
          header-border={false}
          header-cell-class-name={headerCellname}
          highlightCurrentRow={this.highlightCurrentRow}
          max-height={this.maxHeight}
          outer-border={this.outerBorder}
          pagination={{ ...this.pagination }}
          showHeader={this.showHeader}
          size={this.tableSize}
          stripe={this.stripe}
          on-filter-change={this.handleFilterChange}
          on-page-change={this.handlePageChange}
          on-page-limit-change={this.handlePageLimitChange}
          on-row-click={this.handleRowClick}
          on-scroll-end={this.handleScrollEnd}
          on-selection-change={this.handleSelectChange}
          on-sort-change={this.handleSortChange}
        >
          {this.$slots.empty && <div slot='empty'>{this.$slots.empty}</div>}
          {this.checkable && this.selectedCount ? (
            <div
              class='table-prepend'
              slot='prepend'
            >
              {this.$slots.prepend || [
                <i
                  key='1'
                  class='icon-monitor icon-hint prepend-icon'
                />,
                <i18n
                  key='2'
                  path='已选择{count}条'
                  tag='span'
                >
                  <span
                    class='table-prepend-count'
                    slot='count'
                  >
                    {this.selectedCount}
                  </span>
                </i18n>,
                <slot
                  key='3'
                  name='select-content'
                />,
                <bk-button
                  key='4'
                  class='table-prepend-clear'
                  slot='count'
                  text={true}
                  theme='primary'
                  onClick={this.handleClearSelected}
                >
                  {this.$t('取消')}
                </bk-button>,
              ]}
            </div>
          ) : undefined}
          {this.showExpand && (
            <bk-table-column
              scopedSlots={{ default: this.renderRowExpand() }}
              type='expand'
            />
          )}
          {this.transformColumns()}
          {this.hasColumnSetting ? (
            <bk-table-column type='setting'>
              <bk-table-setting-content
                key={`${this.tableKey}__settings`}
                class='event-table-setting'
                fields={this.tableColumns}
                label-key='name'
                selected={this.tableColumns.filter(item => item.checked || item.disabled)}
                size={this.tableSize}
                value-key='id'
                on-setting-change={this.handleSettingChange}
              />
            </bk-table-column>
          ) : (
            ''
          )}
        </bk-table>
      </div>
    );
  }
}
