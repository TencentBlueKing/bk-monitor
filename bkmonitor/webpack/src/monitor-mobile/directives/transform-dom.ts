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

import type { DirectiveOptions } from 'vue';

import type { DirectiveBinding } from 'vue/types/options';

function getTarget(selector: string) {
  let target = document.querySelector(selector);
  if (!target) {
    target = document.body;
  }
  return target;
}

const transferDom: DirectiveOptions = {
  inserted(el: HTMLElement, binding: DirectiveBinding) {
    el.className = el.className ? `${el.className} v-transfer-dom` : 'v-transfer-dom';
    const { parentNode } = el;
    const targetNode = getTarget(binding.value);
    if (!parentNode || !targetNode) return;

    const comment = document.createComment('');
    parentNode.replaceChild(comment, el); // moving out, el is no longer in the document
    targetNode.appendChild(el); // moving into new place
  },
  unbind(el: HTMLElement) {
    el.className = el.className.replace('v-transfer-dom', '');
  },
};

export default transferDom;
