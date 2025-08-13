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
import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import type { TranslateResult } from 'vue-i18n';

import './common-form-item.scss';

interface ICommonFormItemProp {
  isRequired?: boolean;
  showSemicolon?: boolean;
  tips?: string | TranslateResult;
  title: string | TranslateResult;
  topTitle?: boolean;
}
@Component({
  name: 'CommonFormItem',
})
export default class CommonFormItem extends tsc<ICommonFormItemProp> {
  @Prop({ type: String, required: false }) title: string | TranslateResult;
  @Prop({ type: Boolean, default: false }) isRequired: boolean;
  @Prop({ type: Boolean, default: false }) showSemicolon: boolean;
  @Prop({ type: String, default: '' }) tips!: string;
  @Prop({ type: Boolean, default: false }) topTitle: boolean;

  public tooltips = {
    content: this.tips,
    placements: ['top'],
    allowHTML: false,
  };

  render() {
    return (
      <div class={['common-form-item', { 'title-top': this.topTitle }]}>
        <label class={['form-item-label', { 'is-required': this.isRequired }]}>
          {this.showSemicolon ? `${this.title}:` : this.title}
        </label>
        <div class='form-item-content concise'>
          {this.$slots?.default}
          {this.tips ? (
            <span>
              <i
                class='icon-monitor icon-tips form-item-desc'
                v-bk-tooltips={this.tooltips}
              />
            </span>
          ) : undefined}
        </div>
      </div>
    );
  }
}
