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

import { Component } from 'vue-property-decorator';

import BaseEchart from '../../base-echart';
import { CommonSimpleChart } from '../../common-simple-chart';

import type { MonitorEchartOptions } from '../../../typings';

import './caller-pie-chart.scss';
@Component({
  name: 'CallerPieChart',
  components: {},
})
export default class CallerPieChart extends CommonSimpleChart {
  height = 300;
  width = 640;
  needResetChart = true;
  inited = false;
  emptyText = window.i18n.tc('查无数据');
  empty = false;
  data = [
    { value: 1048, name: '0-20%' },
    { value: 735, name: '20-40%' },
    { value: 580, name: '40-60%' },
    { value: 484, name: '60-80%' },
    { value: 300, name: '80-100%' },
  ];
  get customOptions(): MonitorEchartOptions {
    return {
      tooltip: {
        trigger: 'item',
      },
      legend: {
        orient: 'vertical',
        top: '30%',
        left: 'right',
      },
      series: [
        {
          name: 'caller',
          type: 'pie',
          radius: '50%',
          data: this.data,
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowOffsetX: 0,
              shadowColor: 'rgba(0, 0, 0, 0.5)',
            },
          },
        },
      ],
    };
  }
  render() {
    return (
      <div class='caller-pie-chart'>
        {!this.empty ? (
          <div class='pie-echart-content'>
            <div
              ref='chart'
              class='chart-instance'
            >
              <BaseEchart
                ref='baseChart'
                width={this.width}
                height={this.height}
                options={this.customOptions}
              />
            </div>
          </div>
        ) : (
          <div class='empty-chart'>{this.emptyText}</div>
        )}
      </div>
    );
  }
}
