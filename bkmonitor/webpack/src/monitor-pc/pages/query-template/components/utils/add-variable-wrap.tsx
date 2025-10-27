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

import { Component, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { validateVariableNameInput } from '../../variables/template/utils';
import VariableNameInput from './variable-name-input';

import './add-variable-wrap.scss';

interface IProps {
  allVariables?: { name: string }[];
  hasOperate?: boolean;
  notPop?: boolean;
  show?: boolean;
  value: string;
  onAdd?: () => void;
  onCancel?: () => void;
  onChange?: (val: string) => void;
}

@Component
export default class AddVariableWrap extends tsc<IProps> {
  @Prop({ type: String, default: '' }) value: string;
  @Prop({ type: Boolean, default: false }) notPop: boolean;
  @Prop({ type: Boolean, default: false }) show: boolean;
  @Prop({ type: Boolean, default: true }) hasOperate: boolean;
  /* 所有变量，用于校验变量名是否重复 */
  @Prop({ default: () => [] }) allVariables: { name: string }[];

  @Ref('varInput') varInput: VariableNameInput;

  errMsg = '';

  handleChange(val) {
    this.$emit('change', val);
    this.errMsg = '';
  }

  handleAdd() {
    this.errMsg = validateVariableNameInput(this.varInput.localValue);
    if (this.errMsg) {
      return this.errMsg;
    }
    const allVarSet = new Set(this.allVariables.map(item => item.name));
    const varName = '${' + this.varInput.localValue + '}';
    if (allVarSet.has(varName)) {
      this.errMsg = this.$t('变量名不可重复') as string;
      return this.errMsg;
    }
    this.$emit('add');
    return this.errMsg;
  }
  handleCancel() {
    this.$emit('cancel');
  }

  handleEnter() {
    this.handleAdd();
  }

  render() {
    return (
      <div
        class={['template-config-options-add-variable-option-pop', { 'not-pop': this.notPop }]}
        onClick={e => e.stopPropagation()}
      >
        <div class='header-title'>
          <span class='header-title-name'>{this.$t('变量名')}</span>
        </div>
        <VariableNameInput
          ref='varInput'
          class='var-input'
          isErr={!!this.errMsg}
          show={this.show}
          value={this.value}
          onChange={this.handleChange}
          onEnter={this.handleEnter}
        />
        {!!this.errMsg && <div class='error-tip'>{this.errMsg}</div>}
        {this.hasOperate && (
          <div class='btn-wrap'>
            <bk-button
              class='confirm-btn'
              size='small'
              theme='primary'
              onClick={this.handleAdd}
            >
              {this.$t('确定')}
            </bk-button>
            <bk-button
              size='small'
              onClick={this.handleCancel}
            >
              {this.$t('取消')}
            </bk-button>
          </div>
        )}
      </div>
    );
  }
}
