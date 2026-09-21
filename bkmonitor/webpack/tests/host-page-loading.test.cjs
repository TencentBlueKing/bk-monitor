const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const ts = require('typescript');
const vue = require('../src/trace/node_modules/vue');

const root = path.join(__dirname, '../src/trace/pages/host');
const flush = () => new Promise(resolve => setImmediate(resolve));
const host = id => ({ bk_host_id: id, bk_cloud_id: 0, bk_host_innerip: `127.0.0.${id}`, module: [] });
const pageResult = (ids, page = 1, total = 150) => ({ items: ids.map(host), page, page_size: 50, total });

function load(file, dependencies = {}) {
  const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const module = { exports: {} };
  new Function('require', 'module', 'exports', code)(
    id => {
      if (id in dependencies) return dependencies[id];
      if (id === 'vue') return vue;
      throw new Error(`Unexpected dependency: ${id}`);
    },
    module,
    module.exports
  );
  return module.exports;
}

const { createHostListRow } = load(`${root}/utils/host-list-core.ts`, {
  'monitor-common/utils': { isObject: value => value !== null && typeof value === 'object' },
});

test('full handoff removes only invalid selections from its snapshot and retains new selections', async () => {
  let finishValidation;
  const data = {
    fullDataReady: vue.shallowRef(false),
    pagedRows: vue.shallowRef([]),
    total: vue.shallowRef(100),
  };
  const selectedRequests = [];
  const { useHostList } = load(`${root}/composables/use-host-list.ts`, {
    vue: { ...vue, onMounted: () => {} },
    '@vueuse/core': { useDebounceFn: fn => fn },
    'bkui-vue': {},
    'monitor-common/utils': { commonPageSizeGet: () => 50 },
    'monitor-common/utils/utils': {},
    pinia: { storeToRefs: value => value },
    'vue-router': { useRoute: () => ({ query: {} }) },
    '../../../components/across-page-selection/across-page-selection': { SelectType: {} },
    '../../../components/retrieval-filter/typing': { EMode: { ui: 'ui' } },
    '../../../components/time-range/utils': {},
    '../../../hooks/use-table-columns-cache': {
      useTableColumnsCache: () => ({ storageColumns: vue.shallowRef([]), fieldsWidthConfig: {} }),
    },
    '../../../hooks/useUserConfig': { default: () => ({}) },
    '../../../store/modules/app': { useAppStore: () => ({ bizId: 1 }) },
    '../../../store/modules/host': {
      useHostStore: () => ({
        timeRange: vue.shallowRef(['now-1h', 'now']),
        timezone: vue.shallowRef('UTC'),
        refreshGeneration: vue.shallowRef(0),
        refreshInterval: vue.shallowRef(0),
      }),
    },
    '../constants/enum': load(`${root}/constants/enum.ts`),
    '../constants/host-list': { HOST_FILTER_FIELDS: [], HOST_LIST_COLUMNS: [], HOST_LIST_DEFAULT_PAGE_SIZE: 50 },
    '../utils/share-scope': { resolveHostRequestScope: () => ({}) },
    './use-host-list-data': { useHostListData: () => data },
    './use-host-list-worker': {
      useHostListWorker: () => ({
        getSelectedRows: keys => {
          selectedRequests.push(keys);
          return new Promise(resolve => {
            finishValidation = resolve;
          });
        },
      }),
    },
    './use-host-url-params': { useHostUrlParams: () => ({ setUrlParams: () => {} }) },
  });
  const effect = vue.effectScope();
  const controller = effect.run(() =>
    useHostList({
      activeCategory: vue.shallowRef(''),
      filterExpanded: vue.shallowRef(false),
      keyword: vue.shallowRef(''),
      readonly: false,
      selectedNode: vue.shallowRef(null),
      where: vue.shallowRef([]),
    })
  );
  controller.handleRowCheck('1', true);
  controller.handleRowCheck('missing', true);
  data.fullDataReady.value = true;
  await vue.nextTick();
  assert.deepEqual(selectedRequests, [['1', 'missing']]);
  controller.handleRowCheck('2', true);
  finishValidation({ rows: [{ id: '1' }] });
  await flush();
  assert.deepEqual([...controller.selectedRowKeys.value], ['1', '2']);
  effect.stop();
});

function harness(scope = {}) {
  const calls = [];
  const services = Object.fromEntries(
    ['getHostInfoList', 'getHostInfoPage', 'getHostMetricInfoList', 'getHostMetricStats'].map(name => [
      name,
      params => new Promise((resolve, reject) => calls.push({ name, params, resolve, reject })),
    ])
  );
  const pending = (name, predicate = () => true) =>
    calls.find(call => !call.done && call.name === name && predicate(call.params));
  const respond = (name, data, predicate, reject = false) => {
    const call = pending(name, predicate);
    assert.ok(call, `pending ${name}`);
    call.done = true;
    call[reject ? 'reject' : 'resolve'](data);
    return call;
  };
  let response;
  const workerSelf = {
    postMessage: value => {
      response = structuredClone(value);
    },
  };
  vm.runInNewContext(fs.readFileSync(`${root}/workers/host-list.worker.raw.js`, 'utf8'), { self: workerSelf });
  let requestId = 0;
  const send = message => {
    workerSelf.onmessage({ data: { ...message, requestId: ++requestId } });
    return Promise.resolve(response);
  };
  const worker = {
    initBaseData: baseList => send({ type: 'INIT_BASE', baseList }),
    mergeMetrics: metricListMap => send({ type: 'MERGE_METRICS', metricListMap }),
    compute: params => send({ type: 'COMPUTE', params }),
  };
  const { useHostListData } = load(`${root}/composables/use-host-list-data.ts`, {
    '../services/host-service': services,
    '../utils/host-list-core': { createHostListRow },
  });
  const page = vue.shallowRef(1);
  const pageSize = vue.shallowRef(50);
  const currentNode = vue.shallowRef(null);
  const filters = { keyword: '', activeCategory: '', sortInfo: '', stickyValue: {}, where: [] };
  let anchor = 1000;
  let anchorCalls = 0;
  const effect = vue.effectScope();
  const data = effect.run(() =>
    useHostListData({
      getScope: () => ({ ...scope }),
      getPageScope: () => (currentNode.value ? { bk_obj_id: 'module', bk_inst_id: 10 } : { ...scope }),
      getTimeParams: () => {
        anchorCalls += 1;
        return { start_time: anchor - 60, end_time: anchor };
      },
      getComputeParams: () => ({
        ...filters,
        selectedNode: currentNode.value,
        page: page.value,
        pageSize: pageSize.value,
      }),
      page,
      pageSize,
      worker,
    })
  );
  const changePage = value => {
    page.value = value;
    data.invalidatePage();
    if (!data.fullDataReady.value) void data.loadPageData();
    void data.refreshList();
  };
  const completeFull = async (ids = [1, 2], metrics = {}) => {
    respond('getHostInfoList', ids.map(host));
    await flush();
    respond('getHostMetricInfoList', metrics, params =>
      scope.bk_host_id ? !!params.bk_host_ids : !params.bk_host_ids
    );
    await flush();
  };
  return {
    data,
    page,
    pageSize,
    currentNode,
    filters,
    worker,
    effect,
    calls,
    pending,
    respond,
    changePage,
    completeFull,
    setAnchor: value => {
      anchor = value;
    },
    getAnchorCalls: () => anchorCalls,
  };
}

test('starts page, full hosts, full metrics and all cards independently with one time anchor', async () => {
  const h = harness();
  void h.data.loadData();
  assert.equal(h.calls.length, 6);
  assert.equal(h.getAnchorCalls(), 1);
  assert.ok(h.pending('getHostMetricInfoList', params => !('bk_host_ids' in params)));
  h.respond('getHostInfoPage', pageResult([1, 2]));
  await flush();
  assert.equal(h.data.loading.value, false);
  assert.equal(h.data.metricLoading.value, true);
  assert.deepEqual(
    h.data.pagedRows.value.map(row => row.id),
    ['1', '2']
  );
  assert.deepEqual(h.pending('getHostMetricInfoList', p => p.bk_host_ids).params.bk_host_ids, [1, 2]);
  h.respond('getHostMetricInfoList', { 1: { cpu_usage: 90 } }, p => p.bk_host_ids);
  await flush();
  assert.equal(h.data.pagedRows.value[0].cpu_usage, 90);
  assert.equal(h.data.fullDataReady.value, false);
  assert.ok(h.calls.filter(c => c.params.end_time).every(c => c.params.end_time === 1000));
  h.effect.stop();
});

test('continues paging while full data is pending and ignores out-of-order pages and metrics', async () => {
  const h = harness();
  void h.data.loadData();
  h.respond('getHostInfoPage', pageResult([1]));
  await flush();
  h.changePage(2);
  h.changePage(3);
  h.respond('getHostInfoPage', pageResult([3], 3), p => p.page === 3);
  await flush();
  h.respond('getHostInfoPage', pageResult([2], 2), p => p.page === 2);
  h.respond('getHostMetricInfoList', { 1: { cpu_usage: 1 } }, p => p.bk_host_ids?.[0] === 1);
  h.respond('getHostMetricInfoList', { 3: { cpu_usage: 93 } }, p => p.bk_host_ids?.[0] === 3);
  await flush();
  assert.deepEqual(
    h.data.pagedRows.value.map(row => row.id),
    ['3']
  );
  assert.equal(h.data.pagedRows.value[0].cpu_usage, 93);
  assert.equal(h.calls.filter(c => c.name === 'getHostMetricInfoList' && c.params.bk_host_ids?.[0] === 2).length, 0);
  h.effect.stop();
});

test('full data can overtake the page request without launching obsolete page metrics', async () => {
  const h = harness();
  void h.data.loadData();
  await h.completeFull([1, 2], { 1: { cpu_usage: 90 } });
  assert.equal(h.data.fullDataReady.value, true);
  assert.equal(h.data.categoryStats.value.cpu, 1);
  h.respond('getHostInfoPage', pageResult([9]));
  await flush();
  assert.deepEqual(
    h.data.pagedRows.value.map(row => row.id),
    ['1', '2']
  );
  assert.equal(h.calls.filter(c => c.name === 'getHostMetricInfoList').length, 1);
  await h.data.refreshList();
  assert.equal(h.data.rawRowCount.value, 2);
  h.effect.stop();
});

test('cards show early values, then atomically use full rows; late success and error cannot overwrite', async () => {
  const h = harness();
  void h.data.loadData();
  h.respond('getHostMetricStats', { complete: true, value: 99 }, p => p.category === 'cpu');
  await flush();
  assert.equal(h.data.categoryStats.value.cpu, 99);
  assert.equal(h.data.loading.value, true);
  await h.completeFull([1], { 1: { cpu_usage: 80, mem_usage: 80 } });
  assert.equal(h.data.categoryStats.value.cpu, 1);
  assert.equal(h.data.categoryStats.value.mem, 1);
  h.respond('getHostMetricStats', { complete: true, value: 99 }, p => p.category === 'mem');
  h.respond('getHostMetricStats', new Error('late failure'), p => p.category === 'disk', true);
  await flush();
  assert.equal(h.data.categoryStats.value.mem, 1);
  assert.equal(h.data.categoryStates.value.disk.error, false);
  const before = h.calls.length;
  await h.data.retryCategory('cpu');
  assert.equal(h.calls.length, before);
  h.effect.stop();
});

test('full failure leaves pages usable and retries reuse the successful full host request', async () => {
  const h = harness();
  void h.data.loadData();
  h.respond('getHostInfoList', [host(1)]);
  h.respond('getHostMetricInfoList', new Error('full unavailable'), p => !p.bk_host_ids, true);
  h.respond('getHostInfoPage', pageResult([1]));
  await flush();
  h.respond('getHostMetricInfoList', { 1: { cpu_usage: 90 } }, p => p.bk_host_ids);
  await flush();
  assert.equal(h.data.fullLoadError.value, true);
  assert.equal(h.data.fullDataReady.value, false);
  assert.equal(h.data.pagedRows.value[0].cpu_usage, 90);
  void h.data.retryFullData();
  assert.equal(h.calls.filter(c => c.name === 'getHostInfoList').length, 1);
  h.respond('getHostMetricInfoList', { 1: { cpu_usage: 91 } }, p => !p.bk_host_ids);
  await flush();
  assert.equal(h.data.fullDataReady.value, true);
  assert.equal(h.data.pagedRows.value[0].cpu_usage, 91);
  h.effect.stop();
});

test('page metric failure keeps base rows and retries only that page, without changing the query anchor', async () => {
  const h = harness();
  void h.data.loadData();
  h.respond('getHostInfoPage', pageResult([2]));
  await flush();
  h.respond('getHostMetricInfoList', new Error('page failed'), p => p.bk_host_ids, true);
  await flush();
  assert.equal(h.data.metricLoadError.value, true);
  assert.equal(h.data.pagedRows.value[0].id, '2');
  h.setAnchor(2000);
  void h.data.loadMetricData();
  const request = h.pending('getHostMetricInfoList', p => p.bk_host_ids);
  assert.equal(request.params.end_time, 1000);
  request.resolve({ 2: { cpu_usage: 0 } });
  await flush();
  assert.equal(h.data.pagedRows.value[0].cpu_usage, 0);
  assert.equal(h.data.metricLoadError.value, false);
  h.effect.stop();
});

test('empty page never turns an empty host-id list into a full metric query', async () => {
  const h = harness();
  void h.data.loadData();
  h.respond('getHostInfoPage', pageResult([], 1, 0));
  await flush();
  assert.equal(h.data.metricLoading.value, false);
  assert.equal(h.calls.filter(c => c.name === 'getHostMetricInfoList').length, 1);
  h.effect.stop();
});

test('page error does not hide independent statistics and full completion clears the error', async () => {
  const h = harness();
  void h.data.loadData();
  h.respond('getHostInfoPage', new Error('page failed'), undefined, true);
  h.respond('getHostMetricStats', { complete: true, value: 0 }, p => p.category === 'cpu');
  await flush();
  assert.equal(h.data.loadError.value, true);
  assert.deepEqual(h.data.categoryStates.value.cpu, { loading: false, error: false });
  await h.completeFull();
  assert.equal(h.data.loadError.value, false);
  h.effect.stop();
});

test('new refresh invalidates prior page, full and statistic responses', async () => {
  const h = harness();
  void h.data.loadData();
  const old = [...h.calls];
  h.setAnchor(2000);
  void h.data.loadData();
  for (const call of old) {
    call.done = true;
    if (call.name === 'getHostInfoList') call.resolve([host(99)]);
    if (call.name === 'getHostInfoPage') call.resolve(pageResult([99]));
    if (call.name === 'getHostMetricInfoList') call.resolve({ 99: { cpu_usage: 99 } });
    if (call.name === 'getHostMetricStats') call.resolve({ complete: true, value: 99 });
  }
  await flush();
  assert.equal(h.data.fullDataReady.value, false);
  assert.equal(h.data.pagedRows.value.length, 0);
  await h.completeFull([1]);
  assert.equal(h.data.pagedRows.value[0].id, '1');
  assert.equal(h.getAnchorCalls(), 2);
  h.effect.stop();
});

test('only the latest view can complete the full handover', async () => {
  const h = harness();
  const computations = [];
  const originalCompute = h.worker.compute;
  h.worker.compute = params => new Promise(resolve => computations.push({ params, resolve }));
  void h.data.loadData();
  await h.completeFull([1, 2]);
  assert.equal(computations.length, 1);
  h.filters.keyword = '127.0.0.2';
  h.data.invalidateView();
  void h.data.refreshList();
  computations[0].resolve(await originalCompute(computations[0].params));
  await flush();
  assert.equal(h.data.fullDataReady.value, false);
  computations[1].resolve(await originalCompute(computations[1].params));
  await flush();
  assert.equal(h.data.fullDataReady.value, true);
  assert.deepEqual(
    h.data.pagedRows.value.map(row => row.id),
    ['2']
  );
  h.effect.stop();
});

test('shared scope full metrics keep explicit IDs and never query the unrestricted business', async () => {
  const h = harness({ bk_host_id: 2 });
  void h.data.loadData();
  assert.equal(h.pending('getHostMetricInfoList'), undefined);
  h.respond('getHostInfoList', [host(2)]);
  await flush();
  const full = h.pending('getHostMetricInfoList');
  assert.deepEqual(full.params.bk_host_ids, [2]);
  assert.equal(full.params.bk_host_id, 2);
  full.resolve({});
  await flush();
  assert.equal(h.data.fullDataReady.value, true);
  h.effect.stop();
});

test('partial statistics stay unknown, and unmounted responses cannot change displayed data', async () => {
  const h = harness();
  void h.data.loadData();
  h.respond('getHostMetricStats', { complete: false, value: null }, p => p.category === 'cpu');
  await flush();
  assert.equal(h.data.categoryStates.value.cpu.error, true);
  h.effect.stop();
  h.respond('getHostInfoPage', pageResult([1]));
  await flush();
  assert.equal(h.data.pagedRows.value.length, 0);
});

test('a shared descendant page requests metrics under the authorized root with explicit page IDs', async () => {
  const h = harness({ bk_obj_id: 'set', bk_inst_id: 5 });
  h.currentNode.value = { id: 'module|10', bk_obj_id: 'module', bk_inst_id: 10 };
  void h.data.loadData();
  assert.equal(h.pending('getHostInfoPage').params.bk_inst_id, 10);
  h.respond('getHostInfoPage', pageResult([2]));
  await flush();
  const metrics = h.pending('getHostMetricInfoList');
  assert.equal(metrics.params.bk_obj_id, 'set');
  assert.equal(metrics.params.bk_inst_id, 5);
  assert.deepEqual(metrics.params.bk_host_ids, [2]);
  h.effect.stop();
});

test('restored filters clamp the current page before the full view takes over', async () => {
  const h = harness();
  h.page.value = 3;
  h.filters.keyword = '127.0.0.2';
  void h.data.loadData();
  await h.completeFull([1, 2]);
  assert.equal(h.page.value, 1);
  assert.equal(h.data.fullDataReady.value, false);
  await h.data.refreshList();
  assert.equal(h.data.fullDataReady.value, true);
  assert.equal(h.data.total.value, 1);
  assert.equal(h.data.pagedRows.value[0].id, '2');
  h.effect.stop();
});

test('Worker failure keeps the page path and full retry reinitializes the successful HTTP data', async () => {
  const h = harness();
  const initialize = h.worker.initBaseData;
  h.worker.initBaseData = async () => {
    throw new Error('worker crashed');
  };
  void h.data.loadData();
  await h.completeFull([1]);
  assert.equal(h.data.fullDataReady.value, false);
  assert.equal(h.data.fullLoadError.value, true);
  h.respond('getHostInfoPage', pageResult([1]));
  await flush();
  h.respond('getHostMetricInfoList', { 1: { cpu_usage: 90 } }, p => p.bk_host_ids);
  await flush();
  assert.equal(h.data.pagedRows.value[0].cpu_usage, 90);
  h.worker.initBaseData = initialize;
  await h.data.retryFullData();
  assert.equal(h.data.fullDataReady.value, true);
  assert.equal(h.calls.filter(c => c.name === 'getHostInfoList').length, 1);
  h.effect.stop();
});
