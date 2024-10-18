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

import dayjs from 'dayjs';

import ChartHeader from '../../../components/chart-title/chart-title';
import { COLOR_LIST, MONITOR_LINE_OPTIONS } from '../../../constants';
import BaseEchart from '../../monitor-base-echart';
import LineChart from '../../time-series/time-series';

import type { MonitorEchartOptions } from '../../../typings';

import './apm-caller-line-chart.scss';

export const COLOR_LIST_BAR = ['#4051A3', ...COLOR_LIST];

@Component
export default class ApmCallerLineChart extends LineChart {
  height = 100;
  width = 300;
  empty = false;
  needTips = true;
  emptyText = window.i18n.tc('暂无数据');
  options: MonitorEchartOptions = {};
  mounted() {
    this.empty = true;
    setTimeout(() => {
      this.initChart();
      this.emptyText = window.i18n.tc('加载中...');
      this.empty = false;
    }, 1000);
  }
  /* 禁用框选 */
  get disableZoom() {
    return !!this.panel.options?.apm_time_series?.disableZoom;
  }
  get xAxisSplitNumber() {
    return this.panel.options?.apm_time_series?.xAxisSplitNumber;
  }
  initChart() {
    const chartRef = this.$refs?.baseChart?.instance;
    if (chartRef) {
      chartRef.off('click');
      chartRef.on('click', params => {
        const date = dayjs(params.value[0]).format('YYYY-MM-DD HH:mm:ss');
        this.$emit('choosePoint', date);
      });
    }
  }
  render() {
    return (
      <div class='time-series apm-caller-line-chart'>
        <ChartHeader
          menuList={this.menuList}
          showMore={false}
          title={this.panel.title}
        />
        {!this.empty ? (
          <div class='time-series-content'>
            <div
              ref='chart'
              class='chart-instance'
            >
              <BaseEchart
                ref='baseChart'
                width={this.width}
                height={this.height}
                groupId={this.panel.dashboardId}
                hoverAllTooltips={this.hoverAllTooltips}
                isContextmenuPreventDefault={true}
                needTooltips={this.needTips}
                options={this.options}
                showRestore={this.showRestore}
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
