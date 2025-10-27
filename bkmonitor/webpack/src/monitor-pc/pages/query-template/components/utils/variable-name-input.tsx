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

import { Component, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './variable-name-input.scss';

interface IProps {
  isErr?: boolean;
  show?: boolean;
  value: string;
  onChange?: (val: string) => void;
  onEnter?: () => void;
}

@Component
export default class VariableNameInput extends tsc<IProps> {
  @Prop({ type: String, default: '' }) value: string;
  @Prop({ type: Boolean, default: false }) show: boolean;
  @Prop({ type: Boolean, default: false }) isErr: boolean;

  @Ref('input') inputRef;

  localValue = '';

  handleChange(val: string) {
    this.$emit('change', val ? '${' + val + '}' : val);
  }

  @Watch('show', { immediate: true })
  handleWatchShow(val) {
    if (val) {
      this.$nextTick(() => {
        this.inputRef?.focus();
        this.localValue = '';
        // if (!val) {
        //   return;
        // }
        // console.log(val, isVariableName(val), getVariableNameInput(val));
        // if (isVariableName(val)) {
        //   this.localValue = getVariableNameInput(val);
        // } else {
        //   this.localValue = val;
        // }
      });
    }
  }

  handleEnter() {
    this.$emit('enter');
  }

  render() {
    return (
      <div class={['template-config-variable-name-input', { 'is-err': this.isErr }]}>
        <div class='label-left'>{'${'}</div>
        <bk-input
          ref='input'
          class='variable-name-input'
          v-model={this.localValue}
          placeholder={this.$t('大小写字符、数字、下划线、点（.），50个字符以内')}
          onChange={this.handleChange}
          onEnter={this.handleEnter}
        />
        <div class='label-right'>{'}'}</div>
      </div>
    );
  }
}
