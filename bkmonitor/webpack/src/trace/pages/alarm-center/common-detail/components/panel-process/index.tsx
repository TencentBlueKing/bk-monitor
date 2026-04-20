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
import { computed, defineComponent, provide, shallowRef, watch } from 'vue';

import { get } from '@vueuse/core';
import { random } from 'monitor-common/utils';
import { echartsConnect } from 'monitor-ui/monitor-echarts/utils';
import { storeToRefs } from 'pinia';

import ChartSkeleton from '../../../../../components/skeleton/chart-skeleton';
import { useAlarmCenterDetailStore } from '../../../../../store/modules/alarm-center-detail';
import AlarmMetricsDashboard from '../../../components/alarm-metrics-dashboard/alarm-metrics-dashboard';
import { useSceneView } from '../../../composables/use-scene-view';

import type { IDataQuery } from '../../../../../plugins/typings';
import type { DateValue } from '@blueking/date-picker';
import type { IPanelModel } from 'monitor-ui/chart-plugins/typings';

import './index.scss';

export default defineComponent({
  name: 'PanelProcess',
  setup() {
    const { bizId, interval, timeRange, alarmDetail } = storeToRefs(useAlarmCenterDetailStore());
    const { dashboards: processDashboards, loading: sceneViewLoading } = useSceneView(bizId, 'process');
    /** 图表联动Id */
    const dashboardId = shallowRef(random(10));
    /** 图表执行 dataZoom 框线缩放后的时间范围 */
    const dataZoomTimeRange = shallowRef<DateValue>(null);
    /** 当前图表视图的时间范围 */
    const viewerTimeRange = computed<DateValue>(() => get(dataZoomTimeRange) ?? get(timeRange));
    /** 是否立即刷新图表数据 */
    const refreshImmediate = shallowRef('');

    provide('timeRange', viewerTimeRange);
    provide('refreshImmediate', refreshImmediate);

    /** 图表请求参数变量（扁平结构，与 host tab 保持一致） */
    const viewOptions = computed(() => {
      const detail = get(alarmDetail);
      const variables: Record<string, any> = {
        bk_target_ip: '0.0.0.0',
        bk_target_cloud_id: '0',
        ip: '0.0.0.0',
        bk_cloud_id: '0',
      };
      const currentTarget: Record<string, any> = {
        bk_target_ip: '0.0.0.0',
        bk_target_cloud_id: '0',
      };
      detail?.tags?.forEach(item => {
        variables[item.key] = item.value;
      });
      detail?.dimensions?.forEach(item => {
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
      });
      return {
        method: 'AVG',
        interval: get(interval),
        group_by: [],
        current_target: currentTarget,
        ...variables,
      };
    });

    /**
     * @description 将所有 row 分组展开为扁平面板列表（不需要折叠分组）
     */
    const flatPanels = computed<IPanelModel[]>(() => {
      const dashboards = get(processDashboards);
      if (!dashboards?.length) return [];
      const result: IPanelModel[] = [];
      for (const panel of dashboards) {
        if (panel.type === 'row' && panel.panels?.length) {
          result.push(...panel.panels);
        } else {
          result.push(panel);
        }
      }
      return result;
    });

    /**
     * @description 格式化series别名
     */
    const formatSeriesAlias = (item: any) => {
      const dimensions = item?.dimensions ?? {};
      const keys = Object.keys(dimensions);
      if (!keys.length) return item.target;
      if (keys.length === 1) return dimensions[keys[0]];
      return keys.map(key => `${key}=${dimensions[key]}`).join('|');
    };

    /**
     * @description 格式化图表数据
     */
    const formatterData = (data: any, target: IDataQuery) => {
      return {
        ...data,
        query_config: data?.query_config || target.data,
        series: data.series.map(item => ({
          ...item,
          alias: formatSeriesAlias(item),
        })),
      };
    };

    /**
     * @description 数据时间间隔 值改变后回调
     */
    const handleDataZoomTimeRangeChange = (e?: [number, number]) => {
      if (!e?.[0] || !e?.[1]) {
        dataZoomTimeRange.value = null;
        return;
      }
      dataZoomTimeRange.value = e;
    };

    watch(
      () => get(processDashboards),
      () => {
        dashboardId.value = random(10);
        echartsConnect(dashboardId.value);
      }
    );

    return {
      bizId,
      sceneViewLoading,
      flatPanels,
      dashboardId,
      dataZoomTimeRange,
      viewerTimeRange,
      viewOptions,
      formatterData,
      handleDataZoomTimeRangeChange,
    };
  },
  render() {
    if (this.sceneViewLoading) {
      return (
        <div class='alarm-center-detail-panel-process'>
          <div class='panel-process-chart-wrap'>
            <div class='panel-process-skeleton'>
              {new Array(4).fill(0).map((_, index) => (
                <div
                  key={index}
                  class='panel-process-skeleton-item'
                >
                  <ChartSkeleton />
                </div>
              ))}
            </div>
          </div>
        </div>
      );
    }
    return (
      <div class='alarm-center-detail-panel-process'>
        <div class='panel-process-chart-wrap'>
          <AlarmMetricsDashboard
            customOptions={{
              formatterData: this.formatterData,
            }}
            params={{
              bk_biz_id: this.bizId,
            }}
            dashboardId={this.dashboardId}
            panelModels={this.flatPanels}
            showHeader={false}
            showRestore={!!this.dataZoomTimeRange}
            viewOptions={this.viewOptions}
            onDataZoomChange={this.handleDataZoomTimeRangeChange}
            onRestore={this.handleDataZoomTimeRangeChange}
          />
        </div>
      </div>
    );
  },
});
