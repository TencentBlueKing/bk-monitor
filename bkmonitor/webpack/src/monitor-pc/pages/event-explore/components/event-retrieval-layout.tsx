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
import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import MonitorDrag, { type ThemeType } from 'fta-solutions/pages/event/monitor-drag';

import './event-retrieval-layout.scss';

export type CloseTheme = 'button' | 'icon';
export interface EventRetrievalLayoutProps {
  defaultShow?: boolean;
  minWidth?: number;
  maxWidth?: number;
  defaultWidth?: number;
  lineTheme?: ThemeType;
  closeTheme?: CloseTheme;
}

interface EventRetrievalLayoutEvents {
  onShowChange(val: boolean): void;
}

@Component
export default class EventRetrievalLayout extends tsc<EventRetrievalLayoutProps, EventRetrievalLayoutEvents> {
  @Prop({ default: true }) defaultShow: boolean;
  @Prop({ default: 120 }) minWidth: number;
  @Prop({ default: 400 }) maxWidth: number;
  @Prop({ default: 200 }) defaultWidth: number;
  @Prop({ default: 'simple-line-round' }) lineTheme: ThemeType;
  @Prop({ default: 'icon' }) closeTheme: CloseTheme;

  isShow = true;
  width = 200;

  handleDragChange(width: number) {
    if (width < this.minWidth) {
      this.handleClickShrink(false);
    } else {
      this.width = width;
    }
  }

  handleClickShrink(val?: boolean) {
    this.isShow = val ?? !this.isShow;
    this.width = this.isShow ? this.defaultWidth : 0;
    this.$emit('onShowChange', this.isShow);
  }

  mounted() {
    this.width = this.defaultWidth;
    this.isShow = this.defaultShow;
  }

  renderTriggerDrag() {
    if (this.closeTheme === 'button' || this.isShow) {
      return (
        <MonitorDrag
          isShow={this.isShow}
          lineText={this.closeTheme === 'icon' ? '' : this.$tc('展开')}
          maxWidth={this.maxWidth}
          minWidth={this.minWidth}
          startPlacement='right'
          theme={this.lineTheme}
          onMove={this.handleDragChange}
          onTrigger={() => this.handleClickShrink()}
        />
      );
    }
    return (
      <div
        class='expand-trigger'
        v-bk-tooltips={{ content: this.$t('展开') }}
        onClick={() => this.handleClickShrink(true)}
      >
        <i class='icon-monitor icon-gongneng-shouqi' />
      </div>
    );
  }

  render() {
    return (
      <div class='event-retrieval-layout-comp'>
        <div class='layout-aside'>
          <div
            style={{ width: `${this.width}px` }}
            class='layout-aside-content'
          >
            {this.$slots.aside}
          </div>

          {this.renderTriggerDrag()}
        </div>
        <div class='layout-main'>{this.$slots.default}</div>
      </div>
    );
  }
}
