/* eslint-disable vue/one-component-per-file */
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

import { useI18n } from 'vue-i18n';

import './trace-explore-skeleton.scss';

const widths = [72, 48, 86, 60, 78, 54, 90, 66];

// 与 trace_charts 的请求数、错误数、耗时顺序保持一致。
export const TRACE_CHART_SKELETON_TYPES = ['bar', 'bar', 'line'] as const;

export const TraceCellSkeleton = defineComponent({
  name: 'TraceCellSkeleton',
  props: {
    field: { type: String, default: '' },
    index: { type: Number, default: 0 },
  },
  render() {
    const width = `${widths[this.index % widths.length]}%`;
    const isTag = /service|kind|status|collection/.test(this.field);
    return (
      <div
        class={['trace-cell-skeleton', { 'is-tag': isTag }]}
        aria-hidden='true'
      >
        {/id$|status/.test(this.field) && <i class='trace-skeleton-block cell-icon' />}
        <span
          style={{ width }}
          class='trace-skeleton-block cell-text'
        />
        {isTag && <span class='trace-skeleton-block cell-tag' />}
      </div>
    );
  },
});

export default defineComponent({
  name: 'TraceExploreSkeleton',
  props: {
    type: {
      type: String as PropType<'application' | 'chart' | 'fields' | 'filter' | 'resident' | 'results' | 'table'>,
      default: 'results',
    },
    showResident: { type: Boolean, default: true },
    chartType: { type: String as PropType<'bar' | 'line'>, default: 'line' },
    mode: { type: String as PropType<'span' | 'trace'>, default: 'span' },
  },
  setup() {
    const { t } = useI18n();
    const chart = (type: 'bar' | 'line') => (
      <div class='trace-skeleton-chart'>
        <div class='chart-axis'>
          {type === 'line' ? (
            <svg
              class='chart-line'
              preserveAspectRatio='none'
              viewBox='0 0 300 80'
            >
              <path d='M0 60 L20 54 L40 58 L60 40 L80 46 L100 30 L120 38 L140 20 L160 32 L180 24 L200 42 L220 30 L240 38 L260 18 L280 26 L300 14' />
              <path
                class='secondary-line'
                d='M0 68 L20 64 L40 66 L60 56 L80 60 L100 46 L120 54 L140 42 L160 52 L180 48 L200 60 L220 50 L240 54 L260 44 L280 50 L300 38'
              />
            </svg>
          ) : (
            [28, 40, 34, 56, 72, 64, 46, 58, 82, 68, 50, 60, 42, 30, 46, 36].map((height, index) => (
              <span
                key={index}
                style={{ height: `${height}%` }}
                class='trace-skeleton-block chart-bar'
              />
            ))
          )}
        </div>
        <div class='chart-ticks'>
          {[0, 1, 2, 3].map(i => (
            <i
              key={i}
              class='trace-skeleton-block'
            />
          ))}
        </div>
        <div class='chart-legend'>
          <i class='trace-skeleton-block' />
          <i class='trace-skeleton-block' />
        </div>
      </div>
    );
    const resident = () => (
      <div class='trace-resident-skeleton'>
        <div class='left-btn'>
          <i class='trace-skeleton-block setting-icon' />
          <span class='trace-skeleton-block setting-label' />
        </div>
        <div class='right-content'>
          {[0, 1, 2, 3].map(index => (
            <div
              key={index}
              class='resident-control'
            >
              <span
                style={{ width: `${[48, 36, 60, 48][index % 4]}px` }}
                class='trace-skeleton-block resident-key'
              />
              <span class='resident-divider' />
              <span class='trace-skeleton-block resident-value' />
              <i class='resident-arrow' />
            </div>
          ))}
        </div>
      </div>
    );
    return { t, chart, resident };
  },
  render() {
    return (
      <div
        class={['trace-explore-skeleton', `is-${this.type}`]}
        aria-label={this.t('加载中...')}
        role='status'
      >
        <div
          class='skeleton-content'
          aria-hidden='true'
        >
          {this.type === 'application' && (
            <div class='application-placeholder'>
              <span class='trace-skeleton-block application-label' />
              <i class='trace-skeleton-block application-shortcut' />
            </div>
          )}
          {this.type === 'filter' && (
            <>
              <div class='filter-query'>
                <i class='trace-skeleton-block query-mode' />
                <i class='trace-skeleton-block query-text' />
                <i class='trace-skeleton-block query-action' />
              </div>
              {this.showResident && this.resident()}
            </>
          )}
          {this.type === 'resident' && this.resident()}
          {this.type === 'fields' && (
            <>
              <div class='field-title'>
                <i class='trace-skeleton-block' />
              </div>
              <div class='trace-skeleton-block field-search' />
              {widths.map((width, index) => (
                <div
                  key={index}
                  class='field-row'
                >
                  <i class='trace-skeleton-block field-icon' />
                  <span
                    style={{ width: `${width}%` }}
                    class='trace-skeleton-block'
                  />
                </div>
              ))}
            </>
          )}
          {this.type === 'chart' && this.chart(this.chartType)}
          {(this.type === 'results' || this.type === 'table') && (
            <>
              {this.type === 'results' && (
                <>
                  <div class='result-charts'>
                    {TRACE_CHART_SKELETON_TYPES.map((type, i) => (
                      <div
                        key={i}
                        class='result-chart'
                      >
                        <i class='trace-skeleton-block chart-title' />
                        {this.chart(type)}
                      </div>
                    ))}
                  </div>
                  <div class='result-tools'>
                    {[0, 1, 2].map(i => (
                      <span
                        key={i}
                        class='trace-skeleton-block'
                      />
                    ))}
                  </div>
                </>
              )}
              <div class='result-table'>
                <div class='result-table-header'>
                  {[0, 1, 2, 3, 4, 5].map(i => (
                    <i
                      key={i}
                      class='trace-skeleton-block'
                    />
                  ))}
                </div>
                {widths.map((_, index) => (
                  <div
                    key={index}
                    class='result-table-row'
                  >
                    {(this.mode === 'span'
                      ? ['span_id', 'span_name', 'service', 'start_time', 'elapsed_time', 'kind']
                      : [
                          'trace_id',
                          'root_span_name',
                          'root_service',
                          'min_start_time',
                          'trace_duration',
                          'collections',
                        ]
                    ).map(field => (
                      <TraceCellSkeleton
                        key={field}
                        field={field}
                        index={index}
                      />
                    ))}
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    );
  },
});
