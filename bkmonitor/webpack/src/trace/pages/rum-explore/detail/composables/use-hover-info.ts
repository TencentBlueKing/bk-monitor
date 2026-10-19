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
 * documentation files (the "Software") to deal in the Software without restriction, including without limitation
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

import { useTippy } from 'vue-tippy';

import type { IRumHoverInfo } from '../typings';

/** hover 展示延迟（毫秒），与全局 popover 交互习惯一致 */
const SHOW_DELAY = 0;

/**
 * 详情区块标题的 hover-info 卡片控制 hook
 *
 * 返回 hoverBindings：有 hover 数据的元素展开成 mouseenter / mouseleave 事件，
 * 悬停到延迟时间后在触发元素上挂载 tippy 并展示 RumHoverInfo 卡片；离开时销毁浮层。
 * 同一时刻只保留一个浮层（单例），无 hover 数据的元素返回空对象，行为不变。
 */
export function useHoverInfo() {
  const hoverData = shallowRef<IRumHoverInfo>(null);
  const instance = shallowRef<null | ReturnType<typeof useTippy>>(null);
  let delayTimer: null | ReturnType<typeof setTimeout> = null;

  function hide() {
    if (delayTimer) {
      clearTimeout(delayTimer);
      delayTimer = null;
    }
    instance.value?.hide?.();
    instance.value?.destroy?.();
    instance.value = null;
  }

  function show(e: MouseEvent, content: Element) {
    hide();
    const current = useTippy(e.currentTarget as Element, {
      content: () => content,
      appendTo: () => document.body,
      trigger: 'mouseenter',
      animation: false,
      maxWidth: 'none',
      arrow: false,
      interactive: true,
      offset: [10, 0],
      /** 卡片自带深色背景，浮层容器去底色与内边距，样式见 hover-info.scss */
      theme: 'rum-hover-info-popover',
      onHidden() {
        hide();
      },
    });
    instance.value = current;
    delayTimer = setTimeout(() => {
      delayTimer = null;
      if (instance.value === current) {
        current.show?.();
      } else {
        current.destroy?.();
      }
    }, SHOW_DELAY);
  }

  onBeforeUnmount(hide);

  function hoverBindings(content: Element, hover?: IRumHoverInfo) {
    return {
      /** 有 hover 数据的元素提示可交互（JSX spread 走 mergeProps，class 与元素自身类名合并） */
      class: hover ? 'cursor-pointer' : undefined,
      onMouseenter: (e: MouseEvent) => {
        hoverData.value = hover;
        if (hover) {
          show(e, content);
        }
      },
    };
  }

  return { hoverData, hoverBindings };
}
