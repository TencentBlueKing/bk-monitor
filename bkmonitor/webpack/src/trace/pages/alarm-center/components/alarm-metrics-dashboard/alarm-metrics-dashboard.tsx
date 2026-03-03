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
import { type PropType, computed, defineComponent, inject, useTemplateRef } from 'vue';

import { get } from '@vueuse/core';
import { type IPanelModel, PanelModel } from 'monitor-ui/chart-plugins/typings';
import { convertToSeconds } from 'monitor-ui/chart-plugins/utils';
import { getVariablesService } from 'monitor-ui/chart-plugins/utils/variable';

import { DEFAULT_TIME_RANGE, handleTransformToTimestamp } from '../../../../components/time-range/utils';
import ChartCollapse from '../../../trace-explore/components/explore-chart/chart-collapse';
import AlarmLazyChart from './components/alarm-lazy-chart/alarm-lazy-chart';

import type { LegendCustomOptions } from '../../../trace-explore/components/explore-chart/use-chart-legend';
import type { CustomOptions } from '../../../trace-explore/components/explore-chart/use-echarts';

import './alarm-metrics-dashboard.scss';

/** 仅以下 API 需要携带 down_sample_range */
const DOWN_SAMPLE_RANGE_APIS = new Set(['unifyQuery', 'graphUnifyQuery']);

export default defineComponent({
  name: 'AlarmMetricsDashboard',
  props: {
    /** 图表联动Id */
    dashboardId: {
      type: String,
    },
    /** 仪表板标题 */
    dashboardTitle: {
      type: String,
    },
    /** 仪表板面板内图表配置列表 */
    panelModels: {
      type: Array as PropType<IPanelModel[]>,
      default: () => [],
    },
    /** panelModel 配置 - 图表请求接口配置(targets) - 传参配置(data)中的占位变量($xxx)的数据 */
    viewOptions: {
      type: Object as PropType<Record<string, unknown>>,
      default: () => ({}),
    },
    /** 请求图表数据时所需要额外携带的参数 */
    params: {
      type: Object as PropType<Record<string, unknown>>,
      default: () => ({}),
    },
    /** 仪表板面板每行显示的图表列数 */
    gridCol: {
      type: Number,
      default: 2,
    },
    /** 初始化时折叠面板默认是否展开状态 */
    defaultIsExpand: {
      type: Boolean,
      default: true,
    },
    /** 折叠收起时需要展示内容的高度 */
    collapseShowHeight: {
      type: Number,
      default: 36,
    },
    /** 图表数据格式化函数 */
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
    /** 是否渲染折叠面板的 header 区域 */
    showHeader: {
      type: Boolean,
      default: true,
    },
  },
  emits: ['dataZoomChange', 'durationChange', 'restore'],
  setup(props) {
    /** 图表实例 */
    const alarmDashboardRef = useTemplateRef<Element>('alarmDashboardRef');
    const timeRange = inject('timeRange', DEFAULT_TIME_RANGE);
    /** css 变量 */
    const cssVars = computed(() => ({
      /** 仪表板面板每行显示的图表列数 */
      '--dashboard-grid-col': props.gridCol,
    }));

    /** 将其中占位变量转换为实际值后的 panel 配置 */
    const panels = computed(() => {
      return props.panelModels.map(e => {
        let transformTargets = e?.targets;
        if (transformTargets?.length) {
          const [startTime, endTime] = handleTransformToTimestamp(get(timeRange));
          const rawInterval = props.viewOptions?.interval;
          const computedDownSampleRange = downSampleRangeComputed([startTime, endTime]);
          // eslint-disable-next-line @typescript-eslint/naming-convention
          let down_sample_range: string;
          let interval: number | string;
          if (rawInterval === 'auto') {
            // interval=auto: interval 与 down_sample_range 都使用按宽度计算的值
            interval = computedDownSampleRange;
            down_sample_range = computedDownSampleRange;
          } else {
            const originInterval = +rawInterval || 60;
            const computedDownSampleRangeSec = convertToSeconds(computedDownSampleRange);
            interval = originInterval;
            // interval=number: 仅当计算值(秒)大于原 interval 时，down_sample_range 才用计算值
            down_sample_range =
              computedDownSampleRangeSec > originInterval ? computedDownSampleRange : `${originInterval}s`;
          }
          const intervalSecond = typeof interval === 'number' ? interval : convertToSeconds(interval);
          const variableService = getVariablesService();
          transformTargets = transformTargets.map(item => {
            const api = item.api?.split('.').pop();
            // 兼容 grafana.graphUnifyQuery 形式，只取最后一段 API 名称判断
            const shouldPassDownSampleRange = DOWN_SAMPLE_RANGE_APIS.has(api || '');
            return {
              ...item,
              data: {
                ...variableService.transformVariables(item.data, {
                  ...(props.viewOptions ?? {}),
                  interval,
                  interval_second: intervalSecond,
                }),
                ...(shouldPassDownSampleRange ? { down_sample_range } : {}),
              },
            };
          });
        }
        return new PanelModel({
          ...e,
          dashboardId: props.dashboardId,
          targets: transformTargets,
        });
      });
    });

    /**
     * @description 下采样粒度计算：ceil((结束时间 - 开始时间) / 图表宽度)，单位秒
     */
    const downSampleRangeComputed = (timeRange: number[]) => {
      const chartDom = alarmDashboardRef?.value?.querySelector('.alarm-lazy-chart');
      const width = Math.max(chartDom?.clientWidth ?? 1, 1);
      const size = (timeRange[1] - timeRange[0]) / width;
      return `${Math.max(Math.ceil(size), 1)}s`;
    };

    return {
      cssVars,
      panels,
    };
  },
  render() {
    return (
      <div
        ref='alarmDashboardRef'
        style={this.cssVars}
        class='alarm-metrics-dashboard'
      >
        <ChartCollapse
          class='alarm-metrics-dashboard-collapse'
          collapseShowHeight={24}
          defaultHeight={0}
          description={`(${this.panelModels?.length})`}
          hasResize={false}
          showHeader={this.showHeader}
          title={this.dashboardTitle}
        >
          <div class='alarm-metrics-chart-container'>
            {this.panels.map(panel => (
              <AlarmLazyChart
                key={panel.id}
                class='alarm-metrics-dashboard-chart'
                customLegendOptions={this.customLegendOptions}
                customOptions={this.customOptions}
                panel={panel}
                params={this.params}
                showRestore={this.showRestore}
                onDataZoomChange={(timeRange: [number, number]) => this.$emit('dataZoomChange', timeRange)}
                onDurationChange={(duration: number) => this.$emit('durationChange', duration)}
                onRestore={() => this.$emit('restore')}
              >
                {{
                  customBaseChart: this.$slots?.customBaseChart
                    ? renderContext => this.$slots?.customBaseChart?.(renderContext)
                    : null,
                }}
              </AlarmLazyChart>
            ))}
          </div>
        </ChartCollapse>
      </div>
    );
  },
});
