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

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import ts from 'typescript';
import { h, ref } from 'vue';

test('related resize preserves direction, bounds and release/cancel/unmount cleanup', () => {
  const source = readFileSync(new URL('../src/platform/compat/tdesign/legacy-bk-controls.tsx', import.meta.url), 'utf8');
  const code = source.slice(source.indexOf('const BkResizeLayout ='), source.indexOf('const BkSideslider ='));
  const output = ts.transpileModule(code + '\nexports.component = BkResizeLayout;', { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText;
  for (const placement of ['bottom', 'top', 'left', 'right']) {
    const handlers = new Map();
    let dispose;
    const scope = { defineComponent: x => x, mode3: {}, ensureResizeLayoutStyle() {}, h, ref, watch() {}, onBeforeUnmount: fn => { dispose = fn; }, window: { addEventListener: (event, fn) => handlers.set(event, fn), removeEventListener: event => handlers.delete(event) } };
    const exports = {};
    new Function('exports', ...Object.keys(scope), output)(exports, ...Object.values(scope));
    const render = exports.component.setup({ placement, initialDivide: 250, min: 42, max: 400 }, { attrs: {}, slots: {} });
    const aside = () => render().children[placement === 'left' || placement === 'top' ? 0 : 1];
    const trigger = () => aside().children[0];
    assert.equal(trigger().props.class, 'bk-resize-trigger');
    const start = () => trigger().props.onPointerdown({ preventDefault() {}, clientX: 300, clientY: 300 });
    start();
    assert.match(trigger().props.class, /(?:^| )is-dragging(?: |$)/);
    handlers.get('pointermove')({ clientX: 200, clientY: 200 });
    const dimension = placement === 'top' || placement === 'bottom' ? 'height' : 'width';
    assert.equal(aside().props.style[dimension], placement === 'bottom' || placement === 'right' ? '350px' : '150px');
    handlers.get('pointermove')({ clientX: -1000, clientY: -1000 });
    assert.equal(aside().props.style[dimension], placement === 'bottom' || placement === 'right' ? '400px' : '42px');
    handlers.get('pointerup')();
    assert.equal(trigger().props.class, 'bk-resize-trigger');
    assert.equal(handlers.size, 0);
    start(); handlers.get('pointercancel')(); assert.equal(handlers.size, 0);
    start(); dispose(); assert.equal(handlers.size, 0);
  }
});
