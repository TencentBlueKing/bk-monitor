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
import { onMounted, onBeforeUnmount } from 'vue';

import { throttle } from 'lodash-es';

import { getTargetElement } from './hooks-helper';

export default (target, callback: (e: MouseEvent) => void) => {
  const getScrollElement = () => {
    return getTargetElement(target);
  };

  const handleScrollEvent = throttle((event: MouseEvent) => {
    requestAnimationFrame(() => {
      callback?.(event);
    });
  });

  const scrollToTop = (smooth = true) => {
    getScrollElement()?.scrollTo({ left: 0, top: 0, behavior: smooth ? 'smooth' : 'instant' });
  };

  const hasScrollX = () => {
    const newTarget = getScrollElement() as HTMLDivElement;
    return newTarget.scrollWidth > newTarget.offsetWidth;
  };

  onMounted(() => {
    getScrollElement()?.addEventListener('scroll', handleScrollEvent);
  });

  onBeforeUnmount(() => {
    getScrollElement()?.removeEventListener('scroll', handleScrollEvent);
  });

  return {
    scrollToTop,
    hasScrollX,
  };
};
