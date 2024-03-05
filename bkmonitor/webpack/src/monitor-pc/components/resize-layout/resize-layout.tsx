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

import './resize-layout.scss';
/** 侧栏默认高度 */
export const ASIDE_DEFAULT_HEIGHT = 280;
/** 侧栏收起高度 */
export const ASIDE_COLLAPSE_HEIGHT = 40;

interface IProps {
  min?: number;
  max?: number;
  disabled?: boolean;
  default?: number;
  placement?: string;
  toggleBefore?: () => boolean;
}
export interface IUpdateHeight {
  mainHeight: number;
  asideHeight: number;
}
interface IEvents {
  onTriggerMin: IUpdateHeight;
  onUpdateHeight: IUpdateHeight;
  onResizing: IUpdateHeight;
  onTogglePlacement: string;
}
@Component
export default class MonitorResizeLayout extends tsc<IProps, IEvents> {
  /** 侧栏最小值 */
  @Prop({ type: Number }) min: number;
  /** 侧栏最大值 */
  @Prop({ type: Number }) max: number;
  /** 是否禁止拖动 */
  @Prop({ type: Boolean }) disabled: boolean;
  /** 初始化侧栏的值 */
  @Prop({ type: Number, default: ASIDE_DEFAULT_HEIGHT }) default: number;
  /** 侧栏位置 */
  @Prop({ type: String, default: 'bottom' }) placement: number;
  /** 切换视角前置回调 返回boolean决定是否继续切换视角 */
  @Prop({ type: Function }) toggleBefore: () => boolean;
  @Ref() bkResizeLayoutRef: any;

  /** 侧栏位置 */
  localPlacement = 'bottom';

  /** 侧栏高度 */
  asideHeight = ASIDE_DEFAULT_HEIGHT;

  /** 是否需要开启收起侧栏的动画 */
  needAnimation = false;

  /** 拖动状态 */
  isResizing = false;

  /** 主要内容高度 */
  get mainHeight() {
    return this.$el.clientHeight - this.asideHeight;
  }

  created() {
    this.initDefaultHeight();
  }

  mounted() {
    this.handleAfterResize();
  }

  @Watch('placement', { immediate: true })
  placementChange(val) {
    this.localPlacement = val;
  }

  /**
   * 初始化默认值
   * @returns void
   */
  initDefaultHeight() {
    // if (!this.default) return;
    this.asideHeight = this.default;
  }

  /** 更新侧栏位置 供组件外部调用*/
  async updateAside({ height }: { height: number }, enableAnimation = true) {
    enableAnimation && (this.needAnimation = true);
    await this.$nextTick();
    const asideEl = this.bkResizeLayoutRef.$el.querySelector('.bk-resize-layout-aside');
    asideEl.style.height = `${height}px`;
    this.asideHeight = height;
    this.handleAfterResize();
    enableAnimation &&
      setTimeout(() => {
        this.needAnimation = false;
      }, 200);
  }

  /** 切换视角 */
  @Emit('togglePlacement')
  handleTogglePlacement() {
    this.localPlacement = this.localPlacement === 'top' ? 'bottom' : 'top';
    this.updateAside({ height: this.mainHeight }, false);
    this.asideHeight = this.mainHeight;
    this.handleAfterResize();
    return this.localPlacement;
  }
  /**
   * 切换视角的前置校验
   */
  handleToggleBefore() {
    if (this.toggleBefore) {
      this.toggleBefore() && this.handleTogglePlacement();
    } else {
      this.handleTogglePlacement();
    }
  }
  /**
   * 拖拽事件
   * @param height 侧栏高度
   */
  @Emit('resizing')
  handleResizing(height: number) {
    this.asideHeight = height;
    this.isResizing = true;
    if (this.min && height <= this.min + 3) {
      this.handleMinEmit();
    }
    return {
      mainHeight: this.mainHeight,
      asideHeight: this.asideHeight
    };
  }

  /** 触发最小值 */
  @Emit('triggerMin')
  handleMinEmit() {
    return {
      mainHeight: this.mainHeight,
      asideHeight: this.min
    };
  }

  /**
   * 拖拽完成触发
   * 对外返回主要内容区域、侧栏区域的高度
   */
  @Emit('updateHeight')
  handleAfterResize() {
    this.isResizing = false;
    return {
      mainHeight: this.mainHeight,
      asideHeight: this.asideHeight
    };
  }

  render() {
    return (
      <bk-resize-layout
        ref='bkResizeLayoutRef'
        class={[
          'resize-layout-wrapper',
          this.localPlacement,
          {
            animation: this.needAnimation,
            'is-resizing': this.isResizing
          }
        ]}
        style='height: 100%'
        collapsible
        immediate
        disabled={this.disabled}
        min={this.min}
        max={this.max}
        placement={this.localPlacement}
        initial-divide={this.default}
        onResizing={this.handleResizing}
        on-after-resize={this.handleAfterResize}
      >
        <div
          slot='collapse-trigger'
          class='toggle-wrap'
        >
          {['top', 'bottom'].includes(this.localPlacement) && (
            <span
              class='toggle-btn'
              v-bk-tooltips={this.$tc('切换视角')}
              onClick={this.handleToggleBefore}
            >
              <i class='icon-monitor icon-switch'></i>
            </span>
          )}
        </div>
        <div
          slot='main'
          class='resize-main'
        >
          {this.$slots.main}
        </div>
        <div
          slot='aside'
          class='resize-aside'
        >
          {this.$slots.aside}
        </div>
      </bk-resize-layout>
    );
  }
}
