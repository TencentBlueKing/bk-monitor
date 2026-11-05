import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import vm from 'node:vm';
import ts from 'typescript';

const root = path.join(import.meta.dirname, '..');
const chartFile = 'src/monitor-pc/pages/monitor-k8s/components/k8s-charts/k8s-charts.tsx';
const graphFile = 'src/monitor-ui/chart-plugins/plugins/k8s-custom-graph/k8s-custom-graph.tsx';
const tools = path.join(root, 'src/monitor-pc/pages/monitor-k8s/components/k8s-charts/tools');
const modules = new Map();

// Execute the actual query generators with their local imports, without loading the browser application.
function loadModule(file) {
  if (modules.has(file)) return modules.get(file);
  const module = { exports: {} };
  modules.set(file, module.exports);
  const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  vm.runInNewContext(code, {
    exports: module.exports,
    module,
    require: name => {
      assert.ok(name.startsWith('.'), `unexpected dependency: ${name}`);
      return loadModule(path.resolve(path.dirname(file), `${name}.ts`));
    },
  });
  return module.exports;
}

// Isolate actual component methods from decorators, Vue and browser dependencies.
function methods(file, names, globals = {}) {
  const source = ts.createSourceFile(
    file,
    fs.readFileSync(path.join(root, file), 'utf8'),
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX
  );
  const component = source.statements.find(ts.isClassDeclaration);
  const members = component.members
    .filter(member => names.includes(member.name?.getText(source)))
    .map(member =>
      ts.factory.updateMethodDeclaration(
        member,
        member.modifiers?.filter(modifier => !ts.isDecorator(modifier)),
        member.asteriskToken,
        member.name,
        member.questionToken,
        member.typeParameters,
        member.parameters,
        member.type,
        member.body
      )
    );
  assert.equal(members.length, names.length);
  const subject = ts.factory.updateClassDeclaration(
    component,
    undefined,
    ts.factory.createIdentifier('Subject'),
    undefined,
    undefined,
    members
  );
  const code = ts.transpileModule(ts.createPrinter().printNode(ts.EmitHint.Unspecified, subject, source), {
    compilerOptions: { target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.React, jsxFactory: 'h' },
  }).outputText;
  return vm.runInNewContext(`${code}; Subject.prototype`, globals);
}

const { K8sTableColumnKeysEnum: fields, SceneEnum } = loadModule(
  path.join(root, 'src/monitor-pc/pages/monitor-k8s/typings/k8s-new.ts')
);
const { K8sPromqlGeneratorFactory } = loadModule(path.join(tools, 'promql-generator/promql-generator-factory.ts'));
const { K8sChartTargetsCreateTool } = loadModule(path.join(tools, 'targets-create/k8s-chart-targets-create-tool.ts'));
const factory = new K8sPromqlGeneratorFactory();
const context = (namespace = 'alpha|beta') => ({
  bcs_cluster_id: 'BCS-K8S-1',
  groupByField: fields.POD,
  resourceMap: new Map([
    [fields.NAMESPACE, namespace],
    [fields.POD, 'same-pod'],
  ]),
});

function assertPodGrouping(promql, podLabel) {
  assert.ok(promql, 'query is generated');
  const groups = [...promql.matchAll(/\$method by\(([^)]+)\)/g)].map(match => match[1].split(','));
  assert.ok(groups.length, 'query has resource aggregation');
  for (const group of groups) assert.deepEqual(group.sort(), ['namespace', podLabel].sort());
}

test('performance main charts and ratios retain namespace and the canonical pod_name label', () => {
  const generator = factory.getGeneratorInstance(SceneEnum.Performance);
  const metrics = [
    'container_cpu_usage_seconds_total',
    'container_network_receive_bytes_total',
    'container_network_transmit_bytes_total',
    'kube_pod_cpu_limits_ratio',
    'container_cpu_cfs_throttled_ratio',
    'kube_pod_cpu_requests_ratio',
    'container_memory_working_set_bytes',
    'kube_pod_memory_limits_ratio',
    'kube_pod_memory_requests_ratio',
  ];
  for (const metric of metrics) {
    const promql = generator.generate(metric, context());
    assertPodGrouping(promql, 'pod_name');
    assert.match(promql, /pod_name=~"\^\(same-pod\)\$"/);
  }
});

test('request and limit auxiliary lines use the same Pod identity as their performance chart', () => {
  const tool = new K8sChartTargetsCreateTool();
  for (const metric of ['container_cpu_usage_seconds_total', 'container_memory_working_set_bytes']) {
    const targets = tool.createAuxiliaryLineTargets(metric, context());
    assert.equal(targets.length, 2);
    for (const target of targets) assertPodGrouping(target.data.query_configs[0].promql, 'pod_name');
  }
});

test('network charts preserve namespace with their pod label, including a single selected namespace', () => {
  const generator = factory.getGeneratorInstance(SceneEnum.Network);
  const metrics = [
    'nw_container_network_receive_bytes_total',
    'nw_container_network_transmit_bytes_total',
    'nw_container_network_receive_packets_total',
    'nw_container_network_transmit_packets_total',
    'nw_container_network_receive_errors_total',
    'nw_container_network_transmit_errors_total',
    'nw_container_network_receive_errors_ratio',
    'nw_container_network_transmit_errors_ratio',
  ];
  for (const namespace of ['alpha|beta', 'qa']) {
    const params = context(namespace);
    params.filter_dict = { namespace: namespace.split('|') };
    for (const metric of metrics) assertPodGrouping(generator.generate(metric, params), 'pod');
  }
});

test('GPU charts preserve namespace and pod_name for native and DCGM data', () => {
  const generator = factory.getGeneratorInstance(SceneEnum.GPU);
  for (const metric of [
    'container_gpu_utilization',
    'container_gpu_memory_total',
    'container_core_utilization_percentage',
    'container_mem_utilization_percentage',
    'container_request_gpu_memory',
    'container_request_gpu_utilization',
  ]) {
    const promql = generator.generate(metric, context());
    assertPodGrouping(promql, 'pod_name');
    assert.match(promql, /DCGM_FI_DEV_/);
  }
});

function detailSubject() {
  const proto = methods(chartFile, ['handleShowDetail'], { K8sTableColumnKeysEnum: fields });
  return Object.assign(Object.create(proto), {
    groupByField: fields.POD,
    timeOffset: [],
    resourceList: new Set([
      { namespace: 'alpha', pod: 'same-pod' },
      { namespace: 'beta', pod: 'same-pod' },
    ]),
    filterCommonParams: { bcs_cluster_id: 'BCS-K8S-1' },
    sideDetailShow: false,
  });
}

test('Pod legend opens the exact namespace regardless of name formatting or time comparison', () => {
  for (const podLabel of ['pod_name', 'pod']) {
    const subject = detailSubject();
    subject.timeOffset = ['1d'];
    subject.handleShowDetail('1 day ago-beta:same-pod', { namespace: 'beta', [podLabel]: 'same-pod' });
    assert.equal(subject.sideDetailShow, true);
    assert.equal(subject.sideDetail.namespace, 'beta');
    assert.equal(subject.sideDetail.pod, 'same-pod');
    assert.equal(subject.sideDetail.cluster, 'BCS-K8S-1');
  }
});

test('Pod legend with absent or unmatched identity never opens a different same-named Pod', () => {
  for (const dimensions of [undefined, { pod_name: 'same-pod' }, { namespace: 'other', pod_name: 'same-pod' }]) {
    const subject = detailSubject();
    subject.handleShowDetail('same-pod', dimensions);
    assert.equal(subject.sideDetailShow, false);
  }
});

test('single namespace Pod details and other existing resource detail routing remain available', () => {
  const subject = detailSubject();
  subject.resourceList = new Set([{ namespace: 'qa', pod: 'same-pod' }]);
  subject.handleShowDetail('qa:same-pod', { namespace: 'qa', pod_name: 'same-pod' });
  assert.equal(subject.sideDetail.namespace, 'qa');
  subject.groupByField = fields.NODE;
  subject.resourceList = new Set([{ node: 'node-a' }]);
  subject.handleShowDetail('node-a');
  assert.equal(subject.sideDetail.node, 'node-a');
});

test('rendered legend forwards the raw dimensions used by detail routing', () => {
  const h = (tag, props, ...children) => ({ tag, props, children: children.flat() });
  const proto = methods(graphFile, ['render'], {
    h,
    ChartHeader: 'ChartHeader',
    BaseEchart: 'BaseEchart',
    TableLegend: 'TableLegend',
    K8sQuickTools: 'K8sQuickTools',
  });
  const calls = [];
  const subject = Object.assign(Object.create(proto), {
    panel: { externalData: { groupByField: fields.POD } },
    empty: false,
    isSpecialSeries: () => false,
    onShowDetail: (...args) => calls.push(args),
  });
  const find = (node, tag) => (node?.tag === tag ? node : node?.children?.map(child => find(child, tag)).find(Boolean));
  const legend = find(subject.render(), 'TableLegend');
  const item = { name: 'beta:same-pod', show: true, dimensions: { namespace: 'beta', pod_name: 'same-pod' } };
  const name = legend.props.scopedSlots.name({ item });
  find(name, 'span').props.onClick();
  assert.equal(calls.length, 1);
  assert.equal(calls[0][0], item.name);
  assert.equal(calls[0][1], item.dimensions);
});
