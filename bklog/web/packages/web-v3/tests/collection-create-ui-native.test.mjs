import test from 'node:test';
import assert from 'node:assert/strict';
import * as Vue from 'vue';
import ts from 'typescript';
import { loadTypeScript } from './helpers/load-typescript.mjs';

function descendants(node) {
  if (!node || typeof node !== 'object') return [];
  if (Array.isArray(node)) return node.flatMap(descendants);
  const children = typeof node.children?.default === 'function' ? node.children.default() : node.children;
  return [node, ...descendants(children)];
}
test('cluster loading, empty and populated states are exclusive and preserve selection/create behavior', () => {
  const Table = { name: 'Table' }, Empty = { name: 'Empty' }, Skeleton = { name: 'Skeleton' }, Button = { name: 'Button' };
  const resolved = [], events = [];
  const { default: component } = loadTypeScript(new URL('../src/features/collection/current/components/business-comp/step4/cluster-table.tsx', import.meta.url), {
    vue: Vue,
    'tdesign-vue-next': { Button, Progress: {}, Radio: {} },
    '@/app/state/domains/application-store': { useApplicationStore: () => ({ spaceUid: 'synthetic-space' }) },
    '@/shared/lib/util': { formatFileSize: String },
    '@/shared/composables/use-locale': () => ({ t: text => text }),
    'vue-router': { useRouter: () => ({ resolve: value => { resolved.push(value); return { href: '#/synthetic-create' }; } }) },
    '../../common-comp/table-component': Table,
    '@/shared/ui/loading/management-list-loading': Skeleton,
    '@/shared/ui/empty-status/index.vue': Empty,
  }, { jsx: ts.JsxEmit.ReactJSX, jsxImportSource: 'vue' });
  const props = Vue.reactive({ clusterList: [], clusterSelect: undefined, loading: true, showDesc: true, showBizCount: true, name: 'Synthetic group' });
  const scope = Vue.effectScope();
  const render = scope.run(() => component.setup(props, { emit: (...args) => events.push(args) }));
  let nodes = descendants(render());
  assert.equal(nodes.some(n => n.type === Empty), false);
  assert.equal(nodes.find(n => n.type === Skeleton).props.loading, true);
  assert.equal(nodes.find(n => n.type === Table).props.slots.empty().props['aria-hidden'], 'true');
  props.loading = false;
  nodes = descendants(render());
  assert.equal(nodes.some(n => n.type === Table), false);
  assert.equal(nodes.find(n => n.type === Empty).props.showText, false);
  const previous = globalThis.window; const opened = [];
  globalThis.window = { open: (...args) => opened.push(args) };
  try { nodes.find(n => n.type === Button).props.onClick(); }
  finally { globalThis.window = previous; }
  assert.deepEqual(resolved, [{ name: 'es-cluster-manage', query: { spaceUid: 'synthetic-space' } }]);
  assert.deepEqual(opened, [['#/synthetic-create', '_blank']]);
  const row = { storage_cluster_id: 1, storage_display_name: 'Synthetic cluster', storage_total: 100, storage_usage: 10 };
  props.clusterList = [row];
  nodes = descendants(render());
  const table = nodes.find(n => n.type === Table);
  assert.equal(table.props.data[0].storage_cluster_id, 1);
  table.props.onCellClick(table.props.data[0]);
  assert.equal(events[0][0], 'choose');
  assert.equal(events[0][1].storage_cluster_id, 1);
  scope.stop();
});

test('report drawer preserves nested data, copy and close; empty state does not invent a log', async () => {
  const Drawer = { name: 'Drawer' }, Button = { name: 'Button' }, Json = { name: 'Json' };
  const copies = [], messages = [], events = [];
  const { default: component } = loadTypeScript(new URL('../src/features/collection/current/components/business-comp/step3/report-log-slider.tsx', import.meta.url), {
    vue: Vue,
    'tdesign-vue-next': { Drawer, Button },
    '@/shared/global/overlay/overlay-registry.js': { overlayRegistry: { nextZIndex: () => 3000 } },
    '@/shared/global/overlay/z-index-manager.js': { Z_INDEX_LAYERS: { DRAWER: 2000 } },
    '@/shared/global/json-format-wrapper.vue': Json,
    '@/shared/composables/use-locale': () => ({ t: text => text }),
    '../../../utils': { showMessage: value => messages.push(value) },
  }, { jsx: ts.JsxEmit.ReactJSX, jsxImportSource: 'vue' });
  const props = Vue.reactive({ isShow: true, jsonText: { nested: { count: 2 }, items: ['synthetic'] } });
  const render = component.setup(props, { emit: (...args) => events.push(args) });
  let drawer = render();
  assert.equal(drawer.type, Drawer);
  assert.equal(drawer.props.size, '596px');
  assert.equal(drawer.props.closeBtn, true);
  const json = descendants(drawer.props['v-slots'].body()).find(n => n.type === Json);
  assert.equal(json.props.data, props.jsonText);
  const previousNavigator = Object.getOwnPropertyDescriptor(globalThis, 'navigator');
  Object.defineProperty(globalThis, 'navigator', { configurable: true, value: { clipboard: { writeText: async value => copies.push(value) } } });
  try { await descendants(drawer.props['v-slots'].header()).find(n => n.type === Button).props.onClick({}); }
  finally { if (previousNavigator) Object.defineProperty(globalThis, 'navigator', previousNavigator); else delete globalThis.navigator; }
  assert.deepEqual(JSON.parse(copies[0]), props.jsonText);
  assert.equal(messages.length, 1);
  const previousDocument = globalThis.document;
  const calls = [];
  const area = { value: '', style: {}, focus: () => calls.push('focus'), select: () => calls.push('select'), remove: () => calls.push('remove') };
  const host = { appendChild: element => { assert.equal(element, area); calls.push('append'); } };
  Object.defineProperty(globalThis, 'navigator', { configurable: true, value: {} });
  globalThis.document = { createElement: () => area, execCommand: () => true };
  try {
    await descendants(drawer.props['v-slots'].header()).find(n => n.type === Button).props.onClick({ currentTarget: { closest: () => host } });
    assert.deepEqual(calls, ['append', 'focus', 'select', 'remove']);
    assert.deepEqual(JSON.parse(area.value), props.jsonText);
  } finally {
    globalThis.document = previousDocument;
    if (previousNavigator) Object.defineProperty(globalThis, 'navigator', previousNavigator); else delete globalThis.navigator;
  }
  drawer.props.onClose();
  assert.deepEqual(events, [['change', false]]);
  props.jsonText = {};
  drawer = render();
  assert.equal(descendants(drawer.props['v-slots'].body()).some(n => n.type === Json), false);
  assert.equal(descendants(drawer.props['v-slots'].header()).find(n => n.type === Button).props.disabled, true);
  props.isShow = false;
  assert.equal(render().props['v-slots'].body(), false);
});
