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

import { Component, PropSync, ProvideReactive } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import dayjs from 'dayjs';
import TimeRange, { type TimeRangeType } from 'monitor-pc/components/time-range/time-range';
import { getDefaultTimezone, updateTimezone } from 'monitor-pc/i18n/dayjs';

import Metric from './dataStatus/metric';
import TabList from './tabList';
import { ETelemetryDataType, type IAppInfo } from './type';

import type { IViewOptions } from 'monitor-ui/chart-plugins/typings';

import './data-status.scss';

@Component
export default class DataStatus extends tsc<object> {
  @PropSync('data', { type: Object, required: true }) appInfo: IAppInfo;
  pickerTimeRange: string[] = [
    dayjs(new Date()).add(-1, 'd').format('YYYY-MM-DD'),
    dayjs(new Date()).format('YYYY-MM-DD'),
  ];

  activeTab = ETelemetryDataType.trace;
  strategyLoading = false;

  // 派发到子孙组件内的视图配置变量
  // 视图变量
  @ProvideReactive('viewOptions') viewOptions: IViewOptions = {};
  // 时间间隔
  @ProvideReactive('timeRange') timeRange: TimeRangeType = ['now-1d', 'now'];
  /** 时区 */
  @ProvideReactive('timezone') timezone: string = getDefaultTimezone();
  // 对比的时间
  @ProvideReactive('timeOffset') timeOffset: string[] = [];

  get tabList() {
    return [
      {
        name: ETelemetryDataType.metric,
        label: window.i18n.tc('指标'),
        status: this.appInfo.metric_data_status,
      },
      {
        name: ETelemetryDataType.log,
        label: window.i18n.tc('日志'),
        status: this.appInfo.log_data_status,
      },
      {
        name: ETelemetryDataType.trace,
        label: window.i18n.tc('调用链'),
        status: this.appInfo.trace_data_status,
      },
      {
        name: ETelemetryDataType.profiling,
        label: window.i18n.tc('性能分析'),
        status: this.appInfo.profiling_data_status,
      },
    ];
  }

  created() {
    if (this.tabList.find(item => item.name === this.activeTab)?.status === 'disabled') {
      this.activeTab = this.tabList.find(item => item.status !== 'disabled')?.name || ETelemetryDataType.trace;
    }
    this.timezone = getDefaultTimezone();
  }

  /**
   * @desc 日期范围改变
   * @param { array } date 日期范围
   */
  handleTimeRangeChange(date) {
    this.timeRange = date;
  }
  handleTimezoneChange(timezone: string) {
    updateTimezone(timezone);
    this.timezone = timezone;
  }

  /** tab切换时 */
  handleChangeActiveTab(active: ETelemetryDataType) {
    this.activeTab = active;
    // switch (active) {
    //   case ETelemetryDataType.log:
    //     // this.getIndicesList();
    //     break;
    //   case ETelemetryDataType.metric:
    //     // this.getStoreList();
    //     break;
    //   case ETelemetryDataType.trace:
    //     // this.getMetaConfigInfo();
    //     // this.getIndicesList();
    //     // this.getFieldList();
    //     break;
    //   default:
    //     break;
    // }
  }

  /** 获取选择的tab组件 */
  getActiveComponent() {
    return (
      <Metric
        key={this.activeTab}
        activeTab={this.activeTab}
        appInfo={this.appInfo}
      />
    );
  }

  render() {
    return (
      <div class='conf-content data-status-wrap'>
        <div class='data-status-tab-wrap'>
          <TabList
            activeTab={this.activeTab}
            tabList={this.tabList}
            onChange={this.handleChangeActiveTab}
          />
          <TimeRange
            class='data-status-time'
            timezone={this.timezone}
            value={this.timeRange}
            onChange={this.handleTimeRangeChange}
            onTimezoneChange={this.handleTimezoneChange}
          />
        </div>
        <div class='storage-content'>{this.getActiveComponent()}</div>
      </div>
    );
  }
}
