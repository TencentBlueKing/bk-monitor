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

import './profiling-skeleton.scss';

const flameBranches = [
  [0, 100, 0, 1],
  [0, 72, 1, 5],
  [72, 28, 1, 3],
  [0, 43, 6, 8],
  [43, 19, 6, 4],
  [62, 10, 6, 13],
  [72, 18, 4, 8],
  [90, 10, 4, 3],
  [0, 27, 14, 3],
  [27, 12, 14, 8],
  [39, 4, 14, 4],
  [43, 11, 10, 7],
  [54, 5, 10, 3],
  [62, 4, 19, 5],
  [72, 8, 12, 5],
  [80, 6, 12, 11],
  [90, 5, 7, 4],
  [0, 12, 17, 5],
  [12, 7, 17, 9],
  [27, 4, 22, 6],
  [34, 3, 22, 3],
];
const trendPoints =
  '0,64 35,62 70,48 105,51 140,43 175,50 210,47 245,27 280,32 315,37 350,25 385,36 420,39 455,52 490,47 525,60 560,52 600,55';

export default defineComponent({
  name: 'ProfilingSkeleton',
  props: {
    variant: { type: String as PropType<'callgraph' | 'filter' | 'flame' | 'table' | 'trend'>, required: true },
    compared: Boolean,
  },
  render() {
    return (
      <div
        class={['profiling-skeleton', `profiling-skeleton-${this.variant}`]}
        aria-hidden='true'
      >
        {this.variant === 'trend' ? (
          <>
            <div class='skeleton-axis'>
              {[0, 1, 2, 3].map(item => (
                <i
                  key={item}
                  class='skeleton-element'
                />
              ))}
            </div>
            <div class='skeleton-plot'>
              <div class='skeleton-line'>
                <svg
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
              <div class='skeleton-ticks'>
                {[0, 1, 2, 3, 4].map(item => (
                  <i
                    key={item}
                    class='skeleton-element'
                  />
                ))}
              </div>
            </div>
          </>
        ) : this.variant === 'table' ? (
          <div
            style={{
              gridTemplateColumns: `minmax(0, 1fr) repeat(${this.compared ? 3 : 2}, ${this.compared ? 94 : 120}px)`,
            }}
            class='skeleton-table'
          >
            {Array.from({ length: 20 }, (_, row) =>
              Array.from({ length: this.compared ? 4 : 3 }, (_, col) => (
                <div
                  key={`${row}-${col}`}
                  class={['skeleton-table-cell', { heading: row === 0 }]}
                >
                  <i
                    style={{ width: `${col ? 58 : [72, 87, 60, 78][row % 4]}%` }}
                    class='skeleton-element'
                  />
                </div>
              ))
            )}
          </div>
        ) : this.variant === 'flame' ? (
          <>
            {this.compared && <div class='skeleton-element skeleton-legend' />}
            <div class='skeleton-flame-rows'>
              {flameBranches.map(([left, width, depth, count], branch) =>
                Array.from({ length: count }, (_, row) => (
                  <i
                    key={`${branch}-${row}`}
                    style={{
                      left: `${left}%`,
                      width: `calc(${width}% - 1px)`,
                      top: `${(depth + row) * 20}px`,
                      opacity: 0.55 + ((branch + row) % 4) * 0.12,
                    }}
                    class='skeleton-element skeleton-flame-frame'
                  >
                    {width >= 8 && <span style={{ width: `${42 + ((branch + row) % 3) * 16}%` }} />}
                  </i>
                ))
              )}
            </div>
          </>
        ) : this.variant === 'filter' ? (
          <>
            <i class='skeleton-element skeleton-filter-mode' />
            <i class='skeleton-element skeleton-filter-value' />
            <i class='skeleton-element skeleton-filter-action' />
          </>
        ) : (
          <div class='skeleton-callgraph'>
            {[1, 3, 5, 3].map((count, row) => (
              <div
                key={row}
                class='skeleton-callgraph-row'
              >
                {Array.from({ length: count }, (_, index) => (
                  <i
                    key={index}
                    class='skeleton-element'
                  />
                ))}
              </div>
            ))}
          </div>
        )}
      </div>
    );
  },
});
