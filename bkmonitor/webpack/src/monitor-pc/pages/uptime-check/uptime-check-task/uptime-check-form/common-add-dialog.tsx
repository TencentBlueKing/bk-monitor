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
import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import MonitorDialog from 'monitor-ui/monitor-dialog';

import type { TranslateResult } from 'vue-i18n';

import './common-add-dialog.scss';

interface ICommonAddDialogEvent {
  onConfirm: string;
  onFocus: MouseEvent;
  onShowChange: boolean;
}
interface ICommonAddDialogProps {
  defaultValue: string;
  placeholder?: string | TranslateResult;
  show: boolean;
  showValidateTips?: boolean;
  title?: string | TranslateResult;
  validateTips?: string | TranslateResult;
}
@Component
export default class CommonAddDialog extends tsc<ICommonAddDialogProps, ICommonAddDialogEvent> {
  @Prop() show: boolean;
  @Prop() placeholder: string | TranslateResult;
  @Prop() title: string | TranslateResult;
  @Prop() defaultValue: string;
  @Prop() validateTips: string;
  @Prop() showValidateTips: boolean;
  value = '';
  @Watch('show', { immediate: true })
  onShowChange(v: boolean) {
    if (v) {
      this.value = this.defaultValue;
    }
  }
  @Emit('showChange')
  handleShowChange(v: boolean) {
    return v;
  }
  handleCancel() {
    this.handleShowChange(false);
  }
  handleConfirm() {
    if (this.value.length) {
      this.$emit('confirm', this.value);
    }
    // this.handleCancel();
  }
  @Emit('focus')
  handleFocus(e: MouseEvent) {
    return e;
  }
  render() {
    return (
      <MonitorDialog
        width='488'
        class='common-add-dialog'
        title={this.title.toString()}
        value={this.show}
        onCancel={this.handleCancel}
        onChange={this.handleShowChange}
        onConfirm={this.handleConfirm}
      >
        <bk-input
          class={`url-input ${this.showValidateTips ? 'is-error' : ''}`}
          vModel={this.value}
          placeholder={this.placeholder}
          type='textarea'
          onFocus={this.handleFocus}
        />
        {this.showValidateTips && <div class='validate-tips'>{this.validateTips}</div>}
      </MonitorDialog>
    );
  }
}
