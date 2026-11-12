import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import ts from 'typescript';
import * as Vue from 'vue';

function fixture() {
  const source = readFileSync(new URL('../src/features/collection/current/components/list-main/table-list/table-list-v2.tsx', import.meta.url), 'utf8');
  const start = source.indexOf('    const renderParentIndexSetCell');
  const end = source.indexOf('    const settingFields', start);
  const saves = [], auth = [];
  const row = { id: 1, permission: { edit: true }, parents: [{ index_set_id: 10, index_set_name: 'Synthetic group' }] };
  const state = {
    editingIndexSetDraftIds: Vue.ref({}), editingIndexSetRowId: Vue.ref(''), updatingIndexSetRowId: Vue.ref(''),
    indexSetSearch: Vue.ref(''), isAddIndexSet: Vue.ref(false), indexSetOptionList: Vue.ref(row.parents), addIndexSetRef: Vue.ref(null),
  };
  const context = {
    ...state, TSelect: { name: 'TSelect' }, TInput: { name: 'TInput' }, TagMore: { name: 'TagMore' }, AddIndexSet: {},
    t: value => value, getRowUniqueId: row => row.id, getRowParentIndexSetIds: row => row.parents.map(p => p.index_set_id),
    getRowParentIndexSets: row => row.parents, isRowIndexSetEditable: row => !row.readonly,
    getRowEditAuthKey: () => 'edit', getTagMoreTriggerFrameStyle: () => ({}), handleEditOperation: row => auth.push(row.id),
    setEditingIndexSetDraftIds: (id, values) => state.editingIndexSetDraftIds.value[id] = values,
    handleParentIndexSetSubmit: row => saves.push(row.id), handleCancelAddIndexSet() {}, handleSubmitAddIndexSet() {}, handleAddIndexSet() {},
  };
  const output = ts.transpileModule(source.slice(start, end), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX, jsxImportSource: 'vue' } }).outputText;
  const render = new Function('exports', 'require', ...Object.keys(context), output + '\nreturn renderParentIndexSetCell;')({}, createRequire(import.meta.url), ...Object.values(context));
  const trigger = node => node.props['v-slots'].trigger({ content: [], contentBounds: null, isEmpty: false, triggerRef: Vue.ref() });
  return { row, render, state, context, saves, auth, trigger };
}

test('index-set cell retains the V2 trigger, search, multi-select draft and close submission contracts', () => {
  const f = fixture();
  let node = f.render(f.row);
  assert.equal(node.type, f.context.TSelect);
  assert.equal(node.props.showArrow, false);
  assert.equal(node.props.clearable, false);
  assert.equal(node.props.multiple, true);
  assert.deepEqual(node.props.options, [{ value: 10, label: 'Synthetic group' }]);
  assert.equal(node.props.valueDisplay().type, f.context.TagMore);
  f.trigger(node.props.valueDisplay()).props.onClick({});
  assert.equal(f.state.editingIndexSetRowId.value, 1);
  node = f.render(f.row);
  assert.equal(node.props.popupVisible, true);
  const slots = node.props['v-slots'];
  slots.panelTopContent().props.onChange('group');
  assert.equal(f.state.indexSetSearch.value, 'group');
  assert.equal(f.saves.length, 0);
  node.props.onChange([10, 11]);
  assert.deepEqual(f.state.editingIndexSetDraftIds.value[1], [10, 11]);
  assert.equal(f.saves.length, 0);
  assert.equal(slots.panelBottomContent().props.class, 'index-set-inline-extension');
  node.props.onPopupVisibleChange(false);
  assert.equal(f.state.indexSetSearch.value, '');
  assert.deepEqual(f.saves, [1]);
});

test('index-set cell preserves readonly and request-permission branches', () => {
  const f = fixture();
  assert.notEqual(f.render({ ...f.row, readonly: true }).type, f.context.TSelect);
  const request = f.render({ ...f.row, permission: {} });
  f.trigger(request).props.onClick({ preventDefault() {}, stopPropagation() {} });
  assert.deepEqual(f.auth, [1]);
  assert.equal(f.state.editingIndexSetRowId.value, '');
  assert.equal(f.saves.length, 0);
});


test('updating index-set cell cannot reopen its editor from the custom trigger', () => {
  const f = fixture();
  f.state.updatingIndexSetRowId.value = 1;
  const node = f.render(f.row);
  assert.equal(node.props.disabled, true);
  f.trigger(node.props.valueDisplay()).props.onClick({});
  assert.equal(f.state.editingIndexSetRowId.value, '');
  assert.equal(f.saves.length, 0);
});
