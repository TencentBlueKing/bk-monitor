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

import { type PropType, computed, defineComponent, provide, shallowRef, watch } from 'vue';
import { toRef } from 'vue';

import { random } from 'monitor-common/utils';
import { echartsConnect } from 'monitor-ui/monitor-echarts/utils';

import AlarmMetricsDashboard from '../alarm-metrics-dashboard/alarm-metrics-dashboard';
import ChartSkeleton from '@/components/skeleton/chart-skeleton';

import type { LegendCustomOptions } from '../../../trace-explore/components/explore-chart/use-chart-legend';
import type { CustomOptions } from '../../../trace-explore/components/explore-chart/use-echarts';
import type { DateValue } from '@blueking/date-picker';
import type { IPanelModel } from 'monitor-ui/chart-plugins/typings';

import './alarm-dashboard-group.scss';
export default defineComponent({
  name: 'AlarmDashboardGroup',
  props: {
    /** 需要渲染的仪表盘配置数组 */
    dashboards: {
      type: Array as PropType<IPanelModel[]>,
    },
    /** 图表需要请求的数据的开始时间 */
    timeRange: {
      type: Array as unknown as PropType<DateValue>,
    },
    /** 是否开启图表联动 */
    enabledChartConnect: {
      type: Boolean,
      default: true,
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
    /** 仪表盘配置是否正在请求加载中 */
    loading: {
      type: Boolean,
      default: false,
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
  },
  emits: ['dataZoomChange', 'durationChange', 'restore'],
  setup(props) {
    /** 图表联动Id */
    const dashboardId = shallowRef(random(10));
    /** 是否立即刷新图表数据 */
    const refreshImmediate = shallowRef('');
    /** css 变量 */
    const cssVars = computed(() => ({
      /** 仪表板面板每行显示的图表列数 */
      '--dashboard-grid-col': props.gridCol,
    }));

    provide('timeRange', toRef(props, 'timeRange'));
    provide('refreshImmediate', refreshImmediate);

    /**
     * @method createDashboardGroupSkeleton 创建仪表盘骨架屏
     * @description 仪表盘配置通常需要请求接口数据，当请求数据时，需要显示骨架屏，当请求数据成功后，需要隐藏骨架屏
     */
    const createDashboardGroupSkeleton = () => {
      return (
        <div class='alarm-dashboard-group-skeleton'>
          {new Array(2 * (props?.gridCol || 1)).fill(0).map((_, index) => (
            <div
              key={index}
              class='alarm-dashboard-group-skeleton-item'
            >
              <ChartSkeleton />
            </div>
          ))}
        </div>
      );
    };

    watch(
      () => props.dashboards,
      () => {
        if (!props.enabledChartConnect) return;
        dashboardId.value = random(10);
        echartsConnect(dashboardId.value);
      }
    );

    return { dashboardId, cssVars, createDashboardGroupSkeleton };
  },
  render() {
    return (
      <div
        style={this.cssVars}
        class='alarm-dashboard-group'
      >
        {this.loading ? (
          this.createDashboardGroupSkeleton()
        ) : (
          <div class='alarm-dashboard-group-main'>
            {this.dashboards?.map?.(dashboard => (
              <AlarmMetricsDashboard
                key={dashboard.id}
                customLegendOptions={this.customLegendOptions}
                customOptions={this.customOptions}
                dashboardId={this.dashboardId}
                dashboardTitle={dashboard?.title}
                gridCol={this.gridCol}
                panelModels={dashboard?.panels}
                params={this.params}
                showRestore={this.showRestore}
                viewOptions={this.viewOptions}
                onDataZoomChange={(timeRange: [number, number]) => this.$emit('dataZoomChange', timeRange)}
                onDurationChange={(duration: number) => this.$emit('durationChange', duration)}
                onRestore={() => this.$emit('restore')}
              >
                {{
                  customBaseChart: this.$slots?.customBaseChart
                    ? renderContext => this.$slots?.customBaseChart?.(renderContext)
                    : null,
                }}
              </AlarmMetricsDashboard>
            ))}
          </div>
        )}
      </div>
    );
  },
});
