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

import './plugin-status-tag.scss';

interface IProps {
  checked: boolean;
  icon: string;
  iconFontSize?: number;
  text: string;
  tips?: string;
}
@Component
export default class PluginStatusTag extends tsc<IProps> {
  @Prop({ type: String, default: '' }) icon: string;
  @Prop({ type: Boolean, default: false }) checked: boolean;
  @Prop({ type: String, default: '' }) text: string;
  @Prop({ type: Number }) iconFontSize: number;
  @Prop({ type: String }) tips: string;
  render() {
    return (
      <span class={['plugin-status-tag-item', { 'is-checked': this.checked }]}>
        <span class={['plugin-status-icon']}>
          <i
            style={{ fontSize: `${this.iconFontSize}px` }}
            class={['icon-monitor', this.icon]}
            v-bk-tooltips={{ content: this.tips, disabled: !this.tips, allowHTML: false }}
          />
        </span>
        <span class='plugin-status-text'>{this.text}</span>
      </span>
    );
  }
}
