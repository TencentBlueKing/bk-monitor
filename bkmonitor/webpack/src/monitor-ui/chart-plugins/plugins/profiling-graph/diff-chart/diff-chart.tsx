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
import { Component, Mixins, Prop, Ref, Watch } from 'vue-property-decorator';
import { ofType } from 'vue-tsx-support';

import { getValueFormat } from '../../../../monitor-echarts/valueFormats';
import loadingIcon from '../../../icons/spinner.svg';
import { ResizeMixin } from '../../../mixins';
import MonitorBaseEchart from '../../monitor-base-echart';

import './diff-chart.scss';
type IDiffChartEvents = {
  onBrushEnd(val): void;
};

interface IDiffChartProps {
  brushRect?: number[];
  colorIndex?: number;
  data?: Record<string, any>;
  loading?: boolean;
  title?: string;
}

@Component
class DiffChart extends Mixins<ResizeMixin>(ResizeMixin) {
  @Prop({ default: null }) data: Record<string, any>;
  @Prop({ default: '' }) title: string;
  @Prop({ default: () => [] }) brushRect: number[];
  @Prop({ default: 0 }) colorIndex: number;
  @Prop({ default: false }) loading: boolean;

  @Ref() baseEchart;

  options = {};
  brushCoordRange = [];
  width = 300;
  height = 120;

  defaultOptions = Object.freeze({
    animation: false,
    xAxis: [
      {
        type: 'time',
        axisLine: {
          lineStyle: {
            color: '#F0F1F5',
          },
        },
        axisLabel: {
          color: '#979BA5',
        },
        axisTick: {
          show: false,
        },
        splitLine: {
          show: false,
        },
      },
    ],
    toolbox: {
      showTitle: false,
      itemSize: 0,
      feature: {
        brush: {},
      },
    },
    series: [],
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(54,58,67,.88)',
      borderWidth: 0,
    },
    grid: {
      left: 16,
      top: 10,
      right: 40,
      bottom: 10,
      containLabel: true,
    },
  });

  @Watch('data', { immediate: true })
  handleDataChange() {
    this.setOptions();
  }

  @Watch('brushRect', { immediate: true })
  handleBrushRectChange(val) {
    this.brushCoordRange = val;
    this.setOptions();
  }

  setOptions(setChartBrush = true) {
    if (!this.data) return;
    this.options = {
      ...this.defaultOptions,
      yAxis: {
        type: 'value',
        axisTick: {
          show: false,
        },
        axisLabel: {
          formatter: (v: any) => {
            if (this.data.unit !== 'none') {
              const obj = getValueFormat(this.data.unit)(v, 0);
              return obj.text + (obj.suffix || '');
            }
            return v;
          },
        },
        splitNumber: 2,
        minInterval: 1,
        position: 'left',
      },
      brush: {
        xAxisIndex: 'all',
        brushLink: 'all',
        toolbox: ['lineX', 'clear'],
        brushStyle: {
          borderType: 'dashed',
          color: ['rgba(58, 132, 255, 0.1)', 'rgba(255, 86, 86, 0.1)'][this.colorIndex],
        },
        outOfBrush: {
          colorAlpha: 0.1,
        },
      },
      series: [
        {
          name: this.title,
          type: 'line',
          data: this.getSeriesData(false),
          lineStyle: {
            color: ['#3A84FF', '#EA3636'][this.colorIndex],
          },
          showSymbol: false,
          unitFormatter: this.data.unit !== 'none' ? getValueFormat(this.data.unit || '') : (v: any) => ({ text: v }),
          precision: 2,
        },
        {
          type: 'custom',
          renderItem: (param, api) => {
            if (Number.isNaN(api.value(1))) return;
            const isStart = this.brushCoordRange[0] >= api.value(0);
            const point = api.coord([api.value(0), api.value(1)]);
            return {
              type: 'path',
              shape: {
                pathData: 'M 1,0A 1,1 0 0,1 3,0L 3,50A 1,1 0 0,1 1,50L 1,0',
                x: isStart ? -1.5 : -1.5,
                y: -35,
                width: 4,
                height: 24,
              },
              position: point,
              style: api.style({
                stroke: ['#699DF4', '#FE8A8A'][this.colorIndex],
                lineWidth: 3,
              }),
            };
          },
          tooltip: {
            show: false,
          },
          data: this.getSeriesData(true),
          z: 100000,
          silent: true,
        },
      ],
    };
    if (setChartBrush) {
      this.$nextTick(() => {
        this.setChartBrush();
      });
    }
  }

  getSeriesData(isCustom = false) {
    if (!this.data?.datapoints?.length) return [];
    const data = this.data.datapoints.map(item => [item[1], item[0]]);
    if (!isCustom) return data;
    const customData = [];
    const [start, end] = this.brushCoordRange;
    for (let i = 0, len = data.length; i < len; i++) {
      const [time] = data[i];
      if (i === 0 || i === len - 1) {
        if (start < time || start > time) {
          customData.push([start, 1]);
        }
        if (end < time || end > time) {
          customData.push([end, 1]);
        }
        customData.push([time, null]);
        continue;
      }
      customData.push([time, null]);
      if (!this.brushCoordRange.length) continue;
      const [preTime] = data[i - 1];
      const [nextTime] = data[i + 1];
      if (start >= preTime && start <= time) {
        customData.push([start, 1]);
        continue;
      }
      if (end >= time && end <= nextTime) {
        customData.push([end, 1]);
      }
    }
    return customData;
  }

  /** 设置图表框选区域 */
  setChartBrush() {
    this.baseEchart?.dispatchAction({
      type: 'brush',
      areas: this.brushCoordRange.length
        ? [
            {
              brushType: 'lineX',
              xAxisIndex: 0,
              coordRange: this.brushCoordRange,
            },
          ]
        : [],
    });
  }

  handleBrushEnd(data) {
    const coordRange = data.areas?.[0]?.coordRange || [];
    if (coordRange.length) {
      this.brushCoordRange = coordRange;
      this.$emit('brushEnd', this.brushCoordRange);
    }
  }
  handleBrush(data) {
    const coordRange = data.areas?.[0]?.coordRange || [];
    if (coordRange.length) {
      this.brushCoordRange = coordRange;
    }
    this.setOptions(!coordRange.length);
  }

  render() {
    return (
      <div class='diff-chart-card'>
        <div class='chart-title'>
          {this.$t('查询项')}
          {this.loading && (
            <img
              class='chart-loading-icon'
              alt='loading'
              src={loadingIcon}
            />
          )}
        </div>
        <div
          ref='chart'
          class='diff-chart-wrap'
        >
          {this.data ? (
            <MonitorBaseEchart
              ref='baseEchart'
              width={this.width}
              height={this.height}
              notMerge={false}
              options={this.options}
              toolbox={['brush', 'dataZoom']}
              onBrush={this.handleBrush}
              onBrushEnd={this.handleBrushEnd}
              onLoaded={this.setChartBrush}
            />
          ) : (
            <div class='empty-chart'>{this.$t('查无数据')}</div>
          )}
        </div>
      </div>
    );
  }
}

export default ofType<IDiffChartProps, IDiffChartEvents>().convert(DiffChart);
