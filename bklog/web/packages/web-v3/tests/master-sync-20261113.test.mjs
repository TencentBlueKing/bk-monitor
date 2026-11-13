import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import ts from 'typescript';
import { createPinia, defineStore } from 'pinia';
import { loadTypeScript } from './helpers/load-typescript.mjs';

const source = path => readFileSync(new URL(`../src/${path}`, import.meta.url), 'utf8');
function method(path, name, dependencies) {
  const text = source(path), ast = ts.createSourceFile(path, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  let body;
  const visit = node => {
    if (ts.isMethodDeclaration(node) && node.name.getText(ast) === name) body = node.body.getText(ast);
    ts.forEachChild(node, visit);
  };
  visit(ast);
  assert.ok(body, name);
  const js = ts.transpileModule(`async function run() ${body}`, { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText;
  return new Function(...Object.keys(dependencies), `${js}; return run;`)(...Object.values(dependencies));
}

test('missing space clears masking state and never requests authority or rule data', async () => {
  const warnings = [], requests = [];
  const run = method('features/masking/components/masking-setting.tsx', 'initTableList', {
    TDesignMessage: { warning: value => warnings.push(value) },
    useApplicationStore: () => ({ checkAndGetData: () => { requests.push('authority'); } }),
    ServicesInstance: { masking: { getMaskingRuleList: () => { requests.push('rules'); } } },
  });
  const context = {
    spaceUid: undefined, tableLoading: false, isAllowed: true, emptyType: '500',
    pagination: { current: 3, count: 6, limit: 10 },
    $t: text => text,
    changePagination(value) { Object.assign(this.pagination, value); },
  };
  for (const key of ['tableList', 'tableSearchList', 'tableShowList', 'tableStrList', 'updateSourceFilters']) context[key] = ['synthetic'];
  await run.call(context);
  assert.deepEqual(requests, []);
  for (const key of ['tableList', 'tableSearchList', 'tableShowList', 'tableStrList', 'updateSourceFilters']) assert.deepEqual(context[key], []);
  assert.deepEqual(context.pagination, { current: 1, count: 0, limit: 10 });
  assert.equal(context.emptyType, 'empty');
  assert.equal(context.isAllowed, false);
  assert.equal(context.tableLoading, false);
  assert.deepEqual(warnings, ['请先选择业务']);
  assert.match(source('features/masking/components/masking-setting.tsx'), /@Watch\('\$route.query.spaceUid', \{ immediate: true \}\)/);
});

test('selected space retains permission checks, public/private request modes and loading cleanup', async () => {
  for (const isPublicList of [true, false]) {
    const calls = [];
    const run = method('features/masking/components/masking-setting.tsx', 'initTableList', {
      TDesignMessage: { warning: () => assert.fail('unexpected warning') },
      useApplicationStore: () => ({ checkAndGetData: async value => { calls.push(['authority', value]); return { isAllowed: true }; } }),
      ServicesInstance: { masking: { getMaskingRuleList: async value => { calls.push(['rules', value]); return { data: [] }; } } },
      useUtils: () => ({ formatResponseListTimeZoneString: value => value }),
    });
    const context = {
      spaceUid: 'synthetic-space', isPublicList, authorityData: { action_ids: ['synthetic-permission'] },
      pagination: { current: 2, count: 2, limit: 10 },
      changePagination(value) { Object.assign(this.pagination, value); },
    };
    await run.call(context);
    assert.deepEqual(calls, [
      ['authority', context.authorityData],
      ['rules', { params: { space_uid: 'synthetic-space', rule_type: isPublicList ? 'public' : 'all' } }],
    ]);
    assert.equal(context.isAllowed, true);
    assert.equal(context.tableLoading, false);
    assert.deepEqual(context.tableShowList, []);
    assert.equal(context.pagination.current, 1);
  }
});

test('platform config uses the native Pinia action to apply shared-resource metadata', async t => {
  const calls = [], pinia = createPinia();
  const previousWindow = globalThis.window;
  globalThis.window = { VERSION: 'synthetic', BK_SHARED_RES_URL: 'https://example.invalid/shared' };
  t.after(() => { if (previousWindow === undefined) delete globalThis.window; else globalThis.window = previousWindow; });
  const { usePlatformConfigStore } = loadTypeScript(new URL('../src/app/state/modules/platform-config.ts', import.meta.url), {
    pinia: { defineStore },
    '../pinia': { applicationPinia: pinia },
    '@blueking/platform-config': {
      getPlatformConfig: async (...args) => { calls.push(args); return { favicon: 'synthetic.svg', i18n: { name: 'Synthetic' } }; },
      setShortcutIcon: value => calls.push(['icon', value]),
      setDocumentTitle: value => calls.push(['title', value]),
    },
  });
  // The production module reads window at evaluation time and at request time.
  const store = usePlatformConfigStore(pinia);
  await store.fetchConfig();
  assert.equal(calls.length, 3);
  assert.equal(calls[0][0], 'https://example.invalid/shared//bk_log_search/base.js');
  calls.length = 0;
  globalThis.window.BK_SHARED_RES_URL = '';
  await store.fetchConfig();
  assert.equal(calls[0][0].name, '日志平台');
  assert.equal(store.publicConfig.favicon, 'synthetic.svg');
  assert.match(source('app/shell/app.tsx'), /setup\(\) \{[\s\S]*?usePlatformConfigStore\(\).fetchConfig\(\)/);
});

test('cleaning debug sources disable denied permissions but retain permission application content', () => {
  const text = source('features/collection/current/components/create-operation/step3-clean.tsx');
  const ast = ts.createSourceFile('step.tsx', text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  let declaration;
  const visit = node => {
    if (ts.isVariableDeclaration(node) && node.name.getText(ast) === 'renderCollectorOptions') declaration = node.getText(ast);
    ts.forEachChild(node, visit);
  };
  visit(ast);
  const js = ts.transpileModule(`const ${declaration};`, { compilerOptions: { target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.React, jsxFactory: 'h' } }).outputText;
  const items = [undefined, {}, { manage: false }, { manage: true }].map((permission, i) => ({ collector_config_id: i + 1, collector_config_name: `Synthetic ${i}`, permission }));
  const render = new Function('cleanCollectorList', 'authorityMap', 'h', 't', 'applyProjectAccess', `${js};return renderCollectorOptions;`)(
    { value: items }, { MANAGE_COLLECTION_AUTH: 'manage' }, (type, props, ...children) => ({ type, props, children }), x => x, () => {},
  );
  assert.deepEqual(render().map(node => node.props.disabled), [true, true, true, false]);
});
