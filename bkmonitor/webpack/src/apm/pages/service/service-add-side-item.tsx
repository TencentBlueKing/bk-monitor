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
import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './service-add-side-item.scss';

type IEvent = {
  onCopy: () => void;
};

interface IProps {
  copyValue?: string;
  disabledStyle?: boolean;
  title: string;
}

@Component
export default class ServiceAddSideItem extends tsc<IProps, IEvent> {
  // 展示的标题
  @Prop({ default: '', type: String }) title: string;
  // 灰底背景
  @Prop({ default: false, type: Boolean }) disabledStyle: boolean;

  @Emit('copy')
  handleCopy() {}

  render() {
    return (
      <div class='service-add-side__item'>
        <div class='service-add-side__item-label'>{this.title}</div>
        <div class='service-add-side__item-content'>
          <div class={['service-add-side__item-hd', { 'is-disabled': this.disabledStyle }]}>{this.$slots.default}</div>
          <div
            class='service-add-side__item-bd'
            onClick={this.handleCopy}
          >
            <i
              class='icon-monitor icon-mc-copy'
              v-bk-tooltips={{ content: this.$t('复制') }}
            />
          </div>
        </div>
        {this.$slots.btm && <div class='service-add-side__item-btm'>{this.$slots.btm}</div>}
      </div>
    );
  }
}
