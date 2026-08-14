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

global.window = global.window || {};
global.window.enable_host_metric_progressive = false;
global.window.cc_biz_id = 7;

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
let defaultProgressiveMetricService;
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
      HOST_PROGRESSIVE_METRIC_FIELD_IDS: new Set(['cpu_usage', 'display_name', 'status']),
    };
  }
  if (isHostList && request === '../services/host-service') {
    return {
      getHostInfoList: (...args) => getHostInfo(...args),
      getHostMetricInfoList: (...args) => getHostMetricInfo(...args),
      hostMetricSnapshotService: {
        create: (...args) => defaultProgressiveMetricService.create(...args),
        hashHostIds: (...args) => defaultProgressiveMetricService.hashHostIds(...args),
        poll: (...args) => defaultProgressiveMetricService.poll(...args),
      },
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
    initBaseEpochs: [],
    mergeMetrics: [],
    patchMetrics: [],
    replaceMetrics: [],
    resetMetrics: [],
  };
  let getFilteredRowKeys = async () => ({ rowKeys: [] });
  let computeHandler = () => {};
  return {
    calls,
    computeNow: params => calls.computeNow.push(params),
    getFilterOptions: async () => ({ result: { count: 0, list: [] } }),
    getFilteredRowKeys: params => getFilteredRowKeys(params),
    getSelectedIps: async () => ({ ips: [] }),
    getSelectedRows: async () => ({ rows: [] }),
    getFilterOptionsMap: async () => ({ filterOptionsMap: {} }),
    initBaseData: async (baseList, epoch) => {
      calls.initBaseData.push(baseList);
      calls.initBaseEpochs.push(epoch);
      return { applied: true, epoch, rawRowCount: baseList.length };
    },
    mergeMetrics: async metricListMap => {
      calls.mergeMetrics.push(metricListMap);
      return { filterOptionsMap: {} };
    },
    patchMetrics: async (epoch, hostIds, metricListMap) => {
      calls.patchMetrics.push({ epoch, hostIds, metricListMap });
      return { applied: true, epoch };
    },
    replaceMetrics: async (epoch, metricListMap) => {
      calls.replaceMetrics.push({ epoch, metricListMap });
      return { applied: true, epoch, filterOptionsMap: { display_name: [{ id: 'redis', name: 'redis' }] } };
    },
    resetMetrics: async epoch => {
      calls.resetMetrics.push(epoch);
      return { applied: true, epoch };
    },
    scheduleCompute: () => {},
    setComputeHandler: callback => {
      computeHandler = callback;
    },
    setFilteredRowKeysHandler: callback => {
      getFilteredRowKeys = callback;
    },
    emitComputeDone: pagedRows =>
      computeHandler({ categoryStats: { alarm: 0, cpu: 0, disk: 0, mem: 0 }, pagedRows, total: pagedRows.length }),
  };
};

const createHostListController = ({ progressive = false, progressiveMetricService } = {}) => {
  mountedCallbacks = [];
  global.window.enable_host_metric_progressive = progressive;
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
      progressiveMetricService,
    });
  });
  return { context, mountedCallbacks: [...mountedCallbacks], scope };
};

const createSnapshotResult = overrides => ({
  canonicalEndTime: 900,
  canonicalStartTime: 800,
  expired: false,
  failedSections: [],
  hostCount: 0,
  hostIdsHash: '',
  retryAfterMs: 0,
  revision: 0,
  sections: [],
  snapshotId: 'snapshot-1',
  status: 'RUNNING',
  ...overrides,
});

test('progressive mode starts the snapshot with the base list and requests only the visible page while running', async () => {
  const baseRequest = deferred();
  const snapshotCreateRequest = deferred();
  const hosts = [
    createHost({ bkCloudId: 0, bkHostId: 101, ip: '10.0.0.1' }),
    createHost({ bkCloudId: 0, bkHostId: 102, ip: '10.0.0.2' }),
  ];
  const metricRequests = [];
  const pollRequests = [];
  getHostInfo = () => baseRequest.promise;
  getHostMetricInfo = params => {
    metricRequests.push(params);
    return Promise.resolve(Object.fromEntries(params.bk_host_ids.map(id => [id, { cpu_usage: 25 }])));
  };
  hostListWorker = createControllerWorker();
  const progressiveMetricService = {
    create: () => snapshotCreateRequest.promise,
    hashHostIds: async hostIds => hostIds.map(String).sort().join(','),
    poll: params => {
      pollRequests.push(params);
      return new Promise(() => {});
    },
  };
  const { context, scope } = createHostListController({ progressive: true, progressiveMetricService });

  const loading = context.loadData();
  assert.equal(context.metricProgressiveState.value, 'RUNNING');
  baseRequest.resolve(hosts);
  await loading;
  hostListWorker.emitComputeDone([hosts[0]]);
  await flushPromises();

  assert.equal(metricRequests.length, 1);
  assert.equal(metricRequests[0].start_time, 0);
  assert.equal(metricRequests[0].end_time, 1);
  snapshotCreateRequest.resolve(
    createSnapshotResult({ canonicalEndTime: 190, canonicalStartTime: 90, snapshotId: 'snapshot-1' })
  );
  await flushPromises();
  hostListWorker.emitComputeDone([hosts[1]]);
  await flushPromises();

  assert.deepEqual(metricRequests[0].bk_host_ids, [101]);
  assert.equal(metricRequests[0].query_mode, 'page');
  assert.deepEqual(metricRequests[1].bk_host_ids, [102]);
  assert.equal(metricRequests[1].start_time, 90);
  assert.equal(metricRequests[1].end_time, 190);
  assert.deepEqual(hostListWorker.calls.patchMetrics, [
    { epoch: 1, hostIds: [101], metricListMap: { 101: { cpu_usage: 25 } } },
    { epoch: 1, hostIds: [102], metricListMap: { 102: { cpu_usage: 25 } } },
  ]);

  context.keyword.value = '10.0.0.1';
  await context.handleIpMark({ rowId: '101' });
  assert.equal(hostListWorker.calls.computeNow.at(-1).keyword, '10.0.0.1');

  assert.deepEqual(pollRequests[0], {
    bkBizId: 7,
    endTime: 190,
    sinceRevision: 0,
    snapshotId: 'snapshot-1',
    startTime: 90,
  });
  scope.stop();
});

test('an obsolete page metric response cannot patch a newer dataset epoch', async () => {
  const oldPageRequest = deferred();
  let baseRequestCount = 0;
  getHostInfo = async () => [
    createHost({ bkCloudId: 0, bkHostId: ++baseRequestCount, ip: `10.0.0.${baseRequestCount}` }),
  ];
  getHostMetricInfo = () => oldPageRequest.promise;
  hostListWorker = createControllerWorker();
  const neverReadyService = {
    create: async () => createSnapshotResult({ snapshotId: 'snapshot-running' }),
    hashHostIds: async hostIds => hostIds.map(String).sort().join(','),
    poll: () => new Promise(() => {}),
  };
  const { context, scope } = createHostListController({
    progressive: true,
    progressiveMetricService: neverReadyService,
  });

  await context.loadData();
  hostListWorker.emitComputeDone([createHost({ bkCloudId: 0, bkHostId: 1, ip: '10.0.0.1' })]);
  await flushPromises();
  await context.loadData();
  oldPageRequest.resolve({ 1: { cpu_usage: 99 } });
  await flushPromises();

  assert.deepEqual(hostListWorker.calls.patchMetrics, []);
  assert.deepEqual(hostListWorker.calls.initBaseEpochs, [1, 2]);
  scope.stop();
});

test('a failed old-page request releases shared pending hosts and refills the current page once', async () => {
  const hosts = [
    createHost({ bkCloudId: 0, bkHostId: 1, ip: '10.0.0.1' }),
    createHost({ bkCloudId: 0, bkHostId: 2, ip: '10.0.0.2' }),
    createHost({ bkCloudId: 0, bkHostId: 3, ip: '10.0.0.3' }),
  ];
  const metricRequests = [];
  getHostInfo = async () => hosts;
  getHostMetricInfo = params => {
    const request = deferred();
    metricRequests.push({ params, request });
    return request.promise;
  };
  hostListWorker = createControllerWorker();
  const progressiveMetricService = {
    create: () => new Promise(() => {}),
    hashHostIds: async () => '',
    poll: () => new Promise(() => {}),
  };
  const { context, scope } = createHostListController({ progressive: true, progressiveMetricService });

  await context.loadData();
  hostListWorker.emitComputeDone([hosts[0], hosts[1]]);
  await flushPromises();
  hostListWorker.emitComputeDone([hosts[1], hosts[2]]);
  await flushPromises();

  assert.deepEqual(
    metricRequests.map(item => item.params.bk_host_ids),
    [[1, 2], [3]]
  );
  metricRequests[1].request.resolve({ 3: { cpu_usage: 30 } });
  await flushPromises();
  hostListWorker.emitComputeDone([hosts[1], hosts[2]]);
  await flushPromises();
  metricRequests[0].request.reject(new Error('old page failed'));
  await flushPromises();

  assert.deepEqual(
    metricRequests.map(item => item.params.bk_host_ids),
    [[1, 2], [3], [2]]
  );
  assert.equal(context.metricLoadError.value, false);
  scope.stop();
  metricRequests[2].request.resolve({ 2: { cpu_usage: 20 } });
});

test('a failed current-page request exposes the error without immediate retry spinning', async () => {
  const host = createHost({ bkCloudId: 0, bkHostId: 1, ip: '10.0.0.1' });
  let metricRequestCount = 0;
  getHostInfo = async () => [host];
  getHostMetricInfo = async () => {
    metricRequestCount += 1;
    throw new Error('current page failed');
  };
  hostListWorker = createControllerWorker();
  const progressiveMetricService = {
    create: () => new Promise(() => {}),
    hashHostIds: async () => '',
    poll: () => new Promise(() => {}),
  };
  const { context, scope } = createHostListController({ progressive: true, progressiveMetricService });

  await context.loadData();
  hostListWorker.emitComputeDone([host]);
  await flushPromises();

  assert.equal(metricRequestCount, 1);
  assert.equal(context.metricLoadError.value, true);
  scope.stop();
});

test('snapshot sections remain isolated until all four sections and the host hash are ready', async () => {
  const hosts = [createHost({ bkCloudId: 0, bkHostId: 101, ip: '10.0.0.1' })];
  getHostInfo = async () => hosts;
  getHostMetricInfo = async () => ({});
  hostListWorker = createControllerWorker();
  const pollResponses = [
    {
      hostCount: 1,
      hostIdsHash: '101',
      revision: 1,
      sections: [{ data: { 101: { status: 0 } }, name: 'agent_status' }],
      status: 'RUNNING',
      retryAfterMs: 0,
    },
    {
      hostCount: 1,
      hostIdsHash: '101',
      revision: 2,
      sections: [
        { data: { 101: { cpu_usage: 88 } }, name: 'performance_data' },
        { data: { 101: { component: [] } }, name: 'process_status' },
        { data: { 101: { alarm_count: [] } }, name: 'alarm_count' },
      ],
      status: 'READY',
    },
  ];
  const progressiveMetricService = {
    create: async () => createSnapshotResult({ snapshotId: 'snapshot-1' }),
    hashHostIds: async hostIds => hostIds.map(String).sort().join(','),
    poll: async () => createSnapshotResult(pollResponses.shift()),
  };
  const { context, scope } = createHostListController({ progressive: true, progressiveMetricService });

  await context.loadData();
  await flushPromises();
  assert.deepEqual(hostListWorker.calls.replaceMetrics, [
    {
      epoch: 1,
      metricListMap: { 101: { alarm_count: [], component: [], cpu_usage: 88, status: 0 } },
    },
  ]);
  assert.equal(context.metricProgressiveState.value, 'READY');
  assert.deepEqual(context.filterOptionsMap.value, { display_name: [{ id: 'redis', name: 'redis' }] });
  scope.stop();
});

test('a reused ready snapshot with a mismatched host set realigns the base list once without spinning', async () => {
  let hostInfoCount = 0;
  getHostInfo = async () => {
    hostInfoCount += 1;
    return [createHost({ bkCloudId: 0, bkHostId: 101, ip: '10.0.0.1' })];
  };
  getHostMetricInfo = async () => ({});
  hostListWorker = createControllerWorker();
  let createCount = 0;
  let pollCount = 0;
  const progressiveMetricService = {
    create: async () => {
      createCount += 1;
      if (createCount > 2) {
        return new Promise(() => {});
      }
      return createSnapshotResult({ snapshotId: 'snapshot-reused' });
    },
    hashHostIds: async hostIds => hostIds.map(String).sort().join(','),
    poll: async () => {
      pollCount += 1;
      return createSnapshotResult({
        hostCount: 2,
        hostIdsHash: '101,999',
        revision: 1,
        retryAfterMs: 0,
        sections: [
          { data: {}, name: 'agent_status' },
          { data: {}, name: 'performance_data' },
          { data: {}, name: 'process_status' },
          { data: {}, name: 'alarm_count' },
        ],
        status: 'READY',
      });
    },
  };
  const { context, scope } = createHostListController({ progressive: true, progressiveMetricService });

  await context.loadData();
  await flushPromises();

  assert.equal(hostInfoCount, 2);
  assert.equal(createCount, 2);
  assert.equal(pollCount, 2);
  assert.deepEqual(hostListWorker.calls.replaceMetrics, []);
  assert.equal(context.metricProgressiveState.value, 'FAILED');

  context.retryMetricSnapshot();
  await flushPromises();
  assert.equal(hostInfoCount, 3);
  assert.equal(createCount, 3);
  assert.equal(context.metricProgressiveState.value, 'RUNNING');
  scope.stop();
});

test('a reused READY manifest ignores create data and polls from revision zero before committing sections', async () => {
  const host = createHost({ bkCloudId: 0, bkHostId: 101, ip: '10.0.0.1' });
  const pollRequests = [];
  getHostInfo = async () => [host];
  getHostMetricInfo = async () => ({});
  hostListWorker = createControllerWorker();
  const progressiveMetricService = {
    create: async () =>
      createSnapshotResult({
        hostCount: 1,
        hostIdsHash: '101',
        revision: 9,
        sections: [
          { data: { 101: { cpu_usage: 1 } }, name: 'performance_data' },
          { data: { 101: { status: 0 } }, name: 'agent_status' },
          { data: { 101: { component: [] } }, name: 'process_status' },
          { data: { 101: { alarm_count: [] } }, name: 'alarm_count' },
        ],
        status: 'READY',
      }),
    hashHostIds: async () => '101',
    poll: async params => {
      pollRequests.push(params);
      return createSnapshotResult({
        hostCount: 1,
        hostIdsHash: '101',
        revision: 9,
        sections: [
          { data: { 101: { status: 0 } }, name: 'agent_status' },
          { data: { 101: { cpu_usage: 88 } }, name: 'performance_data' },
          { data: { 101: { component: [] } }, name: 'process_status' },
          { data: { 101: { alarm_count: [] } }, name: 'alarm_count' },
        ],
        status: 'READY',
      });
    },
  };
  const { context, scope } = createHostListController({ progressive: true, progressiveMetricService });

  await context.loadData();
  await flushPromises();

  assert.equal(pollRequests.length, 1);
  assert.equal(pollRequests[0].sinceRevision, 0);
  assert.equal(context.metricProgressiveState.value, 'READY');
  assert.equal(context.metricLoading.value, false);
  assert.equal(hostListWorker.calls.replaceMetrics.length, 1);
  scope.stop();
});

test('a page response arriving after snapshot replacement cannot patch READY metrics', async () => {
  const snapshotCreate = deferred();
  const pageMetric = deferred();
  const host = createHost({ bkCloudId: 0, bkHostId: 101, ip: '10.0.0.1' });
  getHostInfo = async () => [host];
  getHostMetricInfo = () => pageMetric.promise;
  hostListWorker = createControllerWorker();
  const progressiveMetricService = {
    create: () => snapshotCreate.promise,
    hashHostIds: async () => '101',
    poll: async () =>
      createSnapshotResult({
        hostCount: 1,
        hostIdsHash: '101',
        sections: [
          { data: { 101: { status: 0 } }, name: 'agent_status' },
          { data: { 101: { cpu_usage: 88 } }, name: 'performance_data' },
          { data: { 101: { component: [] } }, name: 'process_status' },
          { data: { 101: { alarm_count: [] } }, name: 'alarm_count' },
        ],
        status: 'READY',
      }),
  };
  const { context, scope } = createHostListController({ progressive: true, progressiveMetricService });

  await context.loadData();
  hostListWorker.emitComputeDone([host]);
  await flushPromises();
  snapshotCreate.resolve(
    createSnapshotResult({
      hostCount: 1,
      hostIdsHash: '101',
      sections: [],
      status: 'READY',
    })
  );
  await flushPromises();
  assert.equal(context.metricProgressiveState.value, 'READY');

  pageMetric.resolve({ 101: { cpu_usage: 25 } });
  await flushPromises();

  assert.equal(hostListWorker.calls.replaceMetrics.length, 1);
  assert.deepEqual(hostListWorker.calls.patchMetrics, []);
  scope.stop();
});

test('terminal snapshot states remain page-only and retry the snapshot without reloading the base list', async () => {
  for (const status of ['FAILED', 'EXPIRED', 'UNAVAILABLE']) {
    let baseRequestCount = 0;
    let createCount = 0;
    const retryCreate = deferred();
    getHostInfo = async () => {
      baseRequestCount += 1;
      return [createHost({ bkCloudId: 0, bkHostId: 101, ip: '10.0.0.1' })];
    };
    getHostMetricInfo = async () => ({});
    hostListWorker = createControllerWorker();
    const progressiveMetricService = {
      create: async () => {
        createCount += 1;
        if (createCount === 1) {
          return createSnapshotResult({ snapshotId: status === 'UNAVAILABLE' ? undefined : 'snapshot-1', status });
        }
        return retryCreate.promise;
      },
      hashHostIds: async () => '',
      poll: async () => {
        throw new Error('terminal create result must not be polled');
      },
    };
    const { context, scope } = createHostListController({ progressive: true, progressiveMetricService });

    await context.loadData();
    await flushPromises();

    assert.equal(baseRequestCount, 1, status);
    assert.equal(createCount, 2, status);
    assert.deepEqual(hostListWorker.calls.replaceMetrics, [], status);
    scope.stop();
    retryCreate.resolve(createSnapshotResult());
  }
});

test('manual full-snapshot retry invalidates the old retry loop without reloading base or clearing page data', async () => {
  let baseRequestCount = 0;
  let createCount = 0;
  const manualCreate = deferred();
  getHostInfo = async () => {
    baseRequestCount += 1;
    return [createHost({ bkCloudId: 0, bkHostId: 101, ip: '10.0.0.1' })];
  };
  getHostMetricInfo = async () => ({ 101: { cpu_usage: 25 } });
  hostListWorker = createControllerWorker();
  const progressiveMetricService = {
    create: async () => {
      createCount += 1;
      return createCount === 1
        ? createSnapshotResult({ retryAfterMs: 50, status: 'UNAVAILABLE', snapshotId: undefined })
        : manualCreate.promise;
    },
    hashHostIds: async () => '101',
    poll: async () => new Promise(() => {}),
  };
  const { context, scope } = createHostListController({ progressive: true, progressiveMetricService });

  await context.loadData();
  hostListWorker.emitComputeDone([createHost({ bkCloudId: 0, bkHostId: 101, ip: '10.0.0.1' })]);
  await flushPromises();
  assert.equal(context.metricProgressiveState.value, 'UNAVAILABLE');
  assert.equal(hostListWorker.calls.patchMetrics.length, 1);

  context.retryMetricSnapshot();
  context.retryMetricSnapshot();
  await new Promise(resolve => setTimeout(resolve, 60));

  assert.equal(baseRequestCount, 1);
  assert.equal(createCount, 2);
  assert.equal(hostListWorker.calls.patchMetrics.length, 1);
  scope.stop();
  manualCreate.resolve(createSnapshotResult());
});

test('snapshot host-count validation uses the same deduplicated host id set as the hash', async () => {
  const duplicateHosts = [
    createHost({ bkCloudId: 0, bkHostId: 101, ip: '10.0.0.1' }),
    createHost({ bkCloudId: 0, bkHostId: 101, ip: '10.0.0.1' }),
  ];
  getHostInfo = async () => duplicateHosts;
  getHostMetricInfo = async () => ({});
  hostListWorker = createControllerWorker();
  let createCount = 0;
  const progressiveMetricService = {
    create: async () => {
      createCount += 1;
      return createSnapshotResult({
        hostCount: 1,
        hostIdsHash: '101',
        sections: [],
        status: 'READY',
      });
    },
    hashHostIds: async hostIds => hostIds.join(','),
    poll: async () =>
      createSnapshotResult({
        hostCount: 1,
        hostIdsHash: '101',
        sections: [
          { data: {}, name: 'agent_status' },
          { data: {}, name: 'performance_data' },
          { data: {}, name: 'process_status' },
          { data: {}, name: 'alarm_count' },
        ],
        status: 'READY',
      }),
  };
  const { context, scope } = createHostListController({ progressive: true, progressiveMetricService });

  await context.loadData();
  await flushPromises();

  assert.equal(createCount, 1);
  assert.equal(context.metricProgressiveState.value, 'READY');
  assert.equal(hostListWorker.calls.replaceMetrics.length, 1);
  scope.stop();
});

test('a snapshot create failure falls back to the requested time for page metrics while retrying in background', async () => {
  const retryCreate = deferred();
  let createCount = 0;
  const metricRequests = [];
  getHostInfo = async () => [createHost({ bkCloudId: 0, bkHostId: 101, ip: '10.0.0.1' })];
  getHostMetricInfo = async params => {
    metricRequests.push(params);
    return {};
  };
  hostListWorker = createControllerWorker();
  const progressiveMetricService = {
    create: async () => {
      createCount += 1;
      if (createCount === 1) {
        throw new Error('snapshot unavailable');
      }
      return retryCreate.promise;
    },
    hashHostIds: async () => '',
    poll: async () => new Promise(() => {}),
  };
  const { context, scope } = createHostListController({ progressive: true, progressiveMetricService });

  await context.loadData();
  hostListWorker.emitComputeDone([createHost({ bkCloudId: 0, bkHostId: 101, ip: '10.0.0.1' })]);
  await new Promise(resolve => setTimeout(resolve, 1050));

  assert.equal(createCount, 2);
  assert.equal(metricRequests[0].start_time, 0);
  assert.equal(metricRequests[0].end_time, 1);
  scope.stop();
  retryCreate.resolve(createSnapshotResult());
});

test('an unavailable snapshot without canonical fields keeps the requested page time anchor', async () => {
  const metricRequests = [];
  getHostInfo = async () => [createHost({ bkCloudId: 0, bkHostId: 101, ip: '10.0.0.1' })];
  getHostMetricInfo = async params => {
    metricRequests.push(params);
    return {};
  };
  hostListWorker = createControllerWorker();
  const progressiveMetricService = {
    create: async () =>
      createSnapshotResult({
        canonicalEndTime: undefined,
        canonicalStartTime: undefined,
        retryAfterMs: 20,
        snapshotId: undefined,
        status: 'UNAVAILABLE',
      }),
    hashHostIds: async () => '',
    poll: async () => new Promise(() => {}),
  };
  const { context, scope } = createHostListController({ progressive: true, progressiveMetricService });

  await context.loadData();
  hostListWorker.emitComputeDone([createHost({ bkCloudId: 0, bkHostId: 101, ip: '10.0.0.1' })]);
  await flushPromises();

  assert.equal(metricRequests[0].start_time, 0);
  assert.equal(metricRequests[0].end_time, 1);
  scope.stop();
});

test('production progressive mode uses the default snapshot adapter without component injection', async () => {
  const createRequest = deferred();
  defaultProgressiveMetricService = {
    create: () => createRequest.promise,
    hashHostIds: async () => '',
    poll: () => new Promise(() => {}),
  };
  getHostInfo = async () => [];
  getHostMetricInfo = async () => ({});
  hostListWorker = createControllerWorker();
  const { context, scope } = createHostListController({ progressive: true });

  await context.loadData();

  assert.equal(context.metricProgressiveState.value, 'RUNNING');
  scope.stop();
  createRequest.resolve(createSnapshotResult());
});

test('metric quick cards and metric sorting are inert until the full snapshot is ready', () => {
  const progressiveMetricService = {
    create: () => new Promise(() => {}),
    hashHostIds: async () => '',
    poll: () => new Promise(() => {}),
  };
  getHostInfo = async () => [];
  getHostMetricInfo = async () => ({});
  hostListWorker = createControllerWorker();
  const { context, scope } = createHostListController({ progressive: true, progressiveMetricService });

  context.handleCategoryClick('cpu');
  context.handleSortChange('-cpu_usage');
  assert.equal(context.activeCategory.value, '');
  assert.equal(context.sortInfo.value, '');

  context.handleSortChange('bk_host_innerip');
  assert.equal(context.sortInfo.value, 'bk_host_innerip');
  scope.stop();
});

test('disposing the controller rejects late snapshot creation and page responses', async () => {
  const snapshotCreate = deferred();
  const pageMetric = deferred();
  let pollCount = 0;
  getHostInfo = async () => [createHost({ bkCloudId: 0, bkHostId: 101, ip: '10.0.0.1' })];
  getHostMetricInfo = () => pageMetric.promise;
  hostListWorker = createControllerWorker();
  const progressiveMetricService = {
    create: () => snapshotCreate.promise,
    hashHostIds: async () => '101',
    poll: async () => {
      pollCount += 1;
      return new Promise(() => {});
    },
  };
  const { context, scope } = createHostListController({ progressive: true, progressiveMetricService });

  await context.loadData();
  hostListWorker.emitComputeDone([createHost({ bkCloudId: 0, bkHostId: 101, ip: '10.0.0.1' })]);
  await flushPromises();
  scope.stop();
  pageMetric.resolve({ 101: { cpu_usage: 25 } });
  snapshotCreate.resolve(
    createSnapshotResult({
      hostCount: 1,
      hostIdsHash: '101',
      sections: [
        { data: {}, name: 'agent_status' },
        { data: {}, name: 'performance_data' },
        { data: {}, name: 'process_status' },
        { data: {}, name: 'alarm_count' },
      ],
      status: 'READY',
    })
  );
  await flushPromises();

  assert.equal(pollCount, 0);
  assert.deepEqual(hostListWorker.calls.patchMetrics, []);
  assert.deepEqual(hostListWorker.calls.replaceMetrics, []);
});

test('disposing the controller rejects a late poll result without recreating metric state', async () => {
  const pollRequest = deferred();
  getHostInfo = async () => [createHost({ bkCloudId: 0, bkHostId: 101, ip: '10.0.0.1' })];
  getHostMetricInfo = async () => ({});
  hostListWorker = createControllerWorker();
  const progressiveMetricService = {
    create: async () => createSnapshotResult({ snapshotId: 'snapshot-1' }),
    hashHostIds: async () => '101',
    poll: () => pollRequest.promise,
  };
  const { context, scope } = createHostListController({ progressive: true, progressiveMetricService });

  await context.loadData();
  await flushPromises();
  scope.stop();
  pollRequest.resolve(
    createSnapshotResult({
      hostCount: 1,
      hostIdsHash: '101',
      revision: 1,
      sections: [
        { data: {}, name: 'agent_status' },
        { data: {}, name: 'performance_data' },
        { data: {}, name: 'process_status' },
        { data: {}, name: 'alarm_count' },
      ],
      status: 'READY',
    })
  );
  await flushPromises();

  assert.deepEqual(hostListWorker.calls.replaceMetrics, []);
});

test('disposing during a snapshot retry delay prevents the obsolete poll request', async () => {
  let pollCount = 0;
  getHostInfo = async () => [createHost({ bkCloudId: 0, bkHostId: 101, ip: '10.0.0.1' })];
  getHostMetricInfo = async () => ({});
  hostListWorker = createControllerWorker();
  const progressiveMetricService = {
    create: async () => createSnapshotResult({ retryAfterMs: 20, snapshotId: 'snapshot-1' }),
    hashHostIds: async () => '101',
    poll: async () => {
      pollCount += 1;
      return new Promise(() => {});
    },
  };
  const { context, scope } = createHostListController({ progressive: true, progressiveMetricService });

  await context.loadData();
  await flushPromises();
  scope.stop();
  await new Promise(resolve => setTimeout(resolve, 30));

  assert.equal(pollCount, 0);
  assert.deepEqual(hostListWorker.calls.replaceMetrics, []);
});

test('disposing while host-id hashing is pending prevents a worker replacement', async () => {
  const hashRequest = deferred();
  getHostInfo = async () => [createHost({ bkCloudId: 0, bkHostId: 101, ip: '10.0.0.1' })];
  getHostMetricInfo = async () => ({});
  hostListWorker = createControllerWorker();
  const progressiveMetricService = {
    create: async () =>
      createSnapshotResult({
        hostCount: 1,
        hostIdsHash: '101',
        sections: [],
        status: 'READY',
      }),
    hashHostIds: () => hashRequest.promise,
    poll: async () =>
      createSnapshotResult({
        hostCount: 1,
        hostIdsHash: '101',
        sections: [
          { data: {}, name: 'agent_status' },
          { data: {}, name: 'performance_data' },
          { data: {}, name: 'process_status' },
          { data: {}, name: 'alarm_count' },
        ],
        status: 'READY',
      }),
  };
  const { context, scope } = createHostListController({ progressive: true, progressiveMetricService });

  await context.loadData();
  await flushPromises();
  scope.stop();
  hashRequest.resolve('101');
  await flushPromises();

  assert.deepEqual(hostListWorker.calls.replaceMetrics, []);
});

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
  const cardsSource = fs.readFileSync(
    path.resolve(__dirname, '../src/trace/pages/host/components/host-list/host-stat-cards.tsx'),
    'utf8'
  );

  assert.match(hostListSource, /<EmptyStatus[\s\S]*type='500'[\s\S]*onOperation=\{ctx\.loadData\}/);
  assert.match(hostListSource, /metricLoadError=\{ctx\.metricLoadError\.value\}/);
  assert.match(hostListSource, /onRetryMetric=\{ctx\.loadMetricData\}/);
  assert.match(tableSource, /metricLoadError:[\s\S]*type: Boolean/);
  assert.match(tableSource, /retryMetric:/);
  assert.match(tableSource, /指标数据加载失败，当前仅展示主机基础信息/);
  assert.match(tableSource, /HOST_METRIC_DATA_COLUMN_IDS\.has\(config\.id\)/);
  assert.match(hostListSource, /fields=\{ctx\.availableFilterFields\.value\}/);
  assert.match(hostListSource, /disabled=\{!ctx\.metricSemanticsReady\.value\}/);
  assert.match(hostListSource, /metricSemanticsReady=\{ctx\.metricSemanticsReady\.value\}/);
  assert.match(hostListSource, /sort=\{ctx\.availableSortInfo\.value\}/);
  assert.match(tableSource, /HOST_PROGRESSIVE_METRIC_FIELD_IDS\.has\(config\.id\)/);
  assert.match(cardsSource, /!props\.disabled && emit\('cardClick', card\.key\)/);
  assert.match(cardsSource, /title=\{props\.disabled \? t\('全量指标准备中'\) : ''\}/);
  assert.match(hostListSource, /全量指标暂不可用，当前按页加载指标/);
  assert.match(hostListSource, /onClick=\{ctx\.retryMetricSnapshot\}/);
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
