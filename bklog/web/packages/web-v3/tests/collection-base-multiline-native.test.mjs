import { test } from 'node:test';
import assert from 'node:assert/strict';
import * as Vue from 'vue';
import ts from 'typescript';
import { loadTypeScript } from './helpers/load-typescript.mjs';
const root = new URL('../src/features/collection/current/components/business-comp/step2/', import.meta.url);
const native = Object.fromEntries(
  ['Button', 'Form', 'FormItem', 'Input', 'Textarea', 'Tooltip', 'Dialog'].map((name) => [name, { name }]),
);
const compiler = { jsx: ts.JsxEmit.ReactJSX, jsxImportSource: 'vue' };
const t = (key, values) => key.replace('{n}', values?.n ?? '');
function all(n) {
  return !n || typeof n !== 'object' ? [] : Array.isArray(n) ? n.flatMap(all) : [n, ...all(n.children)];
}
function base(extra = {}, response = { data: { allowed: true, message: '' } }) {
  const requests = [],
    calls = [],
    scope = Vue.effectScope();
  let exposed;
  const C = loadTypeScript(
    new URL('base-info.tsx', root),
    {
      vue: Vue,
      'tdesign-vue-next': native,
      '@/platform/services': {
        ServicesInstance: {
          collect: {
            getPreCheck: async (payload) => {
              requests.push(payload);
              return typeof response === 'function' ? response() : response;
            },
          },
        },
      },
      '@/app/state/domains/globals-store': { useGlobalsStore: () => ({ globalsData: { databus_custom: [{ id: 'log', name: '\u65e5\u5fd7' }] } }) },
      '@/shared/composables/use-locale': () => ({ t }),
      '@/shared/composables/use-store': () => ({
        state: { bkBizId: 900001 },
        getters: { 'globals/globalsData': { databus_custom: [{ id: 'log', name: '日志' }] } },
      }),
      '../../common-comp/info-tips': { name: 'InfoTips' },
      './index-set-select': { name: 'IndexSetSelect' },
      '@/shared/lib/util': { xssFilter: (v) => v },
      '../../../hook/useCustomTypeIntro': {
        useCustomTypeIntro: () => ({ customTypeIntro: Vue.ref(''), initProxyHost() {} }),
      },
      './base-info.scss': {},
    },
    compiler,
  ).default;
  const props = Vue.reactive({
    typeKey: 'default',
    data: {
      index_set_name: 'owned draft',
      collector_config_name_en: 'ai_mig_draft',
      parent_index_set_ids: [900101],
      description: '',
    },
    isEdit: false,
    isClone: false,
    ...extra,
  });
  const render = scope.run(() =>
    C.setup(props, {
      emit: (...args) => calls.push(args),
      expose: (value) => {
        exposed = value;
      },
    }),
  );
  return { props, render, exposed, calls, requests, scope, find: (type) => all(render()).find((n) => n.type === type) };
}
test('base form native inputs emit exact values and keep textarea remarks and parent-index selection', () => {
  const vm = base();
  const inputs = all(vm.render()).filter((n) => n.type === native.Input);
  inputs[0].props.onChange('采集草稿');
  inputs[1].props.onChange('ai_mig_owned');
  vm.find(native.Textarea).props.onChange('line one\nline two');
  const value = vm.calls.at(-1)[1];
  assert.equal(value.index_set_name, '采集草稿');
  assert.equal(value.collector_config_name_en, 'ai_mig_owned');
  assert.equal(value.description, 'line one\nline two');
  assert.deepEqual(value.parent_index_set_ids, [900101]);
  vm.scope.stop();
});
test('base form validation keeps reject-on-failure coordinator contract', async () => {
  const vm = base(),
    form = vm.find(native.Form);
  form.ref.r.value = { validate: async () => true };
  assert.equal(await vm.exposed.validate(), true);
  const error = { collector_config_name_en: [{ result: false }] };
  form.ref.r.value = { validate: async () => error };
  await assert.rejects(vm.exposed.validate(), (value) => value === error);
  vm.scope.stop();
});
test('base data-name rules retain required/format/length/precheck and backend error message', async () => {
  const vm = base({}, { data: { allowed: false, message: 'owned fixture duplicate' } });
  const rules = vm.find(native.Form).props.rules.collector_config_name_en;
  assert.equal(rules.length, 5);
  assert.equal(rules[0].validator(), true);
  assert.equal(rules[1].validator(), true);
  assert.deepEqual(await rules[4].validator(), { result: false, message: 'owned fixture duplicate' });
  assert.deepEqual(vm.requests, [{ params: { collector_config_name_en: 'ai_mig_draft', bk_biz_id: 900001 } }]);
  vm.find(native.Input).props.onChange('still named');
  const name = all(vm.render()).filter((n) => n.type === native.Input)[1];
  name.props.onChange('bad-name');
  assert.equal(vm.find(native.Form).props.rules.collector_config_name_en[1].validator(), false);
  name.props.onChange('four');
  assert.equal(vm.find(native.Form).props.rules.collector_config_name_en[2].validator(), false);
  name.props.onChange('x'.repeat(51));
  assert.equal(vm.find(native.Form).props.rules.collector_config_name_en[3].validator(), false);
  vm.scope.stop();
});
test('editing retains disabled data name and skips uniqueness request', async () => {
  const vm = base({ isEdit: true });
  assert.equal(all(vm.render()).filter((n) => n.type === native.Input)[1].props.disabled, true);
  assert.deepEqual(await vm.find(native.Form).props.rules.collector_config_name_en[4].validator(), {
    result: true,
    message: '',
  });
  assert.deepEqual(vm.requests, []);
  vm.scope.stop();
});
function multiline(extra = {}, response = { data: { match_lines: 2 } }) {
  const calls = [],
    requests = [],
    scope = Vue.effectScope();
  const C = loadTypeScript(
    new URL('multiline-reg-dialog.tsx', root),
    {
      vue: Vue,
      'tdesign-vue-next': native,
      '@/platform/services': {
        ServicesInstance: {
          collect: {
            regexDebug: async (payload) => {
              requests.push(payload);
              if (response instanceof Error) throw response;
              return typeof response === 'function' ? response() : response;
            },
          },
        },
      },
      '@/platform/i18n/translation': { name: 'Translation' },
      '@/app/state/domains/globals-store': { useGlobalsStore: () => ({ globalsData: { databus_custom: [{ id: 'log', name: '\u65e5\u5fd7' }] } }) },
      '@/shared/composables/use-locale': () => ({ t }),
      '@/shared/composables/use-store': () => ({ getters: { isEnLanguage: false } }),
      'vue-router': { useRoute: () => ({ params: { collectorId: '10663' } }) },
      './multiline-reg-dialog.scss': {},
    },
    compiler,
  ).default;
  const props = Vue.reactive({ showDialog: true, oldPattern: '^first', ...extra });
  const renderSource = scope.run(() => C.setup(props, { emit: (...args) => calls.push(args) }));
  const render = () => {
    const previous = globalThis.window;
    try {
      globalThis.window = { innerHeight: 720 };
      return renderSource();
    } finally {
      globalThis.window = previous;
    }
  };
  return { props, calls, requests, scope, render, find: (type) => all(render()).find((n) => n.type === type) };
}
test('multiline dialog restores V2 header/top/width and trims both native input drafts', () => {
  const vm = multiline();
  assert.equal(vm.render().props.header, '行首正则调试');
  assert.equal(vm.render().props.top, 170);
  assert.equal(vm.render().props.width, '680');
  assert.equal(vm.render().props.closeOnOverlayClick, false);
  assert.equal(vm.find(native.Input).props.value, '^first');
  vm.find(native.Textarea).props.onChange('  first\nsecond  ');
  vm.find(native.Input).props.onChange('  ^first ');
  assert.equal(vm.find(native.Form).props.data.log_sample, 'first\nsecond');
  assert.equal(vm.find(native.Input).props.value, '^first');
  vm.scope.stop();
});
test('multiline failed TDesign validation never calls preview; successful preview keeps existing payload', async () => {
  const vm = multiline();
  const form = vm.find(native.Form);
  form.ref.r.value = { validate: async () => ({ log_sample: [{ result: false }] }) };
  await vm.find(native.Button).props.onClick();
  assert.deepEqual(vm.requests, []);
  form.ref.r.value = { validate: async () => true };
  vm.find(native.Textarea).props.onChange('first\nsecond');
  await vm.find(native.Button).props.onClick();
  assert.deepEqual(vm.requests, [
    { params: { collector_id: 10663 }, data: { log_sample: 'first\nsecond', multiline_pattern: '^first' } },
  ]);
  assert.equal(vm.find(native.Button).props.loading, false);
  vm.scope.stop();
});
test('multiline confirm emits original update then closes; close clears drafts and next open restores new parent pattern', async () => {
  const vm = multiline();
  let cleared = 0;
  vm.find(native.Form).ref.r.value = {
    clearValidate() {
      cleared++;
    },
  };
  vm.find(native.Input).props.onChange('^saved');
  vm.render().props.onConfirm();
  assert.deepEqual(vm.calls.slice(-2), [
    ['update', '^saved'],
    ['cancel', false],
  ]);
  vm.props.showDialog = false;
  await Vue.nextTick();
  assert.equal(vm.find(native.Form).props.data.log_sample, '');
  assert.equal(vm.find(native.Input).props.value, '');
  assert.equal(cleared, 1);
  vm.props.oldPattern = '^reopened';
  vm.props.showDialog = true;
  await Vue.nextTick();
  assert.equal(vm.find(native.Input).props.value, '^reopened');
  vm.scope.stop();
});

test('line-rule native inputs preserve all collection parameters and required validation', () => {
  const scope = Vue.effectScope(),
    calls = [];
  let exposed;
  const C = loadTypeScript(
    new URL('line-rule-config.tsx', root),
    {
      vue: Vue,
      'tdesign-vue-next': native,
      '@/app/state/domains/globals-store': { useGlobalsStore: () => ({ globalsData: { databus_custom: [{ id: 'log', name: '\u65e5\u5fd7' }] } }) },
      '@/shared/composables/use-locale': () => ({ t }),
      './multiline-reg-dialog': { name: 'Multiline' },
      '../../common-comp/info-tips': { name: 'InfoTips' },
      './line-rule-config.scss': {},
    },
    compiler,
  ).default;
  const props = Vue.reactive({
    data: {
      multiline_pattern: '',
      multiline_max_lines: '50',
      multiline_timeout: '2',
      paths: [{ value: '/owned/test.log' }],
    },
  });
  const render = scope.run(() =>
    C.setup(props, {
      emit: (...args) => calls.push(args),
      expose: (value) => {
        exposed = value;
      },
    }),
  );
  assert.equal(exposed.validate(), false);
  const inputs = all(render()).filter((n) => n.type === native.Input);
  inputs[0].props.onChange('^first');
  assert.deepEqual(calls.at(-1), ['update', { ...props.data, multiline_pattern: '^first' }]);
  props.data = calls.at(-1)[1];
  assert.equal(exposed.validate(), true);
  inputs[1].props.onChange('70');
  assert.equal(calls.at(-1)[1].multiline_max_lines, '70');
  assert.deepEqual(calls.at(-1)[1].paths, [{ value: '/owned/test.log' }]);
  scope.stop();
});

test('closed multiline preview cannot overwrite a newly opened dialog with its stale response', async () => {
  let resolve;
  const pending = new Promise((done) => {
    resolve = done;
  });
  const vm = multiline({}, () => pending);
  vm.find(native.Form).ref.r.value = { validate: async () => true, clearValidate() {} };
  const request = vm.find(native.Button).props.onClick();
  await Vue.nextTick();
  vm.props.showDialog = false;
  await Vue.nextTick();
  vm.props.showDialog = true;
  await Vue.nextTick();
  assert.equal(vm.requests[0].data.multiline_pattern, '^first');
  resolve({ data: { match_lines: 99 } });
  await request;
  assert.equal(
    all(vm.render()).some((n) => n.props?.class === 'match-counts'),
    false,
  );
  assert.equal(vm.find(native.Button).props.loading, false);
  vm.scope.stop();
});
