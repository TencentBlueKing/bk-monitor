import test from 'node:test';
import assert from 'node:assert/strict';
import * as Vue from 'vue';
import ts from 'typescript';
import { loadTypeScript } from './helpers/load-typescript.mjs';

function fixture(overrides = {}, lookup = async () => []) {
  const events = []; let cleanup; let exposed;
  const props = Vue.reactive({ value: ['synthetic.alex'], modelValue: undefined, api: '/synthetic-directory', multiple: true,
    disabled: false, tagClearable: true, tagType: 'tag', fixedHeight: true, displayDomain: false, ...overrides });
  const NativeSelector = { name: 'OfficialVue3Selector' };
  const { default: component } = loadTypeScript(new URL('../src/shared/ui/user-selector/legacy-contract.tsx', import.meta.url), {
    vue: { ...Vue, onBeforeUnmount: fn => { cleanup = fn; } },
    '@blueking/bk-user-selector/vue3': NativeSelector,
    '@/platform/sdk/user-selector/lookup': { lookupLegacyUsernames: lookup },
  }, { jsx: ts.JsxEmit.ReactJSX, jsxImportSource: 'vue' });
  const render = component.setup(props, { attrs: { class: 'consumer-style' },
    emit: (...args) => events.push(args), expose: value => { exposed = value; } });
  return { props, events, render, native: () => render().children[0], exposed, close: () => cleanup() };
}
test('legacy username callers keep multi-select, controlled arrays, endpoint and ordered change/removal events', () => {
  const f = fixture(); const node = f.native();
  assert.equal(node.props.apiBaseUrl, '/synthetic-directory');
  assert.equal(node.props.enableMultiTenantMode, false);
  assert.equal(node.props.multiple, true);
  assert.notEqual(node.props.modelValue, f.props.value);
  node.props['onUpdate:modelValue'](['synthetic.blair']);
  assert.deepEqual(f.events, [
    ['update:modelValue', ['synthetic.blair']], ['input', ['synthetic.blair']],
    ['change', ['synthetic.blair']], ['remove-selected', 'synthetic.alex'],
  ]);
  assert.deepEqual(f.props.value, ['synthetic.alex']);
  f.events.length = 0;
  node.props['onUpdate:modelValue'](['synthetic.alex']);
  assert.deepEqual(f.events, []);
  node.props.onFocus();
  node.props.onBlur(); node.props.onBlur();
  assert.deepEqual(f.events, [['focus'], ['blur']]);
  f.close();
});
test('v-model, single selection, disabled, non-clearable tags and avatar rendering retain caller contracts', () => {
  const f = fixture({ value: undefined, modelValue: ['synthetic.alex'], multiple: false, disabled: true, tagClearable: false, tagType: 'avatar' });
  const node = f.native();
  assert.equal(node.props.modelValue, 'synthetic.alex');
  assert.equal(node.props.disabled, true);
  assert.equal(f.render().props.inert, true);
  node.props['onUpdate:modelValue']('synthetic.blair');
  assert.deepEqual(f.events, []);
  assert.ok(Vue.normalizeClass(f.render().props.class).includes('is-locked-tags'));
  const label = node.props.renderTag(Vue.h, { username: 'synthetic.alex', display_name: 'Synthetic Alpha' });
  assert.equal(label.children[1], 'synthetic.alex(Synthetic Alpha)');
  assert.equal(label.children[0].props.class, 'username-selector-avatar');
  f.close();
});
test('validated Enter emits only username IDs, clears the SDK input, and aborts stale work on unmount', async () => {
  const requests = [];
  const f = fixture({}, async (api, names, signal) => { requests.push({ api, names, signal }); return ['synthetic.blair']; });
  const target = { value: 'synthetic.blair', dispatchEvent(event) { assert.equal(event.type, 'input'); } };
  const event = { key: 'Enter', target, preventDefault() {}, stopPropagation() {} };
  await f.render().props.onKeydownCapture(event);
  assert.deepEqual(requests[0].names, ['synthetic.blair']);
  assert.deepEqual(f.events.find(([name]) => name === 'change')[1], ['synthetic.alex', 'synthetic.blair']);
  assert.equal(target.value, '');
  f.close(); assert.equal(requests[0].signal.aborted, true);
  let resolve;
  const stale = fixture({}, () => new Promise(done => { resolve = done; }));
  const task = stale.render().props.onKeydownCapture({ ...event, target: { ...target, value: 'synthetic.blair' } });
  stale.close(); resolve(['synthetic.blair']); await task;
  assert.deepEqual(stale.events, []);
});
test('directory lookup preserves query semantics and splits all IDs at the existing 100-user limit', async () => {
  const { lookupLegacyUsernames } = loadTypeScript(new URL('../src/platform/sdk/user-selector/lookup.ts', import.meta.url));
  const calls = [], names = Array.from({ length: 205 }, (_, i) => `synthetic-${i}`);
  const found = await lookupLegacyUsernames('/synthetic-directory', names, undefined, async (api, params) => {
    calls.push({ api, params }); return { code: 0, data: { results: params.exact_lookups.split(',').map(username => ({ username })) } };
  });
  assert.deepEqual(calls.map(x => x.params.exact_lookups.split(',').length), [100, 100, 5]);
  assert.ok(calls.every(x => x.params.page_size === 100 && x.params.page === 1 && x.params.app_code === 'bk-magicbox'));
  assert.deepEqual(found, names);
});
