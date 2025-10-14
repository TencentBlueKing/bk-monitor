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

import { type IFilterItem, ECondition } from 'monitor-pc/components/retrieval-filter/utils';

import './condition-condition-tag.scss';

export const CONDITIONS = [
  {
    id: ECondition.and,
    name: 'AND',
  },
  {
    id: ECondition.or,
    name: 'OR',
  },
];

interface IProps {
  value: IFilterItem;
  onChange?: (id: ECondition) => void;
}

@Component
export default class ConditionConditionTag extends tsc<IProps> {
  @Prop({ type: Object, default: () => null }) value: IFilterItem;

  get tipContent() {
    return `<div style="max-width: 600px;">${this.value.condition.id}<div>`;
  }

  handleChange(id) {
    if (id !== this.value.condition.id) {
      this.$emit('change', id);
    }
  }

  render() {
    return (
      <div class='template-config-page-condition-tag-component'>
        <bk-dropdown-menu
          position-fixed={true}
          trigger='click'
        >
          <div
            class='template-config-page-condition-tag-content'
            slot='dropdown-trigger'
            v-bk-tooltips={{
              content: this.tipContent,
              delay: [300, 0],
              allowHTML: true,
            }}
          >
            <div class='name-wrap'>{this.value.condition.name}</div>
          </div>
          <ul
            class='condition-options'
            slot='dropdown-content'
          >
            {CONDITIONS.map(item => (
              <li
                key={item.id}
                class={['condition-option', { active: item.id === this.value.condition.id }]}
                onClick={() => this.handleChange(item.id)}
              >
                {item.name}
              </li>
            ))}
          </ul>
        </bk-dropdown-menu>
      </div>
    );
  }
}
