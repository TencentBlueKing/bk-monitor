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
import { dataStatus } from 'monitor-api/modules/apm_meta';
import TimeRange, { type TimeRangeType } from 'monitor-pc/components/time-range/time-range';
import { getDefaultTimezone, updateTimezone } from 'monitor-pc/i18n/dayjs';

import TabList from '../tabList';
import { type IAppInfo, ETelemetryDataType } from '../type';
import Metric from './data-state-metric';

import type { IViewOptions } from 'monitor-ui/chart-plugins/typings';

import './data-state.scss';

@Component
export default class DataStatus extends tsc<object> {
  @PropSync('data', { type: Object, required: true }) appInfo: IAppInfo;
  pickerTimeRange: string[] = [
    dayjs(new Date()).add(-1, 'd').format('YYYY-MM-DD'),
    dayjs(new Date()).format('YYYY-MM-DD'),
  ];

  activeTab = ETelemetryDataType.trace;
  tabList = [
    {
      name: ETelemetryDataType.metric,
      label: window.i18n.tc('指标'),
      status: 'disabled',
      disabledTips: window.i18n.tc('指标数据未开启'),
      noDataTips: window.i18n.tc('指标无最新数据'),
    },
    {
      name: ETelemetryDataType.log,
      label: window.i18n.tc('日志'),
      status: 'disabled',
      disabledTips: window.i18n.tc('日志数据未开启'),
      noDataTips: window.i18n.tc('日志无最新数据'),
    },
    {
      name: ETelemetryDataType.trace,
      label: window.i18n.tc('调用链'),
      status: 'disabled',
      disabledTips: window.i18n.tc('调用链数据未开启'),
      noDataTips: window.i18n.tc('调用链无最新数据'),
    },
    {
      name: ETelemetryDataType.profiling,
      label: window.i18n.tc('性能分析'),
      status: 'disabled',
      disabledTips: window.i18n.tc('性能分析数据未开启'),
      noDataTips: window.i18n.tc('性能分析无最新数据'),
    },
  ];

  // 派发到子孙组件内的视图配置变量
  // 视图变量
  @ProvideReactive('viewOptions') viewOptions: IViewOptions = {};
  // 时间间隔
  @ProvideReactive('timeRange') timeRange: TimeRangeType = ['now-6h', 'now'];
  /** 时区 */
  @ProvideReactive('timezone') timezone: string = getDefaultTimezone();
  // 对比的时间
  @ProvideReactive('timeOffset') timeOffset: string[] = [];

  dataStatusMap = {
    [ETelemetryDataType.metric]: 'disabled',
    [ETelemetryDataType.log]: 'disabled',
    [ETelemetryDataType.trace]: 'disabled',
    [ETelemetryDataType.profiling]: 'disabled',
  };
  dataStatusLoading = false;

  created() {
    this.timezone = getDefaultTimezone();
    this.getDataStatus();
  }

  /**
   * @description 获取tab状态数据
   */
  async getDataStatus() {
    this.dataStatusLoading = true;
    const endTime = dayjs().unix();
    const startTime = endTime - 60 * 5;
    const data = await dataStatus(this.appInfo.application_id, {
      start_time: startTime,
      end_time: endTime,
    }).catch(() => this.dataStatusMap);
    this.dataStatusMap = data;
    for (const tab of this.tabList) {
      tab.status = this.dataStatusMap[tab.name];
    }
    if (this.tabList.find(item => item.name === this.activeTab)?.status === 'disabled') {
      this.activeTab = this.tabList.find(item => item.status !== 'disabled')?.name || ETelemetryDataType.trace;
    }
    this.dataStatusLoading = false;
    this.handleChangeActiveTab(this.activeTab);
  }

  /**
   * @desc 日期范围改变
   * @param { array } date 日期范围
   */
  handleTimeRangeChange(date) {
    this.timeRange = date;
    this.getDataStatus();
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
          {this.dataStatusLoading ? (
            <div class='skeleton-element w-300 h-32' />
          ) : (
            <TabList
              activeTab={this.activeTab}
              tabList={this.tabList}
              onChange={this.handleChangeActiveTab}
            />
          )}
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
