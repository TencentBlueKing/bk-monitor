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
import { Component, Emit, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './side-slider.scss';

const DEFAULT_WIDTH = 0;
const EXPAND_WIDTH = 400;

export interface IWidthValue {
  animation: boolean;
  val: number;
}

interface IEvent {
  onWidthChange?: (emitValue: IWidthValue) => void;
}

@Component
export default class SideSlider extends tsc<IEvent> {
  width = DEFAULT_WIDTH;
  maxWidth = 800;
  minWidth = 100;
  startClientX = 0;

  /** 是否开启动画 */
  enableAnimation = false;

  get isShowSideSlider() {
    return !!this.width;
  }

  @Watch('width')
  watchWidthChange(val: number) {
    this.handleWidthChange(val);
  }

  @Emit('widthChange')
  handleWidthChange(val: number) {
    const emitValue: IWidthValue = {
      val,
      animation: this.enableAnimation,
    };
    return emitValue;
  }

  handleShowSideSlider() {
    this.enableAnimation = true;
    this.width = this.width > 0 ? DEFAULT_WIDTH : EXPAND_WIDTH;
  }

  handleMousedown(evt) {
    document.onselectstart = () => false;
    document.ondragstart = () => false;
    this.enableAnimation = false;
    this.startClientX = evt.clientX;
    this.handleAddMouseMove();
  }

  handleMouseup() {
    this.handleRemoveMouseMove();
    document.removeEventListener('mouseup', this.handleMouseup, false);
    document.onselectstart = null;
    document.ondragstart = null;
  }

  handleMouseMove(evt) {
    const { clientX } = evt;
    let width = this.width + (this.startClientX - clientX);
    width = Math.max(this.minWidth, Math.min(this.maxWidth, width));
    this.width = width === this.minWidth ? 0 : width;
    this.startClientX = clientX;
  }

  handleAddMouseMove() {
    document.addEventListener('mousemove', this.handleMouseMove, false);
    document.addEventListener('mouseup', this.handleMouseup, false);
  }
  handleRemoveMouseMove() {
    document.removeEventListener('mousemove', this.handleMouseMove, false);
  }
  render() {
    return (
      <div
        style={{ width: `${this.width}px` }}
        class={['side-slider-wrap', { animation: this.enableAnimation }]}
      >
        <span
          class='slider-drag-btn'
          onMousedown={this.handleMousedown}
        />
        <span
          class={['side-slider-btn', { 'is-hidden': !this.isShowSideSlider }]}
          onClick={this.handleShowSideSlider}
        >
          <span class='side-slider-btn-text'>{this.$t('插件说明')}</span>
          <i class='icon-monitor icon-arrow-right' />
        </span>
        <div class='side-slider-content'>{this.$slots.default}</div>
      </div>
    );
  }
}
