import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import vm from 'node:vm';
import ts from 'typescript';

const root = path.join(import.meta.dirname, '..');
const chartFile = 'src/monitor-pc/pages/monitor-k8s/components/k8s-charts/k8s-charts.tsx';
const graphFile = 'src/monitor-ui/chart-plugins/plugins/k8s-custom-graph/k8s-custom-graph.tsx';
const commonUtils = { deepClone: structuredClone, random: () => 'test-id' };
const modules = new Map();

function loadModule(file, stubs = {}) {
  const code = ts.transpileModule(fs.readFileSync(path.join(root, file), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const module = { exports: {} };
  vm.runInNewContext(code, {
    exports: module.exports,
    module,
    structuredClone,
    require: name => {
      if (name in stubs) return stubs[name];
      const external = {
        'monitor-common/utils/utils': commonUtils,
        'monitor-common/utils': commonUtils,
        'monitor-api/modules/strategies': {},
        dayjs: {},
      };
      if (name in external) return external[name];
      assert.ok(name.startsWith('.'), `unexpected dependency: ${name}`);
      const dependency = path.join(path.dirname(file), `${name}.ts`);
      if (!modules.has(dependency)) modules.set(dependency, loadModule(dependency));
      return modules.get(dependency);
    },
  });
  return module.exports;
}

// Execute actual component methods and getters without mounting Vue or ECharts.
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
  const subject = ts.factory.updateClassDeclaration(
    component,
    undefined,
    ts.factory.createIdentifier('Subject'),
    undefined,
    undefined,
    members
  );
  const code = ts.transpileModule(ts.createPrinter().printNode(ts.EmitHint.Unspecified, subject, source), {
    compilerOptions: { target: ts.ScriptTarget.ES2022 },
  }).outputText;
  return vm.runInNewContext(`${code}; Subject.prototype`, { AbortController, structuredClone, ...globals });
}

const { PanelModel } = loadModule('src/monitor-ui/chart-plugins/typings/dashboard-panel.ts');
const { VariablesService } = loadModule('src/monitor-ui/chart-plugins/utils/variable.ts');
const { K8sChartTargetsCreateTool } = loadModule(
  'src/monitor-pc/pages/monitor-k8s/components/k8s-charts/tools/targets-create/k8s-chart-targets-create-tool.ts'
);

async function createPanel(cluster, isDetailMode) {
  const subject = Object.assign(Object.create(methods(chartFile, ['loadPanels'])), {
    requestId: 0,
    queryKey: cluster,
    filterCommonParams: { bcs_cluster_id: cluster, filter_dict: {} },
    metricList: [
      { id: 'cpu', children: [{ id: 'container_cpu_usage_seconds_total', show_chart: true, unit: 'cores' }] },
    ],
    hideMetrics: [],
    groupByField: 'pod',
    scene: 'performance',
    method: 'sum',
    isDetailMode,
    k8sChartTargetsCreateTool: new K8sChartTargetsCreateTool(),
    getResourceList: async () => ({
      resourceMap: new Map([
        ['namespace', 'alpha'],
        ['pod', 'same-pod'],
      ]),
      resourceList: new Set([{ namespace: 'alpha', pod: 'same-pod' }]),
    }),
    $nextTick: async () => {},
    onActiveMetricIdChange() {},
  });
  await subject.loadPanels();
  assert.equal(subject.loadError, false);
  return new PanelModel(subject.panels[0].panels[0]);
}

function graph(panel, responseConfig) {
  const requests = [];
  const events = [];
  const window = { i18n: { t: value => value }, timezone: 'UTC', open: url => events.push(['open', url]) };
  const proto = methods(
    graphFile,
    [
      'menuList',
      'loadPanelData',
      'isCurrentDataRequest',
      'handleMenuToolsSelect',
      'handleAllMetricClick',
      'handleMetricClick',
      'handleAlarmClick',
    ],
    {
      window,
      location: { origin: 'https://example.com', pathname: '/', href: 'https://example.com/#/k8s', hash: '#/k8s' },
      handleTransformToTimestamp: value => value,
      VariablesService,
      CancelToken: class {
        constructor(callback) {
          callback(() => {});
        }
      },
      convertToSeconds: () => 60,
      openAlarmCenter: data => events.push(['alert', data]),
    }
  );
  const subject = Object.assign(Object.create(proto), {
    panel,
    dataRequestId: 1,
    k8sLoadingSkeleton: true,
    chartDataLoaded: false,
    cancelTokens: [],
    timeOffset: [],
    timeRange: [100, 200],
    toolTimeRange: [100, 200],
    bkBizId: 2,
    viewOptions: { interval: '60s', method: 'sum' },
    $el: { clientWidth: 500 },
    $store: { getters: { bizId: 2 } },
    beforeGetPanelData: async () => true,
    downSampleRangeComputed: () => '60s',
    unregisterObserver() {},
    clearErrorMsg() {},
    handleErrorMsgChange: error => assert.fail(error),
    handleLoadingChange() {},
    handleCollectChart: () => events.push(['save', panel.toDashboardPanels()]),
    handleFullScreen: data => events.push(['fullscreen', data]),
    handleAddStrategy: () => events.push(['strategy', panel.toStrategy()]),
    $api: {
      grafana: {
        graphUnifyQuery: async params => {
          requests.push(params);
          const queryConfig = responseConfig ? structuredClone(params) : undefined;
          if (queryConfig) queryConfig.query_configs[0].promql = `sum(${queryConfig.query_configs[0].promql})`;
          return { metrics: [], series: [], query_config: queryConfig };
        },
      },
    },
  });
  return { subject, requests, events };
}

for (const cluster of ['BCS-K8S-NORMAL', 'BCS-K8S-PROXY']) {
  for (const responseConfig of [false, true]) {
    test(`${cluster}: charts reuse ${responseConfig ? 'response' : 'request'} queries in all existing actions`, async () => {
      const panel = await createPanel(cluster, false);
      assert.equal(panel.targets.length, 3, 'main series plus request and limit lines');
      assert.ok(panel.targets.every(target => target.api === 'grafana.graphUnifyQuery'));
      const { subject, requests, events } = graph(panel, responseConfig);
      await subject.loadPanelData();
      assert.equal(subject.chartLoadError, false);
      assert.equal(requests.length, 3);
      assert.ok(panel.targets.every(target => panel.rawTargetQueryMap.has(target)));
      assert.deepEqual(Array.from(subject.menuList), [
        'save',
        'more',
        'explore',
        'area',
        'drill-down',
        'strategy',
        'relate-alert',
      ]);
      for (const id of ['save', 'fullscreen', 'explore', 'strategy', 'relate-alert'])
        subject.handleMenuToolsSelect({ id });
      subject.handleAllMetricClick();
      subject.handleMetricClick({ metric_id: 'cpu' });
      subject.handleAlarmClick({ status: 0 });
      assert.deepEqual(
        events.map(([type]) => type),
        ['save', 'fullscreen', 'open', 'open', 'alert', 'strategy', 'strategy', 'strategy']
      );
      const reusedPromql = request => {
        const promql = request.query_configs[0].promql;
        return responseConfig ? `sum(${promql})` : promql;
      };
      const promql = reusedPromql(requests[0]);
      assert.ok(promql.includes(cluster));
      assert.match(promql, /by\(namespace,pod_name\)/);
      assert.equal(events[0][1].queries[0].query_configs[0].promql, promql);
      assert.equal(events[1][1][0].data.query_configs[0].promql, promql);
      const explore = new URL(events[2][1]).hash.split('?')[1];
      assert.equal(JSON.parse(new URLSearchParams(explore).get('targets'))[0].data.query_configs[0].promql, promql);
      const strategy = new URL(events[3][1]).hash.split('?')[1];
      assert.equal(JSON.parse(new URLSearchParams(strategy).get('data')).query_configs[0].promql, promql);
      assert.equal(events[4][1].promql, reusedPromql(requests[2]));
      assert.equal(events[5][1].query_configs[0].promql, promql);
    });
  }
  test(`${cluster}: detail charts keep the same Grafana route and auxiliary lines`, async () => {
    const panel = await createPanel(cluster, true);
    assert.equal(panel.options.legend.displayMode, 'hidden');
    assert.equal(panel.targets.length, 3);
    assert.ok(panel.targets.every(target => target.api === 'grafana.graphUnifyQuery'));
  });
}

test('resource APIs advertise namespace-aware chart identity without changing input or request options', async () => {
  const calls = [];
  const api = loadModule('src/monitor-api/modules/k8s.js', {
    '../base': { request: (method, url) => async (params, options) => calls.push({ method, url, params, options }) },
  });
  const params = { bcs_cluster_id: 'BCS-K8S-PROXY' };
  const options = { signal: new AbortController().signal };
  for (const name of ['listK8sResources', 'getResourceDetail', 'workloadOverview']) {
    await api[name](params, options);
  }
  assert.equal(calls.length, 3);
  for (const call of calls) {
    assert.equal(call.params.supports_federated_charts, true);
    assert.equal(call.params.bcs_cluster_id, params.bcs_cluster_id);
    assert.equal(call.options, options);
  }
  assert.equal(params.supports_federated_charts, undefined);
  calls.length = 0;
  for (const name of ['listK8sResourcesWithoutFederatedCharts', 'namespaceWorkloadOverview']) {
    await api[name](params, options);
    assert.equal(api.default[name], api[name]);
  }
  assert.equal(calls.length, 2);
  for (const call of calls) {
    assert.equal(call.params, params);
    assert.equal(call.options, options);
    assert.equal(call.params.supports_federated_charts, undefined);
  }
});

test('APM association selectors preserve the original resource scope for both cluster types', async () => {
  for (const cluster of ['BCS-K8S-PROXY', 'BCS-K8S-ORDINARY']) {
    const calls = [];
    const api = loadModule('src/monitor-api/modules/k8s.js', {
      '../base': {
        request: (method, url) => async params => {
          calls.push({ method, url, params });
          return url.endsWith('/namespace_workload_overview/')
            ? {
                count: 1,
                workload_count: 1,
                items: [{ namespace: 'alpha', workload_count: 1, workload_overview: [['Deployment', 1]] }],
              }
            : { count: 1, items: [{ workload: 'Deployment:api' }] };
        },
      },
    });
    const panel = Object.assign(
      Object.create(
        methods(
          'src/apm/pages/service/service-config/components/relation-select-panel.tsx',
          ['getNamespaceWorkloadOverview', 'getListResources'],
          { ...api, QueryFromType: { Workload: 'workload' } }
        )
      ),
      { searchVal: '' }
    );
    const overview = await panel.getNamespaceWorkloadOverview({ bcs_cluster_id: cluster, page: 1 });
    const workload = overview.items[0].children[0];
    const resources = await panel.getListResources({
      bcs_cluster_id: cluster,
      namespace: 'alpha',
      workloadType: 'Deployment',
      page: 1,
      parentData: workload,
    });
    assert.equal(resources.items[0].id, `${cluster}/alpha/Deployment/api`);
    assert.equal(calls.length, 2);
    for (const call of calls) {
      assert.equal(call.params.bcs_cluster_id, cluster);
      assert.equal(call.params.supports_federated_charts, undefined);
    }
    assert.equal(calls[1].params.filter_dict.namespace, 'alpha');
    assert.equal(calls[1].params.filter_dict.workload, 'Deployment:');
  }
});

test('existing readonly and strategy-page restrictions remain in the shared chart header', () => {
  const proto = methods('src/monitor-ui/chart-plugins/components/chart-title/chart-title.tsx', [
    'showMetricAlarm',
    'showAddStrategy',
  ]);
  const header = Object.assign(Object.create(proto), {
    metrics: [{ metric_id: 'cpu' }],
    readonly: false,
    $route: { name: 'k8s' },
  });
  assert.equal(header.showMetricAlarm, true);
  assert.equal(header.showAddStrategy, true);
  header.readonly = true;
  assert.equal(header.showMetricAlarm, false);
  header.$route.name = 'strategy-config';
  assert.equal(header.showAddStrategy, false);
});
