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

import { type PropType, defineComponent, shallowRef, toRef, unref, watch } from 'vue';

import { random } from 'monitor-common/utils';
import { type SceneEnum } from 'monitor-pc/pages/monitor-k8s/typings/k8s-new';

import AlarmMetricsDashboard from '../../../../../components/alarm-metrics-dashboard/alarm-metrics-dashboard';
import { useK8sChartPanel } from '../../../../../composables/use-k8s-chart-panel';

import './panel-container-dashboard.scss';

export default defineComponent({
  name: 'PanelContainerDashboard',
  props: {
    scene: {
      type: String as PropType<SceneEnum>,
      required: true,
    },
  },
  setup(props) {
    /** 图表联动Id */
    const dashboardId = shallowRef(random(10));
    /** 需要渲染的仪表盘面板配置数组 */
    const { panels } = useK8sChartPanel(toRef(props, 'scene'));

    return { dashboardId, panels };
  },
  render() {
    return (
      <div class='panel-container-dashboard'>
        {this.panels?.map?.(dashboard => (
          <AlarmMetricsDashboard
            key={dashboard.id}
            viewOptions={{
              interval: 60,
              method: 'sum',
              unit: undefined,
            }}
            dashboardId={this.dashboardId}
            dashboardTitle={dashboard?.title}
            gridCol={1}
            panelModels={dashboard?.panels}
          />
        ))}
      </div>
    );
  },
});
