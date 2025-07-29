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

import AIWhaleIcon from '../../../../components/ai-whale-icon/ai-whale-icon';

import type { TranslateResult } from 'vue-i18n';

import './common-item.scss';

interface ICommonProps {
  desc?: string;
  isRequired?: boolean;
  isSwitch?: boolean;
  isWrap?: boolean;
  showSemicolon?: boolean;
  tips?: string | TranslateResult;
  title: string | TranslateResult;
}
@Component({ name: 'CommonItem' })
export default class MyComponent extends tsc<ICommonProps> {
  @Prop({ type: String, required: false }) title: string;
  @Prop({ type: Boolean, default: false }) isRequired: boolean;
  @Prop({ type: Boolean, default: false }) showSemicolon: boolean;
  @Prop({ type: String, default: '' }) tips!: string;
  @Prop({ type: Boolean, default: false }) isWrap: boolean;
  @Prop({ type: Boolean, default: false }) isSwitch: boolean;
  @Prop({ type: String, default: '' }) desc: string;
  get tooltips() {
    return {
      content: this.tips,
      placements: ['top'],
    };
  }
  render() {
    return (
      <div class={['common-item', { 'common-item-w50': this.isWrap, 'common-item-switch': this.isSwitch }]}>
        <label
          class='common-item-label-wrap'
          for=''
        >
          <div class={{ 'common-item-label': true, 'is-required': this.isRequired }}>
            {this.showSemicolon ? `${this.title}:` : this.title}
          </div>
          {this.tips && (
            <AIWhaleIcon
              class='common-item-desc'
              content={this.title}
              tip={this.tips}
              type='explanation'
            />
          )}
          {this.desc && <span class='common-item-label-desc'>{this.desc}</span>}
        </label>
        <div class='common-item-content'>{this.$slots?.default}</div>
      </div>
    );
  }
}
