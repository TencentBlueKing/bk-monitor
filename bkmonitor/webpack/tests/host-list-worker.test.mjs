import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import vm from 'node:vm';
import ts from 'typescript';

const hostRoot = path.join(import.meta.dirname, '../src/trace/pages/host');
const workerSource = fs.readFileSync(path.join(hostRoot, 'workers/host-list.worker.raw.js'), 'utf8');
const clone = value => structuredClone(value);
const params = overrides => ({
  activeCategory: '',
  keyword: '',
  page: 1,
  pageSize: 50,
  selectedNode: null,
  sortInfo: '',
  stickyValue: {},
  where: [],
  ...overrides,
});
const moduleInfo = (set, module, name = `Cluster ${set}`) => ({
  bk_inst_name: `Module ${module}`,
  topo_link: ['biz1', `set${set}`, `module${module}`],
  topo_link_display: ['Business', name, `Module ${module}`],
});
const baseList = [1, 2, 12, 21, 22].map((id, index) => ({
  bk_host_id: id,
  bk_host_innerip: index === 2 ? '127.0.0.1' : `127.0.0.${id}`,
  bk_host_outerip: `198.51.100.${id}`,
  bk_host_innerip_v6: `2001:db8::${id}`,
  bk_cloud_id: index === 2 ? 2 : 1,
  bk_cloud_name: index === 2 ? 'Cloud B' : 'Cloud A',
  bk_host_name: `host-${id}`,
  bk_os_name: 'Linux',
  module: index === 4 ? [] : [moduleInfo(index % 2, index % 2, index === 2 ? 'Later name' : undefined)],
}));
const metricListMap = {
  1: {
    cpu_usage: 0,
    mem_usage: 0,
    disk_in_use: 0,
    status: 0,
    alarm_count: [],
    component: [
      { display_name: 'nginx', status: 0, marker: 'first' },
      { display_name: 'nginx', status: 1, marker: 'last' },
      { display_name: 'db', status: -1 },
    ],
  },
  2: { cpu_usage: 90, mem_usage: 85, disk_in_use: 80, status: 2, alarm_count: [{ count: 2 }, { count: 1 }] },
  12: { cpu_usage: 90, mem_usage: null, status: 3, alarm_count: [] },
  22: { cpu_usage: 'unknown', mem_usage: 99, disk_in_use: 79, status: -1 },
};

function createWorker(source = workerSource, instrument = false) {
  const calls = {};
  const names = ['matchTopoNode', 'computeCategoryStats', 'filterByConditions', 'sortRows', 'extractClusters'];
  if (instrument) {
    for (const name of names) {
      calls[name] = 0;
      source = source.replace(`const ${name} =`, `let ${name} =`);
      source += `\nconst original_${name} = ${name}; ${name} = (...args) => {
        calls.${name} += 1; return original_${name}(...args);
      };`;
    }
  }
  let response;
  const context = vm.createContext({ calls, self: { postMessage: value => (response = clone(value)) } });
  vm.runInContext(source, context);
  let requestId = 0;
  return {
    calls,
    send(message) {
      response = undefined;
      context.self.onmessage({ data: clone({ ...message, requestId: ++requestId }) });
      return response;
    },
  };
}

function initialize(worker) {
  worker.send({ type: 'INIT_BASE', baseList });
  worker.send({ type: 'MERGE_METRICS', metricListMap });
}
const compute = (worker, overrides) => worker.send({ type: 'COMPUTE', params: params(overrides) });
const ids = result => result.pagedRows.map(row => row.id);

test('stable numeric sorting keeps pinned rows first and unknown values last; selection retains source order', () => {
  const worker = createWorker();
  initialize(worker);
  const result = compute(worker, { sortInfo: '-cpu_usage', stickyValue: { 1: 1 } });
  assert.deepEqual(ids(result), ['1', '2', '12', '21', '22']);
  assert.deepEqual(result.categoryStats, { alarm: 1, cpu: 2, mem: 2, disk: 1 });
  assert.deepEqual(ids(compute(worker, { sortInfo: '-cpu_usage' })), ['2', '12', '1', '21', '22']);
  assert.deepEqual(ids(compute(worker, { sortInfo: 'cpu_usage' })), ['1', '2', '12', '21', '22']);
  const selection = worker.send({ type: 'GET_FILTERED_ROW_KEYS', params: params({ sortInfo: '-cpu_usage' }) });
  assert.deepEqual(selection.rowKeys, ['1', '2', '12', '21', '22']);
  assert.deepEqual(worker.send({ type: 'GET_SELECTED_IPS', rowKeys: ['12', '1'] }).ips, ['127.0.0.1', '127.0.0.1']);
  const selected = worker.send({ type: 'GET_SELECTED_ROWS', rowKeys: ['1'] }).rows[0];
  assert.deepEqual(selected.component, [
    { display_name: 'nginx', status: 1, marker: 'first' },
    { display_name: 'db', status: -1 },
  ]);
  assert.equal(selected.totalAlarmCount, 0);
  assert.equal(compute(worker).pagedRows[3].totalAlarmCount, null);
});

test('raw Worker filter semantics: path, fuzzy ID/IP, wildcard, numeric missing values and left-to-right conditions', () => {
  const worker = createWorker();
  initialize(worker);
  const cases = [
    [{ key: 'cluster_module', value: ['["biz1","set0"]'] }, ['1', '12']],
    [{ key: 'cluster_module', value: ['invalid-json'] }, ['1', '2', '12', '21']],
    [{ key: 'bk_host_id', value: ['2'] }, ['2', '12', '21', '22']],
    [{ key: 'bk_host_innerip', value: ['127.0.0.1'], method: 'exclude' }, ['2', '21', '22']],
    [{ key: 'bk_host_innerip_v6', value: ['::2'], method: 'include' }, ['2', '21', '22']],
    [{ key: '*', value: [' NGINX '] }, ['1']],
    [{ key: 'cpu_usage', value: [0], method: 'lte' }, ['1']],
    [{ key: 'cpu_usage', value: ['invalid'], method: 'gt' }, ['1', '2', '12', '21', '22']],
    [{ key: 'alarm_count', value: [0], method: 'eq' }, ['1', '12']],
    [{ key: 'status', value: [0], method: 'ne' }, ['2', '12', '21', '22']],
    [{ key: 'bk_cloud_name', value: ['Cloud'], method: 'include' }, ['1', '2', '12', '21', '22']],
    [{ key: 'bk_cloud_name', value: ['Cloud A'], method: 'exclude' }, ['12']],
  ];
  for (const [where, expected] of cases) assert.deepEqual(ids(compute(worker, { where: [where] })), expected);
  assert.deepEqual(
    ids(
      compute(worker, {
        where: [
          { key: 'cpu_usage', value: [0] },
          { key: 'status', value: [2], condition: 'or' },
          { key: 'mem_usage', value: [80], method: 'gt', condition: 'and' },
        ],
      })
    ),
    ['2']
  );
  const category = compute(worker, { activeCategory: 'cpu', selectedNode: { id: 'set0' } });
  assert.deepEqual(ids(category), ['12']);
  assert.deepEqual(category.categoryStats, { alarm: 0, cpu: 1, mem: 0, disk: 0 });
  assert.deepEqual(ids(compute(worker, { selectedNode: { bk_host_id: 12 } })), ['12']);
});

test('page changes only slice; ordering, conditions, topology and data invalidate their own stages', () => {
  const worker = createWorker(workerSource, true);
  initialize(worker);
  compute(worker);
  let before = clone(worker.calls);
  compute(worker, { page: 2, pageSize: 2 });
  worker.send({ type: 'GET_FILTERED_ROW_KEYS', params: params() });
  assert.deepEqual(worker.calls, before);

  compute(worker, { sortInfo: '-cpu_usage' });
  assert.deepEqual(worker.calls, { ...before, sortRows: before.sortRows + 1 });
  before = clone(worker.calls);
  compute(worker, { sortInfo: '-cpu_usage', stickyValue: { 21: 1 } });
  assert.deepEqual(worker.calls, { ...before, sortRows: before.sortRows + 1 });

  before = clone(worker.calls);
  compute(worker, { keyword: 'host', where: [{ key: 'status', value: [0], method: 'ne' }] });
  assert.deepEqual(worker.calls, {
    ...before,
    filterByConditions: before.filterByConditions + 1,
    sortRows: before.sortRows + 1,
  });
  before = clone(worker.calls);
  compute(worker, { keyword: 'host', where: [{ key: 'status', value: [0], method: 'ne' }], page: 2 });
  assert.deepEqual(worker.calls, before);

  for (const conditions of [
    { keyword: 'host-2' },
    { where: [{ key: 'status', value: [2] }] },
    { activeCategory: 'cpu' },
  ]) {
    before = clone(worker.calls);
    compute(worker, conditions);
    assert.deepEqual(worker.calls, {
      ...before,
      filterByConditions: before.filterByConditions + 1,
      sortRows: before.sortRows + 1,
    });
  }

  before = clone(worker.calls);
  compute(worker, { selectedNode: { id: 'set0' } });
  assert.equal(worker.calls.matchTopoNode, before.matchTopoNode + baseList.length);
  assert.equal(worker.calls.computeCategoryStats, before.computeCategoryStats + 1);
  before = clone(worker.calls);
  worker.send({ type: 'MERGE_METRICS', metricListMap: {} });
  const missing = compute(worker, { selectedNode: { id: 'set0' } });
  assert.equal(worker.calls.extractClusters, before.extractClusters);
  assert.equal(worker.calls.computeCategoryStats, before.computeCategoryStats + 1);
  assert.equal(missing.pagedRows[0].cpu_usage, undefined);
  assert.equal(missing.pagedRows[0].component, undefined);
  assert.deepEqual(missing.categoryStats, { alarm: 0, cpu: 0, mem: 0, disk: 0 });
  worker.send({ type: 'INIT_BASE', baseList: [baseList[1]] });
  assert.deepEqual(ids(compute(worker)), ['2']);
});

test('candidate tree retains the first name, parent and insertion order; metric override preserves base derivation', () => {
  const worker = createWorker();
  const init = worker.send({ type: 'INIT_BASE', baseList });
  assert.deepEqual(init.filterOptionsMap.cluster_module, [
    {
      id: 'biz1',
      name: 'Business',
      children: [
        { id: 'set0', name: 'Cluster 0', children: [{ id: 'module0', name: 'Module 0', children: [] }] },
        { id: 'set1', name: 'Cluster 1', children: [{ id: 'module1', name: 'Module 1', children: [] }] },
      ],
    },
  ]);
  worker.send({ type: 'MERGE_METRICS', metricListMap: { 1: { module: [moduleInfo(9, 9)], bk_host_id: 99 } } });
  const row = compute(worker).pagedRows[0];
  assert.equal(row.bk_host_id, 99);
  assert.equal(row.id, '1');
  assert.equal(row.moduleNames, 'Module 0');
  assert.deepEqual(row.module, [moduleInfo(9, 9)]);
});

function loadTypeScript(relativePath, imports) {
  const source = fs.readFileSync(path.join(hostRoot, relativePath), 'utf8');
  const compiled = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  });
  const exports = {};
  vm.runInNewContext(compiled.outputText, { exports, require: id => imports[id], ...imports.globals });
  return exports;
}

test('page row conversion has the same output as actual raw Worker for base, overrides, missing metrics and processes', () => {
  const core = loadTypeScript('utils/host-list-core.ts', {
    'monitor-common/utils': { isObject: value => value && typeof value === 'object' },
  });
  const worker = createWorker();
  const bases = [...baseList, { ...baseList[0], bk_host_id: undefined }];
  worker.send({ type: 'INIT_BASE', baseList: bases });
  assert.deepEqual(compute(worker).pagedRows, clone(bases.map(row => core.createHostListRow(row))));
  for (const metrics of [metricListMap, { 1: { module: [moduleInfo(9, 9)], bk_host_id: 99 } }, {}]) {
    worker.send({ type: 'MERGE_METRICS', metricListMap: metrics });
    assert.deepEqual(
      compute(worker).pagedRows,
      clone(bases.map(row => core.createHostListRow(row, metrics[row.bk_host_id])))
    );
  }
});

test('HTTP data avoids extra JSON serialization, nested Proxy conditions are unwrapped, and errors allow retry', async () => {
  const workers = [];
  const revocations = [];
  const scheduled = [];
  let dispose;
  let serialized = 0;
  class FakeWorker {
    constructor() {
      workers.push(this);
    }
    postMessage(message) {
      this.message = clone(message);
    }
    terminate() {
      this.terminated = true;
    }
    reply(fields) {
      this.onmessage({ data: { requestId: this.message.requestId, ...fields } });
    }
  }
  const { useHostListWorker } = loadTypeScript('composables/use-host-list-worker.ts', {
    vue: { shallowRef: value => ({ value }), toRaw: value => value, onScopeDispose: callback => (dispose = callback) },
    '@vueuse/core': {
      useDebounceFn:
        callback =>
        (...args) =>
          scheduled.push(() => callback(...args)),
    },
    '../workers/host-list.worker.raw.js?raw': { default: workerSource },
    globals: {
      Worker: FakeWorker,
      Blob,
      URL: { createObjectURL: () => `blob:${workers.length}`, revokeObjectURL: url => revocations.push(url) },
      JSON: {
        parse: JSON.parse,
        stringify: value => {
          serialized += 1;
          return JSON.stringify(value);
        },
      },
    },
  });
  const client = useHostListWorker();
  const init = client.initBaseData(baseList);
  assert.equal(serialized, 0);
  workers[0].reply({ type: 'INIT_BASE_DONE' });
  await init;
  const merge = client.mergeMetrics(metricListMap);
  assert.equal(serialized, 0);
  workers[0].reply({ type: 'MERGE_METRICS_DONE' });
  await merge;
  const result = client.compute(params({ where: [new Proxy({ key: 'status', value: [0] }, {})] }));
  assert.deepEqual(workers[0].message.params.where, [{ key: 'status', value: [0] }]);
  workers[0].reply({ type: 'COMPUTE_DONE', total: 5 });
  assert.equal((await result).total, 5);
  const failed = client.compute(params());
  workers[0].onerror(new Error('worker failed'));
  await assert.rejects(failed, /worker failed/);
  assert.equal(workers[0].terminated, true);
  const retry = client.initBaseData(baseList);
  assert.equal(workers.length, 2);
  client.scheduleCompute(params());
  dispose();
  await assert.rejects(retry, /disposed/);
  scheduled[0]();
  assert.equal(workers.length, 2);
  assert.deepEqual(revocations, ['blob:0', 'blob:1']);
});

test(
  'optional baseline comparison exercises production Worker before optimization',
  { skip: !process.env.HOST_WORKER_BASELINE },
  () => {
    const baseline = createWorker(fs.readFileSync(process.env.HOST_WORKER_BASELINE, 'utf8'));
    const actual = createWorker();
    const compare = message => assert.deepEqual(actual.send(message), baseline.send(message));
    compare({ type: 'INIT_BASE', baseList });
    compare({ type: 'MERGE_METRICS', metricListMap });
    for (const category of ['', 'cpu', 'mem', 'disk', 'alarm']) {
      for (const node of [null, { id: 'set0' }, { bk_host_id: 2 }]) {
        for (const sort of ['', 'cpu_usage', '-cpu_usage']) {
          for (const where of [
            [],
            [{ key: 'cluster_module', value: ['["set0"]'] }],
            [{ key: '*', value: ['host'] }],
            [{ key: 'bk_host_id', value: ['2'] }],
          ]) {
            const input = params({
              activeCategory: category,
              selectedNode: node,
              sortInfo: sort,
              where,
              pageSize: 2,
              stickyValue: { 1: 1 },
            });
            compare({ type: 'COMPUTE', params: input });
            compare({ type: 'COMPUTE', params: { ...input, page: 2 } });
            compare({ type: 'GET_FILTERED_ROW_KEYS', params: input });
          }
        }
      }
    }
    compare({ type: 'MERGE_METRICS', metricListMap: {} });
    compare({ type: 'COMPUTE', params: params() });
    compare({ type: 'GET_FILTER_OPTIONS_MAP' });
  }
);
