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

import { toValue } from 'vue';
import { type TippyContent, type TippyOptions, useTippy } from 'vue-tippy';

export interface IUsePopoverTools {
  /** 显示 Popover */
  showPopover: (e: MouseEvent, content: TippyContent, options?: TippyOptions) => void;
  /** 清除 popover */
  hidePopover: () => void;
  /** 清除 popover 延时打开定时器 */
  clearPopoverTimer: () => void;
}

/**
 * @description Popover 管理钩子（单例）
 * @returns Popover 控制方法
 */
export function usePopover(): IUsePopoverTools {
  /** popover 实例 */
  let popoverInstance = null;
  /** popover 延迟打开定时器 */
  let popoverDelayTimer = null;

  // 默认配置
  const defaultOptions: Partial<TippyOptions> = {
    appendTo: () => document.body,
    animation: false,
    maxWidth: 'none',
    allowHTML: true,
    arrow: true,
    interactive: true,
    theme: 'alarm-center-popover max-width-50vw text-wrap padding-0',
    onHidden: () => {
      hidePopover();
    },
  };

  /**
   * 显示 Popover
   * @param target 目标元素
   * @param content 弹窗内容
   * @param options 自定义选项
   *
   */
  function showPopover(e: MouseEvent, content: TippyContent, customOptions: TippyOptions = {}) {
    if (popoverInstance || popoverDelayTimer) {
      hidePopover();
    }
    popoverInstance = useTippy(e.currentTarget, {
      content: toValue(content),
      ...defaultOptions,
      ...customOptions,
    });
    const popoverCache = popoverInstance;
    popoverDelayTimer = setTimeout(() => {
      if (popoverCache === popoverInstance) {
        popoverInstance?.show?.(0);
      } else {
        popoverCache?.hide?.(0);
        popoverCache?.destroy?.();
      }
    }, 300);
  }

  /**
   * @description: 清除popover
   */
  function hidePopover() {
    clearPopoverTimer();
    popoverInstance?.hide?.(0);
    popoverInstance?.destroy?.();
    popoverInstance = null;
  }

  /**
   * @description: 清除popover延时打开定时器
   *
   */
  function clearPopoverTimer() {
    popoverDelayTimer && clearTimeout(popoverDelayTimer);
    popoverDelayTimer = null;
  }

  return {
    showPopover,
    hidePopover,
    clearPopoverTimer,
  };
}
