import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import ts from 'typescript';
import * as Vue from 'vue';

const source = readFileSync(new URL('../src/platform/compat/tdesign/legacy-bk-controls.tsx', import.meta.url), 'utf8');
function component(name, next, dependencies) {
  const code = source.slice(source.indexOf(`const ${name} =`), source.indexOf(next, source.indexOf(`const ${name} =`)));
  const js = ts.transpileModule(code, { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText;
  return new Function(...Object.keys(dependencies), js + `\nreturn ${name};`)(...Object.values(dependencies));
}

test('vertical legacy forms use top labels without a fixed label column; horizontal and inline contracts stay intact', async () => {
  const Form = { name: 'Form' };
  const cmp = component('BkForm', 'const BkFormItem', { ...Vue, mode3: {}, Form });
  for (const formType of ['vertical', 'horizontal', 'inline']) {
    let exposed;
    const data = {}, rules = {};
    const render = cmp.setup({ model: data, rules, labelWidth: 560, formType }, { attrs: {}, slots: {}, expose: value => { exposed = value; } });
    const vnode = render();
    assert.equal(vnode.props.data, data);
    assert.equal(vnode.props.rules, rules);
    assert.equal(vnode.props.labelAlign, formType === 'vertical' ? 'top' : 'right');
    assert.equal(vnode.props.labelWidth, formType === 'vertical' ? undefined : 560);
    assert.equal(vnode.props.layout, formType === 'inline' ? 'inline' : 'vertical');
    let valid = true, cleared = 0;
    vnode.ref.r.value = { validate: async () => valid, clearValidate: () => { cleared++; } };
    assert.equal(await exposed.validate(), true);
    valid = { name: [{ result: false }] };
    await assert.rejects(exposed.validate());
    exposed.clearError();
    assert.equal(cleared, 1);
  }
});

test('form item ext-cls preserves layout scopes and validation inputs', () => {
  const FormItem = { name: 'FormItem' };
  const cmp = component('BkFormItem', 'function visibleProp', { ...Vue, mode3: {}, FormItem });
  const rules = [{ required: true }];
  const slots = { default: () => 'Synthetic control' };
  const node = cmp.setup({ label: 'Synthetic label', property: 'synthetic', required: true, extCls: 'special-layout' }, {
    attrs: { class: ['existing-scope'], rules }, slots,
  })();
  assert.equal(node.props.class, 'special-layout existing-scope');
  assert.equal(node.props.name, 'synthetic');
  assert.equal(node.props.requiredMark, true);
  assert.equal(node.props.rules, rules);
  assert.equal(node.children.default(), 'Synthetic control');
});

test('drawers preserve custom scope, header/body/footer and async close veto', async () => {
  const Drawer = { name: 'Drawer' };
  const cmp = component('BkSideslider', 'const BkCollapse', { ...Vue, mode3: {}, Drawer, Z_INDEX_LAYERS: { DRAWER: 2500 }, overlayRegistry: { nextZIndex: () => 2600 } });
  let allow = false, checks = 0;
  const events = [];
  const props = { isShow: true, title: 'Synthetic title', width: 640, transfer: true, quickClose: true, extCls: 'synthetic-drawer', beforeClose: async () => { checks++; return allow; } };
  const render = cmp.setup(props, { attrs: { class: ['extra-class'], drawerClassName: 'native-class' }, slots: { content: () => 'Body', footer: () => 'Footer' }, emit: (...args) => events.push(args) });
  const node = render();
  assert.equal(node.props.drawerClassName, 'bklog-compat-drawer synthetic-drawer native-class extra-class');
  assert.equal(node.props.size, '640px');
  assert.equal(node.props.header, 'Synthetic title');
  assert.equal(node.props.closeBtn, true);
  assert.equal(node.props.closeOnEscKeydown, true);
  assert.equal(node.children.body(), 'Body');
  assert.equal(node.children.footer(), 'Footer');
  await node.props.onClose();
  assert.equal(checks, 1);
  assert.deepEqual(events, []);
  allow = true;
  await node.props.onClose();
  assert.deepEqual(events, [['update:isShow', false], ['animation-end']]);
  props.isShow = false;
  assert.equal(render().children.body(), null);
  assert.equal(render().children.footer, undefined);
});

test('textarea rows map to native autosize without replacing value events or explicit autosize', () => {
  const Textarea = { name: 'Textarea' }, Input = { name: 'Input' };
  const cmp = component('BkInput', 'function optionNodes', { ...Vue, mode3: {}, modelValue: props => props.value, Textarea, Input });
  const events = [];
  const props = { type: 'textarea', rows: 4, value: 'Synthetic input' };
  const render = cmp.setup(props, { attrs: {}, slots: {}, emit: (...args) => events.push(args) });
  const node = render();
  assert.deepEqual(node.props.autosize, { minRows: 4, maxRows: 4 });
  node.props.onChange('Changed');
  assert.deepEqual(events, [['update:modelValue', 'Changed'], ['input', 'Changed'], ['change', 'Changed']]);
  const fixed = cmp.setup(props, { attrs: { autosize: false }, slots: {}, emit() {} });
  assert.equal(fixed().props.autosize, false);
});

test('table skeleton integration preserves real data, pagination and filter event payloads', () => {
  const Table = { name: 'Table' }, ManagementListLoading = { name: 'ManagementListLoading' };
  const cmp = component('BkTable', 'function modelValue', { ...Vue, mode3: {}, Table, ManagementListLoading,
    flattenNodes: () => [], componentName: () => '', attr: () => undefined, cellRenderer() {} });
  const events = [], data = [{ id: 'synthetic-row' }];
  const props = { data, pagination: { current: 2, limit: 10, count: 30 }, size: 'medium', loading: true };
  const render = cmp.setup(props, { attrs: { class: ['synthetic-table'] }, slots: {}, emit: (...args) => events.push(args), expose() {} });
  const skeleton = render();
  assert.equal(skeleton.type, ManagementListLoading);
  const table = skeleton.children.default();
  assert.equal(table.props.data, data);
  assert.equal(table.props.pagination.current, 2);
  assert.equal(table.props.class, 'bklog-legacy-table synthetic-table');
  props.outerBorder = false;
  assert.equal(render().children.default().props.class, 'bklog-legacy-table synthetic-table is-borderless');
  table.props.onPageChange({ current: 3, pageSize: 20 });
  table.props.onFilterChange({ state: 'ready', owner: [] });
  assert.deepEqual(events, [['page-limit-change', 20], ['page-change', 3], ['filter-change', { state: ['ready'], owner: [] }]]);
  props.loading = false;
  assert.equal(render().children.default().props.data, data);
  props.loading = undefined;
  assert.equal(render().type, Table);
});
