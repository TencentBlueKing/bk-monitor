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
import { type PropType, computed, defineComponent, shallowRef, useTemplateRef } from 'vue';

import VueEcharts from 'vue-echarts';

import { type CustomOptions, useEchartsOptions } from '@/pages/trace-explore/components/explore-chart/use-echarts';

import type { EchartSeriesItem, SeriesItem } from '@/pages/trace-explore/components/explore-chart/types';
import type { IMetricSeriesResult } from '../typing';

import './metric-series-message.scss';

export default defineComponent({
  name: 'MetricSeriesMessage',
  props: {
    content: {
      type: String,
      default: '',
    },
    result: {
      type: Object as PropType<IMetricSeriesResult>,
      required: true,
    },
  },
  setup(props) {
    const CHART_HEIGHT = 200;
    const INIT_OPTIONS = { renderer: 'svg' as const };

    /** 折线样式定制：隐藏数据点、颜色对齐设计稿 */
    const metricSeriesCustomizer: CustomOptions['series'] = (series: EchartSeriesItem[]) =>
      series.map(item => {
        const color = typeof item.color === 'string' ? item.color : undefined;
        return {
          ...item,
          type: 'line',
          showSymbol: false,
          color,
          itemStyle: { color },
          lineStyle: {
            width: 2,
            type: 'solid',
            color,
          },
        };
      });

    /** 坐标轴定制：固定 y 轴 20–80% 三档，对齐设计稿刻度 */
    const metricSeriesOptionsCustomizer: CustomOptions['options'] = (options: Record<string, unknown>) => {
      const xAxis = Array.isArray(options.xAxis) ? options.xAxis : [options.xAxis];
      const yAxis = Array.isArray(options.yAxis) ? options.yAxis : [options.yAxis];
      return {
        ...options,
        toolbox: { show: false },
        grid: {
          containLabel: true,
          left: 4,
          right: 8,
          top: 10,
          bottom: 0,
        },
        xAxis: xAxis.map((axis: Record<string, unknown>) => {
          const axisLabel = (axis.axisLabel || {}) as Record<string, unknown>;
          return {
            ...axis,
            axisLabel: {
              ...axisLabel,
              color: '#8f9fbd',
              showMinLabel: true,
              showMaxLabel: true,
              align: 'center',
            },
          };
        }),
        yAxis: yAxis.map((axis: Record<string, unknown>) => {
          const axisLabel = (axis.axisLabel || {}) as Record<string, unknown>;
          return {
            ...axis,
            min: 20,
            max: 80,
            scale: false,
            splitNumber: 3,
            minInterval: 20,
            splitLine: {
              show: true,
              lineStyle: {
                color: '#e9edf5',
                type: 'solid',
              },
            },
            axisLabel: {
              ...axisLabel,
              color: '#8f9fbd',
              formatter: (value: number) => `${value}%`,
            },
          };
        }),
      };
    };

    const METRIC_SERIES_CUSTOM_OPTIONS: CustomOptions = {
      series: metricSeriesCustomizer,
      options: metricSeriesOptionsCustomizer,
    };

    const chartRef = useTemplateRef<HTMLElement>('chart');
    const mouseIn = shallowRef(false);

    const seriesList = computed(() =>
      props.result.series.map(
        (line): SeriesItem => ({
          alias: line.alias,
          target: line.key,
          type: 'line',
          color: line.color,
          unit: 'none',
          datapoints: line.datapoints,
        })
      )
    );

    const { options } = useEchartsOptions({
      chartRef,
      seriesList,
      customOptions: METRIC_SERIES_CUSTOM_OPTIONS,
      interactionState: {
        isMouseOver: mouseIn,
        hoverAllTooltips: false,
      },
    });

    const handleMouseInChange = (inChart: boolean) => {
      mouseIn.value = inChart;
    };

    return {
      options,
      handleMouseInChange,
      chartHeight: CHART_HEIGHT,
      initOptions: INIT_OPTIONS,
    };
  },
  render() {
    return (
      <div class='metric-series-message'>
        {this.content ? <p class='metric-series-message-text'>{this.content}</p> : null}
        <div class='metric-series-card'>
          <div class='metric-series-card-title'>{this.result.title}</div>
          {this.result.dimensions.length > 0 && (
            <div class='metric-series-card-tags'>
              {this.result.dimensions.map(item => (
                <span
                  key={item.key}
                  class='metric-series-tag'
                >
                  {`${item.alias} = ${item.value}`}
                </span>
              ))}
            </div>
          )}
          <div
            ref='chart'
            class='metric-series-card-chart'
            onMouseout={() => this.handleMouseInChange(false)}
            onMouseover={() => this.handleMouseInChange(true)}
          >
            <VueEcharts
              style={{ height: `${this.chartHeight}px` }}
              class='metric-series-echart'
              initOptions={this.initOptions}
              option={this.options}
              autoresize
            />
          </div>
          <div class='metric-series-card-legend'>
            {this.result.series.map(line => (
              <div
                key={line.key}
                class='metric-series-legend-item'
              >
                <span
                  class='metric-series-legend-bar'
                  style={{ backgroundColor: line.color }}
                />
                <span class='metric-series-legend-name'>{line.alias}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  },
});
