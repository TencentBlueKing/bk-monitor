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
import { Component, InjectReactive, ProvideReactive, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import _ from 'lodash';
import { asyncDebounceDecorator } from 'monitor-common/utils/debounce-decorator';

import customEscalationViewStore from '../../../store/modules/custom-escalation-view';
import HeaderBox from './components/header-box/index';
import MetricsSelect from './components/metrics-select/index';
import ViewColumn from './components/view-column';
import PanelChartView from './metric-chart-view/panel-chart-view';
import { optimizedDeepEqual } from './metric-chart-view/utils';
import { getCustomTsMetricGroups } from './services/scene_view_new';

import type { TimeRangeType } from '../../../components/time-range/time-range';
import type { IMetricAnalysisConfig } from './type';
import type { IViewOptions } from '@/pages/monitor-k8s/typings/book-mark';

import './new-metric-view.scss';

@Component
export default class ApmCustomMetric extends tsc<object> {
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
  @InjectReactive('viewOptions') readonly viewOptions: IViewOptions;
  @ProvideReactive('routeParams') routeParams: Record<string, any> = {};
  @InjectReactive('timeRange') readonly timeRange!: TimeRangeType;

  @ProvideReactive('containerScrollTop') containerScrollTop = 0;

  @Watch('timeRange')
  handleTimeRangeChange(timeRange: TimeRangeType) {
    customEscalationViewStore.updateTimeRange(timeRange);
  }

  @Watch('isCustomTsMetricGroupsLoading')
  isCustomTsMetricGroupsLoadingChange(v) {
    if (!v) {
      this.$nextTick(() => {
        this.initScroll();
      });
    }
  }
  @Watch('graphConfigParams')
  graphConfigPayloadChange(val, old) {
    if (optimizedDeepEqual(val, old)) {
      return;
    }
    this.$router.replace({
      query: {
        ...this.$route.query,
        key: `${Date.now()}`,
        viewTab: 'default',
        viewPayload: JSON.stringify(this.graphConfigParams),
      },
    });
  }
  @Watch('viewOptions', { immediate: true })
  viewOptionsChange() {
    this.routeParams = {
      ...this.routeParams,
      idParams: {
        apm_app_name: this.viewOptions.filters.app_name,
        apm_service_name: this.viewOptions.filters.service_name,
      },
    };
  }

  initScroll() {
    const container = document.querySelector('.metric-view-dashboard-container');
    if (container) {
      container.removeEventListener('scroll', this.handleScroll);
      container.addEventListener('scroll', this.handleScroll);
    }
  }

  removeScrollEvent() {
    const container = document.querySelector('.metric-view-dashboard-container');
    if (container) {
      container.removeEventListener('scroll', this.handleScroll);
    }
  }

  handleScroll(e: MouseEvent) {
    if ((e.target as HTMLElement).scrollTop > 0) {
      this.containerScrollTop = (e.target as HTMLElement).scrollTop;
    }
  }

  get graphConfigParams() {
    return {
      limit: {
        function: 'top', // top/bottom
        limit: 50, // 0不限制
      },
      view_column: 2,
      ...this.dimensionParams,
      metrics: customEscalationViewStore.currentSelectedMetricNameList,
    } as unknown as IMetricAnalysisConfig;
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

  @Watch('routeParams.idParams')
  timeSeriesGroupIdChange() {
    this.getCustomTsMetricGroups();
  }

  @asyncDebounceDecorator(300)
  async getCustomTsMetricGroups() {
    this.isCustomTsMetricGroupsLoading = true;
    try {
      const result = await getCustomTsMetricGroups({
        ...this.routeParams.idParams,
      });

      customEscalationViewStore.updateCommonDimensionList(result.common_dimensions);
      customEscalationViewStore.updateMetricGroupList(result.metric_groups);

      if (!this.handleSetRoutePayload()) {
        const metricGroup = result.metric_groups;
        customEscalationViewStore.updateCurrentSelectedMetricNameList(
          metricGroup.length > 0 && metricGroup[0].metrics.length > 0 ? [metricGroup[0].metrics[0].metric_name] : []
        );
      }
    } finally {
      this.isCustomTsMetricGroupsLoading = false;
    }
  }

  // 刷新视图
  handleImmediateRefresh() {
    this.dimensionParams = Object.freeze({ ...this.dimensionParams });
  }

  handleDimensionParamsChange(payload: Record<string, any>) {
    this.dimensionParams = Object.freeze(payload);
  }

  handleMetricsSelectReset() {
    this.dimensionParams = {};
  }

  parseUrlPayload() {
    if (!this.$route.query.viewPayload) {
      return undefined;
    }
    const payload = JSON.parse((this.$route.query.viewPayload as string) || '');
    return _.isObject(payload) ? payload : undefined;
  }

  handleSetRoutePayload() {
    // url 上面附带的参数优先级高
    const urlPayload = this.parseUrlPayload() as IMetricAnalysisConfig;
    if (!urlPayload) {
      return false;
    }
    // 视图保存的 metric 可能被隐藏，需要过滤掉不存在 metric
    const allMetricNameMap = customEscalationViewStore.metricGroupList.reduce<Record<string, boolean>>(
      (result, groupItem) => {
        for (const metricItem of groupItem.metrics) {
          Object.assign(result, {
            [metricItem.metric_name]: true,
          });
        }
        return result;
      },
      {}
    );
    const realMetricNameList = _.filter(urlPayload.metrics, item => allMetricNameMap[item]);
    // 更新 Store 上的 currentSelectedMetricNameList
    customEscalationViewStore.updateCurrentSelectedMetricNameList(realMetricNameList);
    this.dimensionParams = Object.freeze(urlPayload);
    return true;
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
          '--apm-tab-height': '12px',
        }}
        class='bk-monitor-new-metric-view'
      >
        <div
          class='bk-monitor-new-metric-view-content'
          v-bkloading={{ isLoading: this.isCustomTsMetricGroupsLoading }}
        >
          {!this.isCustomTsMetricGroupsLoading && (
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
                    config={this.graphConfigParams}
                    showStatisticalValue={this.state.showStatisticalValue}
                    viewColumn={this.state.viewColumn}
                  />
                </div>
              </template>
            </bk-resize-layout>
          )}
        </div>
      </div>
    );
  }
}
