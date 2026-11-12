import test from 'node:test';
import assert from 'node:assert/strict';
import * as Vue from 'vue';
import ts from 'typescript';
import { loadTypeScript } from './helpers/load-typescript.mjs';

function fixture(loading = true, constrained = false) {
  let mounted, unmounted, watched;
  const cleanup = [];
  const previous = globalThis.ResizeObserver;
  globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() { cleanup.push('disconnect'); } };
  const ItemSkeleton = { name: 'ItemSkeleton' };
  const { default: component } = loadTypeScript(new URL('../src/shared/ui/loading/management-list-loading.tsx', import.meta.url), {
    vue: { ...Vue, onMounted: fn => { mounted = fn; }, onBeforeUnmount: fn => { unmounted = fn; }, watch: (value, fn) => { watched = fn; } },
    '@/app/skeleton/item-skeleton': ItemSkeleton,
    '@/shared/composables/use-locale': { t: x => x },
    './management-list-loading.scss': {},
  }, { jsx: ts.JsxEmit.ReactJSX, jsxImportSource: 'vue' });
  const props = { loading, rows: 6, rowHeight: 42 };
  const sentinel = Vue.h('table', { 'data-source': 'synthetic-table' });
  const render = component.setup(props, { slots: { default: () => sentinel } });
  const cells = [120, 240, 160].map(width => ({ getBoundingClientRect: () => ({ width }) }));
  const head = { getBoundingClientRect: () => ({ bottom: 180, width: 520, height: 40 }), querySelectorAll: () => cells };
  const row = { getBoundingClientRect: () => ({ height: 58 }) };
  const body = { getBoundingClientRect: () => ({ height: 580 }) };
  const content = { style: constrained ? { maxHeight: '240px' } : {}, getBoundingClientRect: () => ({ bottom: 380 }) };
  const table = { getBoundingClientRect: () => ({ left: 20, width: 520 }), querySelector: selector => selector === 'thead' ? head : selector === 'tbody' ? body : selector === '.t-table__content' ? content : row };
  render().ref.r.value = { getBoundingClientRect: () => ({ top: 100, left: 20 }), scrollTop: 0, scrollLeft: 0, querySelector: () => table, addEventListener() {}, removeEventListener: () => cleanup.push('remove-scroll') };
  return { props, render, mounted: () => mounted(), changed: () => watched(), head, cells, ItemSkeleton, sentinel, cleanup, close: () => { unmounted(); globalThis.ResizeObserver = previous; } };
}

test('management skeleton follows real columns, row height and table start while keeping the table mounted', () => {
  const f = fixture();
  try {
    f.mounted();
    const node = f.render();
    assert.equal(node.children[0], f.sentinel);
    const skeleton = node.children[1];
    assert.equal(skeleton.props.style.top, '80px');
    assert.equal(skeleton.props.style.width, '520px');
    assert.equal(skeleton.children.length, 10);
    assert.equal(skeleton.children[0].props.style.gridTemplateColumns, '120px 240px 160px');
    assert.equal(skeleton.children[0].props.style.height, '58px');
    assert.equal(skeleton.children[0].children.length, 3);
    assert.equal(skeleton.children[0].children[0].children[0].type, f.ItemSkeleton);
  } finally { f.close(); }
  assert.deepEqual(f.cleanup, ['disconnect', 'remove-scroll']);
});

test('resizing and loaded transitions remove the overlay without replacing real content', async () => {
  const f = fixture();
  try {
    f.mounted();
    f.cells[1].getBoundingClientRect = () => ({ width: 300 });
    await f.changed();
    assert.equal(f.render().children[1].children[0].props.style.gridTemplateColumns, '120px 300px 160px');
    f.props.loading = false;
    await f.changed();
    assert.equal(f.render().children[0], f.sentinel);
    assert.equal(f.render().children[1], false);
    assert.equal(f.render().props.style, undefined);
  } finally { f.close(); }
});

test('fixed-height scrolling tables clip skeleton rows at the body viewport without increasing the table height', () => {
  const f = fixture(true, true);
  try {
    f.mounted();
    const node = f.render();
    assert.equal(node.props.style.minHeight, '280px');
    assert.equal(node.props.style['--bklog-table-skeleton-min-height'], '0px');
    assert.equal(node.children[1].props.style.maxHeight, '200px');
  } finally { f.close(); }
});
