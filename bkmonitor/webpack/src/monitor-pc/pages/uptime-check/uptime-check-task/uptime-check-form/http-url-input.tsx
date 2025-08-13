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
import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { isHttpUrl, isIpv6Url } from 'monitor-common/regex/url';

import type { TranslateResult } from 'vue-i18n';

import './http-url-input.scss';

interface IHttpUrlInputProps {
  errorTips?: string | TranslateResult;
  value: string;
  validateFn?: (v: string) => boolean;
}
@Component
export default class HttpUrlInput extends tsc<
  IHttpUrlInputProps,
  {
    onChange: string;
    onDelete: MouseEvent;
    onEidt: MouseEvent;
  }
> {
  @Prop() value: string;
  @Prop({ default: window.i18n.tc('输入正确的url') }) errorTips: string;
  @Prop() validateFn: (v: string) => boolean;
  edit = false;
  isError = false;
  @Emit('change')
  handleChange(v: string) {
    return v;
  }
  @Emit('delete')
  handleDelete(e: MouseEvent) {
    return e;
  }
  @Emit('edit')
  handleEdit() {
    this.edit = true;
    setTimeout(() => {
      (this.$refs.urlInput as any)?.focus?.();
    });
  }
  handleBlur(v: string) {
    if (!this.validateFn) {
      this.isError = !(isHttpUrl(v) || isIpv6Url(v));
    } else {
      this.isError = !this.validateFn(v);
    }
    if (this.isError) return;
    if (this.value !== v) {
      this.handleChange(v);
    }
    this.edit = false;
  }
  handleFocus() {
    this.isError = false;
  }
  render() {
    return (
      <div class='http-url-input'>
        {!this.edit ? (
          <div class='url-text'>
            {this.value}
            <i
              class='icon-monitor icon-bianji text-edit'
              onClick={this.handleEdit}
            />
            <i
              class='icon-monitor icon-mc-close text-close'
              onClick={this.handleDelete}
            />
          </div>
        ) : (
          <div class={`bk-form-item ${this.isError ? 'is-error' : ''}`}>
            <bk-input
              ref='urlInput'
              class='url-input'
              value={this.value}
              onBlur={this.handleBlur}
              onChange={this.handleChange}
              onEnter={this.handleBlur}
              onFocus={this.handleFocus}
            />
            {this.isError && (
              <i
                class='bk-icon icon-exclamation-circle-shape terror-tips-icon'
                v-bk-tooltips={{ content: this.errorTips, allowHTML: false }}
              />
            )}
            {/* {this.isError && <div class='error-tips'>{this.errorTips}</div>} */}
          </div>
        )}
      </div>
    );
  }
}
