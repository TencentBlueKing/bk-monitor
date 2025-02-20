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
import { Component, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { getCharLength } from './utils';
import ValueTagInput from './value-tag-input';

import './value-tag-selector.scss';

interface IValue {
  id: string;
  name: string; // 暂不显示 预留
}

@Component
export default class ValueTagSelector extends tsc<object> {
  @Ref('input') inputRef: HTMLInputElement;
  localValue: IValue[] = [
    {
      id: 'test1',
      name: 'test',
    },
    {
      id: 'test2',
      name: 'test2',
    },
  ];
  localOptions: IValue[] = [
    {
      id: 'test1',
      name: 'test',
    },
    {
      id: 'test2',
      name: 'test2',
    },
  ];
  /* 是否显示下拉框 */
  isShowDropDown = false;
  /* 当前光标位置 */
  activeIndex = -1;
  /* 当前光标位置输入值 */
  inputValue = '';

  handleCheck(item: IValue) {
    this.localValue.push(item);
  }

  handleClick() {
    this.isShowDropDown = !this.isShowDropDown;
    this.activeIndex = this.localValue.length - 1;
    this.inputFocus();
  }

  handleInput(event) {
    const input = event.target;
    const value = input.value;
    const charLen = getCharLength(value);
    input.style.setProperty('width', `${charLen * 12}px`);
  }

  inputFocus() {
    this.$nextTick(() => {
      this.inputRef?.focus?.();
    });
  }

  render() {
    return (
      <div class='retrieval__value-tag-selector-component'>
        <div
          class='value-tag-selector-component-wrap'
          onClick={this.handleClick}
        >
          {this.localValue.length ? (
            this.localValue.map((item, index) => [
              <ValueTagInput
                key={index}
                class='value-tag-input'
                value={item.id}
              />,
              this.activeIndex === index && (
                <input
                  ref='input'
                  class='focus-input'
                  v-model={this.inputValue}
                  type='text'
                  onInput={this.handleInput}
                />
              ),
            ])
          ) : (
            <span class='placeholder-span'>{`${this.$t('请输入')} ${this.$t('或')} ${this.$t('选择')}`}</span>
          )}
        </div>
        {this.isShowDropDown && (
          <div class='options-drop-down-wrap'>
            {this.localOptions.map((item, index) => (
              <div
                key={index}
                class='options-item'
                onClick={e => {
                  e.stopPropagation();
                  this.handleCheck(item);
                }}
              >
                {item.name}
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }
}
