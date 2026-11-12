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
import { loadTypeScript } from './helpers/load-typescript.mjs';
import { h } from 'vue';

test('IP selector dialog host does not inherit page height; inline mode retains sizing', () => {
  const factory = loadTypeScript(new URL('../src/features/collection/ip-selector/bk-ip-selector-vue3.js', import.meta.url), {
    vue: { h },
    '@blueking/ip-selector/dist/vue2.6.x.esm': { merge() {}, Component: { props: {}, emits: [] } },
  }).default;
  const component = factory({});
  for (const showDialog of [false, true]) {
    const dialog = component.render.call({ mode: 'dialog', showDialog });
    assert.equal(dialog.props.style.height, 'auto');
    assert.equal(dialog.props.role, 'bk-ip-selector');
    assert.equal(dialog.ref.r, 'rootRef');
  }
  for (const mode of ['section', undefined]) {
    assert.equal(component.render.call({ mode }).props.style.height, 'inherit');
  }
});
