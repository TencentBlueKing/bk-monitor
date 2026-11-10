import { test } from 'node:test';
import assert from 'node:assert/strict';
import * as Vue from 'vue';
import ts from 'typescript';
import { loadTypeScript } from './helpers/load-typescript.mjs';
const native = Object.fromEntries(['Empty', 'Input', 'List', 'ListItem', 'Popup'].map((name) => [name, { name }]));
const Component = loadTypeScript(
  new URL('../src/features/collection/shared/sample-column-select.tsx', import.meta.url),
  {
    vue: Vue,
    'tdesign-vue-next': native,
    'tdesign-icons-vue-next': { ChevronDownIcon: { name: 'Arrow' }, SearchIcon: { name: 'Search' } },
    '@/platform/i18n/i18n': { t: (key, values) => key.replace('{n}', values?.n ?? '') },
    './sample-column-select.scss': {},
  },
  { jsx: ts.JsxEmit.ReactJSX, jsxImportSource: 'vue' },
).default;
function all(n) {
  return !n || typeof n !== 'object' ? [] : Array.isArray(n) ? n.flatMap(all) : [n, ...all(n.children)];
}
function setup() {
  const props = Vue.reactive({
    value: '2',
    options: [
      { id: '1', name: '第1列 | alpha', value: 'alpha' },
      { id: '2', name: '第2列 | error', value: 'error' },
    ],
  });
  const calls = [],
    scope = Vue.effectScope();
  const render = scope.run(() =>
    Component.setup(props, {
      emit: (...args) => calls.push(args),
      slots: { default: () => Vue.h('input', { 'data-test': 'manual-column', value: props.value }) },
    }),
  );
  const panel = () => render().props.content();
  return { props, calls, render, panel, scope, find: (type) => all(panel()).find((n) => n.type === type) };
}
test('sample search is independent from manual trigger and selected value; outside close resets only search', async () => {
  const vm = setup();
  vm.render().props.onVisibleChange(true);
  assert.equal(all(vm.render()).find((n) => n.type === 'input').props['data-test'], 'manual-column');
  vm.find(native.Input).props.onChange('ERROR');
  await Vue.nextTick();
  assert.equal(all(vm.panel()).filter((n) => n.type === 'li').length, 1);
  assert.equal(vm.props.value, '2');
  assert.deepEqual(vm.calls, []);
  vm.render().props.onVisibleChange(false);
  await Vue.nextTick();
  assert.equal(vm.find(native.Input).props.value, '');
  assert.equal(all(vm.panel()).filter((n) => n.type === 'li').length, 2);
  vm.scope.stop();
});
test('preview option picks retain string ids and close the popup', () => {
  const vm = setup();
  vm.render().props.onVisibleChange(true);
  const option = all(vm.panel()).filter((n) => n.type === 'li')[0];
  assert.equal(all(option).find((n) => n.type === 'span').props.title, '第1行 alpha');
  option.props.onClick();
  assert.deepEqual(vm.calls, [['change', '1']]);
  assert.equal(vm.render().props.visible, false);
  vm.scope.stop();
});
test('keyboard traversal, enter and escape preserve selection without rewriting model on search', async () => {
  const vm = setup();
  const event = (key) => ({ key, preventDefault() {}, stopPropagation() {} });
  const panel = () => vm.panel().props;
  await panel().onKeydown(event('ArrowDown'));
  assert.equal(vm.render().props.visible, true);
  await panel().onKeydown(event('ArrowDown'));
  await panel().onKeydown(event('Enter'));
  assert.deepEqual(vm.calls, [['change', '2']]);
  vm.render().props.onVisibleChange(true);
  await panel().onKeydown(event('Escape'));
  assert.equal(vm.render().props.visible, false);
  vm.scope.stop();
});
