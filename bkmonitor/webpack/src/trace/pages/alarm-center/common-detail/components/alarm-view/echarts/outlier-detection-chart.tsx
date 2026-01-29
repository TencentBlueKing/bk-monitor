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

import { type PropType, computed, defineComponent, onMounted, provide } from 'vue';
import { shallowRef } from 'vue';

import { get } from '@vueuse/core';
import dayjs from 'dayjs';
import { COLOR_LIST } from 'monitor-ui/chart-plugins/constants/charts';

import { createAutoTimeRange } from './aiops-charts';
import MonitorCharts from './monitor-charts';
import { DEFAULT_TIME_RANGE } from '@/components/time-range/utils';
import { PanelModel } from '@/plugins/typings';

import type { AlarmDetail } from '@/pages/alarm-center/typings';

import './outlier-detection-chart.scss';

export default defineComponent({
  name: 'OutlierDetectionChart',
  props: {
    detail: {
      type: Object as PropType<AlarmDetail>,
      default: () => ({}),
    },
  },
  setup(props) {
    /** 图表配置对象 */
    const panel = shallowRef(null);
    /** 初始时间范围 */
    const timeRange = shallowRef(DEFAULT_TIME_RANGE);
    /** 图表执行 dataZoom 框线缩放后的时间范围 */
    const dataZoomTimeRange = shallowRef(null);
    /** 当前图表视图的时间范围 */
    const viewerTimeRange = computed(() => get(dataZoomTimeRange) ?? get(timeRange));
    provide('timeRange', viewerTimeRange);

    /**
     * @description 数据时间间隔 值改变后回调
     * @param {[number, number]} e
     */
    const handleDataZoomTimeRangeChange = (e?: [number, number]) => {
      if (!e?.[0] || !e?.[1]) {
        dataZoomTimeRange.value = null;
        return;
      }
      const startTime = dayjs.tz(e?.[0]).format('YYYY-MM-DD HH:mm:ss');
      const endTime = dayjs.tz(e?.[1]).format('YYYY-MM-DD HH:mm:ss');
      dataZoomTimeRange.value = startTime && endTime ? [startTime, endTime] : null;
    };

    /**
     * @description 初始化图表配置对象
     */
    const initPanel = async () => {
      const { startTime, endTime } = createAutoTimeRange(
        props.detail.begin_time,
        props.detail.end_time,
        props.detail.extra_info?.strategy?.items?.[0]?.query_configs?.[0]?.agg_interval
      );
      timeRange.value = [startTime, endTime];
      const panelSrcData = props.detail.graph_panel;
      const { id, title, subTitle, targets } = panelSrcData;
      const panelData = {
        id,
        title,
        subTitle,
        type: 'time-series-outlier',
        options: {},
        targets: targets.map(item => ({
          ...item,
          alias: '',
          options: {},
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

    onMounted(() => {
      initPanel();
    });

    return {
      panel,
      dataZoomTimeRange,
      handleDataZoomTimeRangeChange,
    };
  },
  render() {
    return (
      <div class='outlier-detection-chart'>
        {this.panel && (
          <MonitorCharts
            customOptions={{
              options: options => {
                options.color = COLOR_LIST;
                return options;
              },
            }}
            panel={this.panel}
            showRestore={this.dataZoomTimeRange}
            onDataZoomChange={this.handleDataZoomTimeRangeChange}
            onRestore={this.handleDataZoomTimeRangeChange}
          />
        )}
      </div>
    );
  },
});
