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

import { computed, defineComponent } from 'vue';

import { PanelModel } from 'monitor-ui/chart-plugins/typings';
import { useI18n } from 'vue-i18n';

import BasicCard from '../basic-card/basic-card';
import MonitorCharts from '@/pages/alarm-center/common-detail/components/alarm-view/echarts/monitor-charts';
import { AlarmStatusEnum } from '@/pages/alarm-center/typings';

import './issues-trend-chart.scss';

export interface TrendChartData {
  /** 日期 */
  date: string;
  /** 已失效数量 */
  expired: number;
  /** 已恢复数量 */
  resolved: number;
  /** 未恢复数量 */
  unresolved: number;
}

export default defineComponent({
  name: 'IssuesTrendChart',
  setup() {
    const { t } = useI18n();
    const totalCount = computed(() => {
      return 68;
    });

    // 构造 PanelModel 对象
    const panel = computed<PanelModel>(() => {
      return new PanelModel({
        title: t('趋势'),
        gridPos: { x: 16, y: 16, w: 8, h: 4 },
        id: 'alarm-trend-chart',
        type: 'graph',
        options: {},
        targets: [
          {
            datasource: 'time_series',
            dataType: 'time_series',
            api: 'alert_v2.alertGraphQuery',
            data: {
              stack: true,
            },
          },
        ],
      });
    });

    const customSeries = series => {
      const colorMap = {
        [AlarmStatusEnum.ABNORMAL]: '#FF7763',
        [AlarmStatusEnum.RECOVERED]: '#56CCBC',
        [AlarmStatusEnum.CLOSED]: '#FAC20A',
      };

      return series.map(item => ({
        ...item,
        color: colorMap[item.metric_field],
      }));
    };

    return {
      panel,
      customSeries,
      totalCount,
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
                <span class='count'>{this.totalCount}</span>
              </span>
            </div>
          ),
        }}
      >
        {/* MonitorCharts 组件 */}
        <div class='chart-body'>
          <MonitorCharts
            customOptions={{
              series: this.customSeries,
            }}
            downSampleRange=''
            panel={this.panel}
            showTitle={false}
          />
        </div>
      </BasicCard>
    );
  },
});
