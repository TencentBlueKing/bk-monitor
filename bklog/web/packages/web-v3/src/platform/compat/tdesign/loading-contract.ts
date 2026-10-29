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

import type { DirectiveBinding } from 'vue';
export interface LoadingOptions {
  isLoading?: boolean;
  immediate?: boolean;
  title?: string;
  size?: string;
  delay?: number | string;
  color?: string;
  opacity?: number;
  zIndex?: number | string;
}
type LoadingTimer = ReturnType<typeof setTimeout> | number;
interface LoadingState {
  visible: boolean;
  title: string;
  size: string;
  timer: LoadingTimer | undefined;
  options: LoadingOptions;
}
interface LoadingDriver {
  paint(element: HTMLElement, state: LoadingOptions & {visible: boolean;title: string;size: string}, binding: DirectiveBinding<LoadingOptions>): void;
  remove(element: HTMLElement): void;
  schedule?: (callback: () => void, delay: number) => LoadingTimer;
  cancel?: (timer: LoadingTimer) => void;
}
// Source: bk-magic-vue/lib/loading.js directive inserted/update (xp).
// V2's delay postpones hiding. TDesign's delay postpones showing, so it cannot
// be forwarded directly without changing fast-request and retry behavior.
export function createLoadingDirective({ paint, remove, schedule = setTimeout, cancel = clearTimeout }: LoadingDriver) {
  const states = new WeakMap<HTMLElement, LoadingState>();
  function update(el: HTMLElement, binding: DirectiveBinding<LoadingOptions>, initial = false) {
    const value = binding.value || {};
    let state = states.get(el);
    if (!state) {
      state = { visible: false, title: '', size: 'large', timer: undefined, options: { ...value } };
      states.set(el, state);
    }
    const current = state;
    if (current.timer !== undefined) cancel(current.timer);
    current.timer = undefined;
    // The source only replaces truthy title/size and retains initial styling.
    if (value.title) current.title = value.title;
    if (value.size) current.size = value.size;
    const draw = () =>
      paint(el, { ...current.options, title: current.title, size: current.size, visible: current.visible }, binding);
    if ((initial && value.immediate) || value.isLoading) {
      current.visible = true;
      draw();
    } else {
      const delay = Number(value.delay);
      if (delay > 0) {
        current.timer = schedule(() => {
          current.timer = undefined;
          current.visible = false;
          draw();
        }, delay);
        draw();
      } else {
        current.visible = false;
        draw();
      }
    }
  }
  return {
    mounted: (el: HTMLElement, binding: DirectiveBinding<LoadingOptions>) => update(el, binding, true),
    updated: (el: HTMLElement, binding: DirectiveBinding<LoadingOptions>) => update(el, binding),
    unmounted(el: HTMLElement) {
      const state = states.get(el);
      if (state?.timer !== undefined) cancel(state.timer);
      states.delete(el);
      remove(el);
    },
  };
}
