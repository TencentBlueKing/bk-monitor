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
import { nextTick, onMounted, Ref } from 'vue';

import * as Echarts from 'echarts';

import BarCharOptionHelper from '../components/monitor-echarts/options/bar-chart-option';
import chartOption from './trend-chart-options';

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
  const options: any = Object.assign({}, chartOption);
  const barChartOptionInstance = new BarCharOptionHelper({});

  const delegateMethod = (name: string, ...args) => {
    return chartInstance?.[name](...args);
  };
  // resize
  // const resize = (options: EChartOption = null) => {
  //   delegateMethod('resize', options);
  // };

  const dispatchAction = payload => {
    delegateMethod('dispatchAction', payload);
  };

  const updateChart = (data: EchartData[]) => {
    options.series[0].data = data;
    options.xAxis[0].axisLabel.formatter = barChartOptionInstance.handleSetFormatterFunc(data);
    chartInstance.setOption(options);
    nextTick(() => {
      dispatchAction({
        type: 'takeGlobalCursor',
        key: 'dataZoomSelect',
        dataZoomSelectActive: true,
      });
    });
  };
  onMounted(() => {
    if (target.value) {
      chartInstance = Echarts.init(target.value);
      chartInstance.on('dblclick', () => {
        dispatchAction({
          type: 'restore',
        });
      });
    }
  });

  return { updateChart };
};
