const assert = require('node:assert/strict');
const Module = require('node:module');
const path = require('node:path');
const test = require('node:test');
const vue = require('../src/trace/node_modules/vue');

process.env.TS_NODE_PROJECT = path.resolve(__dirname, '../src/trace/tsconfig.json');
process.env.TS_NODE_COMPILER_OPTIONS = JSON.stringify({
  module: 'commonjs',
  moduleResolution: 'node',
});
require('ts-node/register/transpile-only');

let alarmStore;

const originalLoad = Module._load;
Module._load = function load(request, parent, isMain) {
  if (request === 'vue') {
    return {
      ...vue,
      onMounted: callback => callback(),
      onScopeDispose: () => {},
    };
  }
  if (request === 'monitor-common/utils') {
    return { commonPageSizeGet: () => 50 };
  }
  if (request === '../utils' && parent?.filename.endsWith('use-alarm-table.ts')) {
    return { getOperatorDisabled: () => false };
  }
  if (request === '@/store/modules/alarm-center') {
    return { useAlarmCenterStore: () => alarmStore };
  }
  return originalLoad(request, parent, isMain);
};

const { useAlarmTable } = require('../src/trace/pages/alarm-center/composables/use-alarm-table.ts');
Module._load = originalLoad;

const deferred = () => {
  let resolve;
  const promise = new Promise(resolvePromise => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
};

const flushPromises = () => new Promise(resolve => setImmediate(resolve));

test('关联信息未返回时先展示告警列表', async () => {
  const relevance = deferred();
  const row = { id: 'alert-1', assignee: [], follower: [] };
  let relevanceRequested = false;

  alarmStore = {
    commonFilterParams: {},
    alarmService: {
      getAlterRelevance: () => {
        relevanceRequested = true;
        return relevance.promise;
      },
      getFilterTableList: async () => ({ data: [row], total: 1 }),
    },
  };

  const table = useAlarmTable();
  await flushPromises();
  let renderedEventCount;
  const stopRenderEffect = vue.watchEffect(() => {
    renderedEventCount = table.data.value[0]?.event_count;
  });

  assert.equal(relevanceRequested, true);
  assert.deepEqual(table.data.value, [row]);
  assert.equal(table.loading.value, false);
  assert.equal(renderedEventCount, undefined);

  relevance.resolve({ event_count: { 'alert-1': 5 }, extend_info: {} });
  await flushPromises();
  assert.equal(renderedEventCount, 5);
  stopRenderEffect();
});

test('旧请求返回时不覆盖新列表的关联信息', async () => {
  const firstRelevance = deferred();
  const secondRelevance = deferred();
  const firstRow = { id: 'alert-1', assignee: [], follower: [] };
  const secondRow = { id: 'alert-1', assignee: [], follower: [] };
  let listRequestCount = 0;
  let relevanceRequestCount = 0;
  const signals = [];

  alarmStore = {
    commonFilterParams: {},
    alarmService: {
      getAlterRelevance: (_data, { signal }) => {
        relevanceRequestCount += 1;
        signals.push(signal);
        return relevanceRequestCount === 1 ? firstRelevance.promise : secondRelevance.promise;
      },
      getFilterTableList: async () => {
        listRequestCount += 1;
        return listRequestCount === 1 ? { data: [firstRow], total: 1 } : { data: [secondRow], total: 1 };
      },
    },
  };

  const table = useAlarmTable();
  await flushPromises();
  table.page.value = 2;
  await flushPromises();

  assert.deepEqual(table.data.value, [secondRow]);
  assert.equal(signals[0].aborted, true);
  assert.equal(signals[1].aborted, false);

  secondRelevance.resolve({ event_count: { 'alert-1': 5 }, extend_info: {} });
  await flushPromises();
  assert.equal(table.data.value[0].event_count, 5);

  firstRelevance.resolve({ event_count: { 'alert-1': 3 }, extend_info: {} });
  await flushPromises();
  assert.equal(table.data.value[0].event_count, 5);
});
