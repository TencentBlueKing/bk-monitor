/**
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
 *
 * BlueKing PaaS is licensed under the MIT License.
 */

'use strict';

process.env.TS_NODE_COMPILER_OPTIONS = JSON.stringify({
  esModuleInterop: true,
  module: 'commonjs',
  moduleResolution: 'node',
  target: 'es2019',
});
process.env.TS_NODE_TRANSPILE_ONLY = '1';

require('ts-node/register/transpile-only');

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const Module = require('node:module');
const vue = require('vue');

const originalLoad = Module._load;
Module._load = function mockCoreDependencies(request, parent, isMain) {
  if (request === 'monitor-common/utils') {
    return { isObject: value => value !== null && typeof value === 'object' };
  }
  return originalLoad.call(this, request, parent, isMain);
};
const { createHostListRow, matchWhere, sortRows } = require('../src/trace/pages/host/utils/host-list-core.ts');
Module._load = originalLoad;

const createHost = ({ bkCloudId, bkHostId, ip }) => ({
  bk_cloud_id: bkCloudId,
  bk_host_id: bkHostId,
  bk_host_innerip: ip,
  module: [],
  status: 0,
});

const createWorkerHarness = () => {
  const source = fs.readFileSync(
    path.resolve(__dirname, '../src/trace/pages/host/workers/host-list.worker.raw.js'),
    'utf8'
  );
  const messages = [];
  const workerSelf = {
    postMessage: message => messages.push(message),
  };
  vm.runInNewContext(source, {
    Map,
    Number,
    Object,
    Set,
    String,
    self: workerSelf,
  });
  let requestId = 0;
  return {
    send(message) {
      messages.length = 0;
      requestId += 1;
      workerSelf.onmessage({ data: { ...message, requestId } });
      assert.equal(messages.length, 1);
      return messages[0];
    },
  };
};

const defaultComputeParams = {
  activeCategory: '',
  keyword: '',
  page: 1,
  pageSize: 50,
  selectedNode: null,
  sortInfo: '',
  stickyValue: {},
  where: [],
};

test('host row key prefers bk_host_id and falls back to ip plus cloud id', () => {
  const hostWithId = createHost({ bkCloudId: 0, bkHostId: 101, ip: '10.0.0.1' });
  const fallbackHost = createHost({ bkCloudId: 3, bkHostId: undefined, ip: '10.0.0.1' });

  assert.equal(createHostListRow(hostWithId).id, '101');
  assert.equal(createHostListRow(hostWithId).rowId, '101');
  assert.equal(createHostListRow(fallbackHost).id, '10.0.0.1|3');
  assert.equal(createHostListRow(fallbackHost).rowId, '10.0.0.1|3');
});

test('worker keeps same-ip hosts in different clouds independently selectable and copyable', () => {
  const worker = createWorkerHarness();
  worker.send({
    baseList: [
      createHost({ bkCloudId: 0, bkHostId: 101, ip: '10.0.0.1' }),
      createHost({ bkCloudId: 3, bkHostId: 202, ip: '10.0.0.1' }),
    ],
    type: 'INIT_BASE',
  });

  const filtered = worker.send({ params: defaultComputeParams, type: 'GET_FILTERED_ROW_KEYS' });
  assert.deepEqual(Array.from(filtered.rowKeys), ['101', '202']);

  const selected = worker.send({ rowKeys: filtered.rowKeys, type: 'GET_SELECTED_ROWS' });
  assert.deepEqual(
    Array.from(selected.rows, row => [row.bk_host_id, row.bk_cloud_id]),
    [
      [101, 0],
      [202, 3],
    ]
  );
});

test('worker clears stale metrics when a later metric response is empty', () => {
  const worker = createWorkerHarness();
  worker.send({
    baseList: [createHost({ bkCloudId: 0, bkHostId: 101, ip: '10.0.0.1' })],
    type: 'INIT_BASE',
  });
  worker.send({
    metricListMap: {
      101: { alarm_count: [], component: [], cpu_usage: 88 },
    },
    type: 'MERGE_METRICS',
  });

  const before = worker.send({ params: defaultComputeParams, type: 'COMPUTE' });
  assert.equal(before.pagedRows[0].cpu_usage, 88);

  worker.send({ metricListMap: {}, type: 'MERGE_METRICS' });
  const after = worker.send({ params: defaultComputeParams, type: 'COMPUTE' });
  assert.equal(after.pagedRows[0].cpu_usage, undefined);
  assert.equal(after.pagedRows[0].totalAlarmCount, 0);
});

test('numeric filters distinguish a real zero from a missing metric', () => {
  const missing = createHostListRow(createHost({ bkCloudId: 0, bkHostId: 101, ip: '10.0.0.1' }));
  const zero = createHostListRow(createHost({ bkCloudId: 0, bkHostId: 102, ip: '10.0.0.2' }), { cpu_usage: 0 });
  const where = [{ key: 'cpu_usage', method: 'eq', value: ['0'] }];

  assert.equal(matchWhere(missing, where), false);
  assert.equal(matchWhere(zero, where), true);
});

test('numeric sorting keeps missing metrics last while retaining a real zero', () => {
  const missing = createHostListRow(createHost({ bkCloudId: 0, bkHostId: 101, ip: '10.0.0.1' }));
  const positive = createHostListRow(createHost({ bkCloudId: 0, bkHostId: 103, ip: '10.0.0.3' }), { cpu_usage: 25 });
  const zero = createHostListRow(createHost({ bkCloudId: 0, bkHostId: 102, ip: '10.0.0.2' }), { cpu_usage: 0 });

  assert.deepEqual(
    sortRows([missing, positive, zero], 'cpu_usage').map(row => row.rowId),
    ['102', '103', '101']
  );
  assert.deepEqual(
    sortRows([missing, positive, zero], '-cpu_usage').map(row => row.rowId),
    ['103', '102', '101']
  );
});

test('worker applies the same missing-versus-zero numeric semantics', () => {
  const worker = createWorkerHarness();
  worker.send({
    baseList: [
      createHost({ bkCloudId: 0, bkHostId: 101, ip: '10.0.0.1' }),
      createHost({ bkCloudId: 0, bkHostId: 102, ip: '10.0.0.2' }),
      createHost({ bkCloudId: 0, bkHostId: 103, ip: '10.0.0.3' }),
    ],
    type: 'INIT_BASE',
  });
  worker.send({
    metricListMap: {
      102: { cpu_usage: 0 },
      103: { cpu_usage: 25 },
    },
    type: 'MERGE_METRICS',
  });

  const filtered = worker.send({
    params: {
      ...defaultComputeParams,
      where: [{ key: 'cpu_usage', method: 'eq', value: ['0'] }],
    },
    type: 'COMPUTE',
  });
  assert.deepEqual(
    Array.from(filtered.pagedRows, row => row.rowId),
    ['102']
  );

  const sorted = worker.send({
    params: { ...defaultComputeParams, sortInfo: 'cpu_usage' },
    type: 'COMPUTE',
  });
  assert.deepEqual(
    Array.from(sorted.pagedRows, row => row.rowId),
    ['102', '103', '101']
  );
});

const deferred = () => {
  let resolve;
  const promise = new Promise(resolvePromise => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
};

const flushPromises = () => new Promise(resolve => setImmediate(resolve));

const hostStore = {
  refreshImmediate: vue.shallowRef(0),
  refreshInterval: vue.shallowRef(-1),
  timeRange: vue.shallowRef([0, 1]),
  timezone: vue.shallowRef('Asia/Shanghai'),
};
let getHostInfo;
let getHostMetricInfo;
let hostListWorker;

Module._load = function mockHostListDependencies(request, parent, isMain) {
  const isHostList = parent?.filename.endsWith('/trace/pages/host/composables/use-host-list.ts');
  if (request === 'vue') {
    return {
      ...vue,
      onBeforeUnmount: () => {},
      onMounted: () => {},
    };
  }
  if (request === '@vueuse/core') {
    return { useDebounceFn: callback => callback };
  }
  if (request === 'bkui-vue') {
    return { Message: () => {} };
  }
  if (request === 'monitor-common/utils') {
    return {
      commonPageSizeGet: () => 50,
      commonPageSizeSet: () => {},
    };
  }
  if (request === 'monitor-common/utils/utils') {
    return { copyText: () => {} };
  }
  if (request === 'pinia') {
    return { storeToRefs: store => store };
  }
  if (isHostList && request === '../../../components/across-page-selection/across-page-selection') {
    return {
      SelectType: {
        ALL_SELECTED: 'all',
        HALF_ALL_SELECTED: 'half-all',
        HALF_SELECTED: 'half',
        SELECTED: 'selected',
        UN_SELECTED: 'unselected',
      },
    };
  }
  if (isHostList && request === '../../../components/retrieval-filter/typing') {
    return { EMode: { ui: 'ui' } };
  }
  if (isHostList && request === '../../../components/time-range/utils') {
    return { handleTransformToTimestamp: range => range };
  }
  if (isHostList && request === '../../../hooks/useUserConfig') {
    return () => ({
      handleGetUserConfig: async () => ({}),
      handleSetUserConfig: async () => {},
    });
  }
  if (isHostList && request === '../../../store/modules/host') {
    return { useHostStore: () => hostStore };
  }
  if (isHostList && request === '../constants/enum') {
    return { HostSelectAllModeEnum: { ACROSS: 'across', NONE: 'none', PAGE: 'page' } };
  }
  if (isHostList && request === '../constants/host-list') {
    return {
      HOST_FILTER_FIELDS: [],
      HOST_LIST_COLUMNS: [{ checked: true, id: 'bk_host_innerip' }],
      HOST_LIST_DEFAULT_PAGE_SIZE: 50,
    };
  }
  if (isHostList && request === '../services/host-service') {
    return {
      getHostInfoList: (...args) => getHostInfo(...args),
      getHostMetricInfoList: (...args) => getHostMetricInfo(...args),
    };
  }
  if (isHostList && request === './use-host-list-worker') {
    return { useHostListWorker: () => hostListWorker };
  }
  if (isHostList && request === './use-host-url-params') {
    return { useHostUrlParams: () => ({ setUrlParams: () => {} }) };
  }
  return originalLoad.call(this, request, parent, isMain);
};
const { useHostList } = require('../src/trace/pages/host/composables/use-host-list.ts');
Module._load = originalLoad;

const createControllerWorker = () => {
  const calls = {
    computeNow: [],
    initBaseData: [],
    mergeMetrics: [],
  };
  let getFilteredRowKeys = async () => ({ rowKeys: [] });
  return {
    calls,
    computeNow: params => calls.computeNow.push(params),
    getFilterOptions: async () => ({ result: { count: 0, list: [] } }),
    getFilteredRowKeys: params => getFilteredRowKeys(params),
    getSelectedIps: async () => ({ ips: [] }),
    getSelectedRows: async () => ({ rows: [] }),
    getFilterOptionsMap: async () => ({ filterOptionsMap: {} }),
    initBaseData: async baseList => {
      calls.initBaseData.push(baseList);
      return { rawRowCount: baseList.length };
    },
    mergeMetrics: async metricListMap => {
      calls.mergeMetrics.push(metricListMap);
      return { filterOptionsMap: {} };
    },
    scheduleCompute: () => {},
    setComputeHandler: () => {},
    setFilteredRowKeysHandler: callback => {
      getFilteredRowKeys = callback;
    },
  };
};

const createHostListController = () => {
  const scope = vue.effectScope();
  let context;
  scope.run(() => {
    context = useHostList({
      activeCategory: vue.shallowRef(''),
      filterExpanded: vue.shallowRef(false),
      keyword: vue.shallowRef(''),
      selectedNode: vue.shallowRef(null),
      where: vue.shallowRef([]),
    });
  });
  return { context, scope };
};

test('a slower old base-list request cannot replace a newer refresh', async () => {
  const first = deferred();
  const second = deferred();
  let requestCount = 0;
  getHostInfo = () => (++requestCount === 1 ? first.promise : second.promise);
  getHostMetricInfo = async () => ({});
  hostListWorker = createControllerWorker();
  const { context, scope } = createHostListController();

  const firstLoad = context.loadData();
  const secondLoad = context.loadData();
  const newBaseList = [createHost({ bkCloudId: 0, bkHostId: 202, ip: '10.0.0.2' })];
  second.resolve(newBaseList);
  await secondLoad;
  first.resolve([createHost({ bkCloudId: 0, bkHostId: 101, ip: '10.0.0.1' })]);
  await firstLoad;

  assert.equal(hostListWorker.calls.initBaseData.length, 1);
  assert.deepEqual(hostListWorker.calls.initBaseData[0], newBaseList);
  scope.stop();
});

test('a slower old historical metric request cannot replace the latest range', async () => {
  getHostInfo = async () => [createHost({ bkCloudId: 0, bkHostId: 101, ip: '10.0.0.1' })];
  getHostMetricInfo = async () => ({ 101: { cpu_usage: 1 } });
  hostListWorker = createControllerWorker();
  const { context, scope } = createHostListController();
  await context.loadData();

  const metricRequests = [];
  getHostMetricInfo = params => {
    const request = deferred();
    metricRequests.push({ params, request });
    return request.promise;
  };
  const computeCountBeforeRangeChange = hostListWorker.calls.computeNow.length;
  hostStore.timeRange.value = [10, 20];
  await vue.nextTick();
  hostStore.timeRange.value = [30, 40];
  await vue.nextTick();

  metricRequests[1].request.resolve({ 101: { cpu_usage: 22 } });
  await flushPromises();
  metricRequests[0].request.resolve({ 101: { cpu_usage: 11 } });
  await flushPromises();

  assert.deepEqual(hostListWorker.calls.mergeMetrics.at(-1), { 101: { cpu_usage: 22 } });
  assert.equal(hostListWorker.calls.computeNow.length, computeCountBeforeRangeChange + 1);
  scope.stop();
});

test('a slower old quick-filter selection response cannot overwrite the latest across-page selection', async () => {
  getHostInfo = async () => [createHost({ bkCloudId: 0, bkHostId: 101, ip: '10.0.0.1' })];
  getHostMetricInfo = async () => ({});
  hostListWorker = createControllerWorker();
  hostListWorker.setFilteredRowKeysHandler(async () => ({ rowKeys: ['initial'] }));
  const { context, scope } = createHostListController();
  await context.loadData();
  await context.handleHeaderSelect('all');

  const filterRequests = [];
  hostListWorker.setFilteredRowKeysHandler(() => {
    const request = deferred();
    filterRequests.push(request);
    return request.promise;
  });
  context.activeCategory.value = 'cpu';
  await vue.nextTick();
  context.activeCategory.value = 'mem';
  await vue.nextTick();

  filterRequests[1].resolve({ rowKeys: ['latest'] });
  await flushPromises();
  filterRequests[0].resolve({ rowKeys: ['old'] });
  await flushPromises();

  assert.deepEqual([...context.selectedRowKeys.value], ['latest']);
  scope.stop();
});

test('a pending across-page selection cannot restore rows cleared by a data refresh', async () => {
  getHostInfo = async () => [createHost({ bkCloudId: 0, bkHostId: 101, ip: '10.0.0.1' })];
  getHostMetricInfo = async () => ({});
  hostListWorker = createControllerWorker();
  const selectionRequest = deferred();
  hostListWorker.setFilteredRowKeysHandler(() => selectionRequest.promise);
  const { context, scope } = createHostListController();
  await context.loadData();

  const selection = context.handleHeaderSelect('all');
  await context.loadData();
  selectionRequest.resolve({ rowKeys: ['old'] });
  await selection;

  assert.deepEqual([...context.selectedRowKeys.value], []);
  scope.stop();
});
