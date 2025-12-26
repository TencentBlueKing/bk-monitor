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

import { type PropType, defineComponent, onMounted, shallowRef } from 'vue';

import { Loading } from 'bkui-vue';
import { multiAnomalyDetectGraph } from 'monitor-api/modules/alert_v2';
import { random } from 'monitor-common/utils';

import { createAutoTimeRange } from './aiops-charts';
import MonitorCharts from './monitor-charts';
import { DEFAULT_TIME_RANGE } from '@/components/time-range/utils';
import { PanelModel } from '@/plugins/typings';

import type { AlarmDetail } from '@/pages/alarm-center/typings';

import './intelligence-scene.scss';

export default defineComponent({
  name: 'IntelligenceScene',
  props: {
    detail: {
      type: Object as PropType<AlarmDetail>,
      default: () => ({}),
    },
  },
  setup(props) {
    const loading = shallowRef(false);
    const dashboardId = random(10);
    const panels = shallowRef<PanelModel[]>([]);
    const viewOptions = shallowRef({});

    const showRestore = shallowRef(false);
    const timeRange = shallowRef(DEFAULT_TIME_RANGE);
    const cacheTimeRange = shallowRef(DEFAULT_TIME_RANGE);
    const handleDataZoomChange = (value: any[]) => {
      if (JSON.stringify(timeRange.value) !== JSON.stringify(value)) {
        cacheTimeRange.value = JSON.parse(JSON.stringify(timeRange.value));
        timeRange.value = value;
        showRestore.value = true;
      }
    };

    const handleRestore = () => {
      const cacheTime = JSON.parse(JSON.stringify(cacheTimeRange.value));
      timeRange.value = cacheTime;
      showRestore.value = false;
    };

    const timeRangeInit = () => {
      const interval = props.detail.extra_info?.strategy?.items?.[0]?.query_configs?.[0]?.agg_interval || 60;
      const { startTime, endTime } = createAutoTimeRange(props.detail.begin_time, props.detail.end_time, interval);
      const currentTarget: Record<string, any> = {
        bk_target_ip: '0.0.0.0',
        bk_target_cloud_id: '0',
      };
      props.detail.dimensions.forEach(item => {
        if (item.key === 'bk_host_id') {
          currentTarget.bk_host_id = item.value;
        }
        if (['bk_target_ip', 'ip', 'bk_host_id'].includes(item.key)) {
          currentTarget.bk_target_ip = item.value;
        }
        if (['bk_cloud_id', 'bk_target_cloud_id', 'bk_host_id'].includes(item.key)) {
          currentTarget.bk_target_cloud_id = item.value;
        }
      });
      viewOptions.value = {
        interval,
        current_target: currentTarget,
        strategy_id: props.detail?.strategy_id,
      };
      timeRange.value = [startTime, endTime];
    };

    onMounted(async () => {
      loading.value = true;
      const data = await multiAnomalyDetectGraph({
        alert_id: props.detail.id,
        bk_biz_id: props.detail.bk_biz_id,
      }).catch(() => []);
      timeRangeInit();
      const result = data.map(item => {
        return {
          ...item,
          type: 'performance-chart',
          dashboardId: dashboardId,
          targets: item.targets.map(target => ({
            ...target,
            data: {
              ...target.data,
              id: props.detail.id,
              bk_biz_id: props.detail.bk_biz_id,
              ...viewOptions.value,
            },
            datasource: 'time_series',
          })),
          options: {
            time_series: {
              custom_timerange: true,
              hoverAllTooltips: true,
              YAxisLabelWidth: 70,
              needAllAlertMarkArea: true,
            },
          },
        };
      });
      panels.value = result.map(item => new PanelModel(item));
      loading.value = false;
    });

    return {
      loading,
      showRestore,
      panels,
      handleDataZoomChange,
      handleRestore,
    };
  },
  render() {
    return (
      <Loading loading={this.loading}>
        <div class='intelligence-scene-view-component'>
          {this.panels.map((panel, index) => (
            <div
              key={index}
              class='intelligenc-scene-item'
            >
              <MonitorCharts
                panel={panel}
                showRestore={this.showRestore}
                onDataZoomChange={this.handleDataZoomChange}
                onRestore={this.handleRestore}
              />
            </div>
          ))}
        </div>
      </Loading>
    );
  },
});
