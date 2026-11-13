const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

const root = path.resolve(__dirname, '../src/monitor-ui/chart-plugins');
const compile = source => ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const loadModule = (file, requireModule, window = {}) => {
  const moduleObject = { exports: {} };
  new Function('require', 'module', 'exports', 'window', compile(fs.readFileSync(file, 'utf8')))(
    requireModule, moduleObject, moduleObject.exports, window
  );
  return moduleObject.exports;
};
const variables = loadModule(path.join(root, 'utils/variable.ts'), () => ({ deepClone: structuredClone }));
const utilsFile = path.join(root, 'utils/utils.ts');
const utilsSource = ts.createSourceFile(utilsFile, fs.readFileSync(utilsFile, 'utf8'), ts.ScriptTarget.Latest, true);
const metricIdStatement = utilsSource.statements.find(statement =>
  ts.isVariableStatement(statement) && statement.declarationList.declarations.some(item => item.name.getText(utilsSource) === 'getMetricId')
);
const utils = {};
new Function('exports', compile(metricIdStatement.getText(utilsSource)))(utils);
const commonUtilsFile = path.resolve(root, '../../monitor-common/utils/utils.js');
const commonUtilsSource = ts.createSourceFile(commonUtilsFile, fs.readFileSync(commonUtilsFile, 'utf8'), ts.ScriptTarget.Latest, true);
const cloneStatement = commonUtilsSource.statements.find(statement =>
  ts.isVariableStatement(statement) && statement.declarationList.declarations.some(item => item.name.getText(commonUtilsSource) === 'deepClone')
);
const commonUtils = {};
new Function('exports', compile(cloneStatement.getText(commonUtilsSource)))(commonUtils);
const opened = [];
const menu = loadModule(path.join(root, 'utils/menu.ts'), id => {
  if (id === './utils') return utils;
  assert.equal(id, 'monitor-common/utils/alarm-center-router');
  return { openAlarmCenter: query => opened.push(query) };
}, { timezone: 'UTC' });

function method(file, name) {
  const source = ts.createSourceFile(file, fs.readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  let result;
  function visit(node) {
    if (ts.isMethodDeclaration(node) && node.name?.getText(source) === name) result = node.getText(source);
    ts.forEachChild(node, visit);
  }
  visit(source);
  assert.ok(result, name);
  return result;
}

const chartFile = path.join(root, 'plugins/time-series/time-series.tsx');
const chartMethods = ['handleMenuToolsSelect', 'queryPanelData'].map(name => method(chartFile, name)).join('\n');
const Chart = new Function('VariablesService', 'getPromqlUnitOverride', 'deepClone', 'handleRelateAlert', 'window',
  'handleTransformToTimestamp', 'reviewInterval', 'CancelToken', 'dayjs',
  compile(`class Chart { ${chartMethods} } return Chart;`))(
  variables.VariablesService, variables.getPromqlUnitOverride, commonUtils.deepClone, menu.handleRelateAlert,
  { i18n: { t: value => value } }, () => [100, 200], interval => interval, class CancelToken {},
  { tz: value => ({ unix: () => Number(value) }) }
);

function podQuery() {
  return {
    data_source_label: 'prometheus', data_type_label: 'time_series', interval: '$interval',
    promql: '$method by ($group_by) (container_memory_rss{namespace=~"^(${namespace:regex})$"} $time_shift)',
    pod_promql: '$method by ($group_by) (pod_memory_rss{namespace=~"^(${namespace:regex})$"} $time_shift)',
    related_metric_ids: ['bk_monitor..container_memory_rss', 'bk_monitor..kube_pod_container_resource_requests_memory_bytes'],
    metrics: [{ field: 'container_memory_rss', alias: 'A', method: '$method' }], functions: [],
  };
}

test('Pod memory alert link retains original metric IDs and does not freeze the chart query', async () => {
  const requests = [];
  const panelFile = path.join(root, 'typings/dashboard-panel.ts');
  const panelSource = ts.createSourceFile(panelFile, fs.readFileSync(panelFile, 'utf8'), ts.ScriptTarget.Latest, true);
  const dataQueryClass = panelSource.statements.find(statement => ts.isClassDeclaration(statement) && statement.name?.text === 'DataQuery');
  const panelModule = {};
  new Function('exports', compile(dataQueryClass.getText(panelSource)))(panelModule);
  const chart = Object.assign(new Chart(), {
    createRequestGuard: () => () => true, cancelTokens: [], isInViewPort: () => true,
    handleBeforeRequestLoadingChange() {}, unregisterObserver() {}, clearErrorMsg() {}, handleLoadingChange() {},
    handleErrorMsgChange(message) { assert.fail(message); }, downSampleRangeComputed: () => '',
    $route: { query: {} }, $emit() {},
    $api: { grafana: { graphUnifyQuery: async request => { requests.push(request); return { series: [] }; } } },
    panel: { options: {}, targets: [new panelModule.DataQuery({ api: 'grafana.graphUnifyQuery', data: { expression: 'A', query_configs: [podQuery()] } })] },
    timeRange: ['now-1h', 'now'], timeOffset: ['1h'],
    viewOptions: { method: 'sum', group_by: [], interval: 60, namespace: ['qa'], filters: { namespace: ['qa'] } },
    customScopedVars: {},
  });
  const original = structuredClone(chart.panel.targets);
  chart.handleMenuToolsSelect({ id: 'relate-alert' });
  assert.deepEqual(structuredClone(chart.panel.targets), original);
  assert.equal(opened.at(-1).queryString,
    '指标ID : bk_monitor..container_memory_rss OR 指标ID : bk_monitor..kube_pod_container_resource_requests_memory_bytes');
  assert.equal('promql' in opened.at(-1), false);

  chart.viewOptions = { method: 'avg', group_by: ['container_name'], interval: 60, filters: { namespace: ['other'] } };
  await chart.queryPanelData();
  assert.equal(requests.length, 2);
  assert.match(requests[0].query_configs[0].promql, /^avg by \(container_name\) \(container_memory_rss/);
  assert.ok(requests[0].query_configs[0].promql.includes('other'));
  assert.ok(requests[1].query_configs[0].promql.includes('offset 1h'));
});

test('Existing native and structured alert links retain their original behavior', () => {
  menu.handleRelateAlert({ targets: [{ data: { query_configs: [{ promql: 'sum(rate(test_total[1m]))' }] } }] }, ['1', '2']);
  assert.equal(opened.at(-1).promql, 'sum(rate(test_total[1m]))');
  menu.handleRelateAlert({ targets: [{ data: { query_configs: [{
    data_source_label: 'bk_monitor', data_type_label: 'time_series', table: '', metrics: [{ field: 'container_memory_rss' }],
  }] } }] }, ['1', '2']);
  assert.equal(opened.at(-1).queryString, '指标ID : bk_monitor..container_memory_rss');
});

test('Panel alert conversion also honors original metric IDs', () => {
  const code = `class Panel { ${method(path.join(root, 'typings/dashboard-panel.ts'), 'toRelateEvent')} } return Panel;`;
  const Panel = new Function('filterDictConvertedToWhere', 'getMetricId', compile(code))(value => value, utils.getMetricId);
  const target = {};
  const panel = Object.assign(new Panel(), { targets: [target], rawTargetQueryMap: new WeakMap() });
  panel.rawTargetQueryMap.set(target, { query_configs: [podQuery()] });
  assert.equal(panel.toRelateEvent().queryString,
    '指标ID : bk_monitor..container_memory_rss OR 指标ID : bk_monitor..kube_pod_container_resource_requests_memory_bytes');
});

test('Related PromQL is interpolated and preserves the existing last-target alert behavior', () => {
  const code = `class Panel { ${method(path.join(root, 'typings/dashboard-panel.ts'), 'toRelateEvent')} } return Panel;`;
  const Panel = new Function('filterDictConvertedToWhere', 'getMetricId', compile(code))(value => value, utils.getMetricId);
  const source = [
    { promql: '$method(sum(container_memory_rss))', related_promql: '$method(container_memory_rss $time_shift)' },
    { promql: '$method(sum(kube_pod_container_resource_limits))', related_promql: '$method(kube_pod_container_resource_limits)' },
    { promql: '$method(sum(kube_pod_container_resource_requests_memory_bytes))', related_promql: '$method(kube_pod_container_resource_requests_memory_bytes)' },
  ];
  const panel = Object.assign(new Panel(), { targets: source.map(() => ({})), rawTargetQueryMap: new WeakMap() });
  const service = new variables.VariablesService({ method: 'sum', time_shift: '1h' });
  source.forEach((query, index) => {
    panel.rawTargetQueryMap.set(panel.targets[index], { query_configs: [service.transformVariables(query)] });
  });
  assert.equal(panel.toRelateEvent().promql, 'sum(kube_pod_container_resource_requests_memory_bytes)');
  assert.equal(service.transformVariables(source[0]).related_promql, 'sum(container_memory_rss offset 1h)');
});
