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
import { onMounted, type Ref, onBeforeUnmount, ref } from 'vue';

import { debounce, isElement } from 'lodash-es';

export default (
  target: (() => HTMLElement | string) | Ref<HTMLElement> | string,
  callbackFn: (entry: ResizeObserverEntry) => void,
  delayCallback: boolean | number = 120,
  immediateStart = true,
) => {
  const debounceCallback = debounce(entry => {
    callbackFn?.(entry);
  }, delayCallback);

  const getTarget = () => {
    if (typeof target === 'string') {
      return document.querySelector(target);
    }

    if (isElement(target)) {
      return target;
    }

    if (typeof target === 'function') {
      return target?.();
    }

    return target?.value;
  };

  let resizeObserver: ResizeObserver;
  const isStoped = ref(true);

  const observeElement = () => {
    if (isStoped.value) {
      isStoped.value = false;
      const cellElement = getTarget() as HTMLElement;
      resizeObserver?.observe(cellElement);
    }
  };

  const createResizeObserve = () => {
    const cellElement = getTarget() as HTMLElement;

    if (isElement(cellElement)) {
      // 创建一个 ResizeObserver 实例
      resizeObserver = new ResizeObserver(entries => {
        for (const entry of entries) {
          if (delayCallback === false) {
            callbackFn?.(entry);
          }

          if (typeof delayCallback === 'number') {
            // 获取元素的新高度
            debounceCallback(entry);
          }
        }
      });
    }

    if (immediateStart) {
      observeElement();
    }
  };

  const stopObserve = () => {
    const cellElement = getTarget() as HTMLElement;
    isStoped.value = true;

    if (isElement(cellElement)) {
      resizeObserver?.unobserve(cellElement);
      resizeObserver?.disconnect();
    }
  };

  const destoyResizeObserve = () => {
    stopObserve();
    resizeObserver = undefined;
  };

  onMounted(() => {
    createResizeObserve();
  });

  onBeforeUnmount(() => {
    destoyResizeObserve();
  });

  const getInstance = () => resizeObserver;

  return { destoyResizeObserve, getInstance, observeElement, stopObserve, isStoped };
};
