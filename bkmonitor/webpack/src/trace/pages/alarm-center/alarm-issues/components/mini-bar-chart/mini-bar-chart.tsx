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

import { type PropType, defineComponent, shallowRef, toRef, useTemplateRef } from 'vue';

import VueEcharts from 'vue-echarts';

import { type CustomOptions, useEchartsOptions } from '@/pages/trace-explore/components/explore-chart/use-echarts';

import type { EchartSeriesItem, SeriesItem } from '@/pages/trace-explore/components/explore-chart/types';

import './mini-bar-chart.scss';

/** 柱子默认颜色（灰色） */
const BAR_COLOR = '#8F9FBD';
/** 柱子 hover 高亮颜色 */
const BAR_HOVER_COLOR = '#7080A0';

/** vue-echarts 初始化配置（使用 SVG 渲染器，迷你图场景更轻量） */
const INIT_OPTIONS = { renderer: 'svg' as const };

/**
 * @description 迷你柱状图 customOptions.series 回调，注入 bar 专属样式
 * @param {EchartSeriesItem[]} series - createSeries 生成的标准系列数据
 * @returns {EchartSeriesItem[]} 注入迷你柱状图样式后的系列数据
 */
const miniBarSeriesCustomizer: CustomOptions['series'] = (series: EchartSeriesItem[]) => {
  return series.map(item => ({
    ...item,
    barMinWidth: 2,
    barMaxWidth: 6,
    barGap: '10%',
    barCategoryGap: '20%',
    itemStyle: {
      color: BAR_COLOR,
      borderRadius: [1, 1, 0, 0],
    },
    emphasis: {
      itemStyle: {
        color: BAR_HOVER_COLOR,
      },
    },
  }));
};

/**
 * @description 迷你柱状图 customOptions.options 回调，裁剪为紧凑无装饰配置
 * @param {any} options - createOptions 生成的标准 options
 * @returns {any} 适配迷你图场景的裁剪后 options
 */
const miniBarOptionsCustomizer: CustomOptions['options'] = (options: Record<string, unknown>) => {
  const xAxis = options.xAxis;
  const yAxis = options.yAxis;
  return {
    ...options,
    grid: {
      left: 0,
      right: 0,
      top: 1,
      bottom: 0,
      containLabel: false,
    },
    xAxis: Array.isArray(xAxis)
      ? xAxis.map((axis: Record<string, unknown>) => ({ ...axis, show: false }))
      : { ...(xAxis as Record<string, unknown>), show: false },
    yAxis: Array.isArray(yAxis)
      ? yAxis.map((axis: Record<string, unknown>) => ({ ...axis, show: false }))
      : { ...(yAxis as Record<string, unknown>), show: false },
    toolbox: { show: false },
  };
};

/** 迷你柱状图自定义配置（静态，无需每次 setup 重建） */
const MINI_BAR_CUSTOM_OPTIONS: CustomOptions = {
  series: miniBarSeriesCustomizer,
  options: miniBarOptionsCustomizer,
};

export default defineComponent({
  name: 'MiniBarChart',
  props: {
    /** 标准系列数据（SeriesItem[]），由调用方负责将原始数据转换为此格式 */
    seriesList: {
      type: Array as PropType<SeriesItem[]>,
      default: () => [],
    },
    /** 总数 */
    total: {
      type: Number,
    },
    /** 图表容器高度（px） */
    chartHeight: {
      type: Number,
      default: 38,
    },
    /** 图表联动 ID（相同 group 的 ECharts 实例会联动 tooltip / 高亮） */
    group: {
      type: String,
      default: '',
    },
    /** 联动时是否展示所有图表的 tooltip（默认 false，仅 hover 所在图表展示） */
    hoverAllTooltips: {
      type: Boolean,
      default: false,
    },
  },
  setup(props) {
    const chartRef = useTemplateRef<HTMLElement>('chart');
    /** 鼠标是否在当前图表区域内 */
    const mouseIn = shallowRef(false);

    const { options } = useEchartsOptions({
      chartRef,
      seriesList: toRef(props, 'seriesList'),
      customOptions: MINI_BAR_CUSTOM_OPTIONS,
      interactionState: {
        isMouseOver: mouseIn,
        hoverAllTooltips: toRef(props, 'hoverAllTooltips'),
      },
    });

    /**
     * @description 处理鼠标进入/离开图表区域，更新 mouseIn 状态
     * @param {boolean} v - 是否在图表区域内
     */
    const handleMouseInChange = (v: boolean) => {
      mouseIn.value = v;
    };

    return {
      options,
      handleMouseInChange,
    };
  },
  render() {
    return (
      <div class='mini-bar-chart-wrap'>
        <span class='mini-bar-total'>{this.total}</span>
        <div
          ref='chart'
          class='mini-bar-chart-container'
          onMouseout={() => this.handleMouseInChange(false)}
          onMouseover={() => this.handleMouseInChange(true)}
        >
          <VueEcharts
            style={{ height: `${this.chartHeight}px` }}
            class='mini-bar-chart'
            group={this.group || undefined}
            initOptions={INIT_OPTIONS}
            option={this.options}
            autoresize
          />
        </div>
      </div>
    );
  },
});
