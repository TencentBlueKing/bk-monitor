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
import { Ref } from 'vue';

import { isElement } from 'lodash';

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

export const getTargetElement = (
  target: (() => HTMLElement) | HTMLElement | Ref<HTMLElement> | string,
): HTMLElement => {
  if (typeof target === 'string') {
    if (window.__IS_MONITOR_TRACE__) {
      return deepQueryShadowSelector(target);
    }
    return document.querySelector(target);
  }

  if (isElement(target)) {
    return target as HTMLElement;
  }

  if (typeof target === 'function') {
    return target?.();
  }

  return (target as Ref<HTMLElement>)?.value;
};
