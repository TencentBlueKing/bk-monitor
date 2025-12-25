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

import {
  createOrUpdateGroupingRule,
  customTimeSeriesDetail,
  customTimeSeriesList,
  customTsGroupingRuleList,
  getCustomTimeSeriesLatestDataByFields,
  getCustomTsDimensionValues,
  getCustomTsFields,
  getCustomTsGraphConfig,
  getCustomTsMetricGroups,
  getSceneView,
  modifyCustomTsFields,
} from '../service';
// import HeaderBox from './components/header-box/index';
// import MetricsSelect from './components/metrics-select/index';
import PageHeadr from './components/page-header/index';
// import PanelChartView from './components/panel-chart-view';
// import ViewColumn from './components/view-column/index';
import ViewMain from './components/view-main';
import ViewTab from './components/view-tab/index';

import type { RequestHandlerMap } from './type';
import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';

import './index.scss';

type GetSceneViewParams = Parameters<typeof getSceneView>[0];

@Component
export default class NewMetricView extends tsc<object> {
  currentView = 'default';
  dimenstionParams: GetSceneViewParams | null = null;
  showStatisticalValue = false;
  isCustomTsMetricGroupsLoading = true;
  viewColumn = 2;
  // state = {
  //   showStatisticalValue: false,
  //   viewColumn: 2,
  // };
  cacheTimeRange = [];
  @ProvideReactive('timeRange') timeRange: TimeRangeType = [this.startTime, this.endTime];
  @Provide('handleUpdateQueryData') handleUpdateQueryData = undefined;
  @Provide('enableSelectionRestoreAll') enableSelectionRestoreAll = true;
  @ProvideReactive('showRestore') showRestore = false;
  @ProvideReactive('containerScrollTop') containerScrollTop = 0;
  @ProvideReactive('refreshInterval') refreshInterval = -1;
  @Provide('requestHandlerMap') requestHandlerMap: RequestHandlerMap = {
    getCustomTsMetricGroups,
    customTimeSeriesList,
    customTimeSeriesDetail, // 详情页面暂未使用过
    getCustomTsFields, // 详情页面暂未使用
    modifyCustomTsFields,
    createOrUpdateGroupingRule, // 详情页面暂未使用
    customTsGroupingRuleList, // 详情页面暂未使用
    getCustomTimeSeriesLatestDataByFields, // 详情页面暂未使用
    getCustomTsDimensionValues,
    getCustomTsGraphConfig,
    getSceneView,
  };

  @Provide('handleChartDataZoom')
  handleChartDataZoom(value) {
    if (JSON.stringify(this.timeRange) !== JSON.stringify(value)) {
      this.cacheTimeRange = JSON.parse(JSON.stringify(this.timeRange));
      this.timeRange = value;
      this.showRestore = true;
    }
  }
  @Provide('handleRestoreEvent')
  handleRestoreEvent() {
    this.timeRange = JSON.parse(JSON.stringify(this.cacheTimeRange));
    this.showRestore = false;
  }

  @Watch('isCustomTsMetricGroupsLoading')
  isCustomTsMetricGroupsLoadingChange(v) {
    if (!v) {
      this.$nextTick(() => {
        this.initScroll();
      });
    }
  }
  initScroll() {
    const container = document.querySelector('.metric-view-dashboard-container') as HTMLElement;
    if (container) {
      container.removeEventListener('scroll', this.handleScroll);
      container.addEventListener('scroll', this.handleScroll);
    }
  }

  removeScrollEvent() {
    const container = document.querySelector('.metric-view-dashboard-container') as HTMLElement;
    if (container) {
      container.removeEventListener('scroll', this.handleScroll);
    }
  }

  handleScroll(e) {
    if (e.target.scrollTop > 0) {
      this.containerScrollTop = e.target.scrollTop;
    }
  }

  @ProvideReactive('timeSeriesGroupId')
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
      // start_time: this.startTime,
      // end_time: this.endTime,
      // metrics: customEscalationViewStore.currentSelectedMetricNameList,
      metrics: this.metricsData,
    };
  }

  // @Watch('state', { deep: true })
  // stateChange() {
  //   this.$router.replace({
  //     query: {
  //       ...this.$route.query,
  //       ...(this.state as Record<string, any>),
  //       key: `${Date.now()}`, // query 相同时 router.replace 会报错
  //     },
  //   });
  // }

  @Watch('timeSeriesGroupId')
  timeSeriesGroupIdChange() {
    this.currentTimeSeriesGroupId = this.timeSeriesGroupId;
    this.isCustomTsMetricGroupsLoading = true;
  }

  async handleSuccess() {
    this.isCustomTsMetricGroupsLoading = false;
  }

  // async getCustomTsMetricGroups() {
  //   const needParseUrl = Boolean(this.$route.query.viewPayload);
  //   this.isCustomTsMetricGroupsLoading = true;
  //   try {
  //     const result = await getCustomTsMetricGroups({
  //       time_series_group_id: this.timeSeriesGroupId,
  //       // is_mock: true,
  //     });
  //     customEscalationViewStore.updateMetricGroupList(result.metric_groups);
  //     if (!needParseUrl) {
  //       const metricGroup = result.metric_groups;
  //       const defaultSelectedData = {
  //         groupName: metricGroup[0]?.name || '',
  //         metricsName: [metricGroup[0]?.metrics[0]?.metric_name || ''],
  //       };
  //       customEscalationViewStore.updateCurrentSelectedGroupAndMetricNameList(
  //         metricGroup.length > 0 && metricGroup[0].metrics.length > 0 ? [defaultSelectedData] : []
  //       );
  //     }
  //   } finally {
  //     this.isCustomTsMetricGroupsLoading = false;
  //   }
  // }

  handleTimeRangeChange(timeRange: TimeRangeType) {
    customEscalationViewStore.updateTimeRange(timeRange);
    this.timeRange = timeRange;
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

  created() {
    const routerQuery = this.$route.query as Record<string, string>;
    this.currentView = routerQuery.viewTab || 'default';
    // this.state = {
    //   viewColumn: Number.parseInt(routerQuery.viewColumn, 10) || 2,
    //   showStatisticalValue: routerQuery.showStatisticalValue === 'true',
    // };
  }

  beforeDestroy() {
    this.removeScrollEvent();
  }

  render() {
    return (
      <div class='bk-monitor-new-metric-view'>
        <PageHeadr>
          <DashboardTools
            isSplitPanel={false}
            refreshInterval={this.refreshInterval}
            showListMenu={false}
            timeRange={this.timeRange}
            onImmediateRefresh={this.handleImmediateRefresh}
            onRefreshChange={this.handleRefreshChange}
            onTimeRangeChange={this.handleTimeRangeChange}
          />
        </PageHeadr>
        <div
          key={this.timeSeriesGroupId}
          v-bkloading={{ isLoading: this.isCustomTsMetricGroupsLoading }}
        >
          {!this.isCustomTsMetricGroupsLoading && (
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
            onCustomTsMetricGroups={this.handleSuccess}
            onDimensionParamsChange={this.handleDimensionParamsChange}
            onResetMetricsSelect={this.handleMetricsSelectReset}
          />
          {/* <bk-resize-layout
              style='height: calc(100vh - 140px - var(--notice-alert-height))'
              collapsible={true}
              initial-divide={220}
              max={550}
              min={200}
            >
              <template slot='aside'>
                <MetricsSelect onReset={this.handleMetricsSelectReset} />
              </template>
              <template slot='main'>
                <HeaderBox
                  key={this.currentView}
                  dimenstionParams={this.dimenstionParams}
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
                    ref='panelChartView'
                    config={this.graphConfigParams as any}
                    showStatisticalValue={this.state.showStatisticalValue}
                    viewColumn={this.state.viewColumn}
                  />
                </div>
              </template>
            </bk-resize-layout> */}
        </div>
      </div>
    );
  }
}
