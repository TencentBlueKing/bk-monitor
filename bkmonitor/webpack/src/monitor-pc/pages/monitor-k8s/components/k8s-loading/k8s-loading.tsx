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
import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './k8s-loading.scss';

@Component
export default class K8sLoading extends tsc<{ type?: 'chart' | 'charts' | 'sidebar' | 'table' }> {
  @Prop({ default: 'table' }) type: 'chart' | 'charts' | 'sidebar' | 'table';

  renderChartPlaceholder() {
    const trendPoints =
      '0,64 35,62 70,48 105,51 140,43 175,50 210,47 245,27 280,32 315,37 350,25 385,36 420,39 455,52 490,47 525,60 560,52 600,55';
    return (
      <div
        class='loading-chart-placeholder'
        aria-hidden='true'
      >
        <div class='loading-chart-axis'>
          {[0, 1, 2, 3].map(item => (
            <i
              key={item}
              class='skeleton-element'
            />
          ))}
        </div>
        <div class='loading-chart-plot'>
          <div class='loading-chart-line'>
            <svg
              focusable='false'
              preserveAspectRatio='none'
              viewBox='0 0 600 100'
            >
              <polygon points={`0,100 ${trendPoints} 600,100`} />
              <polyline
                points={trendPoints}
                vector-effect='non-scaling-stroke'
              />
            </svg>
          </div>
          <div class='loading-chart-ticks'>
            {[0, 1, 2, 3, 4].map(item => (
              <i
                key={item}
                class='skeleton-element'
              />
            ))}
          </div>
        </div>
      </div>
    );
  }
  render() {
    return (
      <div
        class={['k8s-loading', `is-${this.type}`]}
        aria-busy='true'
        aria-label={this.$t('加载中')}
      >
        {this.type === 'chart'
          ? this.renderChartPlaceholder()
          : this.type === 'charts'
            ? [0, 1].map(group => (
                <div
                  key={group}
                  class='loading-chart-group'
                  aria-hidden='true'
                >
                  <div class='loading-group-title'>
                    <i class='skeleton-element' />
                  </div>
                  <div class='loading-chart-card'>
                    <div class='loading-chart-title'>
                      <i class='skeleton-element' />
                    </div>
                    <div class='loading-chart-content'>{this.renderChartPlaceholder()}</div>
                  </div>
                </div>
              ))
            : this.type === 'sidebar'
              ? [0, 1, 2].map(group => (
                  <div
                    key={group}
                    class='loading-sidebar-group'
                    aria-hidden='true'
                  >
                    <div class='loading-sidebar-heading'>
                      <i class='skeleton-element' />
                      <span class='skeleton-element' />
                      <b class='skeleton-element' />
                    </div>
                    {[0, 1, 2].map(row => (
                      <div
                        key={row}
                        class='loading-sidebar-row'
                      >
                        <i class='skeleton-element' />
                        <span
                          style={{ width: `${[64, 82, 52][row]}%` }}
                          class='skeleton-element'
                        />
                      </div>
                    ))}
                  </div>
                ))
              : Array.from({ length: 7 }, (_, row) => (
                  <div
                    key={row}
                    class={['loading-table-row', { 'is-header': row === 0 }]}
                    aria-hidden='true'
                  >
                    {[0, 1, 2, 3, 4].map(column => (
                      <div
                        key={column}
                        class='loading-table-cell'
                      >
                        <i
                          style={{ width: `${[68, 44, 56][(row + column) % 3]}%` }}
                          class='skeleton-element'
                        />
                      </div>
                    ))}
                  </div>
                ))}
      </div>
    );
  }
}
