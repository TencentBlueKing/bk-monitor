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

import { Component, Inject, InjectReactive, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { getFunctions } from 'monitor-api/modules/grafana';
import { commonPageSizeGet, commonPageSizeSet, Debounce, random } from 'monitor-common/utils';
import StatusTab from 'monitor-ui/chart-plugins/plugins/table-chart/status-tab';

import AlarmTemplateTable from './components/alarm-template-table/alarm-template-table';
import AlarmTemplateSearch from './components/alarm-templte-search/alarm-template-search';
import BatchOperations from './components/batch-operations/batch-operations';
import EditTemplateSlider from './components/template-form/edit-template-slider';
import {
  ALARM_TEMPLATE_OPTIONS_FIELDS,
  ALARM_TEMPLATE_QUICK_FILTER_LIST,
  AlarmTemplateTypeMap,
  TEMPLATE_DETAILS_ROUTER_QUERY_KEY,
} from './constant';
import {
  destroyAlarmTemplateById,
  fetchAlarmTemplateList,
  getAlarmSelectOptions,
  updateAlarmTemplateByIds,
} from './service';
import TemplateDetails from './template-operate/template-details';
import TemplatePush from './template-operate/template-push';
import { type TDetailsTabValue, detailsTabColumn } from './template-operate/typings';

import type { AlarmDeleteConfirmEvent } from './components/alarm-delete-confirm/alarm-delete-confirm';
import type {
  AlarmListRequestParams,
  AlarmTemplateConditionParamItem,
  AlarmTemplateDetailTabEnumType,
  AlarmTemplateField,
  AlarmTemplateListItem,
  AlarmTemplateOptionsItem,
  AlarmTemplateTypeEnumType,
  BatchOperationTypeEnumType,
} from './typing';
import type { IViewOptions } from 'monitor-ui/chart-plugins/typings';

import './alarm-template.scss';

@Component
export default class AlarmTemplate extends tsc<object> {
  // 同步route query
  @Inject('handleCustomRouteQueryChange') handleCustomRouteQueryChange: (
    customRouteQuery: Record<string, number | string>
  ) => void;

  @InjectReactive('customRouteQuery') customRouteQuery: Record<string, string>;
  @InjectReactive('viewOptions') readonly viewOptions!: IViewOptions;
  /** 自动刷新间隔 */
  @InjectReactive('refreshInterval') refreshInterval: number;
  /** 手动刷新 */
  @InjectReactive('refreshImmediate') refreshImmediate: number;

  /** 下发重新请求接口数据标志 */
  refreshKey = random(8);
  /** 当前页码 */
  current = 1;
  /** 每页条数 */
  pageSize = 50;
  /** 排序字段 */
  sort = '-update_time';
  /** 总条数 */
  total = 0;
  /** 列表请求状态 loading */
  tableLoading = false;
  /** 表格数据 */
  tableData: AlarmTemplateListItem[] = [];
  /** 模板类型快速筛选tab */
  quickStatus = 'all';
  /** 搜索关键字 */
  searchKeyword: AlarmTemplateConditionParamItem[] = [];
  /** 表格已勾选的数据行id */
  selectedRowKeys: AlarmTemplateListItem['id'][] = [];
  /** 候选值映射表 */
  selectOptionsMap: Record<AlarmTemplateField, AlarmTemplateOptionsItem[]> = null;
  /** 数据请求中止控制器 */
  abortController: AbortController = null;

  editTemplateId = null;
  editTemplateShow = false;
  /** 编辑模板场景 */
  editTemplateSliderScene: 'clone' | 'edit' = 'edit';

  /** 模板详情侧栏 */
  templateDetailObj = {
    show: false,
    tabActive: detailsTabColumn.basic as TDetailsTabValue,
    params: {},
  };

  templatePushObj = {
    show: false,
    params: {},
  };

  /** 函数列表 */
  metricFunctions = [];
  /** 自动刷新定时器 */
  refreshIntervalInstance = null;

  /** 告警列表接口请求参数 */
  get requestParam() {
    const conditions = [...this.searchKeyword];
    if (this.quickStatus !== 'all') {
      conditions.push({
        key: 'type',
        value: [this.quickStatus],
      });
    }
    const param = {
      refreshKey: this.refreshKey,
      app_name: this.viewOptions.filters?.app_name,
      conditions,
      page: this.current,
      page_size: this.pageSize,
      order_by: this.sort ? [this.sort] : [],
      simple: false,
    };

    delete param.refreshKey;
    return param as unknown as AlarmListRequestParams;
  }

  /** 自动刷新间隔 */
  @Watch('refreshInterval')
  handleRefreshIntervalChange(v: number) {
    if (this.refreshIntervalInstance) {
      window.clearInterval(this.refreshIntervalInstance);
    }
    if (v == null || v <= 0) return;
    this.refreshIntervalInstance = window.setInterval(() => {
      this.getQueryTemplateList();
    }, this.refreshInterval);
  }

  /** 手动刷新 */
  @Watch('refreshImmediate')
  handleRefreshImmediateChange() {
    this.getQueryTemplateList();
  }

  /**
   * @description 获取告警列表数据
   */
  @Debounce(200)
  @Watch('requestParam')
  async getQueryTemplateList() {
    this.abortRequest();
    this.tableLoading = true;
    this.abortController = new AbortController();
    const { templateList, isAborted, total } = await fetchAlarmTemplateList(this.requestParam, {
      signal: this.abortController.signal,
    });
    if (isAborted) {
      return;
    }
    await this.getSelectOptions();
    this.tableData = templateList;
    this.total = total;
    this.tableLoading = false;
    this.selectedRowKeys = [];
  }
  /** 获取函数列表 */
  async handleGetMetricFunctions() {
    this.metricFunctions = await getFunctions().catch(() => []);
  }

  created() {
    this.pageSize = commonPageSizeGet();
    this.getRouterParams();
  }

  mounted() {
    this.handleGetMetricFunctions();
    const detailsId = this.$route.query?.[TEMPLATE_DETAILS_ROUTER_QUERY_KEY];
    if (detailsId) {
      this.handleShowDetail({ id: Number(detailsId), sliderActiveTab: 'base_info' });
    }
  }

  /**
   * @description 中止数据请求
   */
  abortRequest() {
    if (!this.abortController) return;
    this.abortController.abort();
    this.abortController = null;
  }

  /**
   * @description 获取路由参数
   */
  getRouterParams() {
    const { quickStatus = 'all', searchKeyword = '[]', sort = '-update_time' } = this.customRouteQuery;
    this.quickStatus = quickStatus;
    this.sort = sort;
    try {
      this.searchKeyword = JSON.parse(searchKeyword);
    } catch (_error) {
      this.searchKeyword = [];
    }
  }

  /**
   * @description 缓存条件参数知路由
   */
  setRouterParams(otherParams: Record<string, any> = {}) {
    const query = {
      ...this.customRouteQuery,
      quickStatus: this.quickStatus,
      searchKeyword: JSON.stringify(this.searchKeyword),
      sort: this.sort,
      ...otherParams,
    };

    this.handleCustomRouteQueryChange(query);
  }

  /**
   * @description 获取搜索选择器候选值选项数据
   */
  async getSelectOptions() {
    const result = await getAlarmSelectOptions({
      app_name: this.viewOptions.filters?.app_name,
      fields: ALARM_TEMPLATE_OPTIONS_FIELDS,
    });
    this.selectOptionsMap = result || {};
  }

  /**
   * @description 模板类型快捷筛选值改变后回调
   * @param {AlarmTemplateTypeEnumType | 'all'} status 当前选中的模板类型快捷筛选值
   */
  handleQuickStatusChange(status: 'all' | AlarmTemplateTypeEnumType) {
    this.quickStatus = status;
    this.handleCurrentPageChange(1);
    this.setRouterParams();
  }
  /**
   * @description 批量操作按钮点击事件
   * @param {BatchOperationTypeEnumType} operationType 批量操作类型
   */
  handleBatchOperationClick(operationType: BatchOperationTypeEnumType) {
    this.handleBatchUpdate(this.selectedRowKeys, { is_auto_apply: operationType === 'auto_apply' });
  }

  /**
   * @description 筛选值改变后回调（作用于 表格表头筛选 & 顶部筛选searchInput框）
   * @param {AlarmTemplateConditionParamItem[]} keyword 筛选值改变后的值
   **/
  handleSearchChange(keyword: AlarmTemplateConditionParamItem[]) {
    this.handleCurrentPageChange(1);
    this.searchKeyword = keyword;
    this.setRouterParams();
  }
  /**
   * @description 表格排序值改变后回调
   * @param {string} sort 排序值
   */
  handleSortChange(sort: `-${string}` | string) {
    if (sort === this.sort) return;
    this.sort = sort;
    this.handleCurrentPageChange(1);
    this.setRouterParams();
  }

  /**
   * @description 删除查询模板
   * @param templateId 模板Id
   * @param {AlarmDeleteConfirmEvent['promiseEvent']} promiseEvent.promiseEvent Promise 对象，用于告诉 操作发起者 接口请求状态
   * @param {AlarmDeleteConfirmEvent['errorCallback']} promiseEvent.errorCallback Promise.reject 方法，用于告诉 操作发起者 接口请求失败
   * @param {AlarmDeleteConfirmEvent['successCallback']} promiseEvent.successCallback Promise.resolve 方法，用于告诉 操作发起者 接口请求成功
   */
  deleteTemplateById(templateId: AlarmTemplateListItem['id'], confirmEvent: AlarmDeleteConfirmEvent) {
    destroyAlarmTemplateById({ strategy_template_id: templateId, app_name: this.viewOptions.filters?.app_name })
      .then(() => {
        confirmEvent.successCallback();
        this.$bkMessage({
          message: this.$t('删除成功'),
          theme: 'success',
        });
        this.handleRefresh();
      })
      .catch(() => {
        confirmEvent.errorCallback();
        this.$bkMessage({
          message: this.$t('删除失败'),
          theme: 'error',
        });
      });
  }

  /**
   * @description 下发事件回调
   */
  handleDispatch(id: AlarmTemplateListItem['id']) {
    this.templatePushObj = {
      show: true,
      params: {
        strategy_template_ids: [id],
        app_name: this.viewOptions.filters?.app_name,
        name: this.tableData.find(item => item.id === id)?.name,
      },
    };
  }

  /**
   * @description 克隆事件回调
   */
  handleCloneTemplate(id: AlarmTemplateListItem['id']) {
    this.editTemplateId = id;
    this.editTemplateShow = true;
    this.editTemplateSliderScene = 'clone';
  }

  /**
   * @description 展示模板详情事件回调
   */
  handleShowDetail(obj: { id: AlarmTemplateListItem['id']; sliderActiveTab: AlarmTemplateDetailTabEnumType }) {
    this.templateDetailObj = {
      show: true,
      tabActive: obj.sliderActiveTab === 'base_info' ? detailsTabColumn.basic : detailsTabColumn.service,
      params: {
        app_name: this.viewOptions.filters?.app_name,
        ids: [obj.id],
        name: this.tableData.find(item => item.id === obj.id)?.name,
      },
    };
  }

  /**
   * @description 表格行勾选事件回调
   * @param {AlarmTemplateListItem['id'][]} selectedRowKeys 当前表格选中的行id数组
   */
  handleTableSelectedChange(selectedRowKeys: AlarmTemplateListItem['id'][]) {
    this.selectedRowKeys = selectedRowKeys;
  }

  /**
   * @description 批量/单个模板内属性更新事件回调
   * @param {AlarmTemplateListItem['id'] | AlarmTemplateListItem['id'][]} id 需要进行更新数据的 模板id 或 模板id数组
   * @param {Partial<AlarmTemplateListItem>} updateValue 需要更新的数据
   * @param {AlarmDeleteConfirmEvent['promiseEvent']} promiseEvent.promiseEvent Promise 对象，用于告诉 操作发起者 接口请求状态
   * @param {AlarmDeleteConfirmEvent['errorCallback']} promiseEvent.errorCallback Promise.reject 方法，用于告诉 操作发起者 接口请求失败
   * @param {AlarmDeleteConfirmEvent['successCallback']} promiseEvent.successCallback Promise.resolve 方法，用于告诉 操作发起者 接口请求成功
   */
  handleBatchUpdate(
    id: AlarmTemplateListItem['id'] | AlarmTemplateListItem['id'][],
    updateValue: Partial<AlarmTemplateListItem>,
    promiseEvent?: AlarmDeleteConfirmEvent
  ) {
    const ids = Array.isArray(id) ? id : [id];
    updateAlarmTemplateByIds({ ids, app_name: this.viewOptions.filters?.app_name, edit_data: updateValue })
      .then(() => {
        promiseEvent?.successCallback?.();
        this.$bkMessage({
          message: this.$t('更新成功'),
          theme: 'success',
        });
        this.handleRefresh();
      })
      .catch(() => {
        promiseEvent?.errorCallback?.();
        this.$bkMessage({
          message: this.$t('更新失败'),
          theme: 'error',
        });
      });
  }

  /**
   * @description 表格开关改变事件回调
   * @param id 模板id 或 模板id数组
   * @param updateValue 需要更新的数据
   * @returns
   */
  handleSwitchChangeFn(
    id: AlarmTemplateListItem['id'] | AlarmTemplateListItem['id'][],
    updateValue: Partial<AlarmTemplateListItem>
  ) {
    const ids = Array.isArray(id) ? id : [id];
    return new Promise((resolve, reject) => {
      updateAlarmTemplateByIds({ ids, app_name: this.viewOptions.filters?.app_name, edit_data: updateValue })
        .then(() => {
          this.$bkMessage({
            message: this.$t('更新成功'),
            theme: 'success',
          });
          resolve(true);
          this.handleRefresh();
        })
        .catch(() => {
          this.$bkMessage({
            message: this.$t('更新失败'),
            theme: 'error',
          });
          reject();
        });
    });
  }

  /**
   * @description 表格分页页码改变事件回调
   * @param {number} currentPage 改值后的页码
   */
  handleCurrentPageChange(currentPage: number) {
    this.current = currentPage;
  }

  /**
   * @description 表格分页每页条数改变事件回调
   * @param {number} pageSize 改值后的每页条数
   */
  handlePageSizeChange(pageSize: number) {
    this.pageSize = pageSize;
    this.handleCurrentPageChange(1);
    commonPageSizeSet(this.pageSize);
  }

  /**
   * @description 刷新表格数据
   */
  handleRefresh() {
    this.handleCurrentPageChange(1);
    this.refreshKey = random(8);
  }

  handleEditTemplate(id: number) {
    this.editTemplateId = id;
    this.editTemplateShow = true;
    this.editTemplateSliderScene = 'edit';
  }

  handleShowTemplatePush(show: boolean) {
    this.templatePushObj.show = show;
  }

  render() {
    return (
      <div class='alarm-template'>
        <div class='alarm-template-header'>
          <div class='alarm-template-header-operations'>
            <BatchOperations
              disabled={!this.selectedRowKeys?.length}
              onOperationClick={this.handleBatchOperationClick}
            />
            <StatusTab
              class='alarm-template-header-filter-tab'
              v-model={this.quickStatus}
              needAll={false}
              statusList={ALARM_TEMPLATE_QUICK_FILTER_LIST.map(e => AlarmTemplateTypeMap[e])}
              onChange={this.handleQuickStatusChange}
            />
          </div>
          <div class='alarm-template-header-search'>
            <AlarmTemplateSearch
              class='search-input'
              searchKeyword={this.searchKeyword}
              selectOptionMap={this.selectOptionsMap}
              onChange={this.handleSearchChange}
            />
          </div>
        </div>
        <div class='alarm-template-main'>
          <AlarmTemplateTable
            appName={this.viewOptions.filters?.app_name}
            current={this.current}
            emptyType={this.searchKeyword?.length ? 'search-empty' : 'empty'}
            loading={this.tableLoading}
            pageSize={this.pageSize}
            searchKeyword={this.searchKeyword}
            selectedRowKeys={this.selectedRowKeys}
            selectOptionMap={this.selectOptionsMap}
            sort={this.sort}
            switchChangeFn={this.handleSwitchChangeFn}
            tableData={this.tableData}
            total={this.total}
            onBatchUpdate={this.handleBatchUpdate}
            onClearSearch={() => this.handleSearchChange([])}
            onCloneTemplate={this.handleCloneTemplate}
            onCurrentPageChange={this.handleCurrentPageChange}
            onDeleteTemplate={this.deleteTemplateById}
            onDispatch={this.handleDispatch}
            onEditTemplate={this.handleEditTemplate}
            onFilterChange={this.handleSearchChange}
            onPageSizeChange={this.handlePageSizeChange}
            onSelectedChange={this.handleTableSelectedChange}
            onShowDetail={this.handleShowDetail}
            onSortChange={this.handleSortChange}
          />
        </div>

        <TemplateDetails
          defaultTab={this.templateDetailObj.tabActive}
          metricFunctions={this.metricFunctions}
          params={this.templateDetailObj.params}
          show={this.templateDetailObj.show}
          onShowChange={show => {
            this.templateDetailObj.show = show;
          }}
          onShowEdit={params => {
            this.templateDetailObj.show = false;
            this.editTemplateId = params.id;
            this.editTemplateShow = true;
          }}
          onShowPush={params => {
            this.templateDetailObj.show = false;
            this.templatePushObj = {
              show: true,
              params,
            };
          }}
        />
        <EditTemplateSlider
          appName={this.requestParam.app_name}
          isShow={this.editTemplateShow}
          metricFunctions={this.metricFunctions}
          scene={this.editTemplateSliderScene}
          templateId={this.editTemplateId}
          onShowChange={show => {
            this.editTemplateShow = show;
          }}
          onSuccess={this.handleRefresh}
        />
        <TemplatePush
          metricFunctions={this.metricFunctions}
          params={this.templatePushObj.params}
          show={this.templatePushObj.show}
          onShowChange={show => this.handleShowTemplatePush(show)}
          onShowDetails={params => {
            this.templatePushObj.show = false;
            this.handleShowDetail({ id: params.id, sliderActiveTab: 'base_info' });
          }}
          onSuccess={() => this.handleRefresh()}
        />
      </div>
    );
  }
}
