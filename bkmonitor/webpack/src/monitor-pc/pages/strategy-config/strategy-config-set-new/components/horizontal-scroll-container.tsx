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
import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './horizontal-scroll-container.scss';

interface IProps {
  isWatchWidth?: boolean;
  smallBtn?: boolean;
}

@Component
export default class HorizontalScrollContainer extends tsc<IProps> {
  @Prop({ type: Boolean, default: false }) isWatchWidth: boolean;
  @Prop({ type: Boolean, default: false }) smallBtn: boolean;
  hasScroll = false;
  timer = null;
  running = false;

  canNext = false;
  canPre = false;

  resizeObserver = null;

  mounted() {
    if (this.isWatchWidth) {
      this.resizeObserver = new ResizeObserver(() => {
        this.handleWatchScroll();
      });
      const scrollEl: HTMLDivElement = this.$el.querySelector('.scroll-container');
      this.resizeObserver.observe(scrollEl);
    }
    this.handleWatchScroll();
  }

  destroyed() {
    this.resizeObserver?.disconnect?.();
  }

  handleWatchScroll() {
    const scrollEl: HTMLDivElement = this.$el.querySelector('.scroll-container');
    this.hasScroll = scrollEl.scrollWidth > scrollEl.clientWidth;
    this.canNext = true;
  }

  handleClick(type: 'pre' | 'next') {
    if (this.running) return;
    let course = 120;
    const speed = 5;
    const time = 10;
    const scrollEl: HTMLDivElement = this.$el.querySelector('.scroll-container');
    const remnantWidth = scrollEl.scrollWidth - scrollEl.clientWidth;
    if (type === 'pre') {
      this.timer = setInterval(() => {
        if (course === 0 || Math.ceil(scrollEl.scrollLeft) === 0) {
          this.running = false;
          this.statusChange();
          clearInterval(this.timer);
        } else {
          this.running = true;
          if (scrollEl.scrollLeft < speed) {
            scrollEl.scrollLeft = 0;
          } else {
            scrollEl.scrollLeft -= speed;
            course -= speed;
          }
        }
      }, time);
    } else {
      this.timer = setInterval(() => {
        if (course === 0 || Math.ceil(scrollEl.scrollLeft) === remnantWidth) {
          this.running = false;
          this.statusChange();
          clearInterval(this.timer);
        } else {
          this.running = true;
          if (remnantWidth - scrollEl.scrollLeft < speed) {
            scrollEl.scrollLeft = remnantWidth;
          } else {
            scrollEl.scrollLeft += speed;
            course -= speed;
          }
        }
      }, time);
    }
  }

  statusChange() {
    const scrollEl: HTMLDivElement = this.$el.querySelector('.scroll-container');
    this.canNext = !(Math.ceil(scrollEl.scrollLeft) + scrollEl.clientWidth === scrollEl.scrollWidth);
    this.canPre = !(Math.ceil(scrollEl.scrollLeft) === 0);
  }

  render() {
    return (
      <div
        class={[
          'horizontal-scroll-container',
          { 'has-scroll': this.hasScroll },
          { 'small-btn': this.smallBtn && this.hasScroll }
        ]}
      >
        <div class='scroll-container'>{this.$slots?.default}</div>
        {this.hasScroll && (
          <div
            class={['pre', { disabled: !this.canPre }]}
            onClick={() => this.handleClick('pre')}
          >
            <span class='icon-monitor icon-arrow-left'></span>
          </div>
        )}
        {this.hasScroll && (
          <div
            class={['next', { disabled: !this.canNext }]}
            onClick={() => this.handleClick('next')}
          >
            <span class='icon-monitor icon-arrow-right'></span>
          </div>
        )}
      </div>
    );
  }
}
