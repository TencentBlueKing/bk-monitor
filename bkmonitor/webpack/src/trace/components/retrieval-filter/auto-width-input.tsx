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

import { defineComponent, shallowRef, useTemplateRef, watch } from 'vue';

import { AUTO_WIDTH_INPUT_EMITS, AUTO_WIDTH_INPUT_PROPS } from './typing';

import './auto-width-input.scss';

export default defineComponent({
  name: 'AutoWidthInput',
  props: AUTO_WIDTH_INPUT_PROPS,
  emits: AUTO_WIDTH_INPUT_EMITS,
  setup(props, { emit }) {
    const inputRef = useTemplateRef<HTMLInputElement>('input');

    const cacheValue = shallowRef('');

    watch(
      () => props.isFocus,
      val => {
        setTimeout(() => {
          if (val) {
            inputRef.value?.focus();
          } else {
            inputRef.value?.blur();
          }
        }, 50);
      },
      { immediate: true }
    );

    function handleInput(e: Event) {
      emit('input', e.target.value);
    }
    function handleFocus() {
      emit('focus');
    }
    function handleBlur() {
      emit('blur');
    }
    function handleKeyup(event) {
      const key = event.key || event.keyCode || event.which;
      if (key === 'Enter' || key === 13) {
        event.preventDefault();
        emit('enter');
      }
      if (key === 'Backspace' || key === 8) {
        emit('backspace');
        if (!cacheValue.value) {
          emit('backspaceNull');
        }
      }
      cacheValue.value = event.target.value;
    }

    return {
      handleBlur,
      handleFocus,
      handleInput,
      handleKeyup,
    };
  },
  render() {
    return (
      <div
        style={{
          height: `${this.height}px`,
          lineHeight: `${this.height}px`,
        }}
        class='vue3_auto-width-input-component'
      >
        <input
          ref={'input'}
          placeholder={this.placeholder}
          spellcheck={false}
          type='text'
          value={this.value}
          onBlur={this.handleBlur}
          onFocus={this.handleFocus}
          onInput={this.handleInput}
          onKeyup={this.handleKeyup}
        />
        <span class='input-value-hidden'>{this.value}</span>
      </div>
    );
  },
});
