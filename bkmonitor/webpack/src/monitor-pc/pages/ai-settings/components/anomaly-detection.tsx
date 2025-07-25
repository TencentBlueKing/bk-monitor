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

import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import type { TranslateResult } from 'vue-i18n';

import './anomaly-detection.scss';

interface IGroupPanelProps {
  defaultExpand?: boolean;
  isPackUp?: boolean;
  readonly?: boolean;
  showExpand?: boolean;
  subtitle?: string | TranslateResult;
  theme?: 'dark' | 'light';
  title?: string | TranslateResult;
  validate?: boolean;
}

@Component
export default class AnomalyDetection extends tsc<IGroupPanelProps, { onExpand: boolean }> {
  @Prop({ default: '', type: String }) title!: string;
  @Prop({ default: '', type: String }) subtitle!: string;
  @Prop({ default: false, type: Boolean }) showExpand!: boolean;
  @Prop({ default: true, type: Boolean }) defaultExpand!: boolean;
  @Prop({ default: false, type: Boolean }) readonly: boolean;
  @Prop({ default: true, type: Boolean }) validate: boolean;
  @Prop({ default: false, type: Boolean }) isPackUp: boolean; // 是否只能收起
  @Prop({ default: 'light', type: String }) theme: string;

  expand = true;

  created() {
    this.expand = this.defaultExpand;
  }

  @Watch('isPackUp')
  handleIsPackUp(v: boolean) {
    this.expand = !v;
  }

  @Emit('expand')
  handleExpandPanel() {
    if (!this.showExpand) return this.expand;

    this.expand = !this.expand;
    return this.expand;
  }

  render() {
    return (
      <div class={['anomaly-detection', { 'anomaly-dark': this.theme === 'dark' }]}>
        <div class='anomaly-detection-header'>
          <div
            style={{ cursor: this.showExpand ? 'pointer' : 'default' }}
            class='header-wrapper'
            onClick={() => !this.isPackUp && this.handleExpandPanel()}
          >
            {this.showExpand ? (
              <span class='collapse-expand'>
                <i class={['bk-icon icon-play-shape', { 'icon-rotate': this.expand }]} />
              </span>
            ) : undefined}
            <span class='title'>{this.title}</span>
            {this.$slots.titleRight}
            {this.subtitle ? <span class='subtitle ml10'>{`(${this.subtitle})`}</span> : undefined}
            {this.$slots.tools && !this.readonly && <span class='header-tool'>{this.$slots.tools}</span>}
          </div>
        </div>
        <div
          style={{ display: this.expand ? 'block' : 'none' }}
          class='anomaly-detection-content'
        >
          {this.$slots.default}
          {this.readonly && <div class='content-readonly' />}
        </div>
      </div>
    );
  }
}
