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

import { type PropType, computed, defineComponent } from 'vue';

import { type IBookMark, BookMarkModel } from 'monitor-ui/chart-plugins/typings';

import AlarmMetricsDashboard from '../../../../../components/alarm-metrics-dashboard/alarm-metrics-dashboard';

import './panel-host-dashboard.scss';

export default defineComponent({
  name: 'PanelHostDashboard',
  props: {
    /** 图表联动Id */
    dashboardId: {
      type: String,
    },
    /** host 场景指标视图配置信息 */
    sceneData: {
      type: Object as PropType<IBookMark>,
      default: () => ({ id: '', panels: [], name: '' }),
    },
    /** 图表请求参数变量 */
    viewOptions: {
      type: Object as PropType<Record<string, unknown>>,
      default: () => ({}),
    },
  },
  setup(props) {
    /** 需要渲染的仪表盘面板配置数组 */
    const sceneView = computed(() => {
      const transformData = new BookMarkModel(props.sceneData || { id: '', panels: [], name: '' });
      const unGroupKey = '__UNGROUP__';
      const panels = transformData.panels;
      /** 处理只有一个分组且为未分组时则不显示组名 */
      const rowPanels = panels.filter(item => item.type === 'row');
      let resultPanels = panels;
      if (rowPanels.length === 1 && rowPanels[0]?.id === unGroupKey) {
        resultPanels = panels.reduce((prev, curr) => {
          if (curr.type === 'row') {
            prev.push(...curr.panels);
          } else {
            prev.push(curr);
          }
          return prev;
        }, []);
      } else if (panels.length > 1 && panels.some(item => item.id === unGroupKey)) {
        /* 当有多个分组且未分组为空的情况则不显示未分组 */
        resultPanels = panels.filter(item => (item.id === unGroupKey ? !!item.panels?.length : true));
      }
      transformData.panels = resultPanels;
      return transformData;
    });

    return { sceneView };
  },
  render() {
    return (
      <div class='panel-host-dashboard'>
        {this.sceneView?.panels?.map?.(dashboard => (
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
