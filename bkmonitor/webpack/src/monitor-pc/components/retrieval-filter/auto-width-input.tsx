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

import './auto-width-input.scss';

interface IProps {
  fontSize?: number;
  height?: number;
  initWidth?: number;
  isFocus?: boolean;
  placeholder?: string;
  value?: string;
  onBackspace?: () => void;
  onBackspaceNull?: () => void;
  onBlur?: () => void;
  onEnter?: () => void;
  onFocus?: () => void;
  onInput?: (value: string) => void;
}
@Component
export default class AutoWidthInput extends tsc<IProps> {
  @Prop({ type: String, default: '' }) value: string;
  @Prop({ type: Number, default: 12 }) fontSize: number;
  @Prop({ type: Boolean, default: false }) isFocus: boolean;
  @Prop({ type: Number, default: 22 }) height: number;
  @Prop({ type: Number, default: 12 }) initWidth: number;
  @Prop({ type: String, default: '' }) placeholder: string;

  cacheValue = '';

  @Ref('input') inputRef: HTMLInputElement;

  @Watch('isFocus', { immediate: true })
  handleWatchFocus() {
    setTimeout(() => {
      if (this.isFocus) {
        this.inputRef?.focus();
      } else {
        this.inputRef?.blur();
      }
    }, 50);
  }

  handleInput(e: InputEvent) {
    this.$emit('input', e.target.value);
  }

  handleFocus() {
    this.$emit('focus');
  }
  handleBlur() {
    this.$emit('blur');
  }
  handleKeyup(event) {
    const key = event.key || event.keyCode || event.which;
    if (key === 'Enter' || key === 13) {
      event.preventDefault();
      this.$emit('enter');
    }
    if (key === 'Backspace' || key === 8) {
      this.$emit('backspace');
      if (!this.cacheValue) {
        this.$emit('backspaceNull');
      }
    }
    this.cacheValue = event.target.value;
  }

  render() {
    return (
      <div
        style={{
          height: `${this.height}px`,
          lineHeight: `${this.height}px`,
        }}
        class='auto-width-input-component'
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
  }
}
