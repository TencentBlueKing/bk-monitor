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
import { Component, InjectReactive, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { calculateByRange, timeSeries } from 'monitor-api/modules/llm_web';
import { Debounce } from 'monitor-common/utils/utils';
import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';

import LlmOverviewChart from './llm-overview-chart';
import {
  type CalType,
  type ICalculateItem,
  type IMetricCard,
  type IPieLegendItem,
  type IRankItem,
  type ITimeSeriesItem,
  buildPieOptions,
  buildTimeLineOptions,
  formatCount,
  formatDuration,
  formatGrowthRate,
  formatMetricValue,
  getDimensionName,
  getOperationDisplayName,
  GROUP_BY_MODEL,
  GROUP_BY_OPERATION,
  METRIC_CARD_CONFIG,
  PIE_COLORS,
  sortByCurrentValue,
  toEchartsPoints,
  unwrapCalculateList,
  unwrapSeriesList,
} from './utils';

import type { IViewOptions, MonitorEchartOptions } from '../../typings';
import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';

import './index.scss';

const API_CONFIG = { needMessage: false };

@Component
export default class ApmLlmOverview extends tsc<Record<string, never>> {
  @InjectReactive('viewOptions') readonly viewOptions!: IViewOptions;
  @InjectReactive('timeRange') readonly timeRange!: TimeRangeType;
  // 图表刷新间隔
  @InjectReactive('refreshInterval') readonly refreshInterval!: number;
  // 立即刷新图表
  @InjectReactive('refreshImmediate') readonly refreshImmediate: string;

  pageLoading = false;
  refreshIntervalInstance = null;
  metricCards: IMetricCard[] = METRIC_CARD_CONFIG.map(item => ({
    title: item.title,
    value: '--',
    trend: '--',
    trendTheme: item.trendTheme,
  }));
  pieLegend: IPieLegendItem[] = [];
  modelCallRankList: IRankItem[] = [];
  durationRankList: IRankItem[] = [];
  tokenInputPoints: [number, number][] = [];
  tokenOutputPoints: [number, number][] = [];
  modelCallPoints: [number, number][] = [];

  get appName() {
    return this.viewOptions?.filters?.app_name || this.viewOptions?.app_name;
  }

  get serviceName() {
    return this.viewOptions?.filters?.service_name || this.viewOptions?.service_name;
  }

  get canQuery() {
    return Boolean(this.appName);
  }

  get pieTotal() {
    return this.pieLegend.reduce((total, item) => total + item.rawValue, 0);
  }

  get tokenTrendOptions() {
    return buildTimeLineOptions([
      {
        name: this.$t('输入 Tokens') as string,
        data: this.tokenInputPoints,
        color: '#f8b64f',
      },
      {
        name: this.$t('输出 Tokens') as string,
        data: this.tokenOutputPoints,
        color: '#3a84ff',
      },
    ]);
  }

  get callTrendOptions() {
    return buildTimeLineOptions([
      {
        name: this.$t('模型调用次数') as string,
        data: this.modelCallPoints,
        color: '#3a84ff',
      },
    ]);
  }

  get pieOptions(): MonitorEchartOptions {
    return buildPieOptions(
      this.pieLegend.map(item => ({
        ...item,
        name: this.$t(item.name) as string,
      }))
    );
  }

  get queryBase() {
    const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
    return {
      app_name: this.appName,
      service_name: this.serviceName,
      start_time: startTime,
      end_time: endTime,
    };
  }

  @Watch('timeRange')
  @Watch('refreshImmediate')
  @Watch('viewOptions', { deep: true })
  handleQueryChange() {
    this.getPageData();
  }

  @Watch('refreshInterval', { immediate: true })
  handleRefreshIntervalChange(v: number) {
    if (this.refreshIntervalInstance) {
      window.clearInterval(this.refreshIntervalInstance);
      this.refreshIntervalInstance = null;
    }
    if (!v || +v < 1000 * 60) return;
    this.refreshIntervalInstance = window.setInterval(() => {
      this.getPageData(false);
    }, v);
  }

  created() {
    this.getPageData();
  }

  beforeDestroy() {
    if (this.refreshIntervalInstance) {
      window.clearInterval(this.refreshIntervalInstance);
      this.refreshIntervalInstance = null;
    }
  }

  @Debounce(200)
  async getPageData(showLoading = true) {
    if (!this.canQuery) return;
    if (showLoading) this.pageLoading = true;
    try {
      await Promise.all([this.fetchMetricCards(), this.fetchAnalysis(), this.fetchTrends()]);
    } finally {
      if (showLoading) this.pageLoading = false;
    }
  }

  async fetchCalculate(calType: CalType, extra: Record<string, unknown> = {}) {
    try {
      const res = await calculateByRange(
        {
          ...this.queryBase,
          cal_type: calType,
          group_by: [],
          ...extra,
        },
        API_CONFIG
      );
      return unwrapCalculateList(res);
    } catch {
      return [] as ICalculateItem[];
    }
  }

  async fetchTrend(calType: CalType) {
    try {
      const res = await timeSeries(
        {
          ...this.queryBase,
          cal_type: calType,
          group_by: [],
        },
        API_CONFIG
      );
      return unwrapSeriesList(res);
    } catch {
      return [] as ITimeSeriesItem[];
    }
  }

  async fetchMetricCards() {
    const results = await Promise.all(
      METRIC_CARD_CONFIG.map(item =>
        this.fetchCalculate(item.calType, {
          baseline: '0s',
          time_shifts: ['0s', '1d'],
        })
      )
    );
    this.metricCards = METRIC_CARD_CONFIG.map((item, index) => {
      const current = results[index][0];
      const value = Number(current?.['0s']);
      return {
        title: item.title,
        value: formatMetricValue(value, item.format),
        trend: formatGrowthRate(current?.growth_rates?.['1d']),
        trendTheme: item.trendTheme,
      };
    });
  }

  async fetchAnalysis() {
    const [operationList, modelCallList, durationList] = await Promise.all([
      this.fetchCalculate('operation_count', { group_by: GROUP_BY_OPERATION }),
      this.fetchCalculate('model_call_count', { group_by: GROUP_BY_MODEL }),
      this.fetchCalculate('duration', { group_by: GROUP_BY_MODEL }),
    ]);
    this.pieLegend = sortByCurrentValue(operationList).map((item, index) => {
      const rawValue = Number(item['0s']) || 0;
      return {
        name: getOperationDisplayName(getDimensionName(item, GROUP_BY_OPERATION[0])),
        rawValue,
        value: formatCount(rawValue),
        color: PIE_COLORS[index % PIE_COLORS.length],
      };
    });
    this.modelCallRankList = this.toRankList(modelCallList, formatCount);
    this.durationRankList = this.toRankList(durationList, formatDuration);
  }

  async fetchTrends() {
    const [inputSeries, outputSeries, callSeries] = await Promise.all([
      this.fetchTrend('input_tokens'),
      this.fetchTrend('output_tokens'),
      this.fetchTrend('model_call_count'),
    ]);
    this.tokenInputPoints = toEchartsPoints(inputSeries[0]?.datapoints);
    this.tokenOutputPoints = toEchartsPoints(outputSeries[0]?.datapoints);
    this.modelCallPoints = toEchartsPoints(callSeries[0]?.datapoints);
  }

  toRankList(list: ICalculateItem[], formatter: (value: number) => string): IRankItem[] {
    return sortByCurrentValue(list).map(item => {
      const value = Number(item['0s']) || 0;
      return {
        name: getDimensionName(item, GROUP_BY_MODEL[0]),
        value,
        displayValue: formatter(value),
      };
    });
  }

  renderMetricCards() {
    return (
      <div class='llm-overview-metrics'>
        {this.metricCards.map(item => (
          <div
            key={item.title}
            class='llm-overview-metric-card'
          >
            <div class='metric-card-title'>{this.$t(item.title)}</div>
            <div class='metric-card-body'>
              <span class='metric-card-value'>{item.value}</span>
              <span class={['metric-card-trend', `is-${item.trendTheme}`]}>{item.trend}</span>
            </div>
          </div>
        ))}
      </div>
    );
  }

  renderTrendCard(title: string, options: MonitorEchartOptions, hasData: boolean) {
    return (
      <div class='llm-overview-card'>
        <div class='llm-overview-card-title'>{title}</div>
        {hasData ? (
          <div class='llm-overview-card-chart'>
            <LlmOverviewChart options={options} />
          </div>
        ) : (
          <div class='llm-overview-empty'>{this.$t('查无数据')}</div>
        )}
      </div>
    );
  }

  renderRankList(list: IRankItem[], barClass: string) {
    if (!list.length) {
      return <div class='llm-overview-empty'>{this.$t('查无数据')}</div>;
    }
    const rankMax = Math.max(...list.map(item => item.value), 1);
    return (
      <div class='llm-overview-rank-list'>
        {list.map(item => (
          <div
            key={item.name}
            class='llm-overview-rank-item'
          >
            <div class='rank-item-header'>
              <span class='rank-item-name'>{item.name}</span>
              <span class='rank-item-value'>{item.displayValue}</span>
            </div>
            <div class='rank-item-track'>
              <div
                style={{ width: `${(item.value / rankMax) * 100}%` }}
                class={['rank-item-bar', barClass]}
              />
            </div>
          </div>
        ))}
      </div>
    );
  }

  render() {
    return (
      <div
        id='apm-llm-overview-main'
        class='apm-llm-overview-page'
        v-bkloading={{ isLoading: this.pageLoading }}
      >
        {this.renderMetricCards()}
        <div class='llm-overview-trends'>
          {this.renderTrendCard(
            this.$t('输入输出 Token 趋势') as string,
            this.tokenTrendOptions,
            Boolean(this.tokenInputPoints.length || this.tokenOutputPoints.length)
          )}
          {this.renderTrendCard(
            this.$t('模型调用次数趋势') as string,
            this.callTrendOptions,
            Boolean(this.modelCallPoints.length)
          )}
        </div>
        <div class='llm-overview-analysis'>
          <div class='llm-overview-card llm-overview-pie-card'>
            <div class='llm-overview-card-title'>{this.$t('操作类型分布')}</div>
            {this.pieLegend.length ? (
              <div class='llm-overview-pie'>
                <div class='llm-overview-pie-chart'>
                  <LlmOverviewChart options={this.pieOptions} />
                  <div class='llm-overview-pie-center'>
                    <div class='pie-center-label'>{this.$t('操作总数')}</div>
                    <div class='pie-center-value'>{formatCount(this.pieTotal)}</div>
                  </div>
                </div>
                <div class='llm-overview-pie-legend'>
                  {this.pieLegend.map(item => (
                    <div
                      key={item.name}
                      class='pie-legend-item'
                    >
                      <span
                        style={{ background: item.color }}
                        class='pie-legend-dot'
                      />
                      <span
                        class='pie-legend-name'
                        v-bk-overflow-tips
                      >
                        {this.$t(item.name)}
                      </span>
                      <span class='pie-legend-value'>{item.value}</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div class='llm-overview-empty'>{this.$t('查无数据')}</div>
            )}
          </div>
          <div class='llm-overview-card'>
            <div class='llm-overview-card-header'>
              <div class='llm-overview-card-title'>{this.$t('模型调用总数排行')}</div>
              <div class='llm-overview-card-extra'>{this.$t('按模型')}</div>
            </div>
            {this.renderRankList(this.modelCallRankList, 'is-brand')}
          </div>
          <div class='llm-overview-card'>
            <div class='llm-overview-card-header'>
              <div class='llm-overview-card-title'>{this.$t('模型调用平均耗时 TOP10')}</div>
              <div class='llm-overview-card-extra'>
                {this.$t('当前 {0} 个模型 · 最多 TOP10', [this.durationRankList.length])}
              </div>
            </div>
            {this.renderRankList(this.durationRankList, 'is-warn')}
          </div>
        </div>
      </div>
    );
  }
}
