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

/**
 * @description 告警视图专用 MonitorCharts
 *
 * 基于公共 MonitorCharts 抽离，仅供 failure-view 使用，避免改动公共文件行为。
 * 相对公共版额外能力：
 *  1. 缩放后锁定手动框选（showRestore=true 时关闭 dataZoomSelect，复位后解锁）
 *  2. loading 卸载时重置 mouseIn，防止 connect 误广播错误时间范围
 *  3. dataZoom 时间用 getOption() 计算，并在索引非法时降级为百分比
 */

import {
  type PropType,
  type Ref,
  computed,
  defineComponent,
  getCurrentInstance,
  inject,
  nextTick,
  shallowRef,
  toRef,
  useTemplateRef,
  watch,
} from 'vue';

import VueEcharts from 'vue-echarts';

import { type CustomOptions, useEcharts } from '../../../trace-explore/components/explore-chart/use-echarts';
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

/** 复用公共 MonitorCharts 样式，避免样式分叉 */
import '../../../alarm-center/common-detail/components/alarm-view/echarts/monitor-charts.scss';

/**
 * provide/inject 键：告警视图注入本组件，公共 AlarmCharts 未注入时仍使用公共 MonitorCharts
 */
export const FAILURE_VIEW_MONITOR_CHARTS_KEY = 'FailureViewMonitorCharts';

/**
 * provide/inject 键：同步「当前图是否有可展示数据」给 FailureViewAlarmChart。
 * 无数据图不展示复位、也不接收 dataZoom 联动。
 */
export const FAILURE_VIEW_CHART_HAS_DATA_KEY = 'FailureViewChartHasData';

export default defineComponent({
  name: 'FailureViewMonitorCharts',
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
    downSampleRange: {
      type: String,
      default: 'auto',
    },
    showRestore: {
      type: Boolean,
      default: false,
    },
    showAddMetric: {
      type: Boolean,
      default: true,
    },
    /** 联动组内任意图表 hover 时，是否在所有同组图表上展示 tooltip */
    hoverAllTooltips: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['dataZoomChange', 'durationChange', 'restore', 'click', 'menuClick', 'zrClick', 'mouseover', 'mouseout'],
  setup(props, { emit }) {
    const chartInstance = useTemplateRef<InstanceType<typeof VueEcharts>>('echart');
    const instance = getCurrentInstance();
    const chartRef = useTemplateRef<HTMLElement>('chart');
    const echartContainerRef = useTemplateRef<HTMLElement>('echartContainer');
    const panel = computed(() => props.panel);
    const params = computed(() => props.params);
    /** 鼠标是否在本图容器内：仅主动 hover 框选才向外 emit */
    const mouseIn = shallowRef(false);
    /**
     * 父级 FailureViewAlarmChart 注入的「是否有数据」标记。
     * loading 期间不改写，避免缩放重拉时短暂清空导致联动被误取消。
     */
    const chartHasDataRef = inject<null | Ref<boolean>>(FAILURE_VIEW_CHART_HAS_DATA_KEY, null);

    /* 降采样计算 */
    const downSampleRangeComputed = (timeRange: number[]) => {
      if (props.downSampleRange === 'auto') {
        let width = 1;
        if (echartContainerRef.value) {
          width = echartContainerRef.value.clientWidth;
        } else {
          width = chartRef.value?.clientWidth - (panel.value?.options?.legend?.placement === 'right' ? 320 : 0);
        }
        const size = (timeRange[1] - timeRange[0]) / width;
        return size > 0 ? `${Math.ceil(size)}s` : undefined;
      }
      return props.downSampleRange;
    };

    const { options, loading, metricList, targets, series, duration, chartId } = useEcharts({
      panel,
      chartRef,
      $api: instance.appContext.config.globalProperties.$api,
      params,
      customOptions: props.customOptions,
      interactionState: {
        isMouseOver: mouseIn,
        hoverAllTooltips: toRef(props, 'hoverAllTooltips'),
      },
      downSampleRangeComputed: props.downSampleRange ? downSampleRangeComputed : undefined,
    });
    const { handleAlarmClick, handleMenuClick, handleMetricClick } = useChartTitleEvent(
      metricList,
      targets,
      panel.value?.title,
      series,
      chartRef
    );
    const { legendData, handleSelectLegend } = useChartLegend(options, chartId, props.customLegendOptions);

    /**
     * @description 是否允许手动框选（已缩放且显示复位时锁定）
     */
    const canBrushZoom = () => !props.showRestore;

    /**
     * @description 同步 dataZoom 框选游标开关
     * vue-echarts 未 init 时 dispatchAction 会抛错，需判断 chart 是否就绪。
     */
    const syncDataZoomBrush = (active: boolean) => {
      const inst = chartInstance.value as { chart?: unknown; dispatchAction?: (payload: object) => void } | null;
      if (!inst?.chart || typeof inst.dispatchAction !== 'function') return;
      try {
        inst.dispatchAction({
          type: 'takeGlobalCursor',
          key: 'dataZoomSelect',
          dataZoomSelectActive: active,
        });
      } catch {
        // 实例竞态未就绪时忽略，后续 setTimeout 会再尝试
      }
    };

    const handleDataZoom = (event: DataZoomEvent) => {
      /**
       * 使用 echarts 实例 getOption() 取实际 xAxis，避免与 Vue options 不同步。
       */
      const inst = chartInstance.value as { chart?: unknown; getOption?: () => any; dispatchAction?: Function } | null;
      if (!inst?.chart || typeof inst.getOption !== 'function') return;
      let op: any;
      try {
        op = inst.getOption();
      } catch {
        return;
      }
      const xAxisData = op?.xAxis?.[0]?.data;
      if (!xAxisData?.length || xAxisData.length <= 2) return;

      inst.dispatchAction?.({
        type: 'restore',
      });

      // 仅处理本图主动 hover 框选；connect 联动的 dataZoom 一律忽略
      if (!mouseIn.value) return;
      // 缩放锁定期间忽略后续框选
      if (!canBrushZoom()) return;

      const { start, end, startValue, endValue } = event.batch[0];

      /**
       * 优先用 startValue / endValue（category 轴为 ordinal 索引），
       * 非法时降级为 start / end 百分比换算。
       */
      let startIdx: number;
      let endIdx: number;
      if (
        Number.isFinite(startValue) &&
        Number.isFinite(endValue) &&
        startValue >= 0 &&
        endValue <= xAxisData.length - 1
      ) {
        startIdx = Math.max(0, Math.round(startValue));
        endIdx = Math.min(Math.round(endValue), xAxisData.length - 1);
      } else {
        startIdx = Math.max(0, Math.round((start / 100) * (xAxisData.length - 1)));
        endIdx = Math.min(Math.round((end / 100) * (xAxisData.length - 1)), xAxisData.length - 1);
      }

      let endTime = xAxisData[endIdx];
      let startTime = xAxisData[startIdx];
      if (startIdx === endIdx) {
        endTime = xAxisData[endIdx + 1];
      }
      if (!endTime) {
        endTime = xAxisData[startIdx] + 1000;
      }
      if (!startTime) {
        startTime = xAxisData[0];
      }
      emit('dataZoomChange', [startTime, endTime]);
    };

    const handleClick = params => {
      emit('click', params);
    };

    const handleMouseover = (params: Record<string, any>) => {
      emit('mouseover', params);
    };

    const handleMouseout = (params: Record<string, any>) => {
      emit('mouseout', params);
    };

    const handleZrClick = params => {
      const pointInPixel = [params.offsetX, params.offsetY];
      const pointInGrid = chartInstance.value.convertFromPixel({ seriesIndex: 0 }, pointInPixel);
      const xIndex = pointInGrid[0];
      const op = chartInstance.value.getOption();
      const xAxis = op.xAxis[0].data[xIndex];
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

    const handleMouseInChange = (v: boolean) => {
      mouseIn.value = v;
    };

    watch(
      () => duration.value,
      val => {
        emit('durationChange', val);
      }
    );

    /**
     * loading=true 会卸载 echart-container，mouseout 可能丢失导致 mouseIn 残留。
     * 在卸载前主动清零，避免 connect 把错误时间广播出去。
     */
    watch(loading, val => {
      if (val) {
        mouseIn.value = false;
      }
    });

    /** 同步是否有可渲染 options，供标题复位 / 联动门禁使用 */
    watch(
      [loading, options],
      () => {
        if (!chartHasDataRef || loading.value) return;
        chartHasDataRef.value = !!options.value;
      },
      { immediate: true }
    );

    watch(
      [loading, options, () => props.showRestore],
      async () => {
        if (!loading.value && options.value) {
          await nextTick();
          syncDataZoomBrush(canBrushZoom());
          setTimeout(() => {
            syncDataZoomBrush(canBrushZoom());
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
      handleAlarmClick,
      handleCustomMenuClick,
      handleMetricClick,
      handleSelectLegend,
      handleDataZoom,
      handleClick,
      handleZrClick,
      handleMouseInChange,
      handleMouseover,
      handleMouseout,
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
            <div
              ref='echartContainer'
              class='echart-container'
              onMouseout={() => this.handleMouseInChange(false)}
              onMouseover={() => this.handleMouseInChange(true)}
            >
              <VueEcharts
                ref='echart'
                group={this.panel?.dashboardId}
                option={this.options}
                autoresize
                onClick={this.handleClick}
                onDatazoom={this.handleDataZoom}
                onMouseout={this.handleMouseout}
                onMouseover={this.handleMouseover}
                onZr:click={this.handleZrClick}
              />
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
