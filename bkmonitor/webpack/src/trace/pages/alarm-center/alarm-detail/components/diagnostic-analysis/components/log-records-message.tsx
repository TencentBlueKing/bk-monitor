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
import { useI18n } from 'vue-i18n';

import { type CustomOptions, useEchartsOptions } from '@/pages/trace-explore/components/explore-chart/use-echarts';

import type { EchartSeriesItem, SeriesItem } from '@/pages/trace-explore/components/explore-chart/types';
import type { ILogRecordsResult, ILogTextToken, LogSeriesKey } from '../typing';

import './log-records-message.scss';

export default defineComponent({
  name: 'LogRecordsMessage',
  props: {
    content: {
      type: String,
      default: '',
    },
    result: {
      type: Object as PropType<ILogRecordsResult>,
      required: true,
    },
  },
  setup(props) {
    const CHART_HEIGHT = 148;
    const INIT_OPTIONS = { renderer: 'svg' as const };

    const SERIES_NAME_KEY: Record<LogSeriesKey, string> = {
      count: '日志条数',
    };

    /** 折线样式定制：隐藏数据点、颜色对齐设计稿 */
    const logSeriesCustomizer: CustomOptions['series'] = (series: EchartSeriesItem[]) =>
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

    /** 坐标轴定制：固定 y 轴 40–160 三档，对齐设计稿刻度 */
    const logSeriesOptionsCustomizer: CustomOptions['options'] = (options: Record<string, unknown>) => {
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
            min: 40,
            max: 160,
            scale: false,
            splitNumber: 3,
            minInterval: 40,
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
            },
          };
        }),
      };
    };

    const LOG_SERIES_CUSTOM_OPTIONS: CustomOptions = {
      series: logSeriesCustomizer,
      options: logSeriesOptionsCustomizer,
    };

    /** 渲染聚类文本片段：wildcard 为 Pattern 占位、value 为示例日志的实际取值 */
    const renderLogTokens = (tokens: ILogTextToken[]) =>
      tokens.map((item, index) => (
        <span
          key={`${item.text}-${index}`}
          class={['log-records-token', item.highlight ? `is-${item.highlight}` : '']}
        >
          {item.text}
        </span>
      ));

    const { t } = useI18n();
    const chartRef = useTemplateRef<HTMLElement>('chart');
    const mouseIn = shallowRef(false);

    const seriesList = computed(() =>
      props.result.series.map(
        (line): SeriesItem => ({
          alias: t(SERIES_NAME_KEY[line.key]),
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
      customOptions: LOG_SERIES_CUSTOM_OPTIONS,
      interactionState: {
        isMouseOver: mouseIn,
        hoverAllTooltips: false,
      },
    });

    const handleMouseInChange = (inChart: boolean) => {
      mouseIn.value = inChart;
    };

    return {
      t,
      options,
      handleMouseInChange,
      chartHeight: CHART_HEIGHT,
      initOptions: INIT_OPTIONS,
      seriesNameKey: SERIES_NAME_KEY,
      renderLogTokens,
    };
  },
  render() {
    return (
      <div class='log-records-message'>
        {this.content ? <p class='log-records-message-text'>{this.content}</p> : null}
        <div class='log-records-card'>
          <div class='log-records-card-title'>
            {this.t('该 Pattern 共匹配到 {n} 条日志', { n: this.result.matchCount })}
          </div>
          <div
            ref='chart'
            class='log-records-card-chart'
            onMouseout={() => this.handleMouseInChange(false)}
            onMouseover={() => this.handleMouseInChange(true)}
          >
            <VueEcharts
              style={{ height: `${this.chartHeight}px` }}
              class='log-records-echart'
              initOptions={this.initOptions}
              option={this.options}
              autoresize
            />
          </div>
          <div class='log-records-card-legend'>
            {this.result.series.map(line => (
              <div
                key={line.key}
                class='log-records-legend-item'
              >
                <span
                  class='log-records-legend-bar'
                  style={{ backgroundColor: line.color }}
                />
                <span class='log-records-legend-name'>{this.t(this.seriesNameKey[line.key])}</span>
              </div>
            ))}
          </div>
          <div class='log-records-section'>
            <div class='log-records-section-title'>Pattern:</div>
            <div class='log-records-code-block'>{this.renderLogTokens(this.result.pattern)}</div>
          </div>
          <div class='log-records-section'>
            <div class='log-records-section-title'>{this.t('示例日志')}:</div>
            {this.result.samples.map((sample, index) => (
              <div
                key={`sample-${index}`}
                class='log-records-code-block'
              >
                {this.renderLogTokens(sample)}
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  },
});
