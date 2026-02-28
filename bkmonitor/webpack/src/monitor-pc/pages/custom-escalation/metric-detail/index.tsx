/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { Component, Provide, ProvideReactive, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import DashboardTools from 'monitor-pc/pages/monitor-k8s/components/dashboard-tools';
import customEscalationViewStore from 'monitor-pc/store/modules/custom-escalation-view';

import PageHeadr from './components/page-header/index';
import ViewMain from './components/view-main';
import ViewTab from './components/view-tab/index';

import type { getSceneView } from '../service';
import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';

import './index.scss';

type GetSceneViewParams = Parameters<typeof getSceneView>[0];
@Component
export default class NewMetricView extends tsc<object> {
  currentView = 'default';
  dimenstionParams: GetSceneViewParams | null = null;
  showStatisticalValue = false;
  loading = true;
  viewColumn = 2;
  cacheTimeRange = [];
  asideWidth = 220; // 侧边栏初始化宽度
  metricTimeRange: TimeRangeType = [this.startTime, this.endTime];
  @Provide('handleUpdateQueryData') handleUpdateQueryData = undefined;
  @Provide('enableSelectionRestoreAll') enableSelectionRestoreAll = true;
  @ProvideReactive('showRestore') showRestore = false;
  @ProvideReactive('refreshInterval') refreshInterval = -1;

  @Provide('handleChartDataZoom')
  handleChartDataZoom(value) {
    if (JSON.stringify(this.metricTimeRange) !== JSON.stringify(value)) {
      this.cacheTimeRange = JSON.parse(JSON.stringify(this.metricTimeRange));
      this.metricTimeRange = value;
      this.showRestore = true;
    }
  }
  @Provide('handleRestoreEvent')
  handleRestoreEvent() {
    this.metricTimeRange = JSON.parse(JSON.stringify(this.cacheTimeRange));
    this.showRestore = false;
  }

  get timeSeriesGroupId() {
    return Number(this.$route.params.id);
  }

  get startTime() {
    return customEscalationViewStore.startTime;
  }

  get endTime() {
    return customEscalationViewStore.endTime;
  }

  get metricsData() {
    return customEscalationViewStore.currentSelectedMetricList.map(item => {
      return {
        name: item.metric_name,
        scope_name: item.scope_name,
      };
    });
  }

  get graphConfigParams() {
    return {
      limit: {
        function: 'top' as const, // top/bottom
        limit: 50, // 0不限制
      },
      view_column: 2,
      ...this.dimenstionParams,
      metrics: this.metricsData,
    };
  }

  @Watch('timeSeriesGroupId')
  timeSeriesGroupIdChange() {
    this.loading = true;
  }

  async handleSuccess() {
    this.loading = false;
  }

  handleTimeRangeChange(timeRange: TimeRangeType) {
    customEscalationViewStore.updateTimeRange(timeRange);
    this.metricTimeRange = timeRange;
  }
  // 刷新视图
  handleImmediateRefresh() {
    this.dimenstionParams = Object.freeze({ ...this.dimenstionParams });
  }

  handleDimensionParamsChange(payload: GetSceneViewParams) {
    this.dimenstionParams = Object.freeze(payload);
  }

  handleMetricsSelectReset() {
    this.dimenstionParams = null;
  }
  handleRefreshChange(value: number) {
    this.refreshInterval = value;
  }
  handleOpenSideslider() {
    // 打开指标管理操作面板
  }

  created() {
    const routerQuery = this.$route.query as Record<string, string>;
    this.currentView = routerQuery.viewTab || 'default';
  }

  render() {
    return (
      <div class='bk-monitor-new-metric-view'>
        <PageHeadr>
          <DashboardTools
            isSplitPanel={false}
            refreshInterval={this.refreshInterval}
            showListMenu={false}
            timeRange={this.metricTimeRange}
            onImmediateRefresh={this.handleImmediateRefresh}
            onRefreshChange={this.handleRefreshChange}
            onTimeRangeChange={this.handleTimeRangeChange}
          />
        </PageHeadr>
        <div
          key={this.timeSeriesGroupId}
          v-bkloading={{ isLoading: this.loading }}
        >
          {!this.loading && (
            <ViewTab
              v-model={this.currentView}
              graphConfigPayload={this.graphConfigParams}
              onPayloadChange={this.handleDimensionParamsChange}
            />
          )}
          <ViewMain
            config={this.graphConfigParams}
            currentView={this.currentView}
            dimenstionParams={this.dimenstionParams}
            metricTimeRange={this.metricTimeRange}
            timeSeriesGroupId={this.timeSeriesGroupId}
            onCustomTsMetricGroups={this.handleSuccess}
            onDimensionParamsChange={this.handleDimensionParamsChange}
            onResetMetricsSelect={this.handleMetricsSelectReset}
          />
        </div>
      </div>
    );
  }
}
