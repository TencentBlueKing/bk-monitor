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
import { Component, Prop, Provide, ProvideReactive, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import DashboardTools from 'monitor-pc/pages/monitor-k8s/components/dashboard-tools';

import customEscalationViewStore from '../../../store/modules/custom-escalation-view';
import HeaderBox from './components/header-box/index';
import MetricsSelect from './components/metrics-select/index';
import PageHeadr from './components/page-header/index';
import ViewColumn from './components/view-column/index';
import ViewTab from './components/view-tab/index';
import PanelChartView from './metric-chart-view/panel-chart-view';
import { getCustomTsMetricGroups } from './services/scene_view_new';

import type { IRouteParams } from './type';
import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';

import './new-metric-view.scss';
Component.registerHooks(['beforeRouteEnter']);

@Component
export default class NewMetricView extends tsc<object> {
  @Prop({ required: true, type: String }) readonly id: string;
  currentView = 'default';
  dimensionParams: Record<string, any> = {};
  showStatisticalValue = false;
  isCustomTsMetricGroupsLoading = true;
  viewColumn = 2;
  state = {
    showStatisticalValue: false,
    viewColumn: 2,
  };
  cacheTimeRange = [];
  @ProvideReactive('routeParams') routeParams: Partial<IRouteParams> = {};
  @ProvideReactive('timeRange') timeRange: TimeRangeType = [this.startTime, this.endTime];
  @Provide('handleUpdateQueryData') handleUpdateQueryData = undefined;
  @Provide('enableSelectionRestoreAll') enableSelectionRestoreAll = true;
  @ProvideReactive('showRestore') showRestore = false;
  @ProvideReactive('containerScrollTop') containerScrollTop = 0;
  @ProvideReactive('refreshInterval') refreshInterval = -1;
  @Ref('panelChartView') panelChartView!: PanelChartView;

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
  @Watch('id', { immediate: true })
  idChange() {
    this.routeParams = {
      id: this.id,
      idParams: {
        time_series_group_id: Number(this.id),
        apm_app_name: undefined,
        apm_service_name: undefined,
      },
    };
    if (!this.id) {
      this.$router.push('/custom-metric');
      return;
    }
    this.getCustomTsMetricGroups();
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
        limit: 50, // 0不限制
      },
      view_column: 2,
      ...this.dimensionParams,
      // start_time: this.startTime,
      // end_time: this.endTime,
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

  async getCustomTsMetricGroups() {
    const needParseUrl = Boolean(this.$route.query.viewPayload);
    this.isCustomTsMetricGroupsLoading = true;
    try {
      const result = await getCustomTsMetricGroups({
        time_series_group_id: Number(this.id),
      });

      customEscalationViewStore.updateCommonDimensionList(result.common_dimensions);
      customEscalationViewStore.updateMetricGroupList(result.metric_groups);

      if (!needParseUrl) {
        const metricGroup = result.metric_groups;
        customEscalationViewStore.updateCurrentSelectedMetricNameList(
          metricGroup.length > 0 && metricGroup[0].metrics.length > 0 ? [metricGroup[0].metrics[0].metric_name] : []
        );
      }
    } finally {
      this.isCustomTsMetricGroupsLoading = false;
    }
  }

  handleTimeRangeChange(timeRange: TimeRangeType) {
    customEscalationViewStore.updateTimeRange(timeRange);
    this.timeRange = timeRange;
  }
  // 刷新视图
  handleImmediateRefresh() {
    this.dimensionParams = Object.freeze({ ...this.dimensionParams });
  }

  handleDimensionParamsChange(payload: any) {
    this.dimensionParams = Object.freeze(payload);
  }

  handleMetricsSelectReset() {
    this.dimensionParams = {};
  }
  handleRefreshChange(value: number) {
    this.refreshInterval = value;
  }

  created() {
    const routerQuery = this.$route.query as Record<string, string>;
    this.currentView = routerQuery.viewTab || 'default';
    this.state = {
      viewColumn: Number.parseInt(routerQuery.viewColumn, 10) || 2,
      showStatisticalValue: routerQuery.showStatisticalValue === 'true',
    };
  }

  beforeDestroy() {
    this.removeScrollEvent();
  }

  render() {
    return (
      <div
        style={{
          '--apm-tab-height': '32px',
        }}
        class='bk-monitor-new-metric-view'
      >
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
          key={this.id}
          v-bkloading={{ isLoading: this.isCustomTsMetricGroupsLoading }}
        >
          {!this.isCustomTsMetricGroupsLoading && (
            <ViewTab
              v-model={this.currentView}
              graphConfigPayload={this.graphConfigParams}
              onPayloadChange={this.handleDimensionParamsChange}
            >
              <bk-resize-layout
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
                    dimensionParams={this.dimensionParams}
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
              </bk-resize-layout>
            </ViewTab>
          )}
        </div>
      </div>
    );
  }
}
