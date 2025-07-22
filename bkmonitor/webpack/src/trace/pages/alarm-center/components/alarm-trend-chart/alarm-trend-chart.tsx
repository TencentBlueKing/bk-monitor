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

import { defineComponent, provide, shallowRef } from 'vue';
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';

import { PanelModel } from 'monitor-ui/chart-plugins/typings';

import IntervalSelect from '../../../../components/interval-select/interval-select';
import ChartCollapse from '../../../../pages/trace-explore/components/explore-chart/chart-collapse';
import ExploreChart from '../../../../pages/trace-explore/components/explore-chart/explore-chart';
import { useAlarmCenterStore } from '../../../../store/modules/alarm-center';
import { AlarmStatusIconMap, AlarmType } from '../../typings';

import './alarm-trend-chart.scss';

export default defineComponent({
  name: 'AlarmTrendChart',
  setup() {
    const { t } = useI18n();
    const store = useAlarmCenterStore();

    const apiMap = {
      [AlarmType.ALERT]: 'alert.alertDateHistogram',
      [AlarmType.ACTION]: 'alert.actionDateHistogram',
      [AlarmType.INCIDENT]: '',
    };

    /** 汇聚周期 */
    const interval = shallowRef('auto');
    const handleIntervalChange = (value: string) => {
      interval.value = value;
    };

    const seriesColorMap = {
      ...AlarmStatusIconMap,
      success: '#6FC5BF',
      failure: '#F59789',
    };

    const panel = computed(() => {
      return new PanelModel({
        title: '',
        gridPos: {
          x: 16,
          y: 16,
          w: 8,
          h: 4,
        },
        id: 'alarm-trend-chart',
        type: 'graph',
        options: {
          time_series: {
            type: 'bar',
            echart_option: {
              grid: {
                bottom: 6,
              },
              yAxis: {
                splitLine: {
                  lineStyle: {
                    type: 'solid',
                  },
                },
              },
            },
          },
        },
        targets: [
          {
            datasource: 'time_series',
            dataType: 'time_series',
            api: apiMap[store.alarmType],
            data: {
              interval: 'auto',
              stack: true,
            },
          },
        ],
      });
    });

    const timeRange = computed(() => store.timeRange);
    const refreshImmediate = computed(() => store.refreshImmediate);
    provide('timeRange', timeRange);
    provide('refreshImmediate', refreshImmediate);

    const params = computed(() => {
      const { start_time, end_time, ...otherParmas } = store.commonFilterParams;
      return {
        ...otherParmas,
        interval: interval.value,
      };
    });

    /** 格式化图表数据 */
    const formatterData = (data: any) => {
      return {
        series: data.series.map(item => {
          return {
            datapoints: item.data.map(([timestamp, value]) => [value, timestamp]),
            alias: item.display_name,
            type: 'bar',
            itemStyle: {
              color: seriesColorMap[item.name].iconColor,
            },
            color: seriesColorMap[item.name].iconColor,
            unit: data.unit,
          };
        }),
        query_config: {},
        metrics: [],
      };
    };

    /** 图表框选 */
    const handleDataZoomChange = dataZoom => {
      store.timeRange = dataZoom;
    };

    return {
      t,
      panel,
      params,
      interval,
      formatterData,
      handleDataZoomChange,
      handleIntervalChange,
    };
  },
  render() {
    return (
      <div class='alarm-trend-chart-comp'>
        <ChartCollapse
          class='alarm-trend-chart-wrapper-collapse'
          defaultHeight={166}
          hasResize={true}
          title={this.t('总趋势')}
        >
          {{
            default: () => (
              <div class='alarm-trend-chart-container'>
                <ExploreChart
                  formatterData={this.formatterData}
                  panel={this.panel}
                  params={this.params}
                  showTitle={false}
                  onDataZoomChange={this.handleDataZoomChange}
                />
              </div>
            ),
            headerCustom: () => (
              <div class='header-custom'>
                <IntervalSelect
                  interval={this.interval}
                  label={this.t('汇聚周期')}
                  onChange={this.handleIntervalChange}
                />
              </div>
            ),
          }}
        </ChartCollapse>
      </div>
    );
  },
});
