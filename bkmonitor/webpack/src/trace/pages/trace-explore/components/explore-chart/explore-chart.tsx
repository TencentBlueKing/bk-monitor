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
import { type PropType, computed, defineComponent, toRef, useTemplateRef, watch } from 'vue';
import { getCurrentInstance } from 'vue';
import { shallowRef } from 'vue';

import VueEcharts from 'vue-echarts';
import { useI18n } from 'vue-i18n';

import ChartSkeleton from '../../../../components/skeleton/chart-skeleton';
// import { useTraceExploreStore } from '@/store/modules/explore';
import ChartTitle from '../../../../plugins/components/chart-title';
import CommonLegend from '../../../../plugins/components/common-legend';
import { type LegendCustomOptions, useChartLegend } from './use-chart-legend';
import { useChartTitleEvent } from './use-chart-title-event';
import { type CustomOptions, useEcharts } from './use-echarts';

import type { DataZoomEvent } from './types';
import type { PanelModel } from 'monitor-ui/chart-plugins/typings';

import './explore-chart.scss';
export default defineComponent({
  name: 'ExploreChart',
  props: {
    /** 面板数据配置 */
    panel: {
      type: Object as PropType<PanelModel>,
      required: true,
    },
    /** 是否显示图表 Title 组件 */
    showTitle: {
      type: Boolean,
      default: true,
    },
    /** 查询参数 */
    params: {
      type: Object as PropType<Record<string, any>>,
      default: () => ({}),
    },
    customOptions: {
      type: Object as PropType<CustomOptions>,
      default: () => ({}),
    },
    /** 图例配置 */
    customLegendOptions: {
      type: Object as PropType<LegendCustomOptions>,
      default: () => ({}),
    },
    /** 是否展示复位按钮 */
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
  emits: ['dataZoomChange', 'durationChange', 'restore'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const chartInstance = useTemplateRef<InstanceType<typeof VueEcharts>>('echart');
    const instance = getCurrentInstance();
    const chartRef = useTemplateRef<HTMLElement>('chart');
    const chartMainRef = useTemplateRef<HTMLElement>('chartMain');
    const mouseIn = shallowRef(false);
    const panel = computed(() => props.panel);
    const params = computed(() => props.params);

    const { options, loading, metricList, targets, series, duration, chartId } = useEcharts(
      panel,
      chartMainRef,
      instance.appContext.config.globalProperties.$api,
      params,
      props.customOptions,
      {
        isMouseOver: mouseIn,
        hoverAllTooltips: toRef(props, 'hoverAllTooltips'),
      }
    );
    const { handleAlarmClick, handleMenuClick, handleMetricClick } = useChartTitleEvent(
      metricList,
      targets,
      panel.value.title,
      series,
      chartRef
    );
    const { legendData, handleSelectLegend } = useChartLegend(options, chartId, props.customLegendOptions);
    const handleDataZoom = (event: DataZoomEvent, echartOptions) => {
      chartInstance.value.dispatchAction({
        type: 'restore',
      });
      if (!mouseIn.value) return;
      const xAxisData = echartOptions.xAxis[0]?.data;
      if (!xAxisData.length || xAxisData.length <= 2) return;
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
    const handleMouseInChange = (v: boolean) => {
      mouseIn.value = v;
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
      loading,
      options,
      metricList,
      legendData,
      handleAlarmClick,
      handleMenuClick,
      handleMetricClick,
      handleSelectLegend,
      handleDataZoom,
      handleMouseInChange,
      t,
    };
  },
  render() {
    return (
      <div
        ref='chart'
        class='explore-chart'
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
            <div
              ref='chartMain'
              class='base-chart-container'
              onMouseout={() => this.handleMouseInChange(false)}
              onMouseover={() => this.handleMouseInChange(true)}
            >
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
                  onClick={() => this.$emit('restore')}
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
          <div class='empty-chart'>{this.t('暂无数据')}</div>
        )}
      </div>
    );
  },
});
