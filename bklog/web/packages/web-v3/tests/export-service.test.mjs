/* Copyright (C) 2021 THL A29 Limited, a Tencent company.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS), MIT License. */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import ts from 'typescript';
const source = readFileSync(
  new URL('../src/features/retrieval/workbench/result-comp/download/exportTask.ts', import.meta.url),
  'utf8',
);
const ast = ts.createSourceFile('exportTask.ts', source, ts.ScriptTarget.Latest, true);
let code = source;
for (const node of [...ast.statements].reverse())
  if (ts.isImportDeclaration(node)) code = code.slice(0, node.getStart(ast)) + code.slice(node.end);
const { outputText } = ts.transpileModule(code, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
});
const services = Object.fromEntries(
  ['getSceneAsyncExport', 'unionExportAsync', 'exportAsync'].map((name) => [
    name,
    Object.assign(() => {}, { id: `retrieve/${name}` }),
  ]),
);
const api = {};
let confirmAction = false;
const nativeDialog = {
  confirm(options) {
    queueMicrotask(() => (confirmAction ? options.onConfirm : options.onClose)());
    return { destroy() {} };
  },
};
new Function('exports', 'cloneDeep', 'ServicesInstance', 'TDesignDialog', 'TDesignMessage', outputText)(
  api,
  structuredClone,
  { retrieve: services },
  nativeDialog,
  () => {},
);
const task = {
  log_index_set_id: 900102,
  log_index_set_ids: [900102, 40679],
  engine: 'legacy',
  export_type: 'async',
  search_dict: { sort_list: [['dtEventTime', 'DESC']], keyword: 'fixture' },
};

test('export retry chooses named endpoints and preserves the saved query snapshot', () => {
  for (const [type, name] of [
    ['single', 'exportAsync'],
    ['union', 'unionExportAsync'],
    ['scene', 'getSceneAsyncExport'],
  ]) {
    const original = { ...task, index_set_type: type };
    const snapshot = structuredClone(original);
    const request = api.buildExportRetryRequest(original);
    assert.equal(request.service, services[name]);
    assert.equal(request.isSync, false);
    request.config.data.sort_list.push(['fixture', 'ASC']);
    assert.deepEqual(original, snapshot);
  }
  const union = api.buildExportRetryRequest({ ...task, index_set_type: 'union' });
  assert.deepEqual(union.config.data.union_configs, [
    { begin: 0, index_set_id: 900102 },
    { begin: 0, index_set_id: 40679 },
  ]);
  assert.equal(union.config.data.is_quick_export, false);
});
test('synchronous download URLs remain separate from service dispatch', () => {
  for (const [type, url] of [
    ['single', '/search/index_set/900102/export/'],
    ['union', '/search/index_set/union_search/export/'],
    ['scene', '/search/scene/export/sample/'],
  ]) {
    const request = api.buildExportRetryRequest({ ...task, index_set_type: type, export_type: 'sync' });
    assert.equal(request.isSync, true);
    assert.equal(request.url, url);
  }
});
for (const confirm of [false, true]) {
  test(`sort preflight only resubmits after confirmation: ${confirm}`, async () => {
    const requests = [];
    const original = { data: { sort_list: [['dtEventTime', 'DESC']] } };
    const operation = async (config) => {
      requests.push(structuredClone(config));
      return requests.length === 1
        ? { result: true, data: { requires_sort_confirmation: true, sort_list: [['gseIndex', 'ASC']] } }
        : { result: true, data: { task_id: 'fixture' } };
    };
    confirmAction = confirm;
    const context = { $t: (s) => s };
    const result = await api.submitExportWithSortConfirmation(context, operation, original);
    assert.equal(requests.length, confirm ? 2 : 1);
    assert.deepEqual(original.data.sort_list, [['dtEventTime', 'DESC']]);
    if (confirm) assert.deepEqual(requests[1].data.sort_list, [['gseIndex', 'ASC']]);
    else assert.equal(result, null);
  });
}
