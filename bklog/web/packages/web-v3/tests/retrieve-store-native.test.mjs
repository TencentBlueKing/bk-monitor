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
const business = new WeakMap();
let indexRequest, sceneRequest;
const mod = loadTypeScript(new URL('../src/app/state/domains/retrieve-store.ts', import.meta.url), {
  '../pinia': { applicationPinia: createPinia(), resolveApplicationPinia: pinia => pinia },
  './application-store': { useApplicationStore: (pinia) => ({ bkBizId: business.get(pinia) }) },
  '@/platform/services': {
    ServicesInstance: {
      retrieve: {
        getIndexSetList: (options) => indexRequest(options),
        getSceneConfigs: (options) => sceneRequest(options),
      },
    },
  },
  '../scene-filter-config': { transformSceneConfigs: (items) => items.map((item) => ({ ...item, transformed: true })) },
});
test('native retrieve preserves ID normalization, permission order, tree keys, flat list and response tuple', async () => {
  const pinia = createPinia(),
    store = mod.useRetrieveStore(pinia),
    other = mod.useRetrieveStore(createPinia());
  const response = {
    data: [
      { index_set_id: 2, index_set_name: 'second', auth_wieght: 0 },
      {
        index_set_id: 1,
        index_set_name: 'first',
        auth_wieght: 1,
        parent_node: 'drop',
        indices: [
          { result_table_id: 'a' },
          { result_table_id: 'b' },
          { result_table_id: 'c' },
          { result_table_id: 'd' },
        ],
        children: [{ index_set_id: 3, index_set_name: 'child' }],
      },
    ],
  };
  let resolve;
  indexRequest = (options) => {
    assert.deepEqual(options, { query: { space_uid: 'space', is_group: true } });
    return new Promise((done) => (resolve = done));
  };
  store.updateIndexSetList([{ index_set_id: 'stale' }]);
  const pending = store.getIndexSetList({ spaceUid: 'space', is_group: true });
  assert.equal(store.isIndexSetLoading, true);
  assert.equal(store.indexSetList.length, 0);
  resolve(response);
  const result = await pending;
  assert.equal(result[0], response);
  assert.deepEqual(
    store.indexSetList.map((item) => item.index_set_id),
    ['1', '2'],
  );
  assert.equal(store.indexSetList[0].unique_id, '#_1');
  assert.equal(store.indexSetList[0].children[0].unique_id, '1_3');
  assert.equal(store.indexSetList[0].lightenName, ' (a;b;c+1)');
  assert.equal('parent_node' in store.indexSetList[0], false);
  assert.deepEqual(
    store.flatIndexSetList.map((item) => item.index_set_id),
    ['1', '3', '2'],
  );
  assert.equal(store.isIndexSetLoading, false);
  assert.deepEqual(other.indexSetList, []);
  indexRequest = () => Promise.reject(new Error('offline'));
  await assert.rejects(store.getIndexSetList({ spaceUid: 'space' }), /offline/);
  assert.equal(store.isIndexSetLoading, false);
  assert.deepEqual(store.indexSetList, []);
});
test('scene requests use the action owning Pinia instance and retain failure/empty/finally semantics', async () => {
  const pa = createPinia(),
    pb = createPinia();
  business.set(pa, 'biz-a');
  business.set(pb, 'biz-b');
  const a = mod.useRetrieveStore(pa),
    b = mod.useRetrieveStore(pb);
  sceneRequest = async (options) => ({ data: [{ id: options.query.bk_biz_id }] });
  assert.deepEqual(await a.requestSceneConfigs(), [{ id: 'biz-a' }]);
  assert.deepEqual(await b.requestSceneConfigs(), [{ id: 'biz-b' }]);
  assert.equal(a.sceneConfigList[0].transformed, true);
  assert.equal(a.sceneConfigs.is_loading, false);
  sceneRequest = async () => {
    throw new Error('fixture scene failure');
  };
  assert.deepEqual(await a.requestSceneConfigs(), []);
  assert.deepEqual(a.sceneConfigs.data, []);
  assert.equal(a.sceneConfigs.is_loading, false);
  assert.equal(b.sceneConfigs.data[0].id, 'biz-b');
});
test('retrieve cache merge and cleanup retain V2 empty-addition and shell-state behavior', () => {
  const store = mod.useRetrieveStore(createPinia());
  store.updateCatchFieldCustomConfig({ fixedFilterAddition: true, displayFields: ['log'], fieldsWidth: { log: 300 } });
  store.updateCatchFieldCustomConfig({ sortList: [['time', 'desc']] });
  assert.equal(store.catchFieldCustomConfig.fixedFilterAddition, true);
  assert.deepEqual(store.catchFieldCustomConfig.displayFields, []);
  store.updateCatchFilterAddition({ addition: [{ field: 'log', value: ['x'] }] });
  store.updateCatchFilterAddition({ addition: [] });
  assert.equal(store.catchFieldCustomConfig.filterAddition.length, 1);
  store.updateTrendShellPending(false);
  store.updateResultShellReady(true);
  store.resetRuntimeState();
  assert.equal(store.trendShellPending, false);
  assert.equal(store.resultShellReady, true);
  assert.equal(store.catchFieldCustomConfig.fixedFilterAddition, false);
  assert.deepEqual(store.sceneConfigs, { is_loading: false, data: [] });
});
