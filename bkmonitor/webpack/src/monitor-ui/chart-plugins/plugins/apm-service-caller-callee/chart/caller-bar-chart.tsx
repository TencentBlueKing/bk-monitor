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

import { CommonSimpleChart } from '../../common-simple-chart';
import BaseEchart from '../../monitor-base-echart';

import type { MonitorEchartOptions } from '../../../typings';

import './caller-bar-chart.scss';
@Component({
  name: 'CallerBarChart',
  components: {},
})
export default class CallerBarChart extends CommonSimpleChart {
  height = 300;
  width = 640;
  needResetChart = true;
  inited = false;
  emptyText = window.i18n.tc('查无数据');
  empty = false;
  needTips = true;
  data = [
    { value: 1048, name: '0-20%' },
    { value: 735, name: '20-40%' },
    { value: 580, name: '40-60%' },
    { value: 484, name: '60-80%' },
    { value: 300, name: '80-100%' },
  ];
  get customOptions(): MonitorEchartOptions {
    return {
      xAxis: {
        type: 'time',
      },
      yAxis: {
        type: 'value',
      },
      series: [
        {
          data: [
            {
              value: [1728525360000, 1162],
            },
            {
              value: [1728525480000, 1323],
            },
            {
              value: [1728525600000, 1132],
            },
            {
              value: [1728525720000, 1135],
            },
            {
              value: [1728525840000, 1144],
            },
            {
              value: [1728525960000, 1103],
            },
          ],
          type: 'bar',
        },
      ],
    };
  }
  render() {
    return (
      <div class='caller-bar-chart'>
        {!this.empty ? (
          <div class='bar-echart-content'>
            <div
              ref='chart'
              class='chart-instance'
            >
              <BaseEchart
                ref='baseChart'
                width={this.width}
                height={this.height}
                // groupId={this.panel.dashboardId}
                isContextmenuPreventDefault={true}
                needTooltips={this.needTips}
                options={this.customOptions}
                sortTooltipsValue={false}
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
