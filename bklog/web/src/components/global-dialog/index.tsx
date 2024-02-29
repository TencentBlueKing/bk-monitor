/*
 * Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 * BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
 *
 * License for BK-LOG 蓝鲸日志平台:
 * --------------------------------------------------------------------
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
 * and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 * The above copyright notice and this permission notice shall be included in all copies or substantial
 * portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
 * LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
 * NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
 * WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
 * SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE
 */

import { Component as tsc } from 'vue-tsx-support';
import {
  Component,
  Model,
  Prop,
} from 'vue-property-decorator';
import { Dialog } from 'bk-magic-vue';
import './index.scss';

interface IProps {
  value: boolean;
  title: string;
}

@Component
export default class MaskingDialog extends tsc<IProps> {
  @Model('change', { type: Boolean, default: false }) value: IProps['value'];
  @Prop({ required: true, default: '' }) title: IProps['title'];

  render() {
    return (
      <Dialog
        value={this.value}
        render-directive="if"
        width="100%"
        scrollable
        show-mask={false}
        show-footer={false}
        draggable={false}
        close-icon={false}
        ext-cls="global-dialog"
        position={{
          top: 50,
          left: 0,
        }}
        style='z-index: 1000;'
      >
        <div class='global-container'>
          <div class="global-title">
            <div></div>
            <span>{this.title}</span>
            <div class="bk-icon icon-close" onClick={() => {
              this.$emit('change', false);
            }}></div>
          </div>
          <div class="center-box">
            <div class='content-panel'>
              {this.$slots.default}
            </div>
          </div>
        </div>
      </Dialog>
    );
  }
}
