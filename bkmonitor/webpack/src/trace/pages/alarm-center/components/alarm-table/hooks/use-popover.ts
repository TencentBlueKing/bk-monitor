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

import { onBeforeUnmount, shallowRef } from 'vue';

import { get } from '@vueuse/core';
import { type TippyContent, type TippyOptions, useTippy } from 'vue-tippy';

import type { Instance, Props as TProps } from 'tippy.js';

export interface IUsePopoverOptions {
  /** 显示延迟（默认 300 毫秒） */
  showDelay?: number;
  /** tippy 配置项（配置项可参考：https://vue-tippy.netlify.app/props） */
  tippyOptions?: TippyOptions;
}
export type IUsePopoverTools = ReturnType<typeof usePopover>;
export type IUseTippyInstance = ReturnType<typeof useTippy> & { instanceKey?: string };

/**
 * @function usePopover 单例 popover hooks
 * @description Popover 管理钩子（单例）
 * @param {number} options.showDelay 显示延迟（默认 300 毫秒）
 * @param {TippyOptions} options.tippyOptions tippy 默认配置项（配置项可参考：https://vue-tippy.netlify.app/props）
 * @returns Popover 控制方法
 */
export function usePopover(options: IUsePopoverOptions = { showDelay: 300, tippyOptions: {} }) {
  /** popover 实例 */
  const popoverInstance = shallowRef<IUseTippyInstance | null>(null);
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
    ...(options?.tippyOptions ?? {}),
  };

  /**
   * @description 显示 Popover
   * @param target 目标元素
   * @param {TippyContent} content 弹窗内容
   * @param {string} instanceKey popover 实例唯一标识，用来判断是否连续同一元素触发，避免连续两次同一元素触发 关闭又打开 交互不好
   * @param {TippyOptions} customOptions 自定义 tippy 配置项（配置项可参考：https://vue-tippy.netlify.app/props）
   */
  function showPopover(e: MouseEvent, content: TippyContent, instanceKey?: string, customOptions?: TippyOptions);
  /**
   * @description 显示 Popover
   * @param target 目标元素
   * @param {TippyContent} content 弹窗内容
   * @param {TippyOptions} customOptions 自定义 tippy 配置项（配置项可参考：https://vue-tippy.netlify.app/props）
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
    const prevInstanceKey = get(popoverInstance)?.instanceKey;
    if (get(popoverInstance) || popoverDelayTimer) {
      hidePopover();
    }

    // 相同实例Key直接返回，只关闭 popover 不在打开
    if (instanceKey && prevInstanceKey === instanceKey) return;

    const instance: IUseTippyInstance = useTippy(e.currentTarget, {
      content: content,
      ...defaultOptions,
      ...customOptions,
      onHidden: (instance: Instance<TProps>) => {
        defaultOptions?.onHidden?.(instance);
        customOptions?.onHidden?.(instance);
      },
    });
    // 设置实例唯一标识key（非必须）
    instance.instanceKey = instanceKey || '';
    popoverInstance.value = instance;
    const currentInstance = get(popoverInstance);
    popoverDelayTimer = setTimeout(() => {
      if (currentInstance === get(popoverInstance)) {
        get(popoverInstance)?.show?.();
      } else {
        currentInstance?.hide?.();
        currentInstance?.destroy?.();
      }
    }, options?.showDelay ?? 300);
  }

  /**
   * @description: 清除popover
   */
  function hidePopover() {
    clearPopoverTimer();
    get(popoverInstance)?.hide?.();
    get(popoverInstance)?.destroy?.();
    popoverInstance.value = null;
  }

  /**
   * @description: 清除popover延时打开定时器
   */
  function clearPopoverTimer() {
    popoverDelayTimer && clearTimeout(popoverDelayTimer);
    popoverDelayTimer = null;
  }

  onBeforeUnmount(() => {
    hidePopover();
  });

  return {
    popoverInstance,
    showPopover,
    hidePopover,
    clearPopoverTimer,
  };
}
