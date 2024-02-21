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

import { Component, Emit, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import echarts from 'echarts';

import BaseEchart from '../../../../../monitor-ui/chart-plugins/plugins/monitor-base-echart';
import EmptyStatus from '../../../../components/empty-status/empty-status';
import TimeRange, { DateValue, TimeRangeType } from '../../../../components/time-range/time-range';
import { DEFAULT_TIME_RANGE, shortcuts } from '../../../../components/time-range/utils';

import './link-status-chart.scss';

interface LinkStatusChartProps {
  timeRange?: TimeRangeType;
  type: 'minute' | 'hour';
  data: [number, number][];
  getChartData: () => any;
}

interface LinkStatusChartEvents {
  onRefresh: void;
  onTimeRangeChange: LinkStatusChartProps['timeRange'];
}

@Component
export default class LinkStatusChart extends tsc<LinkStatusChartProps, LinkStatusChartEvents> {
  @Prop({ type: Array, required: true }) data: LinkStatusChartProps['data'];
  @Prop({ type: String, default: 'minute' }) type: LinkStatusChartProps['type'];
  @Prop({ type: Array, default: () => [...DEFAULT_TIME_RANGE] }) timeRange: LinkStatusChartProps['timeRange'];
  @Prop({
    type: Function,
    default: () =>
      new Promise(resolve => {
        resolve(true);
      })
  })
  getChartData: () => any;

  @Ref('baseChartRef') baseChart;

  defaultOption = Object.freeze<echarts.EChartOption>({
    legend: {
      bottom: 8,
      itemWidth: 8,
      itemHeight: 10,
      icon: 'rect',
      selectedMode: false
    },
    xAxis: {
      type: 'time',
      axisLine: {
        lineStyle: {
          color: '#F0F1F5'
        }
      },
      axisLabel: {
        color: '#979BA5'
      },
      axisTick: {
        show: false
      },
      splitLine: {
        show: false
      }
    },
    yAxis: {
      type: 'value',
      axisTick: {
        show: false
      },
      axisLabel: {
        color: '#979BA5'
      },
      axisLine: {
        show: false
      },
      splitLine: {
        lineStyle: {
          color: '#F0F1F5'
        }
      }
    },
    series: [],
    tooltip: {
      trigger: 'axis'
    },
    textStyle: {
      color: '#63656E'
    },
    grid: {
      left: 50,
      top: 10,
      right: 40,
      bottom: 30,
      containLabel: true
    }
  });

  loading = false;

  get options(): echarts.EChartOption {
    const minute: echarts.EChartOption.SeriesLine = {
      name: this.$tc('分钟数据量'),
      data: this.data.map(item => [item[1], item[0]]) || [],
      type: 'line',
      symbol: 'none',
      itemStyle: {
        color: '#339DFF'
      }
    };
    const hour: echarts.EChartOption.SeriesBar = {
      name: this.$tc('小时数据量'),
      data: this.data.map(item => [item[1], item[0]]) || [],
      type: 'bar',
      barMaxWidth: 30,
      itemStyle: {
        color: '#339DFF'
      }
    };
    return {
      ...this.defaultOption,
      series: [this.type === 'minute' ? minute : hour]
    };
  }

  get defaultShortcuts(): DateValue[] {
    if (this.type === 'minute') return shortcuts.map(item => item.value) as DateValue[];
    return [
      ['now-3h', 'now'],
      ['now-6h', 'now'],
      ['now-24h', 'now'],
      ['now-72h', 'now']
    ];
  }

  mounted() {
    this.handleRefresh();
  }

  chartResize() {
    return this.baseChart?.resize();
  }

  handleTimeRange(val: LinkStatusChartProps['timeRange']) {
    this.handleEmitTimeRange(val);
    this.$nextTick(() => {
      this.handleRefresh();
    });
  }

  @Emit('timeRangeChange')
  handleEmitTimeRange(val: LinkStatusChartProps['timeRange']) {
    return val;
  }

  async handleRefresh() {
    this.loading = true;
    await this.getChartData();
    this.loading = false;
  }

  render() {
    return (
      <div
        class='minute-chart-component'
        v-bkloading={{ isLoading: this.loading }}
      >
        <div class='chart-header'>
          <div class='chart-label'>{this.type === 'minute' ? this.$tc('分钟数据量') : this.$tc('小时数据量')}</div>
          <div class='chart-tools'>
            <TimeRange
              value={this.timeRange}
              onChange={val => this.handleTimeRange(val)}
              commonUseList={this.defaultShortcuts}
              needTimezone={false}
            ></TimeRange>
            <span class='operate'>
              <i
                class='icon-monitor icon-zhongzhi1 refresh'
                onClick={this.handleRefresh}
              ></i>
            </span>
          </div>
        </div>
        {this.data.length ? (
          <div class='chart-wrapper'>
            <BaseEchart
              ref='baseChartRef'
              height={200}
              options={this.options}
            />
          </div>
        ) : (
          <EmptyStatus />
        )}
      </div>
    );
  }
}
