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
import { defineComponent } from 'vue';

import { useI18n } from 'vue-i18n';

import type { SlotReturnValue } from 'tdesign-vue-next';

import './rum-content-skeleton.scss';

export const rumSkeletonLine = (width: number | string, className = '') => (
  <span
    style={{ width: typeof width === 'number' ? `${width}px` : width }}
    class={['rum-content-line', className]}
  />
);

export function renderRumTableSkeletonCell(field: string, index: number) {
  if (field === '__col_setting__') return null;
  const status = /status|health|type|field$/.test(field);
  const metric = /lcp|Rate|count|size|pri|rep/i.test(field);
  return (
    <div
      class='rum-content-cell'
      aria-hidden='true'
    >
      {field === 'appName' && rumSkeletonLine(24, 'is-icon')}
      {rumSkeletonLine(status ? 48 : metric ? 56 : `${[68, 82, 55, 74][index % 4]}%`, status ? 'is-tag' : '')}
    </div>
  ) as unknown as SlotReturnValue;
}

export default defineComponent({
  name: 'RumContentSkeleton',
  setup() {
    const { t } = useI18n();
    return { t };
  },
  render() {
    return (
      <div
        class='rum-content-skeleton'
        aria-label={this.t('加载中...')}
        role='status'
      >
        <div aria-hidden='true'>
          {[0, 1].map(section => (
            <div
              key={section}
              class='rum-content-section'
            >
              {rumSkeletonLine([72, 96][section], 'is-title')}
              <div class='rum-content-description'>
                {rumSkeletonLine('72%')}
                {rumSkeletonLine('48%')}
              </div>
              <div class='rum-content-fields'>
                {(section ? [0] : [0, 1]).map(field => (
                  <div
                    key={field}
                    class='rum-content-field'
                  >
                    {rumSkeletonLine(64)}
                    {rumSkeletonLine(96, 'is-value')}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  },
});
