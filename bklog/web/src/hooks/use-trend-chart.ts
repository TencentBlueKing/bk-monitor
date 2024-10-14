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
import { onMounted, Ref } from 'vue';

import * as Echarts from 'echarts';

import EchartOptions from '../components/monitor-echarts/options/bar-chart-option';

export type TrandChartOption = {
  target: Ref<HTMLDivElement | null>;
};

export type EchartData = {
  datapoints: Array<number[]>;
  target: string;
  isFinish: boolean;
};
export default ({ target }: TrandChartOption) => {
  let chartInstance: Echarts.ECharts = null;
  const chartOptionInstance = new EchartOptions({});

  const updateChart = (data: EchartData[]) => {
    const { options } = chartOptionInstance.getOptions({});
    options.series = [
      {
        data: data,
        type: 'bar',
      },
    ];
    chartInstance.setOption({
      title: {
        show: false,
      },
      useUTC: false,
      color: [
        '#A3C5FD',
        '#EAB839',
        '#6ED0E0',
        '#EF843C',
        '#E24D42',
        '#1F78C1',
        '#BA43A9',
        '#705DA0',
        '#508642',
        '#CCA300',
        '#447EBC',
        '#C15C17',
        '#890F02',
        '#0A437C',
        '#6D1F62',
        '#584477',
        '#B7DBAB',
        '#F4D598',
        '#70DBED',
        '#F9BA8F',
        '#F29191',
        '#82B5D8',
        '#E5A8E2',
        '#AEA2E0',
        '#629E51',
        '#E5AC0E',
        '#64B0C8',
        '#E0752D',
        '#BF1B00',
        '#0A50A1',
        '#962D82',
        '#614D93',
        '#9AC48A',
        '#F2C96D',
        '#65C5DB',
        '#F9934E',
        '#EA6460',
        '#5195CE',
        '#D683CE',
        '#806EB7',
        '#3F6833',
        '#967302',
        '#2F575E',
        '#99440A',
        '#58140C',
        '#052B51',
        '#511749',
        '#3F2B5B',
        '#E0F9D7',
        '#FCEACA',
        '#CFFAFF',
        '#F9E2D2',
        '#FCE2DE',
        '#BADFF4',
        '#F9D9F9',
        '#DEDAF7',
      ],
      tooltip: {
        show: true,
        trigger: 'axis',
        axisPointer: { type: 'line', label: { backgroundColor: '#6a7985' } },
        transitionDuration: 0,
        alwaysShowContent: false,
        backgroundColor: 'rgba(0,0,0,0.8)',
        borderWidth: 0,
        textStyle: { fontSize: 12 },
        extraCssText: 'border-radius: 0',
      },
      grid: { containLabel: true, left: 0, right: 26, top: 16, bottom: 0, backgroundColor: 'transparent' },
      xAxis: {
        type: 'time',
        data: data.map(d => d[0]),
        axisLine: {
          lineStyle: {
            type: 'dashed',
            color: '#666',
          },
          show: true,
        },
      },
      yAxis: {
        type: 'value',
        axisLine: {
          lineStyle: {
            type: 'dashed',
            color: '#666',
          },
        },
      },
      series: [
        {
          data: data.map(d => d[1]),
          type: 'bar',
        },
      ],
    });
  };
  onMounted(() => {
    if (target.value) {
      chartInstance = Echarts.init(target.value);
    }
  });

  return { updateChart };
};
