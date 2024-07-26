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

import dayjs from 'dayjs';

import { type MonitorEchartOptions, echarts } from '../../../typings/index';

import './mini-chart.scss';

interface IProps {
  data?: any;
  chartStyle?: {
    lineMaxHeight: number;
    chartWarpHeight: number;
  };
}

@Component
export default class MiniChart extends tsc<IProps> {
  @Ref('chartInstance') chartRef: HTMLDivElement;
  @Prop({
    type: Object,
    default: () => ({
      lineMaxHeight: 24,
      chartWarpHeight: 50,
    }),
  })
  chartStyle: IProps['chartStyle'];

  options: MonitorEchartOptions = {
    xAxis: {
      show: false,
      type: 'value',
      max: 'dataMax',
      min: 'dataMin',
    },
    yAxis: {
      show: false,
      type: 'value',
    },
    tooltip: {
      show: true,
      trigger: 'axis',
      appendToBody: true,
    },
    series: [
      {
        type: 'line',
        lineStyle: {
          color: '#3A84FF',
          width: 1,
        },
        cursor: 'auto',
        symbol: 'none',
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            {
              offset: 0,
              color: '#A4C6FD',
            },
            {
              offset: 1,
              color: '#FFFFFF',
            },
          ]),
        },
        data: [
          [118, 1721616120000],
          [120, 1721616180000],
          [120, 1721616240000],
          [120, 1721616300000],
          [122, 1721616360000],
          [120, 1721616420000],
          [118, 1721616480000],
          [120, 1721616540000],
          [0, 1721616600000],
          [122, 1721616660000],
          [120, 1721616720000],
          [120, 1721616780000],
          [118, 1721616840000],
          [120, 1721616900000],
          [122, 1721616960000],
          [120, 1721617020000],
          [120, 1721617080000],
          [120, 1721617140000],
          [120, 1721617200000],
          [120, 1721617260000],
          [120, 1721617320000],
          [120, 1721617380000],
          [120, 1721617440000],
          [120, 1721617500000],
          [2, 1721617560000],
          [120, 1721617620000],
          [120, 1721617680000],
          [120, 1721617740000],
          [120, 1721617800000],
          [122, 1721617860000],
          [120, 1721617920000],
          [118, 1721617980000],
          [120, 1721618040000],
          [120, 1721618100000],
          [122, 1721618160000],
          [120, 1721618220000],
          [118, 1721618280000],
          [4, 1721618340000],
          [10, 1721618400000],
          [20, 1721618460000],
          [30, 1721618520000],
          [50, 1721618580000],
          [80, 1721618640000],
          [100, 1721618700000],
          [122, 1721618760000],
          [120, 1721618820000],
          [120, 1721618880000],
          [120, 1721618940000],
          [120, 1721619000000],
          [120, 1721619060000],
          [120, 1721619120000],
          [120, 1721619180000],
          [120, 1721619240000],
          [120, 1721619300000],
          [122, 1721619360000],
          [118, 1721619420000],
          [120, 1721619480000],
          [120, 1721619540000],
          [120, 1721619600000],
          [122, 1721619660000],
        ].map(item => ({
          value: [item[1], item[0]],
        })),
      },
    ],
  };

  mounted() {
    this.initChart();
  }

  initChart() {
    if (!(this as any).instance) {
      setTimeout(() => {
        this.options = {
          ...this.options,
          yAxis: {
            ...this.options.yAxis,
            max: v => {
              return v.max + ((v.max * this.chartStyle.chartWarpHeight) / this.chartStyle.lineMaxHeight - v.max);
            },
            min: v => {
              return 0 - ((v.max * this.chartStyle.chartWarpHeight) / this.chartStyle.lineMaxHeight - v.max) / 1.5;
            },
          },
          tooltip: {
            ...this.options.tooltip,
            className: 'details-side-mini-chart-tooltip',
            formatter: params => {
              const time = params[0].data.value[0];
              const value = params[0].data.value[1];
              return `
              <div class="left-compare-type" style="background: #7B29FF;"></div>
              <div>
                <div>${this.$t('对比时间')}：${dayjs(time).format('YYYY-MM-DD HH:mm:ss')}</div>
                <div>${this.$t('请求数')}：${value}</div>
              </div>`;
            },
          },
        };
        (this as any).instance = echarts.init(this.chartRef);
        (this as any).instance.setOption(this.options);
        (this as any).instance.on('click', params => {
          console.log('---------------', params);
        });
        console.log((this as any).instance);
      }, 100);
    }
  }

  destroy() {
    (this as any).instance?.dispose?.();
    (this as any).instance = null;
  }

  handleClick() {}

  render() {
    return (
      <div
        ref='chartInstance'
        style={{
          height: `${this.chartStyle.chartWarpHeight}px`,
        }}
        class='details-side-mini-chart'
        onClick={this.handleClick}
      />
    );
  }
}
