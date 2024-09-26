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

import { Component, ProvideReactive } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import dayjs from 'dayjs';
import TimeRange, { type TimeRangeType } from 'monitor-pc/components/time-range/time-range';
import { getDefaultTimezone, updateTimezone } from 'monitor-pc/i18n/dayjs';

import Metric from './dataStatus/metric';
import TabList from './tabList';
import { ETelemetryDataType } from './type';

import type { IViewOptions } from 'monitor-ui/chart-plugins/typings';

import './data-status.scss';

@Component
export default class DataStatus extends tsc<object> {
  pickerTimeRange: string[] = [
    dayjs(new Date()).add(-1, 'd').format('YYYY-MM-DD'),
    dayjs(new Date()).format('YYYY-MM-DD'),
  ];

  /** 选择的tab*/
  tabList = [
    {
      name: ETelemetryDataType.metric,
      label: window.i18n.tc('指标'),
    },
    {
      name: ETelemetryDataType.log,
      label: window.i18n.tc('日志'),
    },
    {
      name: ETelemetryDataType.tracing,
      label: window.i18n.tc('调用链'),
    },
    {
      name: ETelemetryDataType.profiling,
      label: window.i18n.tc('性能分析'),
    },
  ];
  activeTab = ETelemetryDataType.metric;
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

  /** 应用ID */
  get appId() {
    return Number(this.$route.params?.id || 0);
  }

  created() {
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
    //   case ETelemetryDataType.tracing:
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
    return <Metric activeTab={this.activeTab} />;
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
