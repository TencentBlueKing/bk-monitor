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
    if (name === 'vue') return require('node:module').createRequire(path.resolve(__dirname, '../../src/trace/package.json'))('vue');
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
  const combos = history.historyCombos(cache.complete, cache.latest).map(makeItem);
  const graph = { getNodes: () => nodes, setItemState(item, state) { if (state === "show-animate") item.show(); }, findById: id => items.get(id), getEdges: () => edges, getCombos: () => combos, showItem: i => { i.show(); if (combos.includes(i)) nodes.filter(n => n.model.comboId === i.model.id).forEach(n => n.show()); }, hideItem: i => { i.hide(); if (combos.includes(i)) nodes.filter(n => n.model.comboId === i.model.id).forEach(n => n.hide()); }, updateItem: (i, m) => { i.model = { ...i.model, ...m }; } };
  const state = Object.fromEntries(['refreshTime', 'isPlay', 'showResourceGraph', 'showServiceOverview', 'timelinePosition'].map(k => [k, { value: false }]));
  const { useTopoTimeline } = load('composables/use-topo-timeline.ts');
  const identity = load('snapshot-analysis.ts').topologyEdgeId;
  const timeline = useTopoTimeline(state, { topoRawDataCache: { value: cache }, findEdges: (es, e) => es.find(x => identity(x) === identity(e)), clearRefreshTimeout() {}, handleChangeRefleshTime() {} }, { getGraph: () => graph }, () => {});
  return { timeline, nodes, edges, combos, cache, state };
}
module.exports = { load, history, layout, timelineHarness };
