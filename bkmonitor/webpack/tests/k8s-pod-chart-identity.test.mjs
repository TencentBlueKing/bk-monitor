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
    .map(member => {
      if (!ts.isMethodDeclaration(member)) return member;
      return ts.factory.updateMethodDeclaration(
        member,
        member.modifiers?.filter(modifier => !ts.isDecorator(modifier)),
        member.asteriskToken,
        member.name,
        member.questionToken,
        member.typeParameters,
        member.parameters,
        member.type,
        member.body
      );
    });
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

const {
  K8sTableColumnKeysEnum: fields,
  K8SToEventWhereKeyMap,
  EDimensionKey,
  SceneEnum,
} = loadModule(path.join(root, 'src/monitor-pc/pages/monitor-k8s/typings/k8s-new.ts'));
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

const quickFile = 'src/monitor-pc/pages/monitor-k8s/components/k8s-quick-tools/k8s-quick-tools.tsx';
const panelFile = 'src/monitor-pc/components/k8s-silder/k8s-monitor-panel.tsx';
const apmFile = 'src/monitor-pc/pages/monitor-k8s/monitor-k8s-apm.tsx';
const json = value => JSON.parse(JSON.stringify(value));

function quickTools(props, panel) {
  const routes = [];
  const proto = methods(
    quickFile,
    [
      'filters',
      'filterValue',
      'scopeFilters',
      'resourceFilters',
      'apmResourceField',
      'filterToolConfig',
      'handleFilterChange',
      'handleDrillDown',
      'handleNewK8sPage',
      'getEventWhereConditions',
    ],
    {
      K8sTableColumnKeysEnum: fields,
      K8SToEventWhereKeyMap,
      SceneEnum,
      EMode: { ui: 'ui' },
      K8sGroupDimension: {
        createInstance: () => ({
          groupFilters: [],
          addGroupFilter(value) {
            this.groupFilters.push(value);
          },
        }),
      },
    }
  );
  const subject = Object.assign(Object.create(proto), {
    dimensions: {},
    timeOffset: [],
    isListTab: false,
    isApmMonitor: false,
    $route: { query: {} },
    onFilterChange: (...args) => panel.filterByChange(...args),
    onDrillDown: (...args) => panel.handleTableGroupChange(...args),
    gotoK8sPageByQuery: query => routes.push(query),
    ...props,
  });
  return { subject, routes };
}

for (const consumer of [panelFile, apmFile]) {
  for (const [scene, podLabel] of [
    [SceneEnum.Performance, 'pod_name'],
    [SceneEnum.Network, 'pod'],
    [SceneEnum.GPU, 'pod_name'],
  ]) {
    for (const timeOffset of [[], ['1d']]) {
      test(`${consumer}: ${scene} Pod legend actions retain raw identity with offsets ${timeOffset}`, () => {
        const panel = Object.assign(
          Object.create(
            methods(consumer, ['filterByChange', 'handleDrillDown', 'handleTableGroupChange'], { EDimensionKey })
          ),
          {
            filterBy: { namespace: ['alpha', 'beta'] },
            $set: (obj, key, value) => {
              obj[key] = value;
            },
            groupInstance: { groupFilters: [fields.POD], hasGroupFilter: () => true },
            groupByChange() {},
          }
        );
        const common = { bcs_cluster_id: 'BCS-K8S-PROXY', scenario: scene, filter_dict: panel.filterBy };
        const dimensions = { namespace: 'beta', [podLabel]: 'same-pod' };
        const h = (tag, props, ...children) => ({ tag, props, children: children.flat() });
        const graph = Object.assign(
          Object.create(
            methods(graphFile, ['render'], {
              h,
              ChartHeader: 'ChartHeader',
              BaseEchart: 'BaseEchart',
              TableLegend: 'TableLegend',
              K8sQuickTools: 'K8sQuickTools',
            })
          ),
          {
            panel: { externalData: { groupByField: fields.POD, filterCommonParams: common } },
            empty: false,
            isSpecialSeries: () => false,
          }
        );
        const find = (node, tag) =>
          node?.tag === tag ? node : node?.children?.map(child => find(child, tag)).find(Boolean);
        const legend = find(graph.render(), 'TableLegend');
        const name = timeOffset.length ? '1 day ago-beta:same-pod' : 'beta:same-pod';
        const slot = legend.props.scopedSlots.name({ item: { name, dimensions, show: true } });
        const { subject, routes } = quickTools({ ...find(slot, 'K8sQuickTools').props, timeOffset }, panel);
        assert.equal(subject.filterValue, 'same-pod');
        subject.handleFilterChange();
        assert.deepEqual(json(panel.filterBy), { namespace: ['beta'], pod: ['same-pod'] });
        assert.equal(subject.filterToolConfig.hasFilter, true);
        subject.handleFilterChange();
        assert.deepEqual(json(panel.filterBy), { namespace: ['beta'], pod: [] });

        panel.filterBy = { namespace: ['alpha', 'beta'] };
        subject.handleDrillDown({ id: fields.POD, dimension: fields.CONTAINER });
        assert.deepEqual(json(panel.filterBy), { namespace: ['beta'], pod: ['same-pod'] });
        assert.deepEqual(json(panel.cacheFilterBy), { namespace: ['alpha', 'beta'] });
        subject.handleNewK8sPage(SceneEnum.Network);
        subject.handleNewK8sPage(SceneEnum.Event);
        for (const route of routes) {
          assert.deepEqual(JSON.parse(route.filterBy), { namespace: ['beta'], pod: ['same-pod'] });
        }
        const where = JSON.parse(routes[1].targets)[0].data.query_configs[0].where;
        assert.deepEqual(
          where.map(item => [item.key, item.value]),
          [
            ['pod', ['same-pod']],
            ['namespace', ['beta']],
          ]
        );
      });
    }
  }
}

test('raw Pod filters do not treat a different namespace or a broader namespace selection as selected', () => {
  for (const namespace of [['alpha'], ['alpha', 'beta'], []]) {
    const { subject } = quickTools({
      groupByField: fields.POD,
      value: 'beta:same-pod',
      dimensions: { namespace: 'beta', pod_name: 'same-pod' },
      filterCommonParams: { filter_dict: { pod: ['same-pod'], namespace } },
    });
    assert.equal(subject.filterToolConfig.hasFilter, false);
  }
});

test('legacy Pod and other resource quick tools preserve their existing values and routes', () => {
  for (const [groupByField, value, expected, timeOffset] of [
    [fields.POD, 'same-pod', 'same-pod', []],
    [fields.NODE, '1 day ago-node-a', 'node-a', ['1d']],
    [fields.CONTAINER, 'worker:same-pod', 'worker', []],
    [fields.WORKLOAD, 'Deployment:api', 'Deployment:api', []],
    [fields.SERVICE, 'alpha:api', 'api', []],
    [fields.INGRESS, 'api:alpha', 'api', []],
  ]) {
    const { subject, routes } = quickTools({
      groupByField,
      value,
      timeOffset,
      filterCommonParams: { filter_dict: {}, bcs_cluster_id: 'BCS-K8S-NORMAL' },
    });
    assert.equal(subject.filterValue, expected);
    subject.handleNewK8sPage(SceneEnum.Performance);
    assert.deepEqual(JSON.parse(routes[0].filterBy), { [groupByField]: [expected] });
  }
});

test('Container and Workload main, ratio and auxiliary queries preserve namespace', () => {
  for (const groupByField of [fields.CONTAINER, fields.WORKLOAD]) {
    const params = context();
    params.groupByField = groupByField;
    params.resourceMap.set(fields.CONTAINER, 'worker');
    params.resourceMap.set(fields.WORKLOAD, 'api');
    params.resourceMap.set(fields.WORKLOAD_KIND, 'Deployment');
    const tool = new K8sChartTargetsCreateTool();
    const queries = [
      ...[
        'container_cpu_usage_seconds_total',
        'container_memory_working_set_bytes',
        'kube_pod_cpu_limits_ratio',
        'kube_pod_cpu_requests_ratio',
        'kube_pod_memory_limits_ratio',
        'kube_pod_memory_requests_ratio',
      ].map(metric => tool.createNodesTarget(SceneEnum.Performance, metric, params)),
      tool.createNodesTarget(SceneEnum.GPU, 'container_gpu_utilization', params),
      ...tool.createAuxiliaryLineTargets('container_cpu_usage_seconds_total', params),
      ...tool.createAuxiliaryLineTargets('container_memory_working_set_bytes', params),
    ];
    for (const target of queries) {
      const promql = target.data.query_configs[0].promql;
      const groups = [...promql.matchAll(/\$method by\s*\(([^)]+)\)/g)].map(match =>
        match[1].split(',').map(v => v.trim())
      );
      assert.ok(groups.length);
      for (const group of groups) assert.ok(group.includes('namespace'), promql);
      assert.ok(
        groups.some(group => group.includes(groupByField === fields.CONTAINER ? 'container_name' : 'workload_name'))
      );
    }
  }
});

const namespaceResources = [
  [fields.CONTAINER, { pod_name: 'same-pod', container_name: 'worker' }, { pod: 'same-pod', container: 'worker' }],
  [fields.WORKLOAD, { workload_kind: 'Deployment', workload_name: 'api' }, { workload: 'Deployment:api' }],
  [fields.SERVICE, { service: 'api' }, { service: 'api' }],
  [fields.INGRESS, { ingress: 'api' }, { ingress: 'api' }],
];

for (const [groupByField, rawDimensions, resource] of namespaceResources) {
  test(`${groupByField} details select raw namespace identity and ignore translated/time comparison labels`, () => {
    const subject = detailSubject();
    subject.groupByField = groupByField;
    subject.timeOffset = ['1d'];
    subject.resourceList = new Set(['alpha', 'beta'].map(namespace => ({ namespace, ...resource })));
    subject.handleShowDetail('display-only-label', { namespace: 'beta', ...rawDimensions });
    assert.equal(subject.sideDetail.namespace, 'beta');
    assert.equal(subject.sideDetail[groupByField], resource[groupByField]);
    for (const dimensions of [rawDimensions, { namespace: 'other', ...rawDimensions }]) {
      subject.sideDetailShow = false;
      subject.handleShowDetail('display-only-label', dimensions);
      assert.equal(subject.sideDetailShow, false);
    }
  });

  test(`${groupByField} quick actions keep namespace and parent Pod scope through cancel and scene changes`, () => {
    const panel = Object.assign(
      Object.create(
        methods(panelFile, ['filterByChange', 'handleDrillDown', 'handleTableGroupChange', 'handleCancelDrillDown'], {
          EDimensionKey,
        })
      ),
      {
        filterBy: { namespace: ['alpha', 'beta'], pod: ['other-pod'] },
        $set: (obj, key, value) => {
          obj[key] = value;
        },
        groupInstance: { groupFilters: [groupByField], hasGroupFilter: () => true, setGroupFilters() {} },
        groupByChange() {},
      }
    );
    const before = json(panel.filterBy);
    const { subject, routes } = quickTools(
      {
        groupByField,
        value: 'display-only-label',
        dimensions: { namespace: 'beta', ...rawDimensions },
        timeOffset: ['1d'],
        filterCommonParams: { filter_dict: panel.filterBy },
      },
      panel
    );
    subject.handleDrillDown({ id: groupByField, dimension: fields.CONTAINER });
    assert.deepEqual(json(panel.filterBy.namespace), ['beta']);
    assert.deepEqual(json(panel.filterBy[groupByField]), [resource[groupByField]]);
    if (groupByField === fields.CONTAINER) assert.deepEqual(json(panel.filterBy.pod), ['same-pod']);
    panel.handleCancelDrillDown();
    assert.deepEqual(json(panel.filterBy), before);
    subject.handleNewK8sPage(SceneEnum.Performance);
    subject.handleNewK8sPage(SceneEnum.Event);
    const expectedFilters = { namespace: ['beta'], [groupByField]: [resource[groupByField]] };
    if (groupByField === fields.CONTAINER) expectedFilters.pod = ['same-pod'];
    for (const route of routes) assert.deepEqual(JSON.parse(route.filterBy), expectedFilters);
    const where = JSON.parse(routes[1].targets)[0].data.query_configs[0].where;
    assert.ok(where.some(item => item.key === 'namespace' && item.value[0] === 'beta'));
    const expected =
      groupByField === fields.CONTAINER
        ? ['pod', 'same-pod']
        : groupByField === fields.WORKLOAD
          ? ['name', 'api']
          : [groupByField, 'api'];
    assert.ok(where.some(item => item.key === expected[0] && item.value[0] === expected[1]));
  });
}
