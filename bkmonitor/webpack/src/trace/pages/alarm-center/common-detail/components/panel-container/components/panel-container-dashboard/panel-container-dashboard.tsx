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

import { type PropType, defineComponent, provide, shallowRef, toRef, watch } from 'vue';

import { random } from 'monitor-common/utils';
import { type SceneEnum, K8sTableColumnKeysEnum } from 'monitor-pc/pages/monitor-k8s/typings/k8s-new';
import { echartsConnect } from 'monitor-ui/monitor-echarts/utils';

import { type TimeRangeType, DEFAULT_TIME_RANGE } from '../../../../../../../components/time-range/utils';
import AlarmMetricsDashboard from '../../../../../components/alarm-metrics-dashboard/alarm-metrics-dashboard';
import { useK8sChartPanel } from '../../../../../composables/use-k8s-chart-panel';
import { useK8sSeriesFormatter } from '../../hooks/use-k8s-series-formatter';

import './panel-container-dashboard.scss';

export default defineComponent({
  name: 'PanelContainerDashboard',
  props: {
    scene: {
      type: String as PropType<SceneEnum>,
      required: true,
    },
    /** 图表需要请求的数据的开始时间 */
    timeRange: {
      type: Array as PropType<TimeRangeType>,
      default: () => DEFAULT_TIME_RANGE,
    },
  },
  setup(props) {
    /** 图表联动Id */
    const dashboardId = shallowRef(random(10));
    /** 是否立即刷新图表数据 */
    const refreshImmediate = shallowRef('');

    provide('timeRange', toRef(props, 'timeRange'));
    provide('refreshImmediate', refreshImmediate);
    /** 需要渲染的仪表盘面板配置数组 */
    const { dashboards } = useK8sChartPanel({
      scene: toRef(props, 'scene'),
      groupByField: K8sTableColumnKeysEnum.POD,
      clusterId: 'BCS-K8S-40003',
      filterBy: {
        pod: ['bkbase-queryengine-bkmonitor-8f798bcd6-vqd9f'],
        namespace: ['bkbase'],
        workload: ['Deployment:bkbase-queryengine-bkmonitor'],
      },
      resourceListData: [
        {
          pod: 'bkbase-queryengine-bkmonitor-8f798bcd6-vqd9f',
          namespace: 'bkbase',
          workload: 'Deployment:bkbase-queryengine-bkmonitor',
        },
      ],
    });

    const { formatterSeriesData } = useK8sSeriesFormatter();

    watch(
      () => dashboards.value,
      () => {
        dashboardId.value = random(10);
        echartsConnect(dashboardId.value);
      }
    );

    return { dashboardId, dashboards, formatterSeriesData };
  },
  render() {
    return (
      <div class='panel-container-dashboard'>
        {this.dashboards?.map?.(dashboard => (
          <AlarmMetricsDashboard
            key={dashboard.id}
            viewOptions={{
              interval: 'auto',
              method: 'sum',
              unit: undefined,
              time_shift: ' ',
            }}
            dashboardId={this.dashboardId}
            dashboardTitle={dashboard?.title}
            formatterData={this.formatterSeriesData}
            panelModels={dashboard?.panels}
          />
        ))}
      </div>
    );
  },
});
