/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { Component, Mixins, Prop, Ref, Watch } from 'vue-property-decorator';
import { ofType } from 'vue-tsx-support';

import dayjs from 'dayjs';
import deepmerge from 'deepmerge';
import { deepClone } from 'monitor-common/utils';
import PageLegend from 'monitor-ui/chart-plugins/components/chart-legend/page-legend';
import { MONITOR_BAR_OPTIONS, MONITOR_LINE_OPTIONS } from 'monitor-ui/chart-plugins/constants';
import { ResizeMixin } from 'monitor-ui/chart-plugins/mixins';
import MonitorBaseEchart from 'monitor-ui/chart-plugins/plugins/monitor-base-echart';
import { getSeriesMaxInterval, getTimeSeriesXInterval } from 'monitor-ui/chart-plugins/utils/axis';

import type { ILegendItem, LegendActionType, MonitorEchartOptions } from 'monitor-ui/chart-plugins/typings';

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

  legendList: ILegendItem[] = [];

  get LegendShowMap(): Record<string, boolean> {
    return this.legendList.reduce((acc, cur) => {
      acc[cur.name] = cur.show;
      return acc;
    }, {});
  }

  width = 370;
  height = 136;

  @Watch('data', { immediate: true })
  handleDataChange(value: any[]) {
    this.legendList = value.map(item => ({ name: item.name, color: item.color, show: true }));
  }

  handleSetFormatterFunc(seriesData: any, onlyBeginEnd = false) {
    let formatterFunc = null;
    const [firstItem] = seriesData;
    const lastItem = seriesData[seriesData.length - 1];
    const val = new Date('2010-01-01').getTime();
    const getXVal = (timeVal: any) => {
      if (!timeVal) return timeVal;
      return timeVal[0] > val ? timeVal[0] : timeVal[1];
    };
    const minX = Array.isArray(firstItem) ? getXVal(firstItem) : getXVal(firstItem?.value);
    const maxX = Array.isArray(lastItem) ? getXVal(lastItem) : getXVal(lastItem?.value);

    minX &&
      maxX &&
      // biome-ignore lint/suspicious/noAssignInExpressions: <explanation>
      (formatterFunc = (v: any) => {
        const duration = Math.abs(dayjs.tz(maxX).diff(dayjs.tz(minX), 'second'));
        if (onlyBeginEnd && v > minX && v < maxX) {
          return '';
        }
        if (duration < 1 * 60) {
          return dayjs.tz(v).format('mm:ss');
        }
        if (duration < 60 * 60 * 24 * 1) {
          return dayjs.tz(v).format('HH:mm');
        }
        if (duration < 60 * 60 * 24 * 6) {
          return dayjs.tz(v).format('MM-DD HH:mm');
        }
        if (duration <= 60 * 60 * 24 * 30 * 12) {
          return dayjs.tz(v).format('MM-DD');
        }
        return dayjs.tz(v).format('YYYY-MM-DD');
      });
    return formatterFunc;
  }

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

  get barOptions(): MonitorEchartOptions {
    const series = this.data.map(item => ({
      type: 'bar',
      name: '',
      data: item.datapoints.map(point => [point[1], point[0]]),
      symbol: 'none',
      z: 6,
      itemStyle: {
        color: item.color,
      },
    }));

    return deepmerge(
      deepClone(MONITOR_BAR_OPTIONS),
      {
        xAxis: {
          type: 'category',
          boundaryGap: true,
          splitNumber: 5,
          axisLabel: {
            showMaxLabel: true,
            showMinLabel: true,
            hideOverlap: true,
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

  get lineOptions(): MonitorEchartOptions {
    const { maxSeriesCount, maxXInterval } = getSeriesMaxInterval(this.data);
    const series = this.data
      .map(item => ({
        type: 'line',
        name: item.name,
        data: item.datapoints.map(point => [point[1], point[0]]),
        symbol: 'none',
        z: 6,
        lineStyle: {
          color: item.color,
        },
      }))
      .filter(item => this.LegendShowMap[item.name]);
    const xInterval = getTimeSeriesXInterval(maxXInterval, this.width, maxSeriesCount);
    const formatterFunc = this.handleSetFormatterFunc(series[0]?.data || []);
    return deepmerge(
      deepClone(MONITOR_LINE_OPTIONS),
      {
        xAxis: {
          type: 'time',
          splitNumber: 4,
          axisLabel: {
            formatter: formatterFunc || '{value}',
            hideOverlap: true,
          },
          ...xInterval,
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

  get options(): MonitorEchartOptions {
    return this.seriesType === 'histogram' ? this.barOptions : this.lineOptions;
  }

  handleSelectLegend({ actionType, item }: { actionType: LegendActionType; item: ILegendItem }) {
    let legendList: ILegendItem[] = deepClone(this.legendList);
    if (actionType === 'click') {
      const hasHidden = legendList.some(legendItem => !legendItem.show);
      legendList = legendList.map(legendItem => {
        if (legendItem.name === item.name) {
          legendItem.show = true;
        } else {
          legendItem.show = hasHidden && item.show;
        }
        return legendItem;
      });
    } else if (actionType === 'shift-click') {
      const result = legendList.find(legendItem => legendItem.name === item.name);
      result.show = !result.show;
    }
    this.legendList = legendList;
  }

  render() {
    return (
      <div
        ref='chartContainer'
        class={['event-explore-dimension-echarts-e', { 'has-legend': this.seriesType === 'line' }]}
      >
        {this.data.length ? (
          <div class='event-explore-dimension-echarts-content'>
            <MonitorBaseEchart
              ref='baseEchartRef'
              width={this.width}
              height={this.height}
              customTooltips={this.seriesType === 'histogram' ? this.customTooltips : undefined}
              options={this.options}
            />
          </div>
        ) : (
          <div class='empty-chart'>{this.$t('查无数据')}</div>
        )}

        {this.seriesType === 'line' && (
          <PageLegend
            legendData={this.legendList}
            wrapHeight={40}
            onSelectLegend={this.handleSelectLegend}
          />
        )}
      </div>
    );
  }
}

export default ofType<DimensionEchartsProps>().convert(DimensionEcharts);
