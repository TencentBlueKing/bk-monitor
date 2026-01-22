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

import './drill-down-options.scss';

export default defineComponent({
  name: 'DrillDownOptions',
  props: {
    active: {
      type: String,
      default: '',
    },
    dimensions: {
      type: Array as PropType<{ id: string; name: string }[]>,
      default: () => [],
    },
    isFixed: {
      type: Boolean,
      default: false,
    },
    hasTitle: {
      type: Boolean,
      default: false,
    },
  },
  emits: {
    select: (_id: string) => true,
  },
  setup(_props, { emit }) {
    const { t } = useI18n();
    const handleSelectDimension = (id: string) => {
      emit('select', id);
    };
    return {
      t,
      handleSelectDimension,
    };
  },
  render() {
    return (
      <div
        style={{
          position: this.isFixed ? 'fixed' : 'relative',
        }}
        class='dimension-analysis-drill-down-options-popover'
      >
        {this.hasTitle && <div class='header-title'>{this.t('下钻至')}</div>}
        <div class='dimension-analysis-drill-down-options-popover-list'>
          {this.dimensions.map((item, index) => {
            const active = this.active === item.id;
            return (
              <div
                key={index}
                class={['selector-item', { active }]}
                onClick={() => {
                  if (!active) {
                    this.handleSelectDimension(item.id);
                  }
                }}
              >
                <span
                  class='selector-item-name'
                  v-overflow-tips
                >
                  {item.name}
                </span>
                {/* {index > 5 && (
                  <span
                    class='suspicious-tag'
                    v-bk-tooltips={{
                      content: <div>可疑可疑</div>,
                    }}
                  >
                    <span>{this.t('可疑')}</span>
                  </span>
                )} */}
              </div>
            );
          })}
        </div>
      </div>
    );
  },
});
