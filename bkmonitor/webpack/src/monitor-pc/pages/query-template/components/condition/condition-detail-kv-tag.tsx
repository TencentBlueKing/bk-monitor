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
import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { type IFilterItem } from '../../../../components/retrieval-filter/utils';
import { type AggCondition } from '../../typings';

import './kv-tag.scss';

interface IProps {
  value: IFilterItem;
}
@Component
export default class KvTag extends tsc<IProps> {
  @Prop({ type: Object, default: () => null }) condition: AggCondition;
  @Prop({ type: Number, default: 0 }) visibleItemLimit: number;

  localValue: IFilterItem = null;
  hideCount = 0;

  get tipContent() {
    return `<div style="max-width: 600px;">${this.condition.key} ${this.condition.method} ${this.condition.value.join(' OR ')}<div>`;
  }

  @Watch('value', { immediate: true })
  handleWatchValue() {
    if (this.value && JSON.stringify(this.localValue || {}) !== JSON.stringify(this.value)) {
      const localValue = JSON.parse(JSON.stringify(this.value));
      let count = 0;
      const value = [];
      for (const item of this.value.value) {
        if (count === 3) {
          break;
        }
        count += 1;
        value.push({
          ...item,
          name: item.name.length > 20 ? `${item.name.slice(0, 20)}...` : item.name,
        });
      }
      this.localValue = {
        ...localValue,
        value,
      };
      this.hideCount = this.condition.value.length - this.visibleItemLimit;
    }
  }

  delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  render() {
    return this.localValue ? (
      <div class='retrieval-filter__kv-tag-component'>
        <div
          key={this.tipContent}
          class='retrieval-filter__kv-tag-component-wrap'
          v-bk-tooltips={{
            content: this.tipContent,
            delay: [300, 0],
            allowHTML: true,
          }}
        >
          <div class='key-wrap'>
            <span class='key-name'>{this.localValue.key.name}</span>
            <span class={['key-method', this.localValue.method.id]}>{this.localValue.method.name}</span>
          </div>
          <div class='value-wrap'>
            {this.localValue.value.map((item, index) => [
              index > 0 && (
                <span
                  key={`${index}_condition`}
                  class='value-condition'
                >
                  OR
                </span>
              ),
              <span
                key={`${index}_key`}
                class='value-name'
              >
                {item.name || '""'}
              </span>,
            ])}
            {this.hideCount > 0 && <span class='value-condition'>{`+${this.hideCount}`}</span>}
          </div>
        </div>
      </div>
    ) : undefined;
  }
}
