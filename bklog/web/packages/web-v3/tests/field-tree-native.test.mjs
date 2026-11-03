import { test } from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';
import { loadTypeScript } from './helpers/load-typescript.mjs';
const root = new URL('../src/features/retrieval/workbench/field-filter-comp/', import.meta.url);
class Base {}
const TreeFixture = { name: 'TreeFixture' },
  DragFixture = { name: 'DragFixture' };
const { default: Fields } = loadTypeScript(
  new URL('index.tsx', root),
  {
    'vue-property-decorator': {
      Component: (value) => value,
      Prop: () => () => {},
      Watch: () => () => {},
      Ref: () => () => {},
    },
    'vue-tsx-support': { Component: Base },
    '@/shared/lib/util': { getRegExp: (value) => new RegExp(value, 'i') },
    '@/shared/constants/index.ts': { builtInInitHiddenList: [] },
    '@/shared/composables/use-feature-toggle': {},
    'vuedraggable-vue3': DragFixture,
    'tdesign-vue-next': { Tree: TreeFixture, Input: { name: 'InputFixture' } },
    'tdesign-vue-next/es/input/style/index.css': {},
    '../../../../shared/ui/empty-status/index.vue': {},
    '../../../../app/state/services/runtime-cache.service.js': {},
    '../../../../app/state/store.type.ts': {},
    './field-item': { name: 'FieldItemFixture' },
    './update/field-setting.vue': {},
    './index.scss': {},
  },
  { jsx: ts.JsxEmit.ReactJSX, jsxImportSource: 'vue', experimentalDecorators: true },
);
const tree = {
  field_name: '__ext',
  fullName: '__ext',
  field_type: 'object',
  filterVisible: true,
  children: [
    {
      field_name: '__ext.labels',
      fullName: '__ext.labels',
      field_type: 'object',
      filterVisible: true,
      children: [
        {
          field_name: '__ext.labels.app',
          fullName: '__ext.labels.app',
          field_type: 'keyword',
          query_alias: 'serviceApp',
          filterVisible: true,
        },
      ],
    },
  ],
};
function vm() {
  const value = new Fields();
  Object.assign(value, {
    $t: (value) => value,
    fieldAliasMap: {},
    retrieveParams: {},
    datePickerValue: [],
    visibleFields: [],
  });
  return value;
}

test('native field tree preserves keys, custom field payloads and controlled expansion', () => {
  const value = vm();
  value.searchKeyword = 'app';
  Object.defineProperties(value, { isFrontStatistics: { value: false }, statisticalFieldsData: { value: {} } });
  const rendered = value.bigTreeRender(tree, '0select');
  assert.equal(rendered.type, TreeFixture);
  assert.deepEqual(rendered.props.keys, { label: 'fullName', value: 'fullName', children: 'children' });
  assert.equal(rendered.props.icon, false);
  assert.equal(rendered.props.expandOnClickNode, true);
  assert.ok(rendered.props.expanded.includes('__ext'));
  assert.ok(rendered.props.expanded.includes('__ext.labels'));
  assert.equal(rendered.props.filter({ data: tree.children[0].children[0] }), true);
  assert.equal(rendered.props.filter({ data: { field_name: 'other' } }), false);
  const label = rendered.props['v-slots'].label({ node: { data: tree.children[0].children[0] } });
  assert.equal(label.props.fieldItem, tree.children[0].children[0]);
  assert.equal(label.props.isFieldObject, true);
  rendered.props.onExpand(['__ext'], { node: { value: '__ext' } });
  assert.equal(value.expandedFieldIds.__ext, true);
  rendered.props.onExpand([], { node: { value: '__ext' } });
  assert.equal('__ext' in value.expandedFieldIds, false);
});

test('field tree lazy hydration preserves original metadata and mounts expanded descendants only', () => {
  const value = vm();
  const before = structuredClone(tree);
  const collapsed = value.hydrateVisibleTree(tree, new Set());
  assert.equal(collapsed.children.length, 1);
  assert.equal(collapsed.children[0].children, undefined);
  const expanded = value.hydrateVisibleTree(tree, new Set(['__ext', '__ext.labels']));
  assert.equal(expanded.children[0].children[0].query_alias, 'serviceApp');
  assert.deepEqual(tree, before);
});

test('field filtering no longer calls the removed imperative tree filter API', () => {
  const value = vm();
  value.searchKeyword = 'service';
  value.visibleFields = [
    { field_name: 'log', query_alias: 'message' },
    { field_name: '__ext.labels.app', query_alias: 'serviceApp' },
  ];
  Object.defineProperty(value, 'hiddenFields', { value: [{ field_name: 'host', field_alias: 'serviceHost' }] });
  value.$nextTick = () => {
    throw new Error('old imperative tree path must not run');
  };
  value.filterListByCondition();
  assert.equal(value.visibleFields[0].filterVisible, false);
  assert.equal(value.visibleFields[1].filterVisible, true);
  assert.equal(value.hiddenFields[0].filterVisible, true);
});

test('field drag keeps V2 string-key ordering and event payload', () => {
  const value = vm();
  value.visibleFields = [{ field_name: 'log' }, { field_name: 'level' }];
  value.watchVisibleFields();
  assert.deepEqual(value.dragVisibleFields, ['log', 'level']);
  value.dragVisibleFields = ['level', 'log'];
  const events = [];
  value.$emit = (...args) => events.push(args);
  value.handleVisibleMoveEnd();
  assert.deepEqual(events, [['fields-updated', ['level', 'log']]]);
  assert.deepEqual(
    value.visibleFields.map((row) => row.field_name),
    ['log', 'level'],
  );
  assert.deepEqual(DragFixture.compatConfig, { MODE: 3 });
});
