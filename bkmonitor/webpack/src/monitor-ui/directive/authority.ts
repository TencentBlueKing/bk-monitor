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
import type { VueConstructor } from 'vue';

import type { DirectiveBinding } from 'vue/types/options';

interface IElement extends HTMLElement {
  [prop: string]: any;
}
interface IOptions {
  active: boolean;
  cls: string;
  offset: number[];
}

const DEFAULT_OPTIONS: IOptions = {
  active: true,
  offset: [12, 0],
  cls: 'cursor-element',
};

// biome-ignore lint/complexity/noStaticOnlyClass: <explanation>
export default class AuthorityDirective {
  public static install(Vue: VueConstructor) {
    Vue.directive('authority', {
      bind(el: IElement, binding: DirectiveBinding) {
        const options: IOptions = Object.assign({}, DEFAULT_OPTIONS, binding.value);
        init(el, options);
      },
      update(el: IElement, binding: DirectiveBinding) {
        const options: IOptions = Object.assign({}, DEFAULT_OPTIONS, binding.value);
        destroy(el);
        init(el, options);
      },
      unbind(el: IElement) {
        destroy(el);
      },
    });
  }
}

function destroy(el: IElement) {
  el.element?.remove();
  el.element = null;
  el.removeEventListener('mouseenter', el.mouseEnterHandler);
  el.removeEventListener('mousemove', el.mouseMoveHandler);
  el.removeEventListener('mouseleave', el.mouseLeaveHandler);
}

function init(el: IElement, options: IOptions) {
  el.mouseEnterHandler = function () {
    const element = document.createElement('div');
    element.id = 'directive-ele';
    element.style.position = 'fixed';
    element.style.zIndex = '9999';
    el.element = element;
    document.body.appendChild(element);

    element.classList.add(options.cls || DEFAULT_OPTIONS.cls);
    el.addEventListener('mousemove', el.mouseMoveHandler);
  };
  el.mouseMoveHandler = function (event: MouseEvent) {
    const { pageX, pageY } = event;
    const elLeft = pageX + DEFAULT_OPTIONS.offset[0];
    const elTop = pageY + DEFAULT_OPTIONS.offset[1];
    el.element.style.left = `${elLeft}px`;
    el.element.style.top = `${elTop}px`;
  };
  el.mouseLeaveHandler = function () {
    el.element?.remove();
    document.querySelector('#directive-ele')?.remove();
    el.element = null;
    el.removeEventListener('mousemove', el.mouseMoveHandler);
  };
  if (options.active) {
    el.addEventListener('mouseenter', el.mouseEnterHandler);
    el.addEventListener('mouseleave', el.mouseLeaveHandler);
  }
}
