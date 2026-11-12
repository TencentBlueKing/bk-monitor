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

import { watch, type Ref } from 'vue';

/** Focus a popup input after attachment and visibility, with cleanup on close. */
export default function useVisibleInputFocus(
  open: Readonly<Ref<boolean>>,
  input: Readonly<Ref<HTMLInputElement | undefined>>,
  popupSelector: string,
) {
  watch([open, input], ([visible, element], _, onCleanup) => {
    if (!visible || !element) return;
    const root = element.closest(popupSelector) ?? element;
    const disconnect = () => {
      resizeObserver.disconnect();
      mutationObserver.disconnect();
    };
    const focusWhenVisible = () => {
      if (!open.value || !element.isConnected || !element.getClientRects().length) return;
      if (getComputedStyle(element).visibility !== 'visible' || element.closest('[inert]')) return;
      element.focus();
      if (document.activeElement === element) disconnect();
    };
    const resizeObserver = new ResizeObserver(focusWhenVisible);
    const mutationObserver = new MutationObserver(focusWhenVisible);
    resizeObserver.observe(element);
    mutationObserver.observe(root, {attributes: true, subtree: true, attributeFilter: ['style', 'class', 'hidden', 'inert']});
    for (let ancestor = root.parentElement; ancestor; ancestor = ancestor.parentElement) {
      mutationObserver.observe(ancestor, {attributes: true, attributeFilter: ['style', 'class', 'hidden', 'inert']});
    }
    onCleanup(disconnect);
    focusWhenVisible();
  }, {flush: 'post'});
}
