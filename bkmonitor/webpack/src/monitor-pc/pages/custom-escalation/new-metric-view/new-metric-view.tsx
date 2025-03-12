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
import { Component, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import customEscalationViewStore from '@store/modules/custom-escalation-view';
import DashboardTools from 'monitor-pc/pages/monitor-k8s/components/dashboard-tools';

import HeaderBox from './components/header-box/index';
import MetricsSelect from './components/metrics-select/index';
import PageHeadr from './components/page-header/index';
import ViewTab from './components/view-tab/index';
import PanelChartView from './metric-chart-view/panel-chart-view';

import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';

import './new-metric-view.scss';

@Component
export default class NewMetricView extends tsc<object> {
  currentView = '';
  dimenstionParams: Record<string, any> = {};
  startTime = 'now-1h';
  endTime = 'now';

  get timeSeriesGroupId() {
    return this.$route.params.id;
  }

  get graphConfigParams() {
    const [startTime, endTime] = customEscalationViewStore.timeRangTimestamp;
    return {
      ...this.dimenstionParams,
      start_time: startTime,
      end_time: endTime,
      time_series_group_id: this.timeSeriesGroupId,
    };
  }

  @Watch('$route')
  routerChange() {
    console.log('from rout change = ', this.$route);
    this.dimenstionParams = {};
  }

  handleTimeRangeChange(timeRange: TimeRangeType) {
    // const [startTime, endTime] = timeRange;
    // this.startTime = startTime;
    // this.endTime = endTime;
    // this.$router.replace({
    //   query: {
    //     ...this.$route.query,
    //     startTime,
    //     endTime,
    //   },
    // });
    customEscalationViewStore.updateTimeRange(timeRange);
  }

  handleDimensionParamsChange(payload: any) {
    this.dimenstionParams = Object.freeze(payload);
  }

  render() {
    return (
      <div class='bk-monitor-new-metric-view'>
        <PageHeadr>
          <DashboardTools
            isSplitPanel={false}
            showListMenu={false}
            timeRange={[this.startTime, this.endTime]}
            onTimeRangeChange={this.handleTimeRangeChange}
          />
        </PageHeadr>
        <div key={this.timeSeriesGroupId}>
          <ViewTab
            v-model={this.currentView}
            graphConfigPayload={this.dimenstionParams}
            onPayloadChange={this.handleDimensionParamsChange}
          >
            <bk-resize-layout
              key={this.currentView}
              style='height: calc(100vh - 140px - var(--notice-alert-height))'
              initial-divide={220}
            >
              <template slot='aside'>
                <MetricsSelect />
              </template>
              <template slot='main'>
                <HeaderBox
                  dimenstionParams={this.dimenstionParams}
                  commonDimensionEnable
                  groupBySplitEnable
                  onChange={this.handleDimensionParamsChange}
                />
                <div class='metric-view-dashboard-container'>
                  <PanelChartView config={this.graphConfigParams as any} />
                </div>
              </template>
            </bk-resize-layout>
          </ViewTab>
        </div>
      </div>
    );
  }
}
