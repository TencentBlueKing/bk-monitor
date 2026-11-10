const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const { parser } = require('@prometheus-io/lezer-promql');
const ts = require('typescript');
const compiler = require('vue/compiler-sfc');
const Vue = require('vue');

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
const { getPromqlUnitOverride, VariablesService } = moduleObject.exports;

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
const menuMethod = component.members.find(member => member.name?.getText(chartSource) === 'handleMenuToolsSelect');
assert.ok(queryMethod);
assert.ok(menuMethod);
const harnessCode = ts.transpileModule(`class Harness { ${queryMethod.getText(chartSource)} ${menuMethod.getText(chartSource)} } return Harness;`, {
  compilerOptions: { target: ts.ScriptTarget.ES2022 },
}).outputText;
const Harness = new Function('VariablesService', 'getPromqlUnitOverride', 'window', 'handleTransformToTimestamp', 'reviewInterval', 'CancelToken', 'dayjs', harnessCode)(
  VariablesService,
  getPromqlUnitOverride,
  { i18n: { t: value => value } },
  () => [100, 200],
  interval => interval,
  class CancelToken {},
  { tz: value => ({ unix: () => Number(value) }) }
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

const childTemplate = template.replace('pod_memory_rss', 'container_memory_rss');
function podConfig() {
  return {
    promql: childTemplate,
    pod_promql: template,
    overview_promql: '$method by ($group_by)(container_memory_rss $time_shift)',
    overview_pod_promql: '$method by ($group_by)(pod_memory_rss $time_shift)',
    metrics: [{ field: 'container_memory_rss', method: '$method', alias: 'A' }],
    functions: [{ id: 'time_shift', params: [{ id: 'n', value: '$time_shift' }] }],
  };
}

test('Pod variants select before interpolation for every consumer input shape and keep metric metadata', () => {
  const shapes = [
    { wrap: qc => qc, read: value => value },
    { wrap: qc => [qc], read: value => value[0] },
    { wrap: qc => ({ query_configs: [qc] }), read: value => value.query_configs[0] },
    { wrap: qc => ({ targets: [{ data: { query_configs: [qc] } }] }), read: value => value.targets[0].data.query_configs[0] },
  ];
  for (const group_by of [[], ['namespace'], ['container_name'], ['container'], ['image'], ['namespace', 'image'], ['container_name', 'pod_name']]) {
    const child = group_by.some(group => ['container_name', 'container', 'image'].includes(group));
    const service = new VariablesService({ method: 'sum', group_by, namespace: ['qa'], pod_name: 'worker-a' });
    for (const { wrap, read } of shapes) {
      const source = wrap(podConfig());
      const before = structuredClone(source);
      const result = read(service.transformVariables(source));
      parse(result.promql);
      assert.ok(result.promql.includes(child ? 'container_memory_rss{' : 'pod_memory_rss{'));
      assert.deepEqual(result.metrics, [{ field: 'container_memory_rss', method: 'sum', alias: 'A' }]);
      for (const field of ['pod_promql', 'overview_promql', 'overview_pod_promql']) assert.equal(field in result, false);
      assert.deepEqual(source, before);
    }
  }
});

test('Fixed variant strings are resolved in nested panels without changing existing fixed or noTransform contracts', () => {
  const source = { targets: [{ data: { query_configs: [{ promql: 'sum(child_metric)', pod_promql: 'sum(parent_metric)' }] } }] };
  const parent = new VariablesService({ group_by: [] }).transformVariables(source);
  const child = new VariablesService({ group_by: ['container'] }).transformVariables(source);
  assert.deepEqual(parent.targets[0].data.query_configs[0], { promql: 'sum(parent_metric)' });
  assert.deepEqual(child.targets[0].data.query_configs[0], { promql: 'sum(child_metric)' });
  const service = new VariablesService({ group_by: [] });
  for (const input of [source, { promql: 'sum(fixed_metric)', overview_promql: 'sum(existing_overview)' }, { values: ['fixed', undefined, null] }]) {
    const before = structuredClone(input);
    assert.strictEqual(service.transformVariables(input, {}, true), input);
    assert.deepEqual(input, before);
  }
  assert.deepEqual(service.transformVariables({ promql: 'sum(fixed_metric)', overview_promql: 'sum(existing_overview)' }), {
    promql: 'sum(fixed_metric)', overview_promql: 'sum(existing_overview)',
  });
});

test('Variant selection follows existing index precedence and scoped fallback', () => {
  const config = podConfig();
  for (const [index, scoped, expected] of [
    [{ group_by: ['container_name'] }, { group_by: ['namespace'] }, 'container_memory_rss'],
    [{ group_by: ['namespace'] }, { group_by: ['container_name'] }, 'pod_memory_rss'],
    [{}, { group_by: ['image'] }, 'container_memory_rss'],
    [{ group_by: [] }, { group_by: ['image'] }, 'pod_memory_rss'],
    [{ group_by: 'namespace,container' }, {}, 'container_memory_rss'],
  ]) {
    const result = new VariablesService({ method: 'sum', ...index }).transformVariables(config, scoped);
    assert.ok(result.promql.includes(`${expected}{`));
  }
});

test('A service without an index leaves fixed native queries intact and selects the fixed Pod variant', () => {
  const service = new VariablesService();
  assert.deepEqual(service.transformVariables({ promql: 'sum(fixed_metric)' }), { promql: 'sum(fixed_metric)' });
  assert.deepEqual(service.transformVariables({ promql: 'sum(child_metric)', pod_promql: 'sum(parent_metric)' }), {
    promql: 'sum(parent_metric)',
  });
});

test('Actual fullscreen menu keeps native method and time shift for current and comparison requests', async () => {
  for (const group_by of [[], ['container_name'], ['container'], ['image'], ['namespace', 'container_name']]) {
    for (const method of ['sum', 'COUNT']) {
      const original = { expression: 'A', unit: 'bytes', query_configs: [podConfig()] };
      const { graph } = graphHarness(original, method);
      graph.viewOptions.group_by = group_by;
      const source = structuredClone(graph.panel);
      let fullscreenPanel;
      graph.handleFullScreen = panel => { fullscreenPanel = panel; };
      graph.handleMenuToolsSelect({ id: 'fullscreen' });
      assert.ok(fullscreenPanel);
      const query = fullscreenPanel.targets[0].data.query_configs[0];
      assert.ok(query.promql.includes('$method'));
      assert.ok(query.promql.includes('$time_shift'));
      const child = group_by.some(group => ['container_name', 'container', 'image'].includes(group));
      assert.ok(query.promql.includes(child ? 'container_memory_rss{' : 'pod_memory_rss{'));
      assert.equal('pod_promql' in query, false);
      assert.equal('overview_promql' in query, false);
      assert.deepEqual(query.functions, original.query_configs[0].functions);
      const { graph: fullGraph, requests } = graphHarness(fullscreenPanel.targets[0].data, method);
      fullGraph.viewOptions = graph.viewOptions;
      await fullGraph.queryPanelData();
      assert.notEqual(fullGraph.emptyText, '出错了');
      assert.equal(requests.length, 2);
      assert.equal(requests[0].query_configs[0].promql.includes('offset'), false);
      assert.ok(requests[1].query_configs[0].promql.endsWith('offset 1h)'));
      for (const request of requests) {
        parse(request.query_configs[0].promql);
        assert.equal(request.unit, method === 'COUNT' ? 'none' : 'bytes');
      }
      assert.deepEqual(graph.panel, source);
    }
  }
});

test('Fullscreen preserves fixed native COUNT units and the structured query contract', async () => {
  for (const query of [
    { promql: 'count(container_memory_rss)', functions: [] },
    { metrics: [{ field: 'container_memory_rss', method: '$method' }], functions: [{ id: 'time_shift', params: [{ id: 'n', value: '$time_shift' }] }] },
  ]) {
    const { graph } = graphHarness({ expression: 'A', unit: 'bytes', query_configs: [query] }, 'COUNT');
    let fullscreenPanel;
    graph.handleFullScreen = panel => { fullscreenPanel = panel; };
    graph.handleMenuToolsSelect({ id: 'fullscreen' });
    const { graph: fullGraph, requests } = graphHarness(fullscreenPanel.targets[0].data, 'COUNT');
    await fullGraph.queryPanelData();
    assert.equal(requests.length, 2);
    for (const request of requests) {
      assert.equal(request.unit, 'bytes');
      if (query.promql) assert.equal(request.query_configs[0].promql, query.promql);
      else assert.equal(request.query_configs[0].metrics[0].method, 'COUNT');
    }
    if (!query.promql) assert.equal(requests[1].query_configs[0].functions[0].params[0].value, '1h');
  }
});

function loadMethods(filename, names, dependencies = {}, content) {
  const source = ts.createSourceFile(filename, content ?? fs.readFileSync(filename, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const klass = source.statements.find(ts.isClassDeclaration);
  const members = klass.members.filter(member => names.includes(member.name?.getText(source)));
  assert.equal(members.length, names.length);
  const printer = ts.createPrinter();
  const code = ts.transpileModule(`class Subject { ${members.map(member => printer.printNode(
    ts.EmitHint.Unspecified,
    ts.factory.replaceModifiers(member, member.modifiers?.filter(modifier => !ts.isDecorator(modifier))),
    source
  )).join('\n')} } return Subject;`, {
    compilerOptions: { target: ts.ScriptTarget.ES2022 },
  }).outputText;
  return new Function(...Object.keys(dependencies), code)(...Object.values(dependencies));
}

const detailUtilsFile = path.join(root, 'monitor-pc/pages/view-detail/utils.ts');
const detailUtilsSource = ts.createSourceFile(detailUtilsFile, fs.readFileSync(detailUtilsFile, 'utf8'), ts.ScriptTarget.Latest, true);
const stepNormalizer = detailUtilsSource.statements.find(statement => ts.isVariableStatement(statement) &&
  statement.declarationList.declarations.some(declaration => declaration.name.getText(detailUtilsSource) === 'normalizePromqlStep'));
assert.ok(stepNormalizer);
const stepExports = {};
new Function('exports', ts.transpileModule(stepNormalizer.getText(detailUtilsSource), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText)(stepExports);
const { normalizePromqlStep } = stepExports;

const Detail = loadMethods(path.join(root, 'monitor-pc/pages/view-detail/view-detail-new.tsx'), [
  'handleQueryChange', 'handleSetPanelParams', 'handleTimeRangeChange', 'handleTimeChange', 'handleImmediateRefresh',
], { random: () => 'chart-refresh', normalizePromqlStep });
const editorFile = path.join(root, 'monitor-pc/pages/view-detail/query-criteria-item.vue');
const editorSource = compiler.parse({ source: fs.readFileSync(editorFile, 'utf8'), filename: editorFile });
assert.deepEqual(editorSource.errors, []);
const Editor = loadMethods(editorFile, [
  'queryConfigChange', 'handlePromqlDataCodeChange', 'handlePromqlDataCodeBlur', 'handleSourceStepChange', 'handleSourceStepBlur',
], { deepClone: structuredClone, normalizePromqlStep }, editorSource.script.content);

const editorTemplate = editorSource.template.content.trim();
const templateResult = compiler.compileTemplate({
  source: editorTemplate, filename: editorFile, compilerOptions: { outputSourceRange: true },
});
assert.deepEqual(templateResult.errors, []);
function findStepInput(node, seen = new Set()) {
  if (!node || seen.has(node)) return undefined;
  seen.add(node);
  if (node.tag === 'bk-input' && node.attrsMap.class === 'step-input') return node;
  for (const child of [...(node.children || []), ...(node.ifConditions || []).map(item => item.block)]) {
    const found = findStepInput(child, seen);
    if (found) return found;
  }
}
const stepNode = findStepInput(templateResult.ast);
assert.ok(stepNode);
const stepTemplate = compiler.compileTemplate({
  source: editorTemplate.slice(stepNode.start, stepNode.end), filename: editorFile,
});
assert.deepEqual(stepTemplate.errors, []);
const stepRender = new Function(`${stepTemplate.code}\nreturn { render, staticRenderFns };`)();

function stepInput(editor) {
  return editor._render().componentOptions;
}

function detailEditor(panel) {
  const detail = Object.assign(new Detail(), {
    panel: structuredClone(panel), queryconfig: structuredClone(panel.targets),
    compare: { value: [] }, timeRange: ['now-1h', 'now'], timeOffset: ['1h'], chartKey: 'initial',
  });
  const messages = [];
  const emitted = [];
  const editor = new Vue({
    ...stepRender,
    components: { 'bk-input': { props: ['value'], render: () => null } },
    data: () => ({ groupIndex: 0, queryConfig: detail.queryconfig[0], queryConfigItem: {}, queryConfigdata: null }),
    methods: Object.fromEntries(Object.getOwnPropertyNames(Editor.prototype)
      .filter(name => name !== 'constructor').map(name => [name, Editor.prototype[name]])),
    watch: { queryConfig: { deep: true, immediate: true, handler: Editor.prototype.queryConfigChange } },
  });
  editor.$t = value => value;
  editor.$bkMessage = message => messages.push(message);
  editor.$on('query-change', (...args) => { emitted.push(args); detail.handleQueryChange(...args); });
  return { detail, editor, messages, emitted };
}

test('Actual native editor blur and Step update the panel used by current and comparison requests', async () => {
  const original = { expression: 'A', unit: 'bytes', query_configs: [{ ...podConfig(), data_source_label: 'prometheus', interval: 60 }] };
  const { graph } = graphHarness(original);
  let fullscreenPanel;
  graph.handleFullScreen = panel => { fullscreenPanel = panel; };
  graph.handleMenuToolsSelect({ id: 'fullscreen' });
  const before = structuredClone(fullscreenPanel);
  const { detail, editor } = detailEditor(fullscreenPanel);
  const changed = '$method by(namespace,pod_name)(container_memory_usage_bytes{namespace="qa"} $time_shift)';
  editor.handlePromqlDataCodeChange(changed);
  editor.handlePromqlDataCodeBlur();
  editor.handleSourceStepChange('30');
  editor.handleSourceStepBlur();
  assert.equal(detail.panel.targets[0].data.query_configs[0].promql, changed);
  assert.equal(detail.panel.targets[0].data.query_configs[0].interval, '30');
  assert.equal(detail.panel.targets[0].data.query_configs[0].agg_interval, '30');
  assert.equal('pod_promql' in detail.panel.targets[0].data.query_configs[0], false);
  const { graph: editedGraph, requests } = graphHarness(detail.panel.targets[0].data);
  await editedGraph.queryPanelData();
  assert.equal(requests.length, 2);
  assert.equal(requests[0].query_configs[0].promql, 'sum by(namespace,pod_name)(container_memory_usage_bytes{namespace="qa"}  )');
  assert.equal(requests[1].query_configs[0].promql, 'sum by(namespace,pod_name)(container_memory_usage_bytes{namespace="qa"} offset 1h)');
  for (const request of requests) {
    assert.equal(request.query_configs[0].interval, '30');
    parse(request.query_configs[0].promql);
  }
  assert.deepEqual(fullscreenPanel, before);
});

test('Native fixed edits stay fixed and keep their unit when the surrounding method is COUNT', async () => {
  const { graph } = graphHarness({ expression: 'A', unit: 'bytes', query_configs: [{
    data_source_label: 'prometheus', promql: 'count(container_memory_rss)', interval: 60, functions: [],
  }] }, 'COUNT');
  let fullscreenPanel;
  graph.handleFullScreen = panel => { fullscreenPanel = panel; };
  graph.handleMenuToolsSelect({ id: 'fullscreen' });
  const { detail, editor } = detailEditor(fullscreenPanel);
  editor.handlePromqlDataCodeChange('sum(container_memory_rss)');
  editor.handlePromqlDataCodeBlur();
  editor.handleSourceStepChange('120');
  editor.handleSourceStepBlur();
  const { graph: editedGraph, requests } = graphHarness(detail.panel.targets[0].data, 'COUNT');
  await editedGraph.queryPanelData();
  assert.equal(requests.length, 2);
  for (const request of requests) {
    assert.equal(request.query_configs[0].promql, 'sum(container_memory_rss)');
    assert.equal(request.query_configs[0].interval, '120');
    assert.equal(request.unit, 'bytes');
  }
});

test('Detail structured method and interval edits retain the existing query configuration contract', async () => {
  const { detail } = detailEditor({ targets: [{ data: { expression: 'A', query_configs: [{
    data_source_label: 'bk_monitor', metrics: [{ field: 'container_memory_rss', method: 'sum' }], interval: 60,
  }] } }] });
  detail.handleQueryChange('avg', 'method', 0);
  detail.handleQueryChange(90, 'interval', 0);
  detail.handleQueryChange('120', 'step', 0);
  const { graph, requests } = graphHarness(detail.panel.targets[0].data);
  await graph.queryPanelData();
  assert.equal(requests.length, 2);
  for (const request of requests) {
    assert.equal(request.query_configs[0].metrics[0].method, 'avg');
    assert.equal(request.query_configs[0].interval, 90);
    assert.equal('promql' in request.query_configs[0], false);
  }
  assert.equal(requests[1].query_configs[0].functions[0].params[0].value, '1h');
});

test('Native Step blur keeps the existing interval for untouched, empty and invalid input', async () => {
  for (const interval of [60, '$interval', 'auto']) {
    for (const value of [undefined, null, '', ' ', 'invalid', '30.5', '1e2', '30s', '-1', '0', 0, NaN, Infinity]) {
      const original = { expression: 'A', unit: 'bytes', query_configs: [{
        ...podConfig(), data_source_label: 'prometheus', interval,
      }] };
      const { detail, editor } = detailEditor({ targets: [{ data: original }] });
      const before = structuredClone(detail.panel);
      if (value !== undefined) editor.handleSourceStepChange(value);
      editor.handleSourceStepBlur();
      assert.deepEqual(detail.panel, before, `Step ${String(value)} changed interval ${interval}`);
      assert.equal(detail.queryconfig[0].data.query_configs[0].interval, interval);
      const { graph, requests } = graphHarness(detail.panel.targets[0].data);
      graph.viewOptions.interval = 60;
      await graph.queryPanelData();
      assert.equal(requests.length, 2);
      for (const request of requests) {
        const serialized = JSON.parse(JSON.stringify(request));
        assert.equal(serialized.query_configs[0].interval, interval === '$interval' ? '60' : interval);
        parse(serialized.query_configs[0].promql);
      }
      assert.ok(requests[1].query_configs[0].promql.includes('offset 1h'));
    }
  }
});

test('Native Step values accept auto and positive integer seconds before current and comparison requests', async () => {
  for (const [value, expected] of [[' 30 ', '30'], ['030', '030'], [90, '90'], ['auto', 'auto']]) {
    const { detail, editor } = detailEditor({ targets: [{ data: {
      expression: 'A', unit: 'bytes', query_configs: [{ ...podConfig(), data_source_label: 'prometheus', interval: 60 }],
    } }] });
    editor.handleSourceStepChange(value);
    editor.handleSourceStepBlur();
    assert.equal(detail.panel.targets[0].data.query_configs[0].interval, expected);
    assert.equal(detail.panel.targets[0].data.query_configs[0].agg_interval, expected);
    const { graph, requests } = graphHarness(detail.panel.targets[0].data);
    await graph.queryPanelData();
    assert.equal(requests.length, 2);
    for (const request of requests) assert.equal(request.query_configs[0].interval, expected);
    assert.ok(requests[1].query_configs[0].promql.includes('offset 1h'));
  }
});

test('Native Step renders the executed interval on initialization instead of a missing or stale input shadow', () => {
  for (const [interval, agg_interval] of [[60, undefined], [60, '30s'], [60, '30'], ['auto', '30'], ['$interval', undefined]]) {
    const { editor } = detailEditor({ targets: [{ data: { query_configs: [{
      data_source_label: 'prometheus', promql: 'container_memory_rss', interval, agg_interval,
    }] } }] });
    assert.equal(stepInput(editor).propsData.value, interval);
    editor.$destroy();
  }
});

test('Native Step rolls rejected edits back in the rendered input and leaves the current query unchanged', async () => {
  for (const value of ['30s', '0', '30.5', '1e2', 'invalid', '', ' ']) {
    const { detail, editor, messages, emitted } = detailEditor({ targets: [{ data: {
      expression: 'A', query_configs: [{ ...podConfig(), data_source_label: 'prometheus', interval: 60 }],
    } }] });
    const before = structuredClone(detail.panel);
    stepInput(editor).listeners.change(value);
    await Vue.nextTick();
    assert.equal(stepInput(editor).propsData.value, value);
    stepInput(editor).listeners.blur();
    await Vue.nextTick();
    assert.equal(stepInput(editor).propsData.value, 60);
    assert.deepEqual(detail.panel, before);
    assert.equal(emitted.length, 0);
    assert.deepEqual(messages, value.trim()
      ? [{ theme: 'error', message: 'Step需填写合法的整数值' }] : []);
    editor.$destroy();
  }
});

test('Native Step rollback follows the latest accepted value across refresh and time changes', async () => {
  const { detail, editor, messages, emitted } = detailEditor({ targets: [{ data: {
    expression: 'A', query_configs: [{ ...podConfig(), data_source_label: 'prometheus', interval: 60 }],
  } }] });
  stepInput(editor).listeners.change(' 30 ');
  stepInput(editor).listeners.blur();
  stepInput(editor).listeners.change('0');
  stepInput(editor).listeners.blur();
  await Vue.nextTick();
  assert.equal(stepInput(editor).propsData.value, '30');
  assert.equal(detail.panel.targets[0].data.query_configs[0].interval, '30');
  assert.equal(emitted.length, 1);
  assert.equal(messages.length, 1);
  detail.handleTimeRangeChange(['now-2h', 'now']);
  detail.handleTimeChange(['2h']);
  detail.handleImmediateRefresh();
  const { graph, requests } = graphHarness(detail.panel.targets[0].data);
  graph.timeRange = detail.timeRange;
  graph.timeOffset = detail.timeOffset;
  await graph.queryPanelData();
  assert.equal(detail.chartKey, 'chart-refresh');
  assert.equal(requests.length, 2);
  for (const request of requests) {
    const payload = JSON.parse(JSON.stringify(request));
    assert.equal(payload.query_configs[0].interval, stepInput(editor).propsData.value);
    parse(payload.query_configs[0].promql);
  }
  assert.ok(requests[1].query_configs[0].promql.includes('offset 2h'));
  editor.$destroy();
});

test('Native unit overrides use the same effective method as the actual query variables', async () => {
  for (const [method, customScopedVars, variables, expectedMethod, expectedUnit] of [
    ['COUNT', { method: 'sum' }, {}, 'sum', 'bytes'],
    ['sum', { method: 'COUNT' }, {}, 'COUNT', 'none'],
    [undefined, {}, { method: 'COUNT' }, 'COUNT', 'none'],
  ]) {
    const { graph, requests } = graphHarness({ expression: 'A', unit: 'bytes', query_configs: [podConfig()] }, method);
    graph.viewOptions.method = method;
    graph.viewOptions.variables = variables;
    graph.customScopedVars = customScopedVars;
    await graph.queryPanelData();
    assert.equal(requests.length, 2);
    for (const request of requests) {
      assert.ok(request.query_configs[0].promql.startsWith(`${expectedMethod} by`));
      assert.equal(request.unit, expectedUnit);
    }
  }
});

const Collect = loadMethods(path.join(root, 'monitor-ui/chart-plugins/components/chart-collect/chart-collect.tsx'), ['checkList'], {
  VariablesService, getPromqlUnitOverride,
  handleTransformToTimestamp: () => [100, 200], reviewInterval: () => 60,
  dayjs: { tz: value => ({ unix: () => Number(value) }) },
});
const utilsFile = path.join(root, 'monitor-ui/chart-plugins/utils/utils.ts');
const utilsSource = ts.createSourceFile(utilsFile, fs.readFileSync(utilsFile, 'utf8'), ts.ScriptTarget.Latest, true);
const utilityCode = utilsSource.statements.filter(statement =>
  ts.isVariableStatement(statement) && statement.declarationList.declarations.some(declaration =>
    ['flattenObject', 'filterDictConvertedToWhere'].includes(declaration.name.getText(utilsSource))
  )
).map(statement => statement.getText(utilsSource)).join('\n');
const utilsExports = {};
new Function('exports', ts.transpileModule(utilityCode, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText)(utilsExports);
const collectionFile = path.join(root, 'monitor-pc/pages/data-retrieval/components/collection-dialog.vue');
const collectionSource = compiler.parse({ source: fs.readFileSync(collectionFile, 'utf8'), filename: collectionFile });
assert.deepEqual(collectionSource.errors, []);

test('Actual collection getter and save payload retain grouping and explicit units without changing legacy defaults', async () => {
  const ratio = podConfig();
  ratio.promql = `(${ratio.promql}) / 100`;
  ratio.pod_promql = `(${ratio.pod_promql}) / 100`;
  const scenarios = [
    { config: podConfig(), method: 'SUM', unit: 'bytes', expected: 'bytes' },
    { config: podConfig(), method: 'COUNT', unit: 'bytes', expected: 'none' },
    { config: ratio, method: 'SUM', unit: 'none', expected: 'none' },
    { config: { promql: 'count(container_memory_rss)', functions: [] }, method: 'COUNT', unit: 'bytes', expected: 'bytes' },
    { config: { metrics: [{ field: 'container_memory_rss', method: '$method' }] }, method: 'COUNT' },
  ];
  for (const group_by of [[], ['container_name'], ['container'], ['image'], ['namespace', 'image']]) {
    for (const scenario of scenarios) {
      const source = {
        id: 'fixture-panel', type: 'graph', title: 'Memory', checked: true, canSetGrafana: true,
        toDashboardPanels: () => undefined,
        targets: [{ data: { expression: 'A', query_configs: [scenario.config], ...(scenario.unit === undefined ? {} : { unit: scenario.unit }) } }],
      };
      const before = JSON.parse(JSON.stringify(source));
      const collect = Object.assign(new Collect(), {
        localPanels: [source], callOptions: {}, timeRange: ['now-1h', 'now'],
        viewOptions: { method: scenario.method, group_by, interval: 60, namespace: ['qa'], pod_name: 'worker-a' },
      });
      const list = collect.checkList;
      assert.equal(list.length, 1);
      const data = list[0].targets[0].data;
      assert.equal(data.unit, scenario.expected);
      if (scenario.expected === undefined) assert.equal('unit' in data, false);
      if (scenario.config.pod_promql) {
        const child = group_by.some(group => ['container_name', 'container', 'image'].includes(group));
        assert.ok(data.query_configs[0].promql.includes(child ? 'container_memory_rss{' : 'pod_memory_rss{'));
      }
      for (const field of ['pod_promql', 'overview_promql', 'overview_pod_promql']) assert.equal(field in data.query_configs[0], false);
      const saved = [];
      const Dialog = loadMethods(collectionFile, ['handleCollectionToDashboard'], {
        saveToDashboard: payload => { saved.push(payload); return Promise.resolve(); },
        filterDictConvertedToWhere: utilsExports.filterDictConvertedToWhere,
      }, collectionSource.script.content);
      const dialog = Object.assign(new Dialog(), {
        collectionList: list, checkedDashboard: { uid: 'fixture-dashboard' },
        $bkMessage() {}, $t: value => value, $emit() {},
      });
      dialog.handleCollectionToDashboard();
      await new Promise(resolve => setImmediate(resolve));
      assert.equal(saved.length, 1);
      const query = saved[0].panels[0].queries[0];
      assert.equal(query.unit, scenario.expected);
      assert.deepEqual(query.query_configs, data.query_configs);
      if (query.query_configs[0].promql) parse(query.query_configs[0].promql);
      assert.deepEqual(JSON.parse(JSON.stringify(source)), before);
    }
  }
});

test('Collection unit overrides preserve index priority over call options and use scoped fallback when absent', () => {
  for (const [method, callMethod, expectedMethod, unit] of [
    ['SUM', 'COUNT', 'SUM', 'bytes'], ['COUNT', 'SUM', 'COUNT', 'none'], [undefined, 'COUNT', 'COUNT', 'none'],
  ]) {
    const collect = Object.assign(new Collect(), {
      localPanels: [{ id: 'fixture-panel', type: 'graph', checked: true, canSetGrafana: true, targets: [{ data: {
        expression: 'A', unit: 'bytes', query_configs: [podConfig()],
      } }] }],
      callOptions: { method: callMethod }, timeRange: ['now-1h', 'now'],
      viewOptions: { method, group_by: [], interval: 60, namespace: ['qa'], pod_name: 'worker-a' },
    });
    const data = collect.checkList[0].targets[0].data;
    assert.ok(data.query_configs[0].promql.startsWith(`${expectedMethod} by`));
    assert.equal(data.unit, unit);
  }
});
