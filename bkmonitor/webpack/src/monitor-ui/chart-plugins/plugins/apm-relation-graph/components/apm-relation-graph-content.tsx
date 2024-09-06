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

import './apm-relation-graph-content.scss';

interface IProps {
  expanded?: string[];
}
@Component
export default class ApmRelationGraphContent extends tsc<IProps> {
  @Prop({ type: Array, default: () => [] }) expanded: string[];
  /* 侧栏拖拽 */
  minWidth = 720;
  width = 720;
  oldWidth = 720;
  isMouseenter = false;
  isDrop = false;
  downPageX = 0;

  @Watch('expanded', { immediate: true })
  handleWatchExpanded(newVal: string[]) {
    if (newVal.length) {
      let width = 0;
      for (const key of newVal) {
        if (key === 'overview') {
          width += 320;
        }
        if (key === 'topo') {
          width += 400;
        }
      }
      this.width = width;
      this.minWidth = width;
    } else {
      this.width = 0;
    }
  }

  /* 侧栏拖转 ---start----- */
  handleSideMouseenter() {
    this.isMouseenter = true;
  }
  handleSideMouseleave() {
    if (!this.isDrop) {
      this.isMouseenter = false;
    }
  }
  handleContentMouseleave() {
    this.isMouseenter = false;
    this.isDrop = false;
  }
  handleSideMouseDown(event) {
    this.isDrop = true;
    this.downPageX = event.pageX;
    this.oldWidth = this.width;
  }
  handleSideMousemove(event) {
    if (this.isDrop) {
      const width = this.oldWidth + (this.downPageX - event.pageX);
      if (width < this.minWidth) {
        this.width = this.minWidth;
      } else {
        this.width = this.oldWidth + (this.downPageX - event.pageX);
      }
    }
  }
  handleSideMouseup() {
    this.isDrop = false;
    this.isMouseenter = false;
    this.downPageX = 0;
  }

  setWidth(width) {
    this.width = width;
  }
  setMinWidth(width) {
    this.minWidth = width;
  }

  /* 侧栏拖转 ---end----- */
  render() {
    return (
      <div class='apm-relation-graph-content'>
        <div
          class={['apm-relation-graph-charts', { 'col-resize': this.isDrop }]}
          onMouseleave={this.handleContentMouseleave}
          onMousemove={this.handleSideMousemove}
          onMouseup={this.handleSideMouseup}
        >
          <div class='main-content'>{this.$slots?.default}</div>
          {!!this.width && (
            <div
              style={{
                width: `${this.width}px`,
              }}
              class={['side-content', { 'drop-active': this.isMouseenter }]}
            >
              <div
                class='side-drop-wrap'
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
              {this.$slots?.side}
            </div>
          )}
        </div>
      </div>
    );
  }
}
