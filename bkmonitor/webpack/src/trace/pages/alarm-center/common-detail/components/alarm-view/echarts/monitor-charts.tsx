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

import { useMonitorEcharts } from './use-monitor-echarts';
import ChartSkeleton from '@/components/skeleton/chart-skeleton';
import { useChartLegend } from '@/pages/trace-explore/components/explore-chart/use-chart-legend';
import { useChartTitleEvent } from '@/pages/trace-explore/components/explore-chart/use-chart-title-event';
import ChartTitle from '@/plugins/components/chart-title';
import CommonLegend from '@/plugins/components/common-legend';

import type { DataZoomEvent } from '@/pages/trace-explore/components/explore-chart/types';
import type { LegendOptions } from '@/plugins/typings';
import type { PanelModel } from 'monitor-ui/chart-plugins/typings';

import './monitor-charts.scss';

export interface FormatterOptions {
  params?: (params: any) => any;
  seriesData?: (data: any) => any;
}

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
    legendOptions: {
      type: Object as PropType<LegendOptions>,
      default: () => ({}),
    },
    formatterOptions: {
      type: Object as PropType<FormatterOptions>,
      default: () => ({ disabledLegendClick: [], legendIconMap: {} }),
    },
    params: {
      type: Object as PropType<Record<string, any>>,
      default: () => ({}),
    },
    showRestore: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['dataZoomChange', 'durationChange', 'restore'],
  setup(props, { emit }) {
    const chartInstance = useTemplateRef<InstanceType<typeof VueEcharts>>('echart');
    const instance = getCurrentInstance();
    const chartRef = useTemplateRef<HTMLElement>('chart');
    const panel = computed(() => props.panel);
    const params = computed(() => props.params);

    const { options, loading, metricList, targets, series, duration, chartId } = useMonitorEcharts(
      panel,
      chartRef,
      instance.appContext.config.globalProperties.$api,
      params,
      props.formatterOptions
    );
    const { handleAlarmClick, handleMenuClick, handleMetricClick } = useChartTitleEvent(
      metricList,
      targets,
      panel.value.title,
      series,
      chartRef
    );
    const { legendData, handleSelectLegend } = useChartLegend(options, chartId, props.legendOptions);
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
      handleMenuClick,
      handleMetricClick,
      handleSelectLegend,
      handleDataZoom,
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
            menuList={['more', 'explore', 'area', 'drill-down', 'relate-alert']}
            metrics={this.metricList}
            showAddMetric={true}
            showMore={true}
            subtitle={this.panel.subTitle || ''}
            title={this.panel.title}
            onAlarmClick={this.handleAlarmClick}
            onAllMetricClick={this.handleMetricClick}
            onMenuClick={this.handleMenuClick}
            onMetricClick={this.handleMetricClick}
            onSelectChild={({ child }) => this.handleMenuClick(child)}
          />
        )}

        {this.loading ? (
          <ChartSkeleton />
        ) : this.options ? (
          <>
            <div class='echart-container'>
              <VueEcharts
                ref='echart'
                group={this.panel.dashboardId}
                option={this.options}
                autoresize
                onDatazoom={e => this.handleDataZoom(e, this.options)}
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
              legendOptions={this.legendOptions}
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
