const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');
const vue = require('../src/trace/node_modules/vue');
const root = path.resolve(__dirname, '../src/trace/pages/host');
const flush = () => new Promise(resolve => setImmediate(resolve));
const deferred = () => {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
};
function load(file, deps = {}) {
  const code = ts.transpileModule(fs.readFileSync(path.join(root, file), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.React, jsxFactory: 'h', jsxFragmentFactory: 'Fragment' },
    fileName: file,
    reportDiagnostics: true,
  });
  assert.equal(code.diagnostics.length, 0, file);
  const module = { exports: {} };
  new Function('require', 'module', 'exports', 'h', 'Fragment', code.outputText)(id => {
    if (id in deps) return deps[id];
    if (id === 'vue') return vue;
    if (id === 'vue-i18n') return { useI18n: () => ({ t: value => value }) };
    if (id.endsWith('.scss')) return {};
    throw new Error(`Unexpected dependency ${id} in ${file}`);
  }, module, module.exports, vue.h, vue.Fragment);
  return module.exports;
}

for (const [file, factory, panelApi, orderApi] of [
  ['use-metric-groups', 'useMetricGroups', 'getHostViewsPanelsApi', 'getHostMetricGroupPanelOrderApi'],
  ['use-process-metric', 'useProcessMetric', 'getProcessViewsPanelsApi', 'getProcessMetricGroupPanelOrderApi'],
]) {
  function harness() {
    const requests = [], saves = [];
    const controller = load(`composables/${file}.ts`, {
      '../services/graph-service': {
        [panelApi]: () => { const request = deferred(); requests.push(request); return request.promise; },
        [orderApi]: () => Promise.resolve([]),
      },
      'monitor-api/modules/scene_view': { updateSceneView: () => { const save = deferred(); saves.push(save); return save.promise; } },
    })[factory];
    const scope = vue.effectScope();
    const state = scope.run(() => controller({ keyword: '', ungroupTitle: '' }));
    return { state, scope, requests, saves };
  }
  const rows = [{ id: 'cpu', title: 'CPU', panels: [{ title: 'Usage' }] }];
  test(`${file}: latest request owns loading; errors retain configuration and can retry`, async () => {
    const h = harness();
    const first = h.state.load();
    const second = h.state.load();
    h.requests[0].reject(new Error('stale'));
    await first;
    assert.equal(h.state.loading.value, true);
    assert.equal(h.state.loadError.value, false);
    h.requests[1].resolve(rows);
    await second;
    assert.equal(h.state.loading.value, false);
    assert.equal(h.state.rows.value.length, 1);
    const retry = h.state.load(true);
    h.requests[2].reject(new Error('failure'));
    await retry;
    assert.equal(h.state.loadError.value, true);
    assert.equal(h.state.rows.value.length, 1);
    const recover = h.state.load(true);
    h.requests[3].resolve(rows);
    await recover;
    assert.equal(h.state.loadError.value, false);
    h.scope.stop();
  });
  test(`${file}: save only owns submitting; failed reload leaves the editor open`, async () => {
    const h = harness();
    const initial = h.state.load();
    h.requests[0].resolve(rows);
    await initial;
    h.state.settingShow.value = true;
    const saving = h.state.handleSave([]);
    assert.equal(h.state.submitting.value, true);
    assert.equal(h.state.loading.value, false);
    await h.state.handleSave([]);
    assert.equal(h.saves.length, 1);
    h.saves[0].resolve({});
    await flush();
    h.requests[1].reject(new Error('reload failed'));
    await saving;
    assert.equal(h.state.submitting.value, false);
    assert.equal(h.state.loading.value, false);
    assert.equal(h.state.settingShow.value, true);
    assert.equal(h.state.rows.value.length, 1);
    h.scope.stop();
  });
  test(`${file}: unmount invalidates configuration responses`, async () => {
    const h = harness();
    const request = h.state.load();
    h.scope.stop();
    h.requests[0].resolve(rows);
    await request;
    assert.equal(h.state.rows.value.length, 0);
  });
}

test('process refresh retains rows, range/host changes reset them, aborted results cannot complete a newer request', async () => {
  const requests = [];
  const host = vue.shallowRef({ bk_host_id: 1, bk_biz_id: 2 });
  const store = {
    timeRange: vue.shallowRef(['now-1h', 'now']), timezone: vue.shallowRef('UTC'),
    timeRangeTimestamp: vue.shallowRef({ start_time: 1, end_time: 2 }),
  };
  const { useProcessList } = load('composables/use-process-list.ts', {
    pinia: { storeToRefs: value => value },
    '../../../store/modules/host': { useHostStore: () => store },
    '../services/process-service': { getHostProcessList: (_, config) => { const request = deferred(); requests.push({ ...request, signal: config.signal }); return request.promise; } },
  });
  const scope = vue.effectScope();
  const state = scope.run(() => useProcessList({ host, keyword: vue.shallowRef('') }));
  requests[0].resolve([{ name: 'nginx', cpuUsage: 1 }]);
  await flush();
  const refresh = state.loadData();
  assert.equal(state.refreshing.value, true);
  assert.equal(state.loading.value, false);
  assert.equal(state.displayList.value[0].name, 'nginx');
  requests[1].reject(new Error('offline'));
  await refresh;
  assert.equal(state.refreshError.value, true);
  assert.equal(state.displayList.value.length, 1);
  void state.loadData();
  host.value = { bk_host_id: 2, bk_biz_id: 2 };
  assert.equal(requests[2].signal.aborted, true);
  assert.equal(state.loading.value, true);
  assert.equal(state.displayList.value.length, 0);
  requests[2].resolve([{ name: 'obsolete' }]);
  await flush();
  assert.equal(state.loading.value, true);
  requests[3].resolve([{ name: 'redis' }]);
  await flush();
  assert.equal(state.displayList.value[0].name, 'redis');
  store.timeRange.value = ['now-24h', 'now'];
  store.timeRangeTimestamp.value = { start_time: 0, end_time: 2 };
  assert.equal(state.displayList.value.length, 0);
  assert.equal(state.loading.value, true);
  scope.stop();
  assert.equal(requests[4].signal.aborted, true);
});

test('detail debounce cannot issue requests after disposal and stable identity avoids metadata reloads', async () => {
  const requests = [], timers = [];
  const refreshGeneration = vue.shallowRef(0);
  const node = vue.shallowRef({ bk_biz_id: 1, bk_host_id: 1 });
  const { useHostDetail } = load('composables/use-host-detail.ts', {
    vue: { ...vue, provide() {} },
    '@vueuse/core': { useDebounceFn: fn => (...args) => timers.push(() => fn(...args)) },
    pinia: { storeToRefs: value => value },
    '@/store/modules/host': { useHostStore: () => ({ refreshGeneration }) },
    '../utils/topo-tree': { isHostNode: value => 'bk_host_id' in value },
    'monitor-api/modules/scene_view': { getHostOrTopoNodeDetail: () => { const request = deferred(); requests.push(request); return request.promise; } },
  });
  const scope = vue.effectScope();
  const state = scope.run(() => useHostDetail(node));
  void timers.shift()();
  requests[0].resolve([{ label: 'IP', value: '127.0.0.1' }]);
  await flush();
  node.value = { ...node.value, name: 'resolved metadata' };
  assert.equal(timers.length, 0);
  refreshGeneration.value++;
  assert.equal(state.detailData.value.length, 1);
  void timers.shift()();
  requests[1].reject(new Error('offline'));
  await flush();
  assert.equal(state.detailData.value.length, 1);
  assert.equal(state.error.value, true);
  node.value = { bk_biz_id: 1, bk_host_id: 2 };
  assert.equal(state.detailData.value.length, 0);
  assert.equal(state.loading.value, true);
  scope.stop();
  await timers.shift()();
  assert.equal(requests.length, 2);
});

const named = name => ({ name });
const find = (node, type) => node?.type === type ? node : Array.isArray(node?.children) ? node.children.map(child => find(child, type)).find(Boolean) : undefined;

test('chart refresh keeps the rendered snapshot, query changes replace it with a skeleton, failure allows retry', async () => {
  const hook = {
    options: vue.shallowRef(null), loading: vue.shallowRef(true), loadError: vue.shallowRef(false),
    metricList: vue.shallowRef([]), targets: vue.shallowRef([]), series: vue.shallowRef([]), chartId: vue.shallowRef('chart'),
    getEchartOptions: async () => hook.options.value,
  };
  const timeRange = vue.shallowRef(['now-1h', 'now']);
  const Chart = named('VueEcharts'), Skeleton = named('HostLoading'), Status = named('HostRefreshStatus'), Empty = named('EmptyStatus');
  const props = vue.reactive({ panel: { targets: [], collect_interval: 60 }, scopedVars: { host: 1 }, customOptions: {}, downSampleRange: 'auto' });
  const Component = load('components/dashbords/components/time-series-card.tsx', {
    vue: { ...vue, getCurrentInstance: () => ({ appContext: { config: { globalProperties: { $api: {} } } } }), useTemplateRef: () => vue.shallowRef(null), inject: (key, fallback) => key === 'timeRange' ? timeRange : fallback },
    'bkui-vue': { ResizeLayout: named('ResizeLayout') },
    'dayjs': { default: { tz: () => ({ unix: () => 1 }) } },
    'monitor-common/utils': { random: () => 'chart' },
    'vue-echarts': { default: Chart },
    '../../../../provider': { useAppReadonlyInject: () => false },
    '../variables/resolve': { resolveGraphPanel: (panel, vars) => ({ ...panel, vars }) },
    '@/components/empty-status/empty-status': { default: Empty },
    '../../host-loading/host-loading': { default: Skeleton, HostRefreshStatus: Status },
    '@/components/time-range/utils': { DEFAULT_TIME_RANGE: [], handleTransformToTimestamp: () => [0, 1] },
    '@/pages/trace-explore/components/explore-chart/use-chart-legend': { useChartLegend: () => ({ legendData: vue.shallowRef([]), handleSelectLegend() {} }) },
    '@/pages/trace-explore/components/explore-chart/use-chart-title-event': { useChartTitleEvent: () => ({}) },
    '@/pages/trace-explore/components/explore-chart/use-echarts': { useEcharts: () => hook },
    '@/plugins/components/chart-title': { default: named('ChartTitle') },
    '@/plugins/components/common-legend': { default: named('CommonLegend') },
    '@/plugins/components/table-legend': { default: named('TableLegend') },
    '@/utils': { reviewInterval: () => 60 },
  }).default;
  const scope = vue.effectScope();
  const state = vue.proxyRefs(scope.run(() => Component.setup(props)));
  const context = new Proxy(state, { get: (target, key) => key in target ? target[key] : props[key] });
  const render = () => Component.render.call(context);
  assert.ok(find(render(), Skeleton));
  const snapshot = { series: [{ data: [1, 2] }] };
  hook.options.value = snapshot; hook.loading.value = false;
  await vue.nextTick();
  assert.equal(find(render(), Chart).props.option, snapshot);
  hook.loading.value = true;
  await vue.nextTick();
  assert.equal(find(render(), Chart).props.option, snapshot);
  assert.equal(find(render(), Skeleton), undefined);
  hook.options.value = null; hook.loadError.value = true; hook.loading.value = false;
  await vue.nextTick();
  assert.equal(find(render(), Chart).props.option, snapshot);
  assert.equal(find(render(), Status).props.error, true);
  props.scopedVars = { host: 2 }; hook.loadError.value = false; hook.loading.value = true;
  await vue.nextTick();
  assert.ok(find(render(), Skeleton));
  assert.equal(find(render(), Chart), undefined);
  hook.loadError.value = true; hook.loading.value = false;
  await vue.nextTick();
  assert.ok(find(render(), Empty));
  scope.stop();
});

test('dashboard placeholders preserve the selected chart column layout and expose one loading status', () => {
  const Component = load('components/host-loading/host-loading.tsx', { 'bkui-vue': { Button: named('Button') } }).default;
  const flatten = node => [node, ...(Array.isArray(node?.children) ? node.children.flatMap(flatten) : [])];
  for (const columns of [1, 2, 3]) {
    const render = Component.setup({ variant: 'dashboard', columns, title: true });
    const tree = render();
    const nodes = flatten(tree);
    assert.equal(tree.props.role, 'status');
    assert.equal(nodes.filter(node => node?.props?.role === 'status').length, 1);
    const grid = nodes.find(node => node?.props?.class === 'host-loading__grid');
    assert.equal(grid.props.style.gridTemplateColumns, `repeat(${columns}, minmax(0, 1fr))`);
    assert.equal(nodes.filter(node => node?.props?.class === 'host-loading__card').length, columns * 2);
  }
});

test('port panels use a matching skeleton and retain same-query values through refresh failure', async () => {
  const requests = [];
  const refresh = vue.shallowRef(0);
  const Skeleton = named('HostLoading'), Status = named('HostRefreshStatus');
  const props = vue.reactive({ panel: { title: 'Ports', type: 'port-status', targets: [{ api: 'host.ports', data: {} }] }, scopedVars: { bk_biz_id: 1, host: 1 } });
  const Component = load('components/dashbords/components/external-panel-card.tsx', {
    vue: { ...vue, getCurrentInstance: () => ({ appContext: { config: { globalProperties: { $api: { host: { ports: () => { const request = deferred(); requests.push(request); return request.promise; } } } } } } }), inject: (key, fallback) => key === 'refreshImmediate' ? refresh : fallback },
    'monitor-ui/monitor-echarts/valueFormats': { getValueFormat: () => value => ({ text: String(value), suffix: '' }) },
    '../../host-loading/host-loading': { default: Skeleton, HostRefreshStatus: Status },
    '../variables/resolve': { resolveVariables: value => value },
    '@/components/time-range/utils': { DEFAULT_TIME_RANGE: [], handleTransformToTimestamp: () => [0, 1] },
    '@/plugins/components/chart-title': { default: named('ChartTitle') },
  }).default;
  const scope = vue.effectScope();
  const render = scope.run(() => Component.setup(props));
  assert.equal(find(render(), Skeleton).props.variant, 'port-status');
  requests[0].resolve([{ value: '8080', name: 'OK', statusColor: 'green' }]);
  await flush();
  assert.ok(find(render(), 'ul'));
  refresh.value++;
  await vue.nextTick();
  assert.ok(find(render(), 'ul'));
  assert.equal(find(render(), Status).props.loading, true);
  requests[1].reject(new Error('offline'));
  await flush();
  assert.ok(find(render(), 'ul'));
  assert.equal(find(render(), Status).props.error, true);
  props.scopedVars = { bk_biz_id: 1, host: 2 };
  await vue.nextTick();
  assert.ok(find(render(), Skeleton));
  assert.equal(find(render(), 'ul'), undefined);
  scope.stop();
  requests[2].resolve([{ value: '9000', name: 'stale' }]);
  await flush();
  assert.equal(find(render(), 'ul'), undefined);
});
