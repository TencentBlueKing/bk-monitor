const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const root = path.join(__dirname, '../../src/trace/pages/host');
const flush = () => new Promise(resolve => setImmediate(resolve));

function loadHostModule(file, dependencies = {}, globals = {}) {
  const code = ts.transpileModule(fs.readFileSync(path.join(root, file), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const module = { exports: {} };
  new Function('require', 'module', 'exports', ...Object.keys(globals), code)(
    id => {
      if (id in dependencies) return dependencies[id];
      throw new Error(`Unexpected dependency: ${id}`);
    },
    module,
    module.exports,
    ...Object.values(globals)
  );
  return module.exports;
}

function serviceHarness(owner = {}, context = {}) {
  const window = { cc_biz_id: 1, user_name: 'test-user', site_url: '/', rawWindow: owner, ...context };
  const calls = [];
  const request = name => (params, config) =>
    new Promise((resolve, reject) => {
      calls.push({ name, params, config, resolve, reject });
    });
  const helper = loadHostModule(
    'services/host-request.ts',
    {
      'monitor-common/utils': { parseBizId: value => (value == null || value === '' ? NaN : Number(value)) },
    },
    { window }
  );
  const performance = Object.fromEntries(
    [
      'searchHostInfo',
      'searchHostMetric',
      'getHostViewsPanels',
      'getHostMetricGroupPanelOrder',
      'getProcessViewsPanels',
      'getProcessMetricGroupPanelOrder',
    ].map(name => [name, request(name)])
  );
  const sceneView = {
    getHostOrTopoNodeDetail: request('getHostOrTopoNodeDetail'),
    getHostProcessList: request('getHostProcessList'),
    getHostProcessUptime: request('getHostProcessUptime'),
    getStrategyAndEventCount: request('getStrategyAndEventCount'),
  };
  const dependencies = {
    './host-request': helper,
    'monitor-api/base': { request: () => request('searchHostMetricStats') },
    'monitor-api/modules/performance': performance,
    'monitor-api/modules/commons': { getTopoTree: request('getTopoTree') },
    'monitor-api/modules/scene_view': sceneView,
  };
  const api = Object.assign(
    {},
    ...['host', 'graph', 'process', 'global'].map(name =>
      loadHostModule(`services/${name}-service.ts`, dependencies, { window })
    )
  );
  return { api, calls, window, owner, sceneView, requestHost: helper.requestHost };
}

module.exports = { loadHostModule, serviceHarness, flush };
