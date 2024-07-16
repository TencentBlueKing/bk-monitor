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
import { Component, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { Debounce } from 'monitor-common/utils';

import './number-select.scss';

interface IProps {
  list?: number[];
  value?: number;
  onChange?: (v: number) => void;
}

@Component
export default class NumberSelect extends tsc<IProps> {
  @Ref('pop') popRef: any;

  @Prop({ type: Array, default: () => [10, 20, 30, 40, 50] }) list: number[];
  @Prop({ type: [Number, String], default: 0 }) value: number;

  localValue = 0;

  @Watch('value', { immediate: true })
  handleWatchValue(v) {
    this.localValue = v;
  }

  handleSelect(item) {
    this.localValue = item;
    this.popRef.instance.hide();
    this.handleChange(item);
  }

  @Debounce(300)
  handleChange(v) {
    if (this.value !== v) {
      this.$emit('change', v);
    }
  }

  handleBlur() {
    this.handleChange(this.localValue);
  }

  render() {
    return (
      <bk-popover
        ref='pop'
        tippyOptions={{
          appendTo: document.body,
        }}
        animation='slide-toggle'
        arrow={false}
        distance={12}
        offset={-1}
        placement='bottom-start'
        theme='light strategy-view-number-select-pop'
        trigger='click'
      >
        <slot
          class='strategy-view-number-select'
          name='trigger'
        >
          <bk-input
            class='width-45'
            v-model={this.localValue}
            behavior='simplicity'
            max={100}
            min={1}
            showControls={false}
            type='number'
            onBlur={() => this.handleBlur()}
          />
        </slot>
        <ul
          class='list-wrap'
          slot='content'
        >
          {this.list.map((item, index) => (
            <li
              key={index}
              class='list-item'
              onClick={() => this.handleSelect(item)}
            >
              {item}
            </li>
          ))}
        </ul>
      </bk-popover>
    );
  }
}
