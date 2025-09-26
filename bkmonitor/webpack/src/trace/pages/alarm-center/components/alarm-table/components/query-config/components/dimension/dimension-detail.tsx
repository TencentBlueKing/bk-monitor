/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
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

import type { DimensionField } from 'monitor-pc/pages/query-template/typings';

import './dimension-detail.scss';

export default defineComponent({
  name: 'DimensionDetail',
  props: {
    /* 聚合维度信息 id-聚合维度对象 映射表 */
    allDimensionMap: {
      type: Object as PropType<Record<string, DimensionField>>,
      default: () => ({}),
    },
    /* 已选聚合维度id数组 */
    value: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
  },
  render() {
    return (
      <div class='alert-dimension-detail-component'>
        <span class='dimension-label'>{this.$slots?.label || this.$t('聚合维度')}</span>
        <span class='dimension-colon'>:</span>
        <div class='tags-wrap'>
          {this.value?.length
            ? this.value?.map?.(v => (
                <div
                  key={v}
                  class='tags-item'
                  v-tippy={{
                    content: v,
                    placement: 'top',
                    disabled: !v,
                    delay: [300, 0],
                  }}
                >
                  <span class='tags-item-name'>{this.allDimensionMap?.[v]?.name || v}</span>
                </div>
              ))
            : '--'}
        </div>
      </div>
    );
  },
});
