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
import { type PropType, type SlotsType, computed, defineComponent } from 'vue';
import type { VNodeChild } from 'vue';

import { ARRAY_ITEM_EMPTY_PLACEHOLDER } from '../../../../utils/array-field-formatter';

import type { CompositeRow, CompositeValue } from '../../column-layout';

import './composite-cell.scss';

export default defineComponent({
  name: 'RumCompositeCell',
  props: {
    /** 已按当前记录解析的可见行，保留协议中的顺序和分隔符。 */
    rows: { type: Array as PropType<CompositeRow[]>, required: true },
  },
  slots: Object as SlotsType<{
    /** 渲染正文后的单个标签字段。 */
    badge: (value: CompositeValue) => VNodeChild;
    /** 渲染正文中的单个字段。 */
    item: (value: CompositeValue) => VNodeChild;
    /** 在当前行正文前插入入口。 */
    prefix: (row: CompositeRow) => VNodeChild;
    /** 在当前行标签后插入入口。 */
    suffix: (row: CompositeRow) => VNodeChild;
  }>,
  setup(props) {
    const isEmpty = computed(() => props.rows.length === 0);
    return { isEmpty };
  },
  render() {
    if (this.isEmpty) return <div class='explore-col rum-empty-text'>{ARRAY_ITEM_EMPTY_PLACEHOLDER}</div>;
    return (
      <div class='explore-col rum-composite-col'>
        {this.rows.map(row => (
          <div
            key={row.index}
            class={['rum-composite-line', { 'is-secondary': row.index > 0 }]}
          >
            {this.$slots.prefix?.(row)}
            {row.items.length > 0 && (
              <span class='rum-composite-main'>
                {row.items.map((item, index) => (
                  <span
                    key={item.key}
                    class='rum-composite-member'
                  >
                    {index > 0 && row.separator && <span class='rum-composite-separator'>{row.separator}</span>}
                    {this.$slots.item?.(item)}
                  </span>
                ))}
              </span>
            )}
            {row.badges.length > 0 && (
              <span class='rum-composite-badges'>
                {row.badges.map(badge => (
                  <span
                    key={badge.key}
                    class='rum-composite-badge'
                  >
                    {this.$slots.badge?.(badge)}
                  </span>
                ))}
              </span>
            )}
            {this.$slots.suffix?.(row)}
          </div>
        ))}
      </div>
    );
  },
});
