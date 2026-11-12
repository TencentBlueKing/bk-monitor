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
import { createPinia } from 'pinia';
import { loadTypeScript } from './helpers/load-typescript.mjs';
const collectionModule = loadTypeScript(new URL('../src/app/state/domains/collection-store.ts', import.meta.url), {
  '../pinia': { applicationPinia: createPinia(), resolveApplicationPinia: (pinia) => pinia },
});
test('native collection keeps replacement merge and export semantics with isolated Pinia instances', () => {
  const a = collectionModule.useCollectionStore(createPinia()),
    b = collectionModule.useCollectionStore(createPinia());
  a.setCurCollect({ id: 7, name: 'original' });
  a.updateCurCollect({ name: 'edited', extra: true });
  assert.deepEqual(a.curCollect, { id: 7, name: 'edited', extra: true });
  assert.deepEqual(b.curCollect, {});
  a.setCurCollect({ id: 9 });
  assert.deepEqual(a.curCollect, { id: 9 });
  a.updateCurIndexSet({ index_set_id: 16176 });
  a.updateScenarioMap({ host: 'host' });
  a.updateExportCollectObj({
    collectID: 9,
    syncType: ['all'],
    collect: { name: 'export' },
  });
  assert.equal(a.curIndexSet.index_set_id, 16176);
  assert.equal(a.exportCollectObj.collectID, 9);
  assert.equal(a.$state.state, undefined, 'native state is flat, not nested behind Vuex-shaped state');
});
test('native collection exposes one action lifecycle and preserves own flat state', () => {
  const pinia = createPinia(),
    store = collectionModule.useCollectionStore(pinia),
    events = [];
  store.$onAction(({ name }) => events.push(name));
  store.setCurCollect({ id: 1 });
  store.updateCurCollect({ name: 'same-owner' });
  assert.equal(collectionModule.useCollectionStore(pinia), store);
  assert.deepEqual(events, ['setCurCollect', 'updateCurCollect']);
  assert.equal(store.$state.curCollect, store.curCollect);
  assert.deepEqual(Object.keys(pinia.state.value), ['bklog.collect']);
});

const globalsModule = loadTypeScript(new URL('../src/app/state/domains/globals-store.ts', import.meta.url), {
  '../pinia': { applicationPinia: createPinia(), resolveApplicationPinia: (pinia) => pinia },
  '../constant': {
    fieldTypeMap: {
      keyword: { name: 'keyword', color: '#fff', icon: 'keyword' },
    },
  },
});
test('native globals isolates initial metadata and keeps replace and permission-state semantics', () => {
  const a = globalsModule.useGlobalsStore(createPinia());
  const b = globalsModule.useGlobalsStore(createPinia());
  a.fieldTypeMap.keyword.name = 'local';
  assert.equal(b.fieldTypeMap.keyword.name, 'keyword');
  a.setGlobalsData({ one: 1 });
  a.updateGlobalsData({ two: 2 });
  assert.deepEqual(a.globalsData, { two: 2 });
  a.updateAuthContainerInfo({ permission: false });
  assert.deepEqual(a.authContainerInfo, { permission: false });
  a.updateAuthContainerInfo(null);
  assert.equal(a.authContainerInfo, null);
});
