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
import * as Vue from 'vue';
import ts from 'typescript';
import { loadTypeScript } from './helpers/load-typescript.mjs';
const controls = Object.fromEntries(['Button', 'Checkbox', 'Input', 'Popup'].map((name) => [name, { name }]));
const component = loadTypeScript(
  new URL(
    '../src/features/retrieval/workspace/search-result/log-clustering/log-table/main-header/filter-operate/index.tsx',
    import.meta.url,
  ),
  {
    'tdesign-vue-next': controls,
    '@/shared/composables/use-locale': () => ({ t: (text) => text }),
    './index.scss': {},
  },
  { jsx: ts.JsxEmit.ReactJSX, jsxImportSource: 'vue' },
).default;
function fixture(multiple = true) {
  const events = [],
    scope = Vue.effectScope();
  let exposed;
  const render = scope.run(() =>
    component.setup(
      {
        multiple,
        searchable: true,
        list: [
          { id: 'alice', name: 'Alice' },
          { id: 'bob', name: 'Bob' },
        ],
      },
      {
        emit: (...args) => events.push(args),
        expose: (value) => {
          exposed = value;
        },
      },
    ),
  );
  const panel = () => render().props['v-slots'].content();
  return {
    render,
    panel,
    events,
    reset: () => exposed.reset(),
    stop: () => scope.stop(),
    options: () =>
      panel()
        .children[1].children.flat()
        .filter((node) => node?.type?.name === 'Checkbox'),
    buttons: () => panel().children[2].children,
  };
}
test('native header renders only a funnel trigger and retains explicit confirm/reset draft semantics', () => {
  const f = fixture();
  try {
    const popup = f.render();
    assert.equal(popup.type.name, 'Popup');
    assert.equal(popup.children.length, 1);
    assert.equal(popup.children[0].type, 'button');
    popup.props.onVisibleChange(true);
    f.options()[0].props.onChange(true);
    assert.deepEqual(f.events, []);
    f.buttons()[0].props.onClick();
    assert.deepEqual(f.events, [['confirm', ['alice']]]);
    assert.equal(f.render().props.visible, false);
    f.buttons()[1].props.onClick();
    assert.deepEqual(f.events.at(-1), ['confirm', []]);
  } finally {
    f.stop();
  }
});
test('remark single selection toggles and replaces using V2 array contract; search reset does not submit', () => {
  const f = fixture(false);
  try {
    f.options()[0].props.onChange(true);
    f.options()[1].props.onChange(true);
    f.buttons()[0].props.onClick();
    assert.deepEqual(f.events, [['confirm', ['bob']]]);
    f.options()[1].props.onChange(false);
    f.buttons()[0].props.onClick();
    assert.deepEqual(f.events.at(-1), ['confirm', []]);
    f.panel().children[0].props.onChange(' ALI ');
    assert.equal(f.options().length, 1);
    f.render().props.onVisibleChange(false);
    assert.equal(f.options().length, 2);
    f.reset();
    assert.equal(f.options()[0].props.checked, false);
  } finally {
    f.stop();
  }
});
