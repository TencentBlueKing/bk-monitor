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

import { Component, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { type MonitorEchartOptions, echarts } from '../../../typings/index';
// import { CommonSimpleChart } from '../../common-simple-chart';

import './mini-chart.scss';

interface IProps {
  data?: any;
}

@Component
export default class MiniChart extends tsc<IProps> {
  @Ref('chartInstance') chartRef: HTMLDivElement;

  // 当前图表配置取消监听函数
  unwatchOptions: () => void = null;

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
      max: 'dataMax',
      min: 0,
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
          width: 0.5,
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
        smooth: true,
        data: [
          [2, 1721894460000],
          [41, 1721894520000],
          [0, 1721894580000],
          [16, 1721894640000],
          [4, 1721894700000],
          [0, 1721894760000],
          [70, 1721894820000],
          [58, 1721894880000],
          [65, 1721894940000],
          [71, 1721895000000],
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
      (this as any).instance = echarts.init(this.chartRef);
      (this as any).instance.setOption(this.options);
    }
  }

  render() {
    return (
      <div
        ref='chartInstance'
        class='details-side-mini-chart'
      />
    );
  }
}
