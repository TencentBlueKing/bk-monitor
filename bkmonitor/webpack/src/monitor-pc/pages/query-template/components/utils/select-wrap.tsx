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

import { Component, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { xssFilter } from 'monitor-common/utils';

import './select-wrap.scss';

interface IProps {
  active?: boolean;
  backgroundColor?: string;
  id?: string;
  loading?: boolean;
  minWidth?: number;
  needPop?: boolean;
  tips?: string;
  tipsPlacements?: string[];
  onClick?: (e: Event) => void;
  onOpenChange?: (v: boolean) => void;
}

@Component
export default class SelectWrap extends tsc<IProps> {
  @Prop({ default: false }) active: boolean;
  @Prop({ default: 127 }) minWidth: number;
  @Prop({ default: '#fff' }) backgroundColor: string;
  @Prop({ default: '' }) id: string;
  @Prop({ default: false }) loading: boolean;
  @Prop({ default: '' }) tips: string;
  @Prop({ default: () => ['top'], type: Array }) tipsPlacements: string[];
  @Prop({ default: false }) needPop: boolean;

  @Ref('pop') popRef: HTMLElement;

  popoverInstance = null;
  isShowPop = false;

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
        duration: [200, 0],
        distance: 1,
        onHidden: () => {
          this.popoverInstance?.hide();
          this.popoverInstance.destroy();
          this.popoverInstance = null;
          this.isShowPop = false;
          this.$emit('openChange', false);
        },
      });
    }
    this.isShowPop = true;
    this.$emit('openChange', true);
    this.popoverInstance?.show(100);
  }

  render() {
    return (
      <div
        id={this.id}
        style={{ minWidth: `${this.minWidth}px`, backgroundColor: this.backgroundColor }}
        class='template-config-utils-select-wrap-component'
        onClick={e => this.handleClick(e)}
      >
        <div
          class='slot-wrap'
          v-bk-tooltips={{
            content: xssFilter(this.tips),
            placements: this.tipsPlacements,
            disabled: !this.tips,
            delay: [300, 0],
          }}
        >
          {this.$slots.default || ''}
        </div>

        <div class={['expand-wrap', { active: this.active }]}>
          <span class='icon-monitor icon-mc-arrow-down' />
        </div>
        {this.loading && <div class='select-loading skeleton-element' />}
        <div style={{ display: 'none' }}>
          <div ref='pop'>{this.$slots.popover}</div>
        </div>
      </div>
    );
  }
}
