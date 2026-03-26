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

import { Component, Emit, Prop, ProvideReactive, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import customEscalationViewStore from 'monitor-pc/store/modules/custom-escalation-view';

import {
  // customTimeSeriesList, // 详情页
  getCustomTsDimensionValues, // 详情页
  getCustomTsGraphConfig, // 详情页
  getCustomTsMetricAggInfo,
  getCustomTsMetricGroups, // 详情页
  getSceneView, // 详情页
  modifyCustomTsFields, // 详情页
} from '../../../service';
import HeaderBox from './components/header-box';
import MetricsSelect from './components/metrics-select';
import PanelChartView from './components/panel-chart-view';
import ViewColumn from './components/view-column';

import type { ChartSettingsParams, IMetricAnalysisConfig, RequestHandlerMap } from '../../type';
import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';

import './index.scss';

type GetSceneViewParams = Parameters<typeof getSceneView>[0];

interface IEmit {
  onCustomTsMetricGroups: (payload: any) => void;
  onDimensionParamsChange: (payload: GetSceneViewParams) => void;
  onMetricManage?: (tab: 'dimension' | 'metric') => void;
  onResetMetricsSelect: () => void;
}

interface IProps {
  config?: IMetricAnalysisConfig | null;
  currentView?: string;
  dimenstionParams?: GetSceneViewParams | null;
  isApm?: boolean;
  metricTimeRange: TimeRangeType;
  requestMap?: object;
  timeSeriesGroupId?: number;
}

const ASIDE_WIDTH_SETTING_KEY = 'ASIDE_WIDTH_SETTING_KEY';
@Component
export default class ViewContent extends tsc<IProps, IEmit> {
  @Prop({ type: Array, default: () => [] }) readonly metricTimeRange: TimeRangeType;
  @Prop({ type: Number, default: -1 }) readonly timeSeriesGroupId: IProps['timeSeriesGroupId'];
  @Prop({ type: String, default: 'default' }) readonly currentView: IProps['currentView'];
  @Prop({ type: Object, default: null }) readonly dimenstionParams: IProps['dimenstionParams'];
  @Prop({ type: Boolean, default: false }) readonly isApm: IProps['isApm'];
  @Prop({ type: Object, default: null }) readonly config: IProps['config'];
  @Prop({
    default: () => ({
      getSceneView,
      getCustomTsDimensionValues,
      getCustomTsGraphConfig,
      getCustomTsMetricAggInfo,
      getCustomTsMetricGroups,
      modifyCustomTsFields,
    }),
  })
  requestMap: RequestHandlerMap;

  @ProvideReactive('requestHandlerMap') requestHandlerMap: RequestHandlerMap;

  @Ref('metricsSelectRef') readonly metricsSelectRef;

  @Emit('metricManage')
  handleMetricManage(tab: 'dimension' | 'metric') {
    return tab;
  }

  @Emit('resetMetricsSelect')
  handleMetricsSelectReset() {}

  @Emit('dimensionParamsChange')
  handleDimensionParamsChange(payload: GetSceneViewParams) {
    return payload;
  }

  @Emit('customTsMetricGroups')
  handleCustomTsMetricGroups() {}

  // 展示统计值
  state = {
    showStatisticalValue: false,
    viewColumn: 2,
    autoYAxis: true,
    decimal: 0,
  };

  asideWidth = 220; // 侧边栏初始化宽度

  selectedMetricIds: (number | string)[] = [];

  get chartSettingParams() {
    return {
      autoYAxis: this.state.autoYAxis,
      decimal: this.state.decimal,
    };
  }

  @ProvideReactive('isApm')
  get isApmMode() {
    return this.isApm;
  }

  @ProvideReactive('timeSeriesGroupId')
  get groupId() {
    return this.timeSeriesGroupId;
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

  @Watch('requestMap', { immediate: true })
  setRequestHandlerMap() {
    this.requestHandlerMap = this.requestMap;
  }

  @ProvideReactive('timeRange')
  get timeRange() {
    return this.metricTimeRange;
  }

  @ProvideReactive('appName')
  get appName() {
    return this.isApmMode ? (this.$route.query['filter-app_name'] as string) : '';
  }

  @ProvideReactive('serviceName')
  get serviceName() {
    return this.isApmMode ? (this.$route.query['filter-service_name'] as string) : '';
  }

  async getCustomTsMetricGroupsData() {
    const needParseUrl = Boolean(this.$route.query?.viewPayload);
    if (this.timeSeriesGroupId < 1 && !this.isApmMode) {
      return [];
    }
    try {
      const params = {
        time_series_group_id: Number(this.timeSeriesGroupId),
      };
      if (this.isApmMode) {
        delete params.time_series_group_id;
        Object.assign(params, {
          apm_app_name: this.appName,
          apm_service_name: this.serviceName,
        });
      }
      const result = await this.requestHandlerMap.getCustomTsMetricGroups(params);
      customEscalationViewStore.updateMetricGroupList(result.metric_groups);
      if (!needParseUrl && this.isApmMode) {
        const metricGroup = result.metric_groups;
        const defaultSelectedData = {
          groupName: metricGroup[0]?.name || '',
          metricsName: [metricGroup[0]?.metrics[0]?.metric_name || ''],
        };
        customEscalationViewStore.updateCurrentSelectedGroupAndMetricNameList(
          metricGroup.length > 0 && metricGroup[0].metrics.length > 0 ? [defaultSelectedData] : []
        );
      }
    } finally {
      this.handleCustomTsMetricGroups();
    }
  }

  handleChartSettingChange(payload: ChartSettingsParams) {
    this.state = { ...this.state, ...payload };
  }

  handleResetAsideWidth(width: number) {
    localStorage.setItem(ASIDE_WIDTH_SETTING_KEY, String(width));
    // 更新分组组件的虚拟滚动宽度
    this.metricsSelectRef?.metricGroupRef?.virtualScrollRef?.resize();
  }

  loadGraphConfigMetricIds({ init, metricIds }: { init: boolean; metricIds: (number | string)[] }) {
    if (init) {
      this.selectedMetricIds = metricIds;
    } else {
      this.selectedMetricIds.push(...metricIds);
    }
    this.fetchAggInfo();
  }

  //  获取过滤条件下拉和维度下拉
  async fetchAggInfo() {
    const selectedMetricList = customEscalationViewStore.currentSelectedMetricList;

    if (selectedMetricList.length === 0) {
      customEscalationViewStore.updateAggInfo({
        all_dimensions: [],
        common_dimensions: [],
      });
      return;
    }

    const aggInfoParams = {
      metric_ids: this.selectedMetricIds,
    };

    if (this.isApm && this.appName && this.serviceName) {
      Object.assign(aggInfoParams, {
        apm_app_name: this.appName,
        apm_service_name: this.serviceName,
      });
    } else {
      Object.assign(aggInfoParams, {
        time_series_group_id: Number(this.timeSeriesGroupId),
      });
    }

    try {
      const aggInfoResult = await this.requestHandlerMap.getCustomTsMetricAggInfo(aggInfoParams);
      customEscalationViewStore.updateAggInfo({
        all_dimensions: aggInfoResult.all_dimensions,
        common_dimensions: aggInfoResult.common_dimensions,
      });
    } catch (error) {
      console.error(error);
    }
  }

  created() {
    const routerQuery = this.$route.query as Record<string, string>;
    if (routerQuery.viewColumn && routerQuery.showStatisticalValue) {
      this.state = {
        viewColumn: Number.parseInt(routerQuery.viewColumn, 10) || 2,
        showStatisticalValue: routerQuery.showStatisticalValue === 'true',
        autoYAxis: routerQuery.autoYAxis === 'true',
        decimal: Number(routerQuery.decimal) || 0,
      };
    }
    // 分组侧栏宽度
    const asideWidth = localStorage.getItem(ASIDE_WIDTH_SETTING_KEY);
    this.asideWidth = Number(asideWidth || 220);
    this.getCustomTsMetricGroupsData();
  }

  render() {
    return (
      <bk-resize-layout
        style='height: calc(100vh - 140px - var(--notice-alert-height))'
        collapsible={true}
        initial-divide={this.asideWidth}
        max={550}
        min={200}
        on-after-resize={this.handleResetAsideWidth}
      >
        <template slot='aside'>
          <MetricsSelect
            ref='metricsSelectRef'
            isApm={this.isApm}
            viewTab={this.currentView}
            onMetricManage={this.handleMetricManage}
            onReset={this.handleMetricsSelectReset}
          />
        </template>
        <template slot='main'>
          <HeaderBox
            key={this.currentView}
            chartSettingParams={this.chartSettingParams}
            dimenstionParams={this.dimenstionParams}
            onChange={this.handleDimensionParamsChange}
            onChartSettingChange={this.handleChartSettingChange}
            onMetricManage={this.handleMetricManage}
          >
            <template slot='actionExtend'>
              <bk-checkbox
                style='margin-right: 14px;'
                v-model={this.state.autoYAxis}
              >
                {this.$t('Y轴最小值自适应')}
              </bk-checkbox>
              <bk-checkbox v-model={this.state.showStatisticalValue}>{this.$t('展示统计值')}</bk-checkbox>
              <ViewColumn
                style='margin-left: 32px;'
                v-model={this.state.viewColumn}
              />
            </template>
          </HeaderBox>
          <div class='metric-view-dashboard-container'>
            <PanelChartView
              chartSettingParams={this.chartSettingParams}
              config={this.config}
              showStatisticalValue={this.state.showStatisticalValue}
              viewColumn={this.state.viewColumn}
              onLoadGraphConfigMetricIds={this.loadGraphConfigMetricIds}
              onMetricManage={this.handleMetricManage}
            />
          </div>
        </template>
      </bk-resize-layout>
    );
  }
}
