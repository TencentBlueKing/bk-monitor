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
import { Component, Emit, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { Debounce } from 'monitor-common/utils/utils';

import { resize } from '../../components/ip-selector/common/observer-directive';

import type { VNode } from 'vue';

import './collapse.scss';

export interface ICollapseProps {
  expand: boolean;
  defaultHeight?: number;
  renderContent?: boolean;
  needCloseButton?: boolean;
  maxHeight?: number;
  renderAnimation?: boolean;
}
export interface ICollapseEvents {
  onExpandChange: boolean;
  onOverflow: boolean;
}
/**
 * 提供根据内容多少展开折叠的能力
 */
@Component({
  directives: {
    resize,
  },
})
export default class Collapse extends tsc<ICollapseProps, ICollapseEvents> {
  /** 展开状态 */
  @Prop({ default: false, type: Boolean }) expand: boolean;
  /** 收起的默认高度 */
  @Prop({ default: 0, type: Number }) defaultHeight: number;
  /** 展开的最大高度 */
  @Prop({ type: Number }) maxHeight: number;
  /** 未展开是否渲染content */
  @Prop({ default: true, type: Boolean }) renderContent: boolean;
  /** 是否需要关闭按钮 */
  @Prop({ default: true, type: Boolean }) needCloseButton: boolean;
  /** 渲染就开启动画 */
  @Prop({ default: true, type: Boolean }) renderAnimation: boolean;
  /** 内容区域 */
  @Ref() collapseContentRef: HTMLElement;

  /** 高度 */
  height = 0;

  /** 最大高度 */
  localMaxHeight = 0;

  /** 是否渲染content */
  showContent = false;

  /** 是否允许溢出滚动 */
  isOverflow = false;

  openAnimation = false;

  created() {
    // this.height = null;
    this.defaultHeight && (this.localMaxHeight = this.defaultHeight);
    if (this.renderAnimation) {
      this.openAnimation = true;
    } else {
      setTimeout(() => {
        this.openAnimation = true;
      }, 50);
    }
  }

  mounted() {
    this.$el.addEventListener('transitionend', this.handleTransitionend);
    if (this.expand) {
      this.$nextTick(() => this.updateHeight(this.expand));
    }
    this.checkOverflow();
  }

  beforeDestroy() {
    this.$el.removeEventListener('transitionend', this.handleTransitionend);
  }

  @Watch('expand', { immediate: true })
  expandChange(val: boolean) {
    this.isOverflow = false;
    if (this.renderContent || (!this.renderContent && val)) this.showContent = val;
    this.renderContent ? this.updateHeight(val) : this.$nextTick(() => this.updateHeight(val));
    !val && this.$el?.scrollTo?.(0, 0);
  }

  /**
   * @description: 监听动画结束
   * @param {TransitionEvent} evt
   */
  handleTransitionend(evt: TransitionEvent) {
    if (evt.propertyName === 'height' && evt.target === this.$el) {
      if (!this.expand) {
        this.showContent = this.expand;
      }
      this.isOverflow = this.expand;
    }
  }

  /**
   * @description: 更新高度
   * @param {boolean} val 展开状态
   */
  updateHeight(val: boolean) {
    this.localMaxHeight = this.maxHeight;
    const contentHeight = this.collapseContentRef?.scrollHeight;
    this.height = val ? contentHeight : contentHeight < this.defaultHeight ? contentHeight : this.defaultHeight;
    !!this.localMaxHeight && val && this.height > this.localMaxHeight && (this.height = this.localMaxHeight);
  }

  /** 对外暴露更新内容区域高度的方法 */
  handleContentResize() {
    this.expand && this.updateHeight(true);
  }

  /**
   * @description: 渲染内容区域
   * @return {VNode[]}
   */
  handleRenderContent(): VNode[] {
    if (this.renderContent) {
      return this.$slots.default;
    }
    return this.showContent ? this.$slots.default : undefined;
  }

  handleRenderCloseBtn() {
    if (!this.needCloseButton) return undefined;
    const tpl = (
      <i
        class={['monitor-collapse-close icon-monitor icon-mc-triangle-down', { 'is-expand': this.showContent }]}
        onClick={this.handleClickClose}
      />
    );
    if (this.renderContent) {
      return tpl;
    }
    return this.showContent ? tpl : undefined;
  }
  @Emit('expandChange')
  handleClickClose() {
    return !this.showContent;
  }

  @Emit('overflow')
  checkOverflow() {
    const isOverflow = this.collapseContentRef?.scrollHeight > this.defaultHeight;
    this.isOverflow = isOverflow;
    return isOverflow;
  }

  @Debounce(300)
  handleResize() {
    console.log(this.height);
    this.$nextTick(() => this.updateHeight(this.expand));
    this.checkOverflow();
  }

  render() {
    return (
      <div
        style={{ height: `${this.height}px` }}
        class={['monitor-collapse-wrap', { 'is-overflow': this.isOverflow, animation: this.openAnimation }]}
        v-resize={this.handleResize}
      >
        <div
          ref='collapseContentRef'
          class='monitor-collapse-content'
        >
          {this.handleRenderContent()}
        </div>
        {this.handleRenderCloseBtn()}
      </div>
    );
  }
}
