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

import { type PropType, computed, defineComponent, shallowRef } from 'vue';

import VueEcharts from 'vue-echarts';

import { formatTraceTableDate } from '../../../../../components/trace-view/utils/date';

import type { BarSeriesOption } from 'echarts/charts';
import type { GridComponentOption, TooltipComponentOption } from 'echarts/components';
import type { ComposeOption } from 'echarts/core';

import './mini-bar-chart.scss';

/** 柱子默认颜色（灰色） */
const BAR_COLOR = '#8F9FBD';
/** 柱子 hover 高亮颜色 */
const BAR_HOVER_COLOR = '#7080A0';
/** tooltip 样式类名（挂载到 body，需全局样式） */
const TOOLTIP_CLASS = 'mini-bar-chart-tooltip';

/** 迷你柱状图 ECharts 配置类型 */
type MiniBarChartOption = ComposeOption<BarSeriesOption | GridComponentOption | TooltipComponentOption>;

/** vue-echarts 初始化配置（使用 SVG 渲染器，迷你图场景更轻量） */
const INIT_OPTIONS = { renderer: 'svg' as const };

export default defineComponent({
  name: 'MiniBarChart',
  props: {
    /** 时间序列数据 [[毫秒时间戳, 数量], ...] */
    data: {
      type: Array as PropType<[number, number][]>,
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
    /** 鼠标是否在当前图表区域内 */
    const mouseIn = shallowRef(false);

    /**
     * @description 构建 ECharts 响应式配置项，data 变化时自动触发重新计算
     * @returns {MiniBarChartOption} ECharts option
     */
    const options = computed<MiniBarChartOption>(() => {
      const data = props.data || [];
      const categories: number[] = [];
      const values: number[] = [];
      for (const [ts, count] of data) {
        categories.push(ts);
        values.push(count);
      }

      return {
        animation: false,
        grid: {
          left: 0,
          right: 0,
          top: 1,
          bottom: 0,
        },
        xAxis: {
          type: 'category',
          show: false,
          data: categories,
        },
        yAxis: {
          type: 'value',
          show: false,
        },
        tooltip: {
          show: true,
          trigger: 'axis',
          appendToBody: true,
          className: TOOLTIP_CLASS,
          padding: [6, 8],
          transitionDuration: 0,
          formatter: ((params: unknown) => {
            // 联动场景：非 hover 所在图表且未开启 hoverAllTooltips 时不展示 tooltip
            if (!mouseIn.value && !props.hoverAllTooltips) return '';
            const item = Array.isArray(params) ? params[0] : params;
            if (!item) return '';
            const time = formatTraceTableDate(item.name as number);
            const value = item.value ?? 0;
            return `<div><div>${time}</div><div>${window.i18n.t('数量')}：${value}</div></div>`;
          }) as TooltipComponentOption['formatter'],
        },
        series: [
          {
            type: 'bar',
            data: values,
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
          },
        ],
      };
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
