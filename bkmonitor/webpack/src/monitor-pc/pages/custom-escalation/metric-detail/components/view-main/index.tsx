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

import { Component, Emit, Inject, InjectReactive, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import customEscalationViewStore from 'monitor-pc/store/modules/custom-escalation-view';

import HeaderBox from './components/header-box';
import MetricsSelect from './components/metrics-select';
import PanelChartView from './components/panel-chart-view';
import ViewColumn from './components/view-column';

import type { getSceneView } from '../../../service';
import type { IMetricAnalysisConfig, RequestHandlerMap } from '../../type';

import './index.scss';

type GetSceneViewParams = Parameters<typeof getSceneView>[0];

interface IEmit {
  onCustomTsMetricGroups: (payload: any) => void;
  onDimensionParamsChange: (payload: GetSceneViewParams) => void;
  onOpenSideslider?: () => void;
  onResetMetricsSelect: () => void;
}

interface IProps {
  config?: IMetricAnalysisConfig | null;
  currentView?: string;
  dimenstionParams?: GetSceneViewParams | null;
  isApm?: boolean;
  // timeSeriesGroupId?: number;
}

@Component
export default class ViewContent extends tsc<IProps, IEmit> {
  // @Prop({ type: Number, default: -1 }) readonly timeSeriesGroupId: IProps['timeSeriesGroupId'];
  @Prop({ type: String, default: 'default' }) readonly currentView: IProps['currentView'];
  @Prop({ type: Object, default: null }) readonly dimenstionParams: IProps['dimenstionParams'];
  @Prop({ type: Boolean, default: false }) readonly isApm: IProps['isApm'];
  @Prop({ type: Object, default: null }) readonly config: IProps['config'];
  @InjectReactive('timeSeriesGroupId') readonly timeSeriesGroupId: number;
  @Inject('requestHandlerMap') readonly requestHandlerMap!: RequestHandlerMap;

  @Emit('openSideslider')
  handleSideslider() {}

  @Emit('resetMetricsSelect')
  handleMetricsSelectReset() {}

  @Emit('dimensionParamsChange')
  handleDimensionParamsChange(payload: GetSceneViewParams) {
    return payload;
  }

  @Emit('customTsMetricGroups')
  handleCustomTsMetricGroups(
    payload: Awaited<ReturnType<RequestHandlerMap['getCustomTsMetricGroups']>>['metric_groups']
  ) {
    return payload;
  }

  state = {
    showStatisticalValue: false,
    viewColumn: 2,
  };

  @Watch('state', { deep: true })
  stateChange() {
    // apm嵌入不需要url参数
    if (!this.isApm) {
      this.$router.replace({
        query: {
          ...this.$route.query,
          ...(this.state as Record<string, any>),
          key: `${Date.now()}`, // query 相同时 router.replace 会报错
        },
      });
    }
  }

  async getCustomTsMetricGroupsData() {
    const needParseUrl = Boolean(this.$route.query.viewPayload);
    let metricGroupsData: Awaited<ReturnType<RequestHandlerMap['getCustomTsMetricGroups']>>['metric_groups'] = [];
    if (this.timeSeriesGroupId < 1) {
      return [];
    }
    try {
      const result = await this.requestHandlerMap.getCustomTsMetricGroups({
        time_series_group_id: Number(this.timeSeriesGroupId),
        // is_mock: true,
      });
      metricGroupsData = result.metric_groups;
      customEscalationViewStore.updateMetricGroupList(result.metric_groups);
      if (!needParseUrl) {
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
      this.handleCustomTsMetricGroups(metricGroupsData);
    }
  }

  created() {
    // apm嵌入不需要url参数
    if (!this.isApm) {
      const routerQuery = this.$route.query as Record<string, string>;
      this.state = {
        viewColumn: Number.parseInt(routerQuery.viewColumn, 10) || 2,
        showStatisticalValue: routerQuery.showStatisticalValue === 'true',
      };
    }
    this.getCustomTsMetricGroupsData();
  }

  render() {
    return (
      <bk-resize-layout
        style='height: calc(100vh - 140px - var(--notice-alert-height))'
        collapsible={true}
        initial-divide={220}
        max={550}
        min={200}
      >
        <template slot='aside'>
          <MetricsSelect
            isApm={this.isApm}
            onOpenSideslider={this.handleSideslider}
            onReset={this.handleMetricsSelectReset}
          />
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
              config={this.config}
              showStatisticalValue={this.state.showStatisticalValue}
              viewColumn={this.state.viewColumn}
            />
          </div>
        </template>
      </bk-resize-layout>
    );
  }
}
