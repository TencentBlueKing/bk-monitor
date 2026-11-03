/* Copyright (C) 2021 THL A29 Limited, a Tencent company, MIT License. */
import { test } from 'node:test';
import * as Vue from 'vue';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import ts from 'typescript';
import { createRequire } from 'node:module';
import { loadScriptSetup } from './helpers/load-script-setup.mjs';
import { loadTypeScript } from './helpers/load-typescript.mjs';
import { baselineUrl } from '../tools/source-baseline.mjs';
const require = createRequire(import.meta.url);
const { parse } = require('@vue/compiler-sfc');
const { ConditionOperator } = loadTypeScript(new URL('../src/app/state/condition-operator.ts', import.meta.url), {
  '@/shared/utils/typed-record': { includesValue: (list, value) => list.includes(value) },
});
const current = new URL('../src/features/retrieval/workbench/sub-bar/', import.meta.url);
const sample = () => ({
  search_mode: 'sql',
  query_string: 'ERROR',
  params: {
    keyword: 'ERROR',
    addition: [{ field: 'level', operator: 'is', value: ['ERROR'] }],
    ip_chooser: {},
    scene_filter_values: [{ field: 'host', value: ['fixture'] }],
    table_id_conditions: [[{ field: 'table_id', value: ['fixture'] }]],
  },
});

test('ordinary, union and scene history preserve V2 endpoint, parameters, operator conversion and refill payload', async () => {
  for (const mode of ['ordinary', 'union', 'scene']) {
    const results = [];
    for (const file of [
      baselineUrl('views/retrieve-v2/sub-bar/query-history.vue'),
      new URL('query-history.vue', current),
    ]) {
      const calls = [],
        emits = [];
      const request = async (id, options) => {
        calls.push([id, structuredClone(options)]);
        return { data: [{ query_string: '*' }, sample()] };
      };
      if (file.href === new URL('query-history.vue', current).href) {
        const { useQueryHistory } = loadTypeScript(new URL('use-query-history.ts', current), {
          vue: Vue,
          '@/platform/services': { ServicesInstance: {} },
          '@/app/state/condition-operator': { ConditionOperator },
        });
        const scope = Vue.effectScope();
        const history = scope.run(() =>
          useQueryHistory(
            () => ({
              isSceneMode: mode === 'scene',
              isUnionSearch: mode === 'union',
              indexId: '16176',
              unionIndexList: ['16176', '40678'],
              retrieveParams: {
                space_uid: 'fixture-space',
                table_id_conditions: sample().params.table_id_conditions,
                scene_filter_values: sample().params.scene_filter_values,
              },
            }),
            (params) => emits.push(['change', params]),
            {
              retrieve: {
                getSearchHistory: (options) => request('retrieve/getSearchHistory', options),
                getSceneSearchHistory: (options) => request('retrieve/getSceneSearchHistory', options),
              },
              unionSearch: { unionSearchHistory: (options) => request('unionSearch/unionSearchHistory', options) },
            },
          ),
        );
        await history.requestSearchHistory();
        assert.equal(history.historyLoading.value, false);
        assert.equal(history.historyRecords.value.length, 1);
        history.handleClickHistory(history.historyRecords.value[0]);
        assert.equal(history.visible.value, false, 'native popup closes after restoring history');
        scope.stop();
      } else {
        const component = loadScriptSetup(file, { $http: { request }, ConditionOperator });
        const vm = {
          ...component.data(),
          ...component.methods,
          $http: { request },
          $emit: (...args) => emits.push(args),
          isSceneMode: mode === 'scene',
          isUnionSearch: mode === 'union',
          indexId: '16176',
          unionIndexList: ['16176', '40678'],
          retrieveParams: {
            space_uid: 'fixture-space',
            table_id_conditions: sample().params.table_id_conditions,
            scene_filter_values: sample().params.scene_filter_values,
          },
          popoverInstance: { hide: () => emits.push(['hide']) },
        };
        vm.requestSearchHistory();
        for (let i = 0; i < 8; i++) await Promise.resolve();
        assert.equal(vm.historyLoading, false);
        assert.equal(vm.historyRecords.length, 1);
        vm.handleClickHistory(vm.historyRecords[0]);
        assert.deepEqual(emits.at(-1), ['hide']);
      }
      assert.equal(emits[0][0], 'change');
      assert.equal(emits[0][1].keyword, 'ERROR');
      assert.equal(emits[0][1].search_mode, 'sql');
      assert.deepEqual(emits[0][1].scene_filter_values, sample().params.scene_filter_values);
      results.push({ calls, emits: emits.filter((event) => event[0] !== 'hide') });
    }
    assert.deepEqual(results[1], results[0]);
    const [id, options] = results[1].calls[0];
    assert.equal(
      id,
      mode === 'scene'
        ? 'retrieve/getSceneSearchHistory'
        : mode === 'union'
          ? 'unionSearch/unionSearchHistory'
          : 'retrieve/getSearchHistory',
    );
    if (mode === 'ordinary') assert.deepEqual(options, { params: { index_set_id: '16176' } });
    if (mode === 'union') assert.deepEqual(options, { params: { index_set_ids: ['16176', '40678'] } });
    if (mode === 'scene') assert.equal(options.data.space_uid, 'fixture-space');
  }
});

function refill(file, scene, hasFields) {
  const { descriptor } = parse(readFileSync(file, 'utf8'));
  const block = descriptor.scriptSetup.content;
  const source = ts.createSourceFile('source.ts', block, ts.ScriptTarget.Latest, true);
  let handler;
  function visit(node) {
    if (ts.isVariableDeclaration(node) && node.name.getText(source) === 'handleHistoryChange')
      handler = node.initializer;
    else ts.forEachChild(node, visit);
  }
  visit(source);
  assert.ok(handler);
  const calls = [],
    timers = [];
  const context = {
    ConditionOperator,
    store: {
      getters: { isSceneMode: scene },
      commit: (...args) => calls.push(['commit', ...args]),
      dispatch: async (id) => {
        calls.push(['dispatch', id]);
        return { data: { fields: hasFields ? [{ field_name: 'log' }] : [] } };
      },
    },
    BK_LOG_STORAGE: { SEARCH_TYPE: 'searchType' },
    setRouteQuery: () => calls.push(['route']),
    getInputQueryIpSelectItem: (value) => ({ field: '_ip-select_', value }),
    parseTableIdConditions: (table, filters) => {
      calls.push(['parse-scene', table, filters]);
      return { scene_active: 'fixture-scene', scene_filter_values: filters };
    },
    RetrieveHelper: { fire: (id) => calls.push(['fire', id]) },
    RetrieveEvent: { TREND_GRAPH_SEARCH: 'trend-search', SCENE_FIELD_EMPTY: 'scene-empty' },
    setTimeout: (fn) => timers.push(fn),
  };
  const code = ts.transpileModule(`const handler=${handler.getText(source)};`, {
    compilerOptions: { target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const run = new Function(...Object.keys(context), `${code}\nreturn handler;`)(...Object.values(context));
  return { calls, timers, run };
}

test('history refill matches V2 commits and requests fields before scene search, including empty-field recovery', async () => {
  for (const [scene, hasFields] of [
    [false, true],
    [true, true],
    [true, false],
  ]) {
    const outcomes = [];
    for (const file of [baselineUrl('views/retrieve-v2/sub-bar/index.vue'), new URL('index.vue', current)]) {
      const fixture = refill(file, scene, hasFields);
      fixture.run({ ...sample().params, search_mode: 'sql' });
      assert.equal(
        fixture.calls.some((c) => c[0] === 'dispatch'),
        false,
        'search waits for the source timer',
      );
      for (const timer of fixture.timers) timer();
      for (let i = 0; i < 5; i++) await Promise.resolve();
      outcomes.push(fixture.calls);
      const requests = fixture.calls.filter((c) => c[0] === 'dispatch').map((c) => c[1]);
      assert.deepEqual(
        requests,
        scene
          ? hasFields
            ? ['requestIndexSetFieldInfo', 'requestIndexSetQuery']
            : ['requestIndexSetFieldInfo']
          : ['requestIndexSetQuery'],
      );
      assert.deepEqual(fixture.calls.at(-1), ['fire', scene && !hasFields ? 'scene-empty' : 'trend-search']);
    }
    assert.deepEqual(outcomes[1], outcomes[0]);
  }
});
