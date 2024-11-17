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
import { onMounted, onUnmounted, ref } from 'vue';

import { throttle, debounce } from 'lodash';

import { GLOBAL_SCROLL_SELECTOR } from './log-row-attributes';

export default ({ loadMoreFn, scrollCallbackFn, container }) => {
  const isRunning = ref(false);
  const searchBarHeight = ref(0);
  const offsetWidth = ref(0);
  const scrollWidth = ref(0);
  let scrollElementOffset = 0;
  let isComputingCalcOffset = false;

  const getScrollElement = () => {
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
      let currentElement = getCurrentElement();
      const relativeTo = getScrollElement();
      let offsetTop = 0;
      while (currentElement && currentElement !== relativeTo) {
        offsetTop += currentElement.offsetTop;
        currentElement = currentElement.offsetParent as HTMLElement;
      }
      scrollElementOffset = offsetTop;
      searchBarHeight.value = (document.querySelector('.search-bar-container') as HTMLElement)?.offsetHeight ?? 0;
      debounceStopComputing();
    }
  };

  const debounceCallback = () => {
    if (!isRunning.value) {
      isRunning.value = true;
      loadMoreFn?.()?.then?.(() => {
        isRunning.value = false;
      });
    }
  };

  let lastPosition = 0;
  const handleScrollEvent = throttle((event: MouseEvent) => {
    calculateOffsetTop();
    const target = event.target as HTMLDivElement;
    const scrollDiff = target.scrollHeight - (target.scrollTop + target.offsetHeight);
    if (target.scrollTop > lastPosition && scrollDiff < 20) {
      debounceCallback();
    }

    scrollCallbackFn?.(target.scrollTop, scrollElementOffset);
    lastPosition = target.scrollTop;
  });

  const scrollToTop = () => {
    getScrollElement().scrollTo({ left: 0, top: 0, behavior: 'smooth' });
  };

  const hasScrollX = () => {
    const target = getCurrentElement() as HTMLDivElement;
    offsetWidth.value = target.offsetWidth;
    scrollWidth.value = target.scrollWidth;
    return target.scrollWidth > target.offsetWidth;
  };

  onMounted(() => {
    getScrollElement()?.addEventListener('scroll', handleScrollEvent);
    calculateOffsetTop();
  });

  onUnmounted(() => {
    getScrollElement()?.removeEventListener('scroll', handleScrollEvent);
  });

  return {
    scrollToTop,
    hasScrollX,
    searchBarHeight,
    offsetWidth,
    scrollWidth,
  };
};
