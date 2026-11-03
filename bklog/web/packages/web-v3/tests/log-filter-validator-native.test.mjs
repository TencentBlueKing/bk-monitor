import { test } from 'node:test';
import assert from 'node:assert/strict';
import * as Vue from 'vue';
import ts from 'typescript';
import { loadTypeScript } from './helpers/load-typescript.mjs';
const native = Object.fromEntries(
  ['Form', 'FormItem', 'Input', 'InputNumber', 'Select'].map((name) => [name, { name }]),
);
const Component = loadTypeScript(
  new URL('../src/features/collection/access/components/log-filter/validator-input.tsx', import.meta.url),
  {
    vue: Vue,
    'tdesign-vue-next': native,
    '@/features/collection/shared/sample-column-select': native.Select,
    './validator-input.scss': {},
    '@/platform/i18n/i18n': { t: (key, values) => key.replace('{n}', values?.n ?? '') },
  },
  { jsx: ts.JsxEmit.ReactJSX, jsxImportSource: 'vue' },
).default;
function all(node) {
  return !node || typeof node !== 'object'
    ? []
    : Array.isArray(node)
      ? node.flatMap(all)
      : [node, ...all(node.children)];
}
function setup(extra = {}) {
  const props = Vue.reactive({
    value: '',
    placeholder: '请输入',
    activeType: 'separator',
    inputType: 'text',
    rowData: {},
    originalFilterItemSelect: [],
    ...extra,
  });
  const calls = [],
    scope = Vue.effectScope();
  let exposed;
  const render = scope.run(() =>
    Component.setup(props, {
      emit: (...args) => calls.push(args),
      expose: (value) => {
        exposed = value;
      },
    }),
  );
  return { props, calls, render, exposed, scope, find: (type) => all(render()).find((node) => node.type === type) };
}
test('paired filter validation exactly follows V2 for absent, partial and complete rows', () => {
  for (const [rowData, value, activeType, expected] of [
    [{}, '', 'separator', true],
    [{ fieldindex: '1' }, '', 'separator', false],
    [{ word: 'error' }, '', 'separator', false],
    [{ fieldindex: '1', word: 'error' }, '', 'separator', true],
    [{ word: 'error' }, '2', 'separator', true],
    [{ fieldindex: '1' }, '', 'match', true],
  ]) {
    const vm = setup({ rowData, value, activeType });
    assert.equal(vm.find(native.Form).props.rules.inputValue[0].validator(), expected);
    vm.scope.stop();
  }
});
test('TDesign fulfilled error objects reject parent validation; absent form remains valid', async () => {
  const vm = setup();
  assert.equal(await vm.exposed.validate(), true);
  const form = vm.find(native.Form);
  for (const [result, expected] of [
    [true, true],
    [false, false],
    [{ inputValue: [{ result: false }] }, false],
  ]) {
    form.ref.r.value = { validate: async () => result };
    assert.equal(await vm.exposed.validate(), expected);
  }
  form.ref.r.value = {
    validate: async () => {
      throw Error('validation failed');
    },
  };
  assert.equal(await vm.exposed.validate(), false);
  vm.scope.stop();
});
test('native input drafts and prop restoration emit original string change payloads', async () => {
  const vm = setup({ value: 'old' });
  vm.find(native.Input).props.onChange('new');
  await Vue.nextTick();
  assert.deepEqual(vm.calls, [['change', 'new']]);
  vm.props.value = 'restored';
  await Vue.nextTick();
  assert.equal(vm.find(native.Input).props.value, 'restored');
  vm.find(native.Input).props.onChange('');
  await Vue.nextTick();
  assert.deepEqual(vm.calls.at(-1), ['change', '']);
  vm.scope.stop();
});
test('sample row selector preserves id/name/content, searchable options and fallback labels', async () => {
  const vm = setup({
    value: '2',
    inputType: 'number',
    originalFilterItemSelect: [{ id: '2', name: 'sample two', value: 'error log' }],
  });
  const select = vm.find(native.Select);
  assert.deepEqual(select.props.options, [{ id: '2', name: 'sample two', value: 'error log' }]);
  assert.equal(all(select.children.default()).find((n) => n.type === 'span').children, 'sample two');
  select.props.onChange('3');
  await Vue.nextTick();
  assert.deepEqual(vm.calls.at(-1), ['change', '3']);
  assert.equal(all(vm.find(native.Select).children.default()).find((n) => n.type === 'span').children, '第3行');
  vm.scope.stop();
});
test('numeric display enters editing, focuses input and preserves string model on change/clear', async () => {
  const vm = setup({ value: '2', inputType: 'number' });
  await all(vm.render())
    .find((n) => n.props?.onClick)
    .props.onClick();
  const number = vm.find(native.InputNumber);
  assert.equal(number.props.min, 1);
  assert.equal(number.props.theme, 'normal');
  let focused = 0;
  number.ref.r.value = {
    focus() {
      focused++;
    },
  };
  await all(vm.render())
    .find((n) => n.props?.onClick)
    .props.onClick();
  assert.equal(focused, 1);
  number.props.onChange(3);
  await Vue.nextTick();
  assert.deepEqual(vm.calls.at(-1), ['change', '3']);
  number.props.onChange(undefined);
  await Vue.nextTick();
  assert.deepEqual(vm.calls.at(-1), ['change', '']);
  vm.scope.stop();
});

const CurrentComponent = loadTypeScript(
  new URL('../src/features/collection/current/components/business-comp/step2/validator-input.tsx', import.meta.url),
  {
    vue: Vue,
    'tdesign-vue-next': native,
    '@/features/collection/shared/sample-column-select': native.Select,
    './validator-input.scss': {},
    '@/shared/composables/use-locale': () => ({ t: (key, values) => key.replace('{n}', values?.n ?? '') }),
  },
  { jsx: ts.JsxEmit.ReactJSX, jsxImportSource: 'vue' },
).default;
function current(extra = {}) {
  const props = Vue.reactive({
    value: '',
    placeholder: '请输入',
    activeType: 'separator',
    inputType: 'text',
    rowData: {},
    originalFilterItemSelect: [],
    ...extra,
  });
  const calls = [],
    scope = Vue.effectScope();
  let exposed;
  const render = scope.run(() =>
    CurrentComponent.setup(props, {
      emit: (...args) => calls.push(args),
      expose: (value) => {
        exposed = value;
      },
    }),
  );
  return { props, render, calls, exposed, scope, find: (type) => all(render()).find((node) => node.type === type) };
}
test('current collection branch preserves its separate required-value contract and clears feedback on valid input', async () => {
  const vm = current({ value: '   ' });
  assert.equal(vm.exposed.validateValue(), false);
  assert.equal(vm.find(native.Input).props.class.includes('input-error'), true);
  vm.find(native.Input).props.onChange('valid');
  await Vue.nextTick();
  assert.equal(vm.exposed.validateValue(), true);
  assert.equal(vm.find(native.Input).props.class.includes('input-error'), false);
  assert.deepEqual(vm.calls.at(-1), ['change', 'valid']);
  vm.find(native.Input).props.onChange('');
  await Vue.nextTick();
  assert.equal(vm.exposed.validateValue(), false);
  vm.scope.stop();
});
test('current sample selector uses native options and emits exact string ids with validation feedback reset', async () => {
  const vm = current({ originalFilterItemSelect: [{ id: '1', name: 'first', value: 'sample' }] });
  assert.equal(vm.exposed.validateValue(), false);
  const select = vm.find(native.Select);
  assert.deepEqual(select.props.options, [{ id: '1', name: 'first', value: 'sample' }]);
  select.props.onChange('1');
  await Vue.nextTick();
  assert.deepEqual(vm.calls.at(-1), ['change', '1']);
  assert.equal(vm.find(native.Select).props.class.includes('input-error'), false);
  assert.equal(vm.exposed.validateValue(), true);
  vm.scope.stop();
});

test('focus keeps empty numeric trigger mounted while entering its first value', async () => {
  for (const factory of [setup, current]) {
    const vm = factory({ inputType: 'number' });
    vm.find(native.InputNumber).props.onFocus();
    vm.find(native.InputNumber).props.onChange('5');
    await Vue.nextTick();
    assert.equal(vm.find(native.InputNumber).props.value, '5');
    assert.equal(vm.find(native.InputNumber).props.largeNumber, true);
    vm.find(native.InputNumber).props.onBlur();
    assert.equal(vm.find(native.InputNumber), undefined);
    assert.deepEqual(vm.calls.at(-1), ['change', '5']);
    vm.scope.stop();
  }
});
