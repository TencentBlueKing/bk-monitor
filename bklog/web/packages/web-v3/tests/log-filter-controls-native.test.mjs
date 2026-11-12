import { test } from 'node:test';
import assert from 'node:assert/strict';
import * as Vue from 'vue';
import ts from 'typescript';
import { loadTypeScript } from './helpers/load-typescript.mjs';
const compiler = { jsx: ts.JsxEmit.ReactJSX, jsxImportSource: 'vue' };
const file = new URL(
  '../src/features/collection/current/components/business-comp/step2/log-filter.tsx',
  import.meta.url,
);
const native = Object.fromEntries(
  ['Button', 'Switch', 'Select', 'Textarea', 'Loading'].map((name) => [name, { name }]),
);
const t = (key, values) => key.replace('{n}', values?.n ?? '');
const previousWindow = globalThis.window;
let utils;
try {
  globalThis.window = { $t: t, mainComponent: { $t: t } };
  utils = loadTypeScript(new URL('../src/features/collection/current/utils.ts', import.meta.url), {
    'tdesign-vue-next': {MessagePlugin:{error(){}}},
    './save-failure': loadTypeScript(new URL('../src/features/collection/current/save-failure.ts', import.meta.url)),
    '@/shared/utils/typed-record': { asDictionary: (v) => v, includesValue: (list, value) => list.includes(value) },
    '@/shared/lib/util': { formatFileSize: String, random: () => '' },
  });
} finally {
  globalThis.window = previousWindow;
}
const worker = loadTypeScript(new URL('../src/shared/lib/worker-message.ts', import.meta.url), { vue: Vue });
function all(n) {
  return !n || typeof n !== 'object' ? [] : Array.isArray(n) ? n.flatMap(all) : [n, ...all(n.children)];
}
function setup(conditions = { type: 'none' }, response = { data: { fields: [] } }) {
  const mounted = [],
    requests = [],
    calls = [],
    scope = Vue.effectScope();
  let exposed;
  const component = loadTypeScript(
    file,
    {
      vue: { ...Vue, onMounted: (fn) => mounted.push(fn) },
      'tdesign-vue-next': native,
      '@/platform/services': {
        ServicesInstance: {
          clean: {
            getEtlPreview: async (payload) => {
              requests.push(payload);
              return response;
            },
          },
        },
      },
      '@/shared/composables/use-locale': () => ({ t }),
      '@/app/state/domains/globals-store': {useGlobalsStore: () => ({globalsData: {data_delimiter: [{id:'|',name:'pipe'},{id:',',name:'comma'}]}})},
      '@/app/state/domains/collection-store': {useCollectionStore: () => ({curCollect:{}})},
      '@/shared/lib/worker-message': worker,
      '../../../utils': utils,
      '../../common-comp/info-tips': { name: 'InfoTips' },
      './validator-input': { name: 'ValidatorInput' },
      './log-filter.scss': {},
    },
    compiler,
  ).default;
  const props = Vue.reactive({ conditions, isCloneOrUpdate: false });
  const render = scope.run(() =>
    component.setup(props, {
      emit: (...args) => calls.push(args),
      expose: (value) => {
        exposed = value;
      },
    }),
  );
  mounted.forEach((fn) => fn());
  return { render, exposed, requests, calls, scope, find: (type) => all(render()).find((n) => n.type === type) };
}
test('sample textarea emits text into the unchanged delimiter-preview API and returns original option metadata', async () => {
  const vm = setup({ type: 'separator', separator: '|' }, { data: { fields: [{ field_index: 2, value: 'error' }] } });
  await Vue.nextTick();
  vm.find(native.Textarea).props.onChange('alpha|error|omega');
  assert.equal(vm.find(native.Textarea).props.value, 'alpha|error|omega');
  const debug = all(vm.render()).find((n) => n.type === native.Button && n.props.theme === 'primary');
  assert.equal(debug.props.disabled, false);
  await debug.props.onClick();
  assert.deepEqual(vm.requests, [
    { data: { etl_config: 'bk_log_delimiter', etl_params: { separator: '|' }, data: 'alpha|error|omega' } },
  ]);
  const validator = all(vm.render()).find((n) => n.type?.name === 'ValidatorInput' && n.props.inputType === 'number');
  assert.deepEqual(validator.props.originalFilterItemSelect, [{ id: '2', name: '第2列 | error', value: 'error' }]);
  vm.scope.stop();
});
test('mode cache survives Vue3 proxies and restores independent draft rules', async () => {
  const vm = setup({ type: 'match', match_content: 'original', match_type: 'include' });
  await Vue.nextTick();
  const buttons = () => all(vm.render()).filter((n) => n.type === native.Button && n.props.size === 'small');
  assert.doesNotThrow(() => buttons()[1].props.onClick());
  const value = all(vm.render()).find((n) => n.type?.name === 'ValidatorInput' && !n.props.inputType);
  value.props.onChange('separator-draft');
  buttons()[0].props.onClick();
  const restored = all(vm.render()).find((n) => n.type?.name === 'ValidatorInput' && !n.props.inputType);
  assert.equal(restored.props.value, 'original');
  buttons()[1].props.onClick();
  assert.equal(
    all(vm.render()).find((n) => n.type?.name === 'ValidatorInput' && !n.props.inputType).props.value,
    'separator-draft',
  );
  vm.scope.stop();
});
test('native delimiter and operator changes preserve condition serialization', async () => {
  const vm = setup({ type: 'separator', separator: '|' });
  await Vue.nextTick();
  const select = all(vm.render()).filter((n) => n.type === native.Select);
  select[0].props.onChange(',');
  select[1].props.onChange('neq');
  const values = all(vm.render()).filter((n) => n.type?.name === 'ValidatorInput');
  values[0].props.onChange('2');
  values[1].props.onChange('error');
  assert.ok(vm.calls.some(([event, payload]) => event === 'conditions-change' && payload.separator === ','));
  const payload = vm.calls.at(-1)[1];
  assert.equal(payload.type, 'separator');
  assert.equal(payload.separator_filters[0].op, 'neq');
  assert.equal(payload.separator_filters[0].fieldindex, '2');
  assert.equal(payload.separator_filters[0].word, 'error');
  vm.scope.stop();
});
