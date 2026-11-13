import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { loadTypeScript } from './helpers/load-typescript.mjs';
import * as Vue from 'vue';

const presence = () => loadTypeScript(new URL('../src/shared/ui/loading/presence.ts', import.meta.url));
test('exit is visual only; new loading cancels old exit and disposal cancels pending work', () => {
  const callbacks = new Map(), states = [];
  let id = 0;
  const controller = presence().createSkeletonPresence((...state) => states.push(state), () => 180,
    fn => { callbacks.set(++id, fn); return id; }, key => callbacks.delete(key));
  controller.update(true);
  controller.update(false);
  assert.deepEqual(states.at(-1), [true, true]);
  controller.update(true);
  assert.equal(callbacks.size, 0);
  assert.deepEqual(states.at(-1), [true, false]);
  controller.update(false);
  [...callbacks.values()][0](); callbacks.clear();
  assert.deepEqual(states.at(-1), [false, false]);
  controller.update(true); controller.update(false); controller.dispose();
  assert.equal(callbacks.size, 0);
  const count = states.length;
  controller.update(true);
  assert.equal(states.length, count);
});
test('reduced motion removes visual state immediately without a timer', () => {
  const states = [];
  const controller = presence().createSkeletonPresence((...state) => states.push(state), () => 0,
    () => { throw Error('unexpected timer'); });
  controller.update(true); controller.update(false);
  assert.deepEqual(states, [[true, false], [false, false]]);
});
test('current space label does not wait for the full dropdown list, and settled failures do not hang', () => {
  const source = readFileSync(new URL('../src/shared/global/bk-space-choice/index.tsx', import.meta.url), 'utf8');
  const start = source.indexOf('    const spaceLabelLoading =');
  const code = source.slice(start, source.indexOf('\n\n', start));
  const store = Vue.reactive({ spaceResolveFailed: false });
  const list = Vue.ref([]), uid = Vue.ref('synthetic-space'), loading = Vue.ref(true);
  const props = Vue.reactive({ isExternalAuth: false }), externalName = Vue.ref('');
  const pending = new Function('computed', 'store', 'mySpaceList', 'spaceUid', 'spaceListLoading', 'props', 'exterlAuthSpaceName',
    code + '\nreturn spaceLabelLoading;')(Vue.computed, store, list, uid, loading, props, externalName);
  assert.equal(pending.value, true);
  list.value = [{ space_uid: 'synthetic-space', space_name: 'Synthetic workspace' }];
  assert.equal(pending.value, false);
  uid.value = 'another-synthetic-space';
  assert.equal(pending.value, true);
  store.spaceResolveFailed = true;
  assert.equal(pending.value, false);
  store.spaceResolveFailed = false;
  loading.value = false;
  assert.equal(pending.value, false);
  loading.value = true;
  props.isExternalAuth = true; externalName.value = 'Synthetic external workspace';
  assert.equal(pending.value, false);
});
test('HTML navigation and body release independently and idempotently', () => {
  const previous = globalThis.document;
  try {
    const exits = [];
    const nav = { style: {} }, body = { remove() { this.removed = true; } };
    const shell = { dataset: {}, querySelector: selector => selector.includes('__nav') ? nav : body,
      remove() { this.removed = true; } };
    globalThis.document = { querySelector: selector => selector === '.log-search-nav' ? {} : shell };
    const gate = loadTypeScript(new URL('../src/app/bootstrap/shell-gate.ts', import.meta.url), {
      '@/shared/ui/loading/presence': { dissolveSkeleton: (element, done) => { exits.push({ element, done }); } },
    });
    let canceled = 0, notified = 0;
    gate.whenTopMenuSettled(() => { notified++; });
    gate.whenTopMenuSettled(() => { canceled++; })();
    gate.releaseBootstrapShell(); gate.releaseBootstrapShell();
    assert.equal(exits.length, 1);
    assert.equal(gate.isBootstrapShellReleased(), true);
    assert.equal(gate.isTopMenuSettled(), false);
    exits[0].done();
    assert.equal(body.removed, true);
    assert.equal(shell.removed, undefined);
    gate.releaseBootstrapNavWhenReady(); gate.releaseBootstrapNavWhenReady();
    assert.equal(exits.length, 2);
    exits[1].done();
    assert.equal(shell.removed, true);
    gate.markTopMenuSettled(); gate.markTopMenuSettled();
    assert.equal(notified, 1); assert.equal(canceled, 0);
  } finally { globalThis.document = previous; }
});
test('route initialization handoff does not wait for logs, trends, menu or fixed timeouts', () => {
  const workspace = readFileSync(new URL('../src/features/retrieval/workspace/index.tsx', import.meta.url), 'utf8');
  const route = readFileSync(new URL('../src/app/router/retrieve.ts', import.meta.url), 'utf8');
  assert.doesNotMatch(workspace, /sawFieldLoad|sawSearchLoad|shellBackstop|retrieveShellReady/);
  assert.match(workspace, /watch\(isPreApiLoaded, async loaded/);
  assert.match(workspace, /await nextTick\(\)/);
  assert.doesNotMatch(route, /whenTopMenuSettled|setTimeout/);
  assert.match(route, /releasePageLoading\(\)/);
  assert.match(route, /presence\.leaving/);
});

test('directive cancels the previous visual exit before creating a new native owner, and destroys on unmount', () => {
  const calls = [];
  const native = loadTypeScript(new URL('../src/shared/ui/loading/native.ts', import.meta.url), {
    'tdesign-vue-next': { Loading: { props: {} }, LoadingPlugin() {} },
    'lodash-es': { isEqual: (a, b) => a === b },
    './skeleton': { renderLoadingSkeleton() {} },
  });
  let id = 0;
  const directive = native.createSkeletonLoadingDirective(() => {
    const owner = ++id; calls.push(`create${owner}`);
    return { hide() { calls.push(`exit${owner}`); }, destroy() { calls.push(`destroy${owner}`); } };
  });
  const element = {}, binding = value => ({ value, oldValue: !value, modifiers: {} });
  directive.mounted(element, binding(true));
  directive.updated(element, binding(false));
  directive.updated(element, binding(true));
  directive.unmounted(element);
  directive.unmounted(element);
  assert.deepEqual(calls, ['create1', 'exit1', 'destroy1', 'create2', 'destroy2']);
});
