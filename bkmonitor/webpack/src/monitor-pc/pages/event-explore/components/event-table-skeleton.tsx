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

import type { EventExploreTableColumn } from '../typing';

import './event-table-skeleton.scss';

@Component
export default class EventTableSkeleton extends tsc<{ columns: EventExploreTableColumn[] }> {
  @Prop({ type: Array, default: () => [] }) columns: EventExploreTableColumn[];

  render() {
    const widths = [72, 56, 86, 64, 80, 48];
    const gridTemplateColumns = [
      '24px',
      ...this.columns.map(column => (column.width ? `${column.width}px` : `minmax(${column.min_width || 100}px, 1fr)`)),
    ].join(' ');
    return (
      <div
        class='event-table-skeleton'
        aria-hidden='true'
      >
        {Array.from({ length: 12 }, (_, row) => (
          <div
            key={row}
            style={{ gridTemplateColumns }}
            class='event-skeleton-row'
          >
            <span class='event-skeleton-expand'>
              <i class='skeleton-element' />
            </span>
            {this.columns.map((column, index) => (
              <span
                key={column.id}
                class={['event-skeleton-cell', { 'is-target': column.id === 'target' }]}
              >
                <i
                  style={{ width: `${widths[(row + index) % widths.length]}%` }}
                  class='skeleton-element'
                />
              </span>
            ))}
          </div>
        ))}
      </div>
    );
  }
}
