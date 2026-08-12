const assert = require('node:assert/strict');
const Module = require('node:module');
const path = require('node:path');
const test = require('node:test');
let vue;
try {
  vue = require('../src/trace/node_modules/vue');
} catch {
  // worktree 复用根 node_modules 时没有 workspace 级软链，回退到 lockfile 中的 Vue 3 runtime。
  vue = require('../node_modules/.pnpm/@vue+runtime-core@3.5.30/node_modules/@vue/runtime-core');
}

process.env.TS_NODE_PROJECT = path.resolve(__dirname, '../src/trace/tsconfig.json');
process.env.TS_NODE_COMPILER_OPTIONS = JSON.stringify({
  jsx: 'react',
  jsxFactory: 'h',
  module: 'commonjs',
  moduleResolution: 'node',
});
require('ts-node/register/transpile-only');

require.extensions['.scss'] = () => {};
global.h = vue.h;

const refreshGeneration = vue.shallowRef(0);
const refreshImmediate = vue.shallowRef('');
const timeRange = vue.ref(['now-1h', 'now']);
const metricAggregationState = vue.ref({
  columns: 3,
  compareTargets: [],
  compareType: 'none',
  keyword: '',
  method: 'AVG',
  timeShift: [],
});
const hostStoreStub = {
  metricAggregationState,
  refreshGeneration,
  refreshImmediate,
  timeRange,
};

let randomSequence = 0;
let detailRequests = [];
let countRequests = [];
const provided = new Map();

const deferred = () => {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
};

const originalLoad = Module._load;
Module._load = function load(request, parent, isMain) {
  const filename = parent?.filename || '';

  if (request === 'vue' && filename.endsWith('/store/modules/host.ts')) {
    return { ...vue, onScopeDispose: () => {} };
  }
  if (request === 'vue' && filename.endsWith('/components/host-metric/host-metric.tsx')) {
    return { ...vue, onMounted: () => {}, provide: (key, value) => provided.set(key, value) };
  }
  if (request === 'vue') {
    return vue;
  }
  if (request === 'monitor-common/utils') {
    return { random: () => `refresh-${++randomSequence}` };
  }
  if (request === '@/components/time-range/utils') {
    return { handleTransformToTimestamp: () => [100, 200] };
  }
  if (request === '@/i18n/dayjs') {
    return { getDefaultTimezone: () => 'UTC' };
  }
  if (request === '@/pages/host/constants/aggregation') {
    return { DEFAULT_AGGREGATION_STATE: metricAggregationState.value };
  }
  if (request === 'monitor-api/modules/scene_view') {
    return {
      getHostOrTopoNodeDetail: params => {
        const request = deferred();
        detailRequests.push({ params, ...request });
        return request.promise;
      },
    };
  }
  if (request === '@vueuse/core' && filename.endsWith('/composables/use-host-detail.ts')) {
    return { useDebounceFn: callback => callback };
  }
  if (request === '@/store/modules/host') {
    return { useHostStore: () => hostStoreStub };
  }
  if (
    request === 'pinia' &&
    (filename.endsWith('/composables/use-host-detail.ts') ||
      filename.endsWith('/components/alarm-tools/index.tsx') ||
      filename.endsWith('/components/host-metric/host-metric.tsx'))
  ) {
    return {
      storeToRefs: () => ({ metricAggregationState, refreshGeneration, refreshImmediate, timeRange }),
    };
  }
  if (request === 'vue-i18n') {
    return { useI18n: () => ({ t: value => value }) };
  }
  if (request === '../../services/global-service' && filename.endsWith('/components/alarm-tools/index.tsx')) {
    return {
      getStrategyAndEventCountApi: params => {
        const request = deferred();
        countRequests.push({ params, ...request });
        return request.promise;
      },
    };
  }
  if (filename.endsWith('/components/host-metric/host-metric.tsx')) {
    if (request === '../../composables/use-metric-aggregation') {
      return {
        useMetricAggregation: state => ({
          state,
          updateState: () => {},
          viewOptions: vue.shallowRef({}),
        }),
      };
    }
    if (request === '../../composables/use-metric-groups') {
      return {
        useMetricGroups: () => ({
          handleReset: () => {},
          handleSave: () => {},
          load: () => {},
          loading: vue.shallowRef(false),
          orderData: vue.shallowRef([]),
          rows: vue.shallowRef([]),
          settingShow: vue.shallowRef(false),
        }),
      };
    }
    if (request === '../dashbords') {
      return { buildScopedVars: () => ({}), DashboardPanel: {} };
    }
    if (request === './group-manage-dialog' || request === './metric-toolbar') {
      return {};
    }
  }
  return originalLoad(request, parent, isMain);
};

const { createPinia, setActivePinia } = require('pinia');
const { useHostStore } = require('../src/trace/store/modules/host.ts');
const { useHostDetail } = require('../src/trace/pages/host/composables/use-host-detail.ts');
const AlarmTools = require('../src/trace/pages/host/components/alarm-tools/index.tsx').default;
const HostMetric = require('../src/trace/pages/host/components/host-metric/host-metric.tsx').default;
Module._load = originalLoad;

const hostNode = id => ({
  alias_name: `host-${id}`,
  bk_biz_id: 2,
  bk_cloud_id: 0,
  bk_host_id: id,
  bk_host_innerip: `10.0.0.${id}`,
  bk_host_innerip_v6: '',
  bk_host_name: `host-${id}`,
  display_name: `host-${id}`,
  id: String(id),
  ip: `10.0.0.${id}`,
  name: `10.0.0.${id}`,
  os_type: 'linux',
});

const flushPromises = () => new Promise(resolve => setImmediate(resolve));

const collectNumbers = vnode => {
  if (typeof vnode === 'number') return [vnode];
  if (!vnode || typeof vnode !== 'object') return [];
  const children = Array.isArray(vnode.children) ? vnode.children : [];
  return children.flatMap(collectNumbers);
};

test('立即刷新与自动刷新推进同一个刷新代次', async () => {
  setActivePinia(createPinia());
  const store = useHostStore();
  assert.equal(typeof store.refreshGeneration, 'number');

  const initialGeneration = store.refreshGeneration;
  store.refreshImmediate = 'manual-refresh';
  await vue.nextTick();
  assert.equal(store.refreshGeneration, initialGeneration + 1);

  const originalSetInterval = global.setInterval;
  let intervalCallback;
  global.setInterval = callback => {
    intervalCallback = callback;
    return 1;
  };
  try {
    store.refreshInterval = 60_000;
    intervalCallback();
    assert.equal(store.refreshGeneration, initialGeneration + 2);
  } finally {
    global.setInterval = originalSetInterval;
  }
});

test('主机图表监听统一刷新代次', () => {
  provided.clear();
  HostMetric.setup({ compareHostList: [], selectedNode: hostNode(1) });

  assert.equal(provided.get('refreshImmediate'), refreshGeneration);
});

test('主机详情随刷新代次重新请求', async t => {
  detailRequests = [];
  refreshGeneration.value = 0;
  const selectedNode = vue.shallowRef(hostNode(1));
  const scope = vue.effectScope();
  t.after(() => scope.stop());
  scope.run(() => useHostDetail(selectedNode));

  assert.equal(detailRequests.length, 1);
  refreshGeneration.value += 1;
  await vue.nextTick();
  assert.equal(detailRequests.length, 2);
});

test('旧主机详情请求不能覆盖新节点', async t => {
  detailRequests = [];
  refreshGeneration.value = 0;
  const selectedNode = vue.shallowRef(hostNode(1));
  const scope = vue.effectScope();
  t.after(() => scope.stop());
  const detail = scope.run(() => useHostDetail(selectedNode));

  selectedNode.value = hostNode(2);
  await vue.nextTick();
  assert.equal(detailRequests.length, 2);

  detailRequests[1].resolve([{ label: 'node', type: 'text', value: 'new' }]);
  await flushPromises();
  assert.equal(detail.detailData.value[0].value, 'new');

  detailRequests[0].resolve([{ label: 'node', type: 'text', value: 'old' }]);
  await flushPromises();
  assert.equal(detail.detailData.value[0].value, 'new');
});

test('告警计数随刷新代次请求且旧节点结果不能回写', async t => {
  countRequests = [];
  refreshGeneration.value = 0;
  const props = vue.reactive({ selectedNode: hostNode(1) });
  const scope = vue.effectScope();
  t.after(() => scope.stop());
  const render = scope.run(() => AlarmTools.setup(props));

  props.selectedNode = hostNode(2);
  await vue.nextTick();
  assert.equal(countRequests.length, 2);

  countRequests[1].resolve({ event_counts: 20, strategy_counts: 2 });
  await flushPromises();
  assert.deepEqual(collectNumbers(render()), [2, 20]);

  countRequests[0].resolve({ event_counts: 10, strategy_counts: 1 });
  await flushPromises();
  assert.deepEqual(collectNumbers(render()), [2, 20]);

  refreshGeneration.value += 1;
  await vue.nextTick();
  assert.equal(countRequests.length, 3);
});
