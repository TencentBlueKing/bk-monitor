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

function fixture(overrides = {}) {
  const events = [];
  const Popup = { name: 'NativePopup' };
  const component = loadTypeScript(new URL('../src/shared/ui/bk-search-select/index.tsx', import.meta.url), {
    vue: { ...Vue, onBeforeUnmount() {} },
    'tdesign-vue-next': { Popup, Checkbox: {} },
    '@/shared/global/overlay/overlay-registry.js': { overlayRegistry: { nextZIndex: () => 3000 } },
    '@/shared/composables/use-locale': () => ({ t: x => x }),
    './index.scss': {},
  }, { jsx: ts.JsxEmit.ReactJSX, jsxImportSource: 'vue' }).default;
  const props = Object.fromEntries(Object.entries(component.props).map(([key, value]) => [key, typeof value.default === 'function' && value.type !== Function ? value.default() : value.default]));
  Object.assign(props, { data: [{ id: 'collector_config_name', name: '采集名' }] }, overrides);
  const scope = Vue.effectScope();
  const model = scope.run(() => component.setup(props, { emit: (...args) => events.push(args) }));
  return { model, events, component, props, scope };
}

test('focus followed by the same Popup click cannot close the field menu or clear the draft', () => {
  const f = fixture({ inputUnfocusClear: true });
  try {
    f.model.handleFocus();
    assert.equal(f.model.menuVisible.value, true);
    f.model.handleVisibleChange(false, { trigger: 'trigger-element-click' });
    assert.equal(f.model.input.focus, true);
    assert.equal(f.model.menuVisible.value, true);
    f.model.updateInput('采集名：draft');
    f.model.handleVisibleChange(false, { trigger: 'trigger-element-click' });
    assert.equal(f.model.input.value, '采集名：draft');
    assert.equal(f.events.some(([event]) => event === 'input-click-outside'), false);
    f.model.handleVisibleChange(false, { trigger: 'document' });
    assert.equal(f.model.menuVisible.value, false);
    assert.equal(f.model.input.focus, false);
    assert.equal(f.model.input.value, '');
    assert.equal(f.events.filter(([event]) => event === 'input-click-outside').length, 1);
  } finally { f.scope.stop(); }
});

test('blank input area click focuses the editor without emitting search or changing values', () => {
  const f = fixture();
  try {
    let focused = 0;
    const vm = new Proxy(f.model, { get: (target, key) => key === 'inputRef' ? { focus: () => focused++ } : key in target ? Vue.unref(target[key]) : f.props[key] });
    const popup = f.component.render.call(vm);
    const root = popup.children[0];
    const inputArea = root.children[0].children[0];
    inputArea.props.onClick();
    assert.equal(focused, 1);
    assert.equal(f.events.length, 0);
    assert.deepEqual(f.model.chips.value, []);
  } finally { f.scope.stop(); }
});


test('selecting a field places caret after prefix, preserves search payload and still closes on outside click', async () => {
  const f = fixture({ showPopoverTagChange: false });
  try {
    const actions = [];
    const range = { selectNodeContents: element => actions.push(['select', element]), collapse: end => actions.push(['collapse', end]) };
    const editor = Vue.markRaw({ innerText: '', focus: () => actions.push(['focus']), ownerDocument: {
      getSelection: () => ({ removeAllRanges: () => actions.push(['clear']), addRange: value => actions.push(['range', value]) }),
      createRange: () => range,
    } });
    f.model.inputRef.value = editor;
    f.model.handleFocus();
    f.model.renderMenu().children[0].children.flat(Infinity).find(node => node?.props?.class === 'bk-search-list-menu-item').props.onClick();
    await Vue.nextTick();
    assert.equal(f.model.input.value, '采集名：');
    assert.deepEqual(actions, [['focus'], ['select', editor], ['collapse', false], ['clear'], ['range', range]]);
    f.model.updateInput('采集名：主机采集示例');
    await f.model.handleKeyEnter();
    const change = f.events.find(([name]) => name === 'change');
    assert.equal(change[1][0].id, 'collector_config_name');
    assert.deepEqual(change[1][0].values, [{ id: '主机采集示例', name: '主机采集示例' }]);
    f.model.handleBlur();
    assert.equal(f.model.input.focus, false);
    f.model.handleVisibleChange(false, { trigger: 'document' });
    assert.equal(f.model.input.focus, false);
    assert.equal(f.events.filter(([name]) => name === 'input-click-outside').length, 1);
  } finally { f.scope.stop(); }
});
