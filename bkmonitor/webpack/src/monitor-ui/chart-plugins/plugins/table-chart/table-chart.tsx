/* eslint-disable array-callback-return */
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
import { Component, Emit, Ref, Watch } from 'vue-property-decorator';
import { ofType } from 'vue-tsx-support';
import dayjs from 'dayjs';
import { Debounce } from 'monitor-common/utils/utils';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';
import CommonTable from 'monitor-pc/pages/monitor-k8s/components/common-table';
import {
  IFilterDict,
  IMenuItem,
  IQueryData,
  ITabelDataFilterItem,
  ITableColumn,
  ITableFilterItem,
  ITablePagination
} from 'monitor-pc/pages/monitor-k8s/typings';
import {
  filterSelectorPanelSearchList,
  transformConditionValueParams,
  transformQueryDataSearch,
  updateBkSearchSelectName
} from 'monitor-pc/pages/monitor-k8s/utils';

import ChartHeader from '../../components/chart-title/chart-title';
import { PanelModel } from '../../typings';
import { ITableDataItem } from '../../typings/table-chart';
import { reviewInterval, setStyle } from '../../utils';
import { VariablesService } from '../../utils/variable';
import { CommonSimpleChart } from '../common-simple-chart';

import StatusTab from './status-tab';

import './table-chart.scss';

const STORE_KEY_PREFIX = 'table_chart_store_key_'; /** 图表缓存前缀 */

export enum TABLE_CHART_TYPE {
  TABLE = 'table',
  FIELD = 'field'
}

interface INumberChartProps {
  panel: PanelModel;
}
interface ITableChartEvents {
  onChangeHeight?: (v: number) => number;
}
@Component
// eslint-disable-next-line max-len
export class TableChart extends CommonSimpleChart {
  @Ref() scrollRef: HTMLElement;
  empty = true;
  emptyText = '';
  /** 状态 */
  status = 'all';
  /** 图表数据 */
  tableData: ITableDataItem[] = [];
  /** 概览数据 */
  overviewData: ITableDataItem = null;

  /** 表格列数据 */
  columns: ITableColumn[] = [];

  /** 分页数据 */
  pagination: ITablePagination = {
    current: 1,
    count: 0,
    limit: 10,
    showTotalCount: true
  };
  sortKey = '';
  keyword = '';

  /** 过滤条件 */
  filterList: ITableFilterItem[] = [];
  /** search-select可选项数据 */
  conditionOptions = [];
  conditionList = [];
  // 表格列数据项过滤
  filterDict: IFilterDict = {};
  // checkbox filter
  checkFilterList: ITabelDataFilterItem[] = [];
  checkedFilter: string[] = [];

  /** 过滤已选得搜索条件 */
  get currentConditionList() {
    return filterSelectorPanelSearchList(this.conditionList, this.conditionOptions);
  }

  /** 是否需要展示标题栏 */
  get hasTitle() {
    return this.panel.options?.table_chart?.need_title ?? false;
  }

  /** 是否需要表格筛选tab */
  get needFilters() {
    return this.panel.options?.table_chart?.need_filters || false;
  }

  /** 是否需要更新表格搜索条件到url */
  get needQueryUpdateUrl() {
    return this.panel.options?.table_chart?.query_update_url || false;
  }

  created() {
    if (this.keyword === '') {
      this.keyword = this.$route?.query?.queryString || '';
    }
  }
  /** 搜索框类型 */
  get searchType() {
    return this.panel.options?.table_chart?.search_type || 'input';
  }

  /** 是否接口自带全部选项 */
  get hasAllFilter() {
    return this.filterList.find(item => item.id === 'all');
  }

  /** 是否需要点击展开内容 */
  get showExpand() {
    return this.panel.options?.table_chart?.show_expand ?? false;
  }
  /** 显示json格式数据的key */
  get jsonViewerDataKey() {
    return this.panel.options?.table_chart?.json_viewer_data_key ?? null;
  }
  /** json格式数据为空时提示内容 */
  get jsonViewerDataEmptyText() {
    return this.panel.options?.table_chart?.json_viewer_data_empty_text ?? window.i18n.tc('数据为空');
  }
  @Watch('queryData', { immediate: true })
  queryDataChange(queryData: IQueryData) {
    this.conditionList = updateBkSearchSelectName(this.conditionOptions, transformQueryDataSearch(queryData.search));
    // this.status = queryData.filter || 'all';
    // this.keyword = queryData.keyword || '';
    // this.pagination.current = queryData.page || 1;
    // this.pagination.limit = queryData.pageSize;
    // this.checkedFilter = queryData.checkboxs || [];
  }

  /** 更新表格搜索条件到url */
  handleUpdateQueryDataProxy() {
    // const { current, limit } = this.pagination;
    // const queryData: IQueryData = {
    //   page: current,
    //   pageSize: limit,
    //   filter: this.status,
    //   keyword: this.keyword,
    //   search: transformConditionValueParams(this.conditionList),
    //   checkboxs: this.checkedFilter
    // };
    // this.handleUpdateQueryData(queryData);
  }

  /**
   * @description: 获取图表数据
   */
  @Debounce(200)
  async getPanelData(start_time?: string, end_time?: string) {
    this.beforeGetPanelData(start_time, end_time);
    this.handleLoadingChange(true);
    if (this.needQueryUpdateUrl) {
      this.handleUpdateQueryDataProxy();
    }
    this.emptyText = window.i18n.tc('加载中...');
    try {
      this.unregisterOberver();
      const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
      const params = {
        start_time: start_time ? dayjs.tz(start_time).unix() : startTime,
        end_time: end_time ? dayjs.tz(end_time).unix() : endTime
      };
      const interval = reviewInterval(
        this.viewOptions.interval,
        params.end_time - params.start_time,
        this.panel.collect_interval
      );
      const variablesService = new VariablesService({
        ...this.viewOptions,
        interval
      });
      const promiseList = this.panel.targets
        .filter(item => item.dataType === TABLE_CHART_TYPE.TABLE)
        .map(item =>
          (this as any).$api[item.apiModule]
            [item.apiFunc](
              variablesService.transformVariables(
                {
                  ...item.data,
                  ...params,
                  filter: this.status === 'all' || !this.needFilters ? '' : this.status,
                  sort: this.sortKey,
                  filter_dict: this.filterDict,
                  check_filter_dict:
                    this.checkedFilter?.reduce((pre, cur) => {
                      pre[cur] = true;
                      return pre;
                    }, {}) || undefined,
                  page: this.pagination.current,
                  page_size: this.pagination.limit,
                  keyword: this.keyword,
                  condition_list: transformConditionValueParams(this.conditionList),
                  view_options: {
                    ...this.viewOptions
                  }
                },
                {
                  ...this.viewOptions.filters,
                  ...(this.viewOptions.filters?.current_target || {}),
                  ...this.viewOptions,
                  ...this.viewOptions.variables,
                  interval
                }
              ),
              { needMessage: false }
            )
            .then(({ columns, data, total, filter, condition_list, overview_data, check_filter = [] }) => {
              this.filterList = filter ?? [];
              this.tableData = data || [];
              this.columns = columns || [];
              this.conditionOptions = condition_list || [];
              this.conditionList = updateBkSearchSelectName(this.conditionOptions, this.conditionList, true, true);
              this.overviewData = overview_data;
              // this.pagination.limit = 10;
              this.pagination.count = total || 0;
              if (filter) {
                this.filterActive = filter[0].id;
                this.filterList = filter;
              }
              this.checkFilterList = check_filter;

              const asyncFields = this.columns.filter(col => col.asyncable).map(val => val.id);
              if (asyncFields.length) {
                // 存在异步获取字段
                this.getAsyncData(asyncFields, params.start_time, params.end_time);
              }
              this.clearErrorMsg();
              return true;
            })
            .catch(error => {
              this.handleErrorMsgChange(error.msg || error.message);
            })
        );
      const res = await Promise.all(promiseList).catch(() => false);
      if (res) {
        this.inited = true;
        this.empty = false;
        this.emptyText = window.i18n.tc('查无数据');
      } else {
        this.emptyText = window.i18n.tc('查无数据');
        this.empty = true;
      }
    } catch (e) {
      this.empty = true;
      this.emptyText = window.i18n.tc('出错了');
      console.error(e);
    }
    this.handleLoadingChange(false);
  }

  handleTimeRangeChange() {
    this.pagination.current = 1;
    this.getPanelData();
  }

  /** 异步获取部分列字段 */
  getAsyncData(fields: string[], start_time, end_time) {
    this.$nextTick();
    fields.forEach(field => {
      const variablesService = new VariablesService({ ...this.viewOptions });
      const params = { start_time, end_time };

      this.panel.targets
        // 根据 queryData 的 data_tyep = field 和 async_columns 匹配当前异步字段的请求target
        .filter(
          item => item.dataType === TABLE_CHART_TYPE.FIELD && item.options?.table_chart?.async_columns?.includes(field)
        )
        .map(item => {
          const asyncDictKey = item.options?.table_chart?.async_dict_key ?? '';
          const asyncConfig = this.panel.options?.table_chart?.async_config?.[asyncDictKey];
          const {
            async_field_key: fieldKey,
            async_field_request_name: fieldRequestName,
            async_field: asyncField
          } = asyncConfig;
          const dataMap = this.tableData.map(val => {
            if (!val[asyncField]) return null;
            if (typeof val[asyncField] === 'object' && val[asyncField].value) return val[asyncField].value;
            return val[asyncField];
          });
          (this as any).$api[item.apiModule]
            [item.apiFunc](
              variablesService.transformVariables(
                {
                  ...item.data,
                  ...params,
                  [fieldKey]: field,
                  [fieldRequestName]: dataMap
                },
                {
                  ...this.viewOptions.filters,
                  ...(this.viewOptions.filters?.current_target || {}),
                  ...this.viewOptions,
                  ...this.viewOptions.variables
                }
              ),
              { needMessage: false }
            )
            .then(res => {
              // 组合结果 以键值对形式组合字段值
              const resultMap = res.reduce((pre, cur) => {
                if (!pre[cur[asyncField]]) {
                  // eslint-disable-next-line no-param-reassign
                  pre[cur[asyncField]] = cur[field];
                }
                return pre;
              }, {});

              // 异步数据回填
              const newData = this.tableData.map(data => {
                const fieldVal =
                  typeof data[asyncField] === 'object' && data[asyncField].value
                    ? resultMap[data[asyncField].value]
                    : resultMap[data[asyncField]];
                return { ...data, [field]: fieldVal };
              });
              this.tableData = [...newData];
            })
            .finally(() => {
              // 取消字段请求 loading 状态
              const newColumns = this.columns.map(col => ({
                ...col,
                asyncable: col.id === field ? false : col.asyncable
              }));
              this.columns = [...newColumns];
            });
        });
    });
  }

  handleMenuToolsSelect(menuItem: IMenuItem) {
    switch (menuItem.id) {
      case 'screenshot': // 保存到本地
        this.handleSaveImage();
        break;
      default:
        break;
    }
  }

  /**
   * @description: 截图处理
   */
  async handleSaveImage() {
    await this.$nextTick();
    /** 存在滚动 */
    if (this.scrollRef.scrollHeight > this.scrollRef.clientHeight) {
      const targetEl = this.$el.cloneNode(true) as HTMLElement;
      const scrollWrap = targetEl.querySelector('.table-chart-contain') as HTMLElement;
      setStyle(targetEl, { height: 'auto' });
      setStyle(scrollWrap, { overflow: 'initial' });
      this.$el.appendChild(targetEl);
      await this.handleStoreImage(this.panel.title, targetEl);
      this.$el.removeChild(targetEl);
    } else {
      this.handleStoreImage(this.panel.title);
    }
  }

  /**
   * @description: 切换分页
   * @param {number} page
   */
  handlePageChange(page: number) {
    this.pagination.current = page;
    this.getPanelData();
  }

  async handleLimitChange(limit: number): Promise<void> {
    this.pagination.current = 1;
    this.pagination.limit = limit;
    await this.getPanelData();
    this.$nextTick(() => {
      const height = 80 + this.$el.querySelector('.common-table').clientHeight;
      this.handleChangeHeight(height);
    });
  }
  handleSortChange({ prop, order }) {
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
    this.getPanelData();
  }
  handleFilterChange(filters: IFilterDict) {
    this.filterDict = filters;
    this.pagination.current = 1;
    this.getPanelData();
  }
  @Debounce(300)
  handleSearchChange(v: string) {
    this.pagination.current = 1;
    this.keyword = v;
    this.getPanelData();
  }
  /* 用于改变panel的高度 */
  @Emit('changeHeight')
  handleChangeHeight(height: number) {
    // 返回高度(px)
    return height;
  }

  /** 切换表格筛选 */
  handleStatusChange() {
    this.pagination.current = 1;
    this.getPanelData();
  }

  /** search select组件搜索 */
  handleConditionChange() {
    this.pagination.current = 1;
    this.getPanelData();
  }

  /* 收藏  */
  handleCollect(val) {
    const apis = val.api.split('.');
    this.$api[apis[0]][apis[1]](val.params).then(() => {
      this.getPanelData();
    });
  }
  handleCheckedFilterChagne(v: string[]) {
    this.checkedFilter = v;
    this.pagination.current = 1;
    this.getPanelData();
  }
  render() {
    return (
      <div class='table-chart-wrap'>
        {this.hasTitle ? (
          <ChartHeader
            class='draggable-handle'
            title={this.panel.title}
            draging={this.panel.draging}
            subtitle={this.panel.subTitle}
            isInstant={this.panel.instant}
            showMore={false}
            onMenuClick={this.handleMenuToolsSelect}
          />
        ) : (
          <div class='draggable-handle drag-area'></div>
        )}
        <div
          class={['table-chart-contain', { 'no-title': !this.hasTitle }]}
          ref='scrollRef'
        >
          {this.columns?.length ? (
            [
              <div class='search-wrapper'>
                {/* eslint-disable-next-line no-nested-ternary */}
                {this.searchType === 'search_select' ? (
                  <bk-search-select
                    v-model={this.conditionList}
                    class='search-wrapper-input'
                    show-condition={false}
                    clearable
                    data={this.conditionOptions}
                    onChange={this.handleConditionChange}
                    onClear={this.handleConditionChange}
                  />
                ) : this.searchType === 'input' ? (
                  <bk-input
                    class='search-wrapper-input'
                    placeholder='搜索'
                    clearable
                    v-model={this.keyword}
                    onEnter={this.handleSearchChange}
                    onClear={() => this.handleSearchChange('')}
                    onChange={this.handleSearchChange}
                    right-icon='bk-icon icon-search'
                  />
                ) : (
                  ''
                )}
                {!!this.checkFilterList?.length && (
                  <bk-checkbox-group
                    class='check-filter-group'
                    value={this.checkedFilter}
                    onChange={this.handleCheckedFilterChagne}
                  >
                    {this.checkFilterList.map(item => (
                      <bk-checkbox
                        value={item.id}
                        key={item.id}
                      >
                        {item.name}
                      </bk-checkbox>
                    ))}
                  </bk-checkbox-group>
                )}
                {this.needFilters && !!this.filterList.length && (
                  <StatusTab
                    class='filter-tab'
                    v-model={this.status}
                    needAll={!this.hasAllFilter}
                    statusList={this.filterList}
                    onChange={this.handleStatusChange}
                  ></StatusTab>
                )}
              </div>,
              <CommonTable
                style='background: #fff;'
                checkable={false}
                data={this.tableData}
                overviewData={this.overviewData}
                columns={this.columns}
                defaultSize='small'
                storeKey={!!this.panel.title ? `${STORE_KEY_PREFIX}${this.panel.title}` : ''}
                paginationType='simple'
                pagination={this.pagination}
                showExpand={this.showExpand}
                jsonViewerDataKey={this.jsonViewerDataKey}
                jsonViewerDataEmptyText={this.jsonViewerDataEmptyText}
                onSortChange={this.handleSortChange}
                // eslint-disable-next-line @typescript-eslint/no-misused-promises
                onLimitChange={this.handleLimitChange}
                onPageChange={this.handlePageChange}
                onCollect={this.handleCollect}
                onFilterChange={this.handleFilterChange}
              />
            ]
          ) : (
            <div class='empty-text'>{this.emptyText}</div>
          )}
        </div>
      </div>
    );
  }
}

export default ofType<INumberChartProps, ITableChartEvents>().convert(TableChart);
