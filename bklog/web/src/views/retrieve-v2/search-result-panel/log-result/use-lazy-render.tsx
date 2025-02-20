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
import { computed, onMounted, onBeforeUnmount, ref } from 'vue';

import useResizeObserve from '@/hooks/use-resize-observe';
import { debounce } from 'lodash';

import { GLOBAL_SCROLL_SELECTOR } from './log-row-attributes';
function deepQueryShadowSelector(selector) {
  // 搜索当前根下的元素
  const searchInRoot = root => {
    // 尝试直接查找
    const el = root.querySelector(selector);
    if (el) return el;

    // 查找当前根下所有可能的 Shadow Host
    const shadowHosts = Array.from(root.querySelectorAll('*')).filter(el => el.shadowRoot);

    // 递归穿透每个 Shadow Host
    for (const host of shadowHosts) {
      const result = searchInRoot(host.shadowRoot);
      if (result) return result;
    }

    return null;
  };

  // 从 document.body 开始搜索
  return searchInRoot(document.body);
}

export default ({ loadMoreFn, container, rootElement }) => {
  // const searchBarHeight = ref(0);
  const offsetWidth = ref(0);
  const scrollWidth = ref(0);
  const scrollDirection = ref('down');

  // let scrollElementOffset = 0;
  let isComputingCalcOffset = false;

  const getScrollElement = () => {
    if (window.__IS_MONITOR_TRACE__) {
      return deepQueryShadowSelector(GLOBAL_SCROLL_SELECTOR);
    }
    return document.body.querySelector(GLOBAL_SCROLL_SELECTOR);
  };

  const debounceStopComputing = debounce(() => {
    isComputingCalcOffset = false;
  }, 500);

  const getCurrentElement = () => {
    return document.querySelector(container) as HTMLElement;
  };

  const calculateOffsetTop = () => {
    if (!isComputingCalcOffset) {
      isComputingCalcOffset = true;
      debounceStopComputing();
    }
  };

  let lastPosition = 0;

  const handleScrollEvent = (event: MouseEvent) => {
    const target = event.target as HTMLDivElement;
    requestAnimationFrame(() => {
      if (target) {
        const scrollDiff = target.scrollHeight - (target.scrollTop + target.offsetHeight);
        if (target.scrollTop > lastPosition && scrollDiff < 80) {
          loadMoreFn?.();
        }

        scrollDirection.value = target.scrollTop > lastPosition ? 'down' : 'up';
        lastPosition = target.scrollTop;
      }
    });
  };

  const scrollToTop = (top = 0, smooth = true) => {
    getScrollElement()?.scrollTo({ left: 0, top: top, behavior: smooth ? 'smooth' : 'instant' });
  };

  const hasScrollX = computed(() => scrollWidth.value > offsetWidth.value);

  const getParentContainer = () => {
    return rootElement.value as HTMLElement;
  };

  const computeRect = () => {
    const current = getCurrentElement();
    const scrollElement = getParentContainer() as HTMLElement;
    scrollWidth.value = (current?.scrollWidth ?? 6) - 6;
    offsetWidth.value = scrollElement?.offsetWidth ?? 0;
  };

  const debounceComputeRect = debounce(computeRect, 120);

  useResizeObserve(getCurrentElement, () => {
    debounceComputeRect();
  });

  useResizeObserve(getParentContainer, () => {
    debounceComputeRect();
  });

  onMounted(() => {
    getScrollElement()?.addEventListener('scroll', handleScrollEvent);
    calculateOffsetTop();
  });

  onBeforeUnmount(() => {
    getScrollElement()?.removeEventListener('scroll', handleScrollEvent);
  });

  return {
    scrollToTop,
    hasScrollX,
    computeRect,
    scrollDirection,
    offsetWidth,
    scrollWidth,
  };
};
