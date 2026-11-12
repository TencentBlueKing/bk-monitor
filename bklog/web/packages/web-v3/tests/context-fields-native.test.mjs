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
import ts from 'typescript';
import * as Vue from 'vue';
import { loadTypeScript } from './helpers/load-typescript.mjs';
const base = new URL(
  '../src/features/retrieval/workspace/search-result/original-log/components/data-filter/fields-config/',
  import.meta.url
);
const { getDefaultDisplayFields } = loadTypeScript(new URL('default-display-fields.ts', base));
const { preserveVue3ComponentModel } = loadTypeScript(
  new URL('../src/platform/compat/vue3-component-model.ts', import.meta.url)
);
async function setup() {
  const events = [],
    calls = [],
    messages = [],
    scope = Vue.effectScope(),
    Draggable = {};
  let resolveWrite;
  const fields = [
    { field_name: 'log', field_type: 'text' },
    { field_name: 'serverIp', field_type: 'keyword' },
    { field_name: 'path', field_type: 'keyword' },
  ];
  const store = {
    getters: { filteredFieldList: fields, rawFieldList: fields },
    state: Vue.reactive({
      retrieve: { catchFieldCustomConfig: { contextDisplayFields: ['log', 'serverIp'] } },
    }),
    dispatch: (action, data) => {
      calls.push({ action, data: JSON.parse(JSON.stringify(data)) });
      return new Promise((resolve) => {
        resolveWrite = resolve;
      });
    },
  };
  const component = loadTypeScript(
    new URL('index.tsx', base),
    {
      vue: { ...Vue, resolveComponent: (name) => name },
      'tdesign-vue-next': { Button: 'native-button' },
      '@/shared/lib/message': { messageSuccess: (message) => messages.push(message) },
      '@/shared/composables/use-locale': () => ({ t: (key) => key }),
      '@/app/state/domains/retrieve-store': { useRetrieveStore: () => ({ ...store.state.retrieve, $state: store.state.retrieve, sceneConfigList: store.getters['retrieve/sceneConfigList'] }) },
      '@/shared/composables/use-store': () => store,
      'vuedraggable-vue3': Draggable,
      '@/platform/compat/vue3-component-model': { preserveVue3ComponentModel },
      './default-display-fields': { getDefaultDisplayFields },
      './index.scss': {},
    },
    { jsx: ts.JsxEmit.ReactJSX, jsxImportSource: 'vue' }
  ).default;
  let exposed;
  const render = scope.run(() =>
    component.setup(
      {},
      {
        emit: (...args) => events.push(JSON.parse(JSON.stringify(args))),
        expose: (value) => {
          exposed = value;
        },
      }
    )
  );
  await new Promise((resolve) => setTimeout(resolve, 0));
  const flatten = (n) =>
    Array.isArray(n) ? n.flatMap(flatten) : n && typeof n === 'object' ? [n, ...flatten(n.children)] : [];
  const nodes = () => flatten(render()),
    drag = () => nodes().find((n) => typeof n.props?.itemKey === 'function'),
    button = (text) =>
      nodes().find(
        (n) =>
          n.type === 'native-button' &&
          (Array.isArray(n.children) ? n.children.join('') : n.children) === text
      );
  const item = (index) => drag().props['v-slots'].item({ element: drag().props.modelValue[index], index });
  const remove = (index) =>
    flatten(item(index))
      .find((n) => String(n.props?.class).split(' ').includes('operate-button'))
      .props.onClick();
  const add = (name) => {
    const row = nodes().find(
      (n) =>
        n.props?.class === 'list-item rest-item' &&
        flatten(n).some(
          (c) =>
            c.props?.class === 'field_name' &&
            (Array.isArray(c.children) ? c.children.join('') : c.children) === name
        )
    );
    flatten(row)
      .find((n) => n.props?.class === 'operate-button')
      .props.onClick();
  };
  return {
    events,
    calls,
    messages,
    store,
    originalDraggable: Draggable,
    nodes,
    drag,
    button,
    remove,
    add,
    exposed,
    resolve: () => resolveWrite(),
    close: () => scope.stop(),
  };
}
async function run(fn) {
  const h = await setup();
  try {
    await fn(h);
  } finally {
    h.close();
  }
}
test('context-fields-native-drag-keeps-source-order-and-slot-contract', () =>
  run((h) => {
    assert.equal(h.originalDraggable.compatConfig, undefined);
    assert.deepEqual(h.drag().props.modelValue, ['log', 'serverIp']);
    assert.equal(h.drag().props.itemKey('serverIp'), 'serverIp');
    assert.equal(h.drag().props.tag, 'transition-group');
    assert.deepEqual(h.drag().props.componentData, { tag: 'ul' });
    assert.equal(h.drag().type.compatConfig.COMPONENT_V_MODEL, false);
    assert.equal(h.drag().type.compatConfig.RENDER_FUNCTION, false);
  }));
test('context-fields-last-display-field-cannot-be-removed', () =>
  run((h) => {
    h.remove(0);
    assert.deepEqual(h.drag().props.modelValue, ['serverIp']);
    h.remove(0);
    assert.deepEqual(h.drag().props.modelValue, ['serverIp']);
    assert.equal(h.calls.length, 0);
  }));
test('context-fields-add-reorder-cancel-restores-draft-without-write', () =>
  run((h) => {
    h.add('path');
    h.drag().props['onUpdate:modelValue'](['path', 'serverIp', 'log']);
    assert.deepEqual(h.drag().props.modelValue, ['path', 'serverIp', 'log']);
    h.button('取消').props.onClick();
    assert.deepEqual(h.drag().props.modelValue, ['log', 'serverIp']);
    assert.deepEqual(h.events.at(-1), ['cancel']);
    assert.equal(h.calls.length, 0);
  }));
test('context-fields-confirm-writes-complete-order-once-and-resolves-loading', () =>
  run(async (h) => {
    h.add('path');
    h.drag().props['onUpdate:modelValue'](['path', 'log', 'serverIp']);
    h.button('确定').props.onClick();
    assert.equal(h.button('确定').props.loading, true);
    assert.deepEqual(h.calls, [
      { action: 'userFieldConfigChange', data: { contextDisplayFields: ['path', 'log', 'serverIp'] } },
    ]);
    h.resolve();
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
    assert.equal(h.button('确定').props.loading, false);
    assert.deepEqual(h.events.at(-1), ['success', ['path', 'log', 'serverIp']]);
    assert.deepEqual(h.messages, ['设置成功']);
  }));
test('context-fields-external-config-updates-cancel-snapshot', () =>
  run(async (h) => {
    h.store.state.retrieve.catchFieldCustomConfig = { contextDisplayFields: ['path'] };
    await Vue.nextTick();
    await new Promise((resolve) => setTimeout(resolve, 0));
    assert.deepEqual(h.drag().props.modelValue, ['path']);
    h.add('log');
    h.button('取消').props.onClick();
    assert.deepEqual(h.drag().props.modelValue, ['path']);
    assert.equal(h.calls.length, 0);
  }));
