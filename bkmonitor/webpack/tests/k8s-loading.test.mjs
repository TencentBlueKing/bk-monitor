import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import vm from 'node:vm';
import ts from 'typescript';

const root = path.join(import.meta.dirname, '..');
const base = 'src/monitor-pc/pages/monitor-k8s/components/';
const tableFile = `${base}k8s-table-new/k8s-table-new.tsx`;
const chartFile = `${base}k8s-charts/k8s-charts.tsx`;
const dimensionFile = `${base}k8s-left-panel/k8s-dimension-list.tsx`;
const filterFile = `${base}filter-by-condition/filter-by-condition.tsx`;
const panelFile = 'src/monitor-pc/components/k8s-silder/k8s-monitor-panel.tsx';
function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((yes, no) => {
    resolve = yes;
    reject = no;
  });
  return { promise, resolve, reject };
}

// Execute the component's actual methods, isolating only browser dependencies and API calls.
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
  const text = ts.createPrinter().printNode(ts.EmitHint.Unspecified, subject, source);
  const code = ts.transpileModule(text, {
    compilerOptions: { target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.React, jsxFactory: 'h' },
  }).outputText;
  return vm.runInNewContext(`${code}; Subject.prototype`, { AbortController, setTimeout, clearTimeout, ...globals });
}

const tick = async () => {
  for (let i = 0; i < 8; i++) await Promise.resolve();
};
const response = name => ({ count: 1, items: [{ pod: name }] });

function table() {
  const requests = [];
  const metrics = [];
  const mutations = [];
  const proto = methods(
    tableFile,
    [
      'getK8sList',
      'abortAsyncData',
      'loadAsyncData',
      'beforeDestroy',
      'debounceGetK8sList',
      'showSkeleton',
      'handleTableScrollEnd',
      'tableHasScrollLoading',
    ],
    {
      listK8sResources: (params, options) => {
        const request = { ...deferred(), params, signal: options.signal };
        requests.push(request);
        return request.promise;
      },
      resourceTrend: (_params, options) => {
        const request = { ...deferred(), signal: options.signal };
        metrics.push(request);
        return request.promise;
      },
      enabledFrontendLimit: false,
      K8sConvergeTypeEnum: { SUM: 'sum' },
      K8sTableColumnKeysEnum: { CONTAINER: 'container' },
      handleTransformToTimestamp: value => value,
      bkMessage() {},
      makeMessage: value => value,
    }
  );
  const subject = Object.assign(Object.create(proto), {
    requestId: 0,
    disposed: false,
    requestTimer: null,
    metricLoading: false,
    queryKey: 'cluster-a',
    loadedQueryKey: '',
    loadError: false,
    filterCommonParams: { bcs_cluster_id: 'a', timeRange: [1, 2] },
    tableLoading: { loading: true, scrollLoading: false },
    pagination: { page: 1, pageSize: 20, pageType: 'scrolling' },
    tableData: [],
    tableDataTotal: 0,
    tableViewData: [],
    tableChartColumns: { ids: [] },
    sortContainer: { prop: null, orderBy: 'desc' },
    metricsForConvergeMap: {},
    asyncDataCache: new Map(),
    abortControllerQueue: new Set(),
    metricControllers: new Map(),
    resourceType: 'pod',
    $nextTick: () => Promise.resolve(),
    calculateRollingBoundary: () => 1,
    formatTableData: () => new Map(),
    removeScrollListener() {},
    renderTableBatchByBatch: (...args) => mutations.push(args),
  });
  return { subject, requests, metrics, mutations };
}

test('a replacement query supersedes an active scroll request and owns loading', async () => {
  const { subject, requests } = table();
  subject.tableLoading.loading = false;
  const scroll = subject.getK8sList({ needIncrement: true });
  await tick();
  assert.equal(subject.tableLoading.scrollLoading, true);
  subject.queryKey = 'cluster-b';
  subject.filterCommonParams.bcs_cluster_id = 'b';
  const latest = subject.getK8sList({ needRefresh: true });
  await tick();
  assert.equal(requests.length, 2);
  assert.equal(requests[0].signal.aborted, true);
  requests[0].resolve(response('old'));
  await scroll;
  assert.equal(subject.tableLoading.loading, true);
  assert.equal(subject.tableData.length, 0);
  requests[1].resolve(response('new'));
  await latest;
  assert.equal(subject.tableData[0].pod, 'new');
  assert.equal(subject.tableLoading.loading, false);
  assert.equal(subject.tableLoading.scrollLoading, false);
});

test('background refresh keeps rows, and failure does not turn retained rows into an empty state', async () => {
  const { subject, requests } = table();
  subject.loadedQueryKey = subject.queryKey;
  subject.tableData = response('retained').items;
  const pending = subject.getK8sList({ needRefresh: true });
  await tick();
  assert.equal(subject.showSkeleton, false);
  assert.equal(subject.tableData[0].pod, 'retained');
  requests[0].reject(new Error('offline'));
  await pending;
  assert.equal(subject.tableData[0].pod, 'retained');
  assert.equal(subject.loadError, true);
  assert.equal(subject.tableLoading.loading, false);
});

test('a failed different query cannot display the previous query rows', async () => {
  const { subject, requests } = table();
  subject.loadedQueryKey = 'old-query';
  subject.tableData = response('old').items;
  const pending = subject.getK8sList();
  await tick();
  assert.equal(subject.showSkeleton, true);
  requests[0].reject(new Error('offline'));
  await pending;
  assert.equal(subject.tableData.length, 0);
  assert.equal(subject.tableLoading.loading, false);
});

test('empty metric metadata still allows resource-only rows; missing clusters finish loading', async () => {
  const { subject, requests } = table();
  const pending = subject.getK8sList();
  await tick();
  assert.equal(requests.length, 1);
  requests[0].resolve({ count: 0, items: [] });
  await pending;
  assert.equal(subject.tableLoading.loading, false);
  subject.filterCommonParams.bcs_cluster_id = '';
  subject.tableLoading.loading = true;
  await subject.getK8sList();
  assert.equal(subject.tableLoading.loading, false);
  assert.equal(subject.tableDataTotal, 0);
});

test('pending metadata gates resource requests, independently of an empty metadata result', async () => {
  const { subject, requests } = table();
  subject.metricLoading = true;
  await subject.getK8sList();
  assert.equal(requests.length, 0);
  assert.equal(subject.showSkeleton, true);
});

test('cancelled metric callbacks cannot mutate replacement rows, but current failures settle their cells', async () => {
  const { subject, metrics, mutations } = table();
  subject.tableChartColumns.ids = ['cpu'];
  const params = new Map([['cpu', { ids: new Set(['pod']), indexForId: { pod: [0] } }]]);
  subject.loadAsyncData('pod', params);
  subject.abortAsyncData();
  subject.requestId++;
  metrics[0].reject(new Error('canceled'));
  await tick();
  assert.equal(mutations.length, 0);
  subject.loadAsyncData('pod', params);
  metrics[1].reject(new Error('offline'));
  await tick();
  assert.equal(mutations.length, 1);
  assert.equal(mutations[0][1].length, 0);
});

test('changing a column aggregation aborts the older request for that column', async () => {
  const { subject, metrics, mutations } = table();
  const params = new Map([['cpu', { ids: new Set(['pod']), indexForId: { pod: [0] } }]]);
  subject.loadAsyncData('pod', params, ['cpu']);
  subject.loadAsyncData('pod', params, ['cpu']);
  assert.equal(metrics[0].signal.aborted, true);
  metrics[0].resolve([{ cpu: 'old' }]);
  metrics[1].resolve([{ cpu: 'new' }]);
  await tick();
  assert.equal(mutations.length, 1);
  assert.equal(mutations[0][1][0].cpu, 'new');
});

test('leaving invalidates pending table data and aborts requests', async () => {
  const { subject, requests } = table();
  const pending = subject.getK8sList();
  await tick();
  subject.beforeDestroy();
  requests[0].resolve(response('late'));
  await pending;
  assert.equal(requests[0].signal.aborted, true);
  assert.equal(subject.tableData.length, 0);
});

test('debouncing invalidates old requests immediately, before the new request is sent', async () => {
  const { subject, requests } = table();
  const pending = subject.getK8sList();
  await tick();
  subject.debounceGetK8sList();
  requests[0].resolve(response('late'));
  await pending;
  assert.equal(subject.tableData.length, 0);
  assert.equal(subject.tableLoading.loading, true);
  subject.beforeDestroy();
});

test('scroll end is ignored while busy and only actual scrolling requests show footer loading', () => {
  const { subject } = table();
  subject.tableDataTotal = 100;
  subject.tableViewData = [{ pod: 'a' }];
  subject.handleTableScrollEnd();
  assert.equal(subject.pagination.page, 1);
  assert.equal(subject.tableHasScrollLoading, false);
  subject.tableLoading.loading = false;
  subject.tableLoading.scrollLoading = true;
  subject.handleTableScrollEnd();
  assert.equal(subject.pagination.page, 1);
  assert.equal(subject.tableHasScrollLoading, true);
});

function charts() {
  const requests = [];
  const proto = methods(chartFile, ['loadPanels', 'showSkeleton', 'beforeDestroy'], {
    K8SPerformanceMetricUnitMap: {},
  });
  const subject = Object.assign(Object.create(proto), {
    requestId: 0,
    disposed: false,
    queryKey: 'new',
    loadedQueryKey: '',
    metricLoading: false,
    filterCommonParams: { bcs_cluster_id: 'a' },
    metricList: [{ id: 'cpu', name: 'CPU', children: [{ id: 'usage', show_chart: true }] }],
    panels: [],
    hideMetrics: [],
    loading: true,
    isDetailMode: false,
    method: 'sum',
    groupByField: 'pod',
    scene: 'performance',
    activeMetricId: '',
    k8sChartTargetsCreateTool: { createTargetsPanelList: () => [] },
    $nextTick: () => Promise.resolve(),
    onActiveMetricIdChange() {},
    getResourceList: () => {
      const request = deferred();
      requests.push(request);
      return request.promise;
    },
  });
  return { subject, requests };
}
const resources = name => ({ resourceMap: new Map([['pod', name]]), resourceList: new Set([{ pod: name }]) });

test('late chart resources cannot replace newer resources or finish the current loading', async () => {
  const { subject, requests } = charts();
  const first = subject.loadPanels();
  const second = subject.loadPanels();
  requests[0].resolve(resources('old'));
  await first;
  assert.equal(subject.loading, true);
  requests[1].resolve(resources('new'));
  await second;
  assert.equal(subject.resourceMap.get('pod'), 'new');
  assert.equal(subject.loading, false);
});

test('empty metadata, empty resources and all-hidden charts end skeletons', async () => {
  for (const kind of ['metadata', 'resources', 'hidden']) {
    const { subject, requests } = charts();
    if (kind === 'metadata') subject.metricList = [];
    if (kind === 'hidden') subject.hideMetrics = ['usage'];
    const pending = subject.loadPanels();
    if (requests.length)
      requests[0].resolve(kind === 'resources' ? { resourceMap: new Map(), resourceList: new Set() } : resources('a'));
    await pending;
    assert.equal(subject.loading, false);
    assert.equal(subject.showSkeleton, false);
    assert.equal(subject.panels.length, 0);
  }
});

test('chart request failures and unmounts settle without publishing invalid data', async () => {
  const { subject, requests } = charts();
  const pending = subject.loadPanels();
  requests[0].reject(new Error('offline'));
  await pending;
  assert.equal(subject.loadError, true);
  assert.equal(subject.loading, false);
  const next = subject.loadPanels();
  subject.beforeDestroy();
  requests[1].resolve(resources('late'));
  await next;
  assert.equal(subject.panels.length, 0);
});

function dimensions() {
  const requests = [];
  class K8sDimension {
    constructor(params) {
      this.params = params;
      this.showDimensionData = [];
    }
    init() {
      const request = { ...deferred(), dimension: this };
      requests.push(request);
      return request.promise;
    }
  }
  const proto = methods(dimensionFile, ['init', 'handleSearch', 'beforeDestroy', 'showSkeleton'], { K8sDimension });
  const subject = Object.assign(Object.create(proto), {
    initCount: 0,
    disposed: false,
    initializing: false,
    localCommonParams: { bcs_cluster_id: 'a' },
    searchValue: '',
    showDimensionList: [],
    contextKey: 'a',
    loadedContext: '',
    initLoading() {},
  });
  return { subject, requests };
}

test('dimension loading belongs to the latest request and missing cluster is terminal', async () => {
  const { subject, requests } = dimensions();
  const first = subject.init();
  const second = subject.init();
  requests[0].dimension.showDimensionData = ['old'];
  requests[0].resolve();
  await first;
  assert.equal(subject.loading, true);
  assert.equal(subject.showDimensionList.length, 0);
  requests[1].dimension.showDimensionData = ['latest'];
  requests[1].resolve();
  await second;
  assert.equal(subject.showDimensionList[0], 'latest');
  assert.equal(subject.loading, false);
  subject.localCommonParams.bcs_cluster_id = '';
  await subject.init();
  assert.equal(subject.loading, false);
});

test('dimension searches own different instances and old search cannot overwrite newer data', async () => {
  const { subject, requests } = dimensions();
  const first = subject.handleSearch('old');
  const second = subject.handleSearch('new');
  assert.notEqual(requests[0].dimension, requests[1].dimension);
  requests[1].dimension.showDimensionData = ['new'];
  requests[1].resolve();
  await second;
  requests[0].dimension.showDimensionData = ['old'];
  requests[0].resolve();
  await first;
  assert.equal(subject.showDimensionList[0], 'new');
});

test('panel waits for cache restoration before fetching metrics or publishing URL state', async () => {
  const cache = deferred();
  const calls = [];
  const proto = methods(panelFile, ['initialize']);
  const subject = Object.assign(Object.create(proto), {
    initializationId: 0,
    disposed: false,
    initialParams: null,
    queryCacheKey: 'cache',
    cluster: 'a',
    bizId: 1,
    initFilterBy() {},
    getClusterList: async () => {},
    handleGetUserConfig: () => cache.promise,
    applyInitialParams: () => calls.push('cache'),
    getScenarioMetricList: () => calls.push('metrics'),
    handleRefreshChange() {
      this.emitStateChange();
    },
    emitStateChange: () => calls.push('state'),
    $nextTick() {},
  });
  const pending = subject.initialize();
  await tick();
  assert.equal(subject.initializing, true);
  assert.equal(calls.length, 0);
  cache.resolve(undefined);
  await pending;
  assert.equal(subject.initializing, false);
  assert.deepEqual(calls, ['metrics', 'state']);
});

test('changing scenes ignores previous metric metadata and its loading completion', async () => {
  const requests = [];
  const proto = methods(panelFile, ['getScenarioMetricList'], {
    SceneEnum: { Event: 'event' },
    scenarioMetricList: () => {
      const request = deferred();
      requests.push(request);
      return request.promise;
    },
  });
  const subject = Object.assign(Object.create(proto), {
    metricRequestId: 0,
    scene: 'performance',
    getHideMetrics: async () => {},
  });
  const first = subject.getScenarioMetricList();
  subject.scene = 'network';
  const second = subject.getScenarioMetricList();
  requests[0].resolve([{ id: 'old', children: [] }]);
  await first;
  assert.equal(subject.metricLoading, true);
  assert.equal(subject.metricList.length, 0);
  requests[1].resolve([{ id: 'new', children: [] }]);
  await second;
  assert.equal(subject.metricList[0].id, 'new');
  assert.equal(subject.metricLoading, false);
});

test('event scenes invalidate previous metric requests and do not leave metricLoading enabled', async () => {
  const request = deferred();
  const proto = methods(panelFile, ['getScenarioMetricList'], {
    SceneEnum: { Event: 'event' },
    scenarioMetricList: () => request.promise,
  });
  const subject = Object.assign(Object.create(proto), {
    metricRequestId: 0,
    scene: 'performance',
    getHideMetrics: async () => {},
  });
  const old = subject.getScenarioMetricList();
  subject.scene = 'event';
  await subject.getScenarioMetricList();
  request.resolve([{ id: 'late', children: [] }]);
  await old;
  assert.equal(subject.metricList.length, 0);
  assert.equal(subject.metricLoading, false);
});

function filters() {
  const requests = [];
  class FilterByOptions {
    constructor(params) {
      this.commonParams = params;
      this.dimensionData = [];
      this.pageMap = {};
    }
    search(value) {
      const request = { ...deferred(), source: this, value };
      requests.push(request);
      return request.promise;
    }
  }
  const proto = methods(filterFile, ['forkOptions', 'handleSearchChange'], {
    FilterByOptions,
    EDimensionKey: { workload: 'workload' },
  });
  const subject = Object.assign(Object.create(proto), {
    loading: false,
    disposed: false,
    filterByOptions: new FilterByOptions({ bcs_cluster_id: 'a' }),
    addValueSelected: new Map(),
    groupSelected: 'pod',
    groupOptions: [],
    allOptions: [],
    initNextPage: async function (_group, _category, source) {
      this.allOptions = source.dimensionData;
    },
    handleSelectGroup() {},
  });
  return { subject, requests };
}

test('filter searches isolate mutable option models and old completion cannot clear current loading', async () => {
  const { subject, requests } = filters();
  const first = subject.handleSearchChange('old');
  const second = subject.handleSearchChange('new');
  assert.notEqual(requests[0].source, requests[1].source);
  requests[0].source.dimensionData = ['old'];
  requests[0].resolve();
  await first;
  assert.equal(subject.valueLoading, true);
  assert.equal(subject.allOptions.length, 0);
  requests[1].source.dimensionData = ['new'];
  requests[1].resolve();
  await second;
  assert.equal(subject.allOptions[0], 'new');
  assert.equal(subject.valueLoading, false);
});

const graphFile = 'src/monitor-ui/chart-plugins/plugins/k8s-custom-graph/k8s-custom-graph.tsx';
function graph() {
  const requests = [];
  const errors = [];
  const loadingEvents = [];
  const proto = methods(graphFile, ['getPanelData', 'loadPanelData', 'isCurrentDataRequest', 'beforeDestroy'], {
    window: { i18n: { t: value => value } },
    handleTransformToTimestamp: value => value,
    VariablesService: class {
      transformVariables(data) {
        return data;
      }
    },
    CancelToken: class {
      constructor(callback) {
        callback(() => {});
      }
    },
    convertToSeconds: () => 60,
    structuredClone,
  });
  const subject = Object.assign(Object.create(proto), {
    k8sLoadingSkeleton: true,
    dataRequestId: 0,
    disposed: false,
    dataLoading: true,
    chartDataLoaded: false,
    initialized: false,
    empty: true,
    metrics: [],
    cancelTokens: [],
    timeRange: [1, 2],
    timeOffset: [],
    viewOptions: { interval: 'auto' },
    $el: { clientWidth: 500 },
    beforeGetPanelData: async () => true,
    unregisterObserver() {},
    downSampleRangeComputed: () => '60s',
    panel: {
      targets: [
        {
          apiModule: 'k8s',
          apiFunc: 'query',
          data: { query_configs: [{ data_source_label: 'prometheus', promql: 'up' }] },
        },
      ],
      setRawQueryConfigs() {},
    },
    $api: {
      k8s: {
        query() {
          const request = deferred();
          requests.push(request);
          return request.promise;
        },
      },
    },
    clearErrorMsg() {},
    handleErrorMsgChange: value => errors.push(value),
    handleLoadingChange: value => loadingEvents.push(value),
  });
  return { subject, requests, errors, loadingEvents };
}

test('actual time-series loading ignores stale errors and only finishes when the latest query settles', async () => {
  const { subject, requests, errors } = graph();
  const first = subject.loadPanelData(undefined, undefined, ++subject.dataRequestId);
  await tick();
  const latest = subject.loadPanelData(undefined, undefined, ++subject.dataRequestId);
  await tick();
  requests[0].reject(new Error('canceled old query'));
  await first;
  assert.equal(errors.length, 0);
  assert.equal(subject.dataLoading, true);
  assert.equal(subject.chartDataLoaded, false);
  requests[1].resolve({ metrics: [], series: [] });
  await latest;
  assert.equal(subject.dataLoading, false);
  assert.equal(subject.chartDataLoaded, true);
  assert.equal(subject.empty, true);
});

test('new chart refresh retains rendered content and emits lightweight loading', async () => {
  const { subject, requests, loadingEvents } = graph();
  subject.chartDataLoaded = true;
  subject.initialized = true;
  subject.empty = false;
  subject.options = { series: ['retained'] };
  const pending = subject.loadPanelData(undefined, undefined, ++subject.dataRequestId);
  await tick();
  assert.equal(subject.empty, false);
  assert.equal(subject.options.series[0], 'retained');
  assert.equal(loadingEvents[0], true);
  requests[0].resolve({ metrics: [], series: [] });
  await pending;
  assert.equal(loadingEvents.at(-1), false);
});

test('closing a chart prevents late time-series responses from completing its loading', async () => {
  const { subject, requests, loadingEvents } = graph();
  const pending = subject.loadPanelData(undefined, undefined, ++subject.dataRequestId);
  await tick();
  subject.beforeDestroy();
  requests[0].resolve({ metrics: [], series: [] });
  await pending;
  assert.equal(subject.chartDataLoaded, false);
  assert.equal(loadingEvents.length, 0);
});

test('request invalidation happens before the graph debounce and is opt-in for existing consumers', () => {
  const { subject } = graph();
  let cancelled = false;
  let queuedId;
  subject.cancelTokens = [
    () => {
      cancelled = true;
    },
  ];
  subject.loadPanelData = (_start, _end, id) => {
    queuedId = id;
  };
  subject.getPanelData();
  assert.equal(cancelled, true);
  assert.equal(queuedId, 1);
  assert.equal(subject.isCurrentDataRequest(0), false);
  subject.k8sLoadingSkeleton = false;
  assert.equal(subject.isCurrentDataRequest(0), true);
});

test('refresh displays cached metric values while still scheduling fresh values', () => {
  const proto = methods(tableFile, ['formatTableData', 'getResourceId'], {
    K8sTableColumnKeysEnum: { CONTAINER: 'container', WORKLOAD: 'workload' },
  });
  const cached = { datapoints: [[42, 1]] };
  const subject = Object.assign(Object.create(proto), {
    tableChartColumns: { ids: ['cpu'] },
    asyncDataCache: new Map([['cpu', { pod: cached }]]),
    $tc: value => value,
  });
  const rows = [{ pod: 'pod' }];
  const pending = subject.formatTableData(rows, 'pod', undefined, true);
  assert.equal(rows[0].cpu, cached);
  assert.equal(pending.get('cpu').ids.has('pod'), true);
  const incremental = subject.formatTableData([{ pod: 'pod' }], 'pod');
  assert.equal(incremental.size, 0);
});

test('failed refresh releases cells whose previous metric requests were cancelled', async () => {
  const { subject, requests } = table();
  subject.loadedQueryKey = subject.queryKey;
  subject.tableChartColumns.ids = ['cpu'];
  subject.tableData = [{ pod: 'a', cpu: { datapoints: null } }];
  const pending = subject.getK8sList({ needRefresh: true });
  await tick();
  requests[0].reject(new Error('offline'));
  await pending;
  assert.equal(subject.tableData[0].cpu.datapoints.length, 0);
  assert.equal(subject.tableLoading.loading, false);
});

test('failed time-series refresh preserves a previously rendered chart and releases loading', async () => {
  const { subject, requests, errors, loadingEvents } = graph();
  subject.chartDataLoaded = true;
  subject.empty = false;
  const pending = subject.loadPanelData(undefined, undefined, ++subject.dataRequestId);
  await tick();
  requests[0].reject(new Error('offline'));
  await pending;
  assert.equal(subject.empty, false);
  assert.equal(subject.dataLoading, false);
  assert.equal(errors.length, 1);
  assert.equal(loadingEvents.at(-1), false);
});

const h = (tag, props, ...children) => ({ tag, props: props || {}, children: children.flat().filter(Boolean) });
const findNodes = (node, match) =>
  [node, ...(node.children || []).flatMap(child => findNodes(child, match))].filter(match);

test('metric initialization retains the same chart container and gates requests until metadata is ready', () => {
  const proto = methods(panelFile, ['tabContentRender'], {
    h,
    K8SCharts: 'charts',
    K8sLoading: 'loading',
    K8sEmptyStatus: 'empty',
    K8sTableNew: 'table',
    K8sNewTabEnum: { CHART: 'chart' },
  });
  const subject = Object.assign(Object.create(proto), {
    initializing: true,
    metricLoading: false,
    clusterError: false,
    metricError: false,
    isChart: true,
    activeTab: 'chart',
    cluster: '',
    handleTableClearSearch() {},
  });
  const initial = subject.tabContentRender();
  assert.equal(initial.tag, 'charts');
  assert.equal(initial.props.metricLoading, true);
  subject.initializing = false;
  subject.cluster = 'cluster';
  subject.metricLoading = true;
  assert.equal(subject.tabContentRender().tag, initial.tag);
  subject.metricLoading = false;
  assert.equal(subject.tabContentRender().tag, initial.tag);
  assert.equal(subject.tabContentRender().props.metricLoading, false);
  assert.equal(subject.tabContentRender().props.onClearSearch, subject.handleTableClearSearch);
  subject.cluster = '';
  assert.equal(subject.tabContentRender().props.type, 'empty');
  subject.metricError = true;
  assert.equal(subject.tabContentRender().props.type, '500');
});

test('metadata loading and time-series loading render the same simple chart placeholder', () => {
  const proto = methods(`${base}k8s-loading/k8s-loading.tsx`, ['render', 'renderChartPlaceholder'], { h });
  const subject = Object.assign(Object.create(proto), { type: 'charts', $t: value => value });
  const matches = node => node.props?.class === 'loading-chart-placeholder';
  const initial = findNodes(subject.render(), matches);
  subject.type = 'chart';
  const series = findNodes(subject.render(), matches);
  assert.equal(initial.length, 2);
  assert.equal(series.length, 1);
  for (const placeholder of initial) assert.deepEqual(placeholder, series[0]);
});

test('unified empty state keeps all status texts and forwards retry/clear operations', () => {
  const defaultTextMap = { empty: '查无数据', 'search-empty': '搜索结果为空', 500: '数据获取异常' };
  const proto = methods(`${base}k8s-empty-status/k8s-empty-status.tsx`, ['render'], {
    h,
    EmptyStatus: 'empty-status',
    defaultTextMap,
  });
  const events = [];
  const subject = Object.assign(Object.create(proto), {
    $t: value => value,
    $emit: (...args) => events.push(args),
    showOperation: true,
    compact: false,
  });
  for (const [type, text] of Object.entries({ ...defaultTextMap, empty: '暂无数据' })) {
    subject.type = type;
    const rendered = subject.render();
    assert.equal(rendered.props.textMap[rendered.props.type], text);
    rendered.props.onOperation(type === '500' ? 'refresh' : 'clear-filter');
  }
  assert.equal(events[0][0], 'operation');
  assert.ok(events.some(([, type]) => type === 'refresh'));
  assert.ok(events.some(([, type]) => type === 'clear-filter'));
});

test('charts and both table tabs agree on empty/search-empty, and retry does not clear filters', () => {
  const chartProto = methods(chartFile, ['emptyType', 'handleEmptyOperation']);
  const tableProto = methods(tableFile, ['tableEmptyType']);
  const events = [];
  const chart = Object.assign(Object.create(chartProto), {
    loadError: false,
    metricList: [{ id: 'cpu' }],
    resourceList: new Set(),
    filterCommonParams: { filter_dict: {} },
    createPanelList: () => events.push('retry'),
    $emit: event => events.push(event),
  });
  const table = Object.assign(Object.create(tableProto), { filterBy: {} });
  assert.equal(chart.emptyType, table.tableEmptyType);
  chart.filterCommonParams.filter_dict = table.filterBy = { namespace: ['missing'] };
  assert.equal(chart.emptyType, 'search-empty');
  assert.equal(chart.emptyType, table.tableEmptyType);
  chart.handleEmptyOperation('clear-filter');
  chart.loadError = true;
  assert.equal(chart.emptyType, '500');
  chart.handleEmptyOperation('refresh');
  assert.deepEqual(events, ['clearSearch', 'retry']);
  chart.loadError = false;
  chart.resourceList.add({ namespace: 'exists' });
  assert.equal(chart.emptyType, 'empty');
  chart.metricList = [];
  chart.resourceList.clear();
  assert.equal(chart.emptyType, 'empty');
});

test('time-series failures stay distinct from no data, and successful retry clears the error', async () => {
  const { subject, requests } = graph();
  const first = subject.loadPanelData(undefined, undefined, ++subject.dataRequestId);
  await tick();
  requests[0].reject(new Error('offline'));
  await first;
  assert.equal(subject.chartLoadError, true);
  assert.equal(subject.empty, true);
  const retry = subject.loadPanelData(undefined, undefined, ++subject.dataRequestId);
  await tick();
  requests[1].resolve({ metrics: [], series: [] });
  await retry;
  assert.equal(subject.chartLoadError, false);
  assert.equal(subject.empty, true);
  assert.equal(subject.dataLoading, false);
});

test('filter menu preserves workload categories while loading values and keeps initial/search skeletons consistent', () => {
  const proto = methods(filterFile, ['render', 'renderMenuSkeleton', 'renderValueSkeleton'], { h });
  const subject = Object.assign(Object.create(proto), {
    loading: true,
    valueLoading: false,
    rightValueLoading: false,
    isSelectedWorkload: true,
    tagList: [],
    groupOptions: [{ id: 'workload' }],
    valueCategoryOptions: [],
    tagsWrap: () => [],
    $t: value => value,
    valuesWrap: () => h('loaded-values'),
  });
  const lists = node => Array.isArray(node.props?.class) && node.props.class[0] === 'filter-menu-skeleton-list';
  assert.equal(findNodes(subject.render(), lists).length, 2);
  subject.loading = false;
  subject.valueLoading = true;
  assert.equal(findNodes(subject.render(), lists).length, 2);
  subject.valueCategoryOptions = [{ id: 'deployment', name: 'Deployment', count: 5 }];
  const searching = subject.render();
  assert.equal(findNodes(searching, lists).length, 1);
  assert.equal(findNodes(searching, node => node.props?.class === 'cate-item-name').length, 1);
  assert.equal(findNodes(searching, node => node.tag === 'loaded-values').length, 0);
  subject.valueLoading = false;
  subject.rightValueLoading = true;
  assert.equal(findNodes(subject.render(), lists).length, 1);
  subject.rightValueLoading = false;
  assert.equal(findNodes(subject.render(), node => node.tag === 'loaded-values').length, 1);
  subject.isSelectedWorkload = false;
  subject.valueLoading = true;
  assert.equal(findNodes(subject.render(), lists).length, 1);
  assert.equal(findNodes(subject.render(), node => node.props?.class === 'left-wrap').length, 0);
});

const apmFile = 'src/monitor-pc/pages/monitor-k8s/monitor-k8s-apm.tsx';
function apmPanel() {
  const configs = [],
    metrics = [],
    routes = [],
    targets = [];
  const proto = methods(
    apmFile,
    ['initialize', 'getRouteParams', 'handleTargetListChange', 'setRouteParams', 'tabContentRender', 'beforeDestroy'],
    {
      h,
      K8SCharts: 'charts',
      K8sTableNew: 'table',
      K8sEmptyStatus: 'empty',
      K8sNewTabEnum: { CHART: 'chart' },
      SceneEnum: { Network: 'network' },
      CACHE_APM_SEARCH_QUERY: 'APM_K8S',
      HIDE_METRICS_KEY: 'hidden',
      networkDefaultHideMetrics: [],
      EDimensionKey: { namespace: 'namespace', workload: 'workload', pod: 'pod' },
      K8sTableColumnKeysEnum: { POD: 'pod', WORKLOAD: 'workload' },
      listServiceK8sTargets: (params, options) => {
        const request = { ...deferred(), params, signal: options.signal };
        targets.push(request);
        return request.promise;
      },
      scenarioMetricList: (_params, options) => {
        const request = { ...deferred(), signal: options.signal };
        metrics.push(request);
        return request.promise;
      },
      bus: { $off() {} },
      APM_K8S_CACHE_FLUSH_EVENT: 'flush',
    }
  );
  const subject = Object.assign(Object.create(proto), {
    disposed: false,
    initializing: true,
    metricLoading: true,
    initializationId: 0,
    appName: 'app',
    serviceName: 'service',
    bizId: 2,
    scene: 'performance',
    customRouteQuery: {},
    cluster: '',
    targetList: [],
    selectTarget: '',
    apmResourceType: '',
    initGroupBy() {
      this.groupInstance = {
        groupFilters: [],
        initGroupFilter() {
          this.groupFilters = [];
        },
        addGroupFilter(id) {
          this.groupFilters.push(id);
        },
      };
    },
    initFilterBy() {
      this.filterBy = {};
    },
    handleGetUserConfig: key => {
      const request = { ...deferred(), key };
      configs.push(request);
      return request.promise;
    },
    handleApmK8sNewEventChange: (_event, route) => routes.push(route),
    saveNewTargetValueToUserConfig() {},
  });
  return { subject, targets, metrics, configs, routes };
}
const apmTargets = [
  { bcs_cluster_id: 'a', namespace: 'ns', workload: 'one', resource_type: 'workload' },
  { bcs_cluster_id: 'b', namespace: 'ns', pod: 'two', resource_type: 'pod' },
];

test('APM shows skeletons in all tabs before cluster resolution and waits for cache while requests run in parallel', async () => {
  const { subject, targets, metrics, configs, routes } = apmPanel();
  const pending = subject.initialize();
  assert.equal(targets.length, 1);
  assert.equal(metrics.length, 1);
  assert.equal(configs.length, 2);
  for (const tab of ['chart', 'list', 'detail']) {
    subject.activeTab = tab;
    const view = subject.tabContentRender();
    assert.equal(view.tag, tab === 'chart' ? 'charts' : 'table');
    assert.equal(view.props.metricLoading, true);
  }
  targets[0].resolve({ target_list: apmTargets });
  metrics[0].resolve([{ id: 'cpu', children: [] }]);
  configs[1].resolve([]);
  await tick();
  assert.equal(subject.initializing, true);
  assert.equal(subject.cluster, '');
  assert.equal(routes.length, 0);
  configs[0].resolve({ service: { target: 'b-ns-two' } });
  await pending;
  assert.equal(subject.cluster, 'b');
  assert.equal(subject.filterBy.pod[0], 'two');
  assert.equal(subject.groupInstance.groupFilters[0], 'pod');
  assert.equal(subject.metricLoading, false);
  assert.equal(subject.initializing, false);
  assert.equal(subject.isUserManualSwitch, false);
  assert.ok(routes.every(route => route.selectTarget.target === 'b-ns-two'));
});

test('APM restores URL targets without reading target cache and applies fallback targets explicitly', async () => {
  for (const target of ['b-ns-two', 'missing']) {
    const { subject, targets, metrics, configs } = apmPanel();
    subject.customRouteQuery = { apmK8sParams: JSON.stringify({ selectTarget: { target } }) };
    const pending = subject.initialize();
    assert.equal(configs.length, 1);
    targets[0].resolve({ target_list: apmTargets });
    metrics[0].resolve([]);
    configs[0].reject(new Error('optional config unavailable'));
    await pending;
    assert.equal(subject.cluster, target === 'missing' ? 'a' : 'b');
    assert.equal(subject.initializationError, false);
    assert.equal(subject.initializing, false);
  }
});

test('APM empty targets settle as empty in all tabs without invalid target access or URL writes', async () => {
  const { subject, targets, metrics, configs, routes } = apmPanel();
  const pending = subject.initialize();
  targets[0].resolve({ target_list: [] });
  metrics[0].resolve([]);
  configs.forEach(request => request.resolve(null));
  await pending;
  assert.equal(subject.initializationError, false);
  assert.equal(subject.initializing, false);
  assert.equal(routes.length, 0);
  for (const tab of ['chart', 'list', 'detail']) {
    subject.activeTab = tab;
    assert.equal(subject.tabContentRender().props.type, 'empty');
  }
});

test('APM initialization failure exposes retry and successful retry releases skeletons', async () => {
  const { subject, targets, metrics, configs } = apmPanel();
  const first = subject.initialize();
  targets[0].reject(new Error('offline'));
  await first;
  assert.equal(subject.tabContentRender().props.type, '500');
  assert.equal(subject.tabContentRender().props.onOperation, subject.initialize);
  assert.equal(metrics[0].signal.aborted, true);
  const retry = subject.initialize();
  targets[1].resolve({ target_list: apmTargets });
  metrics[1].resolve([]);
  configs.slice(2).forEach(request => request.resolve(null));
  await retry;
  assert.equal(subject.initializationError, false);
  assert.equal(subject.cluster, 'a');
  assert.equal(subject.initializing, false);
});

test('APM service changes and unmount prevent stale initialization from publishing data or clearing current loading', async () => {
  const { subject, targets, metrics, configs, routes } = apmPanel();
  const first = subject.initialize();
  subject.serviceName = 'next';
  const next = subject.initialize();
  assert.equal(targets[0].signal.aborted, true);
  targets[0].resolve({ target_list: apmTargets });
  metrics[0].resolve([]);
  configs.slice(0, 2).forEach(request => request.resolve(null));
  await first;
  assert.equal(subject.initializing, true);
  assert.equal(subject.cluster, '');
  assert.equal(routes.length, 0);
  subject.beforeDestroy();
  targets[1].resolve({ target_list: apmTargets });
  metrics[1].resolve([]);
  configs.slice(2).forEach(request => request.resolve(null));
  await next;
  assert.equal(targets[1].signal.aborted, true);
  assert.equal(subject.cluster, '');
  assert.equal(routes.length, 0);
});

test('APM waits for injected service context without sending incomplete requests', async () => {
  const { subject, targets } = apmPanel();
  subject.serviceName = '';
  await subject.initialize();
  assert.equal(targets.length, 0);
  assert.equal(subject.initializing, true);
  assert.equal(subject.metricLoading, true);
});

test('APM programmatic select changes do not reset restored dimensions or mark manual selection', () => {
  const { subject } = apmPanel();
  subject.initGroupBy();
  subject.targetList = apmTargets.map(item => ({
    ...item,
    cacheId: `${item.bcs_cluster_id}-${item.namespace}-${item.pod || item.workload}`,
  }));
  subject.isUserManualSwitch = false;
  subject.getRouteParams({ target: 'b-ns-two' });
  const dimensions = subject.groupInstance.groupFilters;
  subject.initializing = false;
  subject.handleTargetListChange('b-ns-two');
  assert.equal(subject.groupInstance.groupFilters, dimensions);
  assert.equal(subject.isUserManualSwitch, false);
  subject.handleTargetListChange('a-ns-one');
  assert.equal(subject.cluster, 'a');
  assert.equal(subject.isUserManualSwitch, true);
});

test('APM parent renders tab content on the first frame even without a cluster', () => {
  const proto = methods(apmFile, ['render'], {
    h,
    FilterByCondition: 'filters',
    GroupByCondition: 'groups',
    K8sNewTabEnum: { CHART: 'chart' },
    tabList: [],
  });
  const subject = Object.assign(Object.create(proto), {
    cluster: '',
    initializing: true,
    showGuidePage: false,
    $t: value => value,
    $tc: value => value,
    renderTargetListSelect: () => h('target-select'),
    tabContentRender: () => h('pending-tab-content'),
  });
  assert.equal(findNodes(subject.render(), node => node.tag === 'pending-tab-content').length, 1);
});
