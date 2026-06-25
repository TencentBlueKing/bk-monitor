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

import { Checkbox, Input } from 'bkui-vue';

import './reason-section.scss';

export default defineComponent({
  name: 'ReasonSection',
  props: {
    selectValue: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
    inputValue: {
      type: String,
      default: '',
    },
    placeholder: {
      type: String,
      default: '',
    },
    /** 选项列表 */
    options: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
    title: {
      type: String,
      default: '',
    },
    /** 提示文本 */
    tips: {
      type: String,
      default: '',
    },
  },
  emits: ['input', 'selectChange'],
  setup(_, { emit }) {
    const handleSelectChange = (value: string[]) => {
      emit('selectChange', value);
    };

    const handleInput = (value: string) => {
      emit('input', value);
    };

    return {
      handleSelectChange,
      handleInput,
    };
  },
  render() {
    return (
      <div class='reason-section'>
        <div class='reason-section-header'>
          <div class='section-title'>{this.title}</div>
          {this.tips && (
            <span class='reason-tips'>
              <i class='icon-monitor icon-hint' />
              <span>{this.tips}</span>
            </span>
          )}
        </div>
        <Checkbox.Group
          class='reason-checkbox-group'
          modelValue={this.selectValue}
          onChange={this.handleSelectChange}
        >
          {this.options.map(option => (
            <Checkbox
              key={option}
              label={option}
            >
              {option}
            </Checkbox>
          ))}
        </Checkbox.Group>
        <Input
          class='custom-reason-input'
          modelValue={this.inputValue}
          placeholder={this.placeholder}
          onInput={this.handleInput}
        />
      </div>
    );
  },
});
