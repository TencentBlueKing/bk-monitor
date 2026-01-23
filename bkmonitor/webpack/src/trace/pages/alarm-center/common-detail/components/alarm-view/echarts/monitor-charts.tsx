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

import { type PropType, computed, defineComponent, getCurrentInstance, useTemplateRef, watch } from 'vue';

import VueEcharts from 'vue-echarts';

import { type CustomOptions, useEcharts } from '../../../../../trace-explore/components/explore-chart/use-echarts';
import ChartSkeleton from '@/components/skeleton/chart-skeleton';
import {
  type LegendCustomOptions,
  useChartLegend,
} from '@/pages/trace-explore/components/explore-chart/use-chart-legend';
import { useChartTitleEvent } from '@/pages/trace-explore/components/explore-chart/use-chart-title-event';
import ChartTitle from '@/plugins/components/chart-title';
import CommonLegend from '@/plugins/components/common-legend';

import type { DataZoomEvent } from '@/pages/trace-explore/components/explore-chart/types';
import type { ChartTitleMenuType, IMenuItem } from '@/plugins/typings';
import type { PanelModel } from 'monitor-ui/chart-plugins/typings';

import './monitor-charts.scss';

export default defineComponent({
  name: 'MonitorCharts',
  props: {
    panel: {
      type: Object as PropType<PanelModel>,
      required: true,
    },
    showTitle: {
      type: Boolean,
      default: true,
    },
    menuList: {
      type: Array as PropType<ChartTitleMenuType[]>,
      default: () => ['more', 'explore', 'area', 'drill-down', 'relate-alert'],
    },
    customLegendOptions: {
      type: Object as PropType<LegendCustomOptions>,
      default: () => ({}),
    },
    params: {
      type: Object as PropType<Record<string, any>>,
      default: () => ({}),
    },
    customOptions: {
      type: Object as PropType<CustomOptions>,
      default: () => ({}),
    },
    customMenuClick: {
      type: Array as PropType<ChartTitleMenuType[]>,
      default: () => [],
    },
    showRestore: {
      type: Boolean,
      default: false,
    },
    showAddMetric: {
      type: Boolean,
      default: true,
    },
  },
  emits: ['dataZoomChange', 'durationChange', 'restore', 'click', 'menuClick', 'zrClick'],
  setup(props, { emit }) {
    const chartInstance = useTemplateRef<InstanceType<typeof VueEcharts>>('echart');
    const instance = getCurrentInstance();
    const chartRef = useTemplateRef<HTMLElement>('chart');
    const panel = computed(() => props.panel);
    const params = computed(() => props.params);

    const { options, loading, metricList, targets, series, duration, chartId } = useEcharts(
      panel,
      chartRef,
      instance.appContext.config.globalProperties.$api,
      params,
      props.customOptions
    );
    const { handleAlarmClick, handleMenuClick, handleMetricClick } = useChartTitleEvent(
      metricList,
      targets,
      panel.value?.title,
      series,
      chartRef
    );
    const { legendData, handleSelectLegend } = useChartLegend(options, chartId, props.customLegendOptions);
    const handleDataZoom = (event: DataZoomEvent, echartOptions) => {
      const xAxisData = echartOptions.xAxis[0]?.data;
      if (!xAxisData.length || xAxisData.length <= 2) return;
      chartInstance.value.dispatchAction({
        type: 'restore',
      });
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

    const handleCustomMenuClick = (item: IMenuItem) => {
      if (props.customMenuClick?.includes(item.id)) {
        emit('menuClick', item);
        return;
      }
      handleMenuClick(item);
    };

    watch(
      () => duration.value,
      val => {
        emit('durationChange', val);
      }
    );

    watch(
      [loading, options],
      async () => {
        if (!loading.value && options.value) {
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
      loading,
      options,
      metricList,
      legendData,
      handleClickRestore,
      handleAlarmClick,
      handleCustomMenuClick,
      handleMetricClick,
      handleSelectLegend,
      handleDataZoom,
      handleClick,
      handleZrClick,
    };
  },
  render() {
    return (
      <div
        ref='chart'
        class='monitor-charts'
      >
        {this.panel && this.showTitle && (
          <ChartTitle
            class='draggable-handle'
            dragging={this.panel.dragging}
            isInstant={this.panel.instant}
            menuList={this.menuList}
            metrics={this.metricList}
            showAddMetric={this.showAddMetric}
            showMore={true}
            subtitle={this.panel.subTitle || ''}
            title={this.panel.title}
            onAlarmClick={this.handleAlarmClick}
            onAllMetricClick={this.handleMetricClick}
            onMenuClick={this.handleCustomMenuClick}
            onMetricClick={this.handleMetricClick}
            onSelectChild={({ child }) => this.handleCustomMenuClick(child)}
          >
            {{
              customTools: this.$slots?.customTools,
            }}
          </ChartTitle>
        )}

        {this.loading ? (
          <ChartSkeleton />
        ) : this.options ? (
          <>
            <div class='echart-container'>
              <VueEcharts
                ref='echart'
                group={this.panel?.dashboardId}
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
