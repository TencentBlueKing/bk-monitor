/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
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
import { defineComponent, shallowRef, watch } from 'vue';

import { useTraceExploreStore } from '@/store/modules/explore';
import { traceChats } from 'monitor-api/modules/apm_trace';
import { random } from 'monitor-common/utils';
import { PanelModel } from 'monitor-ui/chart-plugins/typings';
import { echartsConnect } from 'monitor-ui/monitor-echarts/utils';

import ExploreChart from './explore-chart';

import './chart-wrapper.scss';
export default defineComponent({
  name: 'ExploreChart',
  props: {},
  setup() {
    const store = useTraceExploreStore();
    const panelModels = shallowRef<PanelModel[]>([]);
    const dashboardId = random(10);
    const getChartPanels = async () => {
      const list =
        store.appName && store.mode
          ? await traceChats({
              app_name: store.appName,
            }).catch(() => [])
          : [];
      panelModels.value = list.map(
        item =>
          new PanelModel({
            ...item,
            dashboardId,
          })
      );

      echartsConnect(dashboardId);
    };
    watch([() => store.appName, () => store.mode], () => {
      getChartPanels();
    });
    return {
      panelModels,
    };
  },
  render() {
    return (
      <div class='explore-chart-wrapper'>
        {this.panelModels.map(panel => (
          <ExploreChart
            key={panel.id}
            panel={panel}
          />
        ))}
      </div>
    );
  },
});
