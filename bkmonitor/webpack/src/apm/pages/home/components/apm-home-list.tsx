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
import { Component, Emit, Prop, Provide, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import axios from 'axios';
import { serviceList, serviceListAsync } from 'monitor-api/modules/apm_metric';
import { commonPageSizeGet, commonPageSizeSet } from 'monitor-common/utils';
import { Debounce } from 'monitor-common/utils/utils';
import EmptyStatus from 'monitor-pc/components/empty-status/empty-status';
import TableSkeleton from 'monitor-pc/components/skeleton/table-skeleton';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';
import CommonTable from 'monitor-pc/pages/monitor-k8s/components/common-table';
import FilterPanel, { type IFilterData } from 'monitor-pc/pages/strategy-config/strategy-config-list/filter-panel';
import { NODE_TYPE_ICON } from 'monitor-ui/chart-plugins/utils';

import authorityStore from '../../../store/modules/authority';
import ApmHomeResizeLayout from './apm-home-resize-layout';

import type { IAppListItem } from '../typings/app';
import type { IAPMService } from '../typings/service';
import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';
import type { ICommonTableProps } from 'monitor-pc/pages/monitor-k8s/components/common-table';
import type { IGroupData } from 'monitor-pc/pages/strategy-config/strategy-config-list/group';

import './apm-home-list.scss';
interface IProps {
  appData: Partial<IAppListItem>;
  appName: string;
  authority: boolean;
  authorityDetail: string;
  timeRange?: TimeRangeType;
}

@Component({
  name: 'ApmServiceList',
})
export default class ApmServiceList extends tsc<
  IProps,
  {
    onGoToServiceByLink?: () => void;
    onRouteUrlChange: (params: Record<string, any>) => void;
    onServiceAddSideShow: (v: boolean) => void;
  }
> {
  @Prop() appData: Partial<IAppListItem>;
  @Prop({
    required: true,
    type: String,
  })
  appName: string;
  @Prop() timeRange: TimeRangeType;
  @Prop({ type: Boolean }) authority: boolean;
  @Prop({ type: String }) authorityDetail: string;
  @Ref() mainResize: InstanceType<typeof ApmHomeResizeLayout>;

  /** 搜索关键词 */
  searchKeyWord = '';

  loading = true;

  showFilterPanel = true;

  searchEmpty = false;

  /** 初次请求 */
  firstRequest = true;

  cancelTokenSource = null;

  /** 服务表格数据 */
  tableData: IAPMService[] = [];
  tableColumns: ICommonTableProps['columns'] = [];
  pagination: ICommonTableProps['pagination'] = {
    count: 100,
    current: 1,
    limit: commonPageSizeGet(),
    showTotalCount: true,
  };
  tableSortKey = '';

  /* 左侧统计数据 */
  filterList: IGroupData[] = [];
  checkedFilter: IFilterData[] = [];
  filterCondition = [];
  defaultActiveName = ['category', 'language', 'apply_module', 'have_data'];
  filterShow = true;
  filterLoading = true;

  get isConnecting() {
    return !this.appData.metric_result_table_id && !this.appData.trace_result_table_id;
  }

  @Provide('handleShowAuthorityDetail')
  handleShowAuthorityDetail(actionIds: string | string[]) {
    authorityStore.getAuthorityDetail(actionIds);
  }

  @Watch('appName', { immediate: true })
  onAppNameChange() {
    if (this.appName) {
      this.handleResetRoute();
      this.filterLoading = true;
      this.getServiceList();
    }
  }
  @Watch('timeRange')
  onTimeRangeChange() {
    if (this.appName) {
      this.getServiceList();
    }
  }
  @Emit('routeUrlChange')
  onRouteUrlChange() {
    return {
      current: String(this.pagination.current),
      limit: String(this.pagination.limit),
      filters: JSON.stringify(this.filterCondition),
      service_keyword: this.searchKeyWord,
      app_name: this.appName,
      from: this.timeRange[0],
      to: this.timeRange[1],
    };
  }
  handleGotoAppOverview() {
    this.$router.push({
      name: 'application',
      query: {
        'filter-app_name': this.appName,
      },
    });
  }
  handleGoToAppConfig() {
    this.$router.push({
      name: 'application-config',
      params: {
        appName: this.appName,
      },
    });
  }
  handleGotoServiceApply() {
    this.$emit('serviceAddSideShow', true);
    // this.$router.push({
    //   name: 'service-add',
    //   params: {
    //     appName: this.appName,
    //   },
    // });
  }
  handleResetRoute() {
    const { current, limit, filters, service_keyword } = this.$route.query;
    this.pagination.current = Number(current) || 1;
    this.pagination.limit = Number(limit) || commonPageSizeGet();
    this.searchKeyWord = service_keyword as string;
    try {
      this.filterCondition = filters ? JSON.parse(filters as string) : [];
    } catch {
      this.filterCondition = [];
    }
    if (this.firstRequest) {
      this.checkedFilter = this.filterCondition.map(item => {
        const { id, name, data } = this.filterList.find(panel => item.key === panel.id) || {
          id: item.key,
          name: item.key,
          data: [],
        };
        let values = [];
        /**
         * 因为有些筛选项需要等待列表接口请求完成后才能知道，所以这里需要判断一下
         * 如果该筛选项没有子级，就暂时使用Url传递的值构造一个id为值的对象,等待接口返回后在进行处理
         */
        if (data?.length) {
          values = data.reduce((values, cur) => {
            if (Array.isArray(cur.children)) {
              values.push(...cur.children.filter(child => item.value.includes(child.id)));
            } else {
              item.value.includes(cur.id) && values.push(cur);
            }
            return values;
          }, []);
        } else if (typeof item.value === 'string') {
          return {
            id: item.value,
            name: item.value,
          };
        } else if (Array.isArray(item.value)) {
          values = item.value.map(id => ({
            id,
            name: id,
          }));
        }
        return {
          id: id,
          name,
          values,
        };
      });
    }
  }

  /**
   * @description: 筛选面板勾选change事件
   * @param {*} data
   * @return {*}
   */
  handleSearchSelectChange(data = []) {
    this.checkedFilter = data;
    this.filterCondition = this.checkedFilter
      ?.map(({ id, values }) => {
        const valueIds = values.map(({ id }) => id);
        return {
          key: id,
          value: valueIds,
        };
      })
      .filter(({ value }) => value.length > 0);
    this.pagination.current = 1;
    this.getServiceList();
  }

  /* 筛选展开收起 */
  handleHidePanel() {
    this.mainResize.setCollapse(!this.showFilterPanel);
  }
  /**
   * @description 条件搜索
   * @param value
   */
  @Debounce(300)
  handleSearchCondition() {
    this.getServiceList();
  }

  /**
   *@description 获取服务列表
   */
  async getServiceList() {
    this.loading = true;
    const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
    const params = {
      app_name: this.appName,
      start_time: startTime,
      end_time: endTime,
      filter: 'all',
      sort: this.tableSortKey,
      field_conditions: this.filterCondition,
      check_filter_dict: {},
      page: this.pagination.current,
      page_size: this.pagination.limit,
      keyword: this.searchKeyWord,
      condition_list: [],
      view_mode: 'page_home',
    };
    this.cancelTokenSource?.cancel?.();
    this.cancelTokenSource = axios.CancelToken.source();
    const { columns, data, total, filter } = await serviceList(params, { cancelToken: this.cancelTokenSource.token })
      .catch(() => {
        this.filterLoading = false;
        return {
          columns: [],
          data: [],
          total: 0,
          filter: [],
        };
      })
      .finally(() => {
        this.loading = false;
      });
    this.tableData = data;
    this.tableColumns = columns;
    this.pagination.count = total;
    // 只需要首次给值
    if (this.filterLoading) {
      this.filterList = filter;
    }
    this.loadAsyncData(startTime, endTime);
    this.onRouteUrlChange();
    this.firstRequest = false;
  }

  loadAsyncData(startTime: number, endTime: number) {
    // const fields = (this.tableColumns || []).filter(col => col.asyncable).map(val => val.id);
    const fields = (this.tableColumns || [])
      .filter(col => col.asyncable)
      .reduce((fieldArr, val) => {
        // 指标、日志、调用链、性能分析列的入参，统一使用data_status
        if (['log_data_status', 'metric_data_status', 'trace_data_status', 'profiling_data_status'].includes(val.id)) {
          !fieldArr.includes('data_status') && fieldArr.push('data_status');
        } else {
          fieldArr.push(val.id);
        }
        return fieldArr;
      }, []);
    const services = (this.tableData || []).map(d => d.service_name.value);
    const valueTitleList = this.tableColumns.map(item => ({
      id: item.id,
      name: item.name,
    }));
    for (const field of fields) {
      // data_status，增加filter_keys选项获取左侧筛选 数据上报、数据状态 的全量数据
      const filter_keys = field === 'data_status' ? ['have_data', 'apply_module'] : [];
      serviceListAsync(
        {
          app_name: this.appName,
          start_time: startTime,
          end_time: endTime,
          column: field, // 指标、日志、调用链、性能分析列的入参，统一使用data_status
          service_names: services,
          filter_keys,
        },
        { cancelToken: this.cancelTokenSource.token }
      ).then(serviceData => {
        this.mapAsyncData(serviceData, field, valueTitleList);
      });
    }
  }

  /**
   * 合并列表左侧筛选数据
   * @param filterDataPart1 // serviceList接口返回的筛选数据（不含数据上报、数据状态）
   * @param filterDataPart2 // serviceListAsync接口返回的筛选数据（数据上报、数据状态）
   */
  async mergeServiceFilterData(filterDataPart2) {
    const filterDataPart1 = JSON.parse(JSON.stringify(this.filterList));
    this.filterList = [...filterDataPart1, ...filterDataPart2].map(item => {
      let newData = item.data;
      // if (item.id === 'category') {
      newData = item.data.map(dataItem => ({
        ...dataItem,
        icon: NODE_TYPE_ICON[dataItem.id] ?? '',
        cssIcon: item.id === 'have_data' ? `have_data-${dataItem.id}` : undefined,
      }));
      // }
      return {
        ...item,
        data: newData,
      };
    });
    this.filterLoading = false;
  }
  getServiceListAsyncChartData(
    startTime: number,
    endTime: number,
    field: string,
    services: string[],
    valueTitleList: { id: string; name: string }[]
  ) {
    return serviceListAsync({
      app_name: this.appName,
      start_time: startTime,
      end_time: endTime,
      column: field,
      service_names: services,
    })
      .then(serviceData => {
        this.mapAsyncData(serviceData, field, valueTitleList);
      })
      .catch(() => {
        const item = this.tableColumns.find(col => col.id === field);
        item.asyncable = false;
      });
  }
  mapAsyncData(serviceData, field, valueTitleList) {
    const dataMap = {};
    if (serviceData.data) {
      field === 'data_status' && this.mapArrayAsyncData(serviceData);
      for (const serviceItem of serviceData.data) {
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
    field !== 'data_status' && this.renderTableBatchByBatch(field, dataMap);
  }

  // data_status(指标、日志、调用链、性能分析)特殊处理
  mapArrayAsyncData(serviceData) {
    const fields = serviceData.data.length
      ? Object.keys(serviceData.data[0]).filter(key => key !== 'service_name')
      : [];
    const newData = fields.map(field => {
      const data = serviceData.data.reduce((res, service) => {
        if (service[field]) {
          res[service.service_name] = { icon: service[field].icon };
        }
        return res;
      }, {});
      return { field, data };
    });
    for (const item of newData) {
      this.renderTableBatchByBatch(item.field, item.data);
    }
    if (this.filterLoading) {
      const { filter: filterDataPart2 = [] } = serviceData;
      this.mergeServiceFilterData(filterDataPart2);
    }
  }
  /**
   *
   * @description: 按需渲染表格数据
   * @param field 字段名
   * @param dataMap 数据map
   */
  renderTableBatchByBatch(field: string, dataMap: Record<string, any> = {}) {
    const setData = (currentIndex = 0) => {
      let needBreak = false;
      if (currentIndex <= this.tableData.length && this.tableData.length) {
        const endIndex = Math.min(currentIndex + 1, this.tableData.length);
        for (let i = currentIndex; i < endIndex; i++) {
          const item = this.tableData[i];
          item[field] = dataMap[String(item.service_name.value || '')] || null;
          needBreak = i === this.tableData.length - 1;
        }
        if (!needBreak) {
          setTimeout(() => {
            window.requestAnimationFrame(() => {
              setData(endIndex);
            });
          }, 300);
        } else {
          this.tableColumns.find(col => col.id === field).asyncable = false;
        }
      }
    };
    // const item = this.tableColumns.find(col => col.id === field);
    // item.asyncable = false;
    this.tableColumns.find(col => col.id === field).asyncable = false;
    setData(0);
  }

  /**
   * @description 收藏
   * @param val
   */
  handleCollect(item: Record<string, any>) {
    const apis = item.api.split('.');
    (this as any).$api[apis[0]][apis[1]](item.params).then(() => {
      item.is_collect = !item.is_collect;
    });
  }

  /**
   * @description 表格排序
   * @param param0
   * @param item
   */
  handleSortChange({ prop, order }) {
    switch (order) {
      case 'ascending':
        this.tableSortKey = prop;
        break;
      case 'descending':
        this.tableSortKey = `-${prop}`;
        break;
      default:
        this.tableSortKey = undefined;
    }
    this.pagination.current = 1;
    this.getServiceList();
  }

  /**
   * @description 表格页数事件
   * @param page
   */
  handlePageChange(page: number) {
    this.pagination.current = page;
    this.getServiceList();
  }

  /**
   * @description 表格页码事件
   * @param limit
   */
  handlePageLimitChange(limit: number) {
    this.pagination.limit = limit;
    commonPageSizeSet(limit);
    this.getServiceList();
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

  handleGotoService(item) {
    this.$emit('goToServiceByLink', item);
  }

  /**
   * @description 清空搜索条件
   * @param value
   * @param values
   */
  handleClearSearch() {
    this.searchKeyWord = '';
    this.checkedFilter = [];
    this.filterCondition = [];
    this.pagination.current = 1;
    this.getServiceList();
  }
  render() {
    return (
      <div class='apm-home-list'>
        <div class='header'>
          {this.filterLoading || !this.appName ? (
            <div
              style='height: 32px; width: 240px'
              class='skeleton-element'
            />
          ) : (
            <div class='header-left'>
              <span>{this.appData?.app_alias}</span>
              {this.appName ? <span>({this.appName})</span> : null}
            </div>
          )}
          {this.filterLoading || !this.appData ? (
            <div style='display: flex;'>
              <div
                style='height: 32px; width: 88px'
                class='skeleton-element mr-8'
              />
              <div
                style='height: 32px; width: 88px'
                class='skeleton-element'
              />
            </div>
          ) : (
            <div class='header-right'>
              <div
                v-bk-tooltips={{
                  content: this.$t('接入中'),
                  disabled: !this.isConnecting,
                }}
              >
                <bk-button
                  class={['header-btn', { disabled: !this.authority }]}
                  v-authority={{ active: !this.authority }}
                  disabled={this.isConnecting}
                  theme='primary'
                  text
                  onClick={() =>
                    this.authority ? this.handleGotoAppOverview() : this.handleShowAuthorityDetail(this.authorityDetail)
                  }
                >
                  <i class='icon-monitor icon-chakan' />
                  {this.$t('应用详情')}
                </bk-button>
              </div>
              <div
                v-bk-tooltips={{
                  content: this.$t('接入中'),
                  disabled: !this.isConnecting,
                }}
              >
                <bk-button
                  class={['header-btn', { disabled: !this.authority }]}
                  v-authority={{ active: !this.authority }}
                  disabled={this.isConnecting}
                  text
                  onClick={() =>
                    this.authority ? this.handleGoToAppConfig() : this.handleShowAuthorityDetail(this.authorityDetail)
                  }
                >
                  <i class='icon-monitor icon-shezhi1' />
                  {this.$t('应用配置')}
                </bk-button>
              </div>
            </div>
          )}
        </div>
        <div class='main'>
          <ApmHomeResizeLayout
            ref='mainResize'
            class='main-left'
            initSideWidth={200}
            maxWidth={300}
            minWidth={150}
            onCollapseChange={val => {
              this.showFilterPanel = val;
            }}
          >
            <div
              class={['main-left-filter']}
              slot='aside'
            >
              <FilterPanel
                class='filter-panel-apm'
                checkedData={this.checkedFilter}
                data={this.filterList}
                defaultActiveName={this.defaultActiveName}
                show={this.filterShow}
                showSkeleton={this.filterLoading}
                on-change={this.handleSearchSelectChange}
              >
                <div
                  class='filter-panel-header'
                  slot='header'
                  onClick={this.handleHidePanel}
                >
                  <span class='folding'>
                    <i class='icon-monitor icon-gongneng-shouqi' />
                  </span>
                  <span class='title'>{this.$t('筛选')}</span>
                </div>
              </FilterPanel>
            </div>
            <div class={['main-left-table', { 'filter-panel-hide': !this.showFilterPanel }]}>
              <div class='app-list-content'>
                <div class='app-list-content-top'>
                  {this.filterLoading || !this.appData ? (
                    <div
                      style='height: 32px; width: 88px'
                      class='skeleton-element'
                    />
                  ) : (
                    <div class='app-list-bts'>
                      <span
                        class='bts-filter-wrap'
                        v-show={!this.showFilterPanel}
                        onClick={this.handleHidePanel}
                      >
                        <i class='icon-monitor icon-gongneng-shouqi bts-filter-hd' />
                        <span class='bts-filter-bd'>{this.$t('筛选')}</span>
                      </span>

                      <bk-button
                        class={[{ disabled: !this.authority }]}
                        ext-cls='app-add-btn-style'
                        v-authority={{ active: !this.authority }}
                        theme='primary'
                        onClick={() =>
                          this.authority
                            ? this.handleGotoServiceApply()
                            : this.handleShowAuthorityDetail(this.authorityDetail)
                        }
                      >
                        <span class='app-add-btn'>
                          <i class='icon-monitor icon-mc-add app-add-icon' />
                          <span>{this.$t('接入服务')}</span>
                        </span>
                      </bk-button>
                    </div>
                  )}

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
                      key={this.appName}
                      class='item-expand-wrap'
                    >
                      {
                        <div class='expand-content'>
                          {!this.loading ? (
                            <CommonTable
                              style={{ display: !this.loading ? 'block' : 'none' }}
                              class='apm-index-table'
                              checkable={false}
                              columns={this.tableColumns}
                              data={this.tableData}
                              hasColumnSetting={false}
                              pagination={this.pagination}
                              scrollLoading={false}
                              onCollect={val => this.handleCollect(val)}
                              onGoToServiceByLink={val => this.handleGotoService(val)}
                              onLimitChange={this.handlePageLimitChange}
                              onPageChange={this.handlePageChange}
                              onSortChange={val => this.handleSortChange(val as any)}
                            >
                              <EmptyStatus
                                slot='empty'
                                textMap={{
                                  empty: this.$t('暂无数据'),
                                }}
                                type={this.searchKeyWord || this.filterCondition?.length ? 'search-empty' : 'empty'}
                                onOperation={() => this.handleClearSearch()}
                              />
                            </CommonTable>
                          ) : (
                            <TableSkeleton
                              class='table-skeleton'
                              type={5}
                            />
                          )}
                        </div>
                      }
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </ApmHomeResizeLayout>
        </div>
      </div>
    );
  }
}
