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
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';
import GroupCompareSelect from 'monitor-pc/pages/monitor-k8s/components/group-compare-select/group-compare-select';
import { ETypeSelect as EGroupCompareType } from 'monitor-pc/pages/monitor-k8s/components/group-compare-select/utils';

import CallerCalleeFilter from './components/caller-callee-filter';
import CallerCalleeTableChart from './components/caller-callee-table-chart';
import ChartView from './components/chart-view';
import TabBtnGroup from './components/tab-btn-group';
import { type CallOptions, type IChartOption, type IFilterCondition, type IFilterData, EKind } from './type';
import {
  CALLER_CALLEE_TYPE,
  formatPreviousDayAndWeekTimestamps,
  getRecordCallOptionKind,
  setRecordCallOptionKind,
} from './utils';

import type { PanelModel, ZrClickEvent } from '../../typings';
import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';

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
  @InjectReactive('viewOptions') viewOptions;

  @InjectReactive('timeRange') readonly timeRange!: TimeRangeType;
  @InjectReactive('refreshInterval') readonly refreshInterval!: number;
  @InjectReactive('refreshImmediate') readonly refreshImmediate: string;

  panelsData = [];
  tabList = CALLER_CALLEE_TYPE;
  callType = EKind.callee;
  dateData = [];
  diffTypeData = [];
  tableColData = [];
  chartPointOption: IChartOption = {};
  collapsed = false;
  // panel 传递过来的一些变量
  get panelScopedVars() {
    const angel = this.commonAngle;
    const options = this.callType === EKind.caller ? angel.caller : angel.callee;
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
  timeStrShow = {};
  // 自动刷新定时任务
  refreshIntervalInstance = null;
  @Watch('refreshInterval', { immediate: true })
  // 数据刷新间隔
  handleRefreshIntervalChange(v: number) {
    if (this.refreshIntervalInstance) {
      window.clearInterval(this.refreshIntervalInstance);
    }
    if (!v || +v < 60 * 1000) return;
    this.refreshIntervalInstance = window.setInterval(() => {
      this.handleSetTimeStrShow();
    }, v);
  }
  @Watch('refreshImmediate')
  handleRefleshImmediate() {
    this.handleSetTimeStrShow();
  }

  @Watch('timeRange', { immediate: true })
  handleTimeRange() {
    this.handleSetTimeStrShow();
  }
  handleSetTimeStrShow() {
    this.timeStrShow = formatPreviousDayAndWeekTimestamps(handleTransformToTimestamp(this.timeRange));
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
    this.callType = routeCallOptions.kind || getRecordCallOptionKind(this.viewOptions.filters) || EKind.callee;
    const groupBy = this.groupByKindReset(this.callType, routeCallOptions.group_by || []);
    this.callOptions = {
      // panel 传递过来的一些变量
      ...this.panelScopedVars,
      // group 字段
      group_by: groupBy,
      method: routeCallOptions.method || '',
      limit: +routeCallOptions.limit || 0,
      metric_cal_type: routeCallOptions.metric_cal_type || '',
      // 时间对比 字段
      time_shift: routeCallOptions.time_shift || [],
      // 左侧查询条件字段
      call_filter: routeCallOptions.call_filter || [],
      tool_mode: routeCallOptions.tool_mode || EGroupCompareType.compare,
      kind: this.callType,
      perspective_type: 'single',
      perspective_group_by: [],
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
          (key === 'tool_mode' && val === EGroupCompareType.compare) ||
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
  changeTab(id: EKind) {
    this.callType = id;
    setRecordCallOptionKind(this.viewOptions.filters, this.callType);
    this.resetCallOptions(id);
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
    this.chartPointOption = {};
    this.replaceRouteQuery();
  }
  /** 表格下钻 */
  handleTableDrill(data: IFilterCondition[]) {
    const call_filter = this.callOptions.call_filter.slice(0);
    for (const item of data) {
      if (item.key === 'time') {
        this.chartPointOption = {
          time: item.value[0] ? dayjs(+item.value[0] * 1000).format('YYYY-MM-DD HH:mm:ss') : '',
          interval: 0,
          dimensions: {},
        };
        continue;
      }
      const callerItem = call_filter.find(call => call.key === item.key);
      if (!callerItem) {
        call_filter.push(item);
        continue;
      }
      callerItem.value = item.value;
    }
    this.searchFilterData(call_filter);
  }
  // 关闭表格中的筛选tag, 调用查询接口
  handleCloseTag(data: IFilterCondition) {
    const list = this.callOptions.call_filter.filter(item => item.key !== data.key);
    this.searchFilterData(list);
  }
  // 查看详情 - 选中的字段回填到左侧筛选栏
  handleDetail({ _row, _key }) {
    // this.callOptions.call_filter.find(item => item.key === key).value = [row[key]];
  }

  /**
   * @description 对比日期选择
   * @param val
   */
  handleContrastDatesChange(val: string[]) {
    this.callOptions = {
      ...this.callOptions,
      time_shift: val,
    };
    this.handleTableColData();
    this.replaceRouteQuery();
  }

  handleCheck(data) {
    this.diffTypeData = data;
    this.handleTableColData();
  }
  handleTableColData() {
    const callTimeShift = this.callOptions.time_shift;
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

  handleParamsModeChange(val: EGroupCompareType) {
    if (val === EGroupCompareType.compare) {
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
    const date = dayjs.tz(event.xAxis).format('YYYY-MM-DD HH:mm:ss');
    this.chartPointOption = {
      dimensions: event?.dimensions || {},
      time: date,
      interval: event?.interval,
    };
  }
  closeChartPoint() {
    this.chartPointOption = {};
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

  // 根据主调背调切换需重置group_by, 剔除不属于此分类的维度
  groupByKindReset(kind: string, groupBy: string[]) {
    const list = (kind === EKind.caller ? this.commonAngle.caller?.tags : this.commonAngle.callee?.tags) || [];
    const sets = new Set();
    const result = [];
    for (const item of list) {
      sets.add(item.value);
    }
    for (const item of groupBy) {
      if (sets.has(item)) {
        result.push(item);
      }
    }
    return result;
  }

  resetCallOptions(kind: EKind) {
    this.callOptions = {
      ...this.panelScopedVars,
      kind: kind,
      group_by: [],
      method: this.supportedMethods?.[0]?.value || '',
      limit: 10,
      metric_cal_type: this.supportedCalculationTypes?.[0]?.value || '',
      call_filter: [],
      tool_mode: EGroupCompareType.compare,
      time_shift: [],
    };
  }
  handleCollapseChange(collapsed: boolean) {
    this.collapsed = collapsed;
  }
  render() {
    return (
      <div class='apm-service-caller-callee'>
        <bk-resize-layout
          class='caller-callee-layout'
          initial-divide={320}
          max={500}
          min={320}
          placement='left'
          collapsible
          on-collapse-change={this.handleCollapseChange}
        >
          <div
            class='layout-aside'
            slot='aside'
          >
            <div class='filter-btn-group'>
              <TabBtnGroup
                activeKey={this.callType}
                list={this.tabList}
                onChange={this.changeTab}
              />
            </div>
            <CallerCalleeFilter
              callOptions={this.callOptions}
              callType={this.callType}
              panel={this.panel}
              onReset={this.resetFilterData}
              onSearch={this.searchFilterData}
            />
          </div>
          <div
            style='background: #F5F7FA;'
            class='layout-main'
            slot='main'
          >
            <div class='caller-callee-head'>
              <div
                style={{
                  width: !this.collapsed ? '0px' : '320px',
                  opacity: !this.collapsed ? 0 : 1,
                  padding: !this.collapsed ? 0 : '24px',
                }}
                class='filter-btn-group header-left'
              >
                <TabBtnGroup
                  activeKey={this.callType}
                  list={this.tabList}
                  onChange={this.changeTab}
                />
              </div>
              <GroupCompareSelect
                groupOptions={
                  this.callType === EKind.caller ? this.commonAngle.caller?.tags : this.commonAngle.callee?.tags
                }
                active={this.callOptions.tool_mode}
                groupOptionsLimitEnabled={true}
                groups={this.callOptions.group_by}
                hasGroupOptions={true}
                limit={this.callOptions.limit}
                limitSortMethod={this.callOptions.method}
                limitSortMethods={this.supportedMethods}
                metricCalType={this.callOptions.metric_cal_type}
                metricCalTypes={this.supportedCalculationTypes}
                paramsMode={this.callOptions.tool_mode}
                supportedCalculationTypes={this.supportedCalculationTypes}
                supportedMethods={this.supportedMethods}
                timeStrShow={this.timeStrShow}
                timeValue={this.callOptions.time_shift}
                onContrastDatesChange={this.handleContrastDatesChange}
                onGroupByChange={this.handleGroupChange}
                onGroupChange={this.handleGroupChange}
                onGroupFilter={this.handleGroupFilter}
                onLimitChange={this.handleLimitChange}
                onLimitSortMethodChange={this.handleMethodChange}
                onMetricCalTypeChange={this.handleMetricCalTypeChange}
                onTimeCompareChange={this.handleContrastDatesChange}
                onTypeChange={this.handleParamsModeChange}
              />
            </div>
            <ChartView
              panelsData={this.panel.extra_panels}
              onZrClick={this.handleZrClick}
            />
            <CallerCalleeTableChart
              activeKey={this.callType}
              chartPointOption={this.chartPointOption}
              filterData={this.callOptions.call_filter}
              panel={this.panel}
              searchList={this.callType === 'caller' ? this.commonAngle.caller?.tags : this.commonAngle.callee?.tags}
              timeStrShow={this.timeStrShow}
              onCloseChartPoint={this.closeChartPoint}
              onCloseTag={this.handleCloseTag}
              onDrill={this.handleTableDrill}
              onHandleDetail={this.handleDetail}
            />
          </div>
        </bk-resize-layout>
      </div>
    );
  }
}
