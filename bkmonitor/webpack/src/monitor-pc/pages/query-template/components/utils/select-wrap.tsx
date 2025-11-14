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

import { Component, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { xssFilter } from 'monitor-common/utils';

import './select-wrap.scss';

interface IProps {
  backgroundColor?: string;
  expanded?: boolean;
  id?: string;
  loading?: boolean;
  minWidth?: number;
  needClear?: boolean;
  needPop?: boolean;
  popClickHide?: boolean;
  popOffset?: number;
  showPop?: boolean;
  tips?: string;
  tipsPlacements?: string[];
  onClear?: () => void;
  onClick?: (e: Event) => void;
  onOpenChange?: (v: boolean) => void;
}

@Component
export default class SelectWrap extends tsc<IProps> {
  /* 是否展开 */
  @Prop({ default: false }) expanded: boolean;
  /* 最小宽度 */
  @Prop({ default: 127 }) minWidth: number;
  /* 背景颜色 */
  @Prop({ default: '#fff' }) backgroundColor: string;
  /* dom id */
  @Prop({ default: '' }) id: string;
  /* 是否显示loading */
  @Prop({ default: false }) loading: boolean;
  /* 提示内容 */
  @Prop({ default: '' }) tips: string;
  /* 提示位置 */
  @Prop({ default: () => ['top'], type: Array }) tipsPlacements: string[];
  /* 是否需要点击触发popover */
  @Prop({ default: false }) needPop: boolean;
  /* 点击popover外部是否隐藏 */
  @Prop({ default: true }) popClickHide: boolean;
  /* 是否展示popover */
  @Prop({ default: false }) showPop: boolean;
  /* 弹出层偏移量 */
  @Prop({ default: 0 }) popOffset: number;
  /* 是否需要清空 */
  @Prop({ default: false }) needClear: boolean;

  @Ref('pop') popRef: HTMLElement;

  popoverInstance = null;
  isShowPop = false;

  outSideClean = null;

  isHover = false;

  beforeDestroy() {
    this.popoverDestroy();
  }

  @Watch('expanded')
  handleWatchShowPop(val) {
    if (!val && this.needPop) {
      this.popoverDestroy();
    }
  }

  handleClick(e) {
    if (this.loading) {
      return;
    }
    if (this.needPop) {
      this.handleShowPopover(e);
      return;
    }
    this.$emit('click', e);
  }

  handleShowPopover(e: Event) {
    if (!this.popoverInstance) {
      this.popoverInstance = this.$bkPopover(e.currentTarget, {
        content: this.popRef,
        arrow: false,
        trigger: 'click',
        placement: 'bottom-start',
        theme: 'light common-monitor',
        boundary: 'window',
        interactive: true,
        distance: 4,
        zIndex: 5000,
        offset: this.popOffset,
        onHide: () => {
          return this.popClickHide;
        },
        onHidden: () => {
          this.popoverDestroy();
        },
      });
    }
    this.isShowPop = true;
    this.$emit('openChange', true);
    this.popoverInstance?.show(100);
  }

  popoverDestroy() {
    this.popoverInstance?.hide();
    this.popoverInstance?.destroy();
    this.popoverInstance = null;
    this.isShowPop = false;
    this.$emit('openChange', false);
  }

  handleMouseenter() {
    this.isHover = true;
  }
  handleMouseleave() {
    this.isHover = false;
  }

  handleClear(e: Event) {
    e.stopPropagation();
    this.$emit('clear');
  }

  render() {
    return (
      <div
        id={this.id}
        style={{ minWidth: `${this.minWidth}px`, backgroundColor: this.backgroundColor }}
        class={['template-config-utils-select-wrap-component', { 'input-active': this.expanded }]}
        onClick={e => this.handleClick(e)}
        onMouseenter={this.handleMouseenter}
        onMouseleave={this.handleMouseleave}
      >
        <div
          class='slot-wrap'
          v-bk-tooltips={{
            content: xssFilter(this.tips),
            placements: this.tipsPlacements,
            disabled: !this.tips,
            delay: [300, 0],
            theme: 'tippy-metric',
          }}
        >
          {this.$slots.default || ''}
        </div>

        {this.needClear && this.isHover && !this.expanded ? (
          <div class='clear-wrap'>
            <span
              class='icon-monitor icon-mc-close-fill'
              onClick={this.handleClear}
            />
          </div>
        ) : (
          <div class={['expand-wrap', { active: this.expanded }]}>
            <span class='icon-monitor icon-mc-arrow-down' />
          </div>
        )}
        {this.loading && <div class='select-loading skeleton-element' />}
        <div style={{ display: 'none' }}>
          <div ref='pop'>{this.$slots.popover}</div>
        </div>
      </div>
    );
  }
}
