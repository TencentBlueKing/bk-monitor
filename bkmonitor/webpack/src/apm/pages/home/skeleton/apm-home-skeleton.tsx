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

import './apm-home-skeleton.scss';

interface IProps {
  kind?: SkeletonKind;
}

type SkeletonKind = 'apps' | 'filters' | 'table';

@Component
export default class ApmHomeSkeleton extends tsc<IProps> {
  @Prop({ type: String, default: 'apps' }) kind: SkeletonKind;

  line(width: string, className = '') {
    return (
      <span
        style={{ width }}
        class={['apm-skeleton-block', className]}
      />
    );
  }

  renderTable() {
    return (
      <div class='apm-skeleton-table'>
        {Array.from({ length: 9 }, (_, row) => (
          <div
            key={row}
            class={['apm-skeleton-row', { 'is-header': row === 0 }]}
          >
            {Array.from({ length: 6 }, (_, column) => (
              <div
                key={column}
                class='apm-skeleton-cell'
              >
                {column === 0 && row > 0 && this.line('20px', 'is-icon')}
                {this.line(`${[68, 48, 58, 76][(row + column) % 4]}%`)}
              </div>
            ))}
          </div>
        ))}
        <div class='apm-skeleton-pagination'>
          {this.line('112px')}
          {this.line('180px')}
        </div>
      </div>
    );
  }

  render() {
    return (
      <div
        class={['apm-home-skeleton', `apm-skeleton-${this.kind}`]}
        aria-label={this.$tc('加载中')}
        role='status'
      >
        <div
          class='apm-skeleton-shapes'
          aria-hidden='true'
        >
          {this.kind === 'apps' &&
            Array.from({ length: 12 }, (_, index) => (
              <div
                key={index}
                class='apm-skeleton-app'
              >
                {this.line('20px', 'is-icon')}
                {this.line(`${[56, 72, 45, 63][index % 4]}%`)}
                {this.line('16px', 'is-count')}
              </div>
            ))}
          {this.kind === 'filters' &&
            Array.from({ length: 4 }, (_, group) => (
              <div
                key={group}
                class='apm-skeleton-filter-group'
              >
                {this.line('44%', 'is-filter-title')}
                {Array.from({ length: 3 }, (_, index) => (
                  <div
                    key={index}
                    class='apm-skeleton-filter'
                  >
                    {this.line('14px', 'is-checkbox')}
                    {this.line(`${[52, 68, 40][index]}%`)}
                    {this.line('18px', 'is-count')}
                  </div>
                ))}
              </div>
            ))}
          {this.kind === 'table' && this.renderTable()}
        </div>
      </div>
    );
  }
}
