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
import { Component, Ref, Prop, Emit, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { serviceList, serviceListAsync } from 'monitor-api/modules/apm_metric';
import { Debounce } from 'monitor-common/utils/utils';
import EmptyStatus from 'monitor-pc/components/empty-status/empty-status';
import GuidePage from 'monitor-pc/components/guide-page/guide-page';
import TableSkeleton from 'monitor-pc/components/skeleton/table-skeleton';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';
import CommonTable from 'monitor-pc/pages/monitor-k8s/components/common-table';
import FilterPanel, { type IFilterData } from 'monitor-pc/pages/strategy-config/strategy-config-list/filter-panel';
import introduceData from 'monitor-pc/router/space';

import type { PartialAppListItem } from '../apm-home';
import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';
import type { ICommonTableProps } from 'monitor-pc/pages/monitor-k8s/components/common-table';
import type { IFilterDict, ITablePagination } from 'monitor-pc/pages/monitor-k8s/typings';
import type { IGroupData } from 'monitor-pc/pages/strategy-config/strategy-config-list/group';

import './apm-home-list.scss';
interface IProps {
  appData: PartialAppListItem;
  showGuidePage?: boolean;
  timeRange?: TimeRangeType;
  isRefreshService?: boolean;
}

interface IEvent {
  onHandleToConfig?: (row: PartialAppListItem) => void;
  onLinkToOverview?: (row: PartialAppListItem) => void;
  onHandleConfig?: (id: string, row: PartialAppListItem) => void;
}

interface TableConfigData {
  tableData: ICommonTableProps;
  tableSortKey: string;
  tableFilters: IFilterDict;
}

@Component({})
export default class ApmHomeList extends tsc<IProps, IEvent> {
  @Prop() appData: PartialAppListItem;
  @Prop({ default: false, type: Boolean }) showGuidePage: boolean;
  @Prop() timeRange: TimeRangeType;
  @Prop({ default: false, type: Boolean }) isRefreshService: boolean;
  @Ref() mainResize: any;

  /** 搜索关键词 */
  searchKeyWord = '';
  showFilterPanel = true;
  loading = true;
  searchEmpty = false;

  /** 分页数据 */
  pagination: ITablePagination = {
    current: 1,
    count: 500,
    limit: 10,
    showTotalCount: true,
  };

  /** 服务表格数据 */
  tableConfigData: TableConfigData = {
    tableData: {
      pagination: {
        count: 100,
        current: 1,
        limit: 0,
        showTotalCount: true,
      },
      columns: [],
      data: [],
      checkable: false,
      outerBorder: true,
      scrollLoading: false,
      hasColnumSetting: false,
    },
    tableSortKey: '',
    tableFilters: {},
  };

  /* 左侧统计数据 */
  leftFilter: {
    checkedData: IFilterData[];
    filterList: IGroupData[];
    defaultActiveName: string[];
    show: boolean;
    isShowSkeleton: boolean;
  } = {
    filterList: [],
    checkedData: [],
    defaultActiveName: ['category', 'language', 'apply_module', 'have_data'],
    show: true,
    isShowSkeleton: true,
  };

  @Emit()
  handleEmit(...args: any[]) {
    this.$emit.apply(this, args);
    return args[0];
  }

  @Watch('isRefreshService')
  isRefreshServiceChange(newItems) {
    if (newItems) {
      this.leftFilter.isShowSkeleton = true;
      this.loading = true;
    }
  }

  created() {
    this.getLimitOfHeight();
  }

  get apmIntroduceData() {
    const apmData = introduceData['apm-home'];
    apmData.is_no_source = false;
    apmData.data.buttons[0].url = window.__POWERED_BY_BK_WEWEB__ ? '#/apm/application/add' : '#/application/add';
    return apmData;
  }

  /**
   * @description: 筛选面板勾选change事件
   * @param {*} data
   * @return {*}
   */
  handleSearchSelectChange(data = []) {
    this.leftFilter.checkedData = data;
    this.tableConfigData.tableData.pagination.current = 1;
    this.getServiceList(this.appData, true);
  }

  /* 筛选展开收起 */
  handleHidePanel() {
    this.mainResize.setCollapse();
    const time = this.mainResize.collapsed ? 350 : 0;
    setTimeout(() => {
      this.showFilterPanel = !this.mainResize.collapsed;
    }, time);
  }

  changeCollapse(width: number) {
    if (width < 200) {
      setTimeout(() => {
        this.showFilterPanel = false;
      }, 350);
    }
  }

  /**
   * @description 条件搜索
   * @param value
   */
  @Debounce(300)
  handleSearchCondition() {
    this.searchEmpty = !!this.searchKeyWord;
    this.getServiceList(this.appData, true);
  }

  /**
   *@description 获取服务列表
   *@param appData
   *@param isRefresh
   *@param isAppClick
   */
  getServiceList(appData, isRefresh = false, isAppClick = false) {
    const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
    const {
      tableData: { data },
    } = this.tableConfigData;
    if (data.length && !isRefresh) {
      return;
    }
    // 设置加载状态
    this.loading = true;
    if (isAppClick) this.leftFilter.isShowSkeleton = true;

    serviceList(this.createServiceRequest(appData, startTime, endTime))
      .then(({ columns, data, total, filter }) => {
        this.updateTableData(data, columns, total, filter);
        this.loadAsyncData(appData, data, columns, startTime, endTime);
      })
      .finally(() => {
        this.loading = false;
        this.leftFilter.isShowSkeleton = false;
      });
  }

  createServiceRequest(item, startTime, endTime) {
    const transformedArray = this.leftFilter.checkedData
      ?.map(({ id, values }) => {
        const valueIds = values.map(({ id }) => id);
        return {
          key: id,
          value: valueIds,
        };
      })
      .filter(({ value }) => value.length > 0);
    const { tableSortKey, tableFilters, tableData } = this.tableConfigData;
    const { current, limit } = tableData.pagination;
    return {
      app_name: item.app_name,
      start_time: startTime,
      end_time: endTime,
      filter: 'all',
      sort: tableSortKey,
      filter_dict: tableFilters,
      field_conditions: transformedArray,
      check_filter_dict: {},
      page: current,
      page_size: limit,
      keyword: this.searchKeyWord,
      condition_list: [],
      view_mode: 'page_home',
      view_options: {
        app_name: item.app_name,
        compare_targets: [],
        current_target: {},
        method: 'AVG',
        interval: 'auto',
        group_by: [],
        filters: {
          app_name: item.app_name,
        },
      },
      bk_biz_id: this.$store.getters.bizId,
    };
  }

  updateTableData(data, columns, total, filter) {
    const { tableData } = this.tableConfigData;
    tableData.data = data;
    tableData.columns = columns;
    tableData.pagination.count = total;
    this.leftFilter.filterList = filter;
  }

  loadAsyncData(item, data, columns, startTime, endTime) {
    const fields = (columns || []).filter(col => col.asyncable).map(val => val.id);
    const services = (data || []).map(d => d.service_name.value);
    const valueTitleList = this.tableConfigData.tableData.columns.map(item => ({
      id: item.id,
      name: item.name,
    }));
    for (const field of fields) {
      serviceListAsync(this.createAsyncRequest(item, field, services, startTime, endTime))
        .then(serviceData => {
          this.mapAsyncData(serviceData, field, valueTitleList);
        })
        .finally(() => {
          this.updateColumnAsyncAbleState(field);
        });
    }
  }

  createAsyncRequest(item, field, services, startTime, endTime) {
    return {
      app_name: item.app_name,
      start_time: startTime,
      end_time: endTime,
      column: field,
      service_names: services,
      bk_biz_id: this.$store.getters.bizId,
    };
  }

  mapAsyncData(serviceData, field, valueTitleList) {
    const dataMap = {};
    if (serviceData) {
      for (const serviceItem of serviceData) {
        if (serviceItem.service_name) {
          if (['request_count', 'error_rate', 'avg_duration'].includes(field)) {
            const operationItem = valueTitleList.find(item => item.id === field);
            serviceItem[field].valueTitle = operationItem?.name || null;
            if (field === 'request_count') {
              serviceItem[field].unitDecimal = 0;
            }
          }
          dataMap[String(serviceItem.service_name)] = serviceItem[field];
        }
      }
    }
    this.tableConfigData.tableData.data = this.tableConfigData.tableData.data.map(d => ({
      ...d,
      [field]: dataMap[String(d.service_name.value || '')] || null,
    }));
  }

  updateColumnAsyncAbleState(field) {
    this.tableConfigData.tableData.columns = this.tableConfigData.tableData.columns.map(col => ({
      ...col,
      asyncable: col.id === field ? false : col.asyncable,
    }));
  }

  /**
   * @description 收藏
   * @param val
   */
  handleCollect(val) {
    const apis = val.api.split('.');
    (this as any).$api[apis[0]][apis[1]](val.params).then(() => {
      this.tableConfigData.tableData.pagination.current = 1;
      this.getServiceList(this.appData, true);
    });
  }

  /**
   * @description 表格筛选
   * @param filters
   */
  handleFilterChange(filters: IFilterDict) {
    this.tableConfigData.tableFilters = filters;
    this.tableConfigData.tableData.pagination.current = 1;
    this.getServiceList(this.appData, true);
  }

  /**
   * @description 表格排序
   * @param param0
   * @param item
   */
  handleSortChange({ prop, order }, item) {
    switch (order) {
      case 'ascending':
        item.tableSortKey = prop;
        break;
      case 'descending':
        item.tableSortKey = `-${prop}`;
        break;
      default:
        item.tableSortKey = undefined;
    }
    this.tableConfigData.tableData.pagination.current = 1;
    this.getServiceList(item, true);
  }

  /**
   * @description 表格页数事件
   * @param page
   */
  handlePageChange(page: number) {
    this.tableConfigData.tableData.pagination.current = page;
    this.getServiceList(this.appData, true);
  }

  /**
   * @description 表格页码事件
   * @param limit
   */
  handlePageLimitChange(limit: number) {
    this.tableConfigData.tableData.pagination.limit = limit;
    this.getServiceList(this.appData, true);
  }

  /**
   * @description 动态计算当前每页数量
   */
  getLimitOfHeight() {
    const itemHeight = 54;
    const limit = Math.ceil((window.screen.height - 361) / itemHeight);
    const closestValue = this.findClosestValue(limit, [10, 20, 50, 100]);
    this.tableConfigData.tableData.pagination.limit = closestValue;
  }

  /**
   * @description 找到最接近的值
   * @param value
   * @param values
   */
  findClosestValue(value: number, values: number[]): number {
    return values.reduce((prev, curr) => {
      return Math.abs(curr - value) < Math.abs(prev - value) ? curr : prev;
    });
  }

  /**
   * @description 清空搜索条件
   * @param value
   * @param values
   */
  handleClearSearch() {
    this.searchKeyWord = '';
    this.tableConfigData.tableData.pagination.current = 1;
    this.getServiceList(this.appData, true);
    this.$nextTick(() => {
      this.searchEmpty = false;
    });
  }
  render() {
    return (
      <div class='apm-home-list'>
        <div class='header'>
          <div class='header-left'>
            <span>{this.appData.app_alias}</span>
            {this.appData.app_name ? <span>（{this.appData.app_name}）</span> : null}
          </div>
          <div class='header-right'>
            <bk-button
              class='mr-8'
              theme='primary'
              onClick={(event: Event) => {
                event.stopPropagation();
                this.handleEmit('linkToOverview', this.appData);
              }}
            >
              {this.$t('查看应用')}
            </bk-button>
            <bk-button
              onClick={(event: Event) => {
                event.stopPropagation();
                this.handleEmit('handleToConfig', this.appData);
              }}
            >
              {this.$t('应用配置')}
            </bk-button>
          </div>
        </div>
        <div class='main'>
          <bk-resize-layout
            ref='mainResize'
            class='main-left'
            auto-minimize={200}
            border={false}
            initial-divide={201}
            min={195}
            collapsible
            on-after-resize={this.changeCollapse}
          >
            <div
              class={['main-left-filter']}
              slot='aside'
            >
              <FilterPanel
                checkedData={this.leftFilter.checkedData}
                data={this.leftFilter.filterList}
                defaultActiveName={this.leftFilter.defaultActiveName}
                show={this.leftFilter.show}
                showSkeleton={this.leftFilter.isShowSkeleton}
                on-change={this.handleSearchSelectChange}
              >
                <div
                  class='filter-panel-header'
                  slot='header'
                >
                  <span class='title'>{this.$t('筛选')}</span>
                  <span
                    class='folding'
                    onClick={this.handleHidePanel}
                  >
                    <i class='icon-monitor icon-double-up' />
                  </span>
                </div>
              </FilterPanel>
            </div>
            <div
              class='main-left-table'
              slot='main'
            >
              {this.showGuidePage ? (
                <GuidePage
                  guideData={this.apmIntroduceData}
                  guideId='apm-home'
                />
              ) : (
                <div class='app-list-content'>
                  <div class='app-list-content-top'>
                    <bk-button
                      class={[{ 'ml-16': !this.showFilterPanel }]}
                      theme='primary'
                      outline
                      onClick={(event: Event) => {
                        event.stopPropagation();
                        this.handleEmit('handleConfig', 'accessService', this.appData);
                      }}
                    >
                      <span class='app-add-btn'>
                        <i class='icon-monitor icon-mc-add app-add-icon' />
                        <span>{this.$t('接入服务')}</span>
                      </span>
                    </bk-button>
                    <div class='app-list-search'>
                      <bk-input
                        v-model={this.searchKeyWord}
                        placeholder={this.$t('请输入服务搜索')}
                        right-icon='bk-icon icon-search'
                        clearable
                        show-clear-only-hover
                        on-right-icon-click={this.handleSearchCondition}
                        onChange={this.handleSearchCondition}
                      />
                    </div>
                  </div>
                  <div class='app-right-content'>
                    <div class='app-list-content-data'>
                      <div
                        key={this.appData.application_id}
                        class='item-expand-wrap'
                      >
                        {
                          <div class='expand-content'>
                            {this.tableConfigData.tableData?.data.length || this.loading ? (
                              (() => {
                                if (this.loading) {
                                  return <TableSkeleton class='table-skeleton' />;
                                }
                                return (
                                  <CommonTable
                                    {...{ props: this.tableConfigData.tableData }}
                                    hasColnumSetting={false}
                                    onCollect={val => this.handleCollect(val)}
                                    onFilterChange={val => this.handleFilterChange(val)}
                                    onLimitChange={this.handlePageLimitChange}
                                    onPageChange={this.handlePageChange}
                                    onSortChange={val => this.handleSortChange(val as any, this.appData)}
                                  />
                                );
                              })()
                            ) : (
                              <EmptyStatus
                                textMap={{
                                  empty: this.$t('暂无数据'),
                                }}
                                type={this.searchEmpty ? 'search-empty' : 'empty'}
                                onOperation={() => this.handleClearSearch()}
                              />
                            )}
                          </div>
                        }
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
            <div
              class={['toggle-wrap']}
              slot='collapse-trigger'
              onClick={this.handleHidePanel}
            >
              <div
                class='rotate'
                v-show={!this.showFilterPanel}
              >
                <i class='icon-monitor icon-double-up' />
              </div>
            </div>
          </bk-resize-layout>
        </div>
      </div>
    );
  }
}
