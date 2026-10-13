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

import './detail-skeleton.scss';

type Section =
  | 'alert'
  | 'chart'
  | 'configuration'
  | 'fields'
  | 'log'
  | 'sample'
  | 'status'
  | 'status-table'
  | 'storage'
  | 'targets';

@Component
export default class DetailSkeleton extends tsc<{ chartType?: 'bar' | 'line'; section: Section }> {
  @Prop({ type: String, required: true }) section: Section;
  @Prop({ type: String, default: 'line' }) chartType: 'bar' | 'line';

  bar(width: string, height = 12) {
    return (
      <span
        style={{ width, height: `${height}px` }}
        class='skeleton-element'
      />
    );
  }

  form(rows: number) {
    return (
      <div class='detail-skeleton-form'>
        {Array.from({ length: rows }, (_, i) => (
          <div
            key={i}
            class='detail-skeleton-field'
          >
            <span class='detail-skeleton-label'>{this.bar(`${[56, 70, 42][i % 3]}px`)}</span>
            {this.bar(`${[180, 64, 120, 220][i % 4]}px`)}
          </div>
        ))}
      </div>
    );
  }

  table(widths: string[], rows = 5) {
    const status = this.section === 'status' || this.section === 'status-table';
    return (
      <div class='detail-skeleton-table'>
        {Array.from({ length: rows + 1 }, (_, row) => (
          <div
            key={row}
            style={{ gridTemplateColumns: widths.join(' ') }}
            class={['detail-skeleton-row', { 'is-header': row === 0 }]}
          >
            {widths.map((_, col) => (
              <div
                key={col}
                class='detail-skeleton-cell'
              >
                {row > 0 && status && col === 2 ? (
                  <div class='detail-skeleton-status'>
                    <span class='skeleton-element detail-skeleton-dot' />
                    {this.bar('48px')}
                  </div>
                ) : row > 0 && status && col === 5 ? (
                  <div class='detail-skeleton-actions'>
                    {this.bar('36px')}
                    {this.bar('36px')}
                  </div>
                ) : row > 0 && this.section === 'sample' && col === 0 ? (
                  this.bar('24px')
                ) : (
                  this.bar(`${row === 0 ? 48 : [64, 82, 42][(row + col) % 3]}%`)
                )}
              </div>
            ))}
          </div>
        ))}
      </div>
    );
  }

  render() {
    let content;
    switch (this.section) {
      case 'configuration':
        content = [
          this.bar('72px', 16),
          this.form(9),
          <div class='detail-skeleton-params'>{this.table(['1fr', '1fr'], 3)}</div>,
        ];
        break;
      case 'targets':
        content = this.table(['1fr', '1fr', '1fr']);
        break;
      case 'status-table':
        content = this.table(['278px', '217px', '165px', '228px', 'minmax(150px, 1fr)', '200px'], 13);
        break;
      case 'status':
        content = [
          <div class='detail-skeleton-toolbar'>
            <div class='detail-skeleton-counts'>
              {[0, 1, 2, 3].map(i => (
                <div key={i}>
                  {this.bar('48px')}
                  {this.bar('16px')}
                </div>
              ))}
            </div>
            <div class='detail-skeleton-actions'>
              {this.bar('88px', 32)}
              {this.bar('88px', 32)}
              {this.bar('80px', 32)}
            </div>
          </div>,
          <div class='detail-skeleton-group'>{this.bar('160px', 14)}</div>,
          this.table(['278px', '217px', '165px', '228px', 'minmax(150px, 1fr)', '200px'], 13),
        ];
        break;
      case 'storage':
        content = [
          this.bar('72px', 16),
          this.form(4),
          <div class='detail-skeleton-group'>{this.bar('120px', 14)}</div>,
          this.table(['1fr', '2fr', '1fr']),
        ];
        break;
      case 'fields':
        content = [0, 1].map(i => (
          <div
            key={i}
            class='detail-skeleton-metric'
          >
            <div class='detail-skeleton-group'>{this.bar('180px', 14)}</div>
            {this.table(['150px', 'minmax(150px, 1fr)', 'minmax(150px, 1fr)', '80px', '100px'], 4)}
          </div>
        ));
        break;
      case 'sample':
        content = this.table(['120px', 'minmax(150px, 1fr)', '250px', '175px']);
        break;
      case 'chart': {
        const trendPoints =
          '0,64 35,62 70,48 105,51 140,43 175,50 210,47 245,27 280,32 315,37 350,25 385,36 420,39 455,52 490,47 525,60 560,52 600,55';
        content = (
          <div class='detail-skeleton-plot'>
            <div class='detail-skeleton-axis'>
              {[0, 1, 2, 3].map(i => (
                <span key={i}>{this.bar('24px', 10)}</span>
              ))}
            </div>
            <div class='detail-skeleton-grid'>
              <div class='detail-skeleton-trend'>
                {this.chartType === 'bar' ? (
                  <div class='detail-skeleton-bars'>
                    {[36, 42, 58, 51, 64, 48, 72, 62, 55, 68, 46, 52].map((height, i) => (
                      <span key={i} class='skeleton-element' style={{ height: `${height}%` }} />
                    ))}
                  </div>
                ) : (
                  <svg focusable='false' preserveAspectRatio='none' viewBox='0 0 600 100'>
                    <polygon points={`0,100 ${trendPoints} 600,100`} />
                    <polyline points={trendPoints} vector-effect='non-scaling-stroke' />
                  </svg>
                )}
              </div>
              <div class='detail-skeleton-ticks'>
                {[0, 1, 2, 3].map(i => (
                  <span key={i}>{this.bar('36px', 10)}</span>
                ))}
              </div>
            </div>
          </div>
        );
        break;
      }
      case 'log':
        content = Array.from({ length: 10 }, (_, i) => (
          <div key={i} class='detail-skeleton-log-line'>
            {this.bar(`${[82, 64, 92, 48, 76][i % 5]}%`)}
          </div>
        ));
        break;
      case 'alert':
        content = (
          <div class='detail-skeleton-alert'>
            {this.bar('120px')}
            {this.bar('200px')}
            {this.bar('220px', 24)}
          </div>
        );
    }
    return (
      <div
        class={['collector-detail-skeleton', `is-${this.section}`]}
        aria-hidden='true'
      >
        {content}
      </div>
    );
  }
}
