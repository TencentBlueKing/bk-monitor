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
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
 * rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so, subject to the following conditions:
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

import { useI18n } from 'vue-i18n';

import type { TimeRangeType } from '../../../../components/time-range/utils';
import DimensionEcharts from '../dimension-echarts';
import { EMPTY_STATISTICS_INFO, MODE_CHART_CONFIG, type StatisticsMode } from './utils';

import type { IStatisticsGraph, IStatisticsInfo } from '../../typing';

import './statistics-info.scss';

/**
 * 统计弹层的信息区：
 * text 模式展示总行数等行级统计；integer/duration 模式展示最大/最小/平均等数值统计（duration 无中位数）；
 * 底部统一拼接图表，图表标题与类型由 mode 决定。
 */
export default defineComponent({
  name: 'StatisticsInfo',
  props: {
    loading: {
      type: Boolean,
      default: false,
    },
    mode: {
      type: String as PropType<StatisticsMode>,
      default: 'text',
    },
    statisticsInfo: {
      type: Object as PropType<IStatisticsInfo>,
      default: () => ({ ...EMPTY_STATISTICS_INFO }),
    },
    chartData: {
      type: Array as PropType<IStatisticsGraph[]>,
      default: () => [],
    },
    rangeText: {
      type: Array as PropType<TimeRangeType>,
      default: () => [],
    },
  },
  setup() {
    const { t } = useI18n();
    return { t };
  },
  render() {
    const { seriesType, titleKey } = MODE_CHART_CONFIG[this.mode];
    if (this.loading) {
      return (
        <div class='info-skeleton'>
          <div class='total-skeleton'>
            <div class='skeleton-element' />
            <div class='skeleton-element' />
            <div class='skeleton-element' />
          </div>
          {this.mode !== 'text' && (
            <div class='info-skeleton'>
              <div class='skeleton-element' />
              <div class='skeleton-element' />
              <div class='skeleton-element' />
              <div class='skeleton-element' />
            </div>
          )}
          <div class='skeleton-element chart' />
        </div>
      );
    }
    return (
      <div class='statistics-info'>
        {this.mode !== 'duration' && (
          <div class='top-k-info-header'>
            <div class='label-item'>
              <span class='label'>{this.t('总行数')}:</span>
              <span class='value'> {this.statisticsInfo.total_count}</span>
            </div>
            <div class='label-item'>
              <span class='label'>{this.t('非空数据')}:</span>
              <span class='value'> {this.statisticsInfo.field_count}</span>
            </div>
            <div class='label-item'>
              <span class='label'>{this.t('非空数据占比')}:</span>
              <span class='value'> {this.statisticsInfo.field_percent}%</span>
            </div>
          </div>
        )}
        {this.mode !== 'text' && (
          <div class='integer-statics-info'>
            <div class='integer-item'>
              <span class='label'>{this.t('最大值')}</span>
              <span class='value'>{this.statisticsInfo.value_analysis?.max || 0}</span>
            </div>
            <div class='integer-item'>
              <span class='label'>{this.t('最小值')}</span>
              <span class='value'>{this.statisticsInfo.value_analysis?.min || 0}</span>
            </div>
            <div class='integer-item'>
              <span class='label'>{this.t('平均值')}</span>
              <span class='value'>{this.statisticsInfo.value_analysis?.avg || 0}</span>
            </div>
            {this.mode === 'integer' && (
              <div class='integer-item'>
                <span class='label'>{this.t('中位数')}</span>
                <span class='value'>{this.statisticsInfo.value_analysis?.median || 0}</span>
              </div>
            )}
          </div>
        )}
        <div class='top-k-chart-title'>
          <span class='title'>{this.t(titleKey)}</span>
          {this.mode !== 'text' && (
            <span
              class='time-range'
              v-overflow-tips
            >
              {this.rangeText[0]} ～ {this.rangeText[1]}
            </span>
          )}
        </div>
        <DimensionEcharts
          data={this.chartData}
          isDuration={this.mode === 'duration'}
          seriesType={seriesType}
        />
      </div>
    );
  },
});
