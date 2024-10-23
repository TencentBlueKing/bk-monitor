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

import { PanelModel } from '../../typings';
import CallerCalleeContrast from './components/caller-callee-contrast';
import CallerCalleeFilter from './components/caller-callee-filter';
import CallerCalleeTableChart from './components/caller-callee-table-chart';
import ChartView from './components/chart-view';
import TabBtnGroup from './components/common-comp/tab-btn-group';
import { SEARCH_KEY_LIST } from './SEARCH_KEY_LIST';
import { EParamsMode, EPreDateType, type CallOptions } from './type';
import { CALLER_CALLEE_TYPE } from './utils';

import './apm-service-caller-callee.scss';
interface IApmServiceCallerCalleeProps {
  panel: PanelModel;
}
@Component({
  name: 'ApmServiceCallerCallee',
})
export default class ApmServiceCallerCallee extends tsc<IApmServiceCallerCalleeProps> {
  @Prop({ required: true, type: Object }) panel: PanelModel;

  @ProvideReactive('callOptions') callOptions: CallOptions = {} as any;
  // 顶层注入数据
  /** 过滤列表loading */
  filterLoading = false;
  variablesService = {};
  // 筛选具体的key list
  searchListData = SEARCH_KEY_LIST;
  filterData = {
    caller: [],
    callee: [],
  };
  /** 初始化filter的列表 */
  filterTags = {
    caller: [],
    callee: [],
  };
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
      kind: this.activeKey,
    };
  }
  @Watch('panel', { immediate: true })
  handlePanelChange() {
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

  get panelOptions() {
    return this.panel.options || {};
  }

  get extraPanels() {
    return this.panel.extra_panels || [];
  }

  get commonOptions() {
    return this.panelOptions?.common || {};
  }

  get variablesData() {
    return this.commonOptions?.variables?.data || {};
  }

  get statisticsOption() {
    return this.commonOptions?.statistics;
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
    this.callOptions = {
      ...this.callOptions,
      ...this.panelScopedVars,
    };
  }

  // 筛选查询
  searchFilterData(data: CallOptions['call_filter']) {
    this.callOptions = {
      ...this.callOptions,
      call_filter: structuredClone(data),
    };
  }
  // 重置
  resetFilterData() {
    this.callOptions = {
      ...this.callOptions,
      call_filter: [],
    };
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
  /** 初始化主被调的相关数据 */
  initDefaultData() {
    const { caller, callee } = this.commonAngle;
    const createFilterData = tags =>
      (tags || []).map(item => ({
        key: item.value,
        method: 'eq',
        value: [],
        condition: 'and',
      }));
    // const createFilterTags = tags => (tags || []).map(item => ({ ...item, values: [] }));

    // 使用通用函数生成数据
    this.filterData = {
      caller: createFilterData(caller?.tags),
      callee: createFilterData(callee?.tags),
    };

    this.filterTags = {
      caller: caller?.tags,
      callee: callee?.tags,
    };
  }

  mounted() {
    this.initDefaultData();
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
                filterData={this.callOptions.call_filter}
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
