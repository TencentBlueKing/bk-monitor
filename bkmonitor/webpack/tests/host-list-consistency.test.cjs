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

test('host row keeps failed process and alarm sections unknown while preserving successful empty results', () => {
  const host = createHost({ bkCloudId: 0, bkHostId: 101, ip: '10.0.0.1' });
  const failed = createHostListRow(host, { alarm_count: null, component: null });
  const empty = createHostListRow(host, { alarm_count: [], component: [] });

  assert.equal(failed.alarm_count, null);
  assert.equal(failed.component, null);
  assert.equal(failed.totalAlarmCount, null);
  assert.deepEqual(empty.alarm_count, []);
  assert.deepEqual(empty.component, []);
  assert.equal(empty.totalAlarmCount, 0);
});

test('raw worker keeps failed process and alarm sections unknown', () => {
  const worker = createWorkerHarness();
  worker.send({
    baseList: [createHost({ bkCloudId: 0, bkHostId: 101, ip: '10.0.0.1' })],
    type: 'INIT_BASE',
  });
  worker.send({
    metricListMap: { 101: { alarm_count: null, component: null } },
    type: 'MERGE_METRICS',
  });

  const computed = worker.send({ params: defaultComputeParams, type: 'COMPUTE' });

  assert.equal(computed.pagedRows[0].alarm_count, null);
  assert.equal(computed.pagedRows[0].component, null);
  assert.equal(computed.pagedRows[0].totalAlarmCount, null);
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

test('worker clears stale metrics and leaves absent sections unknown when a later response is empty', () => {
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
  assert.equal(after.pagedRows[0].totalAlarmCount, null);
});

test('host row merges same-name process badges and preserves abnormal status for tooltip', () => {
  const row = createHostListRow(createHost({ bkCloudId: 0, bkHostId: 101, ip: '192.0.2.1' }), {
    component: [
      { display_name: 'redis', id: 'redis-primary', status: 0 },
      { display_name: 'redis', id: 'redis-replica', status: 1 },
      { display_name: 'nginx', id: 'nginx', status: 0 },
    ],
  });

  assert.deepEqual(
    row.component.map(item => ({ display_name: item.display_name, status: item.status })),
    [
      { display_name: 'redis', status: 1 },
      { display_name: 'nginx', status: 0 },
    ]
  );
  assert.equal(row.processNames, 'redis,nginx');
  assert.equal(matchWhere(row, [{ key: 'display_name', method: 'eq', value: ['redis'] }]), true);

  const tableSource = fs.readFileSync(
    path.resolve(__dirname, '../src/trace/pages/host/components/host-list/host-list-table.tsx'),
    'utf8'
  );
  assert.match(tableSource, /item\.status === -1[\s\S]*`host-table-process__tag--\$\{item\.status\}`/);
  assert.match(tableSource, /handleTipsMouseenter\(e, item, 'Thread'\)/);
});

test('worker applies the same same-name process badge aggregation', () => {
  const worker = createWorkerHarness();
  worker.send({
    baseList: [createHost({ bkCloudId: 0, bkHostId: 101, ip: '192.0.2.1' })],
    type: 'INIT_BASE',
  });
  worker.send({
    metricListMap: {
      101: {
        component: [
          { display_name: 'redis', id: 'redis-primary', status: 0 },
          { display_name: 'redis', id: 'redis-replica', status: 1 },
        ],
      },
    },
    type: 'MERGE_METRICS',
  });

  const result = worker.send({ params: defaultComputeParams, type: 'COMPUTE' });
  assert.deepEqual(
    Array.from(result.pagedRows[0].component, item => ({ display_name: item.display_name, status: item.status })),
    [{ display_name: 'redis', status: 1 }]
  );
  assert.equal(result.pagedRows[0].processNames, 'redis');
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
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
};

const flushPromises = () => new Promise(resolve => setImmediate(resolve));

const hostStore = {
  refreshGeneration: vue.shallowRef(0),
  refreshImmediate: vue.shallowRef(0),
  refreshInterval: vue.shallowRef(-1),
  timeRange: vue.shallowRef([0, 1]),
  timezone: vue.shallowRef('Asia/Shanghai'),
};
let getHostInfo;
let getHostMetricInfo;
let hostListWorker;
let mountedCallbacks = [];

Module._load = function mockHostListDependencies(request, parent, isMain) {
  const isHostList = parent?.filename.endsWith('/trace/pages/host/composables/use-host-list.ts');
  if (request === 'vue') {
    return {
      ...vue,
      onBeforeUnmount: () => {},
      onMounted: callback => mountedCallbacks.push(callback),
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
  if (request === 'vue-router') {
    return { useRoute: () => ({ query: {} }) };
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
  mountedCallbacks = [];
  const scope = vue.effectScope();
  let context;
  scope.run(() => {
    context = useHostList({
      activeCategory: vue.shallowRef(''),
      filterExpanded: vue.shallowRef(false),
      keyword: vue.shallowRef(''),
      readonly: false,
      selectedNode: vue.shallowRef(null),
      where: vue.shallowRef([]),
    });
  });
  return { context, mountedCallbacks: [...mountedCallbacks], scope };
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

test('full host list metric request omits bk_host_ids', async () => {
  getHostInfo = async () => [createHost({ bkCloudId: 0, bkHostId: 101, ip: '10.0.0.1' })];
  let metricParams;
  getHostMetricInfo = async params => {
    metricParams = params;
    return {};
  };
  hostListWorker = createControllerWorker();
  const { context, scope } = createHostListController();
  await context.loadData();

  assert.equal(metricParams.bk_host_ids, undefined);
  assert.ok('start_time' in metricParams);
  assert.ok('end_time' in metricParams);
  scope.stop();
});

test('the host list refreshes from the shared refresh generation', async () => {
  hostStore.refreshGeneration.value = 0;
  hostStore.refreshInterval.value = -1;
  let requestCount = 0;
  getHostInfo = async () => {
    requestCount += 1;
    return [createHost({ bkCloudId: 0, bkHostId: 101, ip: '10.0.0.1' })];
  };
  getHostMetricInfo = async () => ({});
  hostListWorker = createControllerWorker();
  const { context, scope } = createHostListController();
  await context.loadData();

  hostStore.refreshGeneration.value += 1;
  await vue.nextTick();
  await flushPromises();

  assert.equal(requestCount, 2);
  scope.stop();
});

test('mounting with auto-refresh enabled loads once without creating a private timer', async () => {
  hostStore.refreshInterval.value = 30_000;
  let requestCount = 0;
  getHostInfo = async () => {
    requestCount += 1;
    return [];
  };
  getHostMetricInfo = async () => ({});
  hostListWorker = createControllerWorker();
  const originalSetInterval = global.setInterval;
  let intervalCount = 0;
  global.setInterval = () => {
    intervalCount += 1;
    return 1;
  };

  try {
    const { mountedCallbacks: callbacks, scope } = createHostListController();
    assert.equal(callbacks.length, 1);
    callbacks[0]();
    await flushPromises();
    assert.equal(requestCount, 1);
    assert.equal(intervalCount, 0);
    scope.stop();
  } finally {
    hostStore.refreshInterval.value = -1;
    await vue.nextTick();
    global.setInterval = originalSetInterval;
  }
});
test('a base-list failure shows a retryable error while a real empty response stays empty', async () => {
  const baseError = new Error('base list failed');
  let metricRequestCount = 0;
  getHostInfo = async () => {
    throw baseError;
  };
  getHostMetricInfo = async () => {
    metricRequestCount += 1;
    return {};
  };
  hostListWorker = createControllerWorker();
  const { context, scope } = createHostListController();

  await context.loadData();

  assert.equal(context.loadError.value, true);
  assert.equal(context.loading.value, false);
  assert.equal(context.rawRowCount.value, 0);
  assert.equal(context.metricLoadError.value, false);
  assert.equal(metricRequestCount, 0);

  getHostInfo = async () => [];
  await context.loadData();

  assert.equal(context.loadError.value, false);
  assert.equal(context.rawRowCount.value, 0);
  assert.equal(metricRequestCount, 0);
  scope.stop();
});

test('a metric failure keeps base rows and retrying metrics does not reload the base list', async () => {
  let baseRequestCount = 0;
  let metricRequestCount = 0;
  const base = createHost({ bkCloudId: 0, bkHostId: 101, ip: '10.0.0.1' });
  getHostInfo = async () => {
    baseRequestCount += 1;
    return [base];
  };
  getHostMetricInfo = async () => {
    metricRequestCount += 1;
    throw new Error('metric list failed');
  };
  hostListWorker = createControllerWorker();
  const { context, scope } = createHostListController();

  await context.loadData();

  assert.equal(context.loadError.value, false);
  assert.equal(context.metricLoadError.value, true);
  assert.equal(context.rawRowCount.value, 1);
  assert.deepEqual(hostListWorker.calls.initBaseData, [[base]]);
  assert.deepEqual(hostListWorker.calls.mergeMetrics, []);

  getHostMetricInfo = async () => {
    metricRequestCount += 1;
    return { 101: { cpu_usage: 25 } };
  };
  await context.loadMetricData();

  assert.equal(context.metricLoadError.value, false);
  assert.equal(baseRequestCount, 1);
  assert.equal(metricRequestCount, 2);
  assert.deepEqual(hostListWorker.calls.mergeMetrics, [{ 101: { cpu_usage: 25 } }]);
  scope.stop();
});

test('an obsolete metric failure cannot replace the latest successful metric state', async () => {
  getHostInfo = async () => [createHost({ bkCloudId: 0, bkHostId: 101, ip: '10.0.0.1' })];
  getHostMetricInfo = async () => ({});
  hostListWorker = createControllerWorker();
  const { context, scope } = createHostListController();
  await context.loadData();

  const first = deferred();
  const second = deferred();
  let requestCount = 0;
  getHostMetricInfo = () => (++requestCount === 1 ? first.promise : second.promise);
  const oldRequest = context.loadMetricData();
  const latestRequest = context.loadMetricData();
  second.resolve({ 101: { cpu_usage: 50 } });
  await latestRequest;
  first.reject(new Error('obsolete metric failure'));
  await oldRequest;

  assert.equal(context.metricLoadError.value, false);
  assert.deepEqual(hostListWorker.calls.mergeMetrics.at(-1), { 101: { cpu_usage: 50 } });
  scope.stop();
});

test('a base refresh failure invalidates a metric request started from the previous base list', async () => {
  getHostInfo = async () => [createHost({ bkCloudId: 0, bkHostId: 101, ip: '10.0.0.1' })];
  getHostMetricInfo = async () => ({});
  hostListWorker = createControllerWorker();
  const { context, scope } = createHostListController();
  await context.loadData();

  const baseRefresh = deferred();
  const staleMetricRefresh = deferred();
  getHostInfo = () => baseRefresh.promise;
  getHostMetricInfo = () => staleMetricRefresh.promise;
  const metricMergeCount = hostListWorker.calls.mergeMetrics.length;

  const baseRequest = context.loadData();
  const metricRequest = context.loadMetricData();
  baseRefresh.reject(new Error('base refresh failed'));
  await baseRequest;
  staleMetricRefresh.resolve({ 101: { cpu_usage: 75 } });
  await metricRequest;

  assert.equal(context.loadError.value, true);
  assert.equal(hostListWorker.calls.mergeMetrics.length, metricMergeCount);
  scope.stop();
});

test('host list views expose separate retry paths for base and metric failures', () => {
  const hostListSource = fs.readFileSync(
    path.resolve(__dirname, '../src/trace/pages/host/components/host-list/host-list.tsx'),
    'utf8'
  );
  const tableSource = fs.readFileSync(
    path.resolve(__dirname, '../src/trace/pages/host/components/host-list/host-list-table.tsx'),
    'utf8'
  );

  assert.match(hostListSource, /<EmptyStatus[\s\S]*type='500'[\s\S]*onOperation=\{ctx\.loadData\}/);
  assert.match(hostListSource, /metricLoadError=\{ctx\.metricLoadError\.value\}/);
  assert.match(hostListSource, /onRetryMetric=\{ctx\.loadMetricData\}/);
  assert.match(tableSource, /metricLoadError:[\s\S]*type: Boolean/);
  assert.match(tableSource, /retryMetric:/);
  assert.match(tableSource, /指标数据加载失败，当前仅展示主机基础信息/);
  assert.match(tableSource, /HOST_METRIC_DATA_COLUMN_IDS\.has\(config\.id\)/);
});

test('metric failure only replaces columns supplied by the metric response', () => {
  const tableSource = fs.readFileSync(
    path.resolve(__dirname, '../src/trace/pages/host/components/host-list/host-list-table.tsx'),
    'utf8'
  );
  const metricColumnIdsSource = tableSource.match(/const HOST_METRIC_DATA_COLUMN_IDS = new Set\(\[([\s\S]*?)\]\);/);

  assert.ok(metricColumnIdsSource);
  const metricColumnIds = [...metricColumnIdsSource[1].matchAll(/'([^']+)'/g)].map(match => match[1]);
  assert.deepEqual(metricColumnIds, [
    'status',
    'alarm_count',
    'cpu_usage',
    'mem_usage',
    'disk_in_use',
    'io_util',
    'psc_mem_usage',
    'cpu_load',
    'display_name',
  ]);
});
