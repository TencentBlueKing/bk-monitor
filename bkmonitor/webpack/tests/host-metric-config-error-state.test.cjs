const assert = require('node:assert/strict');
const fs = require('node:fs');
const Module = require('node:module');
const path = require('node:path');
const test = require('node:test');

process.env.TS_NODE_PROJECT = path.resolve(__dirname, '../src/trace/tsconfig.json');
process.env.TS_NODE_COMPILER_OPTIONS = JSON.stringify({
  esModuleInterop: true,
  module: 'commonjs',
  moduleResolution: 'node',
});
require('ts-node/register/transpile-only');

const vue = require('../node_modules/.pnpm/@vue+runtime-core@3.5.30/node_modules/@vue/runtime-core');

const deferred = () => {
  let reject;
  let resolve;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
};

let getHostViewsPanelsApi;
let getHostMetricGroupPanelOrderApi;
const originalLoad = Module._load;
Module._load = function loadWithMetricGroupStubs(request, parent, isMain) {
  if (request === 'vue') {
    return vue;
  }
  if (request === 'vue-i18n') {
    return { useI18n: () => ({ t: value => value }) };
  }
  if (request === 'monitor-api/modules/scene_view') {
    return { updateSceneView: async () => {} };
  }
  if (request === '../services/graph-service') {
    return {
      getHostMetricGroupPanelOrderApi: (...args) => getHostMetricGroupPanelOrderApi(...args),
      getHostViewsPanelsApi: (...args) => getHostViewsPanelsApi(...args),
    };
  }
  return originalLoad(request, parent, isMain);
};
const { useMetricGroups } = require('../src/trace/pages/host/composables/use-metric-groups.ts');
Module._load = originalLoad;

const panels = [
  {
    id: 'system',
    panels: [{ id: 'cpu', title: 'CPU' }],
    title: '系统',
  },
];
const order = [{ id: 'system', panels: [{ id: 'cpu' }] }];

const createController = () =>
  useMetricGroups({
    keyword: '',
    ungroupTitle: '未分组',
  });

test('主机指标 panel 请求失败时必须显示错误态而非空态', async () => {
  getHostViewsPanelsApi = () => Promise.reject(new Error('panels request failed'));
  getHostMetricGroupPanelOrderApi = async () => order;
  const context = createController();

  assert.equal(await context.load(), false);
  assert.equal(context.loadError.value, true);
  assert.equal(context.loading.value, false);
  assert.deepEqual(context.rows.value, []);
  assert.deepEqual(context.orderData.value, []);
});

test('主机指标 order 请求失败时必须显示错误态而非空态', async () => {
  getHostViewsPanelsApi = async () => panels;
  getHostMetricGroupPanelOrderApi = () => Promise.reject(new Error('order request failed'));
  const context = createController();

  assert.equal(await context.load(), false);
  assert.equal(context.loadError.value, true);
  assert.equal(context.loading.value, false);
  assert.deepEqual(context.rows.value, []);
  assert.deepEqual(context.orderData.value, []);
});

test('主机指标配置重试成功后清除错误态并恢复图表分组', async () => {
  let requestCount = 0;
  getHostViewsPanelsApi = () => {
    requestCount += 1;
    return requestCount === 1 ? Promise.reject(new Error('panels request failed')) : Promise.resolve(panels);
  };
  getHostMetricGroupPanelOrderApi = async () => order;
  const context = createController();

  assert.equal(await context.load(), false);
  assert.equal(await context.load(), true);
  assert.equal(context.loadError.value, false);
  assert.deepEqual(
    context.rows.value.map(item => item.id),
    ['system']
  );
  assert.deepEqual(context.orderData.value, order);
});

test('旧主机指标配置失败不得覆盖后发成功状态', async () => {
  const firstPanels = deferred();
  const secondPanels = deferred();
  const panelRequests = [firstPanels, secondPanels];
  getHostViewsPanelsApi = () => panelRequests.shift().promise;
  getHostMetricGroupPanelOrderApi = async () => order;
  const context = createController();
  const firstLoad = context.load();
  const secondLoad = context.load();

  secondPanels.resolve(panels);
  assert.equal(await secondLoad, true);
  firstPanels.reject(new Error('stale panels request failed'));
  await firstLoad;

  assert.equal(context.loadError.value, false);
  assert.equal(context.loading.value, false);
  assert.deepEqual(
    context.rows.value.map(item => item.id),
    ['system']
  );
});

test('系统指标配置加载、失败与重试使用独立可辨识状态', () => {
  const hostMetricSource = fs.readFileSync(
    path.resolve(__dirname, '../src/trace/pages/host/components/host-metric/host-metric.tsx'),
    'utf8'
  );
  const dashboardPanelSource = fs.readFileSync(
    path.resolve(__dirname, '../src/trace/pages/host/components/dashbords/components/dashboard-panel.tsx'),
    'utf8'
  );

  assert.match(hostMetricSource, /loadError=\{groupsCtrl\.loadError\.value\}/);
  assert.match(hostMetricSource, /loading=\{groupsCtrl\.loading\.value\}/);
  assert.match(hostMetricSource, /onRetry=\{groupsCtrl\.load\}/);
  assert.match(dashboardPanelSource, /props\.loading[\s\S]*<ChartSkeleton/);
  assert.match(dashboardPanelSource, /props\.loadError[\s\S]*<EmptyStatus[\s\S]*type='500'/);
  assert.match(dashboardPanelSource, /onOperation=\{\(\) => emit\('retry'\)\}/);
});
