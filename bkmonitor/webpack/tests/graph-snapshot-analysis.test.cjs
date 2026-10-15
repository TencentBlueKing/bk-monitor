const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');
const base = path.join(__dirname, '../src/trace/pages/failure/failure-topo');
function load(file) {
  const code = ts.transpileModule(fs.readFileSync(path.join(base, file), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText;
  const module = { exports: {} };
  new Function('require', 'module', 'exports', code)(require, module, module.exports);
  return module.exports;
}
const { snapshotMetrics, snapshotEvents, allowsRealtimeMetrics, allowsRealtimeEvents, topologyEdgeId } =
  load('snapshot-analysis.ts');
const analysis = (evidence = []) => ({
  protocol: 'graph-rca-snapshot',
  version: '1',
  evidence,
  capabilities: { realtime_metrics: false },
});
const metric = (name, value, dimensions = []) => ({
  evidence_id: name,
  evidence_type: 'metric',
  evidence_descriptor: { name, kind: 'metric' },
  unit: 'percent',
  response: { meta: { status: 'OK' }, data: [{ time: 1700000000000, value, dimensions }] },
});

test('CPU and memory remain distinguishable and preserve values, units and dimensions', () => {
  const value = analysis([metric('cpu', 0), metric('mem', 34), metric('cpu', 12, [{ pod: 'second' }])]);
  const frozen = JSON.stringify(value);
  const result = snapshotMetrics(value);
  assert.deepEqual(
    result.map(item => item.metric_name),
    ['cpu', 'mem', 'cpu']
  );
  assert.deepEqual(result[0].time_series.default.datapoints, [[1700000000000, 0, 0]]);
  assert.equal(result[0].time_series.default.unit, 'percent');
  assert.equal(result[2].display_by_dimensions, true);
  assert.equal(JSON.stringify(value), frozen);
});

test('missing, failed, NO_DATA or invalid points never become fabricated zero metrics', () => {
  const noData = metric('cpu', 2);
  noData.response.meta.status = 'NO_DATA';
  const failed = metric('mem', 2);
  failed.response.meta.status = 'QUERY_FAILED';
  const invalid = metric('disk', null);
  assert.deepEqual(snapshotMetrics(analysis([noData, failed, invalid])), []);
  assert.deepEqual(snapshotMetrics(analysis()), []);
  assert.equal(snapshotMetrics(null), null);
  assert.equal(allowsRealtimeMetrics(analysis()), false);
  assert.equal(allowsRealtimeMetrics(null), true);
  assert.equal(
    allowsRealtimeMetrics({ ...analysis(), version: 'future', capabilities: { realtime_metrics: true } }),
    false
  );
  assert.equal(allowsRealtimeMetrics({ ...analysis(), capabilities: { realtime_metrics: true } }), true);
});

test('partial metric series preserve null gaps instead of turning them into zero', () => {
  const value = metric('cpu', 0);
  value.response.data.push({ time: 1700000060000, value: null, label: null });
  value.response.data.push({ time: 1700000120000, value: 5 });
  const result = snapshotMetrics(analysis([value]));
  assert.deepEqual(result[0].time_series.default.datapoints, [
    [1700000000000, 0, 0],
    [1700000060000, null, 0],
    [1700000120000, 5, 0],
  ]);
});

test('parallel relationship edge identifiers are distinct and stable without concatenation collisions', () => {
  const first = { source: 'ab', target: 'c', edge_type: 'dependency' };
  const second = { source: 'a', target: 'bc', edge_type: 'dependency' };
  assert.notEqual(topologyEdgeId(first), topologyEdgeId(second));
  assert.notEqual(topologyEdgeId(first), topologyEdgeId({ ...first, edge_type: 'spread' }));
  assert.equal(topologyEdgeId({ ...first, properties: { edge_id: 'frozen-edge' } }), 'frozen-edge');
});

const vue = require('vue');
const { renderToString } = require('vue/server-renderer');
function loadView(file, overrides = {}) {
  const source = fs.readFileSync(path.join(base, file), 'utf8');
  const code = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020,
      jsx: ts.JsxEmit.React,
      jsxFactory: 'h',
    },
  }).outputText;
  const module = { exports: {} };
  const deps = {
    vue,
    'vue-i18n': { useI18n: () => ({ t: value => value }) },
    '../snapshot-analysis': {
      snapshotMetrics,
      snapshotEvents,
      allowsRealtimeMetrics,
      allowsRealtimeEvents,
      topologyEdgeId,
    },
    ...overrides,
  };
  new Function('require', 'module', 'exports', 'h', code)(id => deps[id] || require(id), module, module.exports, vue.h);
  return module.exports;
}

test('actual sidebar renders candidate rank and original score semantics, preserving zero', async () => {
  const component = loadView('detail/snapshot-analysis-info.tsx').default;
  const app = vue.createSSRApp({
    render: () =>
      vue.h(component, {
        analysis: {
          ...analysis(),
          producer: { engine: 'graph_walk' },
          root_causes: [
            {
              entity_ref: 'a',
              rank: 1,
              scores: [
                { kind: 'legacy_anomaly_score', value: 0, method: 'graph_walk' },
                { kind: 'custom_score', value: 2 },
              ],
              reason: ['cause evidence', 'second explanation'],
            },
          ],
        },
      }),
  });
  const html = await renderToString(app);
  assert.match(html, /候选排名/);
  assert.match(html, /原始异常评分：0/);
  assert.match(html, /custom_score：2/);
  assert.match(html, /图谱游走/);
  assert.match(html, /cause evidence/);
  assert.match(html, /second explanation/);
  assert.doesNotMatch(html, /置信度/);
});

test('small-model path membership is shown as a marker, not confidence or probability', async () => {
  const component = loadView('detail/snapshot-analysis-info.tsx').default;
  const app = vue.createSSRApp({
    render: () =>
      vue.h(component, {
        analysis: { ...analysis(), producer: { engine: 'graph_causal_rca' } },
        scores: [{ kind: 'propagation_path_membership', value: 1, method: 'graph_causal_rca' }],
      }),
  });
  const html = await renderToString(app);
  assert.match(html, /传播路径标记：1/);
  assert.match(html, /小模型图谱RCA/);
  assert.doesNotMatch(html, /置信度|概率/);
});

test('actual layout adapter keeps separate edges between identical endpoints', () => {
  const layout = loadView('graph/elkjs-utils.ts').default;
  const edges = ['owns', 'calls'].map(id => ({ id, source: 'a', target: 'b', edge_type: 'spread' }));
  const projected = layout.getTopoRawData([], edges, []);
  assert.deepEqual(
    projected.edges.map(edge => edge.id),
    ['owns', 'calls']
  );
});

test('nodes without a subgroup stay in their root group and complete actual ELK layout', async () => {
  const layout = loadView('graph/elkjs-utils.ts').default;
  const format = loadView('graph/format-topo-data.ts').default;
  const nodes = ['a', 'b'].map(id => ({ id, comboId: 'service', subComboId: null, width: 90, height: 92 }));
  layout.setSubCombosMap(layout.getSubComboCountMap(nodes));
  const projected = layout.getTopoRawData([{ id: 'service' }], [{ id: 'calls', source: 'a', target: 'b' }], nodes);
  assert.deepEqual(
    projected.nodes.map(node => node.comboId),
    ['service', 'service']
  );
  const formatted = format(projected);
  const result = await layout.getLayoutData(
    layout.getKlayGraphData({ nodes: formatted.layoutNodes, edges: formatted.edges })
  );
  layout.updatePositionFromLayouted(result, projected);
  assert.ok(projected.nodes.every(node => Number.isFinite(node.x) && Number.isFinite(node.y)));
});

test('empty topology history and refresh are safe, and sidebar edges keep their frozen identity', async () => {
  const requests = [];
  const layout = loadView('graph/elkjs-utils.ts').default;
  const { useTopoData } = loadView('composables/use-topo-data.ts', {
    'monitor-api/modules/incident': {
      incidentTopology: async params => {
        requests.push(params);
        return {
          latest: { nodes: [], edges: [], combos: [], sub_combos: [] },
          diff: [],
          complete: { nodes: [], edges: [], sub_combos: [] },
          status: 'NO_DATA',
          message: 'no snapshot',
        };
      },
    },
    'monitor-common/utils/utils.js': { deepClone: value => JSON.parse(JSON.stringify(value)) },
    '../graph/elkjs-utils': { default: layout },
    '../graph/format-topo-data': { default: () => ({}) },
  });
  const state = {
    loading: vue.ref(false),
    wrapRef: vue.ref({}),
    incidentId: vue.ref('1700000000000001'),
    errorData: vue.ref({}),
    timelinePosition: vue.ref(0),
    refreshTime: vue.ref(-1),
    resourceNodeId: vue.ref(''),
    nodeEntityId: vue.ref(''),
    nodeEntityName: vue.ref(''),
  };
  const hook = useTopoData(state, { getGraph: () => null });
  await hook.getGraphData();
  assert.equal(state.errorData.value.isNoData, true);
  assert.equal(state.timelinePosition.value, 0);
  await hook.getGraphData(true);
  assert.equal(requests[1].start_time, '1700000000');
  const frame = { create_time: 100, content: {} };
  hook.topoRawDataCache.value.diff = [frame];
  await hook.getGraphData(true);
  assert.equal(requests[2].start_time, 101);
  assert.deepEqual(hook.topoRawDataCache.value.diff, [frame]);
  const edge = {
    id: 'frozen-edge',
    source: 'a',
    target: 'b',
    edge_type: 'spread',
    graph_analysis: analysis([metric('errors', 3)]),
    properties: {},
  };
  const result = hook.filterEdges([edge], [], 'a');
  assert.equal(result[0].id, 'frozen-edge');
  assert.equal(result[0].graph_analysis.evidence[0].evidence_descriptor.name, 'errors');
});

test('actual metric hook shows frozen evidence and never requests live metrics or events', async () => {
  let requests = 0;
  const useMetrics = loadView('detail/useMetrics.ts', {
    'monitor-api/modules/incident': {
      incidentMetricsSearch: async () => {
        requests++;
        throw new Error('unexpected live metric query');
      },
      incidentEventsSearch: async () => {
        requests++;
        throw new Error('unexpected live event query');
      },
    },
    '../utils': {
      handleEndTime: () => {
        throw new Error('snapshot must not use live time');
      },
      scaleArrayToRange: () => [],
    },
    'monitor-ui/monitor-echarts/types/monitor-echarts': { echarts: { disconnect() {}, connect() {} } },
    'throttle-debounce': { debounce: (_delay, fn) => fn },
  }).default;
  let hook;
  const saved = vue.shallowRef(analysis([metric('cpu', 42)]));
  const app = vue.createSSRApp({
    setup() {
      hook = useMetrics(
        vue.shallowRef({}),
        vue.shallowRef('node'),
        vue.shallowRef(-1),
        vue.shallowRef(true),
        () => {},
        vue.shallowRef([]),
        saved
      );
      return () => vue.h('div');
    },
  });
  app.provide('incidentDetail', vue.shallowRef({ begin_time: 1, end_time: 2 }));
  await renderToString(app);
  await hook.getMetricsData();
  await hook.getEventsData();
  assert.equal(requests, 0);
  assert.equal(hook.metricsData.value[0].metric_name, 'cpu');
  assert.equal(hook.metricsData.value[0].time_series.default.datapoints[0][1], 42);
  saved.value = analysis();
  await hook.getMetricsData();
  assert.deepEqual(hook.metricsData.value, []);
  assert.equal(hook.exceptionData.value.msg, '该分析快照未提供指标数据');
  assert.equal(hook.eventDataMessage.value, '本快照未提供事件数据');
  assert.equal(requests, 0);
});

test('frozen events use actual records, with metric and event live capabilities independent', () => {
  const event = {
    evidence_id: 'event-a',
    evidence_type: 'event',
    evidence_descriptor: { kind: 'event', name: 'k8s-events', source: 'k8s' },
    response: {
      meta: { status: 'OK' },
      data: [
        { time: 1700000000000, event_name: 'BackOff', event_level: 'warning' },
        { time: 1700000001000, event_name: 'BackOff' },
      ],
    },
  };
  const frozen = analysis([event]);
  const result = snapshotEvents(frozen, '未提供');
  assert.deepEqual(result.statistics, { event_source: { k8s: 2 }, event_level: { warning: 1, 未提供: 1 } });
  assert.equal(result.events[0].event_name, 'BackOff');
  assert.deepEqual(result.events[0].series[0].datapoints, [[1700000000000, 1]]);
  assert.equal(snapshotEvents(null, '未提供'), null);
  assert.equal(allowsRealtimeEvents(null), true);
  assert.equal(allowsRealtimeEvents(analysis()), false);
  assert.equal(allowsRealtimeEvents({ ...analysis(), capabilities: { realtime_metrics: true } }), false);
  assert.equal(allowsRealtimeMetrics({ ...analysis(), capabilities: { realtime_events: true } }), false);
  assert.equal(allowsRealtimeEvents({ ...analysis(), capabilities: { realtime_events: true } }), true);
  assert.equal(
    allowsRealtimeEvents({ ...analysis(), version: 'future', capabilities: { realtime_events: true } }),
    false
  );
});

test('actual hook event capability can query events without granting a metric query', async () => {
  let metricRequests = 0;
  let eventRequests = 0;
  const store = new Map();
  global.localStorage = { getItem: key => store.get(key) || null, setItem: (key, value) => store.set(key, value) };
  const useMetrics = loadView('detail/useMetrics.ts', {
    'monitor-api/modules/incident': {
      incidentMetricsSearch: async () => {
        metricRequests++;
        return { metrics: {} };
      },
      incidentEventsSearch: async () => {
        eventRequests++;
        return {
          statistics: { event_source: {}, event_level: {} },
          events: [],
        };
      },
    },
    '../utils': { handleEndTime: (_begin, end) => end, scaleArrayToRange: values => values },
    'monitor-ui/monitor-echarts/types/monitor-echarts': { echarts: { disconnect() {}, connect() {} } },
    'throttle-debounce': { debounce: (_delay, fn) => fn },
  }).default;
  const saved = vue.shallowRef({ ...analysis(), capabilities: { realtime_events: true } });
  let hook;
  const app = vue.createSSRApp({
    setup() {
      hook = useMetrics(
        vue.shallowRef({}),
        vue.shallowRef('node'),
        vue.shallowRef(-1),
        vue.shallowRef(true),
        () => {},
        vue.shallowRef([]),
        saved
      );
      return () => vue.h('div');
    },
  });
  app.provide('incidentDetail', vue.shallowRef({ begin_time: 1, end_time: 601 }));
  await renderToString(app);
  await hook.getMetricsData();
  await hook.getEventsData();
  assert.equal(metricRequests, 0);
  assert.equal(eventRequests, 1);
  assert.equal(hook.endTime.value, 601);
  saved.value = { ...analysis(), capabilities: { realtime_metrics: true } };
  await hook.getMetricsData();
  await hook.getEventsData();
  assert.equal(metricRequests, 1);
  assert.equal(eventRequests, 1);
  assert.equal(hook.eventDataMessage.value, '本快照未提供事件数据');
  saved.value = analysis([
    {
      evidence_id: 'e',
      evidence_type: 'event',
      evidence_descriptor: { kind: 'event', name: 'BackOff', source: 'k8s' },
      response: { meta: { status: 'OK' }, data: [{ time: 1700000000000, event_level: 'warning' }] },
    },
  ]);
  await hook.getEventsData();
  assert.equal(eventRequests, 1);
  assert.equal(hook.allEventsData.value[0].event_name, 'BackOff');
  assert.equal(hook.disableEventAnalysis.value, false);
  delete global.localStorage;
});
