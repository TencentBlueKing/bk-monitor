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
import { TranslateResult } from 'vue-i18n';
import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './notice-item.scss';

interface IProps {
  value: boolean;
  title: string | TranslateResult;
  subTitle: string | TranslateResult;
  onChange?: (v: boolean) => void;
  clearError: () => void;
}

@Component({
  name: 'NoticeItem'
})
export default class NoticeItem extends tsc<IProps> {
  @Prop({ type: Boolean, default: false }) value: boolean;
  @Prop({ type: String, default: '' }) title: string;
  @Prop({ type: String, default: '' }) subTitle: string;
  @Prop({ type: Function, default: () => {} }) clearError: () => void;

  @Emit('change')
  valueChange(val: boolean) {
    return val;
  }
  render() {
    return (
      <div class='notice-item-container mb10'>
        <div class='notice-item-warp'>
          <div class='notice-header-warp'>
            <bk-checkbox
              onChange={value => {
                this.valueChange(value);
                this.clearError();
              }}
              value={this.value}
            ></bk-checkbox>
            <div
              class='title'
              v-bk-overflow-tips
            >
              {this.title}
            </div>
            <div class='subTitle'>
              <i class='icon-monitor icon-hint'></i>
              <span v-bk-overflow-tips> {this.subTitle}</span>
            </div>
            {this.$slots.header && <span class='header-right'>{this.$slots.header}</span>}
          </div>
          {this.value && this.$slots.default && <div class='notice-content-warp'>{this.$slots.default}</div>}
        </div>
      </div>
    );
  }
}
