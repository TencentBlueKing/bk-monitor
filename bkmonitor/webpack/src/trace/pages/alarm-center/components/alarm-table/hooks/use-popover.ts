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

import { onBeforeUnmount } from 'vue';
import { type TippyContent, type TippyOptions, useTippy } from 'vue-tippy';

export type IUsePopoverTools = ReturnType<typeof usePopover>;

/**
 * @description Popover 管理钩子（单例）
 * @returns Popover 控制方法
 */
export function usePopover(popoverDefaultOptions: TippyOptions = {}) {
  /** popover 实例 */
  let popoverInstance = null;
  /** popover 延迟打开定时器 */
  let popoverDelayTimer = null;

  // 默认配置
  const defaultOptions: Partial<TippyOptions> = {
    appendTo: () => document.body,
    trigger: 'mouseenter',
    animation: false,
    maxWidth: 'none',
    allowHTML: false,
    arrow: true,
    interactive: true,
    theme: 'alarm-center-popover max-width-50vw text-wrap padding-0',
    onHidden: () => {
      hidePopover();
    },
    ...popoverDefaultOptions,
  };

  /**
   * @description 显示 Popover
   * @param target 目标元素
   * @param content 弹窗内容
   * @param instanceKey popover 实例唯一标识，用来判断是否连续同一元素触发，避免连续两次同一元素触发 关闭又打开 交互不好
   * @param customOptions 自定义选项
   */
  function showPopover(e: MouseEvent, content: TippyContent, instanceKey?: string, customOptions?: TippyOptions);
  /**
   * @description 显示 Popover
   * @param target 目标元素
   * @param content 弹窗内容
   * @param customOptions 自定义选项
   */
  function showPopover(e: MouseEvent, content: TippyContent, customOptions?: TippyOptions);
  function showPopover(
    e: MouseEvent,
    content: TippyContent,
    instanceKeyOrOptions?: string | TippyOptions,
    customOptions?: TippyOptions
  ) {
    let instanceKey: string | undefined;
    if (typeof instanceKeyOrOptions === 'string') {
      instanceKey = instanceKeyOrOptions;
    } else {
      customOptions = instanceKeyOrOptions;
    }

    customOptions = customOptions || {};
    const prevInstanceKey = popoverInstance?.instanceKey;
    if (popoverInstance || popoverDelayTimer) {
      hidePopover();
    }

    // 相同实例Key直接返回，只关闭 popover 不在打开
    if (instanceKey && prevInstanceKey === instanceKey) return;

    popoverInstance = useTippy(e.currentTarget, {
      content: content,
      ...defaultOptions,
      ...customOptions,
    });
    // 设置实例唯一标识key（非必须）
    popoverInstance.instanceKey = instanceKey || '';
    const currentInstance = popoverInstance;
    popoverDelayTimer = setTimeout(() => {
      if (currentInstance === popoverInstance) {
        popoverInstance?.show?.(0);
      } else {
        currentInstance?.hide?.(0);
        currentInstance?.destroy?.();
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

  onBeforeUnmount(() => {
    hidePopover();
  });

  return {
    showPopover,
    hidePopover,
    clearPopoverTimer,
  };
}
