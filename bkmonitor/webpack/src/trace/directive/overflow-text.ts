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
import tippy, { type Placement } from 'tippy.js';

import type { ObjectDirective } from 'vue';

import 'tippy.js/dist/tippy.css';
type OverflowElement = HTMLElement & { mouseEnterFunc?: (event: MouseEvent) => void; unObserverFunc: () => void };

const OverflowText: ObjectDirective<OverflowElement, { placement: Placement; text: string }> = {
  mounted(el, binding) {
    let instance = null;
    function mouseenter(event: MouseEvent) {
      event.stopPropagation();
      if (!instance) {
        instance = tippy((event as MouseEvent & { target: Element }).target, {
          trigger: 'mouseenter',
          allowHTML: true,
          placement: binding.value?.placement || 'top',
          delay: [300, 0],
          content: `<span style="font-size: 12px;">${binding.value?.text || el.innerText}</span>`,
          onHidden: () => {
            instance?.hide();
            instance?.destroy();
            instance = null;
          },
        });
        instance?.show();
      } else {
        instance?.show();
      }
    }
    function observeElementVisibility(el: OverflowElement, callback: (isVisible: boolean) => void) {
      const observer = new IntersectionObserver(
        entries => {
          for (const entry of entries) {
            callback(entry.isIntersecting);
          }
        },
        {
          threshold: 0.1, // 当10%的元素可见时触发
        }
      );
      observer.observe(el);
      const unObserve = () => {
        observer.unobserve(el);
      };
      el.unObserverFunc = unObserve;
    }
    observeElementVisibility(el, isVisible => {
      if (isVisible) {
        if (el.scrollWidth > el.clientWidth) {
          el.addEventListener('mouseenter', mouseenter);
        }
      } else {
        el.removeEventListener('mouseenter', mouseenter);
      }
    });
  },
  beforeUnmount(el) {
    el.removeEventListener('mouseenter', el.mouseEnterFunc);
    el?.unObserverFunc();
  },
};
export default OverflowText;
