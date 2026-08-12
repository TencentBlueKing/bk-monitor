const assert = require('node:assert/strict');
const Module = require('node:module');
const path = require('node:path');
const test = require('node:test');
const vue = require('@vue/runtime-core');

process.env.TS_NODE_PROJECT = path.resolve(__dirname, '../src/trace/tsconfig.json');
process.env.TS_NODE_COMPILER_OPTIONS = JSON.stringify({
  esModuleInterop: true,
  jsx: 'react',
  jsxFactory: 'h',
  module: 'commonjs',
  moduleResolution: 'node',
});
require('ts-node/register/transpile-only');

require.extensions['.scss'] = () => {};
global.h = vue.h;

const requests = [];
const pending = [];
const deferred = () => {
  let resolve;
  const promise = new Promise(resolvePromise => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
};

const hostStoreRefs = {
  processMetricAggregationState: vue.shallowRef({ columns: 1, compareType: 'none', timeShift: [] }),
  timeRange: vue.shallowRef([100, 200]),
  timezone: vue.shallowRef('Asia/Shanghai'),
};

const originalLoad = Module._load;
Module._load = function load(request, parent, isMain) {
  if (request === 'vue') {
    return { ...vue, onBeforeUnmount: () => {}, provide: () => {} };
  }
  if (request === 'bkui-vue') return { Exception: {}, Sideslider: {} };
  if (request === 'monitor-common/utils') return { random: () => 'refresh' };
  if (request === 'pinia') return { storeToRefs: store => store };
  if (request === 'vue-i18n') return { useI18n: () => ({ t: value => value }) };
  if (request.includes('monitor-api/modules/scene_view')) {
    return {
      getHostProcessUptime: params => {
        requests.push(params);
        const request = deferred();
        pending.push(request);
        return request.promise;
      },
    };
  }
  if (request.endsWith('components/time-range/utils')) {
    return { handleTransformToTimestamp: value => value };
  }
  if (request.includes('components/refresh-rate/refresh-rate')) return { default: { name: 'RefreshRate' } };
  if (request.includes('components/skeleton/chart-skeleton')) return { default: {} };
  if (request.includes('components/time-range/time-range')) return { default: { name: 'TimeRange' } };
  if (request.endsWith('pages/host/constants/enum')) return { ProcessDetailTabEnum: { METRIC: 'metric' } };
  if (request.endsWith('pages/host/constants/process')) {
    return { PROCESS_DETAIL_TABS: [], PROCESS_PORT_STATUS_MAP: {} };
  }
  if (request.endsWith('pages/host/utils/process')) {
    return {
      formatProcessSeriesAlias: (_dimensions, alias) => alias,
      formatProcessUptimeDetail: (uptime, observedAt) => `${uptime}@${observedAt}`,
    };
  }
  if (request.endsWith('composables/use-metric-aggregation')) {
    return {
      useMetricAggregation: state => ({
        state,
        updateState: () => {},
        viewOptions: vue.shallowRef({}),
      }),
    };
  }
  if (request.endsWith('composables/use-process-metric')) {
    return {
      useProcessMetric: () => ({
        rows: vue.shallowRef([]),
        orderData: vue.shallowRef([]),
        loading: vue.shallowRef(false),
        settingShow: vue.shallowRef(false),
        load: () => {},
        handleReset: () => {},
        handleSave: () => {},
      }),
    };
  }
  if (request.endsWith('dashbords')) {
    return { buildScopedVars: () => ({}), DashboardPanel: {} };
  }
  if (request.endsWith('host-metric/group-manage-dialog')) return { default: {} };
  if (request.endsWith('host-metric/metric-toolbar')) return { default: {} };
  if (request === '@/store/modules/host') return { useHostStore: () => hostStoreRefs };
  return originalLoad(request, parent, isMain);
};

const ProcessDetail =
  require('../src/trace/pages/host/components/host-process/process-detail/process-detail.tsx').default;
Module._load = originalLoad;

const flushPromises = async () => {
  await vue.nextTick();
  await new Promise(resolve => setImmediate(resolve));
};

const collectText = vnode => {
  if (vnode == null || typeof vnode === 'boolean') return '';
  if (typeof vnode === 'string' || typeof vnode === 'number') return String(vnode);
  if (Array.isArray(vnode)) return vnode.map(collectText).join('');
  return collectText(vnode.children);
};

const findVNode = (vnode, predicate) => {
  if (!vnode || typeof vnode !== 'object') return null;
  if (predicate(vnode)) return vnode;
  const children = Array.isArray(vnode.children) ? vnode.children : [];
  for (const child of children) {
    const found = findVNode(child, predicate);
    if (found) return found;
  }
  return null;
};

const createProcessDetail = () => {
  requests.length = 0;
  pending.length = 0;
  hostStoreRefs.timeRange.value = [100, 200];
  const props = vue.reactive({
    show: true,
    process: {
      name: 'nginx',
      hostIp: '127.0.0.1',
      uptime: 999,
      instanceCount: 1,
      portStatus: null,
      user: 'root',
      protocol: '',
      bindIp: '',
      port: '',
      startCommand: 'nginx',
    },
    selectedNode: {
      bk_biz_id: 2,
      bk_host_id: 101,
      bk_cloud_id: 0,
      ip: '127.0.0.1',
      name: 'host-1',
    },
    compareHostList: [],
  });
  const scope = vue.effectScope();
  const exposed = scope.run(() => ProcessDetail.setup(props));
  return { exposed, props, scope };
};

test('抽屉头部按局部历史时点重查秒级 uptime', async () => {
  const { exposed, scope } = createProcessDetail();

  assert.deepEqual(requests[0], {
    bk_biz_id: 2,
    bk_host_id: 101,
    display_name: 'nginx',
    start_time: 100,
    end_time: 200,
  });
  pending[0].resolve({ value: 3600, unit: 's' });
  await flushPromises();
  assert.match(collectText(exposed.renderInfo()), /3600@200/);
  assert.doesNotMatch(collectText(exposed.renderInfo()), /999@/);

  const timeRange = findVNode(exposed.renderHeader(), vnode => Array.isArray(vnode.props?.modelValue));
  timeRange.props['onUpdate:modelValue']([300, 400]);
  await flushPromises();
  assert.deepEqual(requests[1], {
    bk_biz_id: 2,
    bk_host_id: 101,
    display_name: 'nginx',
    start_time: 300,
    end_time: 400,
  });
  pending[1].resolve({ value: 7200, unit: 's' });
  await flushPromises();
  assert.match(collectText(exposed.renderInfo()), /7200@400/);
  scope.stop();
});

test('节点和时间连续切换时旧 uptime 响应不能覆盖新响应', async () => {
  const { exposed, props, scope } = createProcessDetail();
  pending[0].resolve({ value: 100, unit: 's' });
  await flushPromises();

  const timeRange = findVNode(exposed.renderHeader(), vnode => Array.isArray(vnode.props?.modelValue));
  timeRange.props['onUpdate:modelValue']([300, 400]);
  await flushPromises();
  props.selectedNode = { ...props.selectedNode, bk_host_id: 202, name: 'host-2' };
  await flushPromises();

  assert.equal(requests[1].bk_host_id, 101);
  assert.equal(requests[1].end_time, 400);
  assert.equal(requests[2].bk_host_id, 202);
  assert.equal(requests[2].end_time, 400);

  pending[2].resolve({ value: 300, unit: 's' });
  await flushPromises();
  pending[1].resolve({ value: 200, unit: 's' });
  await flushPromises();

  assert.match(collectText(exposed.renderInfo()), /300@400/);
  assert.doesNotMatch(collectText(exposed.renderInfo()), /200@400/);
  scope.stop();
});
