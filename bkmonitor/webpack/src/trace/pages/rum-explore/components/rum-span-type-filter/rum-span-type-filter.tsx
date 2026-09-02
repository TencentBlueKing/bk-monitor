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

import { ALL_SPAN_TYPE } from '../../constants';

import type { IRumSpanTypeChip } from '../../composables/use-rum-span-type';

import './rum-span-type-filter.scss';

/** span 类型快捷筛选，列表由接口驱动，前端不写死类型枚举 */
export default defineComponent({
  name: 'RumSpanTypeFilter',
  props: {
    list: {
      type: Array as PropType<IRumSpanTypeChip[]>,
      default: () => [],
    },
    loading: {
      type: Boolean,
      default: false,
    },
    /** 当前选中的类型，空串代表「全部」 */
    value: {
      type: String,
      default: ALL_SPAN_TYPE,
    },
  },
  emits: {
    change: (_value: string) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    return {
      t,
      handleSelect: (value: string) => emit('change', value),
    };
  },
  render() {
    if (this.loading) {
      return (
        <div class='rum-span-type-filter'>
          <div class='skeleton-element filter-label-skeleton' />
          <div class='filter-chips'>
            <div class='skeleton-element type-chip-skeleton' />
            <div class='skeleton-element type-chip-skeleton' />
            <div class='skeleton-element type-chip-skeleton' />
            <div class='skeleton-element type-chip-skeleton' />
          </div>
        </div>
      );
    }
    // if (!this.list.length) return null;
    return (
      <div class='rum-span-type-filter'>
        <span class='filter-label'>{this.t('类型选择')}：</span>
        <div class='filter-chips'>
          <div
            class={['type-chip', { active: !this.value }]}
            onClick={() => this.handleSelect(ALL_SPAN_TYPE)}
          >
            <span class='chip-label'>{this.t('全部')}</span>
          </div>
          {this.list?.map(item => (
            <div
              key={item.value}
              class={['type-chip', { active: this.value === item.value }]}
              onClick={() => this.handleSelect(item.value)}
            >
              {item.icon && (
                <img
                  class='chip-icon'
                  alt=''
                  src={item.icon}
                />
              )}
              <span class='chip-label'>{item.label}</span>
            </div>
          ))}
        </div>
      </div>
    );
  },
});
