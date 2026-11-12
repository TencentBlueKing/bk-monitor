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
import { defineStore, createPinia } from 'pinia';
import { loadTypeScript } from './helpers/load-typescript.mjs';
let fieldsRequest,
  seq = 0;
const jobs = [],
  canceled = [],
  effects = [];
const api = Object.assign((...args) => fieldsRequest(...args), { id: 'retrieve/getLogTableHead' });
const fieldCache = {
  getFieldList: () => [{ field_name: 'log' }],
  getFieldNameIndex: () => ({ log: { field_name: 'log' } }),
};
const rowCache = {
  createQueryKey: () => 'query-' + ++seq,
  getRows: async (keys) => keys.map((log) => ({ log })),
  releaseQuery() {},
  clearQuery: async () => {},
  gc: async () => {},
  clearMemory() {},
};
const health = { clearActiveQuery() {}, markActiveQuery() {}, getActiveQueryKeys: async () => [] };
const worker = {
  cancelSearch: (id) => canceled.push(id),
  searchStream: (options) =>
    new Promise((resolve, reject) => {
      const id = 'request-' + jobs.length;
      options.onRequestId(id);
      jobs.push({ options, id, resolve, reject });
    }),
};
const mod = loadTypeScript(new URL('../src/app/state/actions/retrieve-search-actions.js', import.meta.url), {
  '@/platform/services': {
    ServicesInstance: { retrieve: { getLogTableHead: api, getSceneFields: api }, unionSearch: { unionMapping: api } },
  },
  axios: { isCancel: (e) => e?.code === 'ERR_CANCELED' },
  '@/shared/lib/util': { parseBigNumberList: (x) => x },
  '@/shared/ui/time-range/utils': { handleTransformToTimestamp: () => [1, 2] },
  '@/platform/persistence/index': {
    retrieveFieldCacheService: fieldCache,
    retrieveRowCacheService: rowCache,
    retrieveSearchWorkerService: worker,
    storageHealthService: health,
    storeCacheService: { setApiCache: async (...args) => effects.push(args) },
  },
  '@/platform/persistence/utils/retrieve-field-meta': { normalizeRetrieveFields: (data) => data.fields ?? [] },
  '@/platform/persistence/utils/normalize-search-total': { normalizeSearchTotal: (x) => Number(x) || 0 },
  '../helper.ts': {
    isSceneRetrieve: (state) => state.indexItem.retrieve_type === 'scene',
    formatAdditionalFields: (_state, list) => list,
    getCommonFilterAdditionWithValues: () => [],
  },
  '../modules/report-helper.ts': { reportRouteLog() {} },
});
class Pool {
  tokens = new Map();
  execCanceToken(key) {
    this.tokens.get(key)?.();
    this.tokens.delete(key);
  }
  getCancelToken(key) {
    const value = {};
    this.tokens.set(key, () => {});
    return value;
  }
  setCancelToken(key, fn) {
    this.tokens.set(key, fn);
  }
}
const useQuery = defineStore('fixture.query', {
  state: () => ({
    indexId: '900101',
    bkBizId: '900001',
    spaceUid: 'space',
    userMeta: {},
    mySpaceList: [],
    searchTotal: 2,
    tookTime: 0,
    unionIndexList: [],
    visibleFields: [{ field_name: 'log' }],
    indexItem: {
      ids: ['900101'],
      begin: 0,
      datePickerValue: ['2026-01-01', '2026-01-02'],
      start_time: 's',
      end_time: 'e',
      timezone: 'UTC',
      catchUnionBeginList: [],
    },
    indexFieldInfo: { field_scope: '900101', is_loading: false, time_field: 'time' },
    indexSetQueryResult: {
      row_keys: [],
      row_query_key: '',
      cached_count: 0,
      total: 0,
      took: 0,
      search_count: 0,
      is_error: false,
      is_loading: false,
      is_pagination_loading: false,
    },
    apiErrorInfo: {},
    retrieve: {
      configId: 0,
      updateFiledSettingConfigID(id) {
        this.configId = id;
      },
      updateCatchFieldCustomConfig() {},
    },
    requestPool: new Pool(),
  }),
  getters: {
    retrieveParams: () => ({ size: 10, format: 'date', addition: [], sort_list: [], table_id_conditions: [] }),
    requestAddition: () => [],
  },
  actions: {
    resetIndexFieldInfo(payload) {
      Object.assign(this.indexFieldInfo, { is_loading: false }, payload);
    },
    updateIndexFieldInfo(payload) {
      Object.assign(this.indexFieldInfo, payload);
    },
    updataOperatorDictionary() {},
    updateNotTextTypeFields() {},
    updateIndexSetFieldConfig() {},
    updateVisibleFields() {},
    deleteApiError(name) {
      delete this.apiErrorInfo[name];
    },
    updateApiError({ apiName, errorMessage }) {
      this.apiErrorInfo[apiName] = errorMessage;
    },
    resetVisibleFields() {},
    resetIndexSetOperatorConfig() {},
    updateIsSetDefaultTableColumn() {},
    updateIndexSetQueryResult(payload) {
      Object.assign(this.indexSetQueryResult, payload);
    },
    resetIndexSetQueryResult(payload) {
      Object.assign(this.indexSetQueryResult, { row_keys: [], row_query_key: '', cached_count: 0 }, payload);
    },
    updateIndexItem(payload) {
      Object.assign(this.indexItem, payload);
    },
    updateSqlQueryFieldList() {},
    updateState(payload) {
      Object.assign(this, payload);
    },
  },
});
const app = () => useQuery(createPinia());
const response = (rows, total = rows.length) => ({
  result: true,
  data: { total, took: 1, union_configs: [] },
  rowKeys: rows,
  size: rows.length,
  source: 'fixture',
});
test('field requests deduplicate within an owner and remain independent across Pinia instances', async () => {
  const a = app(),
    b = app(),
    pending = [];
  fieldsRequest = (options, config) => new Promise((resolve) => pending.push({ options, config, resolve }));
  const first = mod.requestIndexSetFieldInfoAction(new Proxy(a, {})),
    duplicate = mod.requestIndexSetFieldInfoAction(new Proxy(a, {})),
    other = mod.requestIndexSetFieldInfoAction(b);
  assert.equal(first, duplicate);
  assert.equal(pending.length, 2);
  assert.notEqual(pending[0].config.cancelToken, pending[1].config.cancelToken);
  assert.equal(a.indexFieldInfo.is_loading, true);
  pending[0].resolve({ data: { fields: [{ field_name: 'log' }], config_id: 11, user_custom_config: {} } });
  pending[1].resolve({ data: { fields: [{ field_name: 'path' }], config_id: 22, user_custom_config: {} } });
  await Promise.all([first, other]);
  assert.equal(a.retrieve.configId, 11);
  assert.equal(b.retrieve.configId, 22);
  assert.equal(a.indexFieldInfo.fields[0].filterVisible, true);
  assert.equal(a.indexFieldInfo.is_loading, false);
  assert.equal(b.indexFieldInfo.is_loading, false);
});
test('field failures preserve error notification state; canceled requests only release loading', async () => {
  const a = app();
  fieldsRequest = async () => {
    throw new Error('offline');
  };
  await mod.requestIndexSetFieldInfoAction(a);
  assert.match(a.apiErrorInfo[api.id].message, /offline/);
  assert.equal(a.indexFieldInfo.is_loading, false);
  delete a.apiErrorInfo[api.id];
  fieldsRequest = async () => {
    throw Object.assign(new Error('cancel'), { code: 'ERR_CANCELED' });
  };
  await mod.requestIndexSetFieldInfoAction(a);
  assert.equal(a.apiErrorInfo[api.id], undefined);
  assert.equal(a.indexFieldInfo.is_loading, false);
});
test('query cancellation, stale responses and request IDs remain scoped to the owning Pinia', async () => {
  const previousWindow = globalThis.window,
    previousDocument = globalThis.document;
  globalThis.window = { AJAX_URL_PREFIX: '/api/v1' };
  globalThis.document = { cookie: '' };
  try {
    jobs.length = 0;
    canceled.length = 0;
    const a = app(),
      b = app();
    const old = mod.requestIndexSetQueryAction(new Proxy(a, {}), {}),
      other = mod.requestIndexSetQueryAction(b, {}),
      latest = mod.requestIndexSetQueryAction(new Proxy(a, {}), {});
    assert.deepEqual(canceled, [jobs[0].id]);
    assert.equal(jobs[2].options.headers['X-Bk-Space-Uid'], 'space');
    assert.equal(jobs[2].options.writeMode, 'replace');
    jobs[0].resolve(response(['stale'], 999));
    assert.equal((await old).ignored, true);
    jobs[1].resolve(response(['other']));
    jobs[2].resolve(response(['latest']));
    await Promise.all([other, latest]);
    assert.deepEqual(a.indexSetQueryResult.row_keys, ['latest']);
    assert.deepEqual(b.indexSetQueryResult.row_keys, ['other']);
    assert.equal(a.indexSetQueryResult.is_loading, false);
    assert.equal(b.indexSetQueryResult.is_loading, false);
  } finally {
    globalThis.window = previousWindow;
    globalThis.document = previousDocument;
  }
});
test('canceled load-more restores cached rows and totals without presenting an empty error', async () => {
  const previousWindow = globalThis.window,
    previousDocument = globalThis.document;
  globalThis.window = { AJAX_URL_PREFIX: '/api/v1' };
  globalThis.document = { cookie: '' };
  try {
    jobs.length = 0;
    const a = app();
    const first = mod.requestIndexSetQueryAction(a, {});
    jobs[0].resolve(response(['first'], 2));
    await first;
    const more = mod.requestIndexSetQueryAction(a, { isPagination: true });
    assert.equal(jobs[1].options.writeMode, 'append');
    assert.equal(jobs[1].options.startSeq, 1);
    jobs[1].reject(Object.assign(new Error('cancel'), { code: 'ERR_CANCELED' }));
    assert.equal((await more).ignored, true);
    assert.deepEqual(a.indexSetQueryResult.row_keys, ['first']);
    assert.equal(a.indexSetQueryResult.total, 2);
    assert.equal(a.indexSetQueryResult.is_loading, false);
    assert.equal(a.indexSetQueryResult.is_pagination_loading, false);
    assert.equal(a.indexSetQueryResult.is_error, false);
  } finally {
    globalThis.window = previousWindow;
    globalThis.document = previousDocument;
  }
});
