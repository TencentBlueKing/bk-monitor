import { test } from 'node:test';
import assert from 'node:assert/strict';
import * as Vue from 'vue';
import { loadTypeScript } from './helpers/load-typescript.mjs';
const util = loadTypeScript(new URL('../src/shared/utils/typed-record.ts', import.meta.url));
const { ConditionOperator } = loadTypeScript(new URL('../src/app/state/condition-operator.ts', import.meta.url), {
  '@/shared/utils/typed-record': util,
});
const { useQueryHistory } = loadTypeScript(
  new URL('../src/features/retrieval/workbench/sub-bar/use-query-history.ts', import.meta.url),
  {
    vue: Vue,
    '@/platform/services': { ServicesInstance: {} },
    '@/app/state/condition-operator': { ConditionOperator },
  },
);
const flush = () => new Promise((resolve) => setImmediate(resolve));
function fixture(handler = async () => ({ data: [] })) {
  const calls = [];
  const changes = [];
  const request = (name) => async (options) => {
    calls.push({ name, options });
    return handler(name, options);
  };
  const services = {
    retrieve: { getSearchHistory: request('ordinary'), getSceneSearchHistory: request('scene') },
    unionSearch: { unionSearchHistory: request('union') },
  };
  const context = Vue.reactive({
    isSceneMode: false,
    isUnionSearch: false,
    indexId: 16176,
    unionIndexList: [16176, 38131],
    retrieveParams: {
      space_uid: 'bkcc__5000140',
      table_id_conditions: [{ table_id: 'a' }],
      scene_filter_values: { x: ['y'] },
    },
  });
  const scope = Vue.effectScope();
  const history = scope.run(() =>
    useQueryHistory(
      () => ({ ...context }),
      (value) => changes.push(value),
      services,
    ),
  );
  return { history, context, calls, changes, scope };
}
const row = (query = 'log:"Error"') => ({
  id: 1,
  query_string: query,
  created_at: '2026-11-03 10:00:00',
  search_mode: 'sql',
  params: {
    keyword: query,
    addition: [{ field: 'log', operator: 'contains match phrase', value: ['Error'], relation: 'OR' }],
    ip_chooser: { host_list: ['test'] },
    scene_filter_values: { region: ['test'] },
    table_id_conditions: [{ table_id: 'a' }],
  },
});

test('ordinary/union/scene history retain V2 endpoints and their distinct request envelopes', async () => {
  const f = fixture();
  await f.history.requestSearchHistory();
  assert.deepEqual(f.calls.pop(), { name: 'ordinary', options: { params: { index_set_id: 16176 } } });
  f.context.isUnionSearch = true;
  await flush();
  await f.history.requestSearchHistory();
  assert.deepEqual(f.calls.pop(), { name: 'union', options: { params: { index_set_ids: [16176, 38131] } } });
  f.context.isSceneMode = true;
  await flush();
  await f.history.requestSearchHistory();
  assert.deepEqual(f.calls.pop(), {
    name: 'scene',
    options: {
      data: { space_uid: 'bkcc__5000140', table_id_conditions: [{ table_id: 'a' }], scene_filter_values: { x: ['y'] } },
    },
  });
  f.scope.stop();
});
test('history excludes bare wildcard and converts addition without mutating the response', async () => {
  const rows = [row('*'), row()];
  const original = structuredClone(rows);
  const f = fixture(async () => ({ data: rows }));
  await f.history.requestSearchHistory();
  assert.equal(f.history.historyRecords.value.length, 1);
  assert.deepEqual(f.history.historyRecords.value[0].params.addition, [
    new ConditionOperator(original[1].params.addition[0]).formatApiOperatorToFront(),
  ]);
  assert.deepEqual(rows, original);
  f.scope.stop();
});
test('history filters case-insensitively and restores every V2 query field and fallback mode', async () => {
  const f = fixture(async () => ({ data: [row(), { ...row('level:WARN'), id: 2 }] }));
  await f.history.requestSearchHistory();
  f.history.searchInput.value = 'ERROR';
  assert.equal(f.history.filterHistoryRecords.value.length, 1);
  const item = f.history.filterHistoryRecords.value[0];
  f.history.handleClickHistory(item);
  assert.deepEqual(f.changes, [
    {
      keyword: item.params.keyword,
      addition: item.params.addition,
      ip_chooser: item.params.ip_chooser,
      search_mode: 'sql',
      scene_filter_values: item.params.scene_filter_values,
      table_id_conditions: item.params.table_id_conditions,
    },
  ]);
  assert.equal(f.history.visible.value, false);
  assert.equal(f.history.historyRecords.value.length, 0);
  f.scope.stop();
});
test('bookmark child popup vetoes outside close, then history can close and reopen', async () => {
  const f = fixture();
  f.history.handleVisibleChange(true);
  assert.equal(f.history.visible.value, true);
  f.history.bookmarkPopRefsShow.value = true;
  f.history.handleVisibleChange(false);
  assert.equal(f.history.visible.value, true);
  f.history.bookmarkPopRefsShow.value = false;
  f.history.handleVisibleChange(false);
  assert.equal(f.history.visible.value, false);
  f.history.handleVisibleChange(true);
  assert.equal(f.calls.length, 2);
  f.scope.stop();
});
test('closing, changing index and unmounting reject late history responses', async () => {
  let resolve;
  const f = fixture(
    () =>
      new Promise((r) => {
        resolve = r;
      }),
  );
  f.history.handleVisibleChange(true);
  f.history.handleVisibleChange(false);
  resolve({ data: [row()] });
  await flush();
  assert.deepEqual(f.history.historyRecords.value, []);
  f.history.handleVisibleChange(true);
  f.history.bookmarkPopRefsShow.value = true;
  f.context.indexId = 38131;
  await flush();
  resolve({ data: [row()] });
  await flush();
  assert.equal(f.history.visible.value, false);
  assert.equal(f.history.bookmarkPopRefsShow.value, false);
  assert.deepEqual(f.history.historyRecords.value, []);
  f.history.handleVisibleChange(true);
  f.scope.stop();
  resolve({ data: [row()] });
  await flush();
  assert.equal(f.history.historyLoading.value, false);
  assert.deepEqual(f.history.historyRecords.value, []);
});
test('failure releases loading and supports retry without a stuck popup', async () => {
  let fail = true;
  const f = fixture(async () => {
    if (fail) throw Error('test request failed');
    return { data: [row()] };
  });
  await f.history.requestSearchHistory();
  assert.equal(f.history.historyLoading.value, false);
  fail = false;
  await f.history.requestSearchHistory();
  assert.equal(f.history.historyRecords.value.length, 1);
  f.scope.stop();
});
test('reopening ignores an older response without ending the newer loading state', async () => {
  const pending = [];
  const f = fixture(() => new Promise((resolve) => pending.push(resolve)));
  f.history.handleVisibleChange(true);
  f.history.handleVisibleChange(true);
  assert.equal(f.calls.length, 1);
  f.history.handleVisibleChange(false);
  f.history.handleVisibleChange(true);
  pending[0]({ data: [row('old')] });
  await flush();
  assert.equal(f.history.historyLoading.value, true);
  assert.deepEqual(f.history.historyRecords.value, []);
  pending[1]({ data: [row('new')] });
  await flush();
  assert.equal(f.history.historyLoading.value, false);
  assert.equal(f.history.historyRecords.value[0].query_string, 'new');
  f.scope.stop();
});
