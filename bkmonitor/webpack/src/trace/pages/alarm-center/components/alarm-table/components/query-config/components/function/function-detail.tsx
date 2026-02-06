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

import type { AggFunction } from 'monitor-pc/pages/query-template/typings';

import './function-detail.scss';

export default defineComponent({
  name: 'FunctionDetail',
  props: {
    /* 已选函数数组 */
    value: {
      type: Array as PropType<AggFunction[]>,
      default: () => [],
    },
  },

  render() {
    return (
      <div class='alert-function-detail-component'>
        <span class='function-label'>{this.$slots?.label?.() || this.$t('函数')}</span>
        <span class='function-colon'>:</span>
        <div class='function-name-wrap'>
          {this.value?.length
            ? this.value?.map?.((item, index) => {
                const paramsStr = item.params?.map?.(param => param.value)?.toString?.();
                return (
                  <span
                    key={`${item.id}-${index}`}
                    class='function-name'
                  >{`${item.id}${paramsStr ? `(${paramsStr})` : ''}; `}</span>
                );
              })
            : '--'}
        </div>
      </div>
    );
  },
});
