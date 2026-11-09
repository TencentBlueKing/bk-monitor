const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const { parser } = require('@prometheus-io/lezer-promql');
const ts = require('typescript');

const root = path.resolve(__dirname, '../src');
const moduleObject = { exports: {} };
const variableCode = ts.transpileModule(
  fs.readFileSync(path.join(root, 'monitor-ui/chart-plugins/utils/variable.ts'), 'utf8'),
  { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }
).outputText;
new Function('require', 'module', 'exports', variableCode)(id => {
  assert.equal(id, 'monitor-common/utils/utils');
  return { deepClone: structuredClone };
}, moduleObject, moduleObject.exports);
const { variableRegex, VariablesService } = moduleObject.exports;

function parse(promql) {
  assert.equal(typeof promql, 'string');
  const tree = parser.parse(promql);
  const cursor = tree.cursor();
  do {
    assert.equal(cursor.type.isError, false, `Invalid PromQL at ${cursor.from}: ${promql}`);
  } while (cursor.next());
}

const template = `$method by ($group_by) (pod_memory_rss{namespace=~"^(\${namespace:regex})$",pod_name=~"^(\${pod_name:regex})$"} $time_shift)`;

test('Native PromQL interpolates grouping arrays and duration offsets while structured fields retain their types', () => {
  const service = new VariablesService({
    method: 'sum', group_by: ['namespace', 'pod_name'], namespace: ['qa', 'team.a'], pod_name: 'worker.a',
  });
  const source = {
    query_configs: [{
      promql: template,
      group_by: ['$group_by'],
      where: [{ key: 'namespace', value: ['$namespace'] }],
      functions: [{ id: 'time_shift', params: [{ id: 'n', value: '$time_shift' }] }],
    }],
  };
  const result = service.transformVariables(source, { time_shift: '1h' });
  const config = result.query_configs[0];
  assert.equal(config.promql, 'sum by (namespace,pod_name) (pod_memory_rss{namespace=~"^(qa|team\\\\.a)$",pod_name=~"^(worker\\\\.a)$"} offset 1h)');
  parse(config.promql);
  assert.deepEqual(config.group_by, ['namespace', 'pod_name']);
  assert.deepEqual(config.where, [{ key: 'namespace', value: ['qa', 'team.a'] }]);
  assert.equal(config.functions[0].params[0].value, '1h');
  assert.equal(source.query_configs[0].promql, template);
});

test('Existing scalar and already formatted native variables retain their values', () => {
  for (const time_shift of ['1h', 'offset 1h', ' offset 1h ']) {
    const service = new VariablesService({ method: 'max', group_by: 'namespace', time_shift, interval: '1m' });
    const result = service.transformVariables({
      promql: '$method by($group_by)(rate(container_cpu_usage_seconds_total[$interval] $time_shift))',
    });
    assert.equal(result.promql, 'max by(namespace)(rate(container_cpu_usage_seconds_total[1m] offset 1h))');
    parse(result.promql);
  }
});

test('Native grouping and time offset empty values remain valid PromQL', () => {
  for (const [group_by, time_shift] of [[[], ''], ['', ' '], [undefined, undefined], [null, null]]) {
    const service = new VariablesService({ method: 'avg', group_by, time_shift, namespace: [], pod_name: undefined });
    const { promql } = service.transformVariables({ promql: template });
    assert.equal(promql, 'avg by () (pod_memory_rss{namespace=~"^(.*)$",pod_name=~"^(.*)$"}  )');
    parse(promql);
  }
});

test('Regex formatting escapes each literal value and PromQL string characters without changing unformatted regex', () => {
  const names = ['worker.a', 'worker+"b', 'worker\\c', 'line\nbreak', '.*'];
  const service = new VariablesService({ pod_name: names, raw: 'worker.*' });
  const { promql } = service.transformVariables({ promql: 'pod_memory_rss{pod_name=~"^([[pod_name:regex]])$",raw=~"$raw"}' });
  parse(promql);
  const labelString = promql.slice(promql.indexOf('=~') + 2, promql.indexOf(',raw='));
  const regex = new RegExp(JSON.parse(labelString));
  for (const name of names) assert.equal(regex.test(name), true, name);
  for (const name of ['workerXa', 'other', 'anything']) assert.equal(regex.test(name), false, name);
  assert.ok(promql.includes('raw=~"worker.*"'));
});

test('Native interpolation preserves variable precedence and noTransform returns the original object', () => {
  const service = new VariablesService({ method: 'sum', group_by: ['namespace'], namespace: ['qa'], pod_name: 'worker-a' });
  const source = { promql: template, group_by: ['$group_by'], value: '$namespace' };
  const result = service.transformVariables(source, { method: 'max', namespace: ['other'], time_shift: '1d' });
  assert.equal(result.promql, 'sum by (namespace) (pod_memory_rss{namespace=~"^(qa)$",pod_name=~"^(worker-a)$"} offset 1d)');
  assert.deepEqual(result.value, ['qa']);
  assert.strictEqual(service.transformVariables(source, { time_shift: '1d' }, true), source);
});

const chartFile = path.join(root, 'monitor-ui/chart-plugins/plugins/time-series/time-series.tsx');
const chartSource = ts.createSourceFile(chartFile, fs.readFileSync(chartFile, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
const component = chartSource.statements.find(ts.isClassDeclaration);
const queryMethod = component.members.find(member => member.name?.getText(chartSource) === 'queryPanelData');
assert.ok(queryMethod);
const harnessCode = ts.transpileModule(`class Harness { ${queryMethod.getText(chartSource)} } return Harness;`, {
  compilerOptions: { target: ts.ScriptTarget.ES2022 },
}).outputText;
const Harness = new Function('VariablesService', 'variableRegex', 'window', 'handleTransformToTimestamp', 'reviewInterval', 'CancelToken', harnessCode)(
  VariablesService,
  variableRegex,
  { i18n: { t: value => value } },
  () => [100, 200],
  () => '1m',
  class CancelToken {}
);

function graphHarness(original, method = 'sum') {
  const requests = [];
  const graph = Object.assign(new Harness(), {
    createRequestGuard: () => () => true,
    cancelTokens: [],
    isInViewPort: () => true,
    handleBeforeRequestLoadingChange() {},
    unregisterObserver() {},
    clearErrorMsg() {},
    handleLoadingChange() {},
    handleErrorMsgChange(message) { assert.fail(message); },
    downSampleRangeComputed: () => '1m',
    $route: { query: {} },
    $emit() {},
    $api: { grafana: { graphUnifyQuery: async request => { requests.push(request); return { series: [] }; } } },
    panel: { options: {}, targets: [{ apiModule: 'grafana', apiFunc: 'graphUnifyQuery', data: original }] },
    timeRange: ['now-1h', 'now'],
    timeOffset: ['1h'],
    viewOptions: {
      method, group_by: ['namespace', 'pod_name'], interval: '1m',
      filters: { namespace: ['qa', 'team.a'], pod_name: ['worker-a'] },
    },
    customScopedVars: {},
  });
  return { graph, requests };
}

test('Actual legacy graph requests interpolate native PromQL for current and time-comparison queries', async () => {
  const original = {
    expression: 'A',
    query_configs: [{
      data_source_label: 'prometheus', data_type_label: 'time_series', alias: 'A', interval: '$interval',
      promql: template,
      where: [{ key: 'namespace', value: ['$namespace'] }],
      functions: [{ id: 'time_shift', params: [{ id: 'n', value: '$time_shift' }] }],
    }],
  };
  const { graph, requests } = graphHarness(original);
  await graph.queryPanelData();
  assert.notEqual(graph.emptyText, '出错了');
  assert.equal(requests.length, 2);
  assert.equal(requests[0].query_configs[0].promql.includes('offset'), false);
  assert.equal(requests[1].query_configs[0].promql.endsWith('offset 1h)'), true);
  assert.equal(requests[1].query_configs[0].functions[0].params[0].value, '1h');
  assert.deepEqual(requests[0].query_configs[0].where[0].value, ['qa', 'team.a']);
  for (const request of requests) {
    parse(request.query_configs[0].promql);
    assert.equal(request.query_configs[0].interval, '1m');
    assert.deepEqual([request.start_time, request.end_time], [100, 200]);
  }
  assert.equal(original.query_configs[0].promql, template);
});

test('Legacy native COUNT requests use no unit while other methods and structured targets retain bytes', async () => {
  for (const method of ['count', 'COUNT', 'sum', 'avg']) {
    for (const native of [true, false]) {
      const original = {
        expression: 'A', unit: 'bytes',
        query_configs: [native ? { promql: template } : { metrics: [{ field: 'container_memory_rss', method: '$method' }] }],
      };
      const { graph, requests } = graphHarness(original, method);
      await graph.queryPanelData();
      assert.notEqual(graph.emptyText, '出错了');
      assert.equal(requests.length, 2);
      for (const request of requests) {
        assert.equal(request.unit, native && method.toLowerCase() === 'count' ? 'none' : 'bytes');
        if (native) parse(request.query_configs[0].promql);
        else assert.equal(request.query_configs[0].metrics[0].method, method);
      }
      assert.equal(original.unit, 'bytes');
    }
  }
});

test('Fixed native queries retain bytes under global COUNT when they do not consume the method variable', async () => {
  for (const method of ['count', 'COUNT']) {
    for (const promql of [
      'sum(container_memory_rss{namespace="qa"})',
      'container_memory_rss{namespace="qa"} $time_shift',
      'container_memory_rss{method="$method_suffix"}',
    ]) {
      const original = { expression: 'A', unit: 'bytes', query_configs: [{ promql }] };
      const { graph, requests } = graphHarness(original, method);
      await graph.queryPanelData();
      assert.notEqual(graph.emptyText, '出错了');
      assert.equal(requests.length, 2);
      for (const request of requests) {
        assert.equal(request.unit, 'bytes');
        parse(request.query_configs[0].promql);
      }
    }
  }
});

test('COUNT method detection follows every existing variable syntax', async () => {
  for (const variable of ['$method', '${method}', '[[method]]']) {
    const original = {
      expression: 'A', unit: 'bytes', query_configs: [{ promql: `${variable}(pod_memory_rss{namespace="qa"})` }],
    };
    const { graph, requests } = graphHarness(original, 'count');
    await graph.queryPanelData();
    assert.notEqual(graph.emptyText, '出错了');
    assert.equal(requests.length, 2);
    for (const request of requests) {
      assert.equal(request.unit, 'none');
      assert.equal(request.query_configs[0].promql, 'count(pod_memory_rss{namespace="qa"})');
    }
  }
});
