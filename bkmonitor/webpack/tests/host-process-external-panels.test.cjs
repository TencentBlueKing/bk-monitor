const assert = require('node:assert/strict');
const Module = require('node:module');
const path = require('node:path');
const test = require('node:test');

let vue;
try {
  vue = require('../src/trace/node_modules/vue');
} catch {
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

class PanelModelStub {
  constructor(model) {
    Object.assign(this, model);
  }
}

const ChartLazyStub = { name: 'ChartLazyStub' };
const ExternalPanelCardStub = { name: 'ExternalPanelCardStub' };
const MonitorCrossDragStub = { name: 'MonitorCrossDragStub' };
const TimeSeriesCardStub = { name: 'TimeSeriesCardStub' };

const originalLoad = Module._load;
Module._load = function load(request, parent, isMain) {
  const filename = parent?.filename || '';
  if (
    request === 'monitor-pc/pages/query-template/variables/template/template-srv' &&
    filename.endsWith('/resolve.ts')
  ) {
    return { getTemplateSrv: () => ({ replace: value => value }) };
  }
  if (request === 'monitor-ui/chart-plugins/typings' && filename.endsWith('/resolve.ts')) {
    return { PanelModel: PanelModelStub };
  }
  if (filename.endsWith('/dashboard-row.tsx')) {
    if (request === './chart-lazy') return { default: ChartLazyStub };
    if (request === './external-panel-card') return { default: ExternalPanelCardStub };
    if (request === './time-series-card') return { default: TimeSeriesCardStub };
    if (request === '@/components/monitor-cross-drag/monitor-cross-drag') return { default: MonitorCrossDragStub };
  }
  return originalLoad(request, parent, isMain);
};

const { resolveVariables } = require('../src/trace/pages/host/components/dashbords/variables/resolve.ts');
const DashboardRow = require('../src/trace/pages/host/components/dashbords/components/dashboard-row.tsx').default;
Module._load = originalLoad;

const target = (api, dataType) => ({
  api,
  data: { bk_host_id: '$bk_host_id', display_name: '$display_name' },
  data_type: dataType,
  datasource: dataType,
});

const panel = (id, type, api) => ({
  id,
  subTitle: '',
  targets: [target(api, type)],
  title: id,
  type,
});

const collectVNodes = vnode => {
  if (!vnode) return [];
  if (Array.isArray(vnode)) return vnode.flatMap(collectVNodes);
  if (typeof vnode === 'function') return collectVNodes(vnode());
  if (typeof vnode !== 'object') return [];
  const result = [vnode];
  if (Array.isArray(vnode.children)) result.push(...vnode.children.flatMap(collectVNodes));
  else if (vnode.children && typeof vnode.children === 'object') {
    result.push(...Object.values(vnode.children).flatMap(collectVNodes));
  }
  return result;
};

test('外部面板 target 替换进程作用域变量', () => {
  const resolved = resolveVariables(target('scene_view.getHostProcessUptime', 'text-unit').data, {
    bk_host_id: 92749,
    display_name: 'kubelet',
  });

  assert.deepEqual(resolved, { bk_host_id: 92749, display_name: 'kubelet' });
});

test('仪表盘按面板类型选择外部插件而非时序图', () => {
  const row = {
    id: 'process',
    title: 'process',
    panels: [
      panel('port_status', 'port-status', 'scene_view.getHostProcessPortStatus'),
      panel('run_time', 'text-unit', 'scene_view.getHostProcessUptime'),
      panel('uptime', 'graph', 'grafana.graphUnifyQuery'),
    ],
  };
  const vnode = DashboardRow.render.call({
    columns: 3,
    customOptions: {},
    dashboardId: 'process-dashboard',
    expanded: true,
    gridStyle: {},
    handleCrossResize: () => {},
    height: 240,
    maxHeight: 600,
    minHeight: 240,
    row,
    scopedVars: { bk_host_id: 92749, display_name: 'kubelet' },
    toggle: () => {},
  });
  const nodes = collectVNodes(vnode);

  assert.equal(nodes.filter(node => node.type === ExternalPanelCardStub).length, 2);
  assert.equal(nodes.filter(node => node.type === TimeSeriesCardStub).length, 1);
  const externalNodes = nodes.filter(node => node.type === ExternalPanelCardStub);
  assert.deepEqual(
    externalNodes.map(node => node.props.panel.type),
    ['port-status', 'text-unit']
  );
  assert.deepEqual(externalNodes[0].props.scopedVars, { bk_host_id: 92749, display_name: 'kubelet' });
});

const timeRange = vue.shallowRef([100, 200]);
const refreshImmediate = vue.shallowRef('');
global.window = { cc_biz_id: 2 };
const apiRequests = [];
const deferred = () => {
  let reject;
  let resolve;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
};
const apiStub = {
  scene_view: {
    getHostProcessPortStatus: params => {
      const request = deferred();
      apiRequests.push({ api: 'port', params, ...request });
      return request.promise;
    },
    getHostProcessUptime: params => {
      const request = deferred();
      apiRequests.push({ api: 'uptime', params, ...request });
      return request.promise;
    },
  },
};

Module._load = function loadExternalCard(request, parent, isMain) {
  const filename = parent?.filename || '';
  if (request === 'vue' && filename.endsWith('/external-panel-card.tsx')) {
    return {
      ...vue,
      getCurrentInstance: () => ({ appContext: { config: { globalProperties: { $api: apiStub } } } }),
      inject: (key, defaultValue) => ({ refreshImmediate, timeRange })[key] ?? defaultValue,
    };
  }
  if (request === 'vue-i18n' && filename.endsWith('/external-panel-card.tsx')) {
    return { useI18n: () => ({ t: value => value }) };
  }
  if (request === '@/components/time-range/utils' && filename.endsWith('/external-panel-card.tsx')) {
    return { handleTransformToTimestamp: value => value };
  }
  if (request === '@/plugins/components/chart-title' && filename.endsWith('/external-panel-card.tsx')) {
    return { default: { name: 'ChartTitleStub' } };
  }
  if (request === 'monitor-ui/monitor-echarts/valueFormats' && filename.endsWith('/external-panel-card.tsx')) {
    return { getValueFormat: unit => value => ({ suffix: unit, text: String(value) }) };
  }
  return originalLoad(request, parent, isMain);
};
const ExternalPanelCard =
  require('../src/trace/pages/host/components/dashbords/components/external-panel-card.tsx').default;
Module._load = originalLoad;

const collectText = vnode => {
  if (vnode == null || typeof vnode === 'boolean') return '';
  if (typeof vnode === 'string' || typeof vnode === 'number') return String(vnode);
  if (Array.isArray(vnode)) return vnode.map(collectText).join('');
  return collectText(vnode.children);
};
const flushPromises = async () => {
  await vue.nextTick();
  await new Promise(resolve => setImmediate(resolve));
};

test('text-unit 按局部时间和进程作用域请求并渲染对象响应', async t => {
  assert.equal(typeof ExternalPanelCard.setup, 'function');
  apiRequests.length = 0;
  timeRange.value = [100, 200];
  const props = vue.reactive({
    panel: panel('run_time', 'text-unit', 'scene_view.getHostProcessUptime'),
    scopedVars: { bk_host_id: 92749, display_name: 'kubelet' },
  });
  const scope = vue.effectScope();
  t.after(() => scope.stop());
  const render = scope.run(() => ExternalPanelCard.setup(props));

  assert.deepEqual(apiRequests[0].params, {
    bk_biz_id: 2,
    bk_host_id: 92749,
    display_name: 'kubelet',
    end_time: 200,
    start_time: 100,
  });
  apiRequests[0].resolve({ unit: 's', value: 3600 });
  await flushPromises();
  assert.match(collectText(render()), /3600s/);
});

test('text-unit 区分后端缺失值与真实零值', async t => {
  apiRequests.length = 0;
  timeRange.value = [100, 200];
  const props = vue.reactive({
    panel: panel('run_time', 'text-unit', 'scene_view.getHostProcessUptime'),
    scopedVars: { bk_host_id: 92749, display_name: 'kubelet' },
  });
  const scope = vue.effectScope();
  t.after(() => scope.stop());
  const render = scope.run(() => ExternalPanelCard.setup(props));

  apiRequests[0].resolve({ unit: 's', value: '' });
  await flushPromises();
  assert.match(collectText(render()), /暂无数据/);
  assert.doesNotMatch(collectText(render()), /0s/);

  refreshImmediate.value = 'refresh-zero';
  await flushPromises();
  apiRequests[1].resolve({ unit: 's', value: 0 });
  await flushPromises();
  assert.match(collectText(render()), /0s/);
});

test('port-status 渲染列表响应且时间或进程变化时旧响应不能覆盖', async t => {
  apiRequests.length = 0;
  timeRange.value = [100, 200];
  refreshImmediate.value = '';
  const props = vue.reactive({
    panel: panel('port_status', 'port-status', 'scene_view.getHostProcessPortStatus'),
    scopedVars: { bk_host_id: 1, display_name: 'mysql' },
  });
  const scope = vue.effectScope();
  t.after(() => scope.stop());
  const render = scope.run(() => ExternalPanelCard.setup(props));

  timeRange.value = [300, 400];
  await flushPromises();
  props.scopedVars = { bk_host_id: 2, display_name: 'mysqld' };
  await flushPromises();
  assert.equal(apiRequests.length, 3);
  assert.equal(apiRequests[2].params.bk_host_id, 2);
  assert.equal(apiRequests[2].params.end_time, 400);

  apiRequests[2].resolve([{ name: '正常', statusColor: '#2dcb56', value: '3306' }]);
  await flushPromises();
  apiRequests[0].resolve([{ name: '异常', statusColor: '#ea3636', value: 'TCP 1' }]);
  apiRequests[1].resolve([{ name: '异常', statusColor: '#ea3636', value: 'TCP 2' }]);
  await flushPromises();
  assert.match(collectText(render()), /3306正常/);
  assert.doesNotMatch(collectText(render()), /端口[12]/);

  refreshImmediate.value = 'refresh-1';
  await flushPromises();
  assert.equal(apiRequests.length, 4);
});
