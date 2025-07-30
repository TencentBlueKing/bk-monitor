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

import { getCharLength } from './utils';

import './value-tag-input.scss';

interface IProps {
  isOneRow?: boolean;
  value: string;
  onChange?: (v: string) => void;
  onDelete?: (e?: MouseEvent) => void;
  onInput?: (v: string) => void;
}

@Component
export default class ValueTagInput extends tsc<IProps> {
  @Prop({ type: String, default: '' }) value: string;
  @Prop({ type: Boolean, default: false }) isOneRow: boolean;
  @Ref('input') inputRef: HTMLInputElement;

  localValue = '';
  isEdit = false;

  @Watch('value', { immediate: true })
  handleWatchValue() {
    if (this.value !== this.localValue) {
      this.localValue = this.value;
    }
  }

  handleClick() {
    this.isEdit = true;
    this.inputFocus();
  }

  /**
   * @description 输入框输入
   * @param event
   */
  handleInput(event) {
    const input = event.target;
    const value = input.value;
    const charLen = getCharLength(value);
    input.style.setProperty('width', `${charLen * 12}px`);
    this.localValue = value.replace(/(\r\n|\n|\r)/gm, '');
  }

  /**
   * @description 监听回车键
   * @param event
   */
  handleKeyUp(event) {
    const key = event.key || event.keyCode || event.which;
    if (key === 'Enter' || key === 13) {
      event.preventDefault();
      this.handleChangeEmit();
      this.isEdit = false;
    }
  }
  handleKeyDown(event) {
    const key = event.key || event.keyCode || event.which;
    if (key === 'Enter' || key === 13) {
      event.preventDefault();
    }
  }
  /**
   * 聚焦
   */
  inputFocus() {
    this.$nextTick(() => {
      this.inputRef?.focus?.();
    });
  }
  /**
   * @description 失焦
   */
  handleBlur() {
    if (this.isEdit) {
      this.isEdit = false;
      this.handleChangeEmit();
    }
  }

  handleChangeEmit() {
    this.$emit('change', this.localValue);
  }

  handleComponentClick(event) {
    event.stopPropagation();
  }
  handleDelete(e) {
    this.$emit('delete', e);
  }

  render() {
    return (
      <div
        class={['retrieval__value-tag-input-component', { 'edit-active': this.isEdit }, { 'one-row': this.isOneRow }]}
        onClick={this.handleComponentClick}
      >
        <span
          key={'01'}
          class={'value-span'}
          onClick={() => this.handleClick()}
        >
          {this.localValue}
        </span>
        {this.isEdit ? (
          <textarea
            ref={'input'}
            class='value-span-input'
            v-model={this.localValue}
            spellcheck={false}
            onBlur={this.handleBlur}
            onInput={this.handleInput}
            onKeydown={this.handleKeyDown}
            onKeyup={this.handleKeyUp}
          />
        ) : (
          <span
            key={'02'}
            class='icon-monitor icon-mc-close'
            onClick={this.handleDelete}
          />
        )}
      </div>
    );
  }
}
