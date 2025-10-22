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

import { Component, Emit, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { BATCH_OPERATION_LIST } from '../../constant';

import type { BatchOperationTypeEnumType } from '../../typing';

import './batch-operations.scss';

interface BatchOperationsEvents {
  /** 菜单点击事件 */
  onOperationClick: (operationType: BatchOperationTypeEnumType) => void;
}

interface BatchOperationsProps {
  /** 是否禁用 批量操作 按钮 */
  disabled: boolean;
}

@Component
export default class BatchOperations extends tsc<BatchOperationsProps, BatchOperationsEvents> {
  /** 批量操作列表dom实例 */
  @Ref('batchMenuRef') batchMenuRef: HTMLDivElement;

  /** 是否禁用 批量操作 按钮 */
  @Prop({ type: Boolean, default: false }) disabled: boolean;

  /** popover 实例 */
  popoverInstance = null;
  /** popover 延迟打开定时器 */
  popoverDelayTimer = null;

  /**
   * @description: 监听 disabled  变化
   */
  @Watch('disabled')
  handleDisabledChange() {
    if (!this.disabled) return;
    this.handlePopoverHide();
  }

  /**
   * @description: 批量操作点击事件
   */
  @Emit('operationClick')
  handleOperationClick(operationType: BatchOperationTypeEnumType) {
    this.handlePopoverHide();
    return operationType;
  }

  /**
   * @description: 展开
   * @param {MouseEvent} e
   * @param {string} content
   */
  handlePopoverShow(e: MouseEvent) {
    if (this.disabled) return;
    if (this.popoverInstance || this.popoverDelayTimer) {
      this.handlePopoverHide();
      return;
    }
    this.popoverInstance = this.$bkPopover(e.currentTarget, {
      content: this.batchMenuRef,
      animation: false,
      maxWidth: 'none',
      arrow: false,
      trigger: 'click',
      boundary: 'window',
      placement: 'bottom',
      interactive: true,
      distance: 14,
      theme: 'light padding-0 apm-alarm-template-batch-operations',
      onHidden: () => {
        this.handlePopoverHide();
      },
    });
    const target = e.currentTarget;
    const popoverCache = this.popoverInstance;
    this.popoverDelayTimer = setTimeout(() => {
      if (popoverCache === this.popoverInstance && target && document.body.contains(target as Node)) {
        this.popoverInstance?.show?.(0);
      } else {
        popoverCache?.hide?.(0);
        popoverCache?.destroy?.();
      }
    }, 200);
  }

  /**
   * @description: 清除popover
   */
  handlePopoverHide() {
    this.handleClearTimer();
    this.popoverInstance?.hide?.(0);
    this.popoverInstance?.destroy?.();
    this.popoverInstance = null;
  }

  /**
   * @description: 清除popover延时打开定时器
   *
   */
  handleClearTimer() {
    this.popoverDelayTimer && clearTimeout(this.popoverDelayTimer);
    this.popoverDelayTimer = null;
  }

  render() {
    return (
      <div
        class={`batch-operations ${this.disabled ? 'is-disabled' : ''}`}
        onClick={this.handlePopoverShow}
      >
        <div
          class='tip-trigger'
          v-bk-tooltips={{ content: this.$t('请先选择模版'), disabled: !this.disabled }}
        >
          <span class='batch-operations-name'> {this.$t('批量操作')} </span>
          <i class={`icon-monitor icon-arrow-down ${this.popoverInstance ? 'is-active' : ''}`} />
        </div>
        <div style='display: none'>
          <ul
            ref='batchMenuRef'
            class='batch-menu-list'
          >
            {BATCH_OPERATION_LIST.map(item => (
              <li
                key={item.id}
                class='batch-menu-item'
                onClick={() => this.handleOperationClick(item.id)}
              >
                {item.name}
              </li>
            ))}
          </ul>
        </div>
      </div>
    );
  }
}
