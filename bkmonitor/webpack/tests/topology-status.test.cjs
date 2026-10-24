const assert = require('node:assert/strict');
const test = require('node:test');
const { load } = require('./helpers/topology-history-harness.cjs');
const response = status => ({ status, latest: { nodes: [] }, diff: [], complete: { nodes: [], edges: [], combos: [], sub_combos: [] } });
function harness(responses) {
  const state = Object.fromEntries(Object.entries({ loading: false, wrapRef: {}, incidentId: '1700000000000001', errorData: {}, timelinePosition: 0, refreshTime: -1, resourceNodeId: '', nodeEntityId: '', nodeEntityName: '' }).map(([key, value]) => [key, { value }]));
  const { useTopoData } = load('composables/use-topo-data.ts', { 'monitor-api/modules/incident': { incidentTopology: async () => {
    const next = responses.shift(); if (next instanceof Error) throw next; return next;
  } } });
  const data = useTopoData(state, { getGraph: () => null });
  return { state, data };
}
test('real data hook distinguishes no result, failed sync, invalid data and transport failure', async () => {
  const h = harness([response('NO_DATA'), response('SYNC_FAILED'), response('INVALID_DATA'), new Error('private transport details')]);
  for (const reason of ['no_result', 'sync_failed', 'invalid_data', 'query_failed']) {
    await h.data.getGraphData();
    assert.equal(h.state.errorData.value.reason, reason);
    assert.equal(h.state.loading.value, false);
    assert.ok(!h.state.errorData.value.msg.includes('private'));
  }
});
test('empty graph with a category is no result; successful retry clears all stale error fields', async () => {
  const empty = response('OK'); empty.complete.combos.push({ id: '0' });
  const valid = response('OK');
  valid.complete.combos.push({ id: '0' });
  valid.complete.nodes.push({ id: 'a', comboId: '0', entity: { entity_id: 'a', entity_name: 'a', is_root: true } });
  valid.latest = structuredClone(valid.complete);
  valid.diff.push({ create_time: 1, content: structuredClone(valid.complete) });
  const h = harness([empty, response('SYNC_FAILED'), valid]);
  let initialized = 0; h.data.registerInitGraphCallback(() => initialized++);
  await h.data.getGraphData(); assert.equal(h.state.errorData.value.reason, 'no_result'); assert.equal(initialized, 0);
  await h.data.getGraphData(); assert.equal(h.state.errorData.value.reason, 'sync_failed');
  await h.data.getGraphData(); assert.deepEqual(h.state.errorData.value, { isError: false, isNoData: false, msg: '' });
  assert.equal(initialized, 1);
});
test('legacy malformed topology reports invalid data before layout', async () => {
  const invalid = response('OK'); invalid.complete.nodes.push({ id: 'a', comboId: 'missing' });
  const malformed = response('OK'); malformed.complete.edges = {};
  const badFrame = response('OK'); badFrame.diff = [{ content: { nodes: null } }];
  const h = harness([invalid, malformed, badFrame]);
  for (let index = 0; index < 3; index++) {
    await h.data.getGraphData();
    assert.equal(h.state.errorData.value.reason, 'invalid_data');
  }
});

test('actual page render binds distinct titles and retains the canvas container across failures', () => {
  const fs = require('node:fs');
  const path = require('node:path');
  const ts = require('typescript');
  const vue = require('node:module').createRequire(path.resolve(__dirname, '../src/trace/package.json'))('vue');
  const source = ts.createSourceFile('failure-topo.tsx', fs.readFileSync(path.join(__dirname, '../src/trace/pages/failure/failure-topo/failure-topo.tsx'), 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  let body;
  function visit(node) {
    if (ts.isMethodDeclaration(node) && node.name.getText(source) === 'render') body = node.body.getText(source);
    ts.forEachChild(node, visit);
  }
  visit(source); assert.ok(body);
  const code = ts.transpileModule(`function render() ${body}`, { compilerOptions: { target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.React, jsxFactory: 'h', jsxFragmentFactory: 'Fragment' } }).outputText;
  const names = ['DataAccess', 'ExceptionComp', 'TopoTools', 'Loading', 'Popover', 'LegendPopoverContent', 'Slider', 'ResourceGraph', 'FailureTopoDetail', 'FeedbackCauseDialog', 'FailureTopoTooltips'];
  const render = new Function('h', 'Fragment', ...names, `${code}; return render;`)(vue.h, vue.Fragment, ...names);
  const { topologyFailure } = load('graph/topology-status.ts');
  for (const reason of ['no_result', 'sync_failed', 'invalid_data', 'layout_failed', 'query_failed', null]) {
    const state = new Proxy({ topoStatus: 'normal', isPlay: false, showResourceGraph: false, showServiceOverview: false, topoRawDataCache: { diff: [] }, errorData: reason ? topologyFailure(reason, x => x) : { isError: false, isNoData: false }, t: x => x }, { get: (target, key) => key in target ? target[key] : () => {} });
    const tree = render.call(state); const nodes = [];
    function walk(node) { if (!node || typeof node !== 'object') return; nodes.push(node); if (Array.isArray(node.children)) node.children.forEach(walk); } walk(tree);
    const exception = nodes.find(node => node.type === 'ExceptionComp');
    assert.equal(Boolean(exception), Boolean(reason));
    if (reason) assert.equal(exception.props.title, state.errorData.title);
    assert.equal(nodes.filter(node => node.props?.id === 'topo-graph').length, 1);
    assert.ok(nodes.some(node => node.props?.style?.display === (reason ? 'none' : 'block')));
  }
});
