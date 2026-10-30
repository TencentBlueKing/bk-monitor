const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

const root = path.resolve(__dirname, '../src/trace/pages/profiling-explore');

function load(entry, external = {}) {
  const cache = new Map();
  function read(file) {
    if (cache.has(file)) return cache.get(file).exports;
    const module = { exports: {} };
    cache.set(file, module);
    const { outputText } = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true },
    });
    new Function('require', 'module', 'exports', outputText)(id => {
      if (id in external) return external[id];
      if (id.startsWith('.')) return read(path.resolve(path.dirname(file), `${id}.ts`));
      if (id.startsWith('@/')) return read(path.resolve(root, '../..', `${id.slice(2)}.ts`));
      if (id === 'vue' || id === 'dayjs') return require(`../src/trace/node_modules/${id}`);
      return require(id);
    }, module, module.exports);
    return module.exports;
  }
  return read(path.join(root, entry));
}

function execution() {
  return {
    task_id: 123, task_name: 'historical-cpu', schedule_type: 'cron', scheduled_at: 1700000000000,
    collection_method: 'perf', collection_type: 'native_cpu', execution_status: 'partial_succeed',
    started_at: 1700000001000, finished_at: 1700000031000, duration_ms: 30000,
    status_summary: { succeed: 1, failed: 1, timeout: 1, cancelled: 1, unknown: 1, outdated: 1 },
    total_hosts: 6,
    config: {
      schedule: { type: 'cron', cron_expression: '0 * * * *', timezone: 'Asia/Shanghai', effective_start_at: 1690000000000, effective_end_at: 1710000000000 },
      target_config: { node_type: 'INSTANCE', nodes: [1, 2, 3, 4, 5, 6].map(bk_host_id => ({ bk_host_id })) },
      process_selector: { type: 'command', config: { enable_dynamic_collection: false, match_pattern: 'worker', exclude_pattern: 'debug', host_pids: [{ bk_host_id: 1, pid: 11 }, { bk_host_id: 2, pid: 22 }, { bk_host_id: 3, pid: 33 }] } },
      collector_config: { duration_sec: 30, frequency_hz: 99, stack_unwind: 'fp' },
      resource_guard_config: { auto_stop_on_resource_pressure: true, max_disk_usage: 1024, min_mem_level: 100 },
    },
    hosts: ['succeed', 'failed', 'timeout', 'cancelled', 'unknown', 'outdated'].map((status, index) => ({
      bk_host_id: index + 1, ip: `192.0.2.${index + 1}`, status, processes: [], message: '',
      started_at: 1700000001000, finished_at: 1700000031000, duration_ms: 30000,
    })),
  };
}

test('失败重试使用历史快照，只提交失败和超时主机及其静态进程', () => {
  const { buildExecutionPayload } = load('utils/collection-history.ts');
  const detail = execution();
  const original = JSON.stringify(detail);
  const payload = buildExecutionPayload(detail, 2, true, 1800000000000);
  assert.deepEqual(payload.target_config, { node_type: 'INSTANCE', nodes: [{ bk_host_id: 2 }, { bk_host_id: 3 }] });
  assert.deepEqual(payload.process_selector.config.host_pids, [{ bk_host_id: 2, pid: 22 }, { bk_host_id: 3, pid: 33 }]);
  assert.deepEqual(payload.schedule, { type: 'immediate', execute_at: 1800000000000, timezone: 'Asia/Shanghai' });
  assert.deepEqual(payload.collector_config, { duration_sec: 30, frequency_hz: 99, stack_unwind: 'fp' });
  assert.equal(payload.name, 'historical-cpu');
  assert.equal(payload.process_selector.config.exclude_pattern, 'debug');
  assert.equal(payload.task_id, undefined);
  assert.equal(JSON.stringify(detail), original);
});

test('失败重试拒绝仍在采集的轮次或没有失败目标的轮次', () => {
  const { buildExecutionPayload } = load('utils/collection-history.ts');
  const detail = execution();
  detail.execution_status = 'running';
  assert.throws(() => buildExecutionPayload(detail, 2, true), /采集中/);
  detail.execution_status = 'succeed';
  detail.hosts = detail.hosts.filter(host => host.status === 'succeed');
  assert.throws(() => buildExecutionPayload(detail, 2, true), /失败/);
});

test('结果链接和历史筛选能恢复，立即执行不能混入任务 ID', () => {
  const { restoreCollectionQuery } = load('utils/collection.ts');
  const { executionSelection } = load('utils/collection-history.ts');
  const detail = execution();
  const result = executionSelection(detail, detail.hosts[0]);
  const history = {
    ips: ['192.0.2.1'], task_id: 7, task_name: '', process_names: ['worker'], process_pids: ['22'], status: 'failed',
  };
  const restored = restoreCollectionQuery(JSON.parse(JSON.stringify({ tab: 'results', history, result })));
  assert.deepEqual(restored.history, history);
  // 任务 ID 与任务名互斥：按 ID 定位时丢弃名称关键词，非法 ID 退回按名称筛选
  assert.equal(restoreCollectionQuery({ history: { ...history, task_name: 'cpu' } }).history.task_name, '');
  assert.equal(restoreCollectionQuery({ history: { ...history, task_id: -1 } }).history.task_id, null);
  assert.equal(restoreCollectionQuery({ history: { ...history, task_id: -1, task_name: 'cpu' } }).history.task_name, 'cpu');
  assert.deepEqual(restored.result, result);
  assert.equal(restored.result.scope, 'host');
  assert.equal(restored.result.bk_host_id, 1);
  assert.equal(executionSelection({ ...detail, schedule_type: 'immediate' }).task_id, undefined);
  assert.equal(restoreCollectionQuery({ result: { ...result, task_id: null } }).result, null);
  assert.equal(restoreCollectionQuery({ result: { ...result, bk_host_id: -1 } }).result, null);
  assert.equal(restoreCollectionQuery({ historyTaskName: 'legacy' }).history.task_name, 'legacy');
});

test('历史分页保留接口顺序，切换条件后旧响应不能混入新列表', async () => {
  const { effectScope, shallowRef, nextTick } = require('../src/trace/node_modules/vue');
  const requests = [];
  const api = {
    listExecutions: (params, options) => new Promise(resolve => requests.push({ params, options, resolve })),
    collectionTopk: async () => [],
  };
  const { useCollectionHistory } = load('composables/use-collection-history.ts', {
    'monitor-api/modules/apm_profile_active_collection': api,
    'vue-i18n': { useI18n: () => ({ t: v => v }) },
  });
  const filters = shallowRef({ ips: [], task_name: '', process_names: [], process_pids: [], status: '' });
  const scope = effectScope();
  const history = scope.run(() => useCollectionHistory({ bizId: shallowRef(2), filters, range: shallowRef([1000, 2000]), revision: shallowRef(0) }));
  try {
    assert.equal(requests[0].params.limit, 20);
    assert.equal(requests[0].params.offset, 0);
    requests[0].resolve({ data: Array.from({ length: 20 }, (_, index) => ({ ...execution(), scheduled_at: 100 - index })) });
    await new Promise(resolve => setImmediate(resolve));
    assert.deepEqual(history.rows.value.map(row => row.scheduled_at), Array.from({ length: 20 }, (_, i) => 100 - i));
    history.loadMore();
    assert.equal(requests[1].params.offset, 20);
    filters.value = { ...filters.value, task_name: 'new' };
    await nextTick();
    assert.equal(requests[1].options.signal.aborted, true);
    assert.equal(requests[2].params.offset, 0);
    assert.equal(requests[2].params.filters.task_name, 'new');
    requests[2].resolve({ data: [{ ...execution(), task_name: 'new' }] });
    await new Promise(resolve => setImmediate(resolve));
    requests[1].resolve({ data: [execution()] });
    await new Promise(resolve => setImmediate(resolve));
    assert.deepEqual(history.rows.value.map(row => row.task_name), ['new']);
    assert.equal(history.hasMore.value, false);
  } finally {
    scope.stop();
  }
});

test('确认失败重试重新读取历史详情，创建成功才切换现场；只读不发起写请求', async () => {
  const { effectScope, shallowRef } = require('../src/trace/node_modules/vue');
  const created = [];
  let completed = 0;
  const api = { executionDetail: async () => execution(), createTask: async payload => { created.push(payload); } };
  const { useCollectionExecution } = load('composables/use-collection-execution.ts', {
    'monitor-api/modules/apm_profile_active_collection': api,
    'vue-i18n': { useI18n: () => ({ t: v => v }) },
  });
  const scope = effectScope();
  const readonly = shallowRef(false);
  const detail = scope.run(() => useCollectionExecution({ bizId: shallowRef(2), readonly, revision: shallowRef(0), onUpdated: () => {}, onCreated: () => { completed += 1; } }));
  try {
    await detail.open(execution());
    detail.requestAction('retry', detail.detail.value);
    await detail.confirmAction();
    assert.equal(created.length, 1);
    assert.deepEqual(created[0].target_config.nodes, [{ bk_host_id: 2 }, { bk_host_id: 3 }]);
    assert.equal(created[0].schedule.type, 'immediate');
    assert.equal(completed, 1);
    assert.equal(detail.selected.value, null);
    readonly.value = true;
    detail.requestAction('rerun', execution());
    await detail.confirmAction();
    assert.equal(created.length, 1);
  } finally { scope.stop(); }
});

test('详情状态排序支持正反向、搜索和恢复接口顺序，不修改历史快照', async () => {
  const { effectScope, shallowRef } = require('../src/trace/node_modules/vue');
  const snapshot = execution();
  const statuses = ['succeed', 'failed', 'unknown', 'timeout', 'outdated', 'running', 'cancelled', 'partial_succeed', 'failed', 'outdate'];
  snapshot.hosts = statuses.map((status, index) => ({
    ...snapshot.hosts[0], bk_host_id: index + 1, ip: `192.0.2.${index + 1}`, status,
  }));
  const original = JSON.stringify(snapshot);
  const { useCollectionExecution } = load('composables/use-collection-execution.ts', {
    'monitor-api/modules/apm_profile_active_collection': { executionDetail: async () => snapshot },
    'vue-i18n': { useI18n: () => ({ t: v => v }) },
  });
  const scope = effectScope();
  const c = scope.run(() => useCollectionExecution({
    bizId: shallowRef(2), readonly: shallowRef(false), revision: shallowRef(0), onUpdated: () => {}, onCreated: () => {},
  }));
  const ids = () => c.hosts.value.map(host => host.bk_host_id);
  try {
    await c.open(snapshot);
    assert.deepEqual(ids(), [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);
    c.hostSort.value = 'asc';
    assert.deepEqual(ids(), [2, 9, 4, 6, 8, 1, 7, 5, 10, 3]);
    c.hostSort.value = 'desc';
    assert.deepEqual(ids(), [3, 5, 10, 7, 1, 8, 6, 4, 2, 9]);
    c.keyword.value = '192.0.2.1';
    assert.deepEqual(ids(), [10, 1]);
    c.hostSort.value = '';
    assert.deepEqual(ids(), [1, 10]);
    c.keyword.value = '';
    assert.deepEqual(ids(), [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);
    assert.equal(JSON.stringify(snapshot), original);
    c.hostSort.value = 'desc';
    await c.open(snapshot);
    assert.equal(c.hostSort.value, '');
    assert.deepEqual(ids(), [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);
  } finally { scope.stop(); }
});

test('历史接入全局时间与手动刷新，新页链接保留业务和执行定位，创建后重置现场', async () => {
  const vue = require('../src/trace/node_modules/vue');
  const { createQueryState } = load('utils/query.ts');
  const initial = createQueryState('Asia/Shanghai');
  initial.view.tab = 'collection';
  initial.collection.tab = 'history';
  initial.collection.history.task_name = 'old';
  initial.timeRange = [1000, 2000];
  const route = vue.reactive({ path: '/profiling-explore', query: { profiling: JSON.stringify(initial) } });
  const opened = [];
  const originalWindow = global.window;
  const originalLocation = global.location;
  global.window = { open: (...args) => opened.push(args), i18n: { t: value => value } };
  global.location = { pathname: '/tenant/monitor/' };
  const { useProfilingQuery } = load('composables/use-profiling-query.ts', {
    vue: { ...vue, onMounted: () => {} },
    'vue-i18n': { useI18n: () => ({ t: value => value }) },
    'vue-router': {
      useRoute: () => route,
      useRouter: () => ({
        replace: async ({ query }) => { route.query = query; },
        resolve: ({ path, query }) => ({ href: `#${path}?${new URLSearchParams(query)}` }),
      }),
    },
    '@blueking/date-picker': { DateRange: class {
      constructor(range) {
        this.isValidate = true;
        this.startDate = new Date(typeof range[0] === 'number' ? range[0] : 3000);
        this.endDate = new Date(typeof range[1] === 'number' ? range[1] : 9000);
      }
    } },
    '@/i18n/dayjs': { getDefaultTimezone: () => 'Asia/Shanghai', updateTimezone: () => {} },
    '@/store/modules/app': { useAppStore: () => ({ bizId: 2 }) },
    'monitor-api/modules/apm_meta': {}, 'monitor-api/modules/apm_profile': {}, 'monitor-api/modules/model': {},
  });
  const scope = vue.effectScope();
  try {
    const query = scope.run(useProfilingQuery);
    await query.initialize();
    await vue.nextTick();
    assert.deepEqual(query.collectionRange.value, [1000, 2000]);
    const revision = query.collectionRevision.value;
    query.executeQuery();
    assert.equal(query.collectionRevision.value, revision + 1);
    query.patch({ timeRange: [4000, 5000] });
    await vue.nextTick();
    assert.deepEqual(query.collectionRange.value, [4000, 5000]);
    const { executionSelection } = load('utils/collection-history.ts');
    const selection = executionSelection(execution(), execution().hosts[0]);
    query.openCollectionResult(selection, true);
    assert.match(opened[0][0], /^\/tenant\/monitor\/\?bizId=2#\/profiling-explore\?/);
    const saved = JSON.parse(new URLSearchParams(opened[0][0].split('#')[1].split('?')[1]).get('profiling'));
    assert.deepEqual(saved.collection.result, selection);
    assert.equal(saved.collection.tab, 'results');
    assert.equal(query.state.value.collection.tab, 'history');
    query.openCollectionResult(selection, false);
    assert.equal(query.state.value.collection.tab, 'results');
    query.collectionCreated();
    await vue.nextTick();
    assert.deepEqual(query.state.value.timeRange, ['now-15m', 'now']);
    assert.equal(query.state.value.collection.tab, 'history');
    assert.equal(query.state.value.collection.history.task_name, '');
    assert.equal(query.state.value.collection.result, null);
    assert.deepEqual(query.collectionRange.value, [3000, 9000]);
  } finally {
    scope.stop();
    global.window = originalWindow;
    global.location = originalLocation;
  }
});

test('进程条件提交后保留候选标识，同 PID 的不同进程别名仍能分别展示', () => {
  const { restoreProcessSelection, parseProcessSelection, processCandidateOptions } = load('utils/collection-history.ts');
  const selected = [JSON.stringify(['process_pids', '22', 'worker:22']), JSON.stringify(['process_pids', '22', 'nginx:22'])];
  const filters = parseProcessSelection(selected);
  assert.deepEqual(filters, { process_names: [], process_pids: ['22'] });
  assert.deepEqual(restoreProcessSelection(filters, selected), selected);
  assert.deepEqual(restoreProcessSelection({ process_names: [], process_pids: [] }, selected), []);
  const restored = restoreProcessSelection(filters, []);
  const options = processCandidateOptions({ process_pids: [{ value: '22', alias: 'worker:22' }, { value: '22', alias: 'nginx:22' }] }, restored);
  assert.equal(options.length, 2);
  assert.equal(options[0].id, restored[0]);
  assert.equal(options[0].name, 'PID: worker:22');
  assert.notEqual(options[1].id, options[0].id);
});

test('终止只提交本轮定位与主机集合，未知轮次不允许终止', async () => {
  const { effectScope, shallowRef } = require('../src/trace/node_modules/vue');
  const calls = [];
  let updated = 0;
  const { useCollectionExecution } = load('composables/use-collection-execution.ts', {
    'monitor-api/modules/apm_profile_active_collection': { cancelExecution: async params => { calls.push(params); } },
    'vue-i18n': { useI18n: () => ({ t: value => value }) },
  });
  const scope = effectScope();
  const controller = scope.run(() => useCollectionExecution({ bizId: shallowRef(2), readonly: shallowRef(false), revision: shallowRef(0), onUpdated: () => { updated += 1; }, onCreated: () => {} }));
  try {
    const row = { ...execution(), schedule_type: 'immediate', execution_status: 'running' };
    controller.requestAction('cancel', row);
    await controller.confirmAction();
    assert.equal(calls.length, 1);
    assert.equal(calls[0].scheduled_at, row.scheduled_at);
    assert.equal(calls[0].task_id, undefined);
    assert.deepEqual(calls[0].hosts, row.hosts.map(({ bk_host_id, ip }) => ({ bk_host_id, ip })));
    assert.equal(updated, 1);
    controller.requestAction('cancel', { ...row, execution_status: 'unknown' });
    await controller.confirmAction();
    assert.equal(calls.length, 1);
  } finally { scope.stop(); }
});

test('重新执行失败保留详情与确认现场，切换业务取消旧快照请求', async () => {
  const { effectScope, shallowRef } = require('../src/trace/node_modules/vue');
  let deferred;
  let defer = false;
  let created = 0;
  let completed = 0;
  const { useCollectionExecution } = load('composables/use-collection-execution.ts', {
    'monitor-api/modules/apm_profile_active_collection': {
      executionDetail: (_, options) => defer ? new Promise(resolve => { deferred = { resolve, signal: options.signal }; }) : Promise.resolve(execution()),
      createTask: async () => { created += 1; throw new Error('create failed'); },
    },
    'vue-i18n': { useI18n: () => ({ t: value => value }) },
  });
  const scope = effectScope();
  const bizId = shallowRef(2);
  const controller = scope.run(() => useCollectionExecution({ bizId, readonly: shallowRef(false), revision: shallowRef(0), onUpdated: () => {}, onCreated: () => { completed += 1; } }));
  try {
    await controller.open(execution());
    controller.requestAction('rerun', execution());
    await controller.confirmAction();
    assert.equal(controller.actionError.value, 'create failed');
    assert.ok(controller.detail.value);
    assert.ok(controller.pending.value);
    assert.equal(completed, 0);
    defer = true;
    const action = controller.confirmAction();
    bizId.value = 3;
    assert.equal(deferred.signal.aborted, true);
    deferred.resolve(execution());
    await action;
    assert.equal(created, 1);
    assert.equal(controller.selected.value, null);
    assert.equal(controller.pending.value, null);
    assert.equal(controller.busy.value, false);
  } finally { scope.stop(); }
});
