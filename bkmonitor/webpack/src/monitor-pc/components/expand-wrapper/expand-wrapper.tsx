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
import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './expand-wrapper.scss';

interface IProps {
  value: boolean;
  onChange?: (v: boolean) => void;
}

@Component
export default class ExpandWrapper extends tsc<IProps> {
  @Prop({ type: Boolean, default: false }) value: boolean;

  isExpan = false;

  @Watch('value', { immediate: true })
  handleWatchValue(v: boolean) {
    if (this.isExpan !== v) {
      this.isExpan = v;
    }
  }

  handleExpan() {
    this.isExpan = !this.isExpan;
    this.$emit('change', this.isExpan);
  }

  render() {
    return (
      <div class='expand-wrapper-component'>
        <div
          class={['wrap-header', { active: this.isExpan }]}
          onClick={this.handleExpan}
        >
          <div class='expan-btn'>
            <span class={['icon-monitor icon-mc-triangle-down', { active: this.isExpan }]} />
          </div>
          <div class='wrap-header-slot'>{this.$slots?.header}</div>
        </div>
        <div class={['wrap-content', { show: this.isExpan }]}>{this.$slots?.content}</div>
      </div>
    );
  }
}
