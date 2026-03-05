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

import { type PropType, computed, defineComponent, onMounted, provide, shallowRef } from 'vue';

import { handleThreshold } from 'monitor-ui/chart-plugins/utils';

import { createAutoTimeRange } from './aiops-charts';
import MonitorCharts from './monitor-charts';
import { PanelModel } from '@/plugins/typings';

import type { AlarmDetail } from '@/pages/alarm-center/typings';
import type { IDetectionConfig } from 'monitor-pc/pages/strategy-config/strategy-config-set-new/typings';

import './time-series-forecasting-chart.scss';

export default defineComponent({
  name: 'TimeSeriesForecastingChart',
  props: {
    detail: {
      type: Object as PropType<AlarmDetail>,
      default: () => ({}),
    },
    detectionConfig: {
      type: Object as PropType<IDetectionConfig>,
      default: () => ({}),
    },
  },
  setup(props) {
    const panel = shallowRef(null);

    const timeRange = shallowRef([]);
    provide('timeRange', timeRange);
    const showRestore = shallowRef(false);
    const cacheTimeRange = shallowRef([]);
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

    /** 时序预测的预测时长 单位：秒 */
    const duration = computed(() => {
      return (
        props.detectionConfig?.data?.find(item => item.type === 'TimeSeriesForecasting')?.config?.duration ||
        24 * 60 * 60
      );
    });

    onMounted(() => {
      initPanel();
    });

    const initPanel = async () => {
      const thresholdOptions = await handleThreshold(props.detectionConfig);

      const { startTime, endTime } = createAutoTimeRange(
        props.detail.begin_time,
        props.detail.end_time,
        props.detail.extra_info?.strategy?.items?.[0]?.query_configs?.[0]?.agg_interval
      );

      const forecastTimeRange: [number, number] = [
        props.detail.latest_time,
        props.detail.latest_time + props.detail.extra_info?.strategy?.items?.[0]?.query_configs?.[0]?.agg_interval,
      ];
      timeRange.value = [startTime, endTime];
      const panelSrcData = props.detail.graph_panel;
      const { id, title, subTitle, targets } = panelSrcData;
      const panelData = {
        id,
        title,
        subTitle,
        type: 'time-series-forecast',
        options: {
          time_series_forecast: {
            need_hover_style: false,
            duration: duration.value,
            ...thresholdOptions,
          },
        },
        targets: targets.map((item, index) => ({
          ...item,
          alias: '',
          options: {
            time_series_forecast: {
              forecast_time_range: index ? forecastTimeRange : undefined,
              no_result: !!index,
            },
          },
          data: {
            ...item.data,
            id: props.detail.id,
            function: undefined,
          },
          api: 'alert_v2.alertGraphQuery',
        })),
      };
      panel.value = new PanelModel(panelData);
    };

    return {
      panel,
      showRestore,
      handleDataZoomChange,
      handleRestore,
    };
  },
  render() {
    return (
      <div class='time-series-forecasting-chart'>
        <MonitorCharts
          panel={this.panel}
          showRestore={this.showRestore}
          onDataZoomChange={this.handleDataZoomChange}
          onRestore={this.handleRestore}
        />
      </div>
    );
  },
});
