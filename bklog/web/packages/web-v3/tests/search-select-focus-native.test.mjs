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
  const helpers = loadTypeScript(new URL('../src/shared/ui/bk-search-select/helpers.ts', import.meta.url));
  const component = loadTypeScript(new URL('../src/shared/ui/bk-search-select/index.tsx', import.meta.url), {
    vue: { ...Vue, onBeforeUnmount() {} },
    'tdesign-vue-next': { Popup, Checkbox: {} },
    '@/shared/global/overlay/overlay-registry.js': { overlayRegistry: { nextZIndex: () => 3000 } },
    '@/shared/composables/use-locale': () => ({ t: x => x }),
    './helpers': helpers,
    './index.scss': {},
  }, { jsx: ts.JsxEmit.ReactJSX, jsxImportSource: 'vue' }).default;
  const props = Object.fromEntries(Object.entries(component.props).map(([key, value]) => [key, typeof value.default === 'function' && value.type !== Function ? value.default() : value.default]));
  Object.assign(props, { data: [{ id: 'collector_config_name', name: '采集名' }] }, overrides);
  const scope = Vue.effectScope();
  const model = scope.run(() => component.setup(props, { emit: (...args) => events.push(args) }));
  return { model, events, component, props, scope, helpers };
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
    f.model.updateInput('采集名：合成采集样本');
    await f.model.handleKeyEnter();
    const change = f.events.find(([name]) => name === 'change');
    assert.equal(change[1][0].id, 'collector_config_name');
    assert.deepEqual(change[1][0].values, [{ id: '合成采集样本', name: '合成采集样本' }]);
    f.model.handleBlur();
    assert.equal(f.model.input.focus, false);
    f.model.handleVisibleChange(false, { trigger: 'document' });
    assert.equal(f.model.input.focus, false);
    assert.equal(f.events.filter(([name]) => name === 'input-click-outside').length, 1);
  } finally { f.scope.stop(); }
});

test('multiable field keeps unselected options visible while checking items, supports Backspace pop and confirm footer', async () => {
  const f = fixture({
    showPopoverTagChange: false,
    data: [{
      id: 'name_en',
      name: '数据名',
      multiable: true,
      children: [
        { id: '13345', name: '13345' },
        { id: '20261113T', name: '20261113T' },
        { id: 'synthetic_alpha', name: 'synthetic_alpha' },
      ],
    }],
  });
  try {
    f.model.handleFocus();
    const fieldItems = f.model.renderMenu().children[0].children.flat(Infinity).filter(n => n?.props?.class?.includes?.('bk-search-list-menu-item'));
    fieldItems[0].props.onClick();
    await Vue.nextTick();
    assert.equal(f.model.input.value, '数据名：');

    // Check first and second options
    let childItems = f.model.renderMenu().children[0].children.flat(Infinity).filter(n => n?.props?.class?.includes?.('bk-search-list-menu-item'));
    assert.equal(childItems.length, 3);
    childItems[0].props.onClick();
    childItems[1].props.onClick();
    assert.equal(f.model.input.value, '数据名：13345 | 20261113T');
    assert.deepEqual(Object.keys(f.model.menu.checked), ['13345', '20261113T']);

    // All 3 options remain visible in multi-select dropdown
    childItems = f.model.renderMenu().children[0].children.flat(Infinity).filter(n => n?.props?.class?.includes?.('bk-search-list-menu-item'));
    assert.equal(childItems.length, 3);

    // Backspace pops only the last checked item
    f.model.handleKeydown({ key: 'Backspace', preventDefault() {} });
    assert.equal(f.model.input.value, '数据名：13345');
    assert.deepEqual(Object.keys(f.model.menu.checked), ['13345']);

    // Re-check second item and click confirm footer button
    childItems[1].props.onClick();
    const footerBtns = f.model.renderMenu().children[1].children.flat(Infinity);
    footerBtns[0].props.onClick();
    const change = f.events.find(([name]) => name === 'change');
    assert.equal(change[1][0].id, 'name_en');
    assert.deepEqual(change[1][0].values.map(v => v.id), ['13345', '20261113T']);
  } finally { f.scope.stop(); }
});

test('computeSearchSelectOverflow handles single chip, leading fit, and oversized first chip + short recent chip', () => {
  const f = fixture();
  try {
    const { computeSearchSelectOverflow, splitHighlightSegments } = f.helpers;
    // Single oversized chip never collapses to +1
    assert.deepEqual(
      computeSearchSelectOverflow({ chipWidths: [500], availableWidth: 300 }),
      { visibleIndices: [0], hiddenIndices: [] },
    );
    // All chips fit
    assert.deepEqual(
      computeSearchSelectOverflow({ chipWidths: [100, 110], availableWidth: 300 }),
      { visibleIndices: [0, 1], hiddenIndices: [] },
    );
    // Leading chips fit alongside +N
    assert.deepEqual(
      computeSearchSelectOverflow({ chipWidths: [120, 120, 120], availableWidth: 310 }),
      { visibleIndices: [0, 1], hiddenIndices: [2] },
    );
    // Oversized first chip + short second chip keeps recent chip visible alongside +1
    assert.deepEqual(
      computeSearchSelectOverflow({ chipWidths: [520, 180], availableWidth: 360 }),
      { visibleIndices: [1], hiddenIndices: [0] },
    );
    // Highlight segment splitting is case-insensitive
    assert.deepEqual(splitHighlightSegments('Agent_Test', 'test'), [
      { text: 'Agent_', matched: false },
      { text: 'Test', matched: true },
    ]);
  } finally { f.scope.stop(); }
});
