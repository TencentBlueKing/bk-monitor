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

import { RUM_ELLIPSIS_MODE_LIST, RumEllipsisModeEnum } from '../../constants';

import type { RumEllipsisModeType } from '../../constants';

import './rum-ellipsis-mode.scss';

export type { RumEllipsisModeType } from '../../constants';

export default defineComponent({
  name: 'RumEllipsisMode',
  props: {
    /** 当前选中的省略方式，默认 ...yz（开头省略） */
    value: {
      type: String as PropType<RumEllipsisModeType>,
      default: RumEllipsisModeEnum.START,
    },
  },
  emits: {
    change: (_value: RumEllipsisModeType) => true,
  },
  setup(_props, { emit }) {
    const { t } = useI18n();
    return {
      t,
      modeList: RUM_ELLIPSIS_MODE_LIST,
      handleSelect: (value: RumEllipsisModeType) => emit('change', value),
    };
  },
  render() {
    return (
      <div class='rum-ellipsis-mode'>
        <span class='mode-label'>{this.t('省略方式')}：</span>
        <div class='mode-group'>
          {this.modeList.map((item, index) => (
            <>
              <div
                key={item.value}
                class={['mode-item', { active: this.value === item.value }]}
                onClick={() => this.handleSelect(item.value)}
              >
                <span class={`mode-item-icon icon-monitor ${item.icon}`} />
              </div>
              {index < this.modeList.length - 1 && (
                <span
                  key={`${item.value}-split`}
                  class='split-line'
                />
              )}
            </>
          ))}
        </div>
      </div>
    );
  },
});
