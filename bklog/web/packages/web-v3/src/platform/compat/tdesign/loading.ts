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

import { h, render } from 'vue';
import { Loading } from 'tdesign-vue-next';
import { createLoadingDirective } from './loading-contract';
import 'tdesign-vue-next/es/loading/style/index.css';

const mounts = new WeakMap<HTMLElement, { container: HTMLDivElement; originalPosition: string; positioned: boolean }>();
export const bkLoadingDirective = createLoadingDirective({
  paint(el, options, binding) {
    let mount = mounts.get(el);
    if (!mount) {
      const container = document.createElement('div');
      container.className = 'bklog-native-loading';
      const originalPosition = el.style.position;
      const positioned = !['relative', 'absolute', 'fixed', 'sticky'].includes(getComputedStyle(el).position);
      if (positioned) el.style.position = 'relative';
      el.appendChild(container);
      mount = { container, originalPosition, positioned };
      mounts.set(el, mount);
    }
    const { visible, title, size, zIndex } = options;
    const color = options.color || '#ffffff';
    const opacity = options.opacity || 0.9;
    mount.container.style.cssText = `position:absolute;inset:0;display:${visible ? 'flex' : 'none'};align-items:center;justify-content:center;z-index:${zIndex ?? 1000}`;
    const vnode = h(
      'div',
      { style: 'position:absolute;inset:0;display:flex;align-items:center;justify-content:center' },
      [
        h('div', { style: { position: 'absolute', inset: 0, backgroundColor: color, opacity } }),
        h(Loading, {
          loading: true,
          showOverlay: false,
          text: title,
          indicator: () =>
            h(
              'span',
              { class: ['bklog-loading-dots', `bklog-loading-dots--${size}`] },
              Array.from({ length: 4 }, () => h('span')),
            ),
          size: size === 'mini' ? '16px' : size,
        }),
      ],
    );
    vnode.appContext = binding.instance?.$?.appContext ?? null;
    render(vnode, mount.container);
  },
  remove(el) {
    const mount = mounts.get(el);
    if (!mount) return;
    render(null, mount.container);
    mount.container.remove();
    if (mount.positioned && el.style.position === 'relative') el.style.position = mount.originalPosition;
    mounts.delete(el);
  },
});
