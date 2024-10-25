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

import { Component, Inject, InjectReactive, Prop, ProvideReactive, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import dayjs from 'dayjs';

import CallerCalleeContrast from './components/caller-callee-contrast';
import CallerCalleeFilter from './components/caller-callee-filter';
import CallerCalleeTableChart from './components/caller-callee-table-chart';
import ChartView from './components/chart-view';
import TabBtnGroup from './components/common-comp/tab-btn-group';
import { EParamsMode, EPreDateType, type CallOptions, type IFilterData } from './type';
import { CALLER_CALLEE_TYPE, type CallerCalleeType } from './utils';

import type { PanelModel, ZrClickEvent } from '../../typings';

import './apm-service-caller-callee.scss';
interface IApmServiceCallerCalleeProps {
  panel: PanelModel;
}
@Component({
  name: 'ApmServiceCallerCallee',
})
export default class ApmServiceCallerCallee extends tsc<IApmServiceCallerCalleeProps> {
  @Prop({ required: true, type: Object }) panel: PanelModel;

  @ProvideReactive('callOptions') callOptions: Partial<CallOptions> = {};
  @ProvideReactive('filterTags') filterTags: IFilterData;

  // 同步route query
  @Inject('handleCustomRouteQueryChange') handleCustomRouteQueryChange: (
    customRouteQuery: Record<string, number | string>
  ) => void;

  @InjectReactive('customRouteQuery') customRouteQuery: Record<string, string>;
  filterData = {
    caller: [],
    callee: [],
  };
  panelsData = [];
  tableListData = [];
  tableTabData = [];
  tabList = CALLER_CALLEE_TYPE;
  callType: CallerCalleeType = 'caller';
  dateData = [];
  diffTypeData = [];
  tableColData = [];
  // panel 传递过来的一些变量
  get panelScopedVars() {
    const angel = this.commonAngle;
    const options = this.callType === 'caller' ? angel.caller : angel.callee;
    return {
      server: options.server,
      ...options?.metrics,
    };
  }
  get commonOptions() {
    return this.panel?.options?.common || {};
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

  @Watch('panel', { immediate: true })
  handlePanelChange() {
    this.initDefaultData();
    let routeCallOptions: Partial<CallOptions> = {};
    if (this.customRouteQuery?.callOptions?.length) {
      try {
        routeCallOptions = JSON.parse(this.customRouteQuery.callOptions);
      } catch {
        routeCallOptions = {};
      }
    }
    console.info('routeCallOptions', routeCallOptions);
    this.callType = routeCallOptions.kind || 'caller';
    this.callOptions = {
      // panel 传递过来的一些变量
      ...this.panelScopedVars,
      // group 字段
      group_by: routeCallOptions.group_by || [],
      method: routeCallOptions.method || '',
      limit: +routeCallOptions.limit || 0,
      metric_cal_type: routeCallOptions.metric_cal_type || '',
      // 时间对比 字段
      time_shift: routeCallOptions.time_shift || [],
      // 左侧查询条件字段
      call_filter: routeCallOptions.call_filter || [],
      tool_mode: routeCallOptions.tool_mode || EParamsMode.contrast,
      kind: this.callType,
    };
  }

  replaceRouteQuery() {
    requestIdleCallback(() => {
      const copyOptions: Partial<CallOptions> = {};
      for (const [key, val] of Object.entries(this.callOptions)) {
        if (
          val === undefined ||
          val === '' ||
          val === 0 ||
          (Array.isArray(val) && val.length < 1) ||
          (key === 'tool_mode' && val === EParamsMode.contrast) ||
          (key === 'kind' && val === 'caller') ||
          key in this.panelScopedVars
        )
          continue;

        copyOptions[key] = val;
      }
      this.handleCustomRouteQueryChange({
        callOptions: JSON.stringify(copyOptions),
      });
    });
  }

  // 左侧主被调切换
  changeTab(id: string) {
    this.callType = id;
    this.callOptions = {
      ...this.callOptions,
      ...this.panelScopedVars,
      call_filter: [], // todo
    };
    this.replaceRouteQuery();
  }

  // 筛选查询
  searchFilterData(data: CallOptions['call_filter']) {
    this.callOptions = {
      ...this.callOptions,
      call_filter: structuredClone(data),
    };
    this.replaceRouteQuery();
  }
  // 重置
  resetFilterData() {
    this.callOptions = {
      ...this.callOptions,
      call_filter: [],
    };
    this.replaceRouteQuery();
  }
  // 关闭表格中的筛选tag, 调用查询接口
  handleCloseTag(data) {
    if (data.key !== 'time') {
      this.callOptions.call_filter = this.callOptions.call_filter.filter(item => item.key !== data.key);
    }
    this.searchFilterData(this.callOptions.call_filter);
  }
  // 查看详情 - 选中的字段回填到左侧筛选栏
  handleDetail({ row, key }) {
    // this.callOptions.call_filter.find(item => item.key === key).value = [row[key]];
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
    };
    this.changeDate(val);
    this.replaceRouteQuery();
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
    const callTimeShift = this.callOptions.time_shift.map(item => item.alias);
    this.tableColData = callTimeShift.length === 2 ? callTimeShift : ['0s', ...callTimeShift];
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
    };
    this.handleCheck(val);
    this.replaceRouteQuery();
  }

  handleParamsModeChange(val: EParamsMode) {
    if (val === EParamsMode.contrast) {
      this.callOptions = {
        ...this.callOptions,
        group_by: [],
        time_shift: [],
        limit: 0,
        metric_cal_type: '',
        method: '',
        tool_mode: val,
      };
    } else {
      this.callOptions = {
        ...this.callOptions,
        group_by: [],
        time_shift: [],
        limit: 10,
        metric_cal_type: this.supportedCalculationTypes?.[0]?.value || '',
        method: this.supportedMethods?.[0]?.value || '',
        tool_mode: val,
      };
    }
    this.replaceRouteQuery();
  }

  /** 点击选中图表里的某个点 */
  handleZrClick(event: ZrClickEvent) {
    if (!event.xAxis) return;
    console.info(event.dimensions, '=========');
    const date = dayjs.tz(event.xAxis).format('YYYY-MM-DD HH:mm:ss');
    const dateItem = this.callOptions.call_filter.find(item => item.key === 'time');
    if (dateItem) {
      dateItem.value = [date];
    } else {
      this.callOptions.call_filter.unshift({
        key: 'time',
        method: 'eq',
        value: [date],
        condition: 'end',
      });
    }
    this.callOptions.call_filter.push({
      key: 'time',
      method: 'eq',
      value: [date],
      condition: 'end',
    });
    this.callOptions = { ...this.callOptions };
  }
  /** 初始化主被调的相关数据 */
  initDefaultData() {
    const { caller, callee } = this.commonAngle;
    this.filterTags = {
      caller: caller?.tags,
      callee: callee?.tags,
    };
  }

  handleLimitChange(val: number) {
    this.callOptions = {
      ...this.callOptions,
      limit: val,
    };
  }
  handleMethodChange(val: string) {
    this.callOptions = {
      ...this.callOptions,
      method: val,
    };
  }
  handleMetricCalTypeChange(val: string) {
    this.callOptions = {
      ...this.callOptions,
      metric_cal_type: val,
    };
  }

  render() {
    return (
      <div class='apm-service-caller-callee'>
        <div class='caller-callee-head'>
          <div class='caller-callee-left'>
            <TabBtnGroup
              activeKey={this.callType}
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
              paramsMode={this.callOptions.tool_mode}
              searchList={this.callType === 'caller' ? this.commonAngle.caller?.tags : this.commonAngle.callee?.tags}
              supportedCalculationTypes={this.supportedCalculationTypes}
              supportedMethods={this.supportedMethods}
              onContrastDatesChange={this.handleContrastDatesChange}
              onGroupByChange={this.handleGroupChange}
              onGroupFilter={this.handleGroupFilter}
              onLimitChange={this.handleLimitChange}
              onMethodChange={this.handleMethodChange}
              onMetricCalType={this.handleMetricCalTypeChange}
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
                activeKey={this.callType}
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
                panelsData={this.panel.extra_panels}
                onZrClick={this.handleZrClick}
              />
              <CallerCalleeTableChart
                activeKey={this.callType}
                filterData={this.callOptions.call_filter}
                panel={this.panel}
                searchList={this.callType === 'caller' ? this.commonAngle.caller?.tags : this.commonAngle.callee?.tags}
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
