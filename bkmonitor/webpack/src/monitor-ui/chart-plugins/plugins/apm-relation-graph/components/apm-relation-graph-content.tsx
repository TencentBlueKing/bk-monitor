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

const sideTopoMinWidth = 480;
const sideOverviewMinWidth = 400;

interface IProps {
  expanded?: string[];
}
@Component
export default class ApmRelationGraphContent extends tsc<IProps> {
  @Prop({ type: Array, default: () => [] }) expanded: string[];
  /* 侧栏拖拽 */
  oldWidth = 0;
  isMouseenter = false;
  isDrop = false;
  downPageX = 0;
  sideTopoWidth = sideTopoMinWidth;
  sideOverviewWidth = sideOverviewMinWidth;
  dropType = '';
  hoverType = '';

  get onlyOverview() {
    return this.expanded.length === 1 && this.expanded[0] === 'overview';
  }

  @Watch('expanded', { immediate: true })
  handleWatchExpanded(newVal: string[]) {
    this.sideOverviewWidth = newVal.includes('overview') ? this.sideOverviewWidth || sideOverviewMinWidth : 0;
    this.sideTopoWidth = newVal.includes('topo') ? this.sideTopoWidth || sideTopoMinWidth : 0;
  }

  /* 侧栏拖转 ---start----- */
  handleContentMouseleave() {
    this.isMouseenter = false;
    this.isDrop = false;
  }
  handleSideMousemove(event) {
    if (this.isDrop) {
      const width = this.oldWidth + (this.downPageX - event.pageX);
      if (this.dropType === 'overview') {
        if (width < sideOverviewMinWidth) {
          this.sideOverviewWidth = sideOverviewMinWidth;
        }
        this.sideOverviewWidth = width;
      }
      if (this.dropType === 'topo') {
        if (width < sideTopoMinWidth) {
          this.sideTopoWidth = sideTopoMinWidth;
        }
        this.sideTopoWidth = width;
      }
    }
  }
  handleSideMouseup() {
    this.dropType = '';
    this.isDrop = false;
    this.isMouseenter = false;
    this.downPageX = 0;
  }

  handleSideMouseenter(type) {
    this.isMouseenter = true;
    this.hoverType = type;
  }
  handleSideMouseleave() {
    if (!this.isDrop) {
      this.isMouseenter = false;
    }
    this.hoverType = '';
  }
  handleSideMouseDown(event, type) {
    this.dropType = type;
    this.isDrop = true;
    this.downPageX = event.pageX;
    if (type === 'topo') {
      this.oldWidth = this.$el.querySelector('.side1______').clientWidth;
    } else {
      this.oldWidth = this.$el.querySelector('.side2______').clientWidth;
    }
  }

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
          <div
            style={{
              'min-width': `${sideTopoMinWidth}px`,
              width: `${this.sideTopoWidth}px`,
              display: this.sideTopoWidth ? 'block' : 'none',
            }}
            class={[
              'side-topo side-content side1______',
              { 'drop-active': (this.isMouseenter && this.dropType === 'topo') || this.hoverType === 'topo' },
            ]}
          >
            <div
              class='side-drop-wrap'
              onMousedown={e => this.handleSideMouseDown(e, 'topo')}
              onMouseenter={() => this.handleSideMouseenter('topo')}
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
            {this.$slots?.side1}
          </div>
          <div
            style={{
              'min-width': `${sideOverviewMinWidth}px`,
              width: `${this.sideOverviewWidth}px`,
              display: this.sideOverviewWidth ? 'block' : 'none',
            }}
            class={[
              'side-overview side-content side2______',
              { 'drop-active': (this.isMouseenter && this.dropType === 'overview') || this.hoverType === 'overview' },
            ]}
          >
            <div
              class='side-drop-wrap'
              onMousedown={e => this.handleSideMouseDown(e, 'overview')}
              onMouseenter={() => this.handleSideMouseenter('overview')}
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
            {this.$slots?.side2}
          </div>
        </div>
      </div>
    );
  }
}
