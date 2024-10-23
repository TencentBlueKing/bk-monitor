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

import { Component, Prop, ProvideReactive, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import dayjs from 'dayjs';
import { Debounce } from 'monitor-common/utils';

import { PanelModel } from '../../typings';
import CallerCalleeContrast from './components/caller-callee-contrast';
import CallerCalleeFilter from './components/caller-callee-filter';
import CallerCalleeTableChart from './components/caller-callee-table-chart';
import ChartView from './components/chart-view';
import TabBtnGroup from './components/common-comp/tab-btn-group';
import { CALLER_CALLEE_TYPE } from './utils';
import { EParamsMode, EPreDateType, type CallOptions, type IFilterType, type IFilterData } from './type';

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

  @ProvideReactive('callOptions') callOptions: CallOptions;
  @ProvideReactive('filterTags') filterTags: IFilterData;

  variablesService = {};
  panelsData = [];
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
  /* 对比/groupBy */
  paramsMode = EParamsMode.contrast;
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
    this.initDefaultData();
    this.panelsData = this.extraPanels.map(panel => new PanelModel(panel));
    this.callOptions = {
      // panel 传递过来的一些变量
      ...this.panelScopedVars,
      // group 字段
      group_by: [],
      method: '',
      limit: 0,
      metric_cal_type: '',
      // 时间对比 字段
      time_shift: [],
      // 左侧查询条件字段
      call_filter: [],
    };
  }

  @Watch('callOptions')
  handleRefreshData(val: IFilterType) {
    if (val) {
      this.initData();
    }
  }

  get panelOptions() {
    return this.panel.options || {};
  }

  get extraPanels() {
    return this.panel.extra_panels || [];
  }

  get commonOptions() {
    return this.panelOptions?.common || {};
  }

  get supportedCalculationTypes() {
    return this.commonOptions?.group_by?.supported_calculation_types || [];
  }

  get supportedMethods() {
    return this.commonOptions?.group_by?.supported_methods || [];
  }

  get commonAngle() {
    return this.commonOptions?.angle || {};
  }

  // 左侧主被调切换
  /*  */

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
    this.callOptions.call_filter = JSON.parse(JSON.stringify(data));
    this.initData();
  }
  // 重置
  resetFilterData() {
    this.callOptions.call_filter = [];
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
      this.callOptions.call_filter.find(item => item.key === data.key).value = [];
    }
    this.searchFilterData(this.callOptions.call_filter);
  }
  // 查看详情 - 选中的字段回填到左侧筛选栏
  handleDetail({ row, key }) {
    this.callOptions.call_filter.find(item => item.key === key).value = [row[key]];
  }

  /**
   * @description 对比日期选择
   * @param val
   */
  handleContrastDatesChange(val: string[]) {
    const timeShift = [];
    for (const item of val) {
      if (item === EPreDateType.yesterday) {
        timeShift.push({
          alias: item,
          start_time: dayjs().subtract(1, 'day').startOf('day').unix(),
          end_time: dayjs().subtract(1, 'day').endOf('day').unix(),
        });
      } else if (item === EPreDateType.lastWeek) {
        timeShift.push({
          alias: item,
          start_time: dayjs().startOf('week').subtract(1, 'week').unix(),
          end_time: dayjs().endOf('week').subtract(1, 'week').unix(),
        });
      } else {
        timeShift.push({
          alias: item,
          start_time: dayjs(item).startOf('day').unix(),
          end_time: dayjs(item).endOf('day').unix(),
        });
      }
    }
    this.callOptions = {
      ...this.callOptions,
      time_shift: timeShift,
    } as any;
    this.changeDate(val);
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
    this.callOptions = {
      ...this.callOptions,
      group_by: val,
    } as any;
    this.handleCheck(val);
  }

  handleParamsModeChange(val: EParamsMode) {
    this.paramsMode = val;
    if (val === EParamsMode.contrast) {
      this.callOptions = {
        ...this.callOptions,
        group_by: [],
        time_shift: [],
        limit: 0,
        metric_cal_type: '',
        method: '',
      } as any;
    } else {
      this.callOptions = {
        ...this.callOptions,
        group_by: [],
        time_shift: [],
        limit: 10,
        metric_cal_type: this.supportedCalculationTypes?.[0]?.value || '',
        method: this.supportedMethods?.[0]?.value || '',
      } as any;
    }
  }

  /** 点击选中图表里的某个点 */
  handleChoosePoint(date) {
    if (this.callOptions.call_filter.findIndex(item => item.key === 'time') !== -1) {
      this.callOptions.call_filter.find(item => item.key === 'time').value = [date];
      return;
    }
    this.callOptions.call_filter.push({
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
  async getPanelData(start_time?: string, end_time?: string) {
    console.log(start_time, end_time);
  }

  /** 初始化主被调的相关数据 */
  initDefaultData() {
    const { caller, callee } = this.commonAngle;
    this.filterTags = {
      caller: caller?.tags,
      callee: callee?.tags,
    };
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
              contrastDates={this.callOptions.time_shift.map(item => item.alias)}
              groupBy={this.callOptions.group_by}
              limit={this.callOptions.limit}
              method={this.callOptions.method}
              metricCalType={this.callOptions.metric_cal_type}
              paramsMode={this.paramsMode}
              searchList={this.filterTags[this.activeKey]}
              supportedCalculationTypes={this.supportedCalculationTypes}
              supportedMethods={this.supportedMethods}
              onContrastDatesChange={this.handleContrastDatesChange}
              onGroupByChange={this.handleGroupChange}
              onGroupFilter={this.handleGroupFilter}
              onTypeChange={this.handleParamsModeChange}
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
                activeKey={this.activeKey}
                panel={this.panel}
                onReset={this.resetFilterData}
                onSearch={this.searchFilterData}
              />
            </div>
            <div
              class='layout-main'
              slot='main'
            >
              <ChartView
                panelsData={this.panel.extra_panels.map(item => {
                  if (item.type === 'graph') {
                    item.type = 'caller-line-chart';
                    return item;
                  }
                  return item;
                })}
                onChoosePoint={this.handleChoosePoint}
              />
              <CallerCalleeTableChart
                activeKey={this.activeKey}
                filterData={this.callOptions.call_filter}
                panel={this.panel}
                searchList={this.filterTags[this.activeKey]}
                tableColData={this.tableColData}
                tableListData={this.tableListData}
                tableTabData={this.tableTabData}
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
