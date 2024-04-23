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

import './form-item.scss';

interface IProps {
  title?: any | string;
  errMsg?: string;
  require?: boolean;
  width?: number;
}

@Component
export default class FormItem extends tsc<IProps> {
  @Prop({ type: String, default: '' }) title: string;
  @Prop({ type: String, default: '' }) errMsg: string;
  @Prop({ type: Boolean, default: false }) require: boolean;
  @Prop({ type: Number, default: 0 }) width: number;

  render() {
    return (
      <div
        style={{ width: !!this.width ? `${this.width}px` : undefined }}
        class='cluster-config-form-item'
      >
        <div class='form-item-title'>
          <span class={{ require: this.require }}>{this.$slots?.title || this.title}</span>
        </div>
        <div class={['form-item-content', { err: !!this.errMsg }]}>{this.$slots?.default}</div>
        {!!this.errMsg && (
          <div class='form-item-errmsg'>
            <span>{this.errMsg}</span>
          </div>
        )}
      </div>
    );
  }
}
