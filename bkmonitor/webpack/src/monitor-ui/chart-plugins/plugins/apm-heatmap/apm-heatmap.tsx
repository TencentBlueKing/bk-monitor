import { Component, Prop } from 'vue-property-decorator';
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
import { ofType } from 'vue-tsx-support';

import dayjs from 'dayjs';
// import { handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';

import { MONITOR_LINE_OPTIONS } from '../../../chart-plugins/constants';
import ChartHeader from '../../components/chart-title/chart-title';
import { CommonSimpleChart } from '../common-simple-chart';
import BaseEchart from '../monitor-base-echart';
import mockData from './test';

import type { PanelModel } from '../../../chart-plugins/typings';

import './apm-heatmap.scss';
interface IApmHeatmapProps {
  panel: PanelModel;
}
@Component
class ApmHeatmap extends CommonSimpleChart {
  @Prop() a: number;
  metrics = [];
  inited = false;
  options = {};
  empty = true;
  emptyText = window.i18n.tc('暂无数据');
  cancelTokens = [];
  async getPanelData() {
    if (!(await this.beforeGetPanelData())) {
      return;
    }
    if (this.inited) this.handleLoadingChange(true);
    this.emptyText = window.i18n.tc('加载中...');
    // const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
    await new Promise(r => setTimeout(r, 2000));
    const { data } = mockData;
    this.metrics = data.metrics;
    const series = data.series;
    if (series.length) {
      const xAxisCategory = new Set();
      const yAxisCategory = new Set();
      const seriesData = [];
      let seriesIndex = 0;
      let min = Number.MAX_VALUE;
      let max = Number.MIN_VALUE;
      for (const item of series) {
        let dataIndex = 0;
        for (const datapoint of item.datapoints) {
          xAxisCategory.add(datapoint[1]);
          seriesData.push([dataIndex, seriesIndex, datapoint[0]]);
          dataIndex += 1;
          min = Math.min(min, datapoint[0]);
          max = Math.max(max, datapoint[0]);
        }
        seriesIndex += 1;
        yAxisCategory.add(item.dimensions.le);
      }
      const xAxisData = Array.from(xAxisCategory);
      const yAxisData = Array.from(yAxisCategory);
      const minX = xAxisData.at(0);
      const maxX = xAxisData.at(-1);
      const duration = Math.abs(dayjs.tz(+maxX).diff(dayjs.tz(+minX), 'second'));
      this.options = {
        tooltip: {
          ...MONITOR_LINE_OPTIONS.tooltip,
          position: 'top',
          formatter: p => {
            if (p.data?.length < 2) {
              return '';
            }
            const xValue = xAxisData[p.data[0]];
            const xNextValue = xAxisData[p.data[0] - 1];
            const yValue = yAxisData[p.data[1]];
            const yNextValue = yAxisData[p.data[1] - 1];
            const demissionValue = p.data[2];
            const getUnit = (v: number) => {
              if (v >= 1) return 's';
              return 'ms';
            };
            return `<div class="monitor-chart-tooltips">
            <p class="tooltips-header">
                ${dayjs.tz(+xNextValue).format('YYYY-MM-DD HH:mm:ss')}
            </p>
            <p class="tooltips-header">
              ${dayjs.tz(+xValue).format('YYYY-MM-DD HH:mm:ss')}
            </p>
            <ul class="tooltips-content">
              <li class="tooltips-content-item">
                <span class="item-series"
                  style="background-color:${p.color};">
                </span>
                <span class="item-name">${yNextValue}${getUnit(yNextValue)} ~ ${yValue}${getUnit(yValue)}:</span>
                <span class="item-value">
                ${demissionValue || '--'}</span>
               </li>
            </ul>
            </div>`;
          },
          trigger: 'item',
          axisPointer: {
            type: 'none',
          },
        },
        grid: {
          ...MONITOR_LINE_OPTIONS.grid,
          bottom: 40,
        },
        xAxis: {
          type: 'category',
          data: xAxisData,
          splitArea: {
            show: true,
          },
          axisTick: {
            show: false,
          },
          axisLine: {
            show: false,
          },
          axisLabel: {
            formatter: (v: any) => {
              if (duration < 1 * 60) {
                return dayjs.tz(+v).format('mm:ss');
              }
              if (duration < 60 * 60 * 24 * 1) {
                return dayjs.tz(+v).format('HH:mm');
              }
              if (duration < 60 * 60 * 24 * 6) {
                return dayjs.tz(+v).format('MM-DD HH:mm');
              }
              if (duration <= 60 * 60 * 24 * 30 * 12) {
                return dayjs.tz(+v).format('MM-DD');
              }
              return dayjs.tz(+v).format('YYYY-MM-DD');
            },
            fontSize: 12,
            color: '#979BA5',
            showMinLabel: true,
            showMaxLabel: true,
            align: 'left',
          },
        },
        yAxis: {
          type: 'category',
          data: yAxisData,
          splitArea: {
            show: true,
          },
          axisLabel: {
            color: '#979BA5',
          },
          axisTick: {
            show: false,
          },
        },
        visualMap: {
          min,
          max,
          calculable: true,
          orient: 'horizontal',
          left: 'center',
          bottom: -6,
          itemWidth: 16,
          itemHeight: 240,
          color: ['#3A84FF', '#C5DBFF', '#EDF3FF', '#F0F1F5'],
          show: true,
        },
        series: [
          {
            type: 'heatmap',
            data: seriesData,
            itemStyle: {
              borderWidth: 2,
              borderColor: '#fff',
            },
            emphasis: {
              disabled: false,
            },
          },
        ],
      };
      this.inited = true;
      this.empty = false;
    } else {
      this.inited = this.metrics.length > 0;
      this.emptyText = window.i18n.tc('暂无数据');
      this.empty = true;
    }
    // this.cancelTokens = [];
    this.handleLoadingChange(false);
  }
  render() {
    return (
      <div class='apm-heatmap'>
        <ChartHeader
          descrition={this.panel.descrition}
          draging={this.panel.draging}
          isInstant={this.panel.instant}
          metrics={this.metrics}
          showAddMetric={false}
          showMore={false}
          subtitle={this.panel.subTitle || ''}
          title={this.panel.title}
        />
        {!this.empty ? (
          <div class={'apm-heatmap-content'}>
            <div
              ref='chart'
              class='chart-instance'
            >
              {this.inited && (
                <BaseEchart
                  ref='baseChart'
                  width={this.width}
                  height={this.height}
                  options={this.options}
                />
              )}
            </div>
          </div>
        ) : (
          <div class='empty-chart'>{this.emptyText}</div>
        )}
      </div>
    );
  }
}

export default ofType<IApmHeatmapProps>().convert(ApmHeatmap);
