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
import { Component, Emit, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './apm-home-resize-layout.scss';

type IEvent = {
  onCollapseChange: (collapse: boolean) => void;
};

type IProps = {
  initSideWidth?: number;
  isShowCollapse?: boolean;
  maxWidth?: number;
  minWidth?: number;
};

@Component
export default class ApmHomeResizeLayout extends tsc<IProps, IEvent> {
  @Prop({ default: 200 }) initSideWidth: number;
  @Prop({ default: 0 }) minWidth: number;
  @Prop({ default: 200 }) maxWidth: number;
  @Prop({ default: false }) isShowCollapse: boolean;

  @Ref('sideContent') sideContentRef: HTMLDivElement;

  /* 侧栏拖拽 */
  oldWidth = 0;
  isMouseenter = false;
  isDrop = false;
  downPageX = 0;
  sideWidth = 0;

  created() {
    this.sideWidth = this.initSideWidth;
  }

  /* 侧栏拖转 ---start----- */
  handleContentMouseleave() {
    this.isMouseenter = false;
    this.isDrop = false;
  }

  handleSideMousemove(event: MouseEvent) {
    if (this.isDrop) {
      const width = this.oldWidth + event.pageX - this.downPageX;
      if (width < this.minWidth) {
        this.setCollapse(false);
      } else {
        this.sideWidth = width;
      }
    }
  }

  handleSideMouseup() {
    this.isDrop = false;
    this.isMouseenter = false;
    this.downPageX = 0;
  }

  handleSideMouseenter() {
    this.isMouseenter = true;
  }
  handleSideMouseleave() {
    if (!this.isDrop) {
      this.isMouseenter = false;
    }
  }
  handleSideMouseDown(event) {
    this.isDrop = true;
    this.downPageX = event.pageX;
    this.oldWidth = this.sideContentRef.clientWidth;
  }

  @Emit('collapseChange')
  setCollapse(collapse: boolean) {
    if (!collapse) {
      this.sideWidth = 0;
    } else {
      this.sideWidth = this.initSideWidth;
    }
    return collapse;
  }

  render() {
    return (
      <div
        class={['apm-home-resize-layout', { 'col-resize': this.isDrop }]}
        onMouseleave={this.handleContentMouseleave}
        onMousemove={this.handleSideMousemove}
        onMouseup={this.handleSideMouseup}
      >
        <div class='aside-wrap'>
          <div
            ref='sideContent'
            style={{
              width: `${this.sideWidth}px`,
              display: this.sideWidth ? 'block' : 'none',
            }}
            class={['aside-content', { 'drop-active': this.isDrop }]}
          >
            <div
              class='aside-drop-wrap'
              onMousedown={this.handleSideMouseDown}
              onMouseenter={this.handleSideMouseenter}
              onMouseleave={this.handleSideMouseleave}
            >
              <div class='drop-point'>
                {new Array(5).fill(null).map((_, index) => (
                  <div
                    key={index}
                    class='point'
                  />
                ))}
              </div>
            </div>

            {this.$slots?.aside}
          </div>

          {this.isShowCollapse && (
            <i
              class={['bk-icon', 'collapse', this.sideWidth ? 'icon-angle-left' : 'icon-angle-right']}
              onClick={() => this.setCollapse(!this.sideWidth)}
            />
          )}
        </div>
        <div class='main-content'>{this.$slots?.default}</div>
      </div>
    );
  }
}
