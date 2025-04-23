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
import { Component, Mixins, Prop, Ref } from 'vue-property-decorator';
import { ofType } from 'vue-tsx-support';

import deepmerge from 'deepmerge';
import { deepClone } from 'monitor-common/utils';
import { MONITOR_BAR_OPTIONS, MONITOR_LINE_OPTIONS } from 'monitor-ui/chart-plugins/constants';
import { ResizeMixin } from 'monitor-ui/chart-plugins/mixins';
import MonitorBaseEchart from 'monitor-ui/chart-plugins/plugins/monitor-base-echart';

import type { MonitorEchartOptions } from 'monitor-ui/chart-plugins/typings';

import './dimension-echarts.scss';

interface DimensionEchartsProps {
  data: any[];
  seriesType: 'histogram' | 'line';
}

@Component
class DimensionEcharts extends Mixins<ResizeMixin>(ResizeMixin) {
  @Prop({ default: () => [] }) data!: any[];
  @Prop({ default: 'histogram' }) seriesType: 'histogram' | 'line';

  @Ref('baseEchartRef') baseEchartRef: any;

  width = 370;
  height = 136;

  customTooltips(params) {
    return `<div class="monitor-chart-tooltips">
            <ul class="tooltips-content">
               <li class="tooltips-content-item" style="--series-color: ${params[0].color}">
                  <span class="item-name" style="color: #fff;font-weight: bold;">${params[0].axisValue}:</span>
                  <span class="item-value" style="color: #fff;font-weight: bold;">${params[0].value[1]}</span>
               </li>
            </ul>
            </div>`;
  }

  get options(): MonitorEchartOptions {
    const series = this.data.map(item => {
      const color =
        this.seriesType === 'histogram'
          ? {
              itemStyle: {
                color: item.color,
              },
            }
          : {
              lineStyle: {
                color: item.color,
              },
            };
      return {
        type: this.seriesType === 'histogram' ? 'bar' : 'line',
        name: this.seriesType === 'histogram' ? '' : item.target,
        data: item.datapoints.map(point => [point[1], point[0]]),
        symbol: 'none',
        z: 6,
        ...color,
      };
    });
    const interval = Math.round(series[0].data.length / 2) - 1;
    return deepmerge(
      deepClone(this.seriesType === 'histogram' ? MONITOR_BAR_OPTIONS : MONITOR_LINE_OPTIONS),
      {
        xAxis: {
          type: this.seriesType === 'histogram' ? 'category' : 'time',
          boundaryGap: this.seriesType === 'histogram',
          splitNumber: 5,
          axisLabel: {
            showMaxLabel: this.seriesType === 'histogram',
            showMinLabel: this.seriesType === 'histogram',
            interval: this.seriesType === 'histogram' ? interval : 1,
          },
        },
        series,
        toolbox: [],
        yAxis: {
          splitLine: {
            lineStyle: {
              color: '#F0F1F5',
              type: 'solid',
            },
          },
          splitNumber: 5,
        },
      },
      { arrayMerge: (_, newArr) => newArr }
    );
  }

  render() {
    return (
      <div
        ref='chartContainer'
        class='event-explore-dimension-echarts-e'
      >
        {this.data.length ? (
          <MonitorBaseEchart
            ref='baseEchartRef'
            width={this.width}
            height={this.height}
            customTooltips={this.seriesType === 'histogram' ? this.customTooltips : undefined}
            // needTooltips={false}
            options={this.options}
          />
        ) : (
          <div class='empty-chart'>{this.$t('查无数据')}</div>
        )}
      </div>
    );
  }
}

export default ofType<DimensionEchartsProps>().convert(DimensionEcharts);
