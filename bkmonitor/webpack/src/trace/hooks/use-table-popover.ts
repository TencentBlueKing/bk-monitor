/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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

import { isEllipsisActiveLine } from '../utils/dom-helper';

import type { PrimaryTable } from '@blueking/tdesign-ui';

/** 默认溢出 tooltip 单元格类名（通用，非页面专属） */
export const DEFAULT_ELLIPSIS_CELL_CLASS_NAME = 'table-ellipsis-cell';

export interface UseTablePopoverOptions {
  /** popover 配置选项（透传给 vue-tippy） */
  popoverOptions?: Partial<TippyOptions>;
  /** 自定义内容获取函数，根据触发元素和事件返回 popover 内容与目标元素 */
  getContentOptions: (
    el: HTMLElement,
    event: MouseEvent
  ) => {
    content: PopoverContent;
    popoverTarget?: HTMLElement;
  };
  /** popover 隐藏回调 */
  onHide?: () => void;
  /** 触发器配置 */
  trigger: {
    /** 延迟触发/防抖时间（毫秒） */
    delay?: number;
    /** 需要监听的触发类型（默认为 'mouseenter'） */
    eventType?: PopoverTriggerEventType;
    /** CSS 选择器，用于匹配触发元素 */
    selector: ICSSSelector;
  };
}

/** 事件委托根节点类型（支持组件实例或原生 DOM） */
type DelegationRoot = MaybeRef<HTMLElement> | MaybeRef<InstanceType<typeof PrimaryTable>>;

/** CSS 选择器字符串 */
type ICSSSelector = string;

/** popover 内容类型（支持 DOM 元素、JSX、数字或字符串） */
type PopoverContent = HTMLElement | JSX.Element | number | string;

/** popover 触发事件类型 */
type PopoverTriggerEventType = 'click' | 'mouseenter';

/**
 * @description 表格 popover Hook，基于事件委托实现，用于在表格单元格等场景下触发气泡提示
 * @param {DelegationRoot} delegationRoot 事件委托根节点（支持原生 DOM 或组件实例）
 * @param {UseTablePopoverOptions} options 配置选项
 * @returns 返回 popover 控制方法与事件监听初始化方法
 */
export const useTablePopover = (delegationRoot: DelegationRoot, options: UseTablePopoverOptions) => {
  let popoverInstance = null;
  let mouseenterDebouncedTimer = null;
  let popoverDelayTimer = null;

  /** 统一获取事件委托根 DOM（兼容组件实例和原生 DOM） */
  const getRootDom = () => {
    // biome-ignore lint/suspicious/noExplicitAny: 需要兼容组件实例和原生 DOM
    const root = get(delegationRoot) as any;
    // 如果是组件实例，返回 $el；否则直接返回 DOM
    return root?.$el || root;
  };

  onBeforeUnmount(() => {
    handlePopoverHide();
    destroyDelegationListeners();
  });

  /**
   * @description 初始化事件委托监听器
   *
   */
  const initListeners = () => {
    // 先销毁之前的事件委托监听器，避免重复绑定导致内存泄漏
    destroyDelegationListeners();

    const rootDom = getRootDom();
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
    const rootDom = getRootDom();
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
    const target = e.target as HTMLElement;
    const handleFn = () => {
      const targetDom: HTMLElement = target?.closest?.(options.trigger.selector);
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
 * @description 表格文本溢出省略弹出 popover 处理（基于 useTablePopover 的快捷封装）
 * @param {DelegationRoot} delegationRoot 事件委托根节点（支持原生 DOM 或组件实例）
 * @param {Omit<UseTablePopoverOptions, 'getContentOptions'>} [options] 配置选项（无需传入 getContentOptions）
 * @returns 返回 popover 控制方法与事件监听初始化方法
 */
export const useTableEllipsis = (
  delegationRoot: DelegationRoot,
  options?: Omit<UseTablePopoverOptions, 'getContentOptions'>
) =>
  useTablePopover(delegationRoot, {
    trigger: {
      ...(options?.trigger || {}),
      selector: options?.trigger?.selector || `.${DEFAULT_ELLIPSIS_CELL_CLASS_NAME}`,
    },
    getContentOptions: triggerDom => {
      const { isEllipsisActive, content } = isEllipsisActiveLine(triggerDom);
      if (!isEllipsisActive) return;
      return { content };
    },
    popoverOptions: {
      ...(options?.popoverOptions || {}),
    },
  });
