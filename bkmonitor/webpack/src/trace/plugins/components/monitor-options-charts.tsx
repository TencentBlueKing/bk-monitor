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

import { type PropType, defineComponent, shallowRef, toRef, useTemplateRef, watch } from 'vue';

import VueEcharts from 'vue-echarts';

import ChartSkeleton from '@/components/skeleton/chart-skeleton';
import {
  type LegendCustomOptions,
  useChartLegend,
} from '@/pages/trace-explore/components/explore-chart/use-chart-legend';
import { type CustomOptions, useEchartsOptions } from '@/pages/trace-explore/components/explore-chart/use-echarts';
import CommonLegend from '@/plugins/components/common-legend';

import type { DataZoomEvent, SeriesItem } from '@/pages/trace-explore/components/explore-chart/types';

import './monitor-options-charts.scss';

export default defineComponent({
  name: 'MonitorOptionsCharts',
  props: {
    dashboardId: {
      type: String,
      default: '',
    },
    loading: {
      type: Boolean,
      default: false,
    },
    seriesList: {
      type: Array as PropType<SeriesItem[]>,
      default: () => [],
    },
    customLegendOptions: {
      type: Object as PropType<LegendCustomOptions>,
      default: () => ({}),
    },
    customOptions: {
      type: Object as PropType<CustomOptions>,
      default: () => ({}),
    },
    showRestore: {
      type: Boolean,
      default: false,
    },
    /** 所有联动图表中存在有一个图表触发 hover 是否展示所有联动图表的 tooltip(默认 false) */
    hoverAllTooltips: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['dataZoomChange', 'restore', 'click', 'zrClick'],
  setup(props, { emit }) {
    const chartInstance = useTemplateRef<InstanceType<typeof VueEcharts>>('echart');
    const chartRef = useTemplateRef<HTMLElement>('chart');
    const mouseIn = shallowRef(false);

    const { options, chartId } = useEchartsOptions({
      chartRef,
      customOptions: props.customOptions,
      seriesList: toRef(props, 'seriesList'),
      interactionState: {
        isMouseOver: mouseIn,
        hoverAllTooltips: toRef(props, 'hoverAllTooltips'),
      },
    });
    const { legendData, handleSelectLegend } = useChartLegend(options, chartId, props.customLegendOptions);
    const handleDataZoom = (event: DataZoomEvent, echartOptions) => {
      const xAxisData = echartOptions.xAxis[0]?.data;
      if (!xAxisData.length || xAxisData.length <= 2) return;
      chartInstance.value.dispatchAction({
        type: 'restore',
      });

      if (!mouseIn.value) return;
      let { startValue, endValue } = event.batch[0];
      startValue = Math.max(0, startValue);
      endValue = Math.min(endValue, xAxisData.length - 1);
      let endTime = xAxisData[endValue];
      let startTime = xAxisData[startValue];
      if (startValue === endValue) {
        endTime = xAxisData[endValue + 1];
      }
      if (!endTime) {
        endTime = xAxisData[startValue] + 1000;
      }
      if (!startTime) {
        startTime = xAxisData[0];
      }
      emit('dataZoomChange', [startTime, endTime]);
    };

    const handleClickRestore = () => {
      emit('restore');
    };

    /**
     * @description 处理点击事件
     */
    const handleClick = params => {
      emit('click', params);
    };

    /**
     * @description 处理空白处点击事件(zr:click)
     */
    const handleZrClick = params => {
      const pointInPixel = [params.offsetX, params.offsetY];
      // x轴数据的索引值
      const pointInGrid = chartInstance.value.convertFromPixel({ seriesIndex: 0 }, pointInPixel);
      // 所点击点的X轴坐标点所在X轴data的下标
      const xIndex = pointInGrid[0];
      // 使用getOption() 获取图表的option
      const op = chartInstance.value.getOption();
      // 获取到x轴的索引值和option之后，我们就可以获取我们需要的任意数据。
      // 点击点的X轴对应坐标的名称
      const xAxis = op.xAxis[0].data[xIndex];
      // 点击点的series -- data对应的值
      const yAxis = op.series[0].data[xIndex]?.value;
      emit('zrClick', { ...params, xAxis, yAxis });
    };

    const handleMouseInChange = (v: boolean) => {
      mouseIn.value = v;
    };

    watch(
      [options],
      async () => {
        if (!props.loading && options.value) {
          setTimeout(() => {
            chartInstance.value?.dispatchAction({
              type: 'takeGlobalCursor',
              key: 'dataZoomSelect',
              dataZoomSelectActive: true,
            });
          }, 1000);
        }
      },
      {
        immediate: false,
        flush: 'post',
      }
    );

    return {
      chartInstance,
      options,
      legendData,
      handleClickRestore,
      handleSelectLegend,
      handleDataZoom,
      handleClick,
      handleZrClick,
      handleMouseInChange,
    };
  },
  render() {
    return (
      <div
        ref='chart'
        class='monitor-options-charts'
      >
        {this.loading ? (
          <ChartSkeleton />
        ) : this.options ? (
          <>
            <div
              ref='echartContainer'
              class='echart-container'
              onMouseout={() => this.handleMouseInChange(false)}
              onMouseover={() => this.handleMouseInChange(true)}
            >
              <VueEcharts
                ref='echart'
                group={this.dashboardId}
                option={this.options}
                autoresize
                onClick={this.handleClick}
                onDatazoom={e => this.handleDataZoom(e, this.options)}
                onZr:click={this.handleZrClick}
              />

              {this.showRestore && (
                <span
                  class='chart-restore'
                  onClick={this.handleClickRestore}
                >
                  {this.$t('复位')}
                </span>
              )}
            </div>

            <CommonLegend
              legendData={this.legendData}
              onSelectLegend={this.handleSelectLegend}
            />
          </>
        ) : (
          <div class='empty-chart'>{this.$t('暂无数据')}</div>
        )}
      </div>
    );
  },
});
