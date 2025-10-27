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

import AddVariableWrap from './add-variable-wrap';

import './add-variable-option.scss';

interface IProps {
  allVariables?: { name: string }[];
  popDistance?: number;
  onAdd?: (val: string) => void;
  onOpenChange?: (v: boolean) => void;
}

@Component
export default class AddVariableOption extends tsc<IProps> {
  @Ref('addVarPopRef') addVarPopRef: HTMLDivElement;
  /* 所有变量，用于校验变量名是否重复 */
  @Prop({ default: () => [] }) allVariables: { name: string }[];
  @Prop({ default: 7 }) popDistance: number;

  inputValue = '';

  popoverInstance = null;
  isShowPop = false;

  handleClick(e: Event) {
    this.handleShowPopover(e);
  }

  handleChange(val) {
    this.inputValue = val;
  }

  beforeDestroy() {
    this.popoverDestroy();
  }

  handleShowPopover(e: Event) {
    if (!this.popoverInstance) {
      this.popoverInstance = this.$bkPopover(e.currentTarget, {
        content: this.addVarPopRef.$el,
        arrow: false,
        trigger: 'click',
        placement: 'right-start',
        theme: 'light common-monitor',
        boundary: 'window',
        interactive: true,
        distance: this.popDistance,
        onHidden: () => {
          this.popoverDestroy();
        },
      });
    }
    this.popoverInstance?.show(100);
    this.isShowPop = true;
    this.$emit('openChange', true);
  }

  popoverDestroy() {
    this.popoverInstance?.hide();
    this.popoverInstance?.destroy();
    this.popoverInstance = null;
    this.isShowPop = false;
    this.inputValue = '';
    this.$emit('openChange', false);
  }

  handleCancel() {
    this.popoverDestroy();
  }

  handleAdd() {
    this.$emit('add', this.inputValue);
    this.popoverDestroy();
  }

  render() {
    return (
      <div class='template-config-options-add-variable-option'>
        <span
          class='add-var-name'
          onClick={this.handleClick}
        >
          <span class='add-var-name-left'>
            {this.$t('创建变量')}&nbsp;
            {'${}'}
          </span>
          <span class='icon-monitor icon-arrow-right' />
        </span>
        <div style={{ display: 'none' }}>
          <AddVariableWrap
            ref='addVarPopRef'
            allVariables={this.allVariables}
            show={this.isShowPop}
            value={this.inputValue}
            onAdd={this.handleAdd}
            onCancel={this.handleCancel}
            onChange={this.handleChange}
          />
        </div>
      </div>
    );
  }
}
