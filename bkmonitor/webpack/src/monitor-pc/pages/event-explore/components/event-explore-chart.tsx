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
import { Component, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { eventTimeSeries } from 'monitor-api/modules/data_explorer';
import MonitorEcharts from 'monitor-ui/monitor-echarts/monitor-echarts-new.vue';

import { chartMockData } from './chart-mock';
import ExploreIntervalSelect from './explore-interval-select';

import type { EventRetrievalViewType } from '../../data-retrieval/typings';

import './event-explore-chart.scss';

interface IEventExploreChartProps {
  /** 数据总数 */
  total: number;
  /** 请求接口公共请求参数 */
  commonParams: Record<string, any>;
}
type IEventExploreChartEvents = {
  onTest: () => void;
};
/**
 * @description 维度信息数据类型
 */
enum DimensionsTypeEnum {
  DEFAULT = 'Default',
  NORMAL = 'Normal',
  WARNING = 'Warning',
}

/**
 * @description 固定维度信息数据类型排序，从而固定类型与图表颜色的映射顺序
 */
const eventChartMap = {
  [DimensionsTypeEnum.WARNING]: 0,
  [DimensionsTypeEnum.NORMAL]: 1,
  [DimensionsTypeEnum.DEFAULT]: 2,
};
const eventChartColors = ['#F5C78E', '#92BEF1', '#DCDEE5'];
const eventChartBgColors = ['#fdf4e8', '#eaf2fc', '#f8f8f9'];

@Component
export default class EventExploreChart extends tsc<IEventExploreChartProps, IEventExploreChartEvents> {
  @Ref('chartRef') chartRef: InstanceType<typeof MonitorEcharts>;
  /** 请求接口公共请求参数 */
  @Prop({ type: Object, default: () => ({}) }) commonParams: Record<string, any>;
  /** 数据总数 */
  @Prop({ type: Number, default: 0 }) total: number;

  /** 图表汇聚周期 */
  chartInterval: EventRetrievalViewType.intervalType = 'auto';
  /** eventTimeSeries 接口请求耗时 */
  duration = 0;
  /** 折叠面板，是否展开图表 */
  expand = true;
  /** 当前显示的图例 */
  showLegends: DimensionsTypeEnum[] = [];

  /**
   * @description: 根据展开状态，返回状态类名
   */
  get classNameByExpand() {
    return this.expand ? 'is-expand' : '';
  }

  /**
   * @description: 切换汇聚周期
   */
  handleIntervalChange(interval: EventRetrievalViewType.intervalType) {
    this.chartInterval = interval;
  }

  /**
   * @description: 获取图表数据
   * */
  async getSeriesData(startTime, endTime) {
    const queryConfigs = { ...this.commonParams.query_configs[0] };
    queryConfigs.interval = this.chartInterval;
    queryConfigs.metrics = [
      {
        field: '_index',
        method: 'SUM',
        alias: 'a',
      },
    ];

    const params = {
      ...this.commonParams,
      expression: 'a',
      query_configs: queryConfigs,
    };
    const start = +new Date();
    const res = await eventTimeSeries(params)
      .then(res => {
        const series = res.series
          .sort((a, b) => eventChartMap[a.dimensions.type] - eventChartMap[b.dimensions.type])
          .map(item => ({
            ...item,
            target: item.dimensions.type,
            stack: 'event-explore',
          }));
        return {
          ...res,
          series,
        };
      })
      .catch(() => ({
        unit: '',
        series: chartMockData.series
          .sort((a, b) => eventChartMap[a.dimensions.type] - eventChartMap[b.dimensions.type])
          .map(item => ({
            ...item,
            target: item.dimensions.type,
            stack: 'event-explore',
          })),
      }));
    this.duration = +new Date() - start;
    return res.series;
  }

  /**
   * @description: 图表显示图例改变后回调
   */
  handleShowLegendChange(legends: DimensionsTypeEnum[]) {
    this.showLegends = legends;
  }

  handleShowLegendDelete(legend: DimensionsTypeEnum) {
    this.chartRef.handleLegendEvent({
      actionType: 'parent-change',
      // @ts-ignore
      item: {
        name: legend,
        show: false,
      },
    });
  }

  /**
   * @description: 展开/收起 折叠面板
   */
  handleExpandChange() {
    this.expand = !this.expand;
  }

  /**
   * @description: 图例标签渲染
   */
  showLegendTagsRender() {
    // if (this.expand) {
    //   return null;
    // }
    return this.showLegends.map(legend => (
      <div
        key={legend}
        style={{
          '--tag-color': eventChartColors[eventChartMap[legend]] || '',
          '--tag-bg-color': eventChartBgColors[eventChartMap[legend]] || '',
        }}
        class='chart-tags-item'
      >
        <i class='icon-monitor icon-filter-fill' />
        <span class='tag-label'>{legend}</span>
        <i
          class='icon-monitor icon-mc-close'
          onClick={() => this.handleShowLegendDelete(legend)}
        />
      </div>
    ));
  }

  render() {
    return (
      <div class={['event-explore-chart', this.classNameByExpand]}>
        <div class='event-explore-chart-container'>
          <MonitorEcharts
            ref='chartRef'
            // @ts-ignore
            height={166}
            class='explore-chart'
            chart-type='bar'
            colors={eventChartColors}
            getSeriesData={this.getSeriesData}
            hasResize={true}
            needFullScreen={false}
            title={this.$t('总趋势')}
            onShowLegendChange={this.handleShowLegendChange}
          >
            <div
              class='event-explore-chart-title'
              slot='title'
            >
              <div class='chart-title-left'>
                <div
                  class='left-text'
                  onClick={this.handleExpandChange}
                >
                  <i class='icon-monitor icon-mc-triangle-down chart-icon' />
                  <span class='chart-title'>{this.$t('总趋势')}</span>
                  <i18n
                    class='chart-description'
                    path='(找到 {0} 条结果，用时 {1} 毫秒)'
                  >
                    <span class='query-count'>{this.total}</span>
                    <span class='query-time'>{this.duration}</span>
                  </i18n>
                </div>
                <div class='chart-tags'>{this.showLegendTagsRender()}</div>
              </div>
              <div class='chart-title-right'>
                <div class='interval-select'>
                  <ExploreIntervalSelect
                    interval={this.chartInterval}
                    selectLabel={`${this.$t('汇聚周期')} :`}
                    onChange={this.handleIntervalChange}
                  />
                </div>
              </div>
            </div>
          </MonitorEcharts>
        </div>
      </div>
    );
  }
}
