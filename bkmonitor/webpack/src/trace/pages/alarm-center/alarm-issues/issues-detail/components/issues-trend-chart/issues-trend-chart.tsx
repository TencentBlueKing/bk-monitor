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

import { type PropType, defineComponent } from 'vue';
import { computed } from 'vue';

import { TrendStatusEnum } from '../../../constant';
import BasicCard from '../basic-card/basic-card';
import MonitorOptionsCharts from '@/plugins/components/monitor-options-charts';

import type { IssueTrendItem } from '../../../typing';
import type { SeriesItem } from '@/pages/trace-explore/components/explore-chart/types';

import './issues-trend-chart.scss';

export default defineComponent({
  name: 'IssuesTrendChart',
  props: {
    alertCount: {
      type: Number,
      default: 0,
    },
    data: {
      type: Array as PropType<IssueTrendItem[]>,
      default: () => [],
    },
  },
  setup(props) {
    const colorMap = {
      [TrendStatusEnum.ABNORMAL]: '#FF7763',
      [TrendStatusEnum.RECOVERED]: '#56CCBC',
      [TrendStatusEnum.CLOSED]: '#FAC20A',
    };
    const seriesList = computed<SeriesItem[]>(() => {
      return props.data.map(series => {
        return {
          datapoints: series.data.map(([time, value]) => [value, time]),
          name: series.display_name,
          stack: true,
          type: 'bar',
          color: colorMap[series.name],
        };
      });
    });

    return {
      seriesList,
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
          <MonitorOptionsCharts seriesList={this.seriesList} />
        </div>
      </BasicCard>
    );
  },
});
