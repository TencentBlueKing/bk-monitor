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

import { addListener, removeListener } from '@blueking/fork-resize-detector';

import type { DirectiveBinding } from 'vue/types/options';

interface ICustomElements extends HTMLElement {
  __mutation__?: MutationObserver;
}

interface IResizeOptions {
  disabled: boolean;
  handler: (el: HTMLElement) => void;
}

export const mutation: DirectiveOptions = {
  bind: (el: ICustomElements, binding: DirectiveBinding) => {
    const options: MutationObserverInit = {
      attributes: true,
      childList: true,
      subtree: true,
    };
    const observer = new MutationObserver(binding.value);
    observer.observe(el, options);

    el.__mutation__ = observer;
  },
  unbind: (el: ICustomElements) => {
    el.__mutation__?.disconnect();
  },
};

/**
 * 两种绑定值的格式:
 * 1：直接绑定一个处理函数，绑定即监听
 * 2: 绑定一个配置对象，配置disabled来判断是否启用监听
 *
 * 注意：disabled暂不支持响应式变化
 */
export const resize: DirectiveOptions = {
  bind: (el: HTMLElement, binding: DirectiveBinding) => {
    const { handler, disabled } = parseBindingValue(binding);
    if (!disabled) addListener(el, handler);
  },
  unbind: (el: HTMLElement, binding: DirectiveBinding) => {
    const { handler, disabled } = parseBindingValue(binding);
    if (!disabled) removeListener(el, handler);
  },
};

export const parseBindingValue = (binding: DirectiveBinding): IResizeOptions => {
  /** 绑定值为一个函数 否则为对象形式{ disabled: boolean, handler: Function } */
  const isFunction = typeof binding.value === 'function';
  const func = isFunction ? binding.value : binding.value.handler;
  const disabled = isFunction ? false : binding.value.disabled;
  return {
    disabled,
    handler: func,
  };
};

export default {
  mutation,
  resize,
};
