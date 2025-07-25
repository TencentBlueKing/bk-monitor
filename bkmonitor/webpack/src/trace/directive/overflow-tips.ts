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

import type { ObjectDirective } from 'vue';

import tippy, { type Instance, type Props } from 'tippy.js';

import type { noop } from '@vueuse/core';

import 'tippy.js/dist/tippy.css';
type MouseEnterFunc = (e?: MouseEvent) => void;
type OverflowElement = HTMLElement & {
  mouseEnterFunc?: MouseEnterFunc;
  mouseLeaveFunc?: MouseEnterFunc;
  unObserverFunc: typeof noop;
};
const DelayMs = 300;
const OverflowTips: ObjectDirective<OverflowElement, Props & { disabled: boolean; text?: string }> = {
  mounted(el, binding) {
    let instance: Instance<Props> = null;
    let isMouseenter = false;
    function getIsEllipsis(el: Element) {
      return el.scrollWidth > el.clientWidth;
    }
    function mouseenter(event: MouseEvent) {
      event.stopPropagation();
      if (binding.value?.disabled) return;
      if (!getIsEllipsis(el)) {
        return;
      }
      isMouseenter = true;
      if (!instance) {
        instance = tippy(el, {
          trigger: 'mouseenter',
          delay: [DelayMs, 0],
          content: binding.value?.text || binding.value?.content || el.innerText,
          placement: binding.value?.placement || 'auto',
          onShow: () => {
            if (!getIsEllipsis(el)) {
              return false;
            }
          },
          onHidden: () => {
            instance?.hide();
            instance?.destroy();
            instance = null;
          },
          ...binding.value,
        });
        // 初始化第一次进入时 tippy 可能出现不展示的情况 这里直接延时处理
        setTimeout(() => {
          if (instance && isMouseenter && getIsEllipsis(el) && !instance.state.isShown) {
            instance.clearDelayTimeouts();
            instance.show();
          }
        }, DelayMs + 16);
      }
    }
    function mouseleave() {
      isMouseenter = false;
    }
    const observer = new IntersectionObserver(
      entries => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            el.addEventListener('mouseenter', mouseenter);
            el.addEventListener('mouseleave', mouseleave);
            el.mouseEnterFunc = mouseenter;
            el.mouseLeaveFunc = mouseleave;
            return;
          }
          el.removeEventListener('mouseenter', mouseenter);
          el.removeEventListener('mouseleave', mouseleave);
        }
      },
      {
        threshold: 0.1, // 当10%的元素可见时触发
      }
    );
    observer.observe(el);
    el.unObserverFunc = () => {
      observer.unobserve(el);
    };
  },
  beforeUnmount(el) {
    el.removeEventListener('mouseenter', el.mouseEnterFunc);
    el.removeEventListener('mouseleave', el.mouseLeaveFunc);
    el.unObserverFunc?.();
    el.mouseEnterFunc = undefined;
    el.mouseLeaveFunc = undefined;
    el.unObserverFunc = undefined;
  },
};
export default OverflowTips;
