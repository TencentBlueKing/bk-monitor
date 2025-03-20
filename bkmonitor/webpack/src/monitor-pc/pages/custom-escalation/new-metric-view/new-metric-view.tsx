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
import ViewColumn from './components/view-column/index';
import ViewTab from './components/view-tab/index';
import PanelChartView from './metric-chart-view/panel-chart-view';

import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';

import './new-metric-view.scss';

@Component
export default class NewMetricView extends tsc<object> {
  currentView = 'default';
  dimenstionParams: Record<string, any> = {};
  showStatisticalValue = false;
  viewColumn = 3;
  state = {
    showStatisticalValue: false,
    viewColumn: 3,
  };

  get timeSeriesGroupId() {
    return Number(this.$route.params.id);
  }

  get startTime() {
    return customEscalationViewStore.startTime;
  }

  get endTime() {
    return customEscalationViewStore.endTime;
  }

  get graphConfigParams() {
    return {
      limit: {
        function: 'top', // top/bottom
        limit: 10, // 0不限制
      },
      view_column: 1,
      ...this.dimenstionParams,
      start_time: this.startTime,
      end_time: this.endTime,
      metrics: customEscalationViewStore.currentSelectedMetricNameList,
    };
  }

  @Watch('state', { deep: true })
  stateChange() {
    this.$router.replace({
      query: {
        ...this.$route.query,
        ...(this.state as Record<string, any>),
        key: `${Date.now()}`, // query 相同时 router.replace 会报错
      },
    });
  }

  handleTimeRangeChange(timeRange: TimeRangeType) {
    customEscalationViewStore.updateTimeRange(timeRange);
  }

  handleDimensionParamsChange(payload: any) {
    this.dimenstionParams = Object.freeze(payload);
  }

  handleMetricsSelectReset() {
    this.dimenstionParams = {};
  }

  created() {
    const routerQuery = this.$route.query as Record<string, string>;
    this.currentView = routerQuery.viewTab || 'default';
    this.state = {
      viewColumn: Number.parseInt(routerQuery.viewColumn) || 3,
      showStatisticalValue: routerQuery.showStatisticalValue === 'true',
    };
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
            graphConfigPayload={this.graphConfigParams}
            onPayloadChange={this.handleDimensionParamsChange}
          >
            <bk-resize-layout
              style='height: calc(100vh - 140px - var(--notice-alert-height))'
              collapsible={true}
              initial-divide={220}
            >
              <template slot='aside'>
                <MetricsSelect onReset={this.handleMetricsSelectReset} />
              </template>
              <template slot='main'>
                <HeaderBox
                  key={this.currentView}
                  dimenstionParams={this.dimenstionParams}
                  commonDimensionEnable
                  groupBySplitEnable
                  onChange={this.handleDimensionParamsChange}
                >
                  <template slot='actionExtend'>
                    <bk-checkbox v-model={this.state.showStatisticalValue}>{this.$t('展示统计值')}</bk-checkbox>
                    <ViewColumn
                      style='margin-left: 32px;'
                      v-model={this.state.viewColumn}
                    />
                  </template>
                </HeaderBox>
                <div class='metric-view-dashboard-container'>
                  <PanelChartView
                    config={this.graphConfigParams as any}
                    showStatisticalValue={this.state.showStatisticalValue}
                    viewColumn={this.state.viewColumn}
                  />
                </div>
              </template>
            </bk-resize-layout>
          </ViewTab>
        </div>
      </div>
    );
  }
}
