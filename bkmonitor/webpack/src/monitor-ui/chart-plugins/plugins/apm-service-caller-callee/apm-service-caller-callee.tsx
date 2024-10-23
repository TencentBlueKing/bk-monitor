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

import { Component, Prop, Provide, ProvideReactive, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
// import dayjs from 'dayjs';
import { getFieldOptionValues } from 'monitor-api/modules/apm_metric';
import { Debounce } from 'monitor-common/utils';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';

import { reviewInterval } from '../../utils';
import { VariablesService } from '../../utils/variable';

import type { PanelModel } from '../../typings';
// import { DEFAULT_FILTER } from './baseFIlterList';
import CallerCalleeContrast from './components/caller-callee-contrast';
import CallerCalleeFilter from './components/caller-callee-filter';
import CallerCalleeTableChart from './components/caller-callee-table-chart';
import ChartView from './components/chart-view';
import TabBtnGroup from './components/common-comp/tab-btn-group';
import { SEARCH_KEY_LIST } from './SEARCH_KEY_LIST';
import { dashboardPanels } from './testData';
import { CALLER_CALLEE_TYPE } from './utils';

import type { IFilterType } from './type';

import './apm-service-caller-callee.scss';
interface IApmServiceCallerCalleeProps {
  panel: PanelModel;
}
@Component({
  name: 'ApmServiceCallerCallee',
  components: {},
})
export default class ApmServiceCallerCallee extends tsc<IApmServiceCallerCalleeProps> {
  @Prop({ required: true, type: Object }) panel: PanelModel;
  // callOption 最终需要的filter数据
  @ProvideReactive('callOptions') callOptions: Record<string, any> = {};
  /** 过滤列表loading */
  filterLoading = false;
  variablesService = {};
  // 筛选具体的key list
  searchListData = SEARCH_KEY_LIST;
  /* 已选的对比日期 */
  contrastDates = [];
  /* 已选的groupBy */
  groupBy = [];
  filterData = {
    caller: [],
    callee: [],
  };
  /** 初始化filter的列表 */
  filterTags = {
    caller: [],
    callee: [],
  };
  panelsData = dashboardPanels;
  testData = [
    {
      caller_service: 'caller.collector.Unknown',
      formal: 'formal',
      now: 33,
      yesterday: 23,
    },
    {
      caller_service: 'caller.collector.UnknownHTTP',
      formal: 'formal1',
      now: 33,
      yesterday: 23,
    },
  ];
  tableListData = this.testData;
  tableTabData = this.testData;
  tabList = CALLER_CALLEE_TYPE;
  activeKey = 'caller';
  filterDataList = [];
  dateData = [];
  diffTypeData = [];
  tableColData = [];
  // panel 传递过来的一些变量
  get panelScopedVars() {
    const angel = this.panel?.options?.common?.angle || {};
    const options = this.activeKey === 'caller' ? angel.caller : angel.callee;
    return {
      server: options.server,
      ...options?.metrics,
    };
  }
  @Watch('panel', { immediate: true })
  handlePanelChange() {
    console.log(this.panelScopedVars, 'this.panelScopedVars');
    this.callOptions = {
      where: [],
      // panel 传递过来的一些变量
      ...this.panelScopedVars,
      // group 字段
      group_by: [],
      method: 'topk',
      limit: '',
      metric_cal_type: '',
      // 时间对比 字段
      time_shift: [],
    };
  }

  @Watch('callOption')
  handleRefreshData(val: IFilterType) {
    if (val) {
      this.initData();
    }
  }

  get sceneDataOption() {
    return this.panel.options || {};
  }

  get extraPanels() {
    return this.panel.extra_panels || [];
  }

  get commonOptions() {
    return this.sceneDataOption?.common || {};
  }

  get variablesData() {
    return this.commonOptions?.variables?.data || {};
  }

  get angleData() {
    return this.commonOptions?.angle || {};
  }

  get statisticsOption() {
    return this.commonOptions?.statistics;
  }

  // 左侧主被调切换
  changeTab(id: string) {
    this.activeKey = id;
    this.getPanelData();
    this.handleUpdateRouteQuery({ filterType: id });
  }

  // 路由同步关键字
  handleUpdateRouteQuery(data) {
    const routerParams = {
      name: this.$route.name,
      query: {
        ...this.$route.query,
        ...data,
      },
    };
    this.$router.replace(routerParams).catch(() => {});
  }
  // 筛选查询
  searchFilterData(data) {
    this.callOption.call_filter = JSON.parse(JSON.stringify(data));
    this.initData();
  }
  // 重置
  resetFilterData() {
    const data = (this.filterData || []).map(item => Object.assign(item, { method: 'eq', value: [] }));
    this.filterData[this.activeKey] = data;
    this.callOption.call_filter = data;
  }
  // 获取表格数据
  handleGetTableData() {}
  // 获取图表数据
  handleGetChartData() {}

  initData() {
    console.log('刷新页面');
    this.handleGetTableData();
    this.handleGetChartData();
  }
  // 关闭表格中的筛选tag, 调用查询接口
  handleCloseTag(data) {
    if (data.key !== 'time') {
      this.filterData[this.activeKey].find(item => item.key === data.key).value = [];
    }
    this.searchFilterData(this.filterData[this.activeKey]);
  }
  // 查看详情 - 选中的字段回填到左侧筛选栏
  handleDetail({ row, key }) {
    this.filterData[this.activeKey].find(item => item.label === key).values = [row[key]];
  }

  /**
   * @description 对比日期选择
   * @param val
   */
  handleContrastDatesChange(val: string[]) {
    this.contrastDates = val;
  }

  changeFilterData({ val, item }) {
    console.log(val, item);
  }

  changeDate(date) {
    this.dateData = date;
    this.handleTableColData();
  }

  handleCheck(data) {
    this.diffTypeData = data;
    this.handleTableColData();
  }
  handleTableColData() {
    this.tableColData = [...this.dateData, ...this.diffTypeData];
  }
  handleGroupFilter() {}
  /**
   * @description groupBy 数据
   * @param val
   */
  handleGroupChange(val: string[]) {
    this.groupBy = val;
  }

  /** 点击选中图表里的某个点 */
  handleChoosePoint(date) {
    if (this.callOptions.where.findIndex(item => item.key === 'time') !== -1) {
      this.callOptions.where.find(item => item.key === 'time').value = [date];
      return;
    }
    this.callOptions.where.push({
      key: 'time',
      method: 'eq',
      value: [date],
      condition: 'end',
    });
  }

  handleSetParams() {}
  /**
   * @description: 获取Panel数据
   */
  @Debounce(200)
  async getPanelData(start_time?: string, end_time?: string) {}
  /** 获取左侧列表可选值 */
  initFilterValList() {}

  /** 初始化主被调的相关数据 */
  initDefaultData() {
    const { caller, callee } = this.angleData;
    const createFilterData = tags =>
      (tags || []).map(item => ({
        key: item.value,
        method: 'eq',
        value: [],
        condition: 'and',
      }));
    const createFilterTags = tags => (tags || []).map(item => ({ ...item, values: [] }));

    // 使用通用函数生成数据
    this.filterData = {
      caller: createFilterData(caller?.tags),
      callee: createFilterData(callee?.tags),
    };

    this.filterTags = {
      caller: createFilterTags(caller?.tags),
      callee: createFilterTags(callee?.tags),
    };
  }
  /** 单视角/多视角切换维度字段 */
  changeViewField(group_by: string[]) {
    // this.callOptions.table_group_by = group_by;
  }
  mounted() {
    this.initDefaultData();
  }
  /** 动态获取左侧列表的下拉值 */
  @Debounce(300)
  searchToggle({ isOpen, key }) {
    if (!isOpen) {
      return;
    }
    const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
    const filter = (this.filterData[this.activeKey] || []).filter(item => item.value.length > 0);
    /** 前端处理数据：
     * 前匹配：调用后台、跳转数据检索时补成 example.*
     * 后匹配：调用后台、跳转数据检索时补成 .*example
     * */
    const updatedFilter = filter.map(item => {
      if (item.method === 'before_req' || item.method === 'after_req') {
        const prefix = item.method === 'before_req' ? '' : '.*';
        const suffix = item.method === 'before_req' ? '.*' : '';
        return {
          ...item,
          value: item.value.map(value => `${prefix}${value}${suffix}`),
          method: 'reg',
        };
      }
      return item;
    });
    const { where, metrics, server } = this.commonOptions.angle[this.activeKey];
    const interval = reviewInterval(this.viewOptions.interval, endTime - startTime, this.panel.collect_interval);
    const variablesService = new VariablesService({
      ...this.viewOptions,
      interval,
      ...metrics,
      server,
    });
    const params = {
      start_time: startTime,
      end_time: endTime,
      field: key,
    };
    const newParams = {
      ...variablesService.transformVariables(this.variablesData, {
        ...this.viewOptions,
        interval,
      }),
      ...params,
    };
    newParams.where = [...newParams.where, ...updatedFilter];
    this.filterLoading = true;
    getFieldOptionValues(newParams)
      .then(res => {
        this.filterLoading = false;
        const newFilter = this.filterTags[this.activeKey].map(item =>
          item.value === key ? { ...item, values: res } : item
        );
        this.$set(this.filterTags, this.activeKey, newFilter);
      })
      .catch(() => (this.filterLoading = true));
  }

  render() {
    return (
      <div class='apm-service-caller-callee'>
        <div class='caller-callee-head'>
          <div class='caller-callee-left'>
            <TabBtnGroup
              activeKey={this.activeKey}
              list={this.tabList}
              onChange={this.changeTab}
            />
          </div>
          <div class='caller-callee-right'>
            <CallerCalleeContrast
              contrastDates={this.contrastDates}
              groupBy={this.groupBy}
              searchList={this.filterTags[this.activeKey]}
              onChangeDate={this.changeDate}
              onCheck={this.handleCheck}
              // onChangeDate={this.changeDate}
              // onCheck={this.handleCheck}
              onContrastDatesChange={this.handleContrastDatesChange}
              onGroupByChange={this.handleGroupChange}
              onGroupChange={this.handleGroupChange}
              onGroupFilter={this.handleGroupFilter}
            />
          </div>
        </div>
        <div class='caller-callee-main'>
          <bk-resize-layout
            class='caller-callee-layout'
            initial-divide={320}
            max={500}
            min={320}
            placement='left'
            collapsible
          >
            <div
              class='layout-aside'
              slot='aside'
            >
              <CallerCalleeFilter
                filterData={this.filterData[this.activeKey]}
                isLoading={this.filterLoading}
                searchList={this.filterTags[this.activeKey]}
                onChange={this.changeFilterData}
                onReset={this.resetFilterData}
                onSearch={this.searchFilterData}
                onToggle={this.searchToggle}
              />
            </div>
            <div
              class='layout-main'
              slot='main'
            >
              <ChartView
                panelsData={this.panelsData}
                onChoosePoint={this.handleChoosePoint}
              />
              <CallerCalleeTableChart
                filterData={this.callOptions.where}
                searchList={this.filterTags[this.activeKey]}
                tableColData={this.tableColData}
                tableListData={this.tableListData}
                tableTabData={this.tableTabData}
                onChange={this.changeViewField}
                onCloseTag={this.handleCloseTag}
                onHandleDetail={this.handleDetail}
              />
            </div>
          </bk-resize-layout>
        </div>
      </div>
    );
  }
}
