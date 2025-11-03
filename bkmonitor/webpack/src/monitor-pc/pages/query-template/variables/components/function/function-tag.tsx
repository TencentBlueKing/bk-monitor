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

import type { AggFunction } from '../../../typings';

interface FunctionTagProps {
  data: AggFunction;
  metricFunctions: any[];
}

@Component
export default class FunctionTag extends tsc<FunctionTagProps> {
  @Prop({ required: true }) data!: AggFunction;
  @Prop({ default: () => [] }) metricFunctions!: any[];

  get optionMap() {
    const optionMap = new Map();
    for (const option of this.metricFunctions) {
      for (const child of option?.children || []) {
        optionMap.set(child.id, child);
      }
    }
    return optionMap;
  }

  get functionItem() {
    const option = this.optionMap.get(this.data.id);
    return {
      ...option,
      params:
        this.data?.params?.map(p => {
          const optionP = option?.params?.find(param => param.id === p.id);
          if (optionP) {
            return {
              ...optionP,
              value: p.value,
            };
          }
          return {
            ...p,
          };
        }) || [],
    };
  }

  render() {
    return (
      <span class='function-tag'>
        <span class={['is-hover', 'func-name']}>{this.functionItem?.name}</span>
        {this.functionItem.params?.length ? <span class='brackets'>&nbsp;(&nbsp;</span> : undefined}
        {this.functionItem.params.map((param, pIndex) => (
          <span
            key={`item-${pIndex}}`}
            class='params-item'
          >
            <span class={['params-text', 'is-hover']}>{param.value || `-${this.$t('空')}-`}</span>
            {pIndex !== this.functionItem.params.length - 1 && <span>,&nbsp;</span>}
          </span>
        ))}
        {this.functionItem.params.length ? <span class='brackets'>&nbsp;)&nbsp;</span> : undefined}
      </span>
    );
  }
}
