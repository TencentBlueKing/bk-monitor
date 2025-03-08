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
import { Component } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import DashboardTools from 'monitor-pc/pages/monitor-k8s/components/dashboard-tools';

import HeaderBox, { type IProps as IHeaderBoxProps } from './components/header-box/index';
import MetricsSelect from './components/metrics-select/index';
import PageHeadr from './components/page-header/index';
import ViewSave from './components/view-save';
import ViewTab from './components/view-tab/index';
import PanelChartView from './metric-chart-view/panel-chart-view';

import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';

import './new-metric-view.scss';

@Component
export default class NewMetricView extends tsc<object> {
  view = 'default';
  commonDimensionList: IHeaderBoxProps['commonDimensionList'] = [];
  metricsList: IHeaderBoxProps['metricsList'] = [];
  bkBizId = 0;
  timeSeriesGroupId = 0;
  dimenstionParams: Record<string, any> = {};
  startTime = '';
  endTime = '';

  handleTimeRangeChange(timeRange: TimeRangeType) {
    const [startTime, endTime] = timeRange;
    this.startTime = startTime;
    this.endTime = endTime;
  }

  handleTabChange(value: string) {
    this.view = value;
  }

  handleMetricsChange(payload: {
    commonDimensionList: IHeaderBoxProps['commonDimensionList'];
    metricsList: IHeaderBoxProps['metricsList'];
  }) {
    this.commonDimensionList = payload.commonDimensionList;
    this.metricsList = payload.metricsList;
  }

  handleHeaderParamsChange(payload: any) {
    this.dimenstionParams = Object.freeze(payload);
  }

  render() {
    return (
      <div class='bk-monitor-new-metric-view'>
        <PageHeadr>
          <DashboardTools
            isSplitPanel={false}
            showListMenu={false}
            onTimeRangeChange={this.handleTimeRangeChange}
          />
        </PageHeadr>
        <div class='metric-view-view-container'>
          <ViewTab />
          <ViewSave />
        </div>
        <bk-resize-layout
          style='height: calc(100vh - 140px - var(--notice-alert-height))'
          initial-divide={220}
        >
          <template slot='aside'>
            <MetricsSelect onChange={this.handleMetricsChange} />
          </template>
          <template slot='main'>
            <HeaderBox
              commonDimensionList={this.commonDimensionList}
              metricsList={this.metricsList}
              onChange={this.handleHeaderParamsChange}
            />
            <div class='metric-view-dashboard-container'>
              {/* <textarea
                style='height: 100px; width: 100%'
                value={JSON.stringify({
                  ...this.dimenstionParams,
                  start_time: this.startTime,
                  end_time: this.endTime,
                  bk_biz_id: this.bkBizId,
                  time_series_group_id: this.timeSeriesGroupId,
                })}
              /> */}
              <PanelChartView columnNum={this.dimenstionParams.view_column} />
            </div>
          </template>
        </bk-resize-layout>
      </div>
    );
  }
}
