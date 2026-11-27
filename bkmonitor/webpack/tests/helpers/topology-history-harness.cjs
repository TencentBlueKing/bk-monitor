const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const base = path.resolve(__dirname, '../../src/trace/pages/failure/failure-topo');
function load(file, imports = {}) {
  const filename = path.resolve(base, file);
  const code = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true },
  }).outputText;
  const module = { exports: {} };
  const boundary = name => {
    if (Object.hasOwn(imports, name)) return imports[name];
    if (name === 'vue-i18n') return { useI18n: () => ({ t: value => value }) };
    if (name === 'monitor-common/utils/utils.js') return { deepClone: structuredClone, random: () => 'animation' };
    if (name.endsWith('service-combo')) return { default: { labelChange() {} }, __esModule: true };
    if (name.startsWith('.')) return load(path.relative(base, path.resolve(path.dirname(filename), name + '.ts')), imports);
    return require(name);
  };
  new Function('require', 'module', 'exports', code)(boundary, module, module.exports);
  return module.exports;
}
const history = load('graph/topology-history.ts');
const topologyEdgeId = load('snapshot-analysis.ts').topologyEdgeId;
const utils = load('graph/elkjs-utils.ts').default;
const format = load('graph/format-topo-data.ts').default;
async function layout(response) {
  const data = structuredClone(response.complete);
  data.combos = history.historyCombos(data, response.latest);
  history.validateTopology(data);
  for (const node of data.nodes) Object.assign(node, { width: 90, height: 92, comboId: utils.getComboId(node.comboId), subComboId: utils.getComboId(node.subComboId) });
  for (const combo of data.combos) Object.assign(combo, { id: utils.getComboId(combo.id), isCombo: true });
  const subCombos = (data.sub_combos ?? []).map(combo => ({ ...combo, id: utils.getComboId(combo.id), comboId: utils.getComboId(combo.comboId) }));
  utils.setSubCombosMap(utils.getSubComboCountMap(data.nodes));
  data.combos.push(...utils.resolveSumbCombos(subCombos));
  const raw = utils.getTopoRawData(data.combos, data.edges, data.nodes);
  const converted = format(raw);
  return { graph: await utils.getLayoutData(utils.getKlayGraphData({ nodes: converted.layoutNodes, edges: converted.edges })), raw };
}
function timelineHarness(response) {
  const cache = structuredClone(response);
  history.prepareHistoryFrames(cache.diff);
  const items = new Map();
  const makeItem = model => {
    const item = { model: { ...model }, _cfg: { visible: true }, getModel() { return this.model; }, isVisible() { return this._cfg.visible; }, getEdges() { return edges.filter(e => e.model.source === model.id || e.model.target === model.id); }, show() { this._cfg.visible = true; }, hide() { this._cfg.visible = false; } };
    items.set(model.id, item);
    return item;
  };
  const nodes = cache.complete.nodes.map(makeItem);
  const edges = cache.complete.edges.map(e => makeItem({ ...e, id: load('snapshot-analysis.ts').topologyEdgeId(e) }));
  const combos = [
    ...history.historyCombos(cache.complete, cache.latest),
    ...(cache.complete.sub_combos ?? []).map(combo => ({ ...combo, parentId: combo.parentId ?? combo.comboId })),
  ].map(makeItem);
  const graph = { getNodes: () => nodes, setItemState(item, state) { if (state === "show-animate") item.show(); }, findById: id => items.get(id), getEdges: () => edges, getCombos: () => combos, showItem: i => { i.show(); if (combos.includes(i)) nodes.filter(n => n.model.comboId === i.model.id).forEach(n => n.show()); }, hideItem: i => { i.hide(); if (combos.includes(i)) nodes.filter(n => n.model.comboId === i.model.id).forEach(n => n.hide()); }, updateItem: (i, m) => { i.model = { ...i.model, ...m }; } };
  const state = Object.fromEntries(['refreshTime', 'isPlay', 'showResourceGraph', 'showServiceOverview', 'timelinePosition'].map(k => [k, { value: false }]));
  const { useTopoTimeline } = load('composables/use-topo-timeline.ts');
  const identity = load('snapshot-analysis.ts').topologyEdgeId;
  const timeline = useTopoTimeline(state, { topoRawDataCache: { value: cache }, findEdges: (es, e) => es.find(x => identity(x) === identity(e)), clearRefreshTimeout() {}, handleChangeRefleshTime() {} }, { getGraph: () => graph }, () => {});
  return { timeline, nodes, edges, combos, cache, state };
}
function renderGraphHarness(timelineCache = { diff: [], complete: { nodes: [], edges: [], combos: [] } }) {
  const cache = structuredClone(timelineCache);
  history.prepareHistoryFrames(cache.diff ?? []);
  const source = ts.createSourceFile(
    'use-topo-graph.ts',
    fs.readFileSync(path.join(base, 'composables/use-topo-graph.ts'), 'utf8'),
    ts.ScriptTarget.Latest,
    true
  );
  let initializer;
  function visit(node) {
    if (ts.isVariableDeclaration(node) && node.name.getText(source) === 'renderGraph') initializer = node.initializer.getText(source);
    ts.forEachChild(node, visit);
  }
  visit(source);
  assert(initializer);
  const code = ts.transpileModule(`const renderGraph = ${initializer};`, {
    compilerOptions: { target: ts.ScriptTarget.ES2020 },
  }).outputText;

  let nodeItems = [];
  let edgeItems = [];
  let comboItems = [];
  const items = new Map();
  const makeItem = model => {
    let visible = true;
    return {
      model: { ...model },
      _cfg: { visible: true },
      getModel() {
        return this.model;
      },
      isVisible() {
        return visible;
      },
      show() {
        visible = true;
        this._cfg.visible = true;
      },
      hide() {
        visible = false;
        this._cfg.visible = false;
      },
      getEdges() {
        return edgeItems.filter(edge => edge.model.source === this.model.id || edge.model.target === this.model.id);
      },
    };
  };
  const graph = {
    data(data) {
      nodeItems = (data.nodes ?? []).map(makeItem);
      edgeItems = (data.edges ?? []).map(edge => makeItem({ ...edge, id: edge.id ?? topologyEdgeId(edge) }));
      comboItems = (data.combos ?? []).map(makeItem);
      items.clear();
      for (const item of [...nodeItems, ...edgeItems, ...comboItems]) items.set(item.model.id, item);
    },
    render() {},
    get(key) {
      // 测试桩中 Graph 始终未销毁；版本号校验已覆盖卸载场景，此处仅满足接口契约
      return key === 'destroyed' ? false : undefined;
    },
    findById(id) {
      return items.get(id);
    },
    getNodes() {
      return nodeItems;
    },
    getEdges() {
      return edgeItems;
    },
    getCombos() {
      return comboItems;
    },
    showItem(item) {
      item?.show?.();
    },
    hideItem(item) {
      item?.hide?.();
    },
    updateItem(item, model) {
      item.model = { ...item.model, ...model };
    },
    setItemState(item, state) {
      if (state === 'running') item?.show?.();
    },
  };
  const ref = value => ({ value });
  const initialTimelinePosition = Math.max(0, (cache.diff?.length ?? 1) - 1);
  const timelineState = {
    isPlay: ref(false),
    refreshTime: ref(-1),
    resizeCacheCallback: ref(null),
    resourceNodeId: ref(''),
    showResourceGraph: ref(false),
    showServiceOverview: ref(false),
    timelinePosition: ref(initialTimelinePosition),
  };
  const { useTopoTimeline } = load('composables/use-topo-timeline.ts');
  const timeline = useTopoTimeline(
    timelineState,
    {
      topoRawDataCache: ref(cache),
      findEdges: () => undefined,
      clearRefreshTimeout() {},
      handleChangeRefleshTime() {},
    },
    { getGraph: () => graph },
    () => {}
  );
  const state = {
    errorData: ref({}),
    graphInstanceRef: ref(graph),
    graphRef: ref({ clientWidth: 100, clientHeight: 100 }),
    g6TooltipRef: ref(undefined),
    incidentDetailData: ref({}),
    isPlay: ref(false),
    isRenderComplete: ref(false),
    resourceEdgeId: ref(''),
    resourceNodeId: ref(''),
    rootComboMovePoint: ref({ x: null, y: null }),
    resizeCacheCallback: ref(null),
    timelinePosition: ref(initialTimelinePosition),
    tooltipCompRef: ref({}),
    zoomValue: ref(1),
  };
  const topoData = {
    topoRawDataCache: ref(cache),
    resolveLayout: async data => ({ data, layouted: null }),
    moveToCenterIfNeeded() {},
  };
  const interaction = {
    setHighlightEdge() {},
    handleZoomChange() {},
    toFrontAnomalyEdge() {},
  };
  const renderGraph = new Function(
    'getGraph',
    'clearEdgeIntervals',
    'topoData',
    'state',
    'interaction',
    'timeline',
    't',
    'localStorage',
    'setTimeout',
    'renderVersion',
    'toFrontEdgeTimer',
    `${code}; return renderGraph;`
  )(
    () => graph,
    () => {},
    topoData,
    state,
    interaction,
    timeline,
    value => value,
    { getItem: () => null },
    () => {},
    0,
    null
  );
  return { renderGraph, nodes: () => nodeItems, edges: () => edgeItems, combos: () => comboItems };
}

async function autoRefreshHarness(response) {
  const ref = value => ({ value });
  const state = {
    errorData: ref({}),
    incidentId: ref('incident-id'),
    isPlay: ref(false),
    loading: ref(false),
    nodeEntityId: ref(''),
    nodeEntityName: ref(''),
    refreshTime: ref(-1),
    resourceNodeId: ref(''),
    timelinePosition: ref(0),
    wrapRef: ref({}),
  };
  const { useTopoData } = load('composables/use-topo-data.ts', {
    'monitor-api/modules/incident': {
      incidentTopology: async () => structuredClone(response),
    },
  });
  const data = useTopoData(state, { getGraph: () => ({}) });
  const renders = [];
  data.registerRenderGraphCallback((renderData, renderComplete) => renders.push({ renderData, renderComplete }));
  await data.getGraphData(true);
  return { data, renders, state };
}

module.exports = { autoRefreshHarness, load, history, layout, renderGraphHarness, timelineHarness };
