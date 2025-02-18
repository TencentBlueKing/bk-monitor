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
import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { eventTimeSeries } from 'monitor-api/modules/data_explorer';
import MonitorEcharts from 'monitor-ui/monitor-echarts/monitor-echarts-new.vue';

import { handleTransformToTimestamp } from '../../../components/time-range/utils';
import { chartMockData } from './chart-mock';
import ExploreIntervalSelect from './explore-interval-select';

import type { TimeRangeType } from '../../../components/time-range/time-range';
import type { EventRetrievalViewType } from '../../data-retrieval/typings';

import './event-explore-chart.scss';

interface IEventExploreChartProps {
  chartInterval?: EventRetrievalViewType.intervalType;
}
interface IEventExploreChartEvents {
  onIntervalChange: (interval: EventRetrievalViewType.intervalType) => void;
  onTimeRangeChange: (timeRange: [string, string] | { start_time: number; end_time: number }) => void;
}

@Component
export default class EventExploreChart extends tsc<IEventExploreChartProps, IEventExploreChartEvents> {
  /** 图表汇聚周期 */
  @Prop({ type: [String, Number], default: 'auto' }) chartInterval: EventRetrievalViewType.intervalType;

  /** eventTimeSeries 接口请求耗时 */
  duration = 0;
  /** 记录总条数 */
  total = 0;
  /** 折叠面板，是否展开图表 */
  expand = true;

  chartOption = {
    grid: {
      right: '20',
    },
  };

  get chartColors() {
    return ['#F59E9E', '#8DD3B5', '#CBCDD2'];
  }

  /**
   * @description: 切换汇聚周期
   */
  @Emit('intervalChange')
  handleIntervalChange(interval: number | string) {
    return interval;
  }

  /**
   * @description: 操作图表切换时间范围 timeRange ["2021-09-04 14:49", "2021-09-04 15:18"]
   */
  @Emit('timeRangeChange')
  handleTimeRangeChange(timeRange: { start_time: number; end_time: number } | TimeRangeType) {
    let time = null;

    const temp = timeRange as { start_time: number; end_time: number };
    if (timeRange && Array.isArray(timeRange)) {
      // time = handleTimeRange(timeRange);
      time = handleTransformToTimestamp(timeRange);
      return time || undefined;
    }
    if (temp?.start_time) {
      return [temp.start_time, temp.end_time];
    }
  }

  /**
   * @description: 图表的时间范围
   */
  timeRange(timeRange?: TimeRangeType) {
    const [start_time, end_time] = handleTransformToTimestamp(timeRange);
    return {
      start_time,
      end_time,
    };
  }

  /**
   * @description: 获取图表数据
   * */
  async getSeriesData(startTime, endTime) {
    const timeRange = startTime && endTime ? ([startTime, endTime] as TimeRangeType) : undefined;
    this.handleTimeRangeChange(timeRange as [string, string]);
    // const params = {
    //   ...this.timeRange(timeRange),
    //   expression: 'a',
    //   query_configs: [],
    // };
    const start = +new Date();
    // const res = await eventTimeSeries(params).catch();
    const res = {
      unit: '',
      series: chartMockData.series.map(item => ({
        ...item,
        stack: 'event-alram',
      })),
    };
    this.duration = +new Date() - start;
    return res.series;
  }

  handleExpandChange() {
    this.expand = !this.expand;
  }
  render() {
    return (
      <div class={['event-explore-chart', { 'is-expand': this.expand }]}>
        <div class='event-explore-chart-container'>
          <MonitorEcharts
            // @ts-ignore
            height={166}
            class='explore-chart'
            chart-type='bar'
            colors={this.chartColors}
            getSeriesData={this.getSeriesData}
            hasResize={true}
            needFullScreen={false}
            options={this.chartOption}
            title={this.$t('总趋势')}
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
                  <i class={['icon-monitor icon-mc-triangle-down chart-icon', { 'is-expand': this.expand }]} />
                  <span class='chart-title'>{this.$t('总趋势')}</span>
                  <i18n
                    class='chart-description'
                    path='(找到 {0} 条结果，用时 {1} 毫秒)'
                  >
                    <span class='query-count'>94</span>
                    <span class='query-time'>{this.duration}</span>
                  </i18n>
                </div>
                <div class='chart-tags' />
              </div>
              <div class='chart-title-right'>
                {this.expand && (
                  <div class='interval-select'>
                    <ExploreIntervalSelect
                      interval={this.chartInterval}
                      selectLabel={`${this.$t('汇聚周期')} :`}
                      onChange={this.handleIntervalChange}
                    />
                  </div>
                )}
              </div>
            </div>
          </MonitorEcharts>
        </div>
      </div>
    );
  }
}
