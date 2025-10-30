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

import { type PropType, computed, defineComponent, provide, shallowRef, toRef, watch } from 'vue';

import { random } from 'monitor-common/utils';
import { echartsConnect } from 'monitor-ui/monitor-echarts/utils';

import { type TimeRangeType, DEFAULT_TIME_RANGE } from '../../../../../../../components/time-range/utils';
import { createAutoTimeRange } from '../../../../../../../plugins/charts/failure-chart/failure-alarm-chart';
import AlarmMetricsDashboard from '../../../../../components/alarm-metrics-dashboard/alarm-metrics-dashboard';
import { useHostSceneView } from '../../../../../composables/use-host-scene-view';

import './panel-host-dashboard.scss';

export default defineComponent({
  name: 'PanelHostDashboard',
  props: {
    /** 业务ID */
    bizId: {
      type: Number,
    },
    /** 图表需要请求的数据的开始时间 */
    timeRange: {
      type: Array as PropType<TimeRangeType>,
      default: () => DEFAULT_TIME_RANGE,
    },
    /** 图表请求参数变量 */
    viewOptions: {
      type: Object as PropType<Record<string, unknown>>,
      default: () => ({}),
    },
  },
  setup(props) {
    /** 图表联动Id */
    const dashboardId = shallowRef(random(10));
    /** 主机监控 需要渲染的仪表盘面板配置数组 */
    const { hostSceneView, loading } = useHostSceneView(toRef(props, 'bizId'));
    /** 是否立即刷新图表数据 */
    const refreshImmediate = shallowRef('');

    provide('timeRange', toRef(props, 'timeRange'));
    provide('refreshImmediate', refreshImmediate);
    watch(
      () => hostSceneView.value,
      () => {
        dashboardId.value = random(10);
        echartsConnect(dashboardId.value);
      }
    );

    return { dashboardId, hostSceneView, loading };
  },
  render() {
    return (
      <div class='panel-host-dashboard'>
        {this.hostSceneView?.panels?.map?.(dashboard => (
          <AlarmMetricsDashboard
            key={dashboard.id}
            dashboardId={this.dashboardId}
            dashboardTitle={dashboard?.title}
            panelModels={dashboard?.panels}
            viewOptions={this.viewOptions}
          />
        ))}
      </div>
    );
  },
});
