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

import type { MetricPopoverEvents, MetricPopoverProps } from './typings';

import './metric-popover.scss';

/**
 * 指标选择器弹层
 */
@Component
export default class MetricPopover extends tsc<MetricPopoverProps, MetricPopoverEvents> {
  /** 触发对象id */
  @Prop({ type: String }) targetId: string;
  /** 显隐状态 */
  @Prop({ type: Boolean, default: false }) show: boolean;
  /** 弹层内容区域 */
  @Ref() metricSelectorPopover: HTMLElement;
  /* 宽度 */
  @Prop({ type: Number, default: 558 }) width: number;

  /** 弹层实例 */
  popoverInstance = null;

  @Watch('show')
  handleShow(val: boolean) {
    val ? this.handleDropDownShow() : this.handleDropDownHide();
  }
  /**
   * @description: 注册条件弹层
   * @param {*} target 触发的目标
   */
  registerDropDown() {
    const target = document.querySelector(this.targetId);
    this.popoverInstance = this.$bkPopover(target, {
      content: this.metricSelectorPopover,
      trigger: 'manual',
      placement: 'bottom-start',
      theme: 'light common-monitor',
      arrow: false,
      // hideOnClick: false,
      interactive: true,
      boundary: 'window',
      // offset: -1,
      distance: 20,
      zIndex: 9999,
      animation: 'slide-toggle',
      followCursor: false,
      onHidden: () => {
        this.destroyPopoverInstance();
        this.handleShowChange(false);
      },
    });
    // this.curTarget = target;
  }
  /**
   * @description: 显示添加条件弹层
   * @param {HTMLElement} target 出发弹层的目标元素
   */
  async handleDropDownShow() {
    // if (target.isSameNode(this.target)) return this.handleDropDownHide();
    this.destroyPopoverInstance();
    this.registerDropDown();
    await this.$nextTick();
    this.popoverInstance?.show();
  }

  // 清除popover实例
  destroyPopoverInstance() {
    this.popoverInstance?.hide?.();
    this.popoverInstance?.destroy?.();
    this.popoverInstance = null;
  }

  /**
   * @description: 隐藏添加条件弹层
   */
  handleDropDownHide() {
    this.popoverInstance?.hide?.();
  }

  @Emit('showChange')
  handleShowChange(val: boolean) {
    return val;
  }
  render() {
    return (
      <div style={{ display: 'none' }}>
        <div
          ref='metricSelectorPopover'
          style={{ width: `${this.width}px` }}
          class='metric-selector-popover'
        >
          {this.$slots.default}
        </div>
      </div>
    );
  }
}
