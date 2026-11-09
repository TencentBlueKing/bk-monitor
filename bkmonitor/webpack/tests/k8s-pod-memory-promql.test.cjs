const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const { parser } = require('@prometheus-io/lezer-promql');
const ts = require('typescript');

const root = path.resolve(__dirname, '../src/monitor-pc/pages/monitor-k8s');
const cache = new Map();

function load(relativePath) {
  const file = path.resolve(root, relativePath);
  if (cache.has(file)) return cache.get(file).exports;
  const module = { exports: {} };
  cache.set(file, module);
  const { outputText } = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  });
  new Function('require', 'module', 'exports', outputText)(id => {
    assert.ok(id.startsWith('.'), `Unexpected dependency: ${id}`);
    return load(path.relative(root, path.resolve(path.dirname(file), `${id}.ts`)));
  }, module, module.exports);
  return module.exports;
}

const { K8sTableColumnKeysEnum: fields, SceneEnum } = load('typings/k8s-new.ts');
const { K8sPerformancePromqlGenerator } = load(
  'components/k8s-charts/tools/promql-generator/performance-promql-generator.ts'
);
const { K8sChartTargetsCreateTool } = load('components/k8s-charts/tools/targets-create/k8s-chart-targets-create-tool.ts');
const generator = new K8sPerformancePromqlGenerator();
const targets = new K8sChartTargetsCreateTool();
const metrics = [
  'container_memory_working_set_bytes',
  'kube_pod_memory_requests_ratio',
  'kube_pod_memory_limits_ratio',
];
const scope = 'bcs_cluster_id="fixture-cluster",namespace=~"^(qa)$",pod_name=~"^(worker-a)$"';
const childFilter = `${scope},container_name!="POD"`;
const childUsage = `sum by(bcs_cluster_id,namespace,pod_name)(container_memory_working_set_bytes{${childFilter},container_name!=""} $time_shift)`;
const parentUsage = `sum by(bcs_cluster_id,namespace,pod_name)(pod_memory_working_set_bytes{${childFilter},metrics_path="/metrics/cadvisor"} $time_shift)`;
const selectedUsage = `(${parentUsage} or on(bcs_cluster_id,namespace,pod_name) ${childUsage})`;

function context(groupByField = fields.POD, filter_dict = {}) {
  return {
    bcs_cluster_id: 'fixture-cluster',
    groupByField,
    filter_dict,
    resourceMap: new Map([
      [fields.POD, 'worker-a'],
      [fields.NAMESPACE, 'qa'],
      [fields.CONTAINER, 'api|sidecar'],
      [fields.WORKLOAD, 'worker'],
      [fields.WORKLOAD_KIND, 'Deployment'],
      [fields.NODE, 'node-a'],
      [fields.CLUSTER, 'fixture-cluster'],
    ]),
  };
}

function parsed(query, method = 'sum', timeShift = '') {
  const promql = query.replaceAll('$method', method).replaceAll('$time_shift', timeShift).replaceAll('$interval', '1m');
  const tree = parser.parse(promql);
  const cursor = tree.cursor();
  do {
    assert.equal(cursor.type.isError, false, `Invalid PromQL at ${cursor.from}: ${promql}`);
  } while (cursor.next());
  return { promql, node: tree.topNode.firstChild };
}

function nodesOfType(node, type) {
  const nodes = [];
  function visit(current) {
    if (current.name === type) nodes.push(current);
    for (let child = current.firstChild; child; child = child.nextSibling) visit(child);
  }
  visit(node);
  return nodes;
}

test('Pod WS target keeps the existing API and selects parent or child total before the display method', () => {
  const target = targets.createNodesTarget(SceneEnum.Performance, metrics[0], context());
  assert.deepEqual(target, {
    data: {
      expression: 'A',
      query_configs: [{
        data_source_label: 'prometheus',
        data_type_label: 'time_series',
        promql: `$method by(namespace,pod_name)(${selectedUsage})`,
        interval: '$interval_second',
        alias: 'a',
        filter_dict: {},
      }],
    },
    datasource: 'time_series',
    data_type: 'time_series',
    api: 'grafana.graphUnifyQuery',
  });
  for (const method of ['sum', 'max', 'avg', 'min', 'count']) {
    const { node } = parsed(target.data.query_configs[0].promql, method);
    assert.equal(node.name, 'AggregateExpr');
    assert.equal(nodesOfType(node, 'Or').length, 1);
    assert.equal(nodesOfType(node, 'AggregateExpr').length, 3);
  }
});

test('Parent selection is a set union without a numeric predicate, so an existing zero remains eligible', () => {
  const { node, promql } = parsed(generator.generate(metrics[0], context()));
  const selection = nodesOfType(node, 'BinaryExpr');
  assert.equal(selection.length, 1);
  assert.equal(selection[0].firstChild.name, 'AggregateExpr');
  assert.equal(selection[0].firstChild.nextSibling.name, 'Or');
  assert.equal(selection[0].lastChild.name, 'AggregateExpr');
  const matching = nodesOfType(selection[0], 'MatchingModifierClause');
  assert.equal(matching.length, 1);
  assert.equal(promql.slice(matching[0].from, matching[0].to), 'on(bcs_cluster_id,namespace,pod_name)');
  for (const branch of [selection[0].firstChild, selection[0].lastChild]) {
    const grouping = branch.getChild('AggregateModifier').getChild('GroupingLabels');
    assert.equal(promql.slice(grouping.from, grouping.to), '(bcs_cluster_id,namespace,pod_name)');
  }
  assert.deepEqual(nodesOfType(selection[0].firstChild, 'Identifier').map(n => promql.slice(n.from, n.to)), [
    'pod_memory_working_set_bytes',
  ]);
  assert.deepEqual(nodesOfType(selection[0].lastChild, 'Identifier').map(n => promql.slice(n.from, n.to)), [
    'container_memory_working_set_bytes',
  ]);
});

test('Missing and empty container selection mean all containers and retain parent fallback', () => {
  const expected = generator.generate(metrics[0], context());
  for (const filters of [undefined, {}, { container: [] }, { container: [''] }]) {
    const input = context();
    input.filter_dict = filters;
    assert.equal(generator.generate(metrics[0], input), expected);
  }
});

test('Explicit container names, including a full name selection, constrain WS and both ratio denominators', () => {
  const input = context(fields.POD, { container: ['api', 'sidecar'] });
  const filter = `${scope},container_name=~"^(api|sidecar)$"`;
  const usage = `sum by(bcs_cluster_id,namespace,pod_name)(container_memory_working_set_bytes{${filter},container_name!=""} $time_shift)`;
  assert.equal(generator.generate(metrics[0], input), `$method by(namespace,pod_name)(${usage})`);
  assert.equal(
    generator.generate(metrics[1], input),
    `$method by(namespace,pod_name)(${usage}) / $method by(namespace,pod_name)(sum by(bcs_cluster_id,namespace,pod_name)(kube_pod_container_resource_requests_memory_bytes{${filter}} $time_shift))`
  );
  for (const metric of metrics) {
    const { node, promql } = parsed(generator.generate(metric, input), 'sum', 'offset 1h');
    assert.equal(promql.includes('pod_memory_working_set_bytes'), false);
    const selectors = nodesOfType(node, 'VectorSelector');
    const memorySelectors = selectors.filter(selector => !promql.slice(selector.from, selector.to).startsWith('kube_pod_init_container_status_running'));
    assert.ok(memorySelectors.length > 0);
    for (const selector of memorySelectors) {
      assert.ok(promql.slice(selector.from, selector.to).includes(filter));
    }
  }
  assert.equal(input.groupByField, fields.POD);
  assert.equal(input.resourceMap.get(fields.CONTAINER), 'api|sidecar');
});

test('Parent and fallback preserve namespace identity, escaped names and the same time shift', () => {
  const input = context();
  input.resourceMap.set(fields.NAMESPACE, 'qa|team.a');
  input.resourceMap.set(fields.POD, 'worker.a|worker-b');
  for (const metric of metrics) {
    const query = generator.generate(metric, input);
    const { node, promql } = parsed(query, 'avg', 'offset 1h');
    const memorySelectors = nodesOfType(node, 'VectorSelector').filter(selector =>
      promql.slice(selector.from, selector.to).startsWith('pod_memory_') ||
      promql.slice(selector.from, selector.to).startsWith('container_memory_')
    );
    assert.equal(memorySelectors.length, 2);
    for (const selector of memorySelectors) {
      const content = promql.slice(selector.from, selector.to);
      assert.ok(content.includes('bcs_cluster_id="fixture-cluster"'));
      assert.ok(content.includes('namespace=~"^(qa|team\\\\.a)$"'));
      assert.ok(content.includes('pod_name=~"^(worker\\\\.a|worker-b)$"'));
      assert.equal(selector.parent.name, 'OffsetExpr');
      assert.equal(promql.slice(selector.to, selector.parent.to), ' offset 1h');
    }
  }
  input.filter_dict.container = ['api.v1', 'sidecar'];
  assert.ok(generator.generate(metrics[0], input).includes('container_name=~"^(api\\\\.v1|sidecar)$"'));
});

test('Pod ratios reuse the selected numerator and retain Request/Limit and running init-container queries', () => {
  const ws = generator.generate(metrics[0], context());
  for (const metric of metrics.slice(1)) {
    const query = generator.generate(metric, context());
    assert.ok(query.startsWith(`${ws} / $method by(namespace,pod_name)(`));
    parsed(query, 'max', 'offset 1d');
  }
  const request = generator.generate(metrics[1], context());
  assert.equal(request, `${ws} / $method by(namespace,pod_name)(sum by(bcs_cluster_id,namespace,pod_name)(kube_pod_container_resource_requests_memory_bytes{${childFilter}} $time_shift))`);
  const limit = generator.generate(metrics[2], context());
  for (const metric of ['kube_pod_container_resource_limits', 'kube_pod_init_container_resource_limits', 'kube_pod_init_container_status_running']) {
    assert.ok(limit.includes(metric));
  }
  assert.ok(limit.includes('resource="memory",unit="byte"'));
  assert.ok(limit.includes('* on(namespace,pod,container) group_left()'));
});

test('Pod Request/Limit denominators aggregate container totals before every display method', () => {
  for (const filters of [{}, { container: ['api', 'sidecar'] }]) {
    for (const metric of metrics.slice(1)) {
      const target = targets.createNodesTarget(SceneEnum.Performance, metric, context(fields.POD, filters));
      for (const method of ['sum', 'max', 'avg', 'min', 'count']) {
        const { node, promql } = parsed(target.data.query_configs[0].promql, method);
        assert.equal(node.name, 'BinaryExpr');
        assert.equal(promql.slice(node.firstChild.firstChild.from, node.firstChild.firstChild.to), method);
        const denominator = node.lastChild;
        assert.equal(denominator.name, 'AggregateExpr');
        assert.equal(promql.slice(denominator.firstChild.from, denominator.firstChild.to), method);
        const total = nodesOfType(denominator, 'AggregateExpr')[1];
        assert.equal(promql.slice(total.firstChild.from, total.firstChild.to), 'sum');
        const grouping = total.getChild('AggregateModifier').getChild('GroupingLabels');
        assert.equal(promql.slice(grouping.from, grouping.to), '(bcs_cluster_id,namespace,pod_name)');
      }
    }
  }
});

test('Non-Pod WS queries and Pod CPU/network retain their existing output', () => {
  const expectedScopes = new Map([
    [fields.CONTAINER, `${scope},container_name=~"^(api|sidecar)$"`],
    [fields.WORKLOAD, 'bcs_cluster_id="fixture-cluster",namespace=~"^(qa)$",workload_kind=~"^(Deployment)$",workload_name=~"^(worker)$"'],
    [fields.NAMESPACE, 'bcs_cluster_id="fixture-cluster",namespace=~"^(qa)$"'],
    [fields.NODE, 'bcs_cluster_id="fixture-cluster",namespace=~"^(qa)$",node=~"^(node-a)$"'],
    [fields.CLUSTER, 'bcs_cluster_id="fixture-cluster",namespace=~"^(qa)$"'],
  ]);
  const groupings = new Map([
    [fields.CONTAINER, 'namespace,pod_name,container_name'],
    [fields.WORKLOAD, 'namespace,workload_kind,workload_name'],
    [fields.NAMESPACE, 'namespace'],
    [fields.NODE, 'node'],
    [fields.CLUSTER, 'bcs_cluster_id'],
  ]);
  for (const [group, filter] of expectedScopes) {
    const input = context(group, { container: ['api'] });
    assert.equal(generator.generate(metrics[0], input), `$method by(${groupings.get(group)})(container_memory_working_set_bytes{${filter}} $time_shift)`);
    for (const metric of metrics.slice(1)) {
      assert.equal(generator.generate(metric, input).includes('pod_memory_working_set_bytes'), false);
      parsed(generator.generate(metric, input));
    }
  }
  assert.equal(
    generator.generate('container_cpu_usage_seconds_total', context()),
    `$method by(namespace,pod_name)(rate(container_cpu_usage_seconds_total{${childFilter}}[$interval] $time_shift))`
  );
  assert.equal(
    generator.generate('container_network_receive_bytes_total', context()),
    `$method by(namespace,pod_name)(rate(container_network_receive_bytes_total{${scope},}[$interval] $time_shift))`
  );
});
