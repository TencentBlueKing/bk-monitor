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

import { type MaybeRef, onBeforeUnmount } from 'vue';

import { get } from '@vueuse/core';
import { $bkPopover } from 'bkui-vue';

import { isEllipsisActiveSingleLine } from '../utils';

import type { PrimaryTable } from '@blueking/tdesign-ui';
import type { $Popover } from 'bkui-vue/lib/popover/plugin-popover';

type ICSSSelector = string;
type PopoverContent = HTMLElement | JSX.Element | number | string;

export interface UseTablePopoverOptions {
  trigger: { selector: ICSSSelector; delay?: number };
  getContent: (el: HTMLElement, event: MouseEvent) => null | string; // 自定义内容获取
  popoverOptions?: Partial<$Popover>;
}

export const useTablePopover = (
  delegationRoot: MaybeRef<InstanceType<typeof PrimaryTable>>,
  options: UseTablePopoverOptions
) => {
  let popoverInstance = null;
  let mouseenterDebouncedTimer = null;
  let popoverDelayTimer = null;

  onBeforeUnmount(() => {
    handlePopoverHide();
    destroyDelegationListeners();
  });

  /**
   * @description 初始化事件委托监听器
   *
   */
  const initListeners = () => {
    const rootDom = get(delegationRoot)?.$el;
    if (!rootDom) {
      console.trace(
        `Event delegation initialization failed because the 'delegationRoot' was not found. Please verify the element selector or ensure proper DOM loading timing.`
      );
      return;
    }
    rootDom.addEventListener('mouseenter', handleMouseenter, true);
    rootDom.addEventListener('mouseleave', handleMouseleave, true);
  };

  /**
   * @description 销毁事件委托监听器
   *
   */
  const destroyDelegationListeners = () => {
    const rootDom = get(delegationRoot)?.$el;
    if (!rootDom) return;
    rootDom?.removeEventListener?.('mouseenter', handleMouseenter, true);
    rootDom?.removeEventListener?.('mouseleave', handleMouseleave, true);
  };

  /**
   * @description 处理鼠标移入事件
   * @param {MouseEvent} e 鼠标事件对象
   *
   */
  const handleMouseenter = (e: MouseEvent) => {
    handlePopoverHide();
    mouseenterDebouncedTimer = setTimeout(() => {
      const targetDom: HTMLElement = (e.target as HTMLElement).closest(options.trigger.selector);
      if (!targetDom) return;

      const content = options.getContent(targetDom, e);
      if (content != null) {
        handlePopoverShow(targetDom, content as string);
      }
    }, options.trigger.delay || 200);
  };

  /**
   * @description 处理鼠标移出事件
   * @param {MouseEvent} e 鼠标事件对象
   *
   */
  const handleMouseleave = (e: MouseEvent) => {
    const targetDom = e.target as HTMLElement;
    if (!targetDom.matches(options.trigger.selector)) return;
    handlePopoverHide();
  };

  /**
   * @description 打开 popover 气泡弹窗
   *
   */
  const handlePopoverShow = (target: HTMLElement, content: PopoverContent) => {
    handlePopoverHide();
    popoverInstance = $bkPopover({
      target: target,
      content: content,
      trigger: 'click',
      placement: 'top',
      theme: 'dark',
      arrow: true,
      boundary: 'viewport',
      popoverDelay: 0,
      isShow: false,
      always: false,
      disabled: false,
      clickContentAutoHide: false,
      height: '',
      maxWidth: '',
      maxHeight: '',
      renderDirective: 'if',
      allowHtml: false,
      renderType: 'auto',
      padding: 0,
      offset: 0,
      zIndex: 0,
      disableTeleport: false,
      autoPlacement: false,
      autoVisibility: false,
      disableOutsideClick: false,
      disableTransform: false,
      modifiers: [],
      extCls: '',
      referenceCls: '',
      hideIgnoreReference: true,
      componentEventDelay: 0,
      forceClickoutside: false,
      immediate: false,
      // @ts-ignore
      onHide: () => {
        handlePopoverHide();
      },
      ...options.popoverOptions,
    });

    popoverInstance.install();
    popoverDelayTimer = setTimeout(() => {
      popoverInstance?.vm?.show?.();
    }, 100);
  };

  /**
   * @description 关闭 popover 气泡弹窗
   *
   */
  const handlePopoverHide = () => {
    clearTimer();
    popoverInstance?.hide?.();
    popoverInstance?.close?.();
    popoverInstance = null;
  };

  /**
   * @description 清除鼠标移入事件防抖定时器
   *
   */
  const clearTimer = () => {
    clearTimeout(mouseenterDebouncedTimer);
    clearTimeout(popoverDelayTimer);
    mouseenterDebouncedTimer = null;
    popoverDelayTimer = null;
  };

  return {
    handlePopoverHide,
    initListeners,
  };
};

/**
 * @description 表格文本溢出省略弹出popover处理
 *
 */
export const useTableEllipsis = (
  delegationRoot: MaybeRef<InstanceType<typeof PrimaryTable>>,
  options: Omit<UseTablePopoverOptions, 'getContent'>
) =>
  useTablePopover(delegationRoot, {
    trigger: { selector: options?.trigger?.selector || '.explore-text-ellipsis' },
    getContent: triggerDom => {
      const { isEllipsisActive, content } = isEllipsisActiveSingleLine(triggerDom);
      if (!isEllipsisActive) return;
      return content;
    },
    popoverOptions: {
      ...(options?.popoverOptions || {}),
    },
  });

/**
 * @description 表格列描述弹出popover处理
 *
 */
export const useTableHeaderDescription = (
  delegationRoot: MaybeRef<InstanceType<typeof PrimaryTable>>,
  options: Omit<UseTablePopoverOptions, 'getContent'>
) =>
  useTablePopover(delegationRoot, {
    trigger: { selector: options?.trigger?.selector || '.explore-table-header-description' },
    getContent: triggerDom => {
      const content = triggerDom.dataset.colDescription;
      if (!content) return;
      return content;
    },
    popoverOptions: {
      theme: 'light',
      placement: 'right',
      offset: 6,
      ...(options?.popoverOptions || {}),
    },
  });
