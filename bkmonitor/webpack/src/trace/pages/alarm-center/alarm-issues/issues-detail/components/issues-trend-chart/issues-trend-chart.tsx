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

import { type PropType, defineComponent, provide, toRef } from 'vue';
import { computed } from 'vue';

import { PanelModel } from 'monitor-ui/chart-plugins/typings';

import { TrendStatusEnum } from '../../../constant';
import BasicCard from '../basic-card/basic-card';
import { type TimeRangeType, DEFAULT_TIME_RANGE } from '@/components/time-range/utils';
import ExploreChart from '@/pages/trace-explore/components/explore-chart/explore-chart';

import './issues-trend-chart.scss';

export default defineComponent({
  name: 'IssuesTrendChart',
  props: {
    alertCount: {
      type: Number,
      default: 0,
    },
    timeRange: {
      type: Array as PropType<TimeRangeType>,
      default: () => DEFAULT_TIME_RANGE,
    },
    commonParams: {
      type: Object,
      default: () => ({}),
    },
  },
  setup(props) {
    provide('timeRange', toRef(props, 'timeRange'));

    const colorMap = {
      [TrendStatusEnum.ABNORMAL]: '#FF7763',
      [TrendStatusEnum.RECOVERED]: '#56CCBC',
      [TrendStatusEnum.CLOSED]: '#FAC20A',
    };

    const params = computed(() => {
      return {
        ...props.commonParams,
        interval: 'auto',
      };
    });

    const panel = new PanelModel({
      title: '',
      gridPos: {
        x: 16,
        y: 16,
        w: 8,
        h: 4,
      },
      id: 'issues-trend-chart',
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
          api: 'alert_v2.alertDateHistogram',
          data: {
            stack: true,
          },
        },
      ],
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
              color: colorMap[item.name],
            },
            color: colorMap[item.name],
            unit: data.unit,
          };
        }),
        query_config: {},
        metrics: [],
      };
    };

    return {
      panel,
      params,
      formatterData,
    };
  },
  render() {
    return (
      <BasicCard
        width='560px'
        class='issues-trend-chart'
        v-slots={{
          header: () => (
            <div class='chart-header'>
              <span class='chart-title'>{this.$t('趋势')}</span>
              <span class='chart-subtitle'>
                <i class='icon-monitor icon-gaojing1' />
                <span>{this.$t('告警事件')}：</span>
                <span class='count'>{this.alertCount}</span>
              </span>
            </div>
          ),
        }}
      >
        <div class='chart-body'>
          <ExploreChart
            customOptions={{ formatterData: this.formatterData }}
            panel={this.panel}
            params={this.params}
            showTitle={false}
          />
        </div>
      </BasicCard>
    );
  },
});
