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

import './notify-box.scss';

interface IStepBoxProps {
  hasBorder: boolean;
  placement: string;
  tipStyles: Record<string, string>;
}

@Component
export default class NotifyBox extends tsc<IStepBoxProps> {
  // 显示的位置
  @Prop({ type: String, default: '' }) placement: string;
  // 是否包含外边框
  @Prop({ type: Boolean, default: false }) hasBorder: boolean;
  // 组件额外样式
  @Prop({ default: {} }) tipStyles: Record<string, string>;

  // className
  get className() {
    return `${this.placement} ${this.hasBorder ? 'has-border' : ''}`;
  }

  render() {
    return (
      <div
        style={this.tipStyles}
        class={`notify-box ${this.className}`}
      >
        <div class='notify-title'>{this.$slots.title}</div>
        <div class='notify-content'>{this.$slots.content}</div>
        <div class='notify-action'>{this.$slots.action}</div>
        <div class='target-arrow' />
      </div>
    );
  }
}
