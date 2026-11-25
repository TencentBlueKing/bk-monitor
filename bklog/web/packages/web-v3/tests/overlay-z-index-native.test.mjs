import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { effectScope, ref, watch } from 'vue';
import { createZIndexManager, Z_INDEX_LAYERS } from '../src/shared/global/overlay/z-index-manager.js';
import { loadTypeScript } from './helpers/load-typescript.mjs';
import { installZIndexManager, ensureMonitorOverlayZIndex } from '../src/shared/global/overlay/z-index-manager.js';
import { OverlayRegistry } from '../src/shared/global/overlay/overlay-registry.js';

test('Monitor raises existing counters after import, stays idempotent and preserves higher host layers', () => {
  for (const mode of ['APM', 'TRACE']) {
    const properties = new Map();
    const win = { document: { documentElement: { style: { setProperty: (key, value) => properties.set(key, value) } } } };
    const manager = installZIndexManager(win);
    assert.equal(manager.nextZIndex(), Z_INDEX_LAYERS.DROPDOWN + 1);
    win.__IS_MONITOR_COMPONENT__ = true;
    win[`__IS_MONITOR_${mode}__`] = true;
    assert.equal(ensureMonitorOverlayZIndex(win), manager);
    assert.equal(manager.getCurrent(), Z_INDEX_LAYERS.DIALOG);
    assert.equal(properties.get('--bklog-z-popup'), String(Z_INDEX_LAYERS.DIALOG));
    ensureMonitorOverlayZIndex(win);
    assert.equal(manager.getCurrent(), Z_INDEX_LAYERS.DIALOG);
    assert.ok(manager.nextZIndex() > Z_INDEX_LAYERS.DIALOG);
    manager.nextZIndex(4200);
    ensureMonitorOverlayZIndex(win);
    assert.ok(manager.nextTickIndex() > 4200);
    assert.ok(manager.nextMessageZIndex() > manager.getCurrent());
    manager.reset();
    assert.ok(manager.nextZIndex() > Z_INDEX_LAYERS.DIALOG);
  }
});

test('legacy host counters retain their floor; standalone allocations remain unchanged', () => {
  const standalone = {};
  assert.equal(ensureMonitorOverlayZIndex(standalone), null);
  assert.equal(installZIndexManager(standalone).nextZIndex(), Z_INDEX_LAYERS.DROPDOWN + 1);
  const win = { __IS_MONITOR_COMPONENT__: true, __bk_zIndex_manager: { zIndex: 4300, nextZIndex() { return ++this.zIndex; } } };
  const manager = ensureMonitorOverlayZIndex(win);
  assert.ok(manager.nextZIndex() > 4300);
  assert.ok(manager.nextTickIndex() > 4300);
});

test('Registry fallback respects Monitor flags set after module import', () => {
  const previousWindow = globalThis.window;
  try {
    globalThis.window = {};
    const registry = new OverlayRegistry();
    assert.equal(registry.nextZIndex(), Z_INDEX_LAYERS.DROPDOWN + 1);
    globalThis.window.__IS_MONITOR_COMPONENT__ = true;
    assert.ok(registry.nextZIndex() > Z_INDEX_LAYERS.DIALOG);
    const first = registry.nextZIndex();
    assert.ok(registry.nextZIndex() > first);
  } finally {
    if (previousWindow === undefined) delete globalThis.window;
    else globalThis.window = previousWindow;
  }
});

const hookFile = new URL('../src/shared/global/overlay/use-overlay-z-index.ts', import.meta.url);
const makeHook = manager => loadTypeScript(hookFile, {
  vue: { ref, watch },
  './z-index-manager.js': { zIndexManager: manager, Z_INDEX_LAYERS },
});
test('visible transitions allocate globally above an open parent and reopens; rerenders do not allocate', () => {
  const manager = createZIndexManager(), hooks = makeHook(manager), scope = effectScope();
  const visible = ref(false), childVisible = ref(false);
  let parent, child;
  scope.run(() => {
    parent = hooks.useOverlayZIndex(visible);
    child = hooks.useOverlayZIndex(childVisible, 'DRAWER');
  });
  assert.equal(manager.getCurrent(), Z_INDEX_LAYERS.DROPDOWN);
  visible.value = true;
  const parentLayer = parent.value;
  assert.ok(parentLayer > Z_INDEX_LAYERS.DIALOG);
  childVisible.value = true;
  assert.ok(child.value > parentLayer);
  const childLayer = child.value;
  assert.ok(hooks.allocateOverlayZIndex('DROPDOWN') > childLayer);
  visible.value = true;
  assert.equal(parent.value, parentLayer);
  visible.value = false;
  visible.value = true;
  assert.ok(parent.value > childLayer);
  const before = manager.getCurrent();
  scope.stop();
  visible.value = false;
  visible.value = true;
  assert.equal(manager.getCurrent(), before);
});
test('initially visible overlays allocate and messages stay above a long-lived overlay counter', () => {
  const manager = createZIndexManager(), hooks = makeHook(manager), scope = effectScope();
  scope.run(() => assert.ok(hooks.useOverlayZIndex(ref(true)).value > Z_INDEX_LAYERS.DIALOG));
  manager.nextTickIndex(7000);
  const message = manager.nextMessageZIndex();
  assert.ok(message > manager.getCurrent());
  assert.ok(manager.nextMessageZIndex() > message);
  scope.stop();
});
test('business overlays no longer bypass the manager with fixed large numeric props', () => {
  for (const path of [
    'features/preferences/index.tsx',
    'features/clusters/current/cluster-manage/index.tsx',
    'features/collection/current/components/create-operation/step2-custom-report.tsx',
    'features/retrieval/workbench/components/batch-input/index.tsx',
  ]) assert.doesNotMatch(readFileSync(new URL(`../src/${path}`, import.meta.url), 'utf8'), /zIndex=\{\d{3,}\}/);
});

test('Trace observer leaves host overlay layers intact and assigns embedded messages', () => {
  class Element {
    style = {};
    constructor(selector, owned) {
      this.selector = selector;
      this.owned = owned;
    }
    matches(selector) {
      return selector.split(', ').includes(this.selector);
    }
    closest() {
      return this.owned ? this : null;
    }
  }
  const host = new Element('.t-message__list', false);
  host.style.zIndex = '4321';
  const log = new Element('.t-message__list', true);
  const hostPopup = new Element('.t-popup', false);
  let notify;
  const layerWrites = [];
  const win = {
    __IS_MONITOR_TRACE__: true,
    Element,
    MutationObserver: class {
      constructor(callback) { notify = callback; }
      observe() {}
    },
    document: {
      body: {},
      documentElement: { style: { setProperty: key => layerWrites.push(key) } },
      querySelectorAll: () => [host, hostPopup],
    },
  };
  installZIndexManager(win);
  assert.equal(layerWrites.filter(key => key === '--bklog-z-popup').length, 1);
  layerWrites.length = 0;
  notify([{ addedNodes: [host, hostPopup] }]);
  assert.deepEqual(layerWrites, []);
  notify([{ addedNodes: [log] }]);
  assert.equal(host.style.zIndex, '4321');
  assert.equal(hostPopup.style.zIndex, undefined);
  assert.ok(Number(log.style.zIndex) >= Z_INDEX_LAYERS.MESSAGE);
});
