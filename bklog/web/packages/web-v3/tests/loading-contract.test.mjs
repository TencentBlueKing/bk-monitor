import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { loadTypeScript } from './helpers/load-typescript.mjs';

function fixture() {
  const calls = [];
  const skeleton = () => 'skeleton';
  const native = loadTypeScript(new URL('../src/shared/ui/loading/native.ts', import.meta.url), {
    'tdesign-vue-next': {
      Loading: { props: { loading: Boolean, indicator: { default: true } } },
      LoadingPlugin(options) {
        const call = { options, hidden: 0 };
        calls.push(call);
        return { hide() { call.hidden++; } };
      },
    },
    'lodash-es': { isEqual: (a, b) => JSON.stringify(a) === JSON.stringify(b) },
    './skeleton': { renderLoadingSkeleton: skeleton },
  });
  return { ...native, calls, skeleton };
}
const binding = (value, oldValue) => ({ value, oldValue, modifiers: {} });

test('directive owns one overlay through active updates, false, retry and unmount', () => {
  const { LoadingDirective: directive, calls, skeleton } = fixture();
  const el = {};
  directive.mounted(el, binding({ loading: false }));
  assert.equal(calls.length, 0);
  directive.updated(el, binding({ loading: true, delay: 150, text: 'query' }, { loading: false }));
  assert.equal(calls[0].options.indicator, skeleton);
  assert.equal(calls[0].options.delay, 150);
  assert.equal(calls[0].options.attach(), el);
  directive.updated(el, binding({ loading: true, text: 'retry' }, { loading: true, text: 'query' }));
  assert.equal(calls[0].hidden, 1);
  assert.equal(calls[1].options.text, 'retry');
  directive.updated(el, binding(false, true));
  assert.equal(calls[1].hidden, 1);
  directive.updated(el, binding(true, false));
  directive.unmounted(el);
  assert.equal(calls[2].hidden, 1);
  directive.unmounted(el);
  assert.equal(calls[2].hidden, 1);
});
test('directive supports boolean, old state/title spelling, modifiers and independent hosts', () => {
  const { LoadingDirective: directive, calls } = fixture();
  const a = {}, b = {};
  directive.mounted(a, { ...binding({ isLoading: true, title: 'Loading', zIndex: 7 }), modifiers: { fullscreen: true } });
  directive.mounted(b, binding(true));
  assert.equal(calls[0].options.fullscreen, true);
  assert.equal(calls[0].options.text, 'Loading');
  assert.equal(calls[0].options.zIndex, 7);
  directive.unmounted(a);
  assert.equal(calls[0].hidden, 1);
  assert.equal(calls[1].hidden, 0);
  directive.updated(b, binding(true, true));
  assert.equal(calls.length, 2);
  directive.unmounted(b);
});
test('plugin defaults to skeleton and retains explicit skeleton or indicator=false', () => {
  const { LoadingPlugin, calls, skeleton } = fixture();
  LoadingPlugin(true);
  LoadingPlugin({ indicator: false, showOverlay: true });
  const customSkeleton = () => 'page skeleton';
  LoadingPlugin({ indicator: customSkeleton });
  assert.equal(calls[0].options.indicator, skeleton);
  assert.equal(calls[1].options.indicator, false);
  assert.equal(calls[1].options.showOverlay, true);
  assert.equal(calls[2].options.indicator, customSkeleton);
});
test('V3 runtime loading imports use the shared entry; no rotating images or dot overrides', () => {
  function walk(dir) {
    for (const item of readdirSync(dir, { withFileTypes: true })) {
      const file = new URL(item.name + (item.isDirectory() ? '/' : ''), dir);
      if (item.isDirectory()) walk(file);
      else if (/\.(vue|tsx?|scss)$/.test(item.name) && !item.name.endsWith('.d.ts') && !file.pathname.endsWith('/loading/native.ts')) {
        const source = readFileSync(file, 'utf8');
        for (const match of source.matchAll(/import\s*\{([^}]+)\}\s*from\s*['"]tdesign-vue-next['"]/g)) {
          assert.doesNotMatch(match[1], /(?:^|,)\s*(?:Loading|LoadingPlugin|LoadingDirective)(?:\s+as\b|\s*,|\s*$)/, file.pathname);
        }
        assert.doesNotMatch(source, /bklog-loading-dots|url\([^;]*loading\.svg/, file.pathname);
      }
    }
  }
  walk(new URL('../src/', import.meta.url));
});

test('dropdown rows default to 24px and width follows the reference on every layout pass', () => {
  const { DropdownLoadingSkeleton } = loadTypeScript(new URL('../src/shared/ui/loading/skeleton.ts', import.meta.url));
  assert.equal(DropdownLoadingSkeleton.props.itemHeight.default, 24);
  const render = DropdownLoadingSkeleton.setup({ rows: 3, itemHeight: 24 });
  assert.equal(render().children.length, 3);
  assert.ok(render().children.every(item => item.props.style.height === '24px'));
  const { dropdownWidthModifier } = loadTypeScript(new URL('../src/shared/global/dropdown-width.ts', import.meta.url));
  const state = { rects: { reference: { width: 392 } }, styles: { popper: {} } };
  dropdownWidthModifier.fn({ state });
  assert.equal(state.styles.popper.width, '392px');
  state.rects.reference.width = 640;
  dropdownWidthModifier.fn({ state });
  assert.equal(state.styles.popper.width, '640px');
});
