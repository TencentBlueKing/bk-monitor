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

import './collection-skeleton.scss';

export default defineComponent({
  name: 'CollectionSkeleton',
  props: {
    variant: { type: String as PropType<'page' | 'table' | 'targets'>, default: 'table' },
    columns: { type: Array as PropType<number[]>, default: () => [30, 16, 24, 10, 20] },
  },
  render() {
    return (
      <div
        class={['collection-skeleton', `collection-skeleton-${this.variant}`]}
        aria-hidden='true'
      >
        {this.variant === 'page' && (
          <>
            <div class='collection-skeleton-tabs'>
              {[0, 1, 2].map(item => (
                <i
                  key={item}
                  class='skeleton-element'
                />
              ))}
            </div>
            <div class='collection-skeleton-toolbar'>
              <i class='skeleton-element' />
              <i class='skeleton-element' />
            </div>
          </>
        )}
        {this.variant === 'targets' ? (
          [0, 1, 2].map(item => (
            <div
              key={item}
              class='collection-skeleton-card'
            >
              <i class='skeleton-element' />
              <i class='skeleton-element' />
            </div>
          ))
        ) : (
          <div class='collection-skeleton-surface'>
            <div
              style={{ gridTemplateColumns: this.columns.map(width => `minmax(0, ${width}fr)`).join(' ') }}
              class='collection-skeleton-grid'
            >
              {Array.from({ length: 11 }, (_, row) =>
                this.columns.map((_, col) => (
                  <div
                    key={`${row}:${col}`}
                    class={['collection-skeleton-cell', { heading: row === 0 }]}
                  >
                    <i
                      style={{ width: `${[65, 85, 50, 75][(row + col) % 4]}%` }}
                      class='skeleton-element'
                    />
                  </div>
                ))
              )}
            </div>
            <div class='collection-skeleton-pagination'>
              <i class='skeleton-element' />
              <i class='skeleton-element' />
            </div>
          </div>
        )}
      </div>
    );
  },
});
