import test from 'node:test';
import assert from 'node:assert/strict';
import * as Vue from 'vue';
import { loadTypeScript } from './helpers/load-typescript.mjs';

test('list skeleton covers the full viewport on initial mount and resize, with list-specific row rhythm', () => {
  let mounted, cleanup, resize, observed, disconnected = false;
  const PreviousObserver = globalThis.ResizeObserver;
  globalThis.ResizeObserver = class {
    constructor(callback) { resize = callback; }
    observe(element) { observed = element; }
    disconnect() { disconnected = true; }
  };
  try {
    const sdk = loadTypeScript(new URL('../src/shared/ui/loading/list-skeleton.ts', import.meta.url), {
      vue: { ...Vue, onMounted: fn => { mounted = fn; }, onBeforeUnmount: fn => { cleanup = fn; } },
      './skeleton': { DropdownLoadingSkeleton: {} },
    });
    for (const [variant, height] of [['log', 64], ['log-table', 64], ['fields', 32]]) {
      const props = Vue.reactive({ variant });
      const render = sdk.ListLoadingSkeleton.setup(props);
      const root = Vue.markRaw({ clientHeight: 510 });
      render().props.ref.value = root;
      mounted();
      assert.equal(observed, root);
      assert.equal(render().children.length, Math.ceil(510 / height));
      root.clientHeight = 900; resize();
      assert.equal(render().children.length, Math.ceil(900 / height));
      assert.equal(render().props.style['--bklog-list-row-height'], `${height}px`);
      assert.equal(render().props.role, 'status');
      cleanup(); assert.equal(disconnected, true);
    }
  } finally { globalThis.ResizeObserver = PreviousObserver; }
});
