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

import { type PropType, computed, defineComponent, onMounted, provide, shallowRef, watch } from 'vue';

import { type IBookMark, BookMarkModel } from 'monitor-ui/chart-plugins/typings';

import { DEFAULT_TIME_RANGE } from '../../../../../../../components/time-range/utils';
import { createAutoTimeRange } from '../../../../../../../plugins/charts/failure-chart/failure-alarm-chart';
import AlarmMetricsDashboard from '../../../../../components/alarm-metrics-dashboard/alarm-metrics-dashboard';

import './panel-host-dashboard.scss';

export default defineComponent({
  name: 'PanelHostDashboard',
  props: {
    /** 图表联动Id */
    dashboardId: {
      type: String,
    },
    sceneData: {
      type: Object as PropType<IBookMark>,
      default: () => ({ id: '', panels: [], name: '' }),
    },
    detail: {
      // TODO 类型需补充完善
      type: Object as PropType<any>,
      default: () => ({}),
    },
  },
  setup(props) {
    /** 数据时间间隔 */
    const timeRange = shallowRef(DEFAULT_TIME_RANGE);
    /** 是否立即刷新图表数据 */
    const refreshImmediate = shallowRef('');
    /** 图表请求参数变量 */
    const viewOptions = shallowRef({});
    /** 需要渲染的仪表盘面板配置数组 */
    const sceneView = computed(() => {
      const transformData = new BookMarkModel(props.sceneData);
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

    provide('timeRange', timeRange);
    provide('refreshImmediate', refreshImmediate);
    watch(
      () => props.detail,
      () => {
        init();
      }
    );
    onMounted(() => {
      init();
    });

    /**
     * @description 初始化 数据时间间隔 & 图表请求参数变量
     */
    function init() {
      const currentTarget: Record<string, any> = {
        bk_target_ip: '0.0.0.0',
        bk_target_cloud_id: '0',
      };
      const variables: Record<string, any> = {
        bk_target_ip: '0.0.0.0',
        bk_target_cloud_id: '0',
        ip: '0.0.0.0',
        bk_cloud_id: '0',
      };

      for (const item of props.detail?.dimensions ?? []) {
        if (item.key === 'bk_host_id') {
          variables.bk_host_id = item.value;
          currentTarget.bk_host_id = item.value;
        }
        if (['bk_target_ip', 'ip', 'bk_host_id'].includes(item.key)) {
          variables.bk_target_ip = item.value;
          variables.ip = item.value;
          currentTarget.bk_target_ip = item.value;
        }
        if (['bk_cloud_id', 'bk_target_cloud_id', 'bk_host_id'].includes(item.key)) {
          variables.bk_target_cloud_id = item.value;
          variables.bk_cloud_id = item.value;
          currentTarget.bk_target_cloud_id = item.value;
        }
      }

      const interval = props.detail.extra_info?.strategy?.items?.[0]?.query_configs?.[0]?.agg_interval || 60;
      const { startTime, endTime } = createAutoTimeRange(props.detail.begin_time, props.detail.end_time, interval);

      timeRange.value = [startTime, endTime];
      timeRange.value = DEFAULT_TIME_RANGE;
      viewOptions.value = {
        method: 'AVG',
        variables,
        interval,
        group_by: [],
        current_target: currentTarget,
      };
    }

    return { sceneView, viewOptions };
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
