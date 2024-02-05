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

import { Component, Emit, Inject, InjectReactive, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { Debounce, deepClone, random } from '../../../../../monitor-common/utils/utils';
import StatusTab from '../../../../../monitor-ui/chart-plugins/plugins/table-chart/status-tab';
import { IViewOptions, PanelModel } from '../../../../../monitor-ui/chart-plugins/typings';
import { ITableDataItem } from '../../../../../monitor-ui/chart-plugins/typings/table-chart';
import { VariablesService } from '../../../../../monitor-ui/chart-plugins/utils/variable';
import type { TimeRangeType } from '../../../../components/time-range/time-range';
import { handleTransformToTimestamp } from '../../../../components/time-range/utils';
import { IFilterDict, IQueryData, IQueryDataSearch, ITableColumn } from '../../typings';
import {
  filterSelectorPanelSearchList,
  transformConditionValueParams,
  transformQueryDataSearch,
  updateBkSearchSelectName
} from '../../utils';
import { type ShowModeType } from '../common-page-new';
import CommonTable from '../common-table';
import SortTool from '../sort-tool/sort-tool';

import './common-select-table.scss';

// 表格是否显示表头宽度临界值 侧栏宽度：280，内边距：32 （280 - 32 = 248）;
const SHOW_HEADER_LIMIT_WIDTH = 248;
// 置顶排序列的宽度
const TABLE_COLUMN_SORT_WIDTH = 120;
// 外容器内边距
const CONTAINER_PADDING_WIDTH = 32;

interface IPagination {
  current: number;
  count: number;
  limit: number;
}

interface ISortFieldItem {
  id: string;
  name: string;
}

interface ICommonSelectTableProps {
  // panel实例
  panel: PanelModel;
  // 视图数据参数配置
  viewOptions: IViewOptions;
  // 是否为数据总览模式
  isOverview: boolean;
  // dashboard 面板是否有overview_panels配置
  hasOverviewPanels?: boolean;
  // 展示模式 纯列表 list 纯视图 dashboar  列表和纯视图混合模式 default
  showMode?: ShowModeType;
  // 容器宽度
  width?: number;
}

interface ICommonSelectTableEvent {
  // 详情选中列表行数据触发
  onChange: IViewOptions;
  // 概览/详情 切换
  onOverviewChange: boolean;
  // 标题修改触发
  onTitleChange: string;
}

@Component
export default class CommonSelectTable extends tsc<ICommonSelectTableProps, ICommonSelectTableEvent> {
  /** panel实例 */
  @Prop({ type: Object }) panel: PanelModel;
  /** 视图数据参数配置 */
  @Prop({ type: Object }) viewOptions: IViewOptions;
  /** 是否为数据总览模式 */
  @Prop({ type: Boolean, default: true }) isOverview: boolean;
  /** dashboard 面板是否有overview_panels配置 */
  @Prop({ type: Boolean, default: false }) hasOverviewPanels: boolean;
  /** 展示模式 纯列表 list 纯视图 dashboar  列表和纯视图混合模式 default */
  @Prop({ required: true, default: 'default' }) showMode: ShowModeType;
  /** 容器宽度 */
  @Prop({ default: 200, type: Number }) width: number;

  /** 时间范围 */
  @InjectReactive('timeRange') readonly timeRange!: TimeRangeType;
  /** 搜索条件 */
  @InjectReactive('queryData') readonly queryData!: IQueryData;
  /** 侧栏搜索条件更新url方法 */
  @Inject('handleUpdateQueryData') handleUpdateQueryData: (queryData: IQueryData) => void;

  @Ref() selectTablePanel: HTMLElement;
  @Ref() tableRef: CommonTable;

  /** 概览 icon */
  overviewIcon = require('../../../../static/images/svg/overview.svg') // eslint-disable-line
  /** 面板 loading */
  loading = false;
  /** 滚动加载loading */
  isScrollLoading = false;
  /** 表格是否出现滚动条 */
  isOverflowTable = false;
  /** 是否重新排序 */
  isSortRefresh = false;
  /** 记录初始化状态 */
  isInit = false;
  /** 刷新 key */
  refreshKey = random(8);
  /** 表格第一列最大宽度 */
  firstColMaxWidth = 0;
  /** 排序字段 */
  sortKey = '';
  /** Input 搜索关键字 */
  keyword = '';
  localKeyword = '';
  /** 监听容器大小变化实例 */
  resizeObserver = null;
  /** 状态筛选 */
  currentStatus = 'all';
  /** 表格列数据项过滤 */
  filterDict: IFilterDict = {};
  /** url带filter-变量集合 用于匹配选中项参数 */
  filterFields: IFilterDict = {};
  /** 是否显示表头 */
  showHeader = true;
  /** 状态可选项 */
  statusList = [];
  /** 搜索条件可选项 */
  conditionList = [];
  /** 搜索条件 - 后端搜索 */
  searchCondition = [];
  /** 表格数据 */
  tableData = [];
  /** 概览数据 */
  overviewData: ITableDataItem | null = {};
  /** 排序字段 */
  sortFields: ISortFieldItem[] = [];
  /** 表格列配置 */
  columns: ITableColumn[] = [];
  /** 表格分页信息 */
  pagination: IPagination = {
    current: 1,
    count: 0,
    limit: 50
  };

  // scoped 变量
  get scopedVars() {
    return {
      ...(this.viewOptions || {}),
      ...(this.viewOptions?.filters || {}),
      ...(this.viewOptions?.current_target || [])
    };
  }
  // active id
  get activeId() {
    return this.isOverview ? '' : this.panel.targets?.[0]?.handleCreateItemId?.(this.scopedVars, false) || '';
  }
  /** 过滤已选的搜索条件 */
  get currentConditionList() {
    return filterSelectorPanelSearchList(this.conditionList, this.searchCondition);
  }
  /** 是否启用状态筛选组件 */
  get isEnableStatusFilter() {
    return this.panel.options?.selector_list?.status_filter ?? false;
  }
  /** 是否启用排序组件 */
  get isEnableSort() {
    return this.panel.options?.selector_list?.field_sort ?? false;
  }
  /** 默认排序字段 */
  get defaultSortField() {
    // 链接自带排序
    return this.queryData?.sort || this.panel.options.selector_list?.default_sort_field || '';
  }
  /** 是否出现底部滚动加载提示 */
  get showScrollLoadBar() {
    const { count, limit } = this.pagination;
    return count > limit;
  }

  created() {
    /** 首次加载 如果是非概览且路由包含变量 则设置filterFields参数 */
    if (!this.isOverview && Object.keys(this.viewOptions.filters)?.length) {
      this.filterFields = this.viewOptions.filters;
    }
  }

  mounted() {
    if (this.defaultSortField) this.sortKey = this.defaultSortField;
    this.getPanelData();
  }

  beforeDestroy() {
    this.resizeObserver?.unobserve(this.selectTablePanel);
  }

  @Watch('timeRange')
  // 数据时间间隔
  handleTimeRangeChange() {
    this.handleResetTable();
  }
  @Watch('queryData.selectorSearch', { immediate: true })
  conditionChange(search: IQueryDataSearch) {
    this.searchCondition = updateBkSearchSelectName(this.conditionList, transformQueryDataSearch(search || []));
  }
  @Watch('queryData.keyword', { immediate: true })
  handleKeywordChange(val: string) {
    this.localKeyword = val || '';
    this.keyword = val || '';
  }
  @Watch('queryData.filter', { immediate: true })
  handleStatusChange(val: string) {
    this.currentStatus = val || 'all';
  }
  @Watch('queryData.sort', { immediate: true })
  handleSortFieldChange(val: string) {
    this.sortKey = val;
  }
  @Watch('queryData.filterDict', { immediate: true })
  handleFilterDictChange(val: IFilterDict) {
    if (val && Object.keys(val).length) {
      this.filterDict = val;
    }
  }

  @Emit('overviewChange')
  handleOverviewChange(v) {
    return v;
  }
  @Emit('titleChange')
  handleTitleChange(title: string) {
    return title.toString();
  }

  /** 表格动态样式 */
  getTableClasses() {
    return {
      'select-table': true,
      'show-header': this.showHeader && this.overviewData,
      'hide-overview': this.showHeader && !this.overviewData,
      'select-overview': this.isOverview,
      'scroll-body': this.isOverflowTable
    };
  }
  /** 获取表格数据 */
  async getPanelData() {
    // 是否滚动加载
    const isScrollLoad = this.pagination.current > 1;
    if (!isScrollLoad) this.loading = true;
    const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
    const { current, limit } = this.pagination;
    let params = {
      condition_list: transformConditionValueParams(this.searchCondition),
      start_time: startTime,
      end_time: endTime,
      keyword: this.keyword,
      sort: this.sortKey,
      page: current,
      page_size: limit,
      status: this.currentStatus,
      filter_dict: this.filterDict
    };
    if (Object.keys(this.filterFields).length) {
      params = Object.assign({}, params, {
        filter_fields: this.filterFields
      });
    }
    const variablesService = new VariablesService(this.scopedVars);
    const promiseList = this.panel.targets.map(item =>
      (this as any).$api[item.apiModule]
        [item.apiFunc]({
          ...variablesService.transformVariables(item.data),
          ...params
        })
        .then(data => {
          const list = data.data || [];
          if (this.isSortRefresh || !this.isInit) {
            // 切换了排序 表格列发生了变化 表格需要重新渲染
            this.refreshKey = random(8);
          }
          this.columns = data.columns || [];
          this.overviewData = this.hasOverviewPanels ? data.overview_data : null;
          this.pagination.count = data.total || 0;
          this.conditionList = data.condition_list || [];
          this.searchCondition = updateBkSearchSelectName(this.conditionList, this.searchCondition);
          this.statusList = data.filter || [];
          this.sortFields = data.sort || [];
          this.firstColMaxWidth = data.columns[0]?.max_width ?? 0;
          if (Object.keys(this.filterDict).length) {
            const newColumns = this.columns.map(col => ({
              ...col,
              filter_value: this.filterDict[col.id] ? this.filterDict[col.id] : []
            }));
            this.columns = [...newColumns];
          }
          return list?.map?.(set => {
            const id = item.handleCreateItemId(set, true) || set.id;
            return {
              ...set,
              id,
              name: set.name || id
            };
          });
        })
    );
    const [data] = await Promise.all(promiseList).catch(() => [[]]);

    if (isScrollLoad) {
      // 分页加载 追加表格数据
      this.tableData.push(...data);
    } else {
      this.$el.querySelector('.bk-table-body-wrapper').scrollTop = 0;
      this.tableData.splice(0, this.tableData.length, ...data);
      this.getCheckedItemName();
      this.resizeObsever();
      this.loading = false;
      this.isSortRefresh = false;
      this.isInit = true;
      this.filterFields = {};
    }
  }
  /** 选中设置 */
  getCheckedItemName() {
    if (this.isOverview) {
      this.handleTitleChange('概览');
    } else {
      const checkedItem = this.tableData.find(item => item.id === this.activeId);
      const title = checkedItem ? checkedItem.name : this.tableData[0]?.name || '';
      if (checkedItem) {
        this.handleSelectDetail(checkedItem);
      }

      if (!!title) {
        this.handleTitleChange(typeof title === 'object' ? title.value : title);
        this.tableRef?.handleSelectedRow(checkedItem);
      }

      if (!checkedItem) {
        this.handleSelectDetail(this.tableData[0]); // 默认选中第一条
        this.$nextTick();
        this.tableRef?.handleSelectedRow(this.tableData[0]);
      }
    }
  }
  /** 重新请求表格数据 */
  handleResetTable() {
    this.pagination.current = 1;
    this.getPanelData();
  }
  /** 监听容器大小变化 */
  resizeObsever() {
    this.resizeObserver = new ResizeObserver(entries => {
      const rect = entries[0].contentRect;
      const tableBody = this.$el.querySelector('.bk-table-body-wrapper');
      this.isOverflowTable = tableBody.scrollHeight > tableBody.clientHeight;
      // 动态控制表头显示隐藏
      this.showHeader = rect.width > this.firstColMaxWidth - CONTAINER_PADDING_WIDTH;

      /** 带筛选的表头 由于自定义表头造成样式的冲突需要做调整 */
      this.$el.querySelectorAll('.bk-table-column-filter-trigger').forEach(el => {
        const preElem = el.previousElementSibling;
        const iconWidth = preElem.querySelector('.header-pre-icon')?.clientWidth || 0;
        const textWidth = preElem.querySelector('.column-header-text')?.clientWidth || preElem?.clientWidth || 0;
        el.setAttribute('style', `left:${iconWidth + textWidth + 20}px`);
      });
    });
    this.resizeObserver?.observe(this.selectTablePanel);
  }
  /** conditionList 搜索 */
  handleSearch() {
    this.handleResetTable();
    const selectorSearch = transformConditionValueParams(this.searchCondition);
    this.handleUpdateQueryData({
      ...this.queryData,
      selectorSearch
    });
  }
  /** Input 搜索 */
  @Debounce(300)
  handleLocalSearch(v: string) {
    this.keyword = v;
    this.handleResetTable();
  }
  handleInputSearch(v: string) {
    if (v !== this.keyword) {
      this.handleLocalSearch(v);
      this.handleUpdateQueryData({
        ...this.queryData,
        keyword: v
      });
    }
  }
  /** 刷新 */
  handleRefresh() {
    this.handleResetTable();
  }
  /** 筛选组件 */
  handleStatusFilter(v) {
    this.currentStatus = v;
    this.handleResetTable();
    this.handleUpdateQueryData({
      ...this.queryData,
      filter: v
    });
  }
  /** 表格排序 */
  handleChangeOrder(sortKey) {
    this.isSortRefresh = true;
    this.sortKey = sortKey;
    this.handleResetTable();
    this.handleUpdateQueryData({
      ...this.queryData,
      sort: sortKey
    });
  }
  /** 选中概览 */
  handleOverviewTitle(e: MouseEvent) {
    this.tableRef?.handleOverviewRow(e);
  }
  /** 选中表格单项详情 */
  handleSelectDetail(data) {
    if (data) {
      const viewOptions = deepClone(this.viewOptions) as IViewOptions;
      const value = this.panel.targets[0].handleCreateFilterDictValue(data, true);
      viewOptions.filters = { ...(value || {}) };
      viewOptions.compares = {
        targets: []
      };
      this.handleTitleChange(typeof data.name === 'object' ? data.name.value : data.name);
      this.$emit('change', viewOptions);
      if (this.isOverview) this.handleOverviewChange(false);
    }
  }
  /** 表格滚动到底部 */
  async handleScrollEnd() {
    if (this.isScrollLoading || this.tableData.length >= this.pagination.count) return;

    this.isScrollLoading = true;
    this.pagination.current += 1;
    await this.getPanelData();
    this.isScrollLoading = false;
  }
  /** 设置排序字段 */
  handleSortChange({ prop, order }: any) {
    switch (order) {
      case 'ascending':
        this.sortKey = prop;
        break;
      case 'descending':
        this.sortKey = `-${prop}`;
        break;
      default:
        this.sortKey = undefined;
    }
    this.handleResetTable();
  }
  /** 设置表头列过滤字段 */
  handleFilterChange(filters: IFilterDict) {
    this.filterDict = filters;
    this.handleResetTable();
    this.handleUpdateQueryData({
      ...this.queryData,
      filterDict: filters
    });
  }
  /** 动态计算赋值表格第一列的宽度 */
  handleColumnWidth(maxVal: number) {
    // 表格实际宽度
    const mainWidth = this.width - CONTAINER_PADDING_WIDTH;

    // 第一列宽度等于 最大宽度
    // 情况一：当有置顶排序组件 表格宽度大于最大宽度与第二列（排序列）的和 因为需要在可视范围保持第二列（排序列）可见
    // 情况二：当无置顶排序组件 表格宽度大于最大宽度
    const maxContentWidth = this.isEnableSort ? maxVal + TABLE_COLUMN_SORT_WIDTH : maxVal;
    if (mainWidth > maxContentWidth) return maxVal;

    // 第一列宽度等于 默认宽度
    if (mainWidth < SHOW_HEADER_LIMIT_WIDTH) return SHOW_HEADER_LIMIT_WIDTH;

    // 第一列宽度 大于默认且小于最大宽度
    // 情况一：当有置顶排序组件
    // 情况二：当无置顶排序组件 第一列宽度等于表格宽度
    if (this.isEnableSort) {
      // 实际设置宽度需包含第二列（排序列）可见 但第一列不能小于默认宽度
      const validWidth = mainWidth - TABLE_COLUMN_SORT_WIDTH;
      return validWidth < SHOW_HEADER_LIMIT_WIDTH ? SHOW_HEADER_LIMIT_WIDTH : validWidth;
    }
    return mainWidth;
  }

  render() {
    const handleLoadBarText = () => {
      if (this.isScrollLoading) {
        return (
          <span>
            <bk-spin
              class='loading-icon'
              size='mini'
              theme='default'
              icon='circle-2-1'
            />
            {this.$t('加载中...')}
          </span>
        );
      }

      const remainCount = this.pagination.count - this.tableData.length;
      if (remainCount) return `${this.$t('剩余 {n} 条数据', { n: remainCount })}`;

      return this.$t('已加载全部数据');
    };

    return (
      <div
        ref='selectTablePanel'
        class='common-select-table'
        v-bkloading={{ isLoading: this.loading }}
      >
        <div class={['list-header', { 'flex-header': this.width > 1000 }]}>
          <div class='search-bar'>
            {this.conditionList.length ? (
              <bk-search-select
                placeholder={this.$t('搜索')}
                vModel={this.searchCondition}
                show-condition={false}
                data={this.currentConditionList}
                show-popover-tag-change={false}
                onChange={this.handleSearch}
              />
            ) : (
              <bk-input
                v-model={this.localKeyword}
                right-icon='bk-icon icon-search'
                placeholder={this.$t('搜索')}
                clearable={true}
                onEnter={this.handleInputSearch}
                onBlur={this.handleInputSearch}
                onClear={this.handleInputSearch}
              />
            )}
            <bk-button
              class='reflesh-btn'
              onClick={this.handleRefresh}
            >
              <i class='icon-monitor icon-shuaxin'></i>
            </bk-button>
          </div>
          <div class='tools-bar'>
            {this.isEnableStatusFilter && (
              <StatusTab
                class='status-tab'
                // style={`min-width:${this.isEnableSort ? '242px' : ''}`}
                v-model={this.currentStatus}
                statusList={this.statusList}
                onChange={this.handleStatusFilter}
              />
            )}
            {this.isEnableSort && (
              <SortTool
                sortFields={this.sortFields}
                defaultField={this.defaultSortField}
                onChange={this.handleChangeOrder}
              />
            )}
          </div>
        </div>
        <div class='list-wrapper'>
          {!this.showHeader && !!this.overviewData && (
            <div
              class={['overview-title', { 'is-active': this.isOverview }]}
              onClick={e => this.handleOverviewTitle(e)}
            >
              <img
                src={this.overviewIcon}
                alt=''
              />
              <span>{`${this.panel?.title}${this.$t('概览')}`}</span>
            </div>
          )}
          <CommonTable
            ref='tableRef'
            key={this.refreshKey}
            class={this.getTableClasses()}
            defaultSize='small'
            height='100%'
            data={this.tableData}
            overviewData={this.overviewData}
            columns={this.columns}
            pagination={null}
            checkable={false}
            stripe={true}
            highlightCurrentRow={true}
            showHeader={this.showHeader}
            hasColnumSetting={this.showHeader && this.showMode === 'list'}
            onSwitchOverview={this.handleOverviewChange}
            onScrollEnd={this.handleScrollEnd}
            onSortChange={this.handleSortChange}
            onFilterChange={this.handleFilterChange}
            onRowClick={this.handleSelectDetail}
            calcColumnWidth={this.handleColumnWidth}
          ></CommonTable>
        </div>
        {this.showScrollLoadBar && <div class='scroll-load-bar'>{handleLoadBarText()}</div>}
      </div>
    );
  }
}
