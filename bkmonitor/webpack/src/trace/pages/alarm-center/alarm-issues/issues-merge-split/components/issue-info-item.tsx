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

import './issue-info-item.scss';

export interface IssueInfoItemMetric {
  label: string;
  value: number | string;
}

export default defineComponent({
  name: 'IssueInfoItem',
  props: {
    name: {
      type: String,
      default: '',
    },
    desc: {
      type: String,
      default: '',
    },
    /** metric 数据列表 */
    list: {
      type: Array as PropType<IssueInfoItemMetric[] | string[]>,
      default: () => [],
    },
    icon: {
      type: Object as PropType<{
        bgColor?: string;
        color?: string;
        icon?: string;
      }>,
      default: null,
    },
    loading: {
      type: Boolean,
      default: false,
    },
  },
  render() {
    return (
      <div class='issue-info-item'>
        <div class='issue-info-row'>
          <div class='issue-info'>
            {this.icon && (
              <div
                style={{ color: this.icon.color, backgroundColor: this.icon.bgColor }}
                class='level-tag'
              >
                <i class={['icon-monitor', 'sign-icon', this.icon.icon]} />
              </div>
            )}
            {this.loading ? (
              <div class='skeleton-element name-skeleton' />
            ) : (
              <span class='issue-name'>{this.name}</span>
            )}
            <span class='divider' />
            {this.loading ? (
              <div class='skeleton-element desc-skeleton' />
            ) : (
              <span
                class='issue-desc'
                v-overflow-tips
              >
                {this.desc}
              </span>
            )}
          </div>

          {this.$slots.actions?.()}
        </div>
        <div class='issue-metrics-row'>
          {this.$slots.prefix?.()}
          {this.loading
            ? new Array(3).fill(0).map((_, index) => (
                <div
                  key={index}
                  style={{ width: `${Math.random() * 80 + 60}px` }}
                  class='skeleton-element tag-skeleton'
                />
              ))
            : this.list.map((item, index) => (
                <div
                  key={index}
                  class='tag-item metric-item'
                >
                  <div class='label'>{typeof item === 'string' ? item : item.label}</div>
                  {typeof item === 'object' && <div class='value'>{item.value}</div>}
                </div>
              ))}
          {this.$slots.suffix?.()}
        </div>
      </div>
    );
  },
});
