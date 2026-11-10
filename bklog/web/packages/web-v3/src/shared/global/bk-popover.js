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

import tippy from 'tippy.js';

import Vue from '@/platform/compat/vue-runtime.mjs';

import { overlayRegistry } from './overlay/overlay-registry.js';
import { Z_INDEX_LAYERS } from './overlay/z-index-manager.js';

const PLACEMENT = {
  top: 'top',
  'top-start': 'top-start',
  'top-end': 'top-end',
  'top-center': 'top',
  bottom: 'bottom',
  'bottom-start': 'bottom-start',
  'bottom-end': 'bottom-end',
  'bottom-center': 'bottom',
  left: 'left',
  'left-start': 'left-start',
  'left-end': 'left-end',
  right: 'right',
  'right-start': 'right-start',
  'right-end': 'right-end',
};

function resolveContent(content) {
  if (!content) return '';
  if (typeof content === 'function') return resolveContent(content());
  return content.$el || content;
}

export function $bkPopover(target, options = {}) {
  const themeNames = String(options.theme || '')
    .split(/\s+/)
    .filter(Boolean);
  const distance = Number(options.distance ?? 8);
  const instance = tippy(target, {
    content: resolveContent(options.content),
    placement: PLACEMENT[options.placement] || options.placement || 'top',
    trigger: options.trigger || 'manual',
    interactive: options.interactive !== false,
    arrow: options.arrow !== false,
    appendTo: () => document.body,
    hideOnClick: options.hideOnClick ?? true,
    maxWidth: options.maxWidth ?? 'none',
    zIndex: options.zIndex ?? Z_INDEX_LAYERS.DROPDOWN,
    offset: [Number(options.offset) || 0, Number.isFinite(distance) ? distance : 8],
    onCreate(created) {
      themeNames.forEach(name => {
        created.popper.classList.add(`${name}-theme`);
      });
    },
    onHidden(created) {
      options.onHidden?.(created);
    },
    onShow(created) {
      if (options.zIndex == null) created.setProps({ zIndex: overlayRegistry.nextZIndex() });
      return options.onShow?.(created);
    },
  });
  return instance;
}

if (typeof Vue.prototype.$bkPopover !== 'function') {
  Vue.prototype.$bkPopover = $bkPopover;
}
