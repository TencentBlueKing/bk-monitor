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
import { type TippyContent, type TippyOptions, useTippy } from 'vue-tippy';

import { ENABLED_TABLE_DESCRIPTION_HEADER_CLASS_NAME, ENABLED_TABLE_ELLIPSIS_CELL_CLASS_NAME } from '../constants';
import { isEllipsisActiveSingleLine } from '../utils/dom-helper';

import type { PrimaryTable } from '@blueking/tdesign-ui';

export interface UseTablePopoverOptions {
  popoverOptions?: Partial<TippyOptions>;
  getContentOptions: (
    el: HTMLElement,
    event: MouseEvent
  ) => {
    content: PopoverContent;
    popoverTarget?: HTMLElement;
  }; // 自定义内容获取
  // popover 隐藏回调
  onHide?: () => void;
  trigger: {
    /** 延迟触发/防抖 时间 */
    delay?: number;
    /** 需要监听的触发类型（默认为 'mouseenter'） */
    eventType?: PopoverTriggerEventType;
    /** 触发元素 */
    selector: ICSSSelector;
  };
}
type ICSSSelector = string;
type PopoverContent = HTMLElement | JSX.Element | number | string;

type PopoverTriggerEventType = 'click' | 'mouseenter';

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
    switch (options.trigger.eventType) {
      case 'click':
        rootDom.addEventListener('click', handleEventTrigger, true);
        break;
      default:
        rootDom.addEventListener('mouseenter', handleEventTrigger, true);
        rootDom.addEventListener('mouseleave', handleMouseleave, true);
        break;
    }
  };

  /**
   * @description 销毁事件委托监听器
   *
   */
  const destroyDelegationListeners = () => {
    const rootDom = get(delegationRoot)?.$el;
    if (!rootDom) return;
    switch (options.trigger.eventType) {
      case 'click':
        rootDom.removeEventListener('click', handleEventTrigger, true);
        break;
      default:
        rootDom?.removeEventListener?.('mouseenter', handleEventTrigger, true);
        rootDom?.removeEventListener?.('mouseleave', handleMouseleave, true);
        break;
    }
  };

  /**
   * @description 处理鼠标移入事件
   * @param {MouseEvent} e 鼠标事件对象
   *
   */
  const handleEventTrigger = (e: MouseEvent) => {
    if (mouseenterDebouncedTimer) {
      clearTimeout(mouseenterDebouncedTimer);
      mouseenterDebouncedTimer = null;
    }
    // 兼容微前端环境下，e.target 在异步任务中会被置空的场景
    const _target = e.target as HTMLElement;
    const handleFn = () => {
      const targetDom: HTMLElement = _target?.closest?.(options.trigger.selector);
      if (!targetDom) return;

      const { content, popoverTarget } = options.getContentOptions(targetDom, e) || {};

      if (content != null) {
        handlePopoverShow(popoverTarget || targetDom, content as string);
      }
    };
    if (options.trigger.delay === 0) {
      handleFn();
    } else {
      mouseenterDebouncedTimer = setTimeout(() => {
        handleFn();
      }, options.trigger.delay || 200);
    }
  };

  /**
   * @description 处理鼠标移出事件
   * @param {MouseEvent} e 鼠标事件对象
   *
   */
  const handleMouseleave = (e: MouseEvent) => {
    const targetDom = e.target as HTMLElement;
    if (!targetDom.matches(options.trigger.selector)) return;
    clearTimer();
  };

  /**
   * @description 打开 popover 气泡弹窗
   *
   */
  const handlePopoverShow = (target: HTMLElement, content: TippyContent) => {
    if (popoverInstance || popoverDelayTimer) {
      handlePopoverHide();
    }
    popoverInstance = useTippy(target, {
      content: () => content,
      appendTo: () => document.body,
      trigger: options?.trigger?.eventType,
      placement: 'top',
      theme: 'dark max-width-50vw text-wrap',
      arrow: true,
      onHidden: () => {
        options?.onHide?.();
        handlePopoverHide();
      },
      ...options.popoverOptions,
    });
    const popoverCache = popoverInstance;
    popoverDelayTimer = setTimeout(() => {
      if (popoverCache === popoverInstance) {
        popoverInstance?.show?.(0);
      } else {
        popoverCache?.hide?.(0);
        popoverCache?.destroy?.();
      }
    }, 100);
  };

  /**
   * @description 关闭 popover 气泡弹窗
   *
   */
  const handlePopoverHide = () => {
    clearTimer();
    popoverInstance?.hide?.(0);
    popoverInstance?.destroy?.();
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
    handlePopoverShow,
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
  options: Omit<UseTablePopoverOptions, 'getContentOptions'>
) =>
  useTablePopover(delegationRoot, {
    trigger: { selector: options?.trigger?.selector || `.${ENABLED_TABLE_ELLIPSIS_CELL_CLASS_NAME}` },
    getContentOptions: triggerDom => {
      const { isEllipsisActive, content } = isEllipsisActiveSingleLine(triggerDom);
      if (!isEllipsisActive) return;
      return { content };
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
  options: Omit<UseTablePopoverOptions, 'getContentOptions'>
) =>
  useTablePopover(delegationRoot, {
    trigger: { selector: options?.trigger?.selector || `.${ENABLED_TABLE_DESCRIPTION_HEADER_CLASS_NAME}` },
    getContentOptions: triggerDom => {
      const content = triggerDom.dataset.colDescription;
      if (!content) return;
      const { isEllipsisActive } = isEllipsisActiveSingleLine(triggerDom.parentElement);
      return { content, popoverTarget: isEllipsisActive ? triggerDom.parentElement : triggerDom };
    },
    popoverOptions: {
      theme: 'light max-width-50vw text-wrap',
      placement: 'right',
      ...(options?.popoverOptions || {}),
    },
  });
