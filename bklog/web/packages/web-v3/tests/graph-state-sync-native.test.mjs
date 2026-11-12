/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import ts from 'typescript';
import { isDeepStrictEqual } from 'node:util';
import { loadTypeScript } from './helpers/load-typescript.mjs';
const file = new URL(
  '../src/features/retrieval/workbench/search-result-panel/graph-analysis/index.tsx',
  import.meta.url,
);
function fixture() {
  const store = {
    indexItem: {
      chart_params: {
        xFields: [],
        yFields: [],
        dimensions: [],
        hiddenFields: [],
        activeGraphCategory: 'table',
        chartActiveType: 'table',
        sql: 'SELECT 1',
      },
    },
  };
  const deps = {};
  for (const [, id] of readFileSync(file, 'utf8').matchAll(/from ['"]([^'"]+)['"]/g)) deps[id] = {};
  deps['vue-property-decorator'] = {
    Component: Object.assign(() => (ctor) => ctor, { registerHooks() {} }),
    Watch: () => () => {},
  };
  deps['vue-tsx-support'] = { Component: class {} };
  deps['lodash-es'] = {
    debounce: (fn) => Object.assign(fn, { cancel() {} }),
    throttle: (fn) => Object.assign(fn, { cancel() {} }),
    isEqual: isDeepStrictEqual,
  };
  deps['@/app/state/domains/application-store'] = { useApplicationStore: () => store };
  deps['@/shared/utils/typed-record'] = { includesValue: (list, value) => list.includes(value) };
  deps['@/app/state/store.type.ts'] = { BK_LOG_STORAGE: {}, SEARCH_MODE_DIC: {} };
  deps['./index.scss'] = {};
  const Class = loadTypeScript(file, deps, {
    experimentalDecorators: true,
    useDefineForClassFields: false,
    jsx: ts.JsxEmit.ReactJSX,
    jsxImportSource: 'vue',
  }).default;
  return { store, vm: new Class() };
}
test('category changes retain SQL-derived axes; explicit changed and empty axes still restore', (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const { store, vm } = fixture();
  vm.handleChartParamsChange();
  t.mock.timers.tick(1);
  vm.setDefaultFieldSettings([
    { field_alias: 'minute1', field_type: 'string' },
    { field_alias: 'log_count', field_type: 'long' },
  ]);
  assert.deepEqual(vm.xFields, ['minute1']);
  assert.deepEqual(vm.yFields, ['log_count']);
  Object.assign(store.indexItem.chart_params, { activeGraphCategory: 'line', chartActiveType: 'chart' });
  vm.handleChartParamsChange();
  t.mock.timers.tick(1);
  assert.deepEqual(vm.xFields, ['minute1']);
  assert.deepEqual(vm.yFields, ['log_count']);
  assert.equal(vm.activeGraphCategory, 'line');
  store.indexItem.chart_params.xFields = ['host'];
  vm.handleChartParamsChange();
  t.mock.timers.tick(1);
  assert.deepEqual(vm.xFields, ['host']);
  assert.deepEqual(vm.yFields, ['log_count']);
  store.indexItem.chart_params.xFields = [];
  vm.handleChartParamsChange();
  t.mock.timers.tick(1);
  assert.deepEqual(vm.xFields, []);
  assert.deepEqual(vm.yFields, ['log_count']);
});
test('favorite-style multi-field restore preserves SQL and detached snapshots without writing back', (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const { store, vm } = fixture();
  vm.handleChartParamsChange();
  t.mock.timers.tick(1);
  Object.assign(store.indexItem.chart_params, {
    xFields: ['pod'],
    yFields: ['count'],
    dimensions: ['time'],
    hiddenFields: ['internal'],
    activeGraphCategory: 'bar',
    chartActiveType: 'chart',
    sql: 'SELECT count',
  });
  vm.handleChartParamsChange();
  t.mock.timers.tick(1);
  assert.deepEqual(vm.xFields, ['pod']);
  assert.deepEqual(vm.yFields, ['count']);
  assert.deepEqual(vm.dimensions, ['time']);
  assert.deepEqual(vm.hiddenFields, ['internal']);
  assert.equal(vm.sqlContent, 'SELECT count');
  vm.xFields.push('local');
  assert.deepEqual(store.indexItem.chart_params.xFields, ['pod']);
  assert.deepEqual(vm.chartParamsSnapshot.xFields, ['pod']);
});
