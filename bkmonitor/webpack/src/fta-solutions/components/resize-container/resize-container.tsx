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

import './resize-container.scss';

interface IResizeContainer {
  height?: number;
  maxHeight?: number;
  maxWidth?: number;
  minHeight?: number;
  minWidth?: number;
  width?: number;
}

@Component
export default class ResizeContainer extends tsc<IResizeContainer> {
  @Prop({ default: null, type: Number }) width: number;
  @Prop({ default: null, type: Number }) maxWidth: number;
  @Prop({ default: null, type: Number }) minWidth: number;
  @Prop({ default: null, type: Number }) height: number;
  @Prop({ default: null, type: Number }) maxHeight: number;
  @Prop({ default: null, type: Number }) minHeight: number;
  @Prop({ default: '', type: String }) placeholder: string;

  resize = {
    startClientX: 0,
    startClientY: 0,
    width: null,
    height: null,
  };

  @Watch('width', { immediate: true })
  widthChange() {
    this.resize.width = this.width;
  }
  @Watch('height', { immediate: true })
  heightChange() {
    this.resize.height = this.height;
  }

  created() {
    this.minHeight && !this.height && (this.resize.height = this.minHeight);
    this.maxWidth && !this.width && (this.resize.width = this.maxWidth);
  }

  // 限制宽度
  widthRange(width: number): number {
    const min = this.minWidth;
    const max = this.maxWidth;
    width = min && width <= min ? min : width;
    width = max && width >= max ? max : width;
    return width;
  }

  // 限制高度
  heightRange(height: number): number {
    const min = this.minHeight;
    const max = this.maxHeight;
    height = min && height <= min ? min : height;
    height = max && height >= max ? max : height;
    return height;
  }

  handleMouseDown(e: MouseEvent) {
    this.resize.startClientX = e.clientX;
    this.resize.startClientY = e.clientY;
    document.addEventListener('mousemove', this.handleMousemove, false);
    document.addEventListener('mouseup', this.handleMouseup, false);
  }
  handleMousemove(e: MouseEvent) {
    if (this.resize.startClientX === 0) return;
    if (this.resize.width === null) {
      const wrapEl = this.$el;
      this.resize.width = wrapEl.clientWidth;
      this.resize.height = wrapEl.clientHeight;
    }
    const offsetX = e.clientX - this.resize.startClientX;
    const offsetY = e.clientY - this.resize.startClientY;
    this.resize.startClientX = e.clientX;
    this.resize.startClientY = e.clientY;
    this.resize.width = this.widthRange(this.resize.width + offsetX);
    this.resize.height = this.heightRange(this.resize.height + offsetY);
  }
  handleMouseup() {
    this.resize.startClientX = 0;
    this.resize.startClientY = 0;
    document.removeEventListener('mousemove', this.handleMousemove, false);
    document.removeEventListener('mouseup', this.handleMousemove, false);
  }

  protected render() {
    return (
      <div
        style={{
          width: `${this.resize.width}px`,
          height: `${this.resize.height}px`,
        }}
        class='resize-container-wrap'
      >
        <div class='resize-container-content'>{this.$slots.default}</div>
        <div
          class='resize-wrap'
          onMousedown={this.handleMouseDown}
          onMousemove={this.handleMousemove}
          onMouseup={this.handleMouseup}
        >
          <i class='resize-icon-inner' />
          <i class='resize-icon-wrap' />
        </div>
      </div>
    );
  }
}
